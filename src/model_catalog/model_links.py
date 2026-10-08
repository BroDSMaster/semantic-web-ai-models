"""Conservative model identities with replayable, checksum-bound source evidence."""
import json
from urllib.parse import urlencode

from .common import BRONZE, RES, ROOT, atomic_write, digest, fetch, now, read_json, uri, write_json


def values(entity, prop):
    return [c.get("mainsnak", {}).get("datavalue", {}).get("value")
            for c in entity.get("claims", {}).get(prop, []) if c.get("rank") != "deprecated"]


def verify_identity(model, candidate, entity):
    """Return rejection reasons; an empty list permits this exact candidate only."""
    reasons = []
    if model.get("id") != uri("model", "openrouter:" + candidate["source_id"]):
        reasons.append("local URI does not identify the reviewed source model")
    if model.get("source_id") != candidate["source_id"]:
        reasons.append("source ID/version differs from reviewed candidate")
    if model.get("name", "").removeprefix("OpenAI: ") != candidate["label"]:
        reasons.append("local model label differs from reviewed identity")
    if model.get("developer_id") != uri("organization", candidate["developer_id"]):
        reasons.append("local developer differs from reviewed developer")
    if entity.get("id") != candidate["qid"]:
        reasons.append("Wikidata entity ID differs")
    if entity.get("labels", {}).get("en", {}).get("value") != candidate["label"]:
        reasons.append("Wikidata model/version label differs")
    if candidate["developer_qid"] not in [v.get("id") for v in values(entity, "P178") if isinstance(v, dict)]:
        reasons.append("Wikidata developer P178 not confirmed")
    if candidate["type_qid"] not in [v.get("id") for v in values(entity, "P31") if isinstance(v, dict)]:
        reasons.append("Wikidata model type P31 not confirmed")
    if not set(candidate["official_urls"]).intersection(v for v in values(entity, "P856") if isinstance(v, str)):
        reasons.append("exact official model page P856 not confirmed")
    return reasons


def snapshot(content, prefix, url):
    checksum = digest(content)
    path = BRONZE / "documents" / f"{prefix}-{checksum}.json"
    atomic_write(path, content)
    return {"url": url, "sha256": checksum, "snapshot_file": str(path.relative_to(ROOT)), "retrieved_at": now()}


def checked_payload(source):
    """Reject absent/tampered files and paths outside the evidence directory."""
    path = (ROOT / source["snapshot_file"]).resolve()
    if not path.is_relative_to((BRONZE / "documents").resolve()):
        raise ValueError("snapshot path outside Bronze documents")
    content = path.read_bytes()
    if digest(content) != source["sha256"]:
        raise ValueError("snapshot SHA-256 mismatch")
    return json.loads(content)


def collect_model_links():
    records = []
    for candidate in read_json(RES / "model-identity-mappings.json")["models"]:
        qid = candidate["qid"]
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        record = {"source_id": candidate["source_id"], "qid": qid}
        try:
            record["wikidata_source"] = snapshot(fetch(url), "wikidata-" + qid, url)
            # The inverse sameAs assertion is the DBpedia evidence; do not guess a page slug.
            query = "SELECT ?entity WHERE { ?entity <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/" + qid + "> } LIMIT 20"
            endpoint = "https://dbpedia.org/sparql?" + urlencode({"query": query, "format": "application/sparql-results+json"})
            try:
                record["dbpedia_source"] = snapshot(fetch(endpoint, {"Accept": "application/sparql-results+json"}), "dbpedia-" + qid, endpoint)
            except (RuntimeError, ValueError) as exc:
                record["dbpedia_warning"] = str(exc)
        except (RuntimeError, ValueError) as exc:
            record["warning"] = str(exc)
        records.append(record)
    write_json(BRONZE / "model_lookups.json", records)
    return records


