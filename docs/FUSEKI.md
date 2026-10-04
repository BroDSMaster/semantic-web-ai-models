# Chạy Apache Jena Fuseki

Apache Jena cung cấp RDF/SPARQL engine và TDB2; Fuseki là SPARQL server của
Jena. Project dùng **Fuseki 6.2.0, Java 21+**, Python chỉ làm ETL và terminal
query. Phiên bản và yêu cầu Java: [Apache Jena downloads](https://jena.apache.org/download/).

Các lệnh dưới chạy từ thư mục `aimodels/` trên Linux/bash.

## 1. Chuẩn bị Java và Fuseki

```bash
java -version
mkdir -p tools
curl -fL https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-6.2.0.tar.gz \
  -o tools/apache-jena-fuseki-6.2.0.tar.gz
curl -fL https://downloads.apache.org/jena/binaries/apache-jena-fuseki-6.2.0.tar.gz.sha512 \
  -o tools/apache-jena-fuseki-6.2.0.tar.gz.sha512
```

Đối chiếu SHA512 trước khi giải nén. File SHA512 của Apache có thể chứa một
hash hoặc kèm filename, nên kiểm tra bằng đoạn Python sau:

```bash
python - <<'PY'
import hashlib, re
from pathlib import Path
p = Path('tools/apache-jena-fuseki-6.2.0.tar.gz')
expected = re.search(r'\b[0-9a-fA-F]{128}\b', Path(str(p)+'.sha512').read_text()).group(0).lower()
actual = hashlib.file_digest(p.open('rb'), 'sha512').hexdigest()
assert actual == expected, 'SHA512 mismatch; do not extract'
print('SHA512 OK')
PY
tar -xzf tools/apache-jena-fuseki-6.2.0.tar.gz -C tools
```

Nếu bản 6.2.0 đã rời mirror, dùng cùng filenames tại
`https://archive.apache.org/dist/jena/binaries/`. Không trộn server và
checksum của các phiên bản khác nhau. Binary Apache giữ license/NOTICE
đi kèm; `tools/` không thuộc source code ETL.

## 2. Terminal thứ nhất: chạy server

```bash
bash scripts/start_fuseki.sh
```

- UI: <http://localhost:3030/>
- Dataset được cấu hình sẵn: `aimodels`
- SPARQL endpoint: <http://localhost:3030/aimodels/sparql>
- Graph Store: <http://localhost:3030/aimodels/data>
- Cấu hình: [res/fuseki-config.ttl](../res/fuseki-config.ttl)
- TDB2 giữ dữ liệu trong `run/tdb2`; không mất khi dừng bằng Ctrl+C.
- `run/fuseki` chứa runtime/config/log; không commit thư mục này.
- Script chạy trên localhost và dùng Java trong PATH, bỏ JAVA_HOME kế thừa
  để tránh đường dẫn JDK không tồn tại.

Nếu port 3030 đang dùng:

```bash
FUSEKI_PORT=3031 bash scripts/start_fuseki.sh
```

Khi đó đổi mọi URL của lệnh load/query sang port 3031.

## 3. Terminal thứ hai: nạp graph

```bash
bash scripts/load_fuseki.sh
```

Với port khác:

```bash
bash scripts/load_fuseki.sh http://localhost:3031/aimodels
```

Script POST bốn graph vào **default graph**: ontology, instance data, dataset
metadata, sameAs links. Triples với cùng URI/literal không bị nhân đôi khi
POST lại; cấu trúc OWL dùng blank nodes có thể có thêm anonymous nodes khi
nạp nhiều lần. Nếu đã thu thập snapshot khác, việc POST là merge:
nên dùng dataset mới để tránh lẫn snapshot, hoặc chủ động quản lý/xóa dữ liệu
cũ qua UI. Script không tự xóa database.

Cách giống HUST: vào UI → dataset `aimodels` → upload lần lượt:

1. `res/ontology.ttl` (hoặc `ontology.owl.xml`)
2. `src/data/gold/research.ttl` (hoặc `research.rdf`)
3. `res/linked_output.nt`
4. `res/dataset-metadata.ttl`

Chọn default graph. Không nhập cả hai serialization của cùng ontology/data
với ý định chúng là hai datasets; đó là cùng một graph ở hai cú pháp.

## 4. Truy vấn UI, terminal hoặc curl

UI → chọn `aimodels` → Query → paste nội dung
[cq07_external_links.rq](../queries/cq07_external_links.rq) → Run.

```bash
source .venv/bin/activate
python src/ask.py queries/count_classes.rq \
  --endpoint http://localhost:3030/aimodels/sparql
python src/ask.py queries/cq07_external_links.rq \
  --endpoint http://localhost:3030/aimodels/sparql
curl --fail-with-body --silent --show-error \
  -H 'Content-Type: application/sparql-query' \
  -H 'Accept: application/sparql-results+json' \
  --data-binary @queries/cq01_top_papers.rq \
  http://localhost:3030/aimodels/sparql
```

## 5. Suy luận

TDB2 ở cấu hình chính lưu asserted triples; nó không tự bật OWL RL. Demo
inverse `authoredPaper` bằng terminal:

```bash
python src/ask.py queries/inference_authored_paper.rq
python src/ask.py queries/inference_authored_paper.rq --reasoning
```

Lệnh đầu chỉ có CSV header vì inverse không assert trong gold. Lệnh thứ hai
có kết quả do OWL RL. Muốn xem closure trong Fuseki:

```bash
python src/validate.py --reasoning --export-inferred
curl --fail-with-body --silent --show-error -X POST \
  -H 'Content-Type: text/turtle' --data-binary @src/data/gold/research-inferred.ttl \
  'http://localhost:3030/aimodels/data?graph=https%3A%2F%2Fexample.org%2Faimodels%2Finferred'
```

Graph suy luận ở named graph riêng, giữ default graph cho dữ liệu assert.
Query named graph:

```sparql
PREFIX ex: <https://example.org/aimodels/>
SELECT ?authorship ?paper WHERE {
  GRAPH ex:inferred { ?authorship ex:authoredPaper ?paper }
} LIMIT 20
```

Đây là closure tính bởi owlrl rồi nạp vào Jena; không mô tả thành Jena tự
thực hiện OWL RL. Có thể cấu hình Jena reasoner khác khi cần; xem
[Fuseki configuration](https://jena.apache.org/documentation/fuseki2/fuseki-configuration.html).

## Xử lý lỗi thường gặp

- `Connection refused`: chưa chạy server hoặc sai port.
- Query không ra dữ liệu: kiểm tra đã load đủ bốn files vào default graph,
  đúng dataset, đúng prefix `https://example.org/aimodels/`.
- `Database lock`: chỉ chạy một server cho cùng `run/tdb2`; dừng server cũ.
- `UnsupportedClassVersionError`: Java đang chạy không đủ mới; Java 21+.
- Không tải được mirror: dùng Apache archive đúng phiên bản hoặc tải từ
  trang Apache và giải nén vào `tools/`.

Tham khảo: [running Fuseki](https://jena.apache.org/documentation/fuseki2/fuseki-server.html),
[configuration](https://jena.apache.org/documentation/fuseki2/fuseki-configuration.html).
