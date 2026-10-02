"""
Look at the real ADEME Base Carbone before building the importer.

  python scripts/inspect_ademe.py path/to/base_carbone.csv
  python scripts/inspect_ademe.py --api

CSV: download from https://www.data.gouv.fr/datasets/base-carbone-r-2
"""
import csv
import io
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

MAX_CELL = 90
MAX_DISTINCT = 25


def clip(value: str) -> str:
    value = value.replace("\n", " ")
    return value if len(value) <= MAX_CELL else value[:MAX_CELL] + "..."


def inspect_csv(path: str) -> None:
    with open(path, "rb") as fh:
        raw = fh.read()
    text, encoding = None, None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text, encoding = raw.decode(enc), enc
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text, encoding = raw.decode("latin-1"), "latin-1"

    try:
        delimiter = csv.Sniffer().sniff(text[:20000], delimiters=";,\t|").delimiter
    except csv.Error:
        delimiter = ";"

    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header, data = rows[0], rows[1:]
    width = len(header)
    data = [r + [""] * (width - len(r)) for r in data]

    print(f"encoding={encoding}  delimiter={delimiter!r}  rows={len(data)}  columns={width}\n")
    print("COLUMNS")
    for i, name in enumerate(header):
        print(f"  {i:>2}  {name}")

    print("\nFIRST 3 ROWS (non-empty cells only)")
    for row in data[:3]:
        print("  ---")
        for name, value in zip(header, row):
            if value.strip():
                print(f"  {name}: {clip(value)}")

    print(f"\nLOW-CARDINALITY COLUMNS (2 to {MAX_DISTINCT} distinct values)")
    for i, name in enumerate(header):
        counts = Counter(r[i].strip() for r in data if r[i].strip())
        if 1 < len(counts) <= MAX_DISTINCT:
            print(f"\n  {name}")
            for value, n in counts.most_common():
                print(f"    {n:>6}  {clip(value)}")


def inspect_api() -> None:
    """Uses the data-fair conventions that data.ademe.fr is built on (unverified)."""
    import httpx

    base = "https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner"
    meta = httpx.get(base, timeout=30).json()
    print("title:", meta.get("title"))
    print("count:", meta.get("count"), "| dataUpdatedAt:", meta.get("dataUpdatedAt"))
    print("\nSCHEMA")
    for f in meta.get("schema", []):
        print(f"  {f.get('key')}  [{f.get('type')}]  {f.get('title', '')}")
    sample = httpx.get(f"{base}/lines", params={"size": 3}, timeout=30).json()
    print("\nSAMPLE LINES")
    for row in sample.get("results", []):
        print(json.dumps(row, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    if sys.argv[1:] == ["--api"]:
        inspect_api()
    elif len(sys.argv) == 2:
        inspect_csv(sys.argv[1])
    else:
        print(__doc__)
