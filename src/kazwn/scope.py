"""Steps 1-2: parse Core WordNet (sense-key format), resolve to PWN 3.0 synsets.

Output: data/scope/core_resolved.tsv (deduplicated by synset, file order kept)
Run: PYTHONPATH=src python -m kazwn.scope
"""
import hashlib, json, re, sys, urllib.request
from collections import Counter
from pathlib import Path

from nltk.corpus import wordnet as wn

URL = "https://wordnetcode.princeton.edu/standoff-files/core-wordnet.txt"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "core-wordnet.txt"
OUT_DIR = ROOT / "data" / "scope"
# e.g.  a [able%5:00:00:capable:00] [able] capable
LINE_RE = re.compile(r"^\s*([nvar])\s+\[([^\]]+)\]\s+\[([^\]]*)\]")


def fetch():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if not RAW.exists() or RAW.stat().st_size == 0:
        urllib.request.urlretrieve(URL, RAW)
    return hashlib.sha256(RAW.read_bytes()).hexdigest()


def parse():
    items, bad = [], []
    for line in RAW.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if m:
            items.append((m.group(1), m.group(2), m.group(3)))
        else:
            bad.append(line)
    if len(items) < 4000:
        print("First unparsed lines:", *bad[:3], sep="\n  ", file=sys.stderr)
        sys.exit(f"Parsed only {len(items)} entries from {RAW}")
    return items, len(bad)


def resolve(sense_key):
    try:
        return wn.lemma_from_key(sense_key).synset()
    except Exception:
        return None


def pos_share(pos_list):
    c = Counter(pos_list)
    t = sum(c.values())
    return {k: f"{v} ({v / t:.1%})" for k, v in sorted(c.items())}


def main():
    sha = fetch()
    items, unparsed = parse()

    rows, seen, dropped, dupes = [], set(), [], 0
    for rank, (pos, key, lemma) in enumerate(items, 1):
        s = resolve(key)
        if s is None:
            dropped.append(key)
            continue
        if s.name() in seen:
            dupes += 1
            continue
        seen.add(s.name())
        rows.append((rank, f"{s.offset():08d}-{s.pos()}", s.pos(), s.name(), key,
                     "|".join(s.lemma_names())))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "core_resolved.tsv", "w", encoding="utf-8") as f:
        f.write("file_rank\tsynset_id\tpos\tnltk_name\tsense_key\tlemmas_en\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")

    manifest = {
        "source_url": URL, "source_sha256": sha, "wordnet_version": wn.get_version(),
        "lines_parsed": len(items), "lines_unparsed": unparsed,
        "dropped_unresolved": dropped, "duplicate_synsets_skipped": dupes,
        "synsets_resolved": len(rows), "pos_full_list": pos_share([r[2] for r in rows]),
    }
    (OUT_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()