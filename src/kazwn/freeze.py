"""Step 4: freeze the scope file with gloss, examples, hypernym.
Run: PYTHONPATH=src python -m kazwn.freeze [--force]
"""
import argparse, csv, hashlib, os, re, sys, unicodedata
from pathlib import Path

from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data" / "scope"
SRC, OUT, SHA = SCOPE / "scope_1k.tsv", SCOPE / "scope_1k_frozen.tsv", SCOPE / "scope_1k_frozen.sha256"
COLS = ["idx", "synset_id", "pos", "lemmas_en", "gloss", "examples", "hypernym_id", "hypernym_lemmas"]


def clean(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", t)).strip()


def get_synset(sid):
    off, pos = sid.split("-")
    return wn.synset_from_pos_and_offset("a" if pos == "s" else pos, int(off))


def sid_of(s):
    return f"{s.offset():08d}-{s.pos()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    if OUT.exists() and not ap.parse_args().force:
        sys.exit(f"{OUT.name} already exists and is frozen. Use --force only to deliberately re-freeze.")
    if OUT.exists():
        OUT.chmod(0o644)
        OUT.unlink()

    with open(SRC, encoding="utf-8", newline="") as f:
        src = list(csv.DictReader(f, delimiter="\t"))

    no_ex = multi = no_hyp = 0
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(COLS)
        for r in src:
            s = get_synset(r["synset_id"])
            hyps = sorted(s.hypernyms() + s.instance_hypernyms(), key=sid_of)
            h = hyps[0] if hyps else None  # first by id; deterministic
            ex = [clean(e) for e in s.examples()]
            no_ex += not ex
            multi += len(s.lemma_names()) > 1
            no_hyp += h is None
            w.writerow([r["idx"], sid_of(s), r["pos"], "|".join(s.lemma_names()),
                        clean(s.definition()), " || ".join(ex),
                        sid_of(h) if h else "", "|".join(h.lemma_names()) if h else ""])

    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    SHA.write_text(f"{digest}  {OUT.name}\n")
    OUT.chmod(0o444)
    print(f"froze {len(src)} synsets -> {OUT.name}\nsha256 {digest}")
    print(f"no examples: {no_ex} | multi-lemma: {multi} | no hypernym: {no_hyp}")


if __name__ == "__main__":
    main()