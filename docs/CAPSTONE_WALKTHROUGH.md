# Giải thích project theo 5 bước capstone

Tài liệu này giải thích nhánh **nghiên cứu OpenAlex**. Với catalog model,
provider và giá API mới, đọc [MODEL_ONTOLOGY.md](MODEL_ONTOLOGY.md) cho năm
bước capstone và [MODEL_CATALOG.md](MODEL_CATALOG.md) cho input/output và query.

Project mô tả **nghiên cứu AI/LLM**: bài báo, người viết, tổ chức, nguồn xuất
bản và chủ đề nghiên cứu. Tài liệu này giải thích cách thiết kế ontology và
trách nhiệm, đầu vào, đầu ra của từng file trong pipeline.

```text
Thiết kế ontology
        ↓
OpenAlex API → JSON nguồn
        ↓
Chuẩn hóa JSON → các bảng CSV
        ↓
Chuyển CSV → RDF theo ontology
        ↓
Bổ sung liên kết OpenAlex/Wikidata/DBpedia
        ↓
Truy vấn bằng SPARQL local hoặc Fuseki
```

Các lệnh bên dưới là hướng dẫn để bạn tự thực hiện từ thư mục `aimodels/`,
sau khi kích hoạt `.venv`. Đọc tài liệu không tự chạy các lệnh này.

## 1. Define an ontology for the selected domain

### Ontology là gì?

Ontology là **mô hình mô tả những loại thực thể tồn tại, thuộc tính của
chúng và quan hệ giữa chúng**.

Bước này là công việc phân tích và thiết kế. Không có script Python tự
quyết định toàn bộ ontology từ dữ liệu. File chính là
[res/ontology.ttl](../res/ontology.ttl).

### Đầu vào của việc thiết kế

- Miền được chọn: nghiên cứu AI/LLM.
- Những câu hỏi hệ thống cần trả lời.
- Cấu trúc dữ liệu mà OpenAlex cung cấp.
- Phương pháp trong [ONTOLOGY_ENGINEERING_SKILL.md](../../ONTOLOGY_ENGINEERING_SKILL.md).

### Xác định hệ thống cần trả lời gì

Ví dụ:

- Bài nào có nhiều trích dẫn?
- Ai viết một bài?
- Tác giả khai báo affiliation nào trong bài đó?
- Những tổ chức nào cùng tham gia một bài?
- Bài thuộc chủ đề và lĩnh vực nào?
- Entity nào liên kết với Wikidata hoặc DBpedia?

Đây là **competency questions**. Các câu hỏi này quyết định những thực thể
và quan hệ cần có trong ontology. Khi có RDF, chúng được chuyển thành các
truy vấn SPARQL để kiểm tra mô hình có trả lời được yêu cầu hay không.

### Xác định các lớp

| Class | Vì sao cần? |
|---|---|
| ResearchPaper | Đại diện cho bài nghiên cứu |
| Person | Đại diện cho người viết bài |
| ResearchInstitution | Đại diện cho tổ chức có affiliation |
| PublicationSource | Đại diện cho journal, conference, repository |
| Publisher | Đại diện cho tổ chức xuất bản |
| ResearchTopic | Chủ đề nghiên cứu cụ thể |
| ResearchSubfield | Nhóm chủ đề, ví dụ Artificial Intelligence |
| ResearchField | Lĩnh vực, ví dụ Computer Science |
| ResearchDomain | Nhóm lĩnh vực rộng hơn |
| Authorship | Một người tham gia viết một bài cụ thể |

**Person là class**, còn một người cụ thể như Daniel Povey là **instance
của Person**. “Computer Science” là một concept cụ thể, được biểu diễn bằng
instance của ResearchField.

Không tạo class cho mọi cột trong dữ liệu. Năm xuất bản, số trích dẫn và
open access là giá trị; affiliation là quan hệ có bối cảnh.

### Tại sao cần Authorship?

Giả sử:

```text
Người A viết bài X với affiliation ở tổ chức M.
Người A viết bài Y với affiliation ở tổ chức N.
```

Nếu chỉ nối Person trực tiếp với cả M và N, ta sẽ mất thông tin tổ chức nào
được khai báo trong bài nào. Ontology giữ bối cảnh bằng:

