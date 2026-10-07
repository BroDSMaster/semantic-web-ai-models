# Chạy và query AI model catalog

Project aimodels độc lập, dành cho model AI và dịch vụ API.
Model/API metadata đã được thu thập vào repo và RDF được tạo sẵn. Agent không
khởi động Fuseki, không inference, không tự nạp/chỉnh dataset server.

## 1. Query local, không cần server

```bash
cd /home/puda14/Desktop/Project/semantic-web/aimodels
.venv/bin/python src/ask.py queries/opus_providers_prices.rq
```

Kết quả gồm model ID, provider, offering kind, mode, loại token, USD/1M
tokens, điều kiện giá, URL bằng chứng và thời điểm lấy nguồn. Một provider
có thể có nhiều endpoint hoặc service mode. `openrouter_endpoint` là provider
qua OpenRouter, **không phải tuyên bố về giá mua trực tiếp tại provider đó**.
`direct` là giá trích từ tài liệu trực tiếp của hãng. `openrouter_catalog`
là giá danh mục chung của router. Không coi ba loại này là cùng một giá.

## 2. Nạp vào Fuseki đang chạy

Trên giao diện `http://localhost:3030`:

1. Vào Manage datasets → Add new dataset; tên `aimodels`, chọn
   Persistent/TDB2 nếu muốn giữ dữ liệu qua lần khởi động sau.
2. Mở dataset → **Add data**.
3. Nạp lần lượt các file sau vào **default graph** (để trống graph name):
   - `res/ontology.ttl`
   - `src/data/gold/models.ttl`
   - `res/linked_output.nt`
   - `res/dataset-metadata.ttl`

   Các đường dẫn trên tính từ thư mục `aimodels/`.
4. Sang tab Query, dán nội dung một file trong `queries/`.

Sau khi tách project, nên dùng kho mới theo scripts/start_fuseki.sh. Dataset cũ có thể còn dữ liệu từ trước khi tách; script không tự xóa dữ liệu đó.

Hoặc, sau khi dataset đã tồn tại, dùng loader:

```bash
bash scripts/load_fuseki.sh http://localhost:3030/aimodels/data
```

Loader dùng POST để thêm vào default graph, không gửi lệnh CLEAR hoặc DELETE.
Không nạp cả TTL và RDF/XML cùng lúc. Việc làm mới nhiều snapshot bằng cách
POST sẽ giữ cả quan sát cũ và mới; khi cần một snapshot độc lập, tạo dataset
mới hoặc chủ động quản lý graph theo snapshot. Loader không tự xóa lịch sử.

Query qua terminal đến server:

```bash
.venv/bin/python src/ask.py queries/opus_providers_prices.rq \
  --endpoint http://localhost:3030/aimodels/sparql
```

Nếu bắt đầu Fuseki từ cấu hình thay vì UI, dùng `res/fuseki-config.ttl`
và chạy từ thư mục aimodels để TDB2 ở `run/tdb2-models`, runtime ở run/fuseki-models. Không mở hai process cùng ghi một TDB2 location.

## 3. Query provider và giá một phiên bản Opus

Dán vào tab Query sau khi nạp dữ liệu:

```sparql
PREFIX ex: <https://example.org/aimodels/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX schema: <https://schema.org/>

SELECT ?provider ?kind ?category ?usdPerMillionTokens ?conditions ?source
WHERE {
  ?model ex:sourceId "anthropic/claude-opus-4.6" .
  ?offering ex:offersModel ?model ; ex:hostedBy ?host ;
            ex:offeringKind ?kind ; ex:serviceMode "standard" ; ex:hasPrice ?p .
  ?host rdfs:label ?provider .
  ?p ex:priceCategory ?category ; ex:priceAmount ?usdPerMillionTokens ;
     ex:priceUnit "million_tokens" ; prov:wasDerivedFrom ?document .
  ?document schema:url ?source .
  FILTER(?category IN ("prompt", "completion", "input_cache_read"))
  OPTIONAL { ?p ex:conditions ?conditions }
}
ORDER BY ?kind ?provider ?category
```

