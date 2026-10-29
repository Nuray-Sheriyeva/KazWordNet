"""Verifies steps 5-6. Run: PYTHONPATH=src python -m kazwn.verify_split"""
import csv, hashlib, json, os, stat, sys

from kazwn.eval_split import FROZEN, OUT, N_ALL, N_DEV
from kazwn.gate import CFG, check_gate, wilson_lower
from kazwn.pos_sample import GROUP, allocate

fails = []


def check(name, ok, detail=""):
    print("PASS" if ok else "FAIL", "-", name, detail)
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def counts(rows):
    c = {}
    for r in rows:
        c[GROUP[r["pos"]]] = c.get(GROUP[r["pos"]], 0) + 1
    return c


m = json.loads((OUT / "eval_split_manifest.json").read_text(encoding="utf-8"))
dev, test, frozen = read(OUT / "eval_dev.tsv"), read(OUT / "eval_test.tsv"), read(FROZEN)
dev_ids, test_ids = {r["synset_id"] for r in dev}, {r["synset_id"] for r in test}

# ---- Step 5
check("dev has 50", len(dev) == N_DEV, str(len(dev)))
check("test has 100", len(test) == N_ALL - N_DEV, str(len(test)))
check("dev/test disjoint", not (dev_ids & test_ids))
check("ids unique within files", len(dev_ids) == len(dev) and len(test_ids) == len(test))
check("subset of frozen scope", (dev_ids | test_ids) <= {r["synset_id"] for r in frozen})
check("rows identical to frozen rows", all(r in frozen for r in dev + test))
q_all = allocate(counts(frozen), N_ALL)
check("150-sample POS counts match quota", counts(dev + test) == {g: q for g, q in q_all.items() if q})
check("dev POS counts match quota", counts(dev) == {g: q for g, q in allocate(q_all, N_DEV).items() if q})
check("frozen hash matches manifest", hashlib.sha256(FROZEN.read_bytes()).hexdigest() == m["frozen_sha256"])
check("dev hash matches", hashlib.sha256((OUT / "eval_dev.tsv").read_bytes()).hexdigest() == m["dev_sha256"])
check("test hash matches", hashlib.sha256((OUT / "eval_test.tsv").read_bytes()).hexdigest() == m["test_sha256"])
ro = lambda p: not (os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
check("eval files read-only", ro(OUT / "eval_dev.tsv") and ro(OUT / "eval_test.tsv"))

# ---- Step 6
cfg = json.loads(CFG.read_text(encoding="utf-8"))
check("gate config has all keys", {"system", "split", "min_precision", "min_precision_wilson95_lower",
      "min_coverage", "min_precision_per_pos", "min_judged_per_pos"} <= cfg.keys())
check("wilson(85/100) ~0.767", abs(wilson_lower(85, 100) - 0.767) < 0.005, f"{wilson_lower(85, 100):.4f}")
check("wilson(80/100) < 0.75", wilson_lower(80, 100) < 0.75)
check("gate passes on a good example", check_gate(90, 100, 70, 100)[0])
check("gate fails on low precision", not check_gate(80, 100, 70, 100)[0])
check("gate fails on low coverage", not check_gate(90, 100, 40, 100)[0])
check("gate fails on weak POS", not check_gate(90, 100, 70, 100, {"v": (6, 10)})[0])

print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)