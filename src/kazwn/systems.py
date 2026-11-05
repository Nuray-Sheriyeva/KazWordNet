"""S6: build B1 (dictionary + MT union) and B3 (2-of-3 vote) from the stored source files.

No API calls. Pair identity = (synset_id, lemma_kk), exact match after normalization (D7).
B1 = pairs proposed by dict or mt (never a voting source). B3 = pairs proposed by >= 2 of dict, mt, llm (D8).
Flagged candidates stay in the vote and their flags are carried (D9). Rejected strings are never read.
Without --allow-test the test pool is left out of the output files; no test-pool statistics are ever printed.
Run: PYTHONPATH=src python -m kazwn.systems [--allow-test]
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from kazwn import mt_dev_score as M
from kazwn.candidates import CAND_DIR, FILES, SOURCES, read_candidates

ROOT = M.ROOT
B1_FILE = CAND_DIR / "b1.tsv"
B3_FILE = CAND_DIR / "b3.tsv"
MANIFEST = CAND_DIR / "systems_manifest.json"
REPORT = ROOT / "data/reports/systems_counts.json"
COLS = ["synset_id", "lemma_en", "lemma_kk", "pos", "system", "sources", "votes", "evidence", "flags"]
B1_PARTS = ("dict", "mt")
VOTERS = SOURCES  # dict, mt, llm
MIN_VOTES = 2


class BuildError(Exception):
    pass


def _ek(e):
    return json.dumps(e, sort_keys=True, ensure_ascii=False)


def pool_of(sid, dev, test):
    return "dev" if sid in dev else "test" if sid in test else "rest"


def collect(by_source, keep=lambda sid: True):
    """{source: [Candidate]} -> {(synset_id, lemma_kk): {"pos", "src": {source: {"en", "flags", "ev"}}}}."""
    pairs = {}
    for src, cands in by_source.items():
        for c in cands:
            if c.source != src:
                raise BuildError(f"row source {c.source!r} in the {src!r} file ({c.synset_id}|{c.lemma_kk})")
            if not keep(c.synset_id):
                continue
            g = pairs.setdefault((c.synset_id, c.lemma_kk), {"pos": c.pos, "src": {}})
            if g["pos"] != c.pos:
                raise BuildError(f"POS mismatch for {c.synset_id}|{c.lemma_kk}: {g['pos']} vs {c.pos} ({src})")
            s = g["src"].setdefault(src, {"en": set(), "flags": set(), "ev": {}})
            s["en"].update(x for x in c.lemma_en.split("|") if x)
            s["flags"].update(c.flags)
            for e in c.evidence:
                s["ev"][_ek(e)] = e
    return pairs


def make_rows(pairs, system, parts, min_votes):
    rows = []
    for (sid, lk), g in sorted(pairs.items()):
        agree = sorted(s for s in g["src"] if s in parts)
        if len(agree) < min_votes:
            continue
        en, flags, ev = set(), set(), {}
        for s in agree:
            d = g["src"][s]
            en |= d["en"]
            flags |= d["flags"]
            ev.update(d["ev"])
        rows.append({
            "synset_id": sid, "lemma_en": "|".join(sorted(en)), "lemma_kk": lk, "pos": g["pos"],
            "system": system, "sources": "|".join(agree), "votes": str(len(agree)),
            "evidence": json.dumps([ev[k] for k in sorted(ev)], ensure_ascii=False, sort_keys=True),
            "flags": "|".join(sorted(flags))})
    return rows


def build(by_source, keep=lambda sid: True):
    """-> (b1_rows, b3_rows). Needs all three sources."""
    if set(by_source) != set(SOURCES):
        raise BuildError(f"need exactly the sources {SOURCES}, got {sorted(by_source)}")
    pairs = collect(by_source, keep)
    return make_rows(pairs, "b1", B1_PARTS, 1), make_rows(pairs, "b3", VOTERS, MIN_VOTES)


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_rows(path):
    path = Path(path)
    if not path.exists():
        raise BuildError(f"missing file: {path}")
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        if header != COLS:
            raise BuildError(f"{path}: header {header} != {COLS}")
        return [dict(zip(COLS, r)) for r in reader if r]


def counts(sets, b3_rows, dev, test, scope_ids):
    """Per system and pool (dev, rest only): pairs and synsets with >= 1 pair. Test is withheld."""
    pool_size = {"dev": len(dev), "rest": len(set(scope_ids) - dev - test)}
    out = {"pool_sizes": pool_size, "test": "withheld until the S7 freeze", "systems": {}}
    for name, pairs in sets.items():
        res = {}
        for pool in ("dev", "rest"):
            ps = [p for p in pairs if pool_of(p[0], dev, test) == pool]
            sy = {p[0] for p in ps}
            res[pool] = {"pairs": len(ps), "synsets_with_candidate": len(sy),
                         "coverage": round(len(sy) / pool_size[pool], 4) if pool_size[pool] else None}
        out["systems"][name] = res
    out["b3_vote_combinations"] = {
        pool: dict(Counter(r["sources"] for r in b3_rows if pool_of(r["synset_id"], dev, test) == pool))
        for pool in ("dev", "rest")}
    return out


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-test", action="store_true", help="include test-pool synsets in the output files")
    a = ap.parse_args()
    from kazwn.kaikki import load_scope
    try:
        dev, test = M.read_ids(M.DEV), M.read_ids(M.TEST)
        scope_ids = {r["synset_id"] for r in load_scope()}
        if not (dev | test) <= scope_ids or dev & test:
            raise BuildError("dev/test ids are not a disjoint subset of the scope")
        by_source = {s: read_candidates(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES}
        keep = (lambda sid: True) if a.allow_test else (lambda sid: sid not in test)
        b1, b3 = build(by_source, keep)
    except (BuildError, M.ScoreError) as e:
        print(f"FAILED: {e}")
        return 1
    write_rows(B1_FILE, b1)
    write_rows(B3_FILE, b3)
    sets = {FILES["dict"]: {(c.synset_id, c.lemma_kk) for c in by_source["dict"]},
            "mt": {(c.synset_id, c.lemma_kk) for c in by_source["mt"]},
            "llm": {(c.synset_id, c.lemma_kk) for c in by_source["llm"]},
            "b1": {(r["synset_id"], r["lemma_kk"]) for r in b1},
            "b3": {(r["synset_id"], r["lemma_kk"]) for r in b3}}
    rep = counts(sets, b3, dev, test, scope_ids)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST.write_text(json.dumps({
        "allow_test": a.allow_test,
        "inputs": {s: sha256(CAND_DIR / f"{FILES[s]}.tsv") for s in SOURCES},
        "outputs": {"b1": sha256(B1_FILE), "b3": sha256(B3_FILE)}}, indent=2), encoding="utf-8")
    print(f"test pool included in files: {a.allow_test}")
    print(f"{'system':<10}{'dev pairs':>10}{'dev syn':>9}{'dev cov':>9}{'rest pairs':>12}{'rest syn':>10}{'rest cov':>10}")
    for n, v in rep["systems"].items():
        d, r = v["dev"], v["rest"]
        print(f"{n:<10}{d['pairs']:>10}{d['synsets_with_candidate']:>9}{d['coverage']:>9.3f}"
              f"{r['pairs']:>12}{r['synsets_with_candidate']:>10}{r['coverage']:>10.3f}")
    print("B3 vote combinations:", rep["b3_vote_combinations"])
    print(f"wrote {B1_FILE}, {B3_FILE}, {MANIFEST}, {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())