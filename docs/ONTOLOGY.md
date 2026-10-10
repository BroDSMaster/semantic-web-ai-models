# Ontology và năm bước capstone cho model AI

Áp dụng [ONTOLOGY_ENGINEERING_SKILL.md](../../ONTOLOGY_ENGINEERING_SKILL.md):
scope → scenarios → competency questions → glossary → taxonomy → properties
→ constraints → validation. [Thiết kế đầy đủ](superpowers/specs/2026-10-05-ai-model-catalog-design.md)
ghi lý do identity, roles, sources và scope; [hướng dẫn](PIPELINE.md) mô tả chạy/query.

## 1. Define an ontology

Miền: model AI và các offering API có thông số/giá/đánh giá theo nguồn.
Người dùng: sinh viên trình bày capstone và người muốn tra model/provider.
Kịch bản chính: tra một phiên bản Opus, xem ai cung cấp, giá và URL kiểm chứng;
lọc model có tools/image input; xem benchmark có attribution.

| Class | Glossary / identity / example |
|---|---|
| AIModel | Model/listing được nguồn định danh. `openai/gpt-5.6-sol`; ID theo nguồn, không số dòng CSV |
| ModelFamily | Nhóm model liên quan. Claude là instance, không class cha của Opus |
| Organization | Tổ chức có các vai trò developer/host qua quan hệ; không dùng string thay entity |
| ModelOffering | Model + dịch vụ + endpoint. Azure qua OpenRouter khác Anthropic direct |
| Capability | Feature/parameter được công bố, ví dụ tools; không phải điểm chất lượng |
| Modality | Loại media như image; input/output là hai quan hệ |
| PriceSpecification | Giá + loại token + unit + điều kiện + nguồn + thời điểm |
| Benchmark | Metric/protocol + evaluator/version; không gộp các thang đo khác nhau |
| Evaluation | Một kết quả model trên benchmark trong cấu hình cụ thể |
| SourceDocument | Snapshot URL/content/checksum; document không đồng nhất với model |
| FactObservation | N-ary statement subject/property/value/source/time; giữ được mâu thuẫn |
| ExternalLink | Mapping identity có bằng chứng, không nối chỉ vì trùng tên |

Xem [sơ đồ toàn bộ ontology](ONTOLOGY_DIAGRAM.md) để xem đủ 12 classes, 17 object
properties, 41 datatype properties, quan hệ kế thừa và vocabulary chuẩn được tái sử dụng.

Namespace: `https://brodsmaster.github.io/semantic-web-ai-models/data/aimodels.ttl#`; ontology version 2.0 tại
`res/ontology.ttl`. Dùng RDF/RDFS/OWL, XSD, schema.org, PROV-O,
Dublin Core và DCAT. Class/property có label/comment/domain/range phù hợp;
trường dữ liệu được khai báo ở ontology thay vì hardcode không có ngữ nghĩa.
Ví dụ giả dùng `res/example-data.ttl`, không load vào dữ liệu thật.

Taxonomy kiểm tra “Every A is a B”: Organization là schema:Organization,
offering là schema:Service, price là schema:PriceSpecification và source document là
prov:Entity. Không dùng subclass để diễn
tả membership của model trong family hoặc offering của model.

Ba disjointness axiom loại trừ các kiểu thực thể không tương thích:
`AIModel` disjoint với `Organization` và `PriceSpecification`; `Evaluation`
disjoint với `Benchmark`. Reasoner báo mâu thuẫn nếu một individual đồng thời
thuộc hai class trong một cặp này.

Identity: percent-encoded source IDs; prices/observations/evaluations dùng
hash các trường identity và snapshot. Family identity gồm source namespace
và tên họ. Một vai trò hosting không biến organization thành model. Một model
không trở thành CheapModel/LatestModel theo giá hay thời điểm.

Quan hệ cốt lõi: belongsToFamily, developedBy, offersModel, hostedBy,
hasPrice, supportsCapability, inputModality/outputModality, evaluatedModel,
onBenchmark, hasRepository; provenance qua prov:wasDerivedFrom và FactObservation.
hasRepository nối model tới repository đã đối chiếu ID, range là schema:SoftwareSourceCode;
không thêm class riêng và không khẳng định repository đồng nhất với model/deployment.
Datatype giữ Decimal/integer/date/dateTime; unknown không được gán zero/false.
Không dùng OWL cardinality theo số lượng tình cờ trong snapshot.

Competency questions được hiện thực bởi 14 `.rq` tại `queries/`:
list Claude; Opus providers/prices; model details; tools/context/budget;
vision; direct-vs-router; benchmark/config/source; official facts;
coverage; conflicting observations; external link evidence; publisher parameter/license/task metadata. Query source
trả provenance cho các phát biểu và kết quả đánh giá.
Ngày phát hành chỉ thêm khi có nguồn xác minh; câu hỏi newest release toàn
thế giới nằm ngoài dữ liệu hiện tại, không thay bằng catalog timestamp.

Validation: fixtures có expected results cho giá zero/null, Decimal,
provider/developer, free/batch variants, catalog schema và query Opus.
Validator chạy mọi query trên graph thật, so CSV/RDF counts, kiểm tra checksum
và OWL RL trên dữ liệu đại diện. Full catalog reasoning và Fuseki runtime
không được tuyên bố đã kiểm chứng nếu chưa chạy.

## 2. Collect relevant data

OpenRouter GET catalog và endpoint của từng source ID; official pricing/model
docs của chín nhóm nhà phát hành và bảng benchmark Aider.
Bronze giữ bytes nguyên gốc và manifest URL/hash/time. Các document developer
chỉ là relatedDocumentation nếu chưa có parser field-level.

## 3. Transform into RDF / 4★

Official schema extractor tạo records có checksum. Normalize tạo entity/relations
CSV; transform tạo `models.ttl` và `models.rdf` của cùng graph. Giá prompt/output/
cache per-token đổi bằng Decimal sang USD/1M tokens, giữ giá và unit gốc.
Giá request/image/search không đổi sang token. Statement convenience triples
kèm observation đủ nguồn và thời điểm để truy vết và phát hiện mâu thuẫn.

## 4. Establish links / hướng tới 5★

Wikidata candidate organizations được kiểm tra P856 official domain; DBpedia
sameAs phải nối tới QID đã xác nhận. Lưu JSON responses, query và evidence CSV;
xuất `linked_output.nt`. Không đoán URI DBpedia từ tên. Project chỉ xuất sameAs
cấp tổ chức; không xuất sameAs cấp model.
`organization_links.py` xác minh 9 tổ chức với OpenAlex Institution bằng exact
local ID/name, OpenAlex ID/name, company type, homepage domain, ROR và QID khi có.
JSON gốc và checksum được đọc lại khi offline. Z.AI/Qwen/MiniMax được giữ ngoài
mapping cho tới khi xác định đúng thực thể tổ chức.
Xem [LINKING.md](LINKING.md) để xem bằng chứng và quan hệ riêng với repository/benchmark.
Nguồn API/docs là provenance; không xuất sameAs giữa model và trang tài liệu.
Để công bố 5★ đầy đủ cần URI dereferenceable và deployment phù hợp;
namespace GitHub Pages phục vụ file Turtle công khai sau khi workflow deploy.

## 5. SPARQL interface

`ask.py` load ontology + gold + links + metadata;
Fuseki load bốn file tương ứng vào default graph. Cùng `.rq` dùng cho terminal
và endpoint. RDF trong repo mới không tự thay dataset đang mở trên server.
Xem [PIPELINE.md](PIPELINE.md) để nạp và query Opus từng bước.
