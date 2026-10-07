"""Validate collected catalog, RDF provenance and every shipped SPARQL query."""
import json
import time
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL

from .common import BRONZE, GOLD, RES, ROOT, digest, read_json, read_tables, write_json
from .transform import EX, PROV, build_graph, load_model_graph


def validate():
    tables = read_tables()
    graph = load_model_graph()
    errors, warnings = [], []
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
    for source in manifest["documents"]:
        if not source.get("file"):
            errors.append("Missing preserved response bytes: " + source["url"])
        elif digest((BRONZE / source["file"]).read_bytes()) != source["sha256"]:
            errors.append("Source checksum mismatch: " + source["url"])
    for table in ("models", "offerings", "prices", "observations", "evaluations", "reviews", "documents"):
        if len({r["id"] for r in tables[table]}) != len(tables[table]):
            errors.append("Duplicate IDs in " + table)
    counts = {name: len(set(graph.subjects(RDF.type, EX[cls]))) for name, cls in
              [("models", "AIModel"), ("offerings", "ModelOffering"), ("prices", "PriceSpecification"),
               ("observations", "FactObservation"), ("evaluations", "Evaluation"), ("reviews", "Review"),
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
            if path.name in {"opus_providers_prices.rq", "claude_models.rq", "reviews.rq", "official_sources.rq", "benchmarks.rq"} and not rows:
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
              "owl_rl": "representative fixture; full catalog closure not run", "fuseki": "not started or uploaded by agent"}
    write_json(RES / "validation-report.json", report)
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    validate()