Đổi ID thành `anthropic/claude-opus-5.5`, hoặc dùng
`claude_models.rq` để tìm những ID đang có trong snapshot. Giá là dữ liệu
thu thập, không được trình bày là báo giá live tại thời điểm người dùng query.
Ngày và coverage thực tế nằm trong `res/coverage.json`.

## 4. Các query kèm theo

| File | Đầu ra |
|---|---|
| `claude_models.rq` | Model/ID thuộc họ Claude; query đã minh họa trước nay có dữ liệu local |
| `opus_providers_prices.rq` | Provider, offering type, mode và giá của các bản Opus |
| `model_details.rq` | Quan sát thông số/description/modality cho model và các offering, kèm nguồn; sửa ID Sol để tra model khác |
| `cheap_tool_models.rq` | Offering có tools, context >=100K, giá input <1 USD/1M tokens; đọc thêm điều kiện giá |
| `vision_models.rq` | Model nhận image input theo catalog |
| `open_weight_specs.rq` | Total checkpoint parameters, license, library và task theo publisher metadata |
| `direct_vs_router.rq` | Liệt kê giá direct/router, sắp cạnh nhau theo ID/category; model thiếu một nguồn vẫn xuất hiện; đọc điều kiện |
| `benchmarks.rq` | Score, scale, config, evaluator attribution và nguồn; không xếp hạng chung các benchmark |
| `reviews.rq` | Model, bài review, tác giả, ngày, URL, tóm tắt ngắn |
| `official_sources.rq` | Facts đã trích từ schema chính thức, không phải mọi URL tài liệu liên quan |
| `coverage.rq` | Số model theo developer/source namespace |
| `conflicting_observations.rq` | Model context/output/cutoff khác nhau giữa nguồn; không coi cách viết description khác là mâu thuẫn |
| `external_links.rq` | Links ngoài và bằng chứng identity |

Nếu chưa nạp catalog vào Fuseki, truy vấn `AIModel` vẫn có thể ra 0 dù local
đã có dữ liệu. Kiểm tra bằng:

```sparql
PREFIX ex: <https://example.org/aimodels/>
SELECT (COUNT(?model) AS ?models) WHERE { ?model a ex:AIModel }
```

Nếu chỉ thấy ontology nhưng không thấy model instances, kiểm tra đã nạp
`src/data/gold/models.ttl` vào default graph đúng dataset chưa. Nếu dùng
named graph, query cần `GRAPH ?g { ... }` hoặc lựa chọn union default graph.

## 5. Thu thập lại hoặc dựng lại offline

```bash
cd /home/puda14/Desktop/Project/semantic-web/aimodels
export PYTHONPATH=src

# Online: public GET metadata; default là toàn catalog và mọi endpoint.
.venv/bin/python -m model_catalog.collect --workers 6
.venv/bin/python -m model_catalog.model_cards

# Extract recognized official pricing tables, checksum-bound to this snapshot.
.venv/bin/python -m model_catalog.official_sources
.venv/bin/python -m model_catalog.normalize
.venv/bin/python -m model_catalog.transform
.venv/bin/python -m model_catalog.link
.venv/bin/python -m model_catalog.validate
```

Nếu muốn giới hạn endpoint enrichment: `collect --endpoint-limit 30`,
ưu tiên Opus trước; danh mục model vẫn lấy toàn bộ. Không giả tạo endpoint
cho model thiếu thông tin. HTTP error tạo warnings; kiểm tra manifest.

Dựng offline từ snapshot hiện có:

```bash
export PYTHONPATH=src
.venv/bin/python -m model_catalog.collect --offline
.venv/bin/python -m model_catalog.model_cards --offline
.venv/bin/python -m model_catalog.official_sources
.venv/bin/python -m model_catalog.normalize
.venv/bin/python -m model_catalog.transform
.venv/bin/python -m model_catalog.link --offline
.venv/bin/python -m model_catalog.validate
```

Normalize ghi lại external_links.csv rỗng; chạy link sau normalize/transform
để tái tạo evidence và `linked_output.nt`. Offline không gọi API bên ngoài.
Sau khi RDF thay đổi, Fuseki vẫn dùng bản đã nạp trước đó tới khi bạn cập nhật.