def verified_model_links(tables, records):
    """Return accepted mappings and audit decisions; re-check evidence during offline export."""
    models = {m["source_id"]: m for m in tables["models"]}
    candidates = {c["source_id"]: c for c in read_json(RES / "model-identity-mappings.json")["models"]}
    accepted, decisions = [], []
    # Read original catalog bytes, not merely the editable Silver rows.
    catalog, catalog_evidence, catalog_error = {}, [], ""
    try:
        manifest = read_json(BRONZE / "manifest.json")
        for doc in manifest["documents"]:
            if doc["url"] == manifest["catalog_url"]:
                source = {"url": doc["url"], "sha256": doc["sha256"],
                          "snapshot_file": str((BRONZE / doc["file"]).relative_to(ROOT)),
                          "retrieved_at": doc["retrieved_at"]}
                payload = checked_payload(source)
                catalog.update({m["id"]: m for m in payload["data"]})
                catalog_evidence.append(source)
        if not catalog_evidence:
            raise ValueError("no original catalog evidence")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        catalog_error = "unverifiable local catalog: " + str(exc)
    for record in records:
        key = record.get("source_id")
        candidate, model = candidates.get(key), models.get(key)
        reasons = []
        if not candidate or not model:
            reasons.append("no reviewed candidate or no exact local model")
        elif record.get("qid") != candidate["qid"]:
            reasons.append("cached candidate QID differs from reviewed mapping")
        else:
            try:
                if catalog_error:
                    raise ValueError(catalog_error)
                raw = catalog.get(key, {})
                if raw.get("name") != model["name"] or raw.get("id") != model["source_id"]:
                    raise ValueError("local model does not match original catalog ID/name")
                source = record["wikidata_source"]
                expected_url = f"https://www.wikidata.org/wiki/Special:EntityData/{candidate['qid']}.json"
                if source["url"] != expected_url:
                    raise ValueError("Wikidata source URL differs from reviewed entity")
                entity = checked_payload(source)["entities"][candidate["qid"]]
                reasons.extend(verify_identity(model, candidate, entity))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                reasons.append("unverifiable Wikidata evidence: " + str(exc))
        decision = {"source_id": key, "qid": record.get("qid"), "status": "rejected" if reasons else "accepted", "reasons": reasons}
        decisions.append(decision)
        if reasons:
            continue
        reason = "Exact reviewed source ID and model label; Wikidata P178 developer, P31 model type and exact P856 official model page confirmed. No snapshot/serving-mode propagation."
        accepted.append({"subject": model["id"], "target": "http://www.wikidata.org/entity/" + candidate["qid"],
                         "source_url": source["url"], "retrieved_at": source["retrieved_at"], "reason": reason,
                         "sha256": source["sha256"], "snapshot_file": source["snapshot_file"]})
        decision["wikidata_evidence"] = source
        decision["catalog_evidence"] = catalog_evidence
        if record.get("dbpedia_source"):
            try:
                dbsource = record["dbpedia_source"]
                expected_query = "SELECT ?entity WHERE { ?entity <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/" + candidate["qid"] + "> } LIMIT 20"
                expected_db_url = "https://dbpedia.org/sparql?" + urlencode({"query": expected_query, "format": "application/sparql-results+json"})
                if dbsource["url"] != expected_db_url:
                    raise ValueError("DBpedia evidence query does not match the verified QID")
                bindings = checked_payload(dbsource)["results"]["bindings"]
                targets = sorted({r.get("entity", {}).get("value", "") for r in bindings
                                  if r.get("entity", {}).get("type") == "uri" and
                                  r.get("entity", {}).get("value", "").startswith("http://dbpedia.org/resource/")})
                for target in targets:
                    accepted.append({"subject": model["id"], "target": target, "source_url": dbsource["url"],
                                     "retrieved_at": dbsource["retrieved_at"], "reason": "DBpedia explicitly asserts owl:sameAs to the independently verified model Wikidata QID.",
                                     "sha256": dbsource["sha256"], "snapshot_file": dbsource["snapshot_file"]})
                decision["dbpedia_targets"] = targets
                decision["dbpedia_evidence"] = dbsource
            except (OSError, ValueError, KeyError, TypeError) as exc:
                decision["dbpedia_warning"] = str(exc)
        elif record.get("dbpedia_warning"):
            decision["dbpedia_warning"] = record["dbpedia_warning"]
    return accepted, decisions


if __name__ == "__main__":
    print(f"Collected {len(collect_model_links())} reviewed model candidates")
