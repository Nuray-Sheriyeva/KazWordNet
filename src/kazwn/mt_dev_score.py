"""S4.4c: score B0 and the MT finalists on the judged dev sheet; apply the pre-registered selection rule.

Dev only. Refuses sheets that contain test-pool synsets. Writes data/reports/mt_dev_score.json.
"""
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

from kazwn.gate import wilson_lower

ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / "data/eval/dev_judgments.tsv"
KEY = ROOT / "data/eval/dev_judging_key.tsv"
SEL = ROOT / "data/reports/mt_selection.json"
DEV = ROOT / "data/eval/eval_dev.tsv"
TEST = ROOT / "data/eval/eval_test.tsv"
OUT = ROOT / "data/reports/mt_dev_score.json"

SHEET_COLS = ["key_id", "synset_id", "pos", "lemma_en", "gloss", "lemma_kk", "correct", "error_category", "notes"]
KEY_COLS = ["key_id", "sources", "flags"]
ERRORS = {"wrong_sense", "calque", "russian_loan", "variant", "form", "other"}
SOURCES = ("b0_dict", "mt_tilmash", "mt_nllb600m")
ENGINE_SOURCE = {"tilmash": "mt_tilmash", "nllb600m": "mt_nllb600m"}
GROUP = {"n": "n", "v": "v", "a": "a", "s": "a"}  # satellites count as adjectives
# Amendment 2026-10-31 (docs/s4_selection_rule.md): tilmash is treated as permissively licensed, nllb600m is not.
PERMISSIVE = {"tilmash"}
TIE_POINTS = 5.0


class ScoreError(Exception):
    pass


