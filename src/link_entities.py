"""Stage 4: establish identity links with identifiers and recorded evidence."""
import argparse
import csv
import re
from collections import Counter

from rdflib import Graph, OWL, URIRef

from common import BRONZE, RES, fetch_json, now, qid, read_json, read_tables, resource, write_json
from transform import ENTITY_MAP

SPARQL_FORMATS = {"Wikidata": "json", "DBpedia": "application/sparql-results+json"}


def exact_dbpedia_links(bindings, requested_qids):
    mapping = {}
    for row in bindings:
        identifier = qid(row.get("wd", {}).get("value"))
        uri = row.get("entity", {}).get("value", "")
        if identifier in requested_qids and uri.startswith("http://dbpedia.org/resource/") and " " not in uri:
            mapping.setdefault(identifier, []).append(uri)
    return {identifier: sorted(set(uris)) for identifier, uris in mapping.items()}


def link(offline=False, ror_limit=10):
    tables = read_tables()
    cache_path = BRONZE / "external_lookups.json"
    cache = read_json(cache_path) if offline else {"requests": {}, "warnings": []}
    evidence, graph = [], Graph()
    graph.bind("owl", OWL)
    checked = now()

    def lookup(key, url, query, source):
        if offline:
            if key not in cache["requests"]:
                cache.setdefault("warnings", []).append(f"No cached {source} response for {key}")
                return {"results": {"bindings": []}}
            return cache["requests"][key]["response"]
        try:
            response = fetch_json(url, {"query": query, "format": SPARQL_FORMATS[source]},
                                  accept="application/sparql-results+json")
            cache["requests"][key] = {"endpoint": url, "query": query, "source": source,
                                      "retrieved_at": checked, "response": response}
            return response
        except RuntimeError as exc:
            cache.setdefault("warnings", []).append(str(exc))
            print(f"Warning: {source} lookup failed; no links invented", flush=True)
            return {"results": {"bindings": []}}

    def accept(local, external, method, source, shared="", observed_at=None):
        graph.add((local, OWL.sameAs, URIRef(external)))
        evidence.append({"local_uri": str(local), "external_uri": external, "predicate": str(OWL.sameAs),
                         "method": method, "shared_identifier": shared, "evidence_source": source,
                         "status": "accepted", "checked_at": observed_at or checked})

    manifest = read_json(BRONZE / "collection_manifest.json")
    collected_at = manifest["retrieved_at"]
    for table, (kind, _) in ENTITY_MAP.items():
        if table == "authorships":
            continue  # OpenAlex has no independent authorship entity identifier.
        for row in tables[table]:
            accept(resource(kind, row["id"]), row["id"], "exact_openalex_id", row["id"], row["id"], collected_at)

    # Full OpenAlex organization/source records declare external Wikidata IDs.
    entities = [("institution", row) for row in tables["institutions"]] + [("source", row) for row in tables["sources"]]
    wd_ids = {row["id"]: row["wikidata_id"] for _, row in entities if row["wikidata_id"]}
    ror_checked_at = {}
    missing = [row for row in tables["institutions"] if not row["wikidata_id"]
               and re.fullmatch(r"https://ror\.org/[a-z0-9]{9}", row["ror"])][:ror_limit]
    if missing:
        rors = {row["ror"].rsplit("/", 1)[-1] for row in missing}
        values = " ".join('"' + value + '"' for value in sorted(rors))
        query = f"SELECT ?entity ?ror WHERE {{ VALUES ?ror {{ {values} }} ?entity <http://www.wikidata.org/prop/direct/P6782> ?ror . }}"
        key = "wikidata-ror:" + ",".join(sorted(rors))
        response = lookup(key, "https://query.wikidata.org/sparql", query, "Wikidata")
        matches = {}
        for binding in response.get("results", {}).get("bindings", []):
            identifier = qid(binding.get("entity", {}).get("value"))
            ror = binding.get("ror", {}).get("value")
            if identifier and ror in rors:
                matches.setdefault(ror, set()).add(identifier)
        for row in missing:
            candidates = matches.get(row["ror"].rsplit("/", 1)[-1], set())
            if len(candidates) == 1:
                wd_ids[row["id"]] = next(iter(candidates))
                ror_checked_at[row["id"]] = cache["requests"][key]["retrieved_at"]
            elif len(candidates) > 1:
                cache.setdefault("warnings", []).append(f"Ambiguous ROR match not accepted: {row['ror']}")

    for kind, row in entities:
        if row["id"] in wd_ids:
            method = "openalex_declared_wikidata_id" if row["wikidata_id"] else "exact_ror_P6782"
            source = row["id"] if row["wikidata_id"] else "https://query.wikidata.org/sparql"
            accept(resource(kind, row["id"]), f"http://www.wikidata.org/entity/{wd_ids[row['id']]}",
                   method, source, row["ror"] if kind == "institution" and method == "exact_ror_P6782" else wd_ids[row["id"]],
                   collected_at if row["wikidata_id"] else ror_checked_at[row["id"]])

    requested = set(wd_ids.values())
    dbpedia, dbpedia_checked_at = {}, {}
    # Bound-object lookups use the identity index. Multiple-QID VALUES queries
    # returned repeated 503 errors on the public endpoint during validation.
    ordered = sorted(requested)
    for identifier in ordered:
        target = f"<http://www.wikidata.org/entity/{identifier}>"
        query = f"SELECT ?entity ?wd WHERE {{ ?entity <http://www.w3.org/2002/07/owl#sameAs> {target} . BIND({target} AS ?wd) }}"
        key = "dbpedia-wikidata:" + identifier
        response = lookup(key, "https://dbpedia.org/sparql", query, "DBpedia")
        matches = exact_dbpedia_links(response.get("results", {}).get("bindings", []), {identifier})
        dbpedia.update(matches)
        if matches:
            for identifier in matches:
                dbpedia_checked_at[identifier] = cache["requests"][key]["retrieved_at"]
    for kind, row in entities:
        identifier = wd_ids.get(row["id"])
        for target in dbpedia.get(identifier, []):
            accept(resource(kind, row["id"]), target, "dbpedia_declared_sameAs_wikidata",
                   "https://dbpedia.org/sparql", identifier, dbpedia_checked_at[identifier])

    RES.mkdir(parents=True, exist_ok=True)
    graph.serialize(RES / "linked_output.nt", format="nt", encoding="utf-8")
    columns = ["local_uri", "external_uri", "predicate", "method", "shared_identifier", "evidence_source", "status", "checked_at"]
    with (RES / "entity_links.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(sorted(evidence, key=lambda row: (row["local_uri"], row["external_uri"])))
    counts = Counter(row["method"] for row in evidence)
    report = {"generated_at": checked, "mode": "offline-cache" if offline else "live",
              "triples": len(graph), "by_method": dict(counts), "external_candidates": len(entities),
              "wikidata_entities": len(wd_ids), "dbpedia_entities": len(dbpedia), "warnings": cache.get("warnings", [])}
    write_json(RES / "linking-report.json", report)
    if not offline:
        write_json(cache_path, cache)
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use recorded external responses; no network requests")
    parser.add_argument("--ror-limit", type=int, default=10)
    args = parser.parse_args()
    if not 0 <= args.ror_limit <= 200:
        parser.error("--ror-limit must be 0..200")
    link(args.offline, args.ror_limit)
