"""Checks that data/candidates/mt.tsv is exactly the chosen engine's parsed candidates and that the test pool was run."""
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from kazwn import candidates as C
from kazwn.mt_final import CAND, RAW, ROOT, SCORE, chosen

INPUTS = RAW / "inputs.tsv"
SCOPE = ROOT / "data/scope/scope_1k_frozen.tsv"


def key(x):
    return json.dumps({k: v for k, v in asdict(x).items() if k != "source"}, sort_keys=True, ensure_ascii=False)


def engine_of(x):
    """Engine id from evidence, which may be a dict, a list of dicts, or a JSON string of either."""
    ev = x.evidence
    if isinstance(ev, (str, bytes)):
        ev = json.loads(ev)
    items = ev if isinstance(ev, list) else [ev]
    found = {d.get("engine") for d in items if isinstance(d, dict) and d.get("engine")}
    return next(iter(found)) if len(found) == 1 else None


def column(path, col):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r[col] for r in csv.DictReader(f, delimiter="\t")}


def check(engine, cand_dir=CAND, raw_dir=RAW, inputs=INPUTS, scope=SCOPE):
    cand_dir, raw_dir = Path(cand_dir), Path(raw_dir)
    fails = []
    for kind, read in (("", C.read_candidates), ("_rejected", C.read_rejected)):
        src = read(cand_dir / f"mt_{engine}{kind}.tsv")
        fin = read(cand_dir / f"mt{kind}.tsv")
        if Counter(map(key, src)) != Counter(map(key, fin)):
            fails.append(f"mt{kind}.tsv differs from mt_{engine}{kind}.tsv (ignoring source)")
        if any(x.source != "mt" for x in fin):
            fails.append(f"mt{kind}.tsv has rows with source != 'mt'")
        if kind == "":
            engines = {engine_of(x) for x in fin}
            if len(engines) != 1 or None in engines:
                fails.append(f"mt.tsv evidence engine values not a single non-empty value: {engines}")
            fin_syn = {x.synset_id for x in fin}
    ids = column(inputs, "input_id")
    with open(raw_dir / f"{engine}.jsonl", encoding="utf-8") as f:
        raw_ids = {json.loads(line)["input_id"] for line in f if line.strip()}
    if ids - raw_ids:
        fails.append(f"{len(ids - raw_ids)} of {len(ids)} inputs have no raw output (test pool not run?)")
    if raw_ids - ids:
        fails.append(f"{len(raw_ids - ids)} raw outputs not in inputs.tsv")
    meta = json.loads((raw_dir / f"{engine}.meta.json").read_text(encoding="utf-8"))
    pools = meta.get("pools")
    pools = set(p.strip() for p in pools.split(",")) if isinstance(pools, str) else set(pools or [])
    if not {"dev", "rest", "test"} <= pools:
        fails.append(f"meta pools {meta.get('pools')!r} does not include dev, rest and test")
    unknown = fin_syn - column(scope, "synset_id")
    if unknown:
        fails.append(f"{len(unknown)} candidate synsets not in the frozen scope")
    return fails


def main():
    engine, _ = chosen(SCORE)
    fails = check(engine)
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())