```text
Bài X → Authorship X-A → Người A
                       → Tổ chức M

Bài Y → Authorship Y-A → Người A
                       → Tổ chức N
```

Vị trí tác giả và trạng thái corresponding author cũng thuộc Authorship.
Affiliation trong bài không khẳng định nơi làm việc hiện tại của người đó.

### Xác định các quan hệ và thuộc tính

| Property | Chủ thể → đối tượng |
|---|---|
| hasAuthorship | Paper → Authorship |
| authorPerson | Authorship → Person |
| affiliatedInstitution | Authorship → Institution |
| publishedIn | Paper → PublicationSource |
| publishedBy | PublicationSource → Publisher |
| hasTopic | Paper → Topic |
| inSubfield | Topic → Subfield |
| inField | Subfield → Field |
| inDomain | Field → Domain |
| dcterms:references | Paper → công trình được tham khảo |

Những thông tin như năm, citation count và open access được biểu diễn bằng
giá trị có kiểu:

```text
publicationYear → xsd:gYear
citationCount   → xsd:nonNegativeInteger
isOpenAccess    → xsd:boolean
```

Topic **thuộc** Subfield là quan hệ phân loại. Không dùng subclass để nói
rằng mọi Topic đều là Subfield. Subclass được dùng khi “mọi A là một B”,
chẳng hạn ResearchPaper là schema:ScholarlyArticle và Person là schema:Person.

Domain/range của property giúp suy ra loại thực thể. Chúng không phải một
cơ chế bắt buộc điền đủ cột trong CSV; việc kiểm tra dữ liệu được thực hiện
bằng validator riêng.

### Đầu ra của bước 1

| File | Nội dung |
|---|---|
| [ontology.ttl](../res/ontology.ttl) | Định nghĩa các lớp, properties và axioms |
| [requirements.md](requirements.md) | Phạm vi, kịch bản và yêu cầu |
| [competency-questions.md](competency-questions.md) | Câu hỏi cần trả lời, truy vấn và expected answers |
| [glossary.md](glossary.md) | Định nghĩa thuật ngữ và phân biệt class/instance/role/value |
| [ontology-design.md](ontology-design.md) | Giải thích các quyết định thiết kế |

`ontology.owl.xml` là cùng ontology ở cú pháp RDF/XML, được tạo ở bước
chuyển đổi để dùng với các công cụ như Protégé.

## 2. Collect relevant data in this domain

File phụ trách: [collect_data.py](../src/collect_data.py).

Script gọi **OpenAlex API** và lưu phản hồi JSON.

| Thành phần | Nội dung |
|---|---|
| Đầu vào | Search, giới hạn số bài và giới hạn enrichment |
| Xử lý | Gọi API, phân trang, lấy works và bổ sung full records của institutions/sources phổ biến |
| Đầu ra | Các JSON trong src/data/bronze/ |

Cấu hình mặc định tìm `"large language models"`, chọn primary field
Computer Science, giữ article/conference-paper/preprint/review và loại
paratext. Các bản ghi proceedings collection không được coi là bài riêng lẻ.

### Các file đầu ra

| File trong bronze/ | Chứa gì? |
|---|---|
| [openalex_works.json](../src/data/bronze/openalex_works.json) | Metadata của 200 bài trong snapshot đi kèm |
| [openalex_institutions.json](../src/data/bronze/openalex_institutions.json) | Full records của tối đa 25 tổ chức phổ biến |
| [openalex_sources.json](../src/data/bronze/openalex_sources.json) | Full records của tối đa 25 nguồn xuất bản phổ biến |
| [collection_manifest.json](../src/data/bronze/collection_manifest.json) | Điều kiện tìm kiếm, URL requests, thời điểm và số lượng thu thập |

Một work trong JSON có thể chứa:

```text
ID, title, DOI, năm/ngày xuất bản
citation count, open access
danh sách authorships
    ├── thông tin người viết
    └── danh sách institutions
nguồn xuất bản
danh sách topics
danh sách referenced works
```

### Vì sao giữ JSON?

