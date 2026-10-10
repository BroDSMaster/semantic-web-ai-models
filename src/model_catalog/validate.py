"""Validate collected catalog, RDF provenance and every shipped SPARQL query."""
import json
import time
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL

from .common import BRONZE, GOLD, RES, ROOT, digest, read_json, read_tables, write_json, provider_kind
from .transform import EX, PROV, SCHEMA, build_graph, load_model_graph


def validate():
    tables = read_tables()
    graph = load_model_graph()
    errors, warnings = [], []
    from .shacl import validate_shacl
    print("Checking SHACL constraints...", flush=True)
    shacl_report = validate_shacl(graph)
    if not shacl_report["conforms"]:
        errors.append(f"SHACL failed: {shacl_report['result_count']} results; see res/shacl-report.json")
    model_ids = {r["id"] for r in tables["models"]}
    docs = {r["id"] for r in tables["documents"]}
    offerings = {r["id"] for r in tables["offerings"]}
    for row in tables["prices"]:
        if row["offering_id"] not in offerings or row["document_id"] not in docs:
            errors.append("Dangling price " + row["id"])
    for row in tables["evaluations"]:
        if row["model_id"] not in model_ids or row["document_id"] not in docs:
            errors.append("Dangling evaluation " + row["id"])
    manifest = read_json(BRONZE / "manifest.json")
    from .wikidata_links import checked_payload, verified_links, dbpedia_url
    identity_records = read_json(BRONZE / 'external_lookups.json')
    expected_identity, identity_decisions = verified_links(tables, identity_records)
    for record in identity_records:
        for key, url in [('source', 'https://www.wikidata.org/wiki/Special:EntityData/' + record['qid'] + '.json'),
                         ('dbpedia_source', dbpedia_url(record['qid']))]:
            if record.get(key):
                try:
                    checked_payload(record[key], url)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors.append('Wikidata/DBpedia identity evidence invalid: ' + str(exc))
    expected_pairs = {(r['subject'], r['target']) for r in expected_identity}
    actual_pairs = {(str(s), str(t)) for s, t in graph.subject_objects(OWL.sameAs)
                    if str(t).startswith(('http://www.wikidata.org/', 'http://dbpedia.org/'))}
    if expected_pairs != actual_pairs:
        errors.append('Wikidata/DBpedia RDF links differ from independently replayed evidence')
    for row in tables['organizations']:
        if provider_kind(row['id']) == 'service':
            platform = URIRef(row['id'])
            if (platform, RDF.type, SCHEMA.Service) not in graph or (platform, RDF.type, EX.Organization) in graph:
                errors.append('Platform incorrectly typed as organization: ' + row['name'])
    for model in model_ids:
        if any(graph.triples((URIRef(model), OWL.sameAs, None))):
            errors.append('Unexpected model-level sameAs: ' + model)
    from .organization_links import checked_payload as checked_openalex_payload, verified_openalex_links
    openalex_cache = BRONZE / "openalex_lookups.json"
    openalex_pairs = set()
    openalex_lookups = read_json(openalex_cache) if openalex_cache.exists() else []
    if openalex_lookups:
        expected_openalex, openalex_decisions = verified_openalex_links(tables, openalex_lookups)
        for lookup in openalex_lookups:
            if lookup.get("source"):
                try:
                    checked_openalex_payload(lookup["source"])
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors.append("OpenAlex organization evidence invalid: " + str(exc))
        expected_openalex_pairs = {(r["subject"], r["target"]) for r in expected_openalex}
        openalex_pairs = {(str(s), str(t)) for s, t in graph.subject_objects(OWL.sameAs)
                          if str(t).startswith("https://openalex.org/I")}
        if expected_openalex_pairs != openalex_pairs:
            errors.append("OpenAlex organization RDF does not match independently replayed evidence")
    for source in manifest["documents"]:
        if not source.get("file"):
            errors.append("Missing preserved response bytes: " + source["url"])
        elif digest((BRONZE / source["file"]).read_bytes()) != source["sha256"]:
            errors.append("Source checksum mismatch: " + source["url"])
    for table in ("models", "offerings", "prices", "observations", "evaluations", "documents"):
        if len({r["id"] for r in tables[table]}) != len(tables[table]):
            errors.append("Duplicate IDs in " + table)
    counts = {name: len(set(graph.subjects(RDF.type, EX[cls]))) for name, cls in
              [("models", "AIModel"), ("offerings", "ModelOffering"), ("prices", "PriceSpecification"),
               ("observations", "FactObservation"), ("evaluations", "Evaluation"),
               ("external_links", "ExternalLink")]}
    for name, count in counts.items():
        if count != len(tables[name]):
            errors.append(f"CSV/RDF count mismatch in {name}: {len(tables[name])}/{count}")
    query_results = {}
    query_times = {}
    for path in sorted((ROOT / "queries").glob("*.rq")):
        print("Checking " + path.name, flush=True)
        try:
            started = time.perf_counter()
            rows = list(graph.query(path.read_text()))
            query_times[path.name] = round(time.perf_counter() - started, 3)
            print(f"  {len(rows)} rows in {query_times[path.name]}s", flush=True)
            query_results[path.name] = len(rows)
            if path.name in {"opus_providers_prices.rq", "claude_models.rq", "official_sources.rq", "benchmarks.rq"} and not rows:
                errors.append("Required query empty: " + path.name)
        except Exception as exc:
            errors.append(f"Query {path.name}: {type(exc).__name__}: {exc}")
    # OWL RL on representative sourced data, not a costly closure of every snapshot observation.
    from owlrl import DeductiveClosure, OWLRL_Semantics
    fixture = Graph().parse(RES / "ontology.ttl")
    sample_model = URIRef(tables["models"][0]["id"])
    fixture.add((sample_model, RDF.type, EX.AIModel))
    family = URIRef(tables["models"][0]["family_id"])
    fixture.add((sample_model, EX.belongsToFamily, family))
    fixture.add((family, RDF.type, EX.ModelFamily))
    DeductiveClosure(OWLRL_Semantics).expand(fixture)
    if (family, RDF.type, EX.AIModel) in fixture or (sample_model, RDF.type, EX.Organization) in fixture:
        errors.append("Unexpected OWL RL class inference")
    report = {"errors": errors, "warnings": warnings, "triples": len(graph), "counts": counts,
              "query_rows": query_results, "query_seconds": query_times, "source_snapshots": len(manifest["documents"]),
              "openalex_snapshots": sum(bool(r.get("source")) for r in openalex_lookups),
              "openalex_organization_links": len(openalex_pairs),
              "wikidata_dbpedia_links": len(actual_pairs),
              "linked_local_entities": len({str(s) for s, _ in graph.subject_objects(OWL.sameAs)}),
              "repository_relations": len(list(graph.triples((None, EX.hasRepository, None)))),
              "owl_rl": "representative fixture; full catalog closure not run", "shacl": {k: v for k, v in shacl_report.items() if k != "results"},
              "fuseki": "not started or uploaded by agent"}
    write_json(RES / "validation-report.json", report)
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    validate()
