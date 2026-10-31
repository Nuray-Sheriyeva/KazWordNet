"""Recompute every number in data/reports/mt_dev_score.json from the raw sheet, independently of mt_dev_score."""
import csv
import json
import sys

from kazwn import mt_dev_score as m

TOL = 1e-9


def main():
    fails = []
    rep = json.loads(m.OUT.read_text(encoding="utf-8"))
    test_ids = m.read_ids(m.TEST)
    sheet = list(csv.DictReader(open(m.SHEET, encoding="utf-8-sig", newline=""), delimiter="\t"))
    key = {r["key_id"]: r["sources"].split("|") for r in csv.DictReader(open(m.KEY, encoding="utf-8", newline=""), delimiter="\t")}
    if any(r["synset_id"] in test_ids for r in sheet):
        fails.append("sheet contains test-pool synsets")
    if len(sheet) != rep["sheet_rows"] or set(key) != {r["key_id"] for r in sheet}:
        fails.append("sheet/key rows differ from report")
    for src, v in rep["sources"].items():
        mine = [r for r in sheet if src in key[r["key_id"]]]
        j = [r for r in mine if r["correct"].strip() in ("0", "1")]
        k = sum(r["correct"].strip() == "1" for r in j)
        checks = {
            "proposed": (len(mine), v["proposed"]),
            "judged": (len(j), v["judged"]),
            "correct": (k, v["correct"]),
            "excluded_blank": (len(mine) - len(j), v["excluded_blank"]),
            "excluded_unsure": (sum(r["notes"].startswith("UNSURE:") and not r["correct"].strip() for r in mine), v["excluded_unsure"]),
            "only_judged": (sum(key[r["key_id"]] == [src] for r in j), v["only_this_source"]["judged"]),
            "synsets_with_correct": (len({r["synset_id"] for r in j if r["correct"].strip() == "1"}), v["dev_synsets_with_correct"]),
        }
        for g in ("n", "v", "a"):
            jj = [r for r in j if {"s": "a"}.get(r["pos"], r["pos"]) == g]
            checks[f"pos_{g}_judged"] = (len(jj), v["per_pos"][g]["judged"])
            checks[f"pos_{g}_correct"] = (sum(r["correct"].strip() == "1" for r in jj), v["per_pos"][g]["correct"])
        errs = {}
        for r in j:
            if r["correct"].strip() == "0":
                errs[r["error_category"].strip()] = errs.get(r["error_category"].strip(), 0) + 1
        if errs != v["error_categories"]:
            fails.append(f"{src}: error categories {errs} != {v['error_categories']}")
        for name, (a, b) in checks.items():
            if a != b:
                fails.append(f"{src}: {name} recomputed {a} != reported {b}")
        if j and abs(k / len(j) - v["precision"]) > TOL:
            fails.append(f"{src}: precision mismatch")
        if j and not (v["wilson_lo"] <= v["precision"] <= v["wilson_hi"]):
            fails.append(f"{src}: precision outside Wilson interval")
    sel = json.loads(m.SEL.read_text(encoding="utf-8"))
    d = m.decide({s: {"precision": rep["sources"][s]["precision"]} for s in rep["sources"]}, sel)
    if d != rep["decision"]:
        fails.append(f"decision does not recompute: {d} != {rep['decision']}")
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())