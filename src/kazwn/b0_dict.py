"""S3: build the B0 (dictionary-only) candidate file from the kaikki en->kk extract.

B0 is sense-blind: every kk translation of a POS-matching English entry goes to every
synset containing that English lemma. Wiktionary's sense label is kept in the evidence only.
Run: PYTHONPATH=src python -m kazwn.b0_dict
"""
import json
from collections import Counter
from pathlib import Path

from kazwn.candidates import process_field, write_candidates, write_rejected
from kazwn.kaikki import GROUP, KAIKKI_POS, load_extract, load_scope, scope_lemmas

ROOT = Path(__file__).resolve().parents[2]
DUMP_VERSION = "2026-10-01"  # enwiktionary dump date, see docs/sources.md


def build_b0(rows, index, dump_version=DUMP_VERSION):
    cands, rejs = [], []
    for r in rows:
        allowed = KAIKKI_POS[GROUP[r["pos"]]]
        for lem in scope_lemmas(r):
            for rec in index.get(lem, []):
                if rec["pos"] not in allowed:
                    continue
                for t in rec["translations"]:
                    ev = {"dict": "kaikki", "entry_id": rec["entry_id"], "dump": dump_version}
                    if t.get("sense"):
                        ev["sense"] = t["sense"]
                    if t.get("tags"):
                        ev["tags"] = t["tags"]
                    c, x = process_field(r["synset_id"], lem, r["pos"], t["word"], "dict", [ev])
                    cands += c
                    rejs += x
    return cands, rejs


def main():
    rows, index = load_scope(), load_extract()
    cands, rejs = build_b0(rows, index)
    merged = write_candidates("dict", cands)
    write_rejected("dict", rejs)
    flags = Counter(f for c in merged for f in c.flags)
    pos = Counter()
    for sid in {c.synset_id for c in merged}:
        pos[next(r["pos"] for r in rows if r["synset_id"] == sid)] += 1
    print(json.dumps({
        "synsets_with_candidates": len({c.synset_id for c in merged}),
        "candidate_rows": len(merged),
        "rejected_rows": len(rejs),
        "rejected_reasons": dict(Counter(x.reason for x in rejs)),
        "flags": dict(flags),
        "synsets_by_pos": dict(pos),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()