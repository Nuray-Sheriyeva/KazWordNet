"""S2 check: how much of the scoped 1,000 synsets does the kaikki en->kk extract cover?

Strict = translations from entries whose POS matches the synset POS (what B0 will use).
Loose  = translations from any POS (diagnostic only).
Candidates are counted after S1 normalization, so rejected strings do not inflate coverage.
Run: PYTHONPATH=src python -m kazwn.b0_coverage
"""
import csv, json, statistics
from pathlib import Path

from kazwn.candidates import normalize, split_translations
from kazwn.kaikki import GROUP, KAIKKI_POS, load_extract, load_scope, scope_lemmas

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "data" / "reports"
THIN = 0.40  # advisory rule of thumb, not a published threshold


def synset_candidates(index, row, strict=True):
    """-> (set of normalized kk lemmas, number of rejected raw strings)."""
    group = GROUP[row["pos"]]
    found, rejected = set(), 0
    for lem in scope_lemmas(row):
        for rec in index.get(lem, []):
            if strict and rec["pos"] not in KAIKKI_POS[group]:
                continue
            for t in rec["translations"]:
                for raw in split_translations(t["word"]):
                    r = normalize(raw, group)
                    if r.ok:
                        found.add(r.lemma)
                    else:
                        rejected += 1
    return found, rejected


def compute_coverage(rows, index):
    per = {}
    uncovered, counts, rejected_total = [], [], 0
    lemmas_all = {x for r in rows for x in scope_lemmas(r)}
    for r in rows:
        g = GROUP[r["pos"]]
        d = per.setdefault(g, {"n": 0, "strict": 0, "loose": 0})
        d["n"] += 1
        strict, rej = synset_candidates(index, r, True)
        loose, _ = synset_candidates(index, r, False)
        rejected_total += rej
        d["strict"] += bool(strict)
        d["loose"] += bool(loose)
        if strict:
            counts.append(len(strict))
        else:
            uncovered.append(r)
    n = len(rows)
    s = sum(d["strict"] for d in per.values())
    lo = sum(d["loose"] for d in per.values())
    report = {
        "n_synsets": n,
        "coverage_strict": round(s / n, 4) if n else 0.0,
        "coverage_loose": round(lo / n, 4) if n else 0.0,
        "per_pos": {g: {**d, "coverage_strict": round(d["strict"] / d["n"], 4)} for g, d in sorted(per.items())},
        "candidates_per_covered_synset": {
            "mean": round(statistics.mean(counts), 2) if counts else 0,
            "median": statistics.median(counts) if counts else 0},
        "distinct_english_lemmas": len(lemmas_all),
        "english_lemmas_with_kk": len(lemmas_all & set(index)),
        "rejected_translation_strings": rejected_total,
    }
    return report, uncovered


def main():
    rows, index = load_scope(), load_extract()
    report, uncovered = compute_coverage(rows, index)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "b0_coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(REPORTS / "b0_uncovered.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["synset_id", "pos", "lemmas_en"])
        w.writerows([[r["synset_id"], r["pos"], r["lemmas_en"]] for r in uncovered])
    print(json.dumps(report, indent=2))
    if report["coverage_strict"] < THIN:
        print(f"\nADVISORY: strict coverage < {THIN:.0%} (rule of thumb, not a published threshold). "
              "B0 may be too thin to be a useful baseline; consider a second source.")


if __name__ == "__main__":
    main()