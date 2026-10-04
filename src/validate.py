"""Check ontology/data structure, formal CQs and an OWL RL closure."""
import argparse
from rdflib import DCTERMS, RDF, RDFS, OWL, XSD, Literal, URIRef

from common import EX, GOLD, RES, ROOT, load_graph, now, write_json
from transform import ENTITY_MAP


def check_graph(graph, reasoning=False):
    errors = []
    for _, (kind, cls) in ENTITY_MAP.items():
        for entity in graph.subjects(RDF.type, cls):
            if not list(graph.objects(entity, RDFS.label)):
                errors.append(f"Missing label: {entity}")
    for paper in graph.subjects(RDF.type, EX.ResearchPaper):
        if not list(graph.objects(paper, DCTERMS.title)):
            errors.append(f"Missing paper title: {paper}")
    for role in graph.subjects(RDF.type, EX.Authorship):
        if len(set(graph.objects(role, EX.authorPerson))) != 1:
            errors.append(f"Authorship must have exactly one person in this export: {role}")
        if len(set(graph.subjects(EX.hasAuthorship, role))) != 1:
            errors.append(f"Authorship must belong to exactly one paper in this export: {role}")
    for person in graph.subjects(RDF.type, EX.Person):
        if list(graph.objects(person, EX.affiliatedInstitution)):
            errors.append(f"Affiliation incorrectly attached to Person: {person}")
    for predicate, datatype in [(EX.publicationYear, XSD.gYear), (EX.citationCount, XSD.nonNegativeInteger),
                                (EX.isOpenAccess, XSD.boolean), (EX.isCorresponding, XSD.boolean), (DCTERMS.issued, XSD.date)]:
        for subject, value in graph.subject_objects(predicate):
            if not isinstance(value, Literal) or value.datatype != datatype or value.ill_typed:
                errors.append(f"Invalid datatype for {predicate}: {subject} {value}")
    checked_triples = len(graph)
    inferred_triples = None
    if reasoning:
        from owlrl import DeductiveClosure, OWLRL_Semantics
        DeductiveClosure(OWLRL_Semantics).expand(graph)
        inferred_triples = len(graph)
        error_ns = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
        errors.extend(str(error) for error in graph.objects(None, error_ns))
        for entity in graph.subjects(RDF.type, OWL.Nothing):
            errors.append(f"Instance of owl:Nothing: {entity}")
        # Detect explicit/inferred collisions in disjoint type groups.
        for group in graph.subjects(RDF.type, OWL.AllDisjointClasses):
            types = list(graph.items(graph.value(group, OWL.members)))
            members = {cls: set(graph.subjects(RDF.type, cls)) for cls in types}
            for i, left in enumerate(types):
                for right in types[i + 1:]:
                    for entity in members[left] & members[right]:
                        errors.append(f"Disjoint type collision: {entity} ({left}, {right})")
        for paper, role in list(graph.subject_objects(EX.hasAuthorship)):
            if (role, EX.authoredPaper, paper) not in graph:
                errors.append(f"Inverse authorship was not inferred: {role}")
    return {"errors": sorted(set(errors)), "asserted_triples": checked_triples, "closure_triples": inferred_triples,
            "reasoning": "OWL RL" if reasoning else "none"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reasoning", action="store_true")
    parser.add_argument("--export-inferred", action="store_true", help="Save closure to gold/research-inferred.ttl")
    args = parser.parse_args()
    if args.export_inferred and not args.reasoning:
        parser.error("--export-inferred requires --reasoning")
    graph = load_graph()
    counts = {str(cls).rsplit("/", 1)[-1]: len(set(graph.subjects(RDF.type, cls))) for _, cls in ENTITY_MAP.values()}
    cqs = {}
    for path in sorted((ROOT / "queries").glob("cq*.rq")):
        result = list(graph.query(path.read_text(encoding="utf-8")))
        cqs[path.name] = {"rows": len(result), "first_row": [str(value) if value is not None else None for value in result[0]] if result else []}
    report = check_graph(graph, args.reasoning)
    report.update({"generated_at": now(), "entity_counts": counts, "competency_queries": cqs,
                   "sameAs_links": len(list(graph.triples((None, OWL.sameAs, None)))) if not args.reasoning else None})
    # Store asserted link counts separately; reasoning creates symmetric/transitive links.
    from rdflib import Graph
    links = Graph().parse(RES / "linked_output.nt", format="nt")
    report["asserted_sameAs_links"] = len(links)
    write_json(RES / "validation-report.json", report)
    if args.export_inferred:
        graph.serialize(GOLD / "research-inferred.ttl", format="turtle")
    print(report)
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
