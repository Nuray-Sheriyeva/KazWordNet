"""Verifies steps 1-3. Run: PYTHONPATH=src python -m kazwn.verify_scope"""
import csv, hashlib, json, sys
from pathlib import Path

from nltk.corpus import wordnet as wn
from kazwn.pos_sample import GROUP, allocate

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data" / "scope"
RAW = ROOT / "data" / "raw" / "core-wordnet.txt"
fails = []


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL"), "-", name, detail)
    if not ok:
        fails.append(name)


def read_tsv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ---- Step 1: source + environment
m1 = json.loads((SCOPE / "MANIFEST.json").read_text(encoding="utf-8"))
check("WordNet version is 3.0", wn.get_version() == "3.0", wn.get_version())
check("raw file non-empty", RAW.exists() and RAW.stat().st_size > 0)
check("raw sha256 matches manifest", hashlib.sha256(RAW.read_bytes()).hexdigest() == m1["source_sha256"])
check("parsed >= 4000 lines", m1["lines_parsed"] >= 4000, str(m1["lines_parsed"]))

# ---- Step 2: resolution
core = read_tsv(SCOPE / "core_resolved.tsv")
ids = [r["synset_id"] for r in core]
check("core_resolved has >= 4000 rows", len(core) >= 4000, str(len(core)))
check("core synset ids unique", len(ids) == len(set(ids)))
bad = [r["synset_id"] for r in core
       if not (lambda o, p: wn.synset_from_pos_and_offset(p, int(o)) is not None)(*r["synset_id"].split("-"))]
check("every core id resolves in WordNet", not bad, str(bad[:3]))
drop = len(m1["dropped_unresolved"]) / max(1, m1["lines_parsed"])
check("dropped <= 2% of lines", drop <= 0.02, f"{drop:.2%}")
check("no empty glosses in core", all(wn.synset_from_pos_and_offset(r["synset_id"][-1], int(r["synset_id"][:8])).definition() for r in core))

# ---- Step 3: POS-proportional sample
m3 = json.loads((SCOPE / "scope_1k_manifest.json").read_text(encoding="utf-8"))
sel = read_tsv(SCOPE / "scope_1k.tsv")
sel_ids = [r["synset_id"] for r in sel]
check("exactly n selected", len(sel) == m3["n"], str(len(sel)))
check("selected ids unique", len(sel_ids) == len(set(sel_ids)))
check("selected subset of core", set(sel_ids) <= set(ids))
check("core hash matches manifest", hashlib.sha256((SCOPE / "core_resolved.tsv").read_bytes()).hexdigest() == m3["core_resolved_sha256"])
counts = {}
for r in core:
    counts[GROUP[r["pos"]]] = counts.get(GROUP[r["pos"]], 0) + 1
expected = allocate(counts, m3["n"])
actual = {}
for r in sel:
    actual[GROUP[r["pos"]]] = actual.get(GROUP[r["pos"]], 0) + 1
check("per-POS counts match largest-remainder quota", actual == expected, f"{actual} vs {expected}")
dev = max(abs(actual[g] / m3["n"] - counts[g] / len(core)) for g in counts) * 100
check("max POS share deviation <= 0.15 pp", dev <= 0.15, f"{dev:.3f} pp")

print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} CHECK(S) FAILED: {fails}")
sys.exit(1 if fails else 0)