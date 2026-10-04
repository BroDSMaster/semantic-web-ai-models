"""Paths, stable identities and small I/O helpers shared by the pipeline."""
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rdflib import Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
BRONZE = ROOT / "src/data/bronze"
SILVER = ROOT / "src/data/silver"
GOLD = ROOT / "src/data/gold"
RES = ROOT / "res"
EX = Namespace("https://example.org/aimodels/")
SCHEMA = Namespace("https://schema.org/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
ALLOWED_WORK_TYPES = ("article", "conference-paper", "preprint", "review")
WORK_FILTER = "primary_topic.field.id:17,is_paratext:false,type:" + "|".join(ALLOWED_WORK_TYPES)

FIELDS = {
    "papers": ["id", "name", "doi", "year", "date", "citations", "is_oa", "type", "source_id", "primary_topic_id"],
    "people": ["id", "name", "orcid"],
    "institutions": ["id", "name", "ror", "country", "type", "wikidata_id"],
    "sources": ["id", "name", "type", "issn_l", "publisher_id", "wikidata_id"],
    "publishers": ["id", "name"],
    "topics": ["id", "name", "subfield_id"],
    "subfields": ["id", "name", "field_id"],
    "fields": ["id", "name", "domain_id"],
    "domains": ["id", "name"],
    "authorships": ["id", "paper_id", "person_id", "position", "is_corresponding"],
    "authorship_institutions": ["authorship_id", "institution_id"],
    "paper_topics": ["paper_id", "topic_id", "score"],
    "references": ["paper_id", "referenced_id"],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def openalex_key(identifier):
    value = str(identifier or "")
    match = re.fullmatch(r"https://openalex\.org/(?:subfields/|fields/|domains/)?([A-Z]?\d+)", value)
    if not match:
        raise ValueError(f"Invalid OpenAlex identifier: {value!r}")
    return match.group(1)


def resource(kind, identifier):
    key = openalex_key(identifier) if str(identifier).startswith("https://openalex.org/") else str(identifier)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ValueError(f"Unsafe resource identifier: {key!r}")
    return URIRef(f"{EX}resource/{kind}/{key}")


def qid(value):
    match = re.fullmatch(r"(?:https?://www\.wikidata\.org/entity/)?(Q\d+)", str(value or ""))
    return match.group(1) if match else ""


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_tables(directory, tables):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, fields in FIELDS.items():
        with (directory / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(tables.get(name, []))


def read_tables(directory=SILVER):
    tables = {}
    for name in FIELDS:
        with (Path(directory) / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
            tables[name] = list(csv.DictReader(handle))
    return tables


def fetch_json(url, params=None, *, openalex=False, accept="application/json"):
    """Public read-only JSON request; never log API keys in stored request URLs."""
    params = dict(params or {})
    if openalex and os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    request_url = url + (("&" if "?" in url else "?") + urlencode(params) if params else "")
    request = Request(request_url, headers={"Accept": accept, "User-Agent": "AIResearchLOD-capstone/1.0"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RuntimeError(f"Non-JSON response from {url.split('?')[0]}; check endpoint format") from None
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError(f"Network request failed: {url.split('?')[0]}") from None
        time.sleep(2 ** attempt)


def load_graph(with_links=True, with_metadata=True):
    graph = Graph()
    files = [RES / "ontology.ttl", GOLD / "research.ttl"]
    if with_links:
        files.append(RES / "linked_output.nt")
    if with_metadata:
        files.append(RES / "dataset-metadata.ttl")
    for path in files:
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; follow README pipeline steps first")
        graph.parse(path)
    return graph
