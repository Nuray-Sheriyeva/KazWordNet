"""Step 3: POS-proportional seeded sample of N synsets from the resolved Core list.

Adjective satellites ('s') count as adjectives ('a') for stratification only.
Run: PYTHONPATH=src python -m kazwn.pos_sample [--n 1000] [--seed 42]
"""
import argparse, csv, hashlib, json, random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data" / "scope"
GROUP = {"n": "n", "v": "v", "a": "a", "s": "a", "r": "r"}


def allocate(counts, n):
    """Largest-remainder allocation so quotas sum to exactly n."""
    total = sum(counts.values())
    exact = {g: c * n / total for g, c in counts.items()}
    quota = {g: int(x) for g, x in exact.items()}
    left = n - sum(quota.values())
    for g in sorted(exact, key=lambda g: (exact[g] - quota[g], g), reverse=True)[:left]:
        quota[g] += 1
    return quota


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    src = SCOPE / "core_resolved.tsv"
    with open(src, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    pools = defaultdict(list)
    for r in rows:
        pools[GROUP[r["pos"]]].append(r)
    for g in pools:
        pools[g].sort(key=lambda r: r["synset_id"])  # deterministic base order

    quota = allocate({g: len(p) for g, p in pools.items()}, args.n)
    rng = random.Random(args.seed)
    chosen = []
    for g in sorted(pools):
        chosen += rng.sample(pools[g], quota[g])
    order = {g: i for i, g in enumerate("nvar")}
    chosen.sort(key=lambda r: (order[GROUP[r["pos"]]], r["synset_id"]))

    with open(SCOPE / "scope_1k.tsv", "w", encoding="utf-8") as f:
        f.write("idx\tsynset_id\tpos\tnltk_name\tlemmas_en\tfile_rank\n")
        for i, r in enumerate(chosen, 1):
            f.write(f"{i}\t{r['synset_id']}\t{r['pos']}\t{r['nltk_name']}\t{r['lemmas_en']}\t{r['file_rank']}\n")

    share = lambda d: {g: f"{v} ({v / sum(d.values()):.1%})" for g, v in sorted(d.items())}
    manifest = {
        "method": "seeded POS-proportional random sample (largest remainder); file has no ranking",
        "seed": args.seed, "n": args.n,
        "core_resolved_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "pos_full": share({g: len(p) for g, p in pools.items()}),
        "quota": quota, "pos_selected": share(quota),
    }
    (SCOPE / "scope_1k_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()