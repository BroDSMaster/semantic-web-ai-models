"""Stage 3b: deterministic CSV → RDF, using stable HTTP entity URIs."""
from rdflib import DCTERMS, RDF, RDFS, XSD, Graph, Literal, URIRef

from common import BRONZE, DCAT, EX, GOLD, RES, SCHEMA, SKOS, now, read_json, read_tables, resource, write_json

ENTITY_MAP = {"papers": ("paper", EX.ResearchPaper), "people": ("person", EX.Person),
              "institutions": ("institution", EX.ResearchInstitution), "sources": ("source", EX.PublicationSource),
              "publishers": ("publisher", EX.Publisher), "topics": ("topic", EX.ResearchTopic),
              "subfields": ("subfield", EX.ResearchSubfield), "fields": ("field", EX.ResearchField),
              "domains": ("domain", EX.ResearchDomain), "authorships": ("authorship", EX.Authorship)}


def build_graph(tables):
    graph = Graph()
    for prefix, ns in [("ex", EX), ("schema", SCHEMA), ("dcterms", DCTERMS), ("skos", SKOS)]:
        graph.bind(prefix, ns)

    def uri(kind, ident):
        return resource(kind, ident)

    def literal(subject, predicate, value, datatype=None):
        if value is not None and value != "":
            graph.add((subject, predicate, Literal(value, datatype=datatype)))

    def relation(subject, predicate, kind, ident):
        if ident:
            graph.add((subject, predicate, uri(kind, ident)))

    for table, (kind, cls) in ENTITY_MAP.items():
        for row in tables[table]:
            subject = uri(kind, row["id"])
            graph.add((subject, RDF.type, cls))
            literal(subject, RDFS.label, row.get("name") or f"Authorship {row['id']}")
            if table != "authorships":
                graph.add((subject, DCTERMS.source, URIRef(row["id"])))
                literal(subject, DCTERMS.identifier, row["id"].rsplit("/", 1)[-1])
            if table == "papers":
                literal(subject, DCTERMS.title, row["name"])
                literal(subject, EX.publicationYear, row["year"], XSD.gYear)
                literal(subject, DCTERMS.issued, row["date"], XSD.date)
                literal(subject, EX.citationCount, row["citations"], XSD.nonNegativeInteger)
                literal(subject, EX.isOpenAccess, row["is_oa"], XSD.boolean)
                literal(subject, EX.workType, row["type"])
                if row["doi"]:
                    graph.add((subject, EX.doi, URIRef(row["doi"])))
                relation(subject, EX.publishedIn, "source", row["source_id"])
                relation(subject, EX.primaryTopic, "topic", row["primary_topic_id"])
            elif table == "people" and row["orcid"]:
                graph.add((subject, EX.orcid, URIRef(row["orcid"])))
            elif table == "institutions":
                literal(subject, EX.countryCode, row["country"])
                literal(subject, EX.institutionType, row["type"])
                if row["ror"]:
                    graph.add((subject, EX.ror, URIRef(row["ror"])))
            elif table == "sources":
                literal(subject, EX.sourceType, row["type"])
                literal(subject, EX.issnL, row["issn_l"])
                relation(subject, EX.publishedBy, "publisher", row["publisher_id"])
            elif table in ("topics", "subfields", "fields"):
                parent_kind, parent_field, predicate = {
                    "topics": ("subfield", "subfield_id", EX.inSubfield),
                    "subfields": ("field", "field_id", EX.inField),
                    "fields": ("domain", "domain_id", EX.inDomain)}[table]
                relation(subject, predicate, parent_kind, row[parent_field])
                relation(subject, SKOS.broader, parent_kind, row[parent_field])
            elif table == "authorships":
                paper = uri("paper", row["paper_id"])
                person = uri("person", row["person_id"])
                graph.add((paper, EX.hasAuthorship, subject))
                graph.add((subject, EX.authorPerson, person))
                graph.add((paper, SCHEMA.author, person))
                graph.add((subject, DCTERMS.source, URIRef(row["paper_id"])))
                literal(subject, EX.authorPosition, row["position"])
                literal(subject, EX.isCorresponding, row["is_corresponding"], XSD.boolean)
    for row in tables["authorship_institutions"]:
        graph.add((uri("authorship", row["authorship_id"]), EX.affiliatedInstitution, uri("institution", row["institution_id"])))
    for row in tables["paper_topics"]:
        graph.add((uri("paper", row["paper_id"]), EX.hasTopic, uri("topic", row["topic_id"])))
    local_papers = {row["id"] for row in tables["papers"]}
    for row in tables["references"]:
        target = uri("paper", row["referenced_id"]) if row["referenced_id"] in local_papers else URIRef(row["referenced_id"])
        graph.add((uri("paper", row["paper_id"]), DCTERMS.references, target))
    return graph


def metadata(manifest):
    graph = Graph()
    graph.bind("dcat", DCAT)
    graph.bind("dcterms", DCTERMS)
    graph.bind("ex", EX)
    dataset = EX.dataset
    graph.add((dataset, RDF.type, DCAT.Dataset))
    graph.add((dataset, DCTERMS.title, Literal("AI research metadata: LLM papers from OpenAlex", lang="en")))
    graph.add((dataset, DCTERMS.description, Literal("Sample of OpenAlex metadata, not full-text articles; classified within Computer Science.", lang="en")))
    graph.add((dataset, DCTERMS.source, URIRef("https://openalex.org/")))
    graph.add((dataset, DCTERMS.license, URIRef("https://creativecommons.org/publicdomain/zero/1.0/")))
    graph.add((dataset, DCTERMS.modified, Literal(manifest["retrieved_at"], datatype=XSD.dateTime)))
    graph.add((dataset, EX.collectionSearch, Literal(manifest["search"])))
    for suffix, media in [("ttl", "text/turtle"), ("rdf", "application/rdf+xml")]:
        distribution = EX[f"distribution-{suffix}"]
        graph.add((dataset, DCAT.distribution, distribution))
        graph.add((distribution, RDF.type, DCAT.Distribution))
        graph.add((distribution, DCAT.mediaType, Literal(media)))
        graph.add((distribution, DCTERMS.description, Literal(f"Local file src/data/gold/research.{suffix}; public download URL not yet assigned.")))
    return graph


if __name__ == "__main__":
    GOLD.mkdir(parents=True, exist_ok=True)
    graph = build_graph(read_tables())
    graph.serialize(GOLD / "research.ttl", format="turtle")
    graph.serialize(GOLD / "research.rdf", format="xml")
    Graph().parse(RES / "ontology.ttl").serialize(RES / "ontology.owl.xml", format="xml")
    metadata(read_json(BRONZE / "collection_manifest.json")).serialize(RES / "dataset-metadata.ttl", format="turtle")
    write_json(GOLD / "transformation-report.json", {"generated_at": now(), "triples": len(graph)})
    print(f"Generated Turtle and RDF/XML: {len(graph)} triples")
