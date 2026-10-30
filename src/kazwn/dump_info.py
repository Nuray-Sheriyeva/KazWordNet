"""Record the downloaded kaikki dump: size, date, sha256 -> manifest + paste-ready block.
Run: PYTHONPATH=src python -m kazwn.dump_info data/dumps/<dump> --url <download url> [--date YYYY-MM-DD]
"""
import argparse, datetime, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "raw" / "kaikki_dump.manifest.json"


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--url", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    p = Path(a.dump)
    m = {"url": a.url, "file": p.name, "size_bytes": p.stat().st_size,
         "downloaded": a.date, "sha256": sha256_file(p)}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"wrote {MANIFEST}\n\nPaste into docs/sources.md:\n")
    print(f"- Dump: {m['url']}\n- File: {m['file']} ({m['size_bytes']} bytes)\n"
          f"- Downloaded: {m['downloaded']}\n- sha256: {m['sha256']}")


if __name__ == "__main__":
    main()