"""S7: freeze all four systems (and the MT source) before any test judging.

Preconditions: b1/b3 were built with --allow-test, verify_b3 --allow-test passed, no test judging file exists.
Writes configs/systems_freeze.json (never overwritten) and makes the frozen files read-only.
After the freeze, test-pool pair and synset counts are shown (counts only, no judgments).
Run: PYTHONPATH=src python -m kazwn.systems_freeze
"""
import csv
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from kazwn import mt_dev_score as M
from kazwn import systems as S
from kazwn import verify_b3 as V
from kazwn.candidates import CAND_DIR, FILES, SOURCES, read_candidates

ROOT = M.ROOT
FREEZE = ROOT / "configs/systems_freeze.json"
SYSTEM_FILES = {"B0": CAND_DIR / "b0_dict.tsv", "B1": S.B1_FILE, "B2": CAND_DIR / "llm.tsv",
                "B3": S.B3_FILE, "MT_source": CAND_DIR / "mt.tsv"}


class FreezeError(Exception):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def n_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f, delimiter="\t")) - 1


def describe(paths, root=ROOT):
    return {n: {"path": os.path.relpath(p, root), "sha256": sha(p), "rows": n_rows(p)} for n, p in paths.items()}


def pool_counts(sets, dev, test, scope_ids):
    size = {"dev": len(dev), "test": len(test), "rest": len(set(scope_ids) - dev - test)}
    out = {}
    for n, pairs in sets.items():
        out[n] = {}
        for pool in ("dev", "test", "rest"):
            ps = [p for p in pairs if S.pool_of(p[0], dev, test) == pool]
            sy = {p[0] for p in ps}
            out[n][pool] = {"pairs": len(ps), "synsets": len(sy), "pool_size": size[pool]}
    return out


def check(freeze, paths, root=ROOT):
    """Compare current files with the freeze record -> list of failures."""
    f = []
    for n, p in paths.items():
        rec = freeze["files"].get(n)
        if rec is None:
            f.append(f"{n}: not in freeze record")
        elif not Path(p).exists():
            f.append(f"{n}: file missing")
        elif sha(p) != rec["sha256"]:
            f.append(f"{n}: file changed since the freeze")
    return f


def load_sets(paths):
    sets = {}
    for n, p in paths.items():
        sets[n] = {(c.synset_id, c.lemma_kk) for c in read_candidates(p)} if n in ("B0", "B2", "MT_source") \
            else {(r["synset_id"], r["lemma_kk"]) for r in S.read_rows(p)}
    return sets


def main():
    from kazwn.kaikki import load_scope
    try:
        if FREEZE.exists():
            raise FreezeError(f"{FREEZE} already exists: the systems are frozen (never overwritten)")
        bad = sorted(p.name for p in (ROOT / "data/eval").glob("*") if "test" in p.name and "judg" in p.name)
        if bad:
            raise FreezeError(f"test judging files exist already: {bad}")
        dev, test = M.read_ids(M.DEV), M.read_ids(M.TEST)
        scope_ids = {r["synset_id"] for r in load_scope()}
        man = json.loads(S.MANIFEST.read_text(encoding="utf-8"))
        if not man["allow_test"]:
            raise FreezeError("systems were built without --allow-test: rebuild with --allow-test first")
        by_source = {s: read_candidates(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES}
        fails = V.verify(by_source, S.read_rows(S.B1_FILE), S.read_rows(S.B3_FILE), dev, test, True)
        for s in SOURCES:
            if man["inputs"][s] != sha(CAND_DIR / f"{FILES[s]}.tsv"):
                fails.append(f"source {s} changed since the build")
        for n, p in (("b1", S.B1_FILE), ("b3", S.B3_FILE)):
            if man["outputs"][n] != sha(p):
                fails.append(f"{n} changed since the build")
        if fails:
            raise FreezeError("verification failed:\n  " + "\n  ".join(fails[:20]))
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        except OSError:
            commit = ""
        sets = load_sets(SYSTEM_FILES)
        rec = {"frozen_on": datetime.date.today().isoformat(), "base_commit": commit,
               "rule": "B1 = dict|mt union; B3 = pairs proposed by >= 2 of dict, mt, llm (exact match after normalization)",
               "files": describe(SYSTEM_FILES), "counts": pool_counts(sets, dev, test, scope_ids)}
    except (FreezeError, S.BuildError, M.ScoreError) as e:
        print(f"FAILED: {e}")
        return 1
    FREEZE.parent.mkdir(parents=True, exist_ok=True)
    FREEZE.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in list(SYSTEM_FILES.values()) + [S.MANIFEST]:
        os.chmod(p, 0o444)
    print(f"frozen on {rec['frozen_on']} (base commit {commit[:7] or 'unknown'}); files are now read-only")
    for n, v in rec["files"].items():
        print(f"  {n:<10}{v['rows']:>6} rows  {v['sha256'][:12]}  {v['path']}")
    print(f"{'system':<10}" + "".join(f"{p + ' pairs':>12}{p + ' syn':>10}" for p in ("dev", "test", "rest")))
    for n, c in rec["counts"].items():
        print(f"{n:<10}" + "".join(f"{c[p]['pairs']:>12}{c[p]['synsets']:>10}" for p in ("dev", "test", "rest")))
    print(f"wrote {FREEZE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())