def read_tsv(path, enc, cols):
    path = Path(path)
    if not path.exists():
        raise ScoreError(f"missing file: {path}")
    with open(path, encoding=enc, newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        if header != cols:
            raise ScoreError(f"{path}: header {header} != {cols} (re-export changed delimiter or encoding?)")
        rows = []
        for i, row in enumerate(reader, start=2):
            if not row or all(not c.strip() for c in row):
                continue
            if len(row) != len(cols):
                raise ScoreError(f"{path} line {i}: {len(row)} fields, expected {len(cols)}")
            rows.append(dict(zip(cols, row)))
    return rows


def read_ids(path):
    path = Path(path)
    if not path.exists():
        raise ScoreError(f"missing file: {path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["synset_id"] for r in csv.DictReader(f, delimiter="\t")}


def load(sheet=SHEET, key=KEY, test_ids=frozenset()):
    rows = read_tsv(sheet, "utf-8-sig", SHEET_COLS)
    keys = read_tsv(key, "utf-8", KEY_COLS)
    errs, kmap = [], {}
    for k in keys:
        if k["key_id"] in kmap:
            errs.append(f"duplicate key row {k['key_id']}")
        srcs = set(k["sources"].split("|"))
        if not srcs or not srcs <= set(SOURCES):
            errs.append(f"{k['key_id']}: bad sources {k['sources']!r}")
        kmap[k["key_id"]] = srcs
    seen, out = set(), []
    for r in rows:
        kid = r["key_id"]
        c, cat = r["correct"].strip(), r["error_category"].strip()
        if kid in seen:
            errs.append(f"duplicate sheet row {kid}")
        seen.add(kid)
        if kid not in kmap:
            errs.append(f"{kid}: not in key file")
        if kid != f"{r['synset_id']}|{r['lemma_kk']}":
            errs.append(f"{kid}: key_id != synset_id|lemma_kk")
        if r["synset_id"] in test_ids:
            errs.append(f"{kid}: test-pool synset")
        if r["pos"] not in GROUP:
            errs.append(f"{kid}: bad pos {r['pos']!r}")
        if c not in ("0", "1", ""):
            errs.append(f"{kid}: invalid correct {c!r}")
        elif c == "1" and cat:
            errs.append(f"{kid}: correct=1 with category {cat!r}")
        elif c == "0" and cat not in ERRORS:
            errs.append(f"{kid}: correct=0 with category {cat!r}")
        elif c == "" and (cat or not r["notes"].startswith("UNSURE:")):
            errs.append(f"{kid}: blank correct without UNSURE: note (or with category)")
        out.append({
            "key_id": kid, "synset_id": r["synset_id"], "grp": GROUP.get(r["pos"]),
            "c": int(c) if c in ("0", "1") else None, "cat": cat,
            "unsure": c == "" and r["notes"].startswith("UNSURE:"),
            "sources": kmap.get(kid, set()),
        })
    for kid in set(kmap) - seen:
        errs.append(f"{kid}: in key file but not in sheet")
    if errs:
        raise ScoreError(f"{len(errs)} problem(s):\n" + "\n".join(errs[:25]))
    return out


def wilson_upper(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    return min(1.0, (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d)


def prec(rows):
    n = len(rows)
    k = sum(r["c"] for r in rows)
    if n == 0:
        return {"judged": 0, "correct": 0, "precision": None, "wilson_lo": None, "wilson_hi": None}
    return {"judged": n, "correct": k, "precision": k / n,
            "wilson_lo": wilson_lower(k, n), "wilson_hi": wilson_upper(k, n)}


def score_source(rows, src):
    mine = [r for r in rows if src in r["sources"]]
    judged = [r for r in mine if r["c"] is not None]
    only = [r for r in judged if r["sources"] == {src}]
    res = {"proposed": len(mine), "excluded_blank": len(mine) - len(judged),
           "excluded_unsure": sum(r["unsure"] for r in mine)}
    res.update(prec(judged))
    res["per_pos"] = {g: prec([r for r in judged if r["grp"] == g]) for g in ("n", "v", "a")}
    res["error_categories"] = dict(Counter(r["cat"] for r in judged if r["c"] == 0))
    res["only_this_source"] = prec(only)
    res["dev_synsets_with_correct"] = len({r["synset_id"] for r in judged if r["c"] == 1})
    return res


def decide(scores, sel, tie=TIE_POINTS):
    fin = sel["finalists"]
    if len(fin) != 2:
        raise ScoreError(f"expected 2 finalists, got {fin}")
    pa, pb = (scores[ENGINE_SOURCE[e]]["precision"] for e in fin)
    if pa is None or pb is None:
        raise ScoreError("a finalist has no judged rows")
    gap = round(abs(pa - pb) * 100, 6)
    d = {"finalists": fin, "dev_precision": dict(zip(fin, (pa, pb))), "gap_points": gap, "tie_points": tie}
    if gap > tie:
        d["winner"] = fin[0] if pa > pb else fin[1]
        d["rule"] = "higher_dev_precision"
        return d
    perm = [e for e in fin if e in PERMISSIVE]
    if len(perm) == 1:
        d["winner"], d["rule"] = perm[0], "within_tie_permissive_license"
        return d
    cov = {e: sel["engines"][e]["incremental_coverage"] for e in fin}
    d["incremental_coverage"] = cov
    if cov[fin[0]] == cov[fin[1]]:
        d["winner"], d["rule"] = None, "unresolved_tie"
    else:
        d["winner"] = max(fin, key=cov.get)
        d["rule"] = "within_tie_incremental_coverage"
    return d


def build_report(rows, sel, n_dev_synsets=None):
    scores = {s: score_source(rows, s) for s in SOURCES}
    return {
        "note": "dev only, one judge, ~50 synsets: informs engine selection; not the evaluation result",
        "dev_synsets": n_dev_synsets,
        "sheet_rows": len(rows),
        "sources": scores,
        "decision": decide(scores, sel),
    }


def show(rep):
    print(f"{'source':<13}{'prop':>5}{'judg':>5}{'excl':>5}{'corr':>5}{'prec':>7}{'wilson95':>16}{'only':>6}{'syn+':>6}")
    for s, v in rep["sources"].items():
        p = "-" if v["precision"] is None else f"{v['precision']:.3f}"
        w = "-" if v["wilson_lo"] is None else f"{v['wilson_lo']:.3f}-{v['wilson_hi']:.3f}"
        print(f"{s:<13}{v['proposed']:>5}{v['judged']:>5}{v['excluded_blank']:>5}{v['correct']:>5}{p:>7}{w:>16}"
              f"{v['only_this_source']['judged']:>6}{v['dev_synsets_with_correct']:>6}")
    for s, v in rep["sources"].items():
        pp = {g: (None if x["precision"] is None else round(x["precision"], 3)) for g, x in v["per_pos"].items()}
        print(f"  {s}: per-POS {pp}; errors {v['error_categories']}")
    d = rep["decision"]
    print(f"decision: {d['winner']} via {d['rule']} (gap {d['gap_points']} points, tie <= {d['tie_points']})")


def main():
    try:
        rows = load(test_ids=read_ids(TEST))
        sel = json.loads(SEL.read_text(encoding="utf-8"))
        rep = build_report(rows, sel, len(read_ids(DEV)))
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