"""B2: score the LLM arms (model x effort) on the judged dev rows and apply the rule in docs/b2_effort_experiment.md.

Joins the S4 sheet (rows judged earlier) with the B2 sheet (new rows) through the B2 key.
Dev only. Writes data/reports/llm_dev_score.json.
"""
import json
import sys

from kazwn import llm_run as L
from kazwn import mt_dev_score as M
from kazwn.mt_dev_score import ScoreError

B2_SHEET = M.ROOT / "data/eval/dev_judgments_b2.tsv"
B2_KEY = M.ROOT / "data/eval/dev_judging_key_b2.tsv"
KEY_COLS = ["key_id", "sources", "flags", "in_s4_sheet"]
OUT = M.ROOT / "data/reports/llm_dev_score.json"
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}


def load_arm_rows(s4_sheet=M.SHEET, s4_key=M.KEY, b2_sheet=B2_SHEET, b2_key=B2_KEY, test_ids=frozenset()):
    """One judged row per (synset, lemma) that at least one LLM arm proposed; sources = the arms."""
    s4 = {r["key_id"]: r for r in M.load(s4_sheet, s4_key, test_ids)}
    keys = M.read_tsv(b2_key, "utf-8-sig", KEY_COLS)
    sheet = M.read_tsv(b2_sheet, "utf-8-sig", M.SHEET_COLS)
    errs, kmap, b2 = [], {}, {}
    for k in keys:
        kid = k["key_id"]
        srcs = set(k["sources"].split("|"))
        if kid in kmap:
            errs.append(f"duplicate key row {kid}")
        if not srcs or not all(s.startswith("llm_") for s in srcs):
            errs.append(f"{kid}: bad sources {k['sources']!r}")
        if k["in_s4_sheet"] not in ("0", "1"):
            errs.append(f"{kid}: in_s4_sheet must be 0 or 1")
        kmap[kid] = (srcs, k["in_s4_sheet"])
    for r in sheet:
        kid = r["key_id"]
        c, cat = r["correct"].strip(), r["error_category"].strip()
        if kid in b2:
            errs.append(f"duplicate sheet row {kid}")
        if kid in s4:
            errs.append(f"{kid}: judged in both sheets")
        if kid not in kmap:
            errs.append(f"{kid}: not in B2 key")
        elif kmap[kid][1] != "0":
            errs.append(f"{kid}: in B2 sheet but key says it is in the S4 sheet")
        if kid != f"{r['synset_id']}|{r['lemma_kk']}":
            errs.append(f"{kid}: key_id != synset_id|lemma_kk")
        if r["synset_id"] in test_ids:
            errs.append(f"{kid}: test-pool synset")
        if r["pos"] not in M.GROUP:
            errs.append(f"{kid}: bad pos {r['pos']!r}")
        if c not in ("0", "1", ""):
            errs.append(f"{kid}: invalid correct {c!r}")
        elif c == "1" and cat:
            errs.append(f"{kid}: correct=1 with category {cat!r}")
        elif c == "0" and cat not in M.ERRORS:
            errs.append(f"{kid}: correct=0 with category {cat!r}")
        elif c == "" and (cat or not r["notes"].startswith("UNSURE:")):
            errs.append(f"{kid}: blank correct without UNSURE: note (or with category)")
        b2[kid] = {"key_id": kid, "synset_id": r["synset_id"], "grp": M.GROUP.get(r["pos"]),
                   "c": int(c) if c in ("0", "1") else None, "cat": cat,
                   "unsure": c == "" and r["notes"].startswith("UNSURE:")}
    rows = []
    for kid, (srcs, in_s4) in kmap.items():
        base = s4.get(kid) if in_s4 == "1" else b2.get(kid)
        if base is None:
            errs.append(f"{kid}: key says {'S4' if in_s4 == '1' else 'B2'} sheet but the row is missing there")
            continue
        rows.append(dict(base, sources=srcs))
    if errs:
        raise ScoreError(f"{len(errs)} problem(s):\n" + "\n".join(errs[:25]))
    return rows


def arm_info(arms, cfg, raw_dir=L.RAW):
    info = {}
    for a in arms:
        try:
            info[a] = L.project(a[len("llm_"):], cfg, raw_dir)
        except L.LLMError as e:
            raise ScoreError(f"{a}: {e}")
    return info


def decide(scores, info, cfg, tie=M.TIE_POINTS):
    eligible = sorted(a for a in scores if info[a]["projected_total_usd"] <= cfg["cap_usd"])
    over_cap = sorted(set(scores) - set(eligible))
    if not eligible:
        raise ScoreError("no arm is within the cost cap")
    if any(scores[a]["precision"] is None for a in eligible):
        raise ScoreError("an eligible arm has no judged rows")
    best = max(scores[a]["precision"] for a in eligible)
    tied = [a for a in eligible if round((best - scores[a]["precision"]) * 100, 6) <= tie]
    key = lambda a: (round(info[a]["projected_total_usd"], 9), EFFORT_RANK.get(info[a]["effort"], 99))
    order = sorted(tied, key=key)
    d = {"best_precision": best, "tie_points": tie, "eligible": eligible, "over_cap": over_cap, "tied": sorted(tied)}
    if len(order) == 1:
        d["winner"], d["rule"] = order[0], "higher_dev_precision"
    elif key(order[0]) == key(order[1]):
        d["winner"], d["rule"] = None, "unresolved_tie"
    else:
        d["winner"], d["rule"] = order[0], "within_tie_lowest_cost_then_lower_effort"
    return d


def build_report(rows, info, cfg):
    arms = sorted(info)
    scores = {a: M.score_source(rows, a) for a in arms}
    return {
        "note": "dev only, one judge, 50 synsets; arms share rows, so their precisions are correlated",
        "judged_rows": len(rows),
        "arms": {a: dict(scores[a], model=info[a]["model"], effort=info[a]["effort"],
                         projected_total_usd=info[a]["projected_total_usd"],
                         mean_cost_usd=info[a]["mean_cost_usd"]) for a in arms},
        "decision": decide(scores, info, cfg),
    }


def show(rep):
    print(f"{'arm':<26}{'model':<19}{'eff':<7}{'prop':>5}{'judg':>5}{'corr':>5}{'prec':>7}{'wilson95':>14}{'syn+':>6}{'proj$':>8}")
    for a, v in rep["arms"].items():
        p = "-" if v["precision"] is None else f"{v['precision']:.3f}"
        w = "-" if v["wilson_lo"] is None else f"{v['wilson_lo']:.3f}-{v['wilson_hi']:.3f}"
        print(f"{a:<26}{v['model']:<19}{v['effort']:<7}{v['proposed']:>5}{v['judged']:>5}{v['correct']:>5}{p:>7}{w:>14}"
              f"{v['dev_synsets_with_correct']:>6}{v['projected_total_usd']:>8.2f}")
    for a, v in rep["arms"].items():
        print(f"  {a}: excluded {v['excluded_blank']}; errors {v['error_categories']}")
    d = rep["decision"]
    print(f"decision: {d['winner']} via {d['rule']}; best {d['best_precision']:.3f}, tied {d['tied']}, over cap {d['over_cap']}")


def main():
    try:
        rows = load_arm_rows(test_ids=M.read_ids(M.TEST))
        cfg = L.load_cfg()
        arms = sorted({s for r in rows for s in r["sources"]})
        rep = build_report(rows, arm_info(arms, cfg), cfg)
    except ScoreError as e:
        print(f"FAILED: {e}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    show(rep)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())