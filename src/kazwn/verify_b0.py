"""Verifies S3. Run: PYTHONPATH=src python -m kazwn.verify_b0"""
import json, sys
from collections import Counter
from pathlib import Path

from kazwn.candidates import CAND_DIR, FILES, normalize, read_candidates, read_rejected, split_translations
from kazwn.kaikki import EXTRACT, GROUP, KAIKKI_POS, load_scope, scope_lemmas

ROOT = Path(__file__).resolve().parents[2]
fails = []


def check(name, ok, detail=""):
    print("PASS" if ok else "FAIL", "-", name, detail)
    if not ok:
        fails.append(name)


cands = read_candidates(CAND_DIR / (FILES["dict"] + ".tsv"))
rejs = read_rejected(CAND_DIR / (FILES["dict"] + "_rejected.tsv"))
scope = {r["synset_id"]: r for r in load_scope()}
report = json.loads((ROOT / "data" / "reports" / "b0_coverage.json").read_text(encoding="utf-8"))
recs = {}
with open(EXTRACT, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        recs[r["entry_id"]] = r

check("has candidates", len(cands) > 0, str(len(cands)))
check("all source == dict", all(c.source == "dict" for c in cands))
keys = [(c.synset_id, c.lemma_kk, c.source) for c in cands]
check("unique (synset, lemma, source)", len(keys) == len(set(keys)))
check("synsets are in frozen scope", all(c.synset_id in scope for c in cands))
check("pos matches scope", all(c.pos == scope[c.synset_id]["pos"] for c in cands))
check("lemma_kk already normalized", all(normalize(c.lemma_kk, c.pos).lemma == c.lemma_kk for c in cands))
check("every row has evidence", all(c.evidence for c in cands))
check("evidence points to kaikki extract entries",
      all(e.get("dict") == "kaikki" and e.get("entry_id") in recs for c in cands for e in c.evidence))
check("lemma_en belongs to the synset",
      all(set(c.lemma_en.split("|")) <= set(scope_lemmas(scope[c.synset_id])) for c in cands))


def traceable(c):
    for e in c.evidence:
        rec = recs[e["entry_id"]]
        if rec["pos"] not in KAIKKI_POS[GROUP[c.pos]] or rec["word"] not in c.lemma_en.split("|"):
            return False
        words = {n.lemma for t in rec["translations"] for raw in split_translations(t["word"])
                 for n in [normalize(raw, c.pos)] if n.ok}
        if c.lemma_kk not in words:
            return False
    return True


check("every candidate traceable to its dictionary entry (pos, lemma, translation)", all(traceable(c) for c in cands))
covered = len({c.synset_id for c in cands})
expected = sum(d["strict"] for d in report["per_pos"].values())
check("synset count matches b0_coverage strict", covered == expected, f"{covered} vs {expected}")
check("rejected count matches coverage report", len(rejs) == report["rejected_translation_strings"],
      f"{len(rejs)} vs {report['rejected_translation_strings']}")
check("rejection rows have reasons", all(r.reason for r in rejs))
check("rejections are not also candidates",
      not ({(r.synset_id, r.lemma_raw) for r in rejs} & {(c.synset_id, c.lemma_raw) for c in cands}))

print("info: flags", dict(Counter(f for c in cands for f in c.flags)))
print("info: rows with sense label", sum(1 for c in cands if any("sense" in e for e in c.evidence)), "of", len(cands))
print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)