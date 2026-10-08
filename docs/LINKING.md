# Liên kết tổ chức tới các dataset bên ngoài

Project dùng `owl:sameAs` khi URI organization local và URI bên ngoài cùng nhận diện
một tổ chức. Provider là nền tảng như Azure/Bedrock được gán `schema:Service` và chỉ nối tới cùng dịch vụ bên ngoài, không nối tới công ty sở hữu. Model, repository, trang tài liệu và kết quả benchmark là các đối tượng
khác nhau nên không được nối `sameAs` với nhau.

## Kết quả đã thu thập và kiểm chứng

Ngày 08/10/2026, code lấy JSON công khai từ Wikidata và OpenAlex, đồng thời truy vấn SPARQL DBpedia. Dữ liệu OpenRouter dùng snapshot ngày 05/10/2026.

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

Ngoài 9 links OpenAlex, có **42 Wikidata links và 26 DBpedia links**, tổng cộng
**77 sameAs cho 43 URI local**. Hai URI developer và provider có thể nhận diện
cùng công ty; 43 URI local không có nghĩa 43 công ty khác nhau.

Mapping Wikidata chứa 25 thực thể đã duyệt. Ví dụ: Mistral AI, DeepSeek, Moonshot AI,
MiniMax, Alibaba (developer Qwen), Nvidia, Tencent, Baidu, Cloudflare, Groq,
DigitalOcean, Cerebras, CoreWeave, Perplexity, Microsoft, Amazon và ByteDance.
Azure nối tới `http://www.wikidata.org/entity/Q725967` và
`http://dbpedia.org/resource/Microsoft_Azure`, không nối tới Microsoft.

Giữ các tên chưa đủ bằng chứng ở trạng thái chưa liên kết; không suy ra công ty
chỉ bằng prefix model hoặc tên provider gần giống.

## Điều kiện để xuất sameAs tổ chức

1. Organization local phải tồn tại trong Silver và có mapping được duyệt.
2. Với Wikidata, QID, label/alias, `P31` (loại thực thể) và `P856` (website chính thức) phải khớp mapping đã duyệt. Domain phải khớp chính xác; với sản phẩm trên domain chung, đường dẫn phải khớp sản phẩm (ví dụ `/bedrock/`).
3. Chỉ thêm DBpedia khi resource DBpedia tự công bố `owl:sameAs` tới QID Wikidata đã xác minh.
4. Với OpenAlex, local URI/name, OpenAlex ID/display name, loại `company`, homepage và ROR phải khớp; QID cũng phải khớp khi mapping yêu cầu.
5. Đọc lại JSON gốc và kiểm tra SHA-256 khi export offline. Không nối gần đúng chỉ vì tên giống nhau.

Các điều kiện là bằng chứng đối chiếu từ nguồn công khai, có thể xem và chạy lại;
không phải bảo đảm rằng nguồn bên ngoài không bao giờ sai. Liên kết phản ánh snapshot
đã lưu trong project.

## Các quan hệ khác

**Hugging Face:** code lấy ID repository do OpenRouter chỉ rõ, kiểm tra API Hugging Face trả đúng ID trong danh sách namespace nhà phát hành, rồi tạo `ex:hasRepository`. Khi chuẩn hóa, code đọc lại response bytes và kiểm tra checksum/URL/ID. 102 listing tham chiếu 92 repository; nhiều listing có thể dùng chung repo. Điều này không xác minh deployment API dùng cùng revision hay weights, vì vậy không tạo sameAs giữa model và repository.

**Tài liệu hãng:** `ex:relatedDocumentation` chỉ quan hệ với trang liên quan; `prov:wasDerivedFrom` ghi nguồn một thông tin hoặc kết quả. Chỉ các parser nhận dạng được trường cụ thể mới trích thông tin từ trang.

**Aider / Artificial Analysis:** `Evaluation ex:evaluatedModel AIModel` nối kết quả đánh giá tới model. Aider dùng bảng đối chiếu ID rõ ràng có sẵn; dữ liệu Artificial Analysis ở đây là kết quả được OpenRouter nhúng trong JSON. Không biến URL benchmark thành sameAs, không tự coi mọi kết quả có tên gần giống là của cùng phiên bản.

## File, đầu vào và đầu ra

