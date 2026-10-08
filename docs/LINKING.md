# Liên kết model: cùng thực thể hay chỉ có liên quan?

Một model có thể xuất hiện ở nhiều nguồn. Ví dụ OpenRouter có mục GPT-4, Wikidata có thực thể GPT-4. Nếu hai định danh nói về cùng model, ta có thể tạo `owl:sameAs`. Ngược lại, repository chứa code/trọng số, bài giới thiệu và kết quả benchmark là những đối tượng có liên quan đến model; không phải mọi URL về GPT-4 đều là GPT-4.

## Kết quả đã thu thập và kiểm chứng

Ngày 08/10/2026, code lấy JSON công khai từ Wikidata và OpenAlex, đồng thời truy vấn SPARQL DBpedia. Dữ liệu OpenRouter dùng snapshot ngày 05/10/2026.

| ID local từ OpenRouter | URI Wikidata đã xác minh | DBpedia |
|---|---|---|
| `openai/gpt-4` | `http://www.wikidata.org/entity/Q116709136` | Truy vấn sameAs trả rỗng; không xuất link |
| `openai/gpt-4o` | `http://www.wikidata.org/entity/Q125919502` | Truy vấn sameAs trả rỗng; không xuất link |

Hai liên kết này nói về **model được đặt tên**, không xác minh checkpoint đang phục vụ một request API. Chúng không được gán cho GPT-4 Turbo, GPT-4o mini, bản có ngày hoặc chế độ batch/free. Không có bằng chứng trong tập mapping hiện tại cho Opus hay các model khác thì không tạo sameAs cho chúng. Đây là tập mapping đã xem xét, không phải công cụ tự khám phá mọi model trên Web.

OpenAlex bổ sung 9 `sameAs` ở cấp Organization:

| Organization local | OpenAlex Institution |
|---|---|
| OpenAI | `https://openalex.org/I4210161460` |
| Anthropic | `https://openalex.org/I4387930290` |
| Google | `https://openalex.org/I1291425158` |
| Meta | `https://openalex.org/I4210114444` |
| Mistral AI | `https://openalex.org/I4390039361` |
| DeepSeek | `https://openalex.org/I4405257960` |
| xAI | `https://openalex.org/I4401726768` |
| Moonshot AI | `https://openalex.org/I4405260227` |
| Cohere | `https://openalex.org/I4401726847` |

Mỗi mapping phải khớp exact local URI/name, OpenAlex ID/display name, loại `company`, homepage domain và ROR. Meta, DeepSeek và Moonshot còn phải khớp Wikidata QID. OpenAlex Work là bài báo nên không bao giờ được dùng làm `sameAs` của AIModel.

## Điều kiện để xuất sameAs

1. ID model nằm trong `res/model-identity-mappings.json`, có QID, hãng, tên và URL model chính thức đã được chọn để đối chiếu.
2. URI local, ID và tên trong Silver khớp dữ liệu JSON OpenRouter gốc. Không tìm gần đúng theo tên.
3. JSON Wikidata trả đúng QID và tên model/phiên bản. `P178` là hãng phát triển; `P31` là loại thực thể; `P856` là URL chính thức. Cả ba phải khớp cấu hình. Cùng domain nhưng khác trang model không đủ.
4. Đọc lại các file JSON gốc và kiểm tra SHA-256 trước mỗi lần export offline. SHA-256 là mã kiểm tra nội dung file; nó phát hiện file bị sửa, không tự chứng minh phát biểu của nguồn là đúng.
5. Chỉ thêm DBpedia khi phản hồi truy vấn chính xác cho QID đã xác minh chứa resource URI có sameAs. Không suy ra URI từ tên trang.

Các điều kiện là bằng chứng đối chiếu từ nguồn công khai, có thể xem và chạy lại; không phải bảo đảm rằng nguồn bên ngoài không bao giờ sai. Liên kết phản ánh snapshot và phạm vi model nói trên.

## Các quan hệ khác

**Hugging Face:** code lấy ID repository do OpenRouter chỉ rõ, kiểm tra API Hugging Face trả đúng ID trong danh sách namespace nhà phát hành, rồi tạo `ex:hasRepository`. Khi chuẩn hóa, code đọc lại response bytes và kiểm tra checksum/URL/ID. 102 listing tham chiếu 92 repository; nhiều listing có thể dùng chung repo. Điều này không xác minh deployment API dùng cùng revision hay weights, vì vậy không tạo sameAs giữa model và repository.

