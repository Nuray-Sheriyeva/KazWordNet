"""S4.4b: build/extend the blind dev judging sheet; --check validates progress.

One row per (synset, Kazakh lemma) across sources, so each candidate is judged once.
Source membership is NOT in the sheet (it is in dev_judging_key.tsv). Existing judgments are preserved.
Run: PYTHONPATH=src python -m kazwn.judge_sheet [--sources b0_dict,mt_tilmash,mt_nllb600m]
     PYTHONPATH=src python -m kazwn.judge_sheet --check
"""
import argparse, csv, random, sys
from pathlib import Path

from kazwn.candidates import CAND_DIR, read_candidates
from kazwn.kaikki import load_scope
from kazwn.mt_inputs import EVAL, read_ids

SHEET = EVAL / "dev_judgments.tsv"
KEY = EVAL / "dev_judging_key.tsv"
COLS = ["key_id", "synset_id", "pos", "lemma_en", "gloss", "lemma_kk", "correct", "error_category", "notes"]
ERRORS = {"wrong_sense", "calque", "russian_loan", "variant", "form", "other"}
SEED = 7


def build_rows(sources, dev_ids, gloss, seed=SEED):
    """sources: {name: [Candidate]} -> (sheet rows, key rows)."""
    groups = {}
    for name, cands in sources.items():
        for c in cands:
            if c.synset_id not in dev_ids:
                continue
            g = groups.setdefault((c.synset_id, c.lemma_kk), {"pos": c.pos, "en": set(), "src": set(), "flags": set()})
            g["en"].update(x for x in c.lemma_en.split("|") if x)
            g["src"].add(name)
            g["flags"].update(c.flags)
    rows, keys = [], []
    for sid in sorted({s for s, _ in groups}):
        lemmas = sorted(l for s, l in groups if s == sid)
        random.Random(f"{seed}|{sid}").shuffle(lemmas)
        for lk in lemmas:
            g = groups[(sid, lk)]
            kid = f"{sid}|{lk}"
            rows.append({"key_id": kid, "synset_id": sid, "pos": g["pos"], "lemma_en": "|".join(sorted(g["en"])),
                         "gloss": gloss[sid], "lemma_kk": lk, "correct": "", "error_category": "", "notes": ""})
            keys.append({"key_id": kid, "sources": "|".join(sorted(g["src"])), "flags": "|".join(sorted(g["flags"]))})
    return rows, keys


def merge_sheet(existing, new_rows):
    seen = {r["key_id"] for r in existing}
    merged = existing + [r for r in new_rows if r["key_id"] not in seen]
    return sorted(merged, key=lambda r: r["synset_id"])  # stable: existing order kept within a synset


def read_sheet(path=SHEET):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_rows(path, cols, rows, enc):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=enc, newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def check_rows(rows):
    bad = [r["key_id"] for r in rows if r["correct"].strip() not in ("", "0", "1")
           or r["error_category"].strip() not in ERRORS | {""}]
    judged = [r for r in rows if r["correct"].strip() in ("0", "1")]
    return {"total": len(rows), "judged": len(judged), "remaining": len(rows) - len(judged),
            "invalid_rows": bad,
            "incorrect_without_category": sum(1 for r in judged if r["correct"].strip() == "0" and not r["error_category"].strip()),
            "correct_with_category": sum(1 for r in judged if r["correct"].strip() == "1" and r["error_category"].strip())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="b0_dict,mt_tilmash,mt_nllb600m")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        res = check_rows(read_sheet())
        print(res)
        sys.exit(1 if res["invalid_rows"] else 0)
    sources = {n: read_candidates(CAND_DIR / f"{n}.tsv") for n in a.sources.split(",")}
    gloss = {r["synset_id"]: r["gloss"] for r in load_scope()}
    rows, keys = build_rows(sources, read_ids(EVAL / "eval_dev.tsv"), gloss)
    existing = read_sheet() if SHEET.exists() else []
    merged = merge_sheet(existing, rows)
    write_rows(SHEET, COLS, merged, "utf-8-sig")
    write_rows(KEY, ["key_id", "sources", "flags"], keys, "utf-8")
    print(f"sheet: {len(merged)} rows ({len(merged) - len(existing)} new) -> {SHEET}")
    print("judged so far:", check_rows(merged)["judged"])


if __name__ == "__main__":
    main()