Dữ liệu có nhiều cấp lồng nhau. Một bài có nhiều người, một người trong bài
có thể có nhiều affiliations. JSON giữ được cấu trúc nguồn trước khi tách
thành bảng.

DOI, ORCID và ROR được lấy từ metadata OpenAlex. Project không thu thập
riêng toàn bộ dataset của ba hệ thống định danh này. Full records bổ sung
thông tin cho tổ chức/source đã xuất hiện trong works; publisher được lấy
từ host organization có ID P trong source records.

Ví dụ lệnh thu thập mới, cần Internet:

```bash
python src/collect_data.py --limit 200 --enrich-limit 25
```

Nếu dùng snapshot đã có trong repo, bạn có thể bắt đầu từ bước chuẩn hóa.

## 3. Transform collected data into 4-star standard

Bước này có hai phần xử lý: **JSON → CSV**, sau đó **CSV → RDF**.

### 3a. Chuẩn hóa bằng clean_data.py

File: [clean_data.py](../src/clean_data.py).

| Thành phần | Nội dung |
|---|---|
| Đầu vào | Ba JSON OpenAlex trong bronze |
| Xử lý | Tách entities và quan hệ, loại trùng, kiểm tra phạm vi, chuẩn hóa dữ liệu |
| Đầu ra | Các CSV trong src/data/silver/ và cleaning-report.json |

Các bảng entities:

```text
papers.csv
people.csv
institutions.csv
sources.csv
publishers.csv
topics.csv
subfields.csv
fields.csv
domains.csv
authorships.csv
```

Các bảng quan hệ:

```text
authorship_institutions.csv
paper_topics.csv
references.csv
```

Ví dụ, một authorship được tách thành:

```text
authorships.csv:
authorship ID | paper ID | person ID | position | corresponding

authorship_institutions.csv:
authorship ID | institution ID
```

Nhờ dùng ID, cùng một người xuất hiện trong nhiều bài vẫn chỉ có một dòng
trong people.csv, nhưng có nhiều dòng trong authorships.csv. Entity thiếu
author ID không được tạo thành một person giả; report ghi số entries bị bỏ.

### 3b. Chuyển CSV thành RDF bằng transform.py

File: [transform.py](../src/transform.py).

| Thành phần | Nội dung |
|---|---|
| Đầu vào | Các CSV silver, ontology Turtle và collection manifest |
| Xử lý | Tạo URI ổn định, ánh xạ cột/quan hệ thành RDF triples, gán kiểu dữ liệu |
| Đầu ra | Research RDF, ontology RDF/XML, dataset metadata và transformation report |

Ví dụ minh họa với ID rút gọn W1/A1/I1 dưới đây là synthetic, không phải
record nguồn thật. Prefix chỉ viết tắt phần đầu URI:

```turtle
@prefix ex: <https://example.org/aimodels/> .
@prefix paper: <https://example.org/aimodels/resource/paper/> .
@prefix authorship: <https://example.org/aimodels/resource/authorship/> .
@prefix person: <https://example.org/aimodels/resource/person/> .
@prefix institution: <https://example.org/aimodels/resource/institution/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

paper:W1
    a ex:ResearchPaper ;
    dcterms:title "Example research paper" ;
    ex:publicationYear "2024"^^xsd:gYear ;
    ex:citationCount "100"^^xsd:nonNegativeInteger ;
    ex:hasAuthorship authorship:W1-A1 .

authorship:W1-A1
    a ex:Authorship ;
    ex:authorPerson person:A1 ;
    ex:affiliatedInstitution institution:I1 .
```

Mỗi phát biểu là một triple:

```text
Chủ thể → Quan hệ → Đối tượng
```

Ví dụ `paper:W1 a ex:ResearchPaper` khẳng định loại của bài; cạnh
`hasAuthorship` nối bài với một authorship. URI bài thật giữ OpenAlex W ID,
nên không đổi theo tên bài hoặc vị trí dòng CSV.

### Các file đầu ra

