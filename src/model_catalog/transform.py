"""Silver catalog tables to RDF, retaining statement-level source observations."""
import json
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD, DCTERMS, OWL

from .common import BASE, GOLD, RES, read_tables, write_json

EX = Namespace(BASE)
SCHEMA = Namespace("https://schema.org/")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")


def build_graph(tables):
    graph = Graph()
    for name, space in [("ex", EX), ("schema", SCHEMA), ("prov", PROV), ("dcterms", DCTERMS), ("dcat", DCAT)]:
        graph.bind(name, space)

    def entity(row, cls, label=None):
        subject = URIRef(row["id"])
        graph.add((subject, RDF.type, cls))
        if row.get("name") or label:
            graph.add((subject, RDFS.label, Literal(row.get("name") or label)))
        if row.get("document_id"):
            graph.add((subject, PROV.wasDerivedFrom, URIRef(row["document_id"])))
        return subject

    def value(subject, prop, val, datatype=None):
        if val is not None and str(val) != "":
            graph.add((subject, prop, Literal(val, datatype=datatype)))

    def link(subject, prop, ident):
        if ident:
            graph.add((subject, prop, URIRef(ident)))

    for row in tables["organizations"]:
        entity(row, EX.Organization)
    for row in tables["families"]:
        entity(row, EX.ModelFamily)
    for table, cls in [("capabilities", EX.Capability), ("modalities", EX.Modality)]:
        for row in tables[table]:
            entity(row, cls)
    for row in tables["documents"]:
        s = entity(row, EX.SourceDocument)
        link(s, SCHEMA.url, row["url"])
        for key, prop, dtype in [("kind", EX.sourceKind, None), ("sha256", EX.sha256, None),
                                 ("snapshot_file", EX.snapshotFile, None), ("retrieved_at", EX.observedAt, XSD.dateTime)]:
            value(s, prop, row.get(key), dtype)
    for row in tables["models"]:
        s = entity(row, EX.AIModel)
        link(s, EX.belongsToFamily, row["family_id"])
        link(s, EX.developedBy, row["developer_id"])
        for key, prop, dtype in [("source_id", EX.sourceId, None), ("catalog_created", EX.catalogCreated, XSD.dateTime),
                                 ("canonical_slug", EX.canonicalSlug, None), ("hugging_face_id", EX.huggingFaceId, None),
                                 ("knowledge_cutoff", EX.knowledgeCutoff, None), ("expiration_date", EX.expirationDate, None)]:
            value(s, prop, row.get(key), dtype)
    for row in tables["offerings"]:
        s = entity(row, EX.ModelOffering)
        link(s, EX.offersModel, row["model_id"])
        link(s, EX.hostedBy, row["provider_id"])
        for key, prop, dtype in [("kind", EX.offeringKind, None), ("mode", EX.serviceMode, None),
                                 ("endpoint_tag", EX.endpointTag, None), ("quantization", EX.quantization, None),
                                 ("observed_at", EX.observedAt, XSD.dateTime)]:
            value(s, prop, row.get(key), dtype)
    for row in tables["prices"]:
        s = entity(row, EX.PriceSpecification)
        graph.add((URIRef(row["offering_id"]), EX.hasPrice, s))
        for key, prop, dtype in [("category", EX.priceCategory, None), ("amount", EX.priceAmount, XSD.decimal),
                                 ("currency", EX.currency, None), ("unit", EX.priceUnit, None),
                                 ("conditions", EX.conditions, None), ("raw_amount", EX.rawAmount, None),
                                 ("tier", EX.priceTier, None), ("discount", EX.discount, XSD.decimal), ("min_prompt_tokens", EX.minPromptTokens, XSD.integer),
                                 ("raw_unit", EX.rawUnit, None), ("observed_at", EX.observedAt, XSD.dateTime)]:
            value(s, prop, row.get(key), dtype)
    for row in tables["observations"]:
        s = entity(row, EX.FactObservation)
        subject, predicate = URIRef(row["subject_id"]), EX[row["predicate"]]
        link(s, EX.aboutEntity, subject)
        link(s, EX.observedProperty, predicate)
        obj = URIRef(row["value"]) if row["value_kind"] == "resource" else Literal(row["value"], datatype=XSD[row["datatype"]])
        graph.add((s, EX.resourceValue if row["value_kind"] == "resource" else EX.literalValue, obj))
        value(s, EX.observedAt, row["observed_at"], XSD.dateTime)
        # Convenience triples; observations are authoritative for provenance/conflicts.
        graph.add((subject, predicate, obj))
    for row in tables["benchmarks"]:
        s = entity(row, EX.Benchmark)
        value(s, EX.evaluator, row["evaluator"])
        value(s, EX.scoreUnit, row["unit"])
        value(s, EX.benchmarkVersion, row["version"])
    for row in tables["evaluations"]:
        s = entity(row, EX.Evaluation)
        link(s, EX.evaluatedModel, row["model_id"])
        link(s, EX.onBenchmark, row["benchmark_id"])
        value(s, EX.score, row["score"], XSD.decimal)
        value(s, EX.scoreUnit, row["unit"])
        value(s, EX.evaluationConfig, row["config"])
        value(s, EX.attribution, row["attribution"])
        value(s, DCTERMS.date, row.get("evaluated_at"))
    for row in tables["reviews"]:
        s = entity(row, EX.Review)
        link(s, SCHEMA.itemReviewed, row["model_id"])
        link(s, SCHEMA.url, row["source_url"])
        value(s, DCTERMS.creator, row["author"])
        value(s, DCTERMS.issued, row.get("date"), XSD.date)
        value(s, DCTERMS.abstract, row.get("summary"))
    return graph


def load_model_graph():
    graph = Graph()
    for path in [RES / "model-ontology.ttl", GOLD / "models.ttl", RES / "model-links.nt", RES / "model-dataset-metadata.ttl"]:
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; see docs/MODEL_CATALOG.md")
        graph.parse(path, format="nt" if path.suffix == ".nt" else "turtle")
    return graph


def main():
    tables = read_tables()
    graph = build_graph(tables)
    GOLD.mkdir(parents=True, exist_ok=True)
    graph.serialize(GOLD / "models.ttl", format="turtle")
    graph.serialize(GOLD / "models.rdf", format="xml")
    ontology = Graph().parse(RES / "model-ontology.ttl")
    ontology.serialize(RES / "model-ontology.rdf", format="xml")
    meta = Graph()
    meta.bind("dcat", DCAT)
    meta.bind("dcterms", DCTERMS)
    dataset = URIRef(BASE + "dataset/models")
    meta.add((dataset, RDF.type, DCAT.Dataset))
    meta.add((dataset, DCTERMS.title, Literal("AI model catalog, offerings, sourced prices and evaluations")))
    meta.add((dataset, DCTERMS.description, Literal("Source-specific terms apply. OpenAlex CC0 does not apply to model/provider data. example.org namespace is a local capstone placeholder.")))
    for doc in tables["documents"]:
        meta.add((dataset, DCTERMS.source, URIRef(doc["url"])))
    meta.serialize(RES / "model-dataset-metadata.ttl", format="turtle")
    if not (RES / "model-links.nt").exists():
        Graph().serialize(RES / "model-links.nt", format="nt", encoding="utf-8")
    write_json(RES / "model-transform-report.json", {"triples": len(graph), "ontology_triples": len(ontology),
               "models": len(tables["models"]), "prices": len(tables["prices"]), "tables": {k: len(v) for k, v in tables.items()}})
    print(f"Exported {len(graph)} catalog triples to models.ttl / models.rdf")


if __name__ == "__main__":
    main()
