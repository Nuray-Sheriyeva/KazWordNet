"""B2: parse raw LLM responses into the shared candidate schema (source llm) via the S1 normalizer."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from kazwn.candidates import CAND_DIR, Candidate, Rejected, normalize, write_candidates, write_rejected
from kazwn.llm_run import RAW, REPORTS, read_raw

GOOD_STOPS = {"end_turn", "stop_sequence"}


def parse_rows(raw_rows, max_lemmas=6):
    cands, rejs, stats = [], [], Counter()
    for r in raw_rows:
        ev = [{"engine": r["model"], "input_id": r["input_id"], "prompt_sha256": r["prompt_sha256"][:12]}]
        base = (r["synset_id"], r["lemma_en"], r["pos"])
        if r["stop_reason"] not in GOOD_STOPS:
            rejs.append(Rejected(*base[:2], r["response_text"][:200], base[2], "llm", f"stop:{r['stop_reason']}", ev))
            stats["stop_not_end_turn"] += 1
            continue
        try:
            lemmas = json.loads(r["response_text"])["lemmas"]
            if not isinstance(lemmas, list) or not all(isinstance(x, str) for x in lemmas):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            rejs.append(Rejected(*base[:2], r["response_text"][:200], base[2], "llm", "parse_fail:json", ev))
            stats["parse_fail"] += 1
            continue
        if not lemmas:
            stats["empty_list"] += 1
        if len(lemmas) > max_lemmas:
            stats["over_max_lemmas"] += 1
        for raw in lemmas:
            n = normalize(raw, r["pos"])
            e = [dict(ev[0], raw=raw)]
            if n.ok:
                cands.append(Candidate(r["synset_id"], r["lemma_en"], n.lemma, raw, r["pos"], "llm", e, n.flags))
            else:
                rejs.append(Rejected(r["synset_id"], r["lemma_en"], raw, r["pos"], "llm", n.reason, e))
    return cands, rejs, stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--allow-test", action="store_true")
    a = ap.parse_args(argv)
    rows = read_raw(RAW / f"{a.tag}.jsonl")
    if not rows:
        print(f"FAILED: no raw rows for tag {a.tag}")
        return 1
    if any(r["pool"] == "test" for r in rows) and not a.allow_test:
        print("FAILED: test-pool rows present; pass --allow-test only after freeze")
        return 1
    from kazwn.llm_run import load_cfg
    cands, rejs, stats = parse_rows(rows, load_cfg()["max_lemmas"])
    merged = write_candidates("llm", cands, CAND_DIR / f"llm_{a.tag}.tsv")
    write_rejected("llm", rejs, CAND_DIR / f"llm_{a.tag}_rejected.tsv")
    rep = {
        "tag": a.tag, "model": rows[0]["model"], "raw_rows": len(rows),
        "synsets_with_candidates": len({c.synset_id for c in merged}),
        "candidate_rows": len(merged), "rejected_rows": len(rejs),
        "lemmas_per_synset_mean": len(merged) / len(rows),
        "response_stats": dict(stats),
        "rejected_reasons": dict(Counter(r.reason for r in rejs)),
        "flags": dict(Counter(f for c in merged for f in c.flags)),
        "cost_usd": sum(r["cost_usd"] for r in rows),
        "mean_output_tokens": sum(r["usage"]["output_tokens"] for r in rows) / len(rows),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"llm_parse_{a.tag}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())