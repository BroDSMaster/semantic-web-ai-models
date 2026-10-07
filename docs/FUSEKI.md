# Chạy Jena Fuseki cho aimodels

Apache Jena xử lý RDF; Fuseki cung cấp server SPARQL và giao diện web. Cần Java 21+; project cấu hình binary Fuseki 6.2.0. Chạy các lệnh từ thư mục `aimodels/`.

## 1. Chuẩn bị

```bash
java -version
```

Binary phải ở `tools/apache-jena-fuseki-6.2.0/fuseki-server`. Nếu chưa có, tải bản 6.2.0 từ [Apache Jena](https://jena.apache.org/download/) hoặc archive cùng phiên bản, kiểm tra checksum Apache công bố rồi giải nén vào tools/. Hai project có thể dùng bản Fuseki riêng; mỗi môi trường Python cài từ requirements.txt của project đó.

## 2. Chạy server

```bash
bash scripts/start_fuseki.sh
```

- UI: http://localhost:3030/
- Dataset: `aimodels`
- SPARQL endpoint: http://localhost:3030/aimodels/sparql
- Graph Store: http://localhost:3030/aimodels/data
- Config: [fuseki-config.ttl](../res/fuseki-config.ttl)
- Database TDB2: `run/tdb2-models`; runtime: `run/fuseki-models`.

Giữ terminal mở; Ctrl+C để dừng. Nếu cổng đã có server khác, dừng server đó hoặc đặt `FUSEKI_PORT=3032 bash scripts/start_fuseki.sh` rồi đổi port trong các URL nạp/query tương ứng. Không mở hai server cùng ghi một TDB2 store.

## 3. Nạp dữ liệu bằng terminal thứ hai

```bash
bash scripts/load_fuseki.sh
```

Để nạp vào URL tùy chọn:

```bash
bash scripts/load_fuseki.sh http://localhost:3030/aimodels/data
```

Hoặc UI → dataset → Add data, nạp bốn file vào default graph (để trống graph name):

1. `res/ontology.ttl`
2. `src/data/gold/models.ttl`
3. `res/linked_output.nt`
4. `res/dataset-metadata.ttl`

Ontology có bản XML `ontology.rdf` và data có bản `models.rdf`; mỗi graph chỉ chọn một định dạng. Loader POST để thêm dữ liệu, không xóa graph cũ. Nạp nhiều snapshots sẽ giữ cả thông tin cũ/mới; dùng dataset mới nếu muốn chỉ giữ một snapshot.

## 4. Query

UI → dataset `aimodels` → Query → dán nội dung file [opus_providers_prices.rq](../queries/opus_providers_prices.rq) → ▶.

Hoặc sau khi activate Python environment:

```bash
python src/ask.py queries/opus_providers_prices.rq \
  --endpoint http://localhost:3030/aimodels/sparql
```

Query local cùng file (không cần server):

```bash
python src/ask.py queries/opus_providers_prices.rq
```

Nếu có 0 kết quả, kiểm tra đúng dataset/prefix và đã nạp instance data vào default graph. Tạo lại RDF trên đĩa không tự cập nhật bản Fuseki. Lần tách project ngày 07/10/2026 không khởi động hoặc chỉnh dữ liệu server; các kiểm chứng runtime trước đó chỉ là lịch sử.
