"""Verify the S7 freeze: hashes match, files read-only, build manifest and counts consistent.
Run: PYTHONPATH=src python -m kazwn.verify_systems_freeze
"""
import json
import os
import stat
import sys

from kazwn import mt_dev_score as M
from kazwn import systems as S
from kazwn import verify_b3 as V
from kazwn.candidates import CAND_DIR, FILES, SOURCES, read_candidates
from kazwn.systems_freeze import FREEZE, SYSTEM_FILES, check, load_sets, pool_counts, sha


def main():
    from kazwn.kaikki import load_scope
    f = []
    try:
        if not FREEZE.exists():
            raise S.BuildError(f"missing {FREEZE}: run kazwn.systems_freeze first")
        rec = json.loads(FREEZE.read_text(encoding="utf-8"))
        f += check(rec, SYSTEM_FILES)
        for n, p in SYSTEM_FILES.items():
            if os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
                f.append(f"{n}: file is writable")
        man = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
        if not man["allow_test"]:
            f.append("build manifest says the test pool is not included")
        dev, test = M.read_ids(M.DEV), M.read_ids(M.TEST)
        scope_ids = {r["synset_id"] for r in load_scope()}
        if pool_counts(load_sets(SYSTEM_FILES), dev, test, scope_ids) != rec["counts"]:
            f.append("counts differ from the freeze record")
        by_source = {s: read_candidates(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES}
        f += V.verify(by_source, S.read_rows(S.B1_FILE), S.read_rows(S.B3_FILE), dev, test, True)
    except (S.BuildError, M.ScoreError) as e:
        f.append(str(e))
    if f:
        print("FAILED:")
        for x in f[:30]:
            print("  -", x)
        return 1
    print("PASS: hashes match, files read-only, counts and vote rules consistent")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())