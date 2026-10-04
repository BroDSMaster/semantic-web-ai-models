"""Optional live integration check: compare all CQs with the local RDF graph.

Read-only on Fuseki. Writes only res/fuseki-validation.json.
Run after loading the four files: python tests/check_fuseki.py
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from common import RES, load_graph, now, write_json


def query_endpoint(endpoint, query):
    request = Request(endpoint, data=query.encode("utf-8"), headers={
        "Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def canonical_rows(data):
    def value(cell, column):
        if not cell:
            return None
        text = cell["value"]
        if cell.get("datatype", "").endswith("#boolean"):
            return "true" if text in ("1", "true") else "false"
        if column == "institutions":
            return " | ".join(sorted(text.split(" | ")))
        return text
    columns = data["head"]["vars"]
    return sorted([tuple(value(row.get(col), col) for col in columns)
                   for row in data["results"]["bindings"]], key=repr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://localhost:3030/aimodels/sparql")
    args = parser.parse_args()
    graph = load_graph()
    checks, errors = {}, []
    for path in [ROOT / "queries/count_classes.rq", *sorted((ROOT / "queries").glob("cq*.rq"))]:
        query = path.read_text(encoding="utf-8")
        local = json.loads(graph.query(query).serialize(format="json"))
        remote = query_endpoint(args.endpoint, query)
        expected, actual = canonical_rows(local), canonical_rows(remote)
        checks[path.name] = {"local_rows": len(expected), "endpoint_rows": len(actual), "matches": expected == actual}
        if expected != actual:
            errors.append(f"Result mismatch: {path.name}")
        print(path.name, checks[path.name], flush=True)
    query = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
    remote = query_endpoint(args.endpoint, query)
    count = int(remote["results"]["bindings"][0]["count"]["value"])
    if count != len(graph):
        errors.append(f"Triple count differs: local={len(graph)}, endpoint={count}; use a fresh dataset")
    report = {"checked_at": now(), "endpoint": args.endpoint, "queries": checks,
              "local_triples": len(graph), "endpoint_triples": count, "errors": errors, "passed": not errors}
    write_json(RES / "fuseki-validation.json", report)
    print(json.dumps({"passed": not errors, "triples": count, "errors": errors}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
