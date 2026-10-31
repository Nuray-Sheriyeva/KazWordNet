"""S4.4a: apply the pre-registered S4 selection rule (docs/s4_selection_rule.md) to the parsed engines.

Proxy metrics only (no labels). Pool = dev + rest synsets (the test pool is never touched).
Run: PYTHONPATH=src python -m kazwn.mt_selection [--engines tilmash,nllb600m]
"""
import argparse, csv, json
from pathlib import Path

from kazwn.candidates import CAND_DIR, FILES, read_candidates
from kazwn.mt_inputs import OUT as INPUTS
from kazwn.mt_parse import MT_DIR, REPORTS, extract_head, read_raw

PARSE_MIN, SURVIVE_MIN = 0.70, 0.90  # thresholds from docs/s4_selection_rule.md


def by_synset(cands, pool):
    d = {}
    for c in cands:
        if c.synset_id in pool:
            d.setdefault(c.synset_id, set()).add(c.lemma_kk)
    return d


def proxies(raw_rows, mt_cands, b0_cands, pool):
    parsed = {r["input_id"] for r in raw_rows if extract_head(r["output"])[0] is not None}
    survived = {e["input_id"] for c in mt_cands for e in c.evidence}
    parse_success = len(parsed) / len(raw_rows) if raw_rows else 0.0
    survival = len(survived & parsed) / len(parsed) if parsed else 0.0
    mt, b0 = by_synset(mt_cands, pool), by_synset(b0_cands, pool)
    covered, uncovered = set(b0), pool - set(b0)
    hit = sum(1 for s in covered if mt.get(s, set()) & b0[s])
    inc = sum(1 for s in uncovered if mt.get(s))
    ov_num = sum(len(mt.get(s, set()) & b0[s]) for s in covered)
    ov_den = sum(len(mt.get(s, set())) for s in covered)
    return {
        "parse_success": round(parse_success, 4), "s1_survival": round(survival, 4),
        "eligible": parse_success >= PARSE_MIN and survival >= SURVIVE_MIN,
        "b0_covered_synsets": len(covered), "b0_hit_rate": round(hit / len(covered), 4) if covered else 0.0,
        "b0_uncovered_synsets": len(uncovered), "incremental_covered": inc,
        "incremental_coverage": round(inc / len(uncovered), 4) if uncovered else 0.0,
        "candidate_overlap_with_b0": round(ov_num / ov_den, 4) if ov_den else 0.0,
        "synsets_with_candidates": len(mt), "candidate_rows": sum(len(v) for v in mt.values()),
    }


def rank(results):
    elig = [e for e, m in results.items() if m["eligible"]]
    return sorted(elig, key=lambda e: (-results[e]["b0_hit_rate"], -results[e]["incremental_coverage"], e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines")
    a = ap.parse_args()
    engines = a.engines.split(",") if a.engines else sorted(
        p.stem[3:] for p in CAND_DIR.glob("mt_*.tsv") if not p.stem.endswith("_rejected"))
    with open(INPUTS, encoding="utf-8", newline="") as f:
        pool = {r["synset_id"] for r in csv.DictReader(f, delimiter="\t") if r["pool"] in ("dev", "rest")}
    b0 = read_candidates(CAND_DIR / (FILES["dict"] + ".tsv"))
    results = {e: proxies(read_raw(MT_DIR / f"{e}.jsonl"), read_candidates(CAND_DIR / f"mt_{e}.tsv"), b0, pool)
               for e in engines}
    ranking = rank(results)
    report = {"pool_synsets": len(pool), "thresholds": {"parse_min": PARSE_MIN, "survival_min": SURVIVE_MIN},
              "engines": results, "ranking": ranking, "finalists": ranking[:2],
              "note": "proxy metrics only; B0 overlap underestimates precision because Wiktionary is incomplete"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "mt_selection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()