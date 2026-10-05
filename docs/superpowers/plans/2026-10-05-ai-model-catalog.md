# AI Model Catalog Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Thu thập catalog đa hãng, provider/giá Opus, nguồn chính thức, benchmark và review; xuất RDF/query chạy được.
**Architecture:** Nhánh model_catalog riêng, giữ pipeline research. JSON/HTML snapshots → CSV → RDF, provenance theo quan sát; Fuseki do người dùng nạp.
**Tech Stack:** Python standard library, RDFLib, OWL RL, Apache Jena Fuseki.
**Spec:** ../specs/2026-10-05-ai-model-catalog-design.md

## Global Constraints

- Không inference, không khởi động/chỉnh dữ liệu Fuseki.
- Yêu cầu mới “triển khai code và thu thập luôn” cho phép collection và tạo RDF; kiểm tra local để xác minh deliverable.
- Không phá dữ liệu/queries nghiên cứu. Không secrets trong snapshots.
- Không fuzzy-match identity, không coi catalog created là release date.
- Giá per-token dùng Decimal; zero hợp lệ, null là unknown.

## Review Focus

- Endpoint provider khác developer; catalog price khác direct price.
- Free/batch/latest variants không tự gộp identity.
- Benchmark effort/scale khác nhau không bị gộp hoặc biến cost/run thành token price.
- Catalog rỗng/schema sai không ghi đè snapshot.
- Source facts phải khớp bản tài liệu đã thu được; stale curated facts không tự cập nhật thời gian giá.

## Tasks / interfaces

1. [x] Tests trước: normalizer nhận catalog/endpoints + manifest; trả dictionary tables. Test zero/null/precision, variants, provider và benchmarks; collector test pagination và failed snapshot.
2. [x] `src/model_catalog/common.py`, `collect.py`: snapshots công khai, checksum, manifests, bounded retries, offline replay; endpoints toàn catalog có concurrency hữu hạn; official HTML sources và Aider.
3. [x] `normalize.py`, `benchmarks.py`: tables chuẩn hóa với source document ID; match model bằng mapping rõ ràng; unmatched lưu riêng.
4. [x] `res/model-ontology.ttl`, `transform.py`, `link.py`: ontology 13 classes, statements/observations có nguồn, dataset metadata và links có evidence.
5. [x] `src/ask.py`, `validate.py`, `queries/models/`, Fuseki config/load script: catalog CLI, CQs và đặc biệt query Opus provider/giá.
6. [x] Thu thập thật, tạo silver/gold, xác minh local; cập nhật README, walkthrough, ontology glossary/CQs, báo coverage thật và giới hạn.

## Verification commands

Run tests: `.venv/bin/python -m unittest discover -s tests -v`.
Run catalog queries: `.venv/bin/python src/ask.py queries/models/opus_providers_prices.rq --dataset models`.
Run validation: `.venv/bin/python -m model_catalog.validate` from src with PYTHONPATH=src.
Expected: RDF parses, tests pass, Opus query has concrete provider names and sourced USD/1M token prices.
No server launch/upload command will be run by the agent.

## Execution ledger

Ruling: Người dùng nhắc lại trực tiếp triển khai/thu thập sau khi đã xem thiết kế; tiếp tục thực hiện, không yêu cầu lại quyền làm các bước đã được chỉ định.
Ruling: Workspace không có Git repository; làm trực tiếp tại aimodels, không dùng git/worktree helper.
Ruling: Collection và local verification là phần cần thiết để bàn giao dữ liệu dùng được; yêu cầu không tự chạy vẫn giữ cho Fuseki/inference và deploy.

Task 1: fixture regression tests written first; observed missing modules/features and failures, then corrected.
Task 2: public catalog and endpoints collected; exact IDs required for :free/:batch; response bytes content-addressed. Immutable aggregate snapshots referenced by manifest prevent interrupted collection mixing datasets.
Task 3: CSV normalization and official schema adapters implemented; source-bound qualifiers extracted from text, context override prices retained. Publisher cards added to enrich checkpoint totals/license/task.
Task 4: ontology and RDF exported; 5 verified external links, one candidate official-site mismatch omitted.
Task 5: model graph selection, Opus/provider pricing queries, default-graph load instructions and loader added; no server launch/upload.
Task 6: completed. 27 regression tests pass; all 13 SPARQL files execute on 353882 combined triples with zero validation errors. CLI Opus returns 336 sourced price rows; coverage and MODEL_VALIDATION.md recorded. No Fuseki startup/upload performed.
Ruling: No direct Artificial Analysis adapter/key flow in this release; embedded AA metrics attributed via OpenRouter and public Aider records satisfy benchmark collection without requiring credentials.
Ruling: “Latest release” omitted as a delivered query because catalog.created does not establish release dates; documentation explicitly states limitation.
Ruling: Free/batch/alias listings remain distinct source references; counts are model/listing counts, not independent weights counts. Do not claim exact equivalence across source versions.
Review: fresh read-only reviewer found three Important issues (endpoint schema, immutable evidence, stale qualifiers); fixed with regression tests. Base-tier comparison and endpoint configurations fixed. Link provenance stays separate in bronze lookup JSON/evidence CSV; no unsupported sameAs emitted.

Final verification: discount/surcharge factors applied with Decimal, raw amount retained; null means no discount. RDFLib Cartesian scans caused by independent literal constraints corrected in catalog price queries; direct/router 3.038s and Opus 4.772s on full graph.
