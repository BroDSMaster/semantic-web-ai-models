"""Aider table extraction with explicit, reviewable model-ID mappings."""
import json
import re
from html.parser import HTMLParser

from .common import BRONZE, RES, digest, read_json, uri


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.rows, self.row, self.cell = [], None, None, None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
        if self.depth == 1 and tag == "tr":
            self.row = []
        if self.depth == 1 and tag in ("td", "th"):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth == 1 and tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        if self.depth == 1 and tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            if self.depth == 1:
                self.tables.append(self.rows)
            self.depth -= 1


def add_aider(tables, manifest):
    source = next((d for d in manifest.get("documents", []) if d.get("id") == "aider-leaderboard"), None)
    if not source:
        return
    parser = TableParser()
    parser.feed((BRONZE / source["file"]).read_text(encoding="utf-8"))
    mappings = read_json(RES / "identity-mappings.json").get("aider", {})
    models = {m["source_id"]: m["id"] for m in tables["models"]}
    document_id = next(d["id"] for d in tables["documents"] if d["url"] == source["url"])
    bench_id = uri("benchmark", "aider:polyglot-225")
    tables["benchmarks"].append({"id": bench_id, "name": "Aider polyglot coding (225 exercises)",
                                 "evaluator": "Aider", "unit": "percent", "version": "polyglot-225"})
    found_table = False
    for rows in parser.tables:
        if not rows or "Model" not in rows[0] or "Percent correct" not in rows[0]:
            continue
        found_table = True
        header = rows[0]
        for row in rows[1:]:
            if len(row) != len(header):
                continue
            record = dict(zip(header, row))
            label = record["Model"]
            model_id = models.get(mappings.get(label, ""))
            raw_score = record["Percent correct"].rstrip("%")
            if not re.fullmatch(r"\d+(?:\.\d+)?", raw_score):
                continue
            if not model_id:
                tables["unmatched"].append({"id": digest([source["url"], label, row]), "kind": "aider_evaluation",
                                            "name": label, "reason": "no explicit ID mapping or mapped model absent",
                                            "source_url": source["url"], "raw_record": json.dumps(record)})
                continue
            tables["evaluations"].append({"id": uri("evaluation", digest([source["sha256"], label, row])),
                                          "model_id": model_id, "benchmark_id": bench_id, "score": raw_score,
                                          "unit": "percent", "config": json.dumps({"source_model_label": label,
                                          "command": record.get("Command", ""), "edit_format": record.get("Edit Format", ""),
                                          "cost_per_run": record.get("Cost", ""), "note": "configuration preserved; no pooled ranking"}),
                                          "document_id": document_id, "source_url": source["url"],
                                          "evaluated_at": "", "attribution": "Aider"})
        break
    if not found_table:
        tables["unmatched"].append({"id": digest([source["sha256"], "schema"]), "kind": "benchmark_schema",
                                    "name": "Aider", "reason": "expected Model/Percent correct table missing",
                                    "source_url": source["url"]})