**Tài liệu hãng:** `ex:relatedDocumentation` chỉ quan hệ với trang liên quan; `prov:wasDerivedFrom` ghi nguồn một thông tin hoặc kết quả. Chỉ các parser nhận dạng được trường cụ thể mới trích thông tin từ trang.

**Aider / Artificial Analysis:** `Evaluation ex:evaluatedModel AIModel` nối kết quả đánh giá tới model. Aider dùng bảng đối chiếu ID rõ ràng có sẵn; dữ liệu Artificial Analysis ở đây là kết quả được OpenRouter nhúng trong JSON. Không biến URL benchmark thành sameAs, không tự coi mọi kết quả có tên gần giống là của cùng phiên bản.

## File, đầu vào và đầu ra

| File code / dữ liệu | Đầu vào → đầu ra |
|---|---|
| `src/model_catalog/model_links.py` | Danh sách ứng viên → JSON Wikidata/DBpedia trong Bronze và `model_lookups.json` |
| `src/model_catalog/organization_links.py` | 9 ứng viên đã duyệt → JSON OpenAlex Institution trong Bronze và `openalex_lookups.json`; phát lại kiểm tra offline |
| `src/model_catalog/link.py --offline` | Silver + ứng viên + JSON gốc + cache → `res/linked_output.nt`, `external_links.csv`, `res/linking-report.json` |
| `src/model_catalog/model_cards.py` | URL HF được catalog chỉ rõ → model card JSON; đọc lại bytes đã kiểm tra khi offline |
| `src/model_catalog/normalize.py` | Catalog + card được xác minh → observations CSV cho `hasRepository` và metadata |
| `src/model_catalog/transform.py` | Silver → `src/data/gold/models.ttl` và `models.rdf`; RDF ghi quan hệ repository cùng nguồn |
| `src/model_catalog/validate.py` | Graph + snapshot nguồn → kiểm tra checksum và so sameAs model trong RDF với các mapping xác minh lại |

[linking-report.json](../res/linking-report.json) ghi quyết định từng ứng viên, URL, thời điểm, checksum và đường dẫn file nguồn. [external_links.csv](../src/data/silver/external_links.csv) giữ mỗi cặp subject/target; `linked_output.nt` có cả triple sameAs và thực thể `ExternalLink` chứa bằng chứng. Metadata identity nằm ngoài manifest catalog; validator kiểm tra riêng các file được `model_lookups.json` và `openalex_lookups.json` trỏ tới.

## Chạy lại và query

Tại thư mục `aimodels`, tạo lại RDF từ nguồn đã lưu, không truy cập mạng:

```bash
PYTHONPATH=src .venv/bin/python -m model_catalog.normalize
PYTHONPATH=src .venv/bin/python -m model_catalog.transform
PYTHONPATH=src .venv/bin/python -m model_catalog.link --offline
PYTHONPATH=src .venv/bin/python -m model_catalog.validate
.venv/bin/python src/ask.py queries/model_identity_links.rq
.venv/bin/python src/ask.py queries/openalex_organizations.rq
.venv/bin/python src/ask.py queries/model_repositories.rq
```

Chạy tuần tự, chờ mỗi lệnh hoàn tất. Muốn lấy lại bằng chứng OpenAlex mới, chạy `PYTHONPATH=src .venv/bin/python -m model_catalog.organization_links`; với Wikidata/DBpedia model, chạy `PYTHONPATH=src .venv/bin/python -m model_catalog.model_links`. Sau đó chạy `link --offline` và `validate`. Các lệnh này chỉ cập nhật cache identity, không thu thập lại giá/catalog.

Query identity model trả 2 dòng; query OpenAlex trả 9 dòng; query repositories trả 102 dòng. Chúng lần lượt biểu diễn cùng model, cùng tổ chức và repository có liên quan — ba ý nghĩa khác nhau.

Với Fuseki đã chạy, tự nạp các file bằng `bash scripts/load_fuseki.sh`, rồi dán query trong `queries/model_identity_links.rq` vào UI của `/aimodels`. Script thêm dữ liệu vào default graph và giữ dữ liệu cũ; nếu đã có triples sai/từ snapshot khác, nên dùng dataset mới để kiểm tra snapshot này riêng. Hướng dẫn khởi động Fuseki ở [PIPELINE.md](PIPELINE.md). Lần triển khai này chỉ xây dựng và kiểm tra offline, không cập nhật server của bạn.
