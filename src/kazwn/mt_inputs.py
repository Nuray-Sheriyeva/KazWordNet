"""S4.1: build MT inputs "lemma: gloss", one per (synset, English lemma) pair of the frozen scope.

Each input carries a pool label: test (eval_test), dev (eval_dev) or rest (everything else).
Run: PYTHONPATH=src python -m kazwn.mt_inputs
"""
import csv
from collections import Counter
from pathlib import Path

from kazwn.kaikki import load_scope, scope_lemmas

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "data" / "eval"
OUT = ROOT / "data" / "raw" / "mt" / "inputs.tsv"
COLS = ["input_id", "synset_id", "lemma_en", "pos", "pool", "text"]


def read_ids(path):
    with open(path, encoding="utf-8", newline="") as f:
        return {r["synset_id"] for r in csv.DictReader(f, delimiter="\t")}


def build_inputs(rows, dev_ids, test_ids):
    out = []
    for r in rows:
        sid = r["synset_id"]
        pool = "test" if sid in test_ids else "dev" if sid in dev_ids else "rest"
        for lem in scope_lemmas(r):
            out.append({"input_id": f"{sid}|{lem}", "synset_id": sid, "lemma_en": lem,
                        "pos": r["pos"], "pool": pool, "text": f"{lem}: {r['gloss']}"})
    return out


def main():
    rows = load_scope()
    inputs = build_inputs(rows, read_ids(EVAL / "eval_dev.tsv"), read_ids(EVAL / "eval_test.tsv"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(inputs)
    print(f"wrote {len(inputs)} inputs -> {OUT}")
    print("inputs by pool:", dict(Counter(i["pool"] for i in inputs)))


if __name__ == "__main__":
    main()