| File | Nội dung |
|---|---|
| [research.ttl](../src/data/gold/research.ttl) | Instance graph bằng Turtle |
| [research.rdf](../src/data/gold/research.rdf) | Cùng graph bằng RDF/XML |
| [ontology.owl.xml](../res/ontology.owl.xml) | Ontology bằng RDF/XML |
| [dataset-metadata.ttl](../res/dataset-metadata.ttl) | Mô tả nguồn, license metadata và snapshot |
| [transformation-report.json](../src/data/gold/transformation-report.json) | Thống kê chuyển đổi |

Phần kỹ thuật hướng tới 4 sao nằm ở **RDF, URI HTTP ổn định và vocabulary
chuẩn**. Để công bố LOD 4 sao trên Web, namespace mẫu example.org còn cần
được thay bằng namespace có dịch vụ trả dữ liệu khi truy cập URI, cùng
quyền sử dụng và bản dữ liệu công khai phù hợp.

Lệnh cho hai phần:

```bash
python src/clean_data.py
python src/transform.py
```

## 4. Find and establish links to other datasets to obtain 5-star standard

File phụ trách: [link_entities.py](../src/link_entities.py).

Script xác định **URI local và URI bên ngoài cùng đại diện cho một thực thể**.

| Thành phần | Nội dung |
|---|---|
| Đầu vào | IDs trong silver, collection manifest và các nguồn đối chiếu hoặc cache |
| Xử lý | Khớp định danh, kiểm tra bằng chứng, tạo triples owl:sameAs |
| Đầu ra | Links RDF, bảng bằng chứng, cache phản hồi và linking report |

### Ba đường liên kết

1. **OpenAlex:** URI local được tạo từ đúng OpenAlex entity ID.
2. **Wikidata:** lấy QID được OpenAlex khai báo; với một số institutions
   thiếu QID, đối chiếu chính xác ROR bằng property P6782.
3. **DBpedia:** hỏi resource nào khai báo owl:sameAs với QID đã xác định.

Một trường hợp trong dữ liệu là Microsoft:

```text
Local institution
https://example.org/aimodels/resource/institution/I1290206253
       ↓
OpenAlex institution I1290206253
       ↓
Wikidata Q2283
       ↓
DBpedia resource Microsoft
```

Link được xuất dạng:

```turtle
<https://example.org/aimodels/resource/institution/I1290206253>
    <http://www.w3.org/2002/07/owl#sameAs>
    <http://dbpedia.org/resource/Microsoft> .
```

owl:sameAs nghĩa là **cùng thực thể**, không chỉ giống tên hoặc có liên
quan. Linker không đoán DBpedia resource từ tên tổ chức; chỉ xuất links có
bằng chứng định danh từ nguồn.

### Các file đầu ra

| File | Vai trò |
|---|---|
| [linked_output.nt](../res/linked_output.nt) | Những triples identity links được chấp nhận |
| [entity_links.csv](../res/entity_links.csv) | Bằng chứng: method, ID chung, nguồn và thời điểm |
| [external_lookups.json](../src/data/bronze/external_lookups.json) | Query và phản hồi từ Wikidata/DBpedia |
| [linking-report.json](../res/linking-report.json) | Số links và warnings |

### Online và offline khác nhau thế nào?

- Online gọi endpoint để lấy bằng chứng mới.
- `--offline` dùng phản hồi đã lưu trong cache.

Lệnh tương ứng:

```bash
# Online, cần Internet
python src/link_entities.py

# Offline, dùng bằng chứng đã lưu
python src/link_entities.py --offline
```

Khi chạy offline, script không gọi DBpedia. Các cảnh báo HTTP 503 được đọc
lại từ lịch sử; QID chưa có phản hồi thành công thì chưa được bổ sung link.
Các links đã xác nhận vẫn được xuất.

Liên kết ngoài là phần hướng tới mức 5 sao: graph local kết nối với những
định danh trong datasets khác. Điều kiện công bố LOD public của bước 3 vẫn
cần được đáp ứng khi đưa dự án lên Web.

## 5. Provide an interface via SPARQL endpoint/terminal to query data

Có hai cách truy vấn: terminal local và endpoint Apache Jena Fuseki.

### Cách A: terminal local bằng ask.py

File: [ask.py](../src/ask.py).

