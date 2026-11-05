"""Verify S6 outputs (b1.tsv, b3.tsv) against the three source files.

Fails on test-pool rows unless --allow-test; fails if any dev pair of B0/MT/B1/B2/B3 has no judgment.
Run: PYTHONPATH=src python -m kazwn.verify_b3 [--allow-test]
"""
import json
import sys
from collections import Counter

from kazwn import mt_dev_score as M
from kazwn.candidates import CAND_DIR, FILES, SOURCES, normalize, read_candidates
from kazwn.systems import B1_FILE, B3_FILE, MANIFEST, B1_PARTS, VOTERS, MIN_VOTES, read_rows, BuildError, pool_of, sha256


def verify(by_source, b1, b3, dev, test, allow_test, judg=None):
    f = []
    keys = {s: {(c.synset_id, c.lemma_kk) for c in cs} for s, cs in by_source.items()}
    pos = {(c.synset_id, c.lemma_kk): c.pos for cs in by_source.values() for c in cs}
    evid = {s: {} for s in SOURCES}
    for s, cs in by_source.items():
        for c in cs:
            evid[s].setdefault((c.synset_id, c.lemma_kk), []).extend(json.dumps(e, sort_keys=True, ensure_ascii=False) for e in c.evidence)
    keep = (lambda p: True) if allow_test else (lambda p: p[0] not in test)
    member = Counter()
    for s in VOTERS:
        member.update(p for p in keys[s] if keep(p))
    exp_b1 = {p for s in B1_PARTS for p in keys[s] if keep(p)}
    exp_b3 = {p for p, n in member.items() if n >= MIN_VOTES}
    for name, rows, exp, parts, lo, hi in (("b1", b1, exp_b1, B1_PARTS, 1, 2), ("b3", b3, exp_b3, VOTERS, 2, 3)):
        got = [(r["synset_id"], r["lemma_kk"]) for r in rows]
        if len(got) != len(set(got)):
            f.append(f"{name}: duplicate (synset, lemma) rows")
        if set(got) != exp:
            f.append(f"{name}: pair set differs from expected (missing {len(exp - set(got))}, extra {len(set(got) - exp)})")
        for r in rows:
            p = (r["synset_id"], r["lemma_kk"])
            srcs = r["sources"].split("|")
            if r["system"] != name:
                f.append(f"{name}: wrong system label {r['system']} at {p}")
            true = sorted(s for s in parts if p in keys[s])
            if srcs != true:
                f.append(f"{name}: sources {srcs} != actual {true} at {p}")
            if r["votes"] != str(len(srcs)) or not lo <= len(srcs) <= hi:
                f.append(f"{name}: bad votes {r['votes']} at {p}")
            if normalize(r["lemma_kk"], r["pos"]).lemma != r["lemma_kk"]:
                f.append(f"{name}: lemma not normalized at {p}")
            if pos.get(p) != r["pos"]:
                f.append(f"{name}: pos mismatch at {p}")
            have = {json.dumps(e, sort_keys=True, ensure_ascii=False) for e in json.loads(r["evidence"])}
            for s in srcs:
                if p in evid[s] and not set(evid[s][p]) <= have:
                    f.append(f"{name}: evidence of {s} missing at {p}")
            if not allow_test and pool_of(r["synset_id"], dev, test) == "test":
                f.append(f"{name}: test-pool row {p} without --allow-test")
    if {(r["synset_id"], r["lemma_kk"]) for r in b3} - {(r["synset_id"], r["lemma_kk"]) for r in b1}:
        f.append("b3 is not a subset of b1")
    if judg is not None:
        for name, rows in (("b0_dict", by_source["dict"]), ("mt", by_source["mt"]), ("llm", by_source["llm"]), ("b1", b1), ("b3", b3)):
            sid_lk = [((r["synset_id"], r["lemma_kk"]) if isinstance(r, dict) else (r.synset_id, r.lemma_kk)) for r in rows]
            miss = sorted({f"{a}|{b}" for a, b in sid_lk if a in dev} - set(judg))
            if miss:
                f.append(f"{name}: {len(miss)} dev pair(s) without judgment, e.g. {miss[:3]}")
    return f


def main():
    allow = "--allow-test" in sys.argv
    try:
        dev, test = M.read_ids(M.DEV), M.read_ids(M.TEST)
        by_source = {s: read_candidates(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES}
        b1, b3 = read_rows(B1_FILE), read_rows(B3_FILE)
        fails = verify(by_source, b1, b3, dev, test, allow)
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if man["allow_test"] != allow:
            fails.append(f"manifest allow_test={man['allow_test']} but verify run with allow_test={allow}")
        for s in SOURCES:
            if man["inputs"][s] != sha256(CAND_DIR / f"{FILES[s]}.tsv"):
                fails.append(f"source file {s} changed since the build")
        for n, p in (("b1", B1_FILE), ("b3", B3_FILE)):
            if man["outputs"][n] != sha256(p):
                fails.append(f"{n} file changed since the build")
        from kazwn.b3_dev_score import load_judgments
        fails += [x for x in verify(by_source, b1, b3, dev, test, allow, load_judgments(test)) if "judgment" in x]
    except (BuildError, M.ScoreError) as e:
        fails = [str(e)]
    if fails:
        print("FAILED:")
        for x in fails[:40]:
            print("  -", x)
        return 1
    print(f"PASS: b1 {len(b1)} rows, b3 {len(b3)} rows match the source files; dev pairs all judged")
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())