"""S8a: blind test-pool judging sheets (owner first, then the checker). Systems must be frozen (S7).

One row per (synset, lemma) pair proposed by any system on the 100 test synsets; each pair is judged once
per judge. Source and system membership live only in the key file (do not open it until judging is finished).
The checker sheet carries no labels or notes: it is the owner's rows blanked, with a different within-synset order.
Run:   PYTHONPATH=src python -m kazwn.test_sheet            (owner sheet + key)
       PYTHONPATH=src python -m kazwn.test_sheet --checker  (checker sheet)
"""
import argparse
import json
import random
import sys

from kazwn import judge_sheet as J
from kazwn import mt_dev_score as M
from kazwn import systems_freeze as F
from kazwn.candidates import CAND_DIR, FILES, SOURCES, read_candidates

OWNER_SHEET = M.ROOT / "data/eval/test_judgments_owner.tsv"
CHECKER_SHEET = M.ROOT / "data/eval/test_judgments_checker.tsv"
KEY = M.ROOT / "data/eval/test_judging_key.tsv"
KEY_COLS = ["key_id", "sources", "flags", "systems"]
CHECKER_SEED = 11


class SheetError(Exception):
    pass


def systems_of(srcs):
    s = set()
    if "dict" in srcs:
        s.add("B0")
    if srcs & {"dict", "mt"}:
        s.add("B1")
    if "llm" in srcs:
        s.add("B2")
    if len(srcs) >= 2:
        s.add("B3")
    return sorted(s)


def build(by_source, test_ids, gloss):
    rows, keys = J.build_rows(by_source, test_ids, gloss)
    for k in keys:
        k["systems"] = "|".join(systems_of(set(k["sources"].split("|"))))
    return rows, keys


def checker_rows(owner_rows, seed=CHECKER_SEED):
    """Owner rows with judgments, notes and categories removed; lemma order reshuffled within each synset."""
    by = {}
    for r in owner_rows:
        by.setdefault(r["synset_id"], []).append(r)
    out = []
    for sid in sorted(by):
        g = list(by[sid])
        random.Random(f"{seed}|{sid}").shuffle(g)
        out += [dict(r, correct="", error_category="", notes="") for r in g]
    return out


def verify(owner, key, checker, sets, test_ids, gloss):
    """sets: {"B0","B1","B2","B3": {(synset_id, lemma_kk)}} restricted to the test pool."""
    f = []
    ids = [r["key_id"] for r in owner]
    if len(ids) != len(set(ids)):
        f.append("owner sheet: duplicate key_id")
    kmap = {k["key_id"]: k for k in key}
    if len(kmap) != len(key):
        f.append("key file: duplicate key_id")
    if set(ids) != set(kmap):
        f.append("owner sheet and key file have different key_ids")
    expected = sets["B1"] | sets["B2"]
    got = {(r["synset_id"], r["lemma_kk"]) for r in owner}
    if got != expected:
        f.append(f"pair set differs from B1 union B2 on test (missing {len(expected - got)}, extra {len(got - expected)})")
    for r in owner:
        if r["key_id"] != f"{r['synset_id']}|{r['lemma_kk']}":
            f.append(f"{r['key_id']}: key_id != synset_id|lemma_kk")
        if r["synset_id"] not in test_ids:
            f.append(f"{r['key_id']}: not a test-pool synset")
        if gloss.get(r["synset_id"]) != r["gloss"]:
            f.append(f"{r['key_id']}: gloss differs from the frozen scope")
    for p in got:
        k = kmap.get(f"{p[0]}|{p[1]}")
        if k is None:
            continue
        want = sorted(n for n in ("B0", "B1", "B2", "B3") if p in sets[n])
        if k["systems"].split("|") != want:
            f.append(f"{p[0]}|{p[1]}: key systems {k['systems']} != {'|'.join(want)}")
    if checker is not None:
        if {r["key_id"] for r in checker} != set(ids) or len(checker) != len(ids):
            f.append("checker sheet rows differ from the owner sheet")
        if any(r["correct"].strip() or r["error_category"].strip() or r["notes"].strip() for r in checker):
            f.append("checker sheet contains labels or notes")
    return f


def _load_test_sets():
    from kazwn import systems as S
    test = M.read_ids(M.TEST)
    sets = {"B0": {(c.synset_id, c.lemma_kk) for c in read_candidates(F.SYSTEM_FILES["B0"])},
            "B1": {(r["synset_id"], r["lemma_kk"]) for r in S.read_rows(F.SYSTEM_FILES["B1"])},
            "B2": {(c.synset_id, c.lemma_kk) for c in read_candidates(F.SYSTEM_FILES["B2"])},
            "B3": {(r["synset_id"], r["lemma_kk"]) for r in S.read_rows(F.SYSTEM_FILES["B3"])}}
    return test, {n: {p for p in s if p[0] in test} for n, s in sets.items()}


def _frozen_ok():
    if not F.FREEZE.exists():
        raise SheetError("systems are not frozen (S7): configs/systems_freeze.json is missing")
    bad = F.check(json.loads(F.FREEZE.read_text(encoding="utf-8")), F.SYSTEM_FILES)
    if bad:
        raise SheetError("frozen files changed: " + "; ".join(bad))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checker", action="store_true")
    a = ap.parse_args()
    try:
        _frozen_ok()
        if a.checker:
            if CHECKER_SHEET.exists():
                raise SheetError(f"{CHECKER_SHEET} exists; not overwritten")
            if not OWNER_SHEET.exists():
                raise SheetError("build the owner sheet first")
            rows = checker_rows(J.read_sheet(OWNER_SHEET))
            J.write_rows(CHECKER_SHEET, J.COLS, rows, "utf-8-sig")
            print(f"checker sheet: {len(rows)} rows, no labels -> {CHECKER_SHEET}")
            return 0
        if OWNER_SHEET.exists():
            raise SheetError(f"{OWNER_SHEET} exists; not overwritten (judgments may be in it)")
        from kazwn.kaikki import load_scope
        test = M.read_ids(M.TEST)
        gloss = {r["synset_id"]: r["gloss"] for r in load_scope()}
        by_source = {s: read_candidates(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES}
        rows, keys = build(by_source, test, gloss)
    except (SheetError, M.ScoreError) as e:
        print(f"FAILED: {e}")
        return 1
    J.write_rows(OWNER_SHEET, J.COLS, rows, "utf-8-sig")
    J.write_rows(KEY, KEY_COLS, keys, "utf-8")
    print(f"owner sheet: {len(rows)} rows over {len({r['synset_id'] for r in rows})} test synsets -> {OWNER_SHEET}")
    print(f"key (do not open until judging is finished) -> {KEY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())