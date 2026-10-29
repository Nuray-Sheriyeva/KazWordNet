"""Step 5: POS-stratified 150-synset eval sample, split 50 dev / 100 test.
Run: PYTHONPATH=src python -m kazwn.eval_split [--seed 7] [--force]
"""
import argparse, csv, hashlib, json, random
from collections import defaultdict
from pathlib import Path

from kazwn.freeze import COLS
from kazwn.pos_sample import GROUP, allocate

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "data" / "scope" / "scope_1k_frozen.tsv"
OUT = ROOT / "data" / "eval"
N_ALL, N_DEV = 150, 50
ORDER = {g: i for i, g in enumerate("nvar")}


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (ORDER[GROUP[r["pos"]]], r["synset_id"])))
    path.chmod(0o444)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    targets = [OUT / "eval_dev.tsv", OUT / "eval_test.tsv", OUT / "eval_split_manifest.json"]
    if any(t.exists() for t in targets):
        if not args.force:
            raise SystemExit("Eval split already exists. Use --force only to deliberately redo it.")
        for t in targets:
            if t.exists():
                t.chmod(0o644)
                t.unlink()

    with open(FROZEN, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    pools = defaultdict(list)
    for r in rows:
        pools[GROUP[r["pos"]]].append(r)
    for g in pools:
        pools[g].sort(key=lambda r: r["synset_id"])

    q_all = allocate({g: len(p) for g, p in pools.items()}, N_ALL)
    q_dev = allocate(q_all, N_DEV)  # dev share per POS, proportional within the 150
    rng = random.Random(args.seed)
    dev, test = [], []
    for g in sorted(pools):
        s = rng.sample(pools[g], q_all[g])  # random order
        dev += s[: q_dev[g]]
        test += s[q_dev[g]:]

    sha_dev, sha_test = write(targets[0], dev), write(targets[1], test)
    manifest = {
        "seed": args.seed, "n_all": N_ALL, "n_dev": len(dev), "n_test": len(test),
        "frozen_sha256": hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
        "pos_pool": {g: len(p) for g, p in sorted(pools.items())},
        "quota_all": q_all, "quota_dev": q_dev,
        "quota_test": {g: q_all[g] - q_dev[g] for g in q_all},
        "dev_sha256": sha_dev, "test_sha256": sha_test,
        "rule": "tune prompts/thresholds on dev only; test is judged once",
    }
    targets[2].write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()