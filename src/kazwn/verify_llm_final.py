"""Checks that data/candidates/llm.tsv is exactly the frozen runs' parsed candidates: python -m kazwn.verify_llm_final --tags ..."""
import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from kazwn import llm_final as F
from kazwn import llm_run as L
from kazwn import verify_llm as V
from kazwn.candidates import CAND_DIR, read_candidates, read_rejected


def key(x):
    return json.dumps({k: v for k, v in asdict(x).items() if k != "source"}, sort_keys=True, ensure_ascii=False)


def check(tags, cfg, scope_ids, freeze_path=L.FREEZE, raw_dir=L.RAW, cand_dir=CAND_DIR, prompt_path=None):
    cand_dir = Path(cand_dir)
    fails = F.check_runs(tags, scope_ids, freeze_path, raw_dir)
    for t in tags:
        f, _ = V.check(t, cfg, allow_test=True, raw_dir=Path(raw_dir), cand_dir=cand_dir, scope_ids=scope_ids, prompt_path=prompt_path)
        fails += [f"{t}: {x}" for x in f]
    missing = F.missing_files(tags, cand_dir, final=True)
    if missing:
        return fails + [f"missing file: {m}" for m in missing]
    fz = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    for kind, read in (("", read_candidates), ("_rejected", read_rejected)):
        src = [x for t in tags for x in read(cand_dir / f"llm_{t}{kind}.tsv")]
        fin = read(cand_dir / f"llm{kind}.tsv")
        if Counter(map(key, src)) != Counter(map(key, fin)):
            fails.append(f"llm{kind}.tsv differs from the per-tag files (ignoring source)")
        if any(x.source != "llm" for x in fin):
            fails.append(f"llm{kind}.tsv has rows with source != 'llm'")
        for x in fin:
            ev = x.evidence[0]
            if ev["engine"] != fz["model"] or ev["prompt_sha256"] != fz["prompt_sha256"][:12]:
                fails.append(f"llm{kind}.tsv: evidence does not match the freeze file")
                break
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True)
    a = ap.parse_args(argv)
    scope = {r["synset_id"] for r in L.read_tsv(L.SCOPE)}
    fails = check(a.tags.split(","), L.load_cfg(), scope)
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())