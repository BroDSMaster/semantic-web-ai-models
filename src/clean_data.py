"""Stage 3a: flatten snapshots into normalized entity and relationship CSVs."""
from datetime import date

from common import ALLOWED_WORK_TYPES, BRONZE, FIELDS, SILVER, openalex_key, qid, read_json, write_json, write_tables


def normalize(works, source_details, institution_details):
    entities = {name: {} for name in FIELDS}
    details_s = {s["id"]: s for s in source_details}
    details_i = {i["id"]: i for i in institution_details}
    report = {"duplicate_works": 0, "skipped_works_without_id": 0,
              "skipped_authors_without_id": 0, "skipped_out_of_scope_works": 0, "warnings": []}

    def add(table, key, **values):
        if key not in entities[table]:
            entities[table][key] = {field: "" for field in FIELDS[table]}
        # Keep known values if another dehydrated record omits them.
        entities[table][key].update({k: v for k, v in values.items() if v is not None and v != ""})

    def boolean(value):
        return "true" if value is True else "false" if value is False else ""

    for work in works:
        if work.get("type") not in ALLOWED_WORK_TYPES or work.get("is_paratext"):
            report["skipped_out_of_scope_works"] += 1
            continue
        wid = work.get("id")
        if not wid:
            report["skipped_works_without_id"] += 1
            continue
        openalex_key(wid)
        if wid in entities["papers"]:
            report["duplicate_works"] += 1
            continue
        published = work.get("publication_date") or ""
        if published:
            try:
                date.fromisoformat(published)
            except ValueError:
                report["warnings"].append(f"Invalid date on {wid}: {published}")
                published = ""
        source = (work.get("primary_location") or {}).get("source") or {}
        sid = source.get("id", "")
        if sid:
            source = dict(source, **details_s.get(sid, {}))
            pid = source.get("host_organization") or ""
            if not pid.startswith("https://openalex.org/P"):
                # A repository may be hosted by an institution, not a Publisher.
                pid = ""
            add("sources", sid, id=sid, name=source.get("display_name"), type=source.get("type"),
                issn_l=source.get("issn_l"), publisher_id=pid, wikidata_id=qid((source.get("ids") or {}).get("wikidata")))
            if pid:
                add("publishers", pid, id=pid, name=source.get("host_organization_name"))
        primary = (work.get("primary_topic") or {}).get("id", "")
        add("papers", wid, id=wid, name=work.get("display_name") or work.get("title"), doi=work.get("doi"),
            year=work.get("publication_year"), date=published, citations=work.get("cited_by_count"),
            is_oa=boolean((work.get("open_access") or {}).get("is_oa")), type=work.get("type"),
            source_id=sid, primary_topic_id=primary)
        topics = list(work.get("topics") or [])
        if primary and primary not in {t["id"] for t in topics}:
            topics.append(work["primary_topic"])
        for topic in topics:
            tid = topic.get("id")
            if not tid:
                continue
            sub = topic.get("subfield") or {}
            field = topic.get("field") or {}
            domain = topic.get("domain") or {}
            add("topics", tid, id=tid, name=topic.get("display_name"), subfield_id=sub.get("id"))
            if sub.get("id"):
                add("subfields", sub["id"], id=sub["id"], name=sub.get("display_name"), field_id=field.get("id"))
            if field.get("id"):
                add("fields", field["id"], id=field["id"], name=field.get("display_name"), domain_id=domain.get("id"))
            if domain.get("id"):
                add("domains", domain["id"], id=domain["id"], name=domain.get("display_name"))
            add("paper_topics", (wid, tid), paper_id=wid, topic_id=tid, score=topic.get("score"))
        for author in work.get("authorships", []):
            person = author.get("author") or {}
            aid = person.get("id")
            if not aid:
                report["skipped_authors_without_id"] += 1
                continue
            role_id = openalex_key(wid) + "-" + openalex_key(aid)
            add("people", aid, id=aid, name=person.get("display_name"), orcid=person.get("orcid"))
            add("authorships", role_id, id=role_id, paper_id=wid, person_id=aid,
                position=author.get("author_position"), is_corresponding=boolean(author.get("is_corresponding")))
            for inst in author.get("institutions", []):
                iid = inst.get("id")
                if not iid:
                    continue
                inst = dict(inst, **details_i.get(iid, {}))
                add("institutions", iid, id=iid, name=inst.get("display_name"), ror=inst.get("ror"),
                    country=inst.get("country_code"), type=inst.get("type"),
                    wikidata_id=qid((inst.get("ids") or {}).get("wikidata")))
                add("authorship_institutions", (role_id, iid), authorship_id=role_id, institution_id=iid)
        for reference in work.get("referenced_works", []):
            add("references", (wid, reference), paper_id=wid, referenced_id=reference)
    tables = {name: [records[key] for key in sorted(records)] for name, records in entities.items()}
    report["counts"] = {name: len(rows) for name, rows in tables.items()}
    return tables, report


if __name__ == "__main__":
    tables, report = normalize(read_json(BRONZE / "openalex_works.json"),
                               read_json(BRONZE / "openalex_sources.json"),
                               read_json(BRONZE / "openalex_institutions.json"))
    write_tables(SILVER, tables)
    write_json(SILVER / "cleaning-report.json", report)
    print(report["counts"])
