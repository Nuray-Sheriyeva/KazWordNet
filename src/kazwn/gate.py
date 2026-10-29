"""Step 6: the pre-registered 5k gate. Call check_gate() once B3 is judged on test."""
import json, math
from pathlib import Path

CFG = Path(__file__).resolve().parents[2] / "configs" / "gate.json"


def wilson_lower(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / d


def check_gate(correct, judged, covered, n_synsets, per_pos=None):
    """per_pos: {pos: (correct, judged)}. Returns (passed, report)."""
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    prec = correct / judged if judged else 0.0
    lo = wilson_lower(correct, judged)
    cov = covered / n_synsets if n_synsets else 0.0
    report = {
        "precision": (round(prec, 4), prec >= cfg["min_precision"]),
        "wilson95_lower": (round(lo, 4), lo >= cfg["min_precision_wilson95_lower"]),
        "coverage": (round(cov, 4), cov >= cfg["min_coverage"]),
    }
    for pos, (c, j) in (per_pos or {}).items():
        if j >= cfg["min_judged_per_pos"]:
            report[f"precision_{pos}"] = (round(c / j, 4), c / j >= cfg["min_precision_per_pos"])
    return all(ok for _, ok in report.values()), report