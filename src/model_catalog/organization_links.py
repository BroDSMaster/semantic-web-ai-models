"""Collect and verify exact local-organization identities in OpenAlex."""
import json
from urllib.parse import urlparse

from .common import BRONZE, RES, ROOT, atomic_write, digest, fetch, now, read_json, uri, write_json


def normalized_qid(value):
    return str(value or "").rstrip("/").rsplit("/", 1)[-1]


def verify_institution(organization, candidate, entity):
    """Return reasons that prevent an owl:sameAs assertion."""
    reasons = []
    target = "https://openalex.org/" + candidate["openalex_id"]
    if organization.get("id") != uri("organization", candidate["local_key"]):
        reasons.append("local organization URI differs")
    if organization.get("name") != candidate["local_name"]:
        reasons.append("local organization name differs")
    if entity.get("id") != target or (entity.get("ids") or {}).get("openalex") != target:
        reasons.append("OpenAlex institution ID differs")
    if entity.get("display_name") != candidate["display_name"]:
        reasons.append("OpenAlex display name differs")
    if entity.get("type") != candidate["type"]:
        reasons.append("OpenAlex institution type differs")
    if entity.get("ror") != candidate["ror"] or (entity.get("ids") or {}).get("ror") != candidate["ror"]:
        reasons.append("OpenAlex ROR differs")
    hostname = (urlparse(entity.get("homepage_url") or "").hostname or "").removeprefix("www.")
    if hostname not in candidate["homepage_domains"]:
        reasons.append("OpenAlex official homepage domain differs")
    if candidate.get("wikidata") and normalized_qid((entity.get("ids") or {}).get("wikidata")) != candidate["wikidata"]:
        reasons.append("OpenAlex Wikidata QID differs")
    return reasons


def snapshot(content, openalex_id, url):
    checksum = digest(content)
    path = BRONZE / "documents" / f"openalex-{openalex_id}-{checksum}.json"
    atomic_write(path, content)
    return {"url": url, "sha256": checksum, "snapshot_file": str(path.relative_to(ROOT)), "retrieved_at": now()}


def checked_payload(source):
    path = (ROOT / source["snapshot_file"]).resolve()
    if not path.is_relative_to((BRONZE / "documents").resolve()):
        raise ValueError("OpenAlex snapshot path outside Bronze documents")
    content = path.read_bytes()
    if digest(content) != source["sha256"]:
        raise ValueError("OpenAlex snapshot SHA-256 mismatch")
    return json.loads(content)


def collect_openalex_links():
    records = []
    for candidate in read_json(RES / "openalex-organization-mappings.json")["organizations"]:
        openalex_id = candidate["openalex_id"]
        url = "https://api.openalex.org/institutions/" + openalex_id
        record = {"local_key": candidate["local_key"], "openalex_id": openalex_id}
        try:
            record["source"] = snapshot(fetch(url, {"Accept": "application/json"}), openalex_id, url)
        except (RuntimeError, ValueError) as exc:
            record["warning"] = str(exc)
        records.append(record)
    write_json(BRONZE / "openalex_lookups.json", records)
    return records


def verified_openalex_links(tables, records):
    """Replay source bytes and return accepted link rows plus audit decisions."""
    organizations = {row["id"]: row for row in tables["organizations"]}
    candidates = {row["local_key"]: row for row in read_json(RES / "openalex-organization-mappings.json")["organizations"]}
    links, decisions = [], []
    for record in records:
        key = record.get("local_key")
        candidate = candidates.get(key)
        organization = organizations.get(uri("organization", key)) if key else None
        reasons = []
        source = record.get("source")
        if not candidate or not organization:
            reasons.append("no reviewed candidate or no exact local organization")
        elif record.get("openalex_id") != candidate["openalex_id"]:
            reasons.append("cached OpenAlex ID differs from reviewed mapping")
        elif not source:
            reasons.append("OpenAlex source evidence is absent")
        else:
            expected_url = "https://api.openalex.org/institutions/" + candidate["openalex_id"]
            try:
                if source["url"] != expected_url:
                    raise ValueError("OpenAlex source URL differs from reviewed institution")
                entity = checked_payload(source)
                reasons.extend(verify_institution(organization, candidate, entity))
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                reasons.append("unverifiable OpenAlex evidence: " + str(exc))
        decision = {"local_key": key, "openalex_id": record.get("openalex_id"),
                    "status": "rejected" if reasons else "accepted", "reasons": reasons}
        decisions.append(decision)
        if reasons:
            continue
        target = "https://openalex.org/" + candidate["openalex_id"]
        reason = "Exact local organization ID/name; OpenAlex institution ID/name, company type, official homepage domain and ROR confirmed"
        if candidate.get("wikidata"):
            reason += "; Wikidata QID also confirmed"
        links.append({"subject": organization["id"], "target": target, "source_url": source["url"],
                      "retrieved_at": source["retrieved_at"], "reason": reason,
                      "sha256": source["sha256"], "snapshot_file": source["snapshot_file"]})
        decision["evidence"] = source
    return links, decisions


if __name__ == "__main__":
    print(f"Collected {len(collect_openalex_links())} reviewed OpenAlex organization candidates")
