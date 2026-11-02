"""B2: blind dev judging sheet for the LLM arms. Leaves the S4 sheet (dev_judgments.tsv) untouched.

Rows already judged in the S4 sheet are not judged again. The key file records every row an LLM arm
proposed (including those already judged) with in_s4_sheet = 1/0, so scoring can join both sheets.
Sources are candidate files data/candidates/<name>.tsv, e.g. llm_dev_v1,llm_dev_v1_medium.
Run:   PYTHONPATH=src python -m kazwn.judge_sheet_b2 --sources llm_dev_v1,llm_dev_v1_medium,...
Check: PYTHONPATH=src python -m kazwn.judge_sheet_b2 --check
"""
import argparse
import sys

from kazwn import judge_sheet as J
from kazwn.candidates import CAND_DIR, read_candidates
from kazwn.kaikki import load_scope
from kazwn.mt_inputs import EVAL, read_ids

SHEET = EVAL / "dev_judgments_b2.tsv"
KEY = EVAL / "dev_judging_key_b2.tsv"
KEY_COLS = ["key_id", "sources", "flags", "in_s4_sheet"]


def build(sources, dev_ids, gloss, s4_ids):
    """-> (new sheet rows for rows not in the S4 sheet, key rows for all rows the arms proposed)."""
    rows, keys = J.build_rows(sources, dev_ids, gloss)
    for k in keys:
        k["in_s4_sheet"] = "1" if k["key_id"] in s4_ids else "0"
    return [r for r in rows if r["key_id"] not in s4_ids], keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        res = J.check_rows(J.read_sheet(SHEET))
        print(res)
        sys.exit(1 if res["invalid_rows"] else 0)
    if not a.sources:
        sys.exit("FAILED: --sources is required")
    names = a.sources.split(",")
    if not all(n.startswith("llm_") for n in names):
        sys.exit("FAILED: only llm_* candidate files belong in this sheet (B0 and MT are in the S4 sheet)")
    s4_ids = {r["key_id"] for r in J.read_sheet()}
    sources = {n: read_candidates(CAND_DIR / f"{n}.tsv") for n in names}
    gloss = {r["synset_id"]: r["gloss"] for r in load_scope()}
    rows, keys = build(sources, read_ids(EVAL / "eval_dev.tsv"), gloss, s4_ids)
    existing = J.read_sheet(SHEET) if SHEET.exists() else []
    merged = J.merge_sheet(existing, rows)
    J.write_rows(SHEET, J.COLS, merged, "utf-8-sig")
    J.write_rows(KEY, KEY_COLS, keys, "utf-8")
    print(f"arms {len(names)}; rows proposed {len(keys)}, already in S4 sheet {sum(k['in_s4_sheet'] == '1' for k in keys)}")
    print(f"sheet: {len(merged)} rows ({len(merged) - len(existing)} new) -> {SHEET}; judged so far {J.check_rows(merged)['judged']}")


if __name__ == "__main__":
    main()