| File code / dữ liệu | Đầu vào → đầu ra |
|---|---|
| `res/wikidata-organization-mappings.json` | 25 QID, tên/alias, loại, website và 42 URI/tên local đã review; không tự tạo từ tên gần giống |
| `src/model_catalog/wikidata_links.py` | Mapping + Silver → raw JSON Wikidata/DBpedia tại Bronze + `external_lookups.json`; replay kiểm tra checksum/tên/loại/website → cặp sameAs được chấp nhận |
| `src/model_catalog/organization_links.py` | 9 ứng viên đã duyệt → JSON OpenAlex Institution trong Bronze và `openalex_lookups.json`; phát lại kiểm tra offline |
| `src/model_catalog/link.py --offline` | Silver + ứng viên + JSON gốc + cache → `res/linked_output.nt`, `external_links.csv`, `res/linking-report.json` |
| `src/model_catalog/model_cards.py` | URL HF được catalog chỉ rõ → model card JSON; đọc lại bytes đã kiểm tra khi offline |
| `src/model_catalog/normalize.py` | Catalog + card được xác minh → observations CSV cho `hasRepository` và metadata |
| `src/model_catalog/transform.py` | Silver → `src/data/gold/models.ttl` và `models.rdf`; RDF ghi quan hệ repository cùng nguồn |
| `src/model_catalog/validate.py` | Graph + snapshot nguồn → kiểm tra checksum và so sameAs Wikidata/DBpedia/OpenAlex trong RDF với mapping xác minh lại, kiểm tra provider service không bị gán Organization |

[linking-report.json](../res/linking-report.json) ghi số link và quyết định từng ứng viên. URL, thời điểm, checksum và đường dẫn file nguồn nằm trong CSV/cache và RDF evidence. [external_links.csv](../src/data/silver/external_links.csv) giữ mỗi cặp subject/target; `linked_output.nt` có cả triple sameAs và thực thể `ExternalLink` chứa bằng chứng. Metadata identity nằm ngoài manifest catalog; validator kiểm tra riêng các file được `openalex_lookups.json` và `external_lookups.json` trỏ tới.

## Chạy lại và query

Tại thư mục `aimodels`, tạo lại RDF từ nguồn đã lưu, không truy cập mạng:

```bash
PYTHONPATH=src .venv/bin/python -m model_catalog.normalize
PYTHONPATH=src .venv/bin/python -m model_catalog.transform
PYTHONPATH=src .venv/bin/python -m model_catalog.link --offline
PYTHONPATH=src .venv/bin/python -m model_catalog.validate
.venv/bin/python src/ask.py queries/linked_providers.rq
.venv/bin/python src/ask.py queries/external_links.rq
.venv/bin/python src/ask.py queries/openalex_organizations.rq
.venv/bin/python src/ask.py queries/model_repositories.rq
```

Chạy tuần tự, chờ mỗi lệnh hoàn tất. Muốn lấy lại bằng chứng OpenAlex mới, chạy `PYTHONPATH=src .venv/bin/python -m model_catalog.organization_links`. Sau đó chạy `link --offline` và `validate`. Các lệnh này chỉ cập nhật cache identity tổ chức, không thu thập lại giá/catalog.

Query external links trả 77 dòng tổ chức/dịch vụ; query OpenAlex trả 9 dòng; query repositories trả 102 dòng. `sameAs` tổ chức và `hasRepository` của model là hai quan hệ có ý nghĩa khác nhau.

Với Fuseki đã chạy, tự nạp các file bằng `bash scripts/load_fuseki.sh`, rồi dán query trong `queries/external_links.rq` hoặc `queries/openalex_organizations.rq` vào UI của `/aimodels`. Script thêm dữ liệu vào default graph và giữ dữ liệu cũ; vì dataset cũ có thể còn model links và kiểu Organization cũ của Azure, hãy tạo dataset `/aimodels` mới hoặc xóa dữ liệu cũ trước khi nạp bản này. Hướng dẫn khởi động Fuseki ở [PIPELINE.md](PIPELINE.md). Lần triển khai này chỉ xây dựng và kiểm tra offline, không cập nhật server của bạn.

Muốn lấy lại bằng chứng Wikidata/DBpedia và OpenAlex qua mạng, chạy
`PYTHONPATH=src .venv/bin/python -m model_catalog.link` (không có `--offline`),
sau đó `validate`. Lệnh này cập nhật identity, không thu thập lại model/giá.

Query provider đã liên kết, bao gồm nền tảng dịch vụ:

```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?name ?type ?externalIdentity WHERE {
  ?provider rdfs:label ?name; a ?type; owl:sameAs ?externalIdentity.
  FILTER(?name = "Azure")
}
```

Không dùng bộ lọc `a ex:Organization` để tìm Azure, vì Azure là `schema:Service`.
