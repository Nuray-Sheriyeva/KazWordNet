"""S4.3: parse raw MT outputs ("headword: gloss translation"), pass headwords through S1.

Writes data/candidates/mt_<engine>.tsv (+ _rejected.tsv) and data/reports/mt_parse_<engine>.json.
Raw outputs are never edited. No colon / empty / overly long head => parse_fail, no candidate.
Run: PYTHONPATH=src python -m kazwn.mt_parse --engine nllb600m
"""
import argparse, json, re
from collections import Counter
from pathlib import Path

from kazwn.candidates import CAND_DIR, Rejected, process_field, write_candidates, write_rejected

ROOT = Path(__file__).resolve().parents[2]
MT_DIR = ROOT / "data" / "raw" / "mt"
REPORTS = ROOT / "data" / "reports"
COLONS = (":", "\uff1a")
MAX_HEAD_WORDS = 3  # my pick: a longer "head" means the colon was not a headword boundary


def extract_head(output):
    """-> (head, reason). reason is '' on success."""
    s = output.strip()
    pos = [s.find(c) for c in COLONS if c in s]
    if not pos:
        return None, "parse_fail:no_colon"
    i = min(pos)
    head = s[:i].strip()
    if not head:
        return None, "parse_fail:empty_head"
    if len(head.split()) > MAX_HEAD_WORDS:
        return None, "parse_fail:head_too_long"
    return head, ""


def parse_rows(raw_rows, engine):
    cands, rejs, parse_fail = [], [], Counter()
    for r in raw_rows:
        out = re.sub(r"[\t\r\n]+", " ", r["output"])
        ev = {"engine": engine, "input_id": r["input_id"], "raw": out}
        head, reason = extract_head(out)
        if head is None:
            parse_fail[reason] += 1
            rejs.append(Rejected(r["synset_id"], r["lemma_en"], out, r["pos"], "mt", reason, [ev]))
            continue
        c, x = process_field(r["synset_id"], r["lemma_en"], r["pos"], head, "mt", [ev])
        cands += c
        rejs += x
    return cands, rejs, parse_fail


def read_raw(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    a = ap.parse_args()
    raw = read_raw(MT_DIR / f"{a.engine}.jsonl")
    cands, rejs, parse_fail = parse_rows(raw, a.engine)
    merged = write_candidates("mt", cands, CAND_DIR / f"mt_{a.engine}.tsv")
    write_rejected("mt", rejs, CAND_DIR / f"mt_{a.engine}_rejected.tsv")
    s1 = Counter(x.reason for x in rejs if not x.reason.startswith("parse_fail"))
    report = {
        "engine": a.engine, "raw_rows": len(raw), "pools": dict(Counter(r["pool"] for r in raw)),
        "parse_ok": len(raw) - sum(parse_fail.values()), "parse_fail": dict(parse_fail),
        "s1_rejected": dict(s1), "candidate_rows": len(merged),
        "synsets_with_candidates": len({c.synset_id for c in merged}),
        "flags": dict(Counter(f for c in merged for f in c.flags)),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"mt_parse_{a.engine}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()