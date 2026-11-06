"""Verify the S8a test sheets against the frozen systems. Run after kazwn.test_sheet (and --checker).
Run: PYTHONPATH=src python -m kazwn.verify_test_sheet
"""
import json
import sys

from kazwn import judge_sheet as J
from kazwn import mt_dev_score as M
from kazwn import systems_freeze as F
from kazwn import test_sheet as T


def main():
    from kazwn.kaikki import load_scope
    f = []
    try:
        T._frozen_ok()
        test, sets = T._load_test_sets()
        gloss = {r["synset_id"]: r["gloss"] for r in load_scope()}
        owner = J.read_sheet(T.OWNER_SHEET)
        key = M.read_tsv(T.KEY, "utf-8-sig", T.KEY_COLS)
        checker = J.read_sheet(T.CHECKER_SHEET) if T.CHECKER_SHEET.exists() else None
        if list(owner[0].keys()) != J.COLS:
            f.append(f"owner sheet header {list(owner[0].keys())} != {J.COLS}")
        f += T.verify(owner, key, checker, sets, test, gloss)
    except (T.SheetError, M.ScoreError, FileNotFoundError, IndexError) as e:
        f.append(str(e) or "owner sheet missing or empty")
    if f:
        print("FAILED:")
        for x in f[:30]:
            print("  -", x)
        return 1
    print(f"PASS: {len(owner)} owner rows match B1 union B2 on test; key systems consistent; "
          f"checker sheet {'blank and complete' if checker is not None else 'not built yet'}")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())