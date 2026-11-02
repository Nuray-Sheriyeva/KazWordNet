"""Checks one B2 run: python -m kazwn.verify_llm --tag <tag> [--allow-test]"""
import argparse
import json
import sys

from kazwn import llm_run as L
from kazwn.candidates import CAND_DIR, read_candidates, read_rejected
from kazwn.llm_parse import GOOD_STOPS

TOL = 1e-9


def check(tag, cfg, allow_test=False, raw_dir=L.RAW, cand_dir=CAND_DIR, scope_ids=None, prompt_path=None):
    fails, info = [], []
    rows = L.read_raw(raw_dir / f"{tag}.jsonl")
    if not rows:
        return [f"no raw rows for {tag}"], info
    ids = [r["input_id"] for r in rows]
    if len(ids) != len(set(ids)):
        fails.append("duplicate input ids in raw file")
    models = {r["model"] for r in rows}
    shas = {r["prompt_sha256"] for r in rows}
    if len(models) != 1 or len(shas) != 1:
        fails.append(f"mixed models/prompts: {models} {shas}")
    prompt_path = prompt_path or L.ROOT / cfg["prompt_file"]
    if shas != {L.sha256_file(prompt_path)}:
        fails.append("prompt file changed since this run (hash mismatch)")
    if not allow_test and any(r["pool"] == "test" for r in rows):
        fails.append("test-pool rows present without --allow-test")
    if scope_ids is not None and not set(ids) <= scope_ids:
        fails.append("input ids not in the frozen scope")
    for r in rows:
        price = cfg["prices_usd_per_mtok"][r["model"]]
        if abs(L.cost_usd(r["usage"], price) - r["cost_usd"]) > TOL:
            fails.append(f"{r['input_id']}: cost does not recompute")
            break
    spent = L.total_spent(raw_dir)
    if spent > cfg["cap_usd"] + 0.05:
        fails.append(f"total spend ${spent:.4f} exceeds cap ${cfg['cap_usd']:.2f}")
    info.append(f"rows {len(rows)}; this tag ${sum(r['cost_usd'] for r in rows):.4f}; all tags ${spent:.4f}")
    n_lemmas = 0
    for r in rows:
        if r["stop_reason"] in GOOD_STOPS:
            try:
                n_lemmas += len(json.loads(r["response_text"])["lemmas"])
            except (ValueError, KeyError, TypeError):
                pass
    cpath, rpath = cand_dir / f"llm_{tag}.tsv", cand_dir / f"llm_{tag}_rejected.tsv"
    if cpath.exists() and rpath.exists():
        cands = read_candidates(cpath)
        rejs = read_rejected(rpath)
        raw_by_id = {r["input_id"]: r for r in rows}
        lemma_rows = [x for x in rejs if not x.reason.startswith(("stop:", "parse_fail"))]
        if len(cands) + len(lemma_rows) > n_lemmas:
            fails.append("more candidate+rejected lemma rows than lemmas in the raw responses")
        for c in cands:
            ev = c.evidence[0]
            r = raw_by_id.get(ev["input_id"])
            if r is None or ev["raw"] not in json.loads(r["response_text"])["lemmas"]:
                fails.append(f"{c.synset_id}|{c.lemma_kk}: not traceable to raw response")
                break
        if any(c.source != "llm" for c in cands):
            fails.append("candidate source != llm")
    else:
        info.append("no parsed candidate files for this tag (run llm_parse)")
    return fails, info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--allow-test", action="store_true")
    a = ap.parse_args(argv)
    cfg = L.load_cfg()
    scope = {r["synset_id"] for r in L.read_tsv(L.SCOPE)}
    fails, info = check(a.tag, cfg, a.allow_test, scope_ids=scope)
    for i in info:
        print("info:", i)
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())