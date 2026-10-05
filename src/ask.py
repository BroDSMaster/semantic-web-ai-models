"""Run a SPARQL file locally or against a Jena Fuseki endpoint."""
import argparse
import csv
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from common import load_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", type=Path, help="SPARQL .rq file")
    parser.add_argument("--endpoint", help="e.g. http://localhost:3030/aimodels/sparql")
    parser.add_argument("--reasoning", action="store_true", help="Local OWL RL closure; does not change disk data")
    parser.add_argument("--dataset", choices=["research", "models", "all"], default="research",
                        help="Local graph selection; with --endpoint the URL selects the server dataset")
    args = parser.parse_args()
    query = args.query.read_text(encoding="utf-8")
    if args.endpoint:
        if args.reasoning:
            parser.error("--reasoning is local only; load an inferred graph for endpoint reasoning")
        request = Request(args.endpoint, data=query.encode(), headers={"Content-Type": "application/sparql-query",
                                                                      "Accept": "application/sparql-results+json"})
        with urlopen(request, timeout=60) as response:
            data = json.load(response)
    else:
        if args.dataset == "research":
            graph = load_graph()
        else:
            from model_catalog.transform import load_model_graph
            graph = load_model_graph()
            if args.dataset == "all":
                graph += load_graph()
        if args.reasoning:
            from owlrl import DeductiveClosure, OWLRL_Semantics
            DeductiveClosure(OWLRL_Semantics).expand(graph)
        data = json.loads(graph.query(query).serialize(format="json"))
    if "boolean" in data:
        print(str(data["boolean"]).lower())
        return
    columns = data["head"]["vars"]
    writer = csv.writer(sys.stdout)
    writer.writerow(columns)
    for row in data["results"]["bindings"]:
        writer.writerow([row.get(column, {}).get("value", "") for column in columns])


if __name__ == "__main__":
    main()