## 6. Module Python: đầu vào và đầu ra

| Module | Xử lý | Input → output |
|---|---|---|
| `common.py` | Paths, identities, Decimal-independent I/O, GET retry, atomic file replacement | URL/records → bytes/JSON/CSV |
| `collect.py` | Catalog, từng provider endpoint, official docs, benchmark/review pages | Public HTTP GET → bronze nguyên gốc và manifest/checksum |
| `official_sources.py` | Parse schema đã nhận dạng; không suy đoán giá từ blog | HTML bronze → official-model-facts.json + extraction report |
| `model_cards.py` | Metadata repository thuộc danh sách publisher xác định rõ, không tải weights | HF public JSON → model-card snapshots, parameter/license/library/task observations |
| `normalize.py` | Tách model/family/org/offering, đổi đơn vị giá bằng Decimal, source observations | Bronze + facts/reviews config → silver CSV + coverage |
| `benchmarks.py` | Parse bảng Aider và mapping ID đã chỉ định; giữ cấu hình riêng | HTML/mapping → evaluations hoặc unmatched rows |
| `transform.py` | Typed RDF và provenance từng statement, bản XML tương đương | Silver → models.ttl/models.rdf + ontology RDF/XML + metadata |
| `link.py` | Kiểm tra official website ở Wikidata; DBpedia sameAs tới QID đã xác nhận | Online/cache → linked_output.nt + external_links.csv |
| `validate.py` | Checksums, IDs, dangling relations, CSV/RDF counts, CQs, OWL RL fixture | Snapshots/CSV/RDF → validation-report.json |
| `ask.py` | Query graph model local hoặc endpoint; không cần --dataset | `.rq` + graph → CSV trên terminal |

## 7. Giới hạn dữ liệu

- Một số listing là alias, free/batch variant hoặc router; giữ source ID
  và source kind, không coi mỗi listing là một model weights độc lập.
- Catalog created không phải release date. Không trả “model mới nhất toàn
  thế giới” từ ngày này. Tên/model ID không được tự suy ra ngày phát hành.
- Description/capability claims được attribution; hỗ trợ tools không chứng
  minh chất lượng coding. Thiếu benchmark/review không phải điểm zero.
- Model cards từ publisher namespaces Qwen, Meta Llama, Mistral, Z.AI,
  MiniMax, DeepSeek, Google và OpenAI bổ sung total checkpoint parameters,
  license, library và task khi trường có sẵn. Tổng parameter không phải
  active MoE parameter count. Chưa parse mọi benchmark từ mọi model card.
- Embedded Artificial Analysis metrics được lấy **qua OpenRouter**, không
  phải gọi trực tiếp AA API. API riêng của AA cần key và chưa được triển khai
  trong bản này; không đặt key thì catalog vẫn có embedded scores.
- Review hiện là tập nhỏ có biên tập; không crawler toàn Internet hoặc sao
  chép toàn văn review vào graph. Giá trong review không dùng làm current price.
- Giá non-token chưa xác định đơn vị giữ `unknown`, không nhân một triệu.
- Pricing overrides được lưu riêng với `priceTier` và boundary; query so
  direct/router chỉ so base rates và vẫn cần đọc điều kiện. Endpoint tag và
  cấu hình/quantization được giữ để phân biệt các offering cùng provider.
- Giá `priceAmount` đã áp dụng hệ số nguồn `discount` theo công thức
  `rawAmount × (1 − discount)`, rồi đổi sang USD/triệu token nếu đã xác định
  đơn vị token. Giá gốc và hệ số vẫn được giữ để kiểm tra; hệ số âm trong
  snapshot là phụ phí theo cùng công thức. `discount` null được coi là 0.
- Link một document không tự đạt identity link 5★. Chỉ xuất sameAs khi đã
  xác minh; example.org vẫn cần namespace/publication thực để thành LOD public.
- Mỗi nguồn có điều khoản riêng; metadata mới không mang license CC0 của
  OpenAlex. Tài liệu giá có thể thay đổi, parser schema fail sẽ báo rõ.
