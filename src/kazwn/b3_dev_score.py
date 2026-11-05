"""S6: dev preview for B0, MT, B1, B2, B3 from existing dev judgments. No new judging, dev only.

Every dev pair of every system must already be judged (S4 sheet or B2 sheet); otherwise it fails.
Precision = correct / judged rows the system proposed. Coverage (D14) = dev synsets with >= 1 proposed
candidate; the stricter figure (>= 1 judged-correct) is reported too. The gate result is a non-binding preview.
Run: PYTHONPATH=src python -m kazwn.b3_dev_score
"""
import json
import sys
from collections import Counter

from kazwn import mt_dev_score as M
from kazwn.candidates import CAND_DIR, FILES, read_candidates
from kazwn.gate import check_gate
from kazwn.mt_dev_score import ScoreError
from kazwn.systems import B1_FILE, B3_FILE, read_rows, BuildError

OUT = M.ROOT / "data/reports/b3_dev_score.json"
SYSTEMS = ("b0_dict", "mt", "b1", "b2", "b3")


def merge_judgments(s4_rows, b2_rows):
    j = {r["key_id"]: r for r in s4_rows}
    for r in b2_rows:
        old = j.get(r["key_id"])
        if old is None:
            j[r["key_id"]] = r
        elif old["c"] != r["c"]:
            raise ScoreError(f"{r['key_id']}: S4 and B2 judgments differ")
    return j


def load_judgments(test_ids):
    from kazwn import llm_dev_score as LD
    return merge_judgments(M.load(test_ids=test_ids), LD.load_arm_rows(test_ids=test_ids))


def dev_pairs(rows, dev):
    """rows: Candidate objects or system-row dicts -> {key_id: {"sid", "flags"}} for dev synsets."""
    out = {}
    for r in rows:
        sid, lk, fl = (r["synset_id"], r["lemma_kk"], r["flags"].split("|")) if isinstance(r, dict) else \
            (r.synset_id, r.lemma_kk, r.flags)
        if sid in dev:
            out[f"{sid}|{lk}"] = {"sid": sid, "flags": {f for f in fl if f}}
    return out


def score(pairs, judg, n_dev):
    missing = sorted(k for k in pairs if k not in judg)
    if missing:
        raise ScoreError(f"{len(missing)} dev pair(s) without a judgment, e.g. {missing[:5]}")
    rows = [dict(judg[k], flags=p["flags"]) for k, p in pairs.items()]
    judged = [r for r in rows if r["c"] is not None]
    res = {"proposed": len(rows), "excluded_blank": len(rows) - len(judged)}
    res.update(M.prec(judged))
    res["per_pos"] = {g: M.prec([r for r in judged if r["grp"] == g]) for g in ("n", "v", "a")}
    res["error_categories"] = dict(Counter(r["cat"] for r in judged if r["c"] == 0))
    res["by_flag"] = {f: M.prec([r for r in judged if f in r["flags"]])
                      for f in sorted({f for r in judged for f in r["flags"]})}
    res["by_flag"]["no_flag"] = M.prec([r for r in judged if not r["flags"]])
    cov = {p["sid"] for p in pairs.values()}
    res["coverage_proposed"] = {"synsets": len(cov), "of": n_dev, "value": len(cov) / n_dev}
    cc = {r["synset_id"] for r in judged if r["c"] == 1}
    res["coverage_judged_correct"] = {"synsets": len(cc), "of": n_dev, "value": len(cc) / n_dev}
    return res


def gate_preview(s, n_dev):
    pp = {g: (v["correct"], v["judged"]) for g, v in s["per_pos"].items()}
    ok, rep = check_gate(s["correct"], s["judged"], s["coverage_proposed"]["synsets"], n_dev, pp)
    return {"note": "non-binding preview on dev (n small; thresholds not tuned on it)", "passed": ok,
            "report": {k: [v[0], v[1]] for k, v in rep.items()}}


def build_report(systems, judg, n_dev):
    sc = {n: score(p, judg, n_dev) for n, p in systems.items()}
    return {"note": "dev only, one judge; systems share rows, so precisions are correlated",
            "dev_synsets": n_dev, "systems": sc, "b3_gate_preview": gate_preview(sc["b3"], n_dev)}


def show(rep):
    print(f"{'system':<9}{'prop':>5}{'judg':>5}{'corr':>5}{'prec':>7}{'wilson95':>14}{'cov':>7}{'cov+':>7}")
    for n, v in rep["systems"].items():
        w = "-" if v["wilson_lo"] is None else f"{v['wilson_lo']:.3f}-{v['wilson_hi']:.3f}"
        p = "-" if v["precision"] is None else f"{v['precision']:.3f}"
        print(f"{n:<9}{v['proposed']:>5}{v['judged']:>5}{v['correct']:>5}{p:>7}{w:>14}"
              f"{v['coverage_proposed']['value']:>7.2f}{v['coverage_judged_correct']['value']:>7.2f}")
    for n, v in rep["systems"].items():
        pp = {g: (None if x["precision"] is None else round(x["precision"], 3), x["judged"])
              for g, x in v["per_pos"].items()}
        print(f"  {n}: per-POS (prec, judged) {pp}; errors {v['error_categories']}")
    g = rep["b3_gate_preview"]
    print(f"B3 gate preview (non-binding): passed={g['passed']} {g['report']}")


def main():
    try:
        dev, test = M.read_ids(M.DEV), M.read_ids(M.TEST)
        judg = load_judgments(test)
        systems = {
            "b0_dict": dev_pairs(read_candidates(CAND_DIR / f"{FILES['dict']}.tsv"), dev),
            "mt": dev_pairs(read_candidates(CAND_DIR / f"{FILES['mt']}.tsv"), dev),
            "b1": dev_pairs(read_rows(B1_FILE), dev),
            "b2": dev_pairs(read_candidates(CAND_DIR / f"{FILES['llm']}.tsv"), dev),
            "b3": dev_pairs(read_rows(B3_FILE), dev)}
        rep = build_report(systems, judg, len(dev))
    except (ScoreError, BuildError) as e:
        print(f"FAILED: {e}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    show(rep)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())