| Thành phần | Nội dung |
|---|---|
| Đầu vào | Một file SPARQL .rq |
| Xử lý | Đọc và kết hợp ontology, research data, links, metadata; thực thi SPARQL bằng RDFLib |
| Đầu ra | Bảng CSV trên terminal, hoặc boolean với ASK |

Ví dụ lệnh:

```bash
python src/ask.py queries/cq01_top_papers.rq
```

Script đọc bốn file:

```text
res/ontology.ttl
src/data/gold/research.ttl
res/linked_output.nt
res/dataset-metadata.ttl
```

Sau đó thực thi nội dung cq01_top_papers.rq. Cách này không cần server
Fuseki. Nội dung queries nằm trong [queries/](../queries/).

### Cách B: endpoint Apache Jena Fuseki

| File/thành phần | Làm gì? |
|---|---|
| [fuseki-config.ttl](../res/fuseki-config.ttl) | Định nghĩa dataset aimodels, endpoints và vị trí TDB2 |
| [start_fuseki.sh](../scripts/start_fuseki.sh) | Khởi động server |
| [load_fuseki.sh](../scripts/load_fuseki.sh) | Nạp bốn file RDF vào default graph |
| Apache Jena Fuseki | Nhận và thực thi SPARQL qua HTTP |
| run/tdb2/ | Lưu graph của server trên đĩa |

Endpoint:

```text
http://localhost:3030/aimodels/sparql
```

Bạn có thể gửi truy vấn qua giao diện web hoặc qua CLI:

```bash
python src/ask.py queries/cq01_top_papers.rq \
  --endpoint http://localhost:3030/aimodels/sparql
```

Khi có --endpoint, ask.py gửi truy vấn đến Fuseki và in kết quả server trả
về. Nó không tự đọc các file RDF local để trả lời truy vấn đó. File RDF
trong repo thay đổi thì graph đã nạp trong Fuseki cần được cập nhật riêng.

Hướng dẫn khởi động/nạp dữ liệu: [FUSEKI.md](FUSEKI.md). TDB2 có thể đã giữ
graph của lần chạy trước; kiểm tra dataset trước khi quyết định nạp lại.

### File kiểm tra bổ trợ: validate.py

[validate.py](../src/validate.py) đọc cùng bốn file RDF, kiểm tra cấu trúc,
typed literals, Authorship và chạy 10 competency queries. Nếu bật
--reasoning, nó còn tính OWL RL closure.

| Thành phần | Nội dung |
|---|---|
| Đầu vào | Ontology, instance graph, links, metadata và các truy vấn CQ |
| Xử lý | Kiểm tra dữ liệu; thực thi CQs; optional OWL RL và kiểm tra lỗi logic theo rule checks |
| Đầu ra | res/validation-report.json; optional gold/research-inferred.ttl |

Inferred graph chỉ được xuất khi có --reasoning --export-inferred. Cấu hình
Fuseki chính không tự bật OWL RL; closure của CLI và graph asserted của
server là hai lựa chọn cần phân biệt.

Ví dụ lệnh kiểm tra:

```bash
python src/validate.py
python src/validate.py --reasoning
```

## Bảng tra trách nhiệm từng file

| File | Chức năng chính |
|---|---|
| ontology.ttl | Định nghĩa mô hình dữ liệu |
| collect_data.py | Lấy dữ liệu từ nguồn |
| clean_data.py | Chuẩn hóa dữ liệu thành các bảng |
| transform.py | Chuyển các bảng thành RDF |
| link_entities.py | Xác lập liên kết danh tính ngoài |
| validate.py | Kiểm tra graph và khả năng trả lời câu hỏi |
| ask.py | Thực thi truy vấn SPARQL |
| start_fuseki.sh | Bật server |
| load_fuseki.sh | Nạp graph cho server |

[common.py](../src/common.py) chứa các hàm dùng chung như đọc/ghi file, tạo
URI và gọi JSON API. Nó hỗ trợ các bước trên, không phải một bước thu thập
hay dataset riêng.

Đọc thêm [README](../README.md) để xem overview hệ thống, danh mục từng tập
dữ liệu và số liệu snapshot; [VALIDATION.md](VALIDATION.md) mô tả kết quả
kiểm tra đã lưu và giới hạn của kết luận.
