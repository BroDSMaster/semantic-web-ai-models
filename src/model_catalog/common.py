"""Snapshot paths, safe identities and lossless I/O."""
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
BRONZE = ROOT / "src/data/bronze"
SILVER = ROOT / "src/data/silver"
GOLD = ROOT / "src/data/gold"
RES = ROOT / "res"
PUBLIC_SITE = "https://brodsmaster.github.io/semantic-web-ai-models/"
# Fragment URIs dereference to the published Turtle document on GitHub Pages.
BASE = PUBLIC_SITE + "data/aimodels.ttl#"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    content = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(content).hexdigest()


def uri(kind, key):
    return BASE + "resource/" + kind + "/" + quote(str(key), safe="")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if isinstance(content, bytes):
        temporary.write_bytes(content)
    else:
        temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def fetch(url, headers=None):
    request = Request(url, headers={"User-Agent": "AIModelLOD-capstone/2.0", **(headers or {})})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=25) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"HTTP {exc.code}: {url.split('?')[0]}") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError(f"Network failure: {url.split('?')[0]}") from None
        time.sleep(2 ** attempt)


def write_tables(tables, directory=SILVER):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        fields = sorted({key for row in rows for key in row}) or ["id"]
        with (directory / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def read_tables(directory=SILVER):
    tables = {}
    for path in sorted(Path(directory).glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            tables[path.stem] = list(csv.DictReader(handle))
    return tables
