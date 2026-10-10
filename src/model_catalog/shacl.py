"""Validate the combined asserted RDF graph against project SHACL constraints."""
import argparse
import json
import time
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from .common import RES, write_json
from .transform import load_model_graph

SH = Namespace('http://www.w3.org/ns/shacl#')


def validate_shacl(graph, *, shapes_path=None, output_dir=RES):
    shapes_path = Path(shapes_path) if shapes_path else RES / 'shapes.ttl'
    shapes = Graph().parse(shapes_path, format='turtle')
    started = time.perf_counter()
    conforms, report_graph, report_text = validate(
        graph, shacl_graph=shapes, inference='none', meta_shacl=True,
        advanced=False, inplace=False, abort_on_first=False,
    )
    if not isinstance(report_graph, Graph):
        raise RuntimeError('SHACL validator failure: ' + str(report_graph))
    results = []
    for node in report_graph.subjects(RDF.type, SH.ValidationResult):
        result = {}
        for key, prop in [('focus_node', SH.focusNode), ('path', SH.resultPath),
                          ('value', SH.value), ('severity', SH.resultSeverity),
                          ('source_shape', SH.sourceShape), ('constraint', SH.sourceConstraintComponent)]:
            value = report_graph.value(node, prop)
            if value is not None:
                result[key] = str(value)
        result['messages'] = [str(v) for v in report_graph.objects(node, SH.resultMessage)]
        results.append(result)
    results.sort(key=lambda row: (row.get('focus_node', ''), row.get('path', ''), row.get('constraint', '')))
    summary = {'conforms': bool(conforms), 'result_count': len(results),
               'data_triples': len(graph), 'shapes_file': str(shapes_path),
               'inference': 'none', 'seconds': round(time.perf_counter() - started, 3),
               'results': results}
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json(output_dir / 'shacl-report.json', summary)
        report_graph.serialize(output_dir / 'shacl-report.ttl', format='turtle')
        (output_dir / 'shacl-report.txt').write_text(report_text, encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, help='Validate a standalone Turtle fixture instead of the catalog')
    parser.add_argument('--output-dir', type=Path, default=RES, help='Directory for JSON/Turtle/text reports')
    args = parser.parse_args()
    graph = Graph().parse(args.data, format='turtle') if args.data else load_model_graph()
    print('Running SHACL on ' + str(len(graph)) + ' triples...', flush=True)
    report = validate_shacl(graph, output_dir=args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))
    if not report['conforms']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
