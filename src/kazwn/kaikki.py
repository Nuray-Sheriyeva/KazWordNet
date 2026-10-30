"""S2: extract en->kk translations for the scoped lemmas from a kaikki/Wiktextract dump.

Run (from repo root):
  PYTHONPATH=src python -m kazwn.kaikki peek    --dump data/dumps/<dump>.jsonl[.gz] [--n 3]
  PYTHONPATH=src python -m kazwn.kaikki extract --dump data/dumps/<dump>.jsonl[.gz]
"""
import argparse, csv, gzip, json, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "data" / "scope" / "scope_1k_frozen.tsv"
EXTRACT = ROOT / "data" / "raw" / "en_kk_extract.jsonl"

GROUP = {"n": "n", "v": "v", "a": "a", "s": "a", "r": "r"}  # WordNet pos -> group
KAIKKI_POS = {"n": {"noun", "name"}, "v": {"verb"}, "a": {"adj"}, "r": {"adv"}}


def lemma_key(lemma):
    return lemma.replace("_", " ")


def load_scope(path=SCOPE):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def scope_lemmas(row):
    return [lemma_key(x) for x in row["lemmas_en"].split("|") if x]


def needed_lemmas(rows):
    return {x for r in rows for x in scope_lemmas(r)}


def _open(path):
    p = str(path)
    return gzip.open(p, "rt", encoding="utf-8") if p.endswith(".gz") else open(p, encoding="utf-8")


def kk_translations(entry):
    """kk translation dicts of one entry: entry-level and sense-level; 'lang_code' or old 'code' key."""
    ts = list(entry.get("translations") or [])
    for s in entry.get("senses") or []:
        ts.extend(s.get("translations") or [])
    return [t for t in ts
            if isinstance(t, dict) and (t.get("lang_code") or t.get("code")) == "kk" and t.get("word")]


def extract(dump, needed, out=EXTRACT):
    stats = dict(lines=0, lines_with_kk=0, bad_json=0, entries_kept=0, translations_kept=0)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with _open(dump) as f, open(out, "w", encoding="utf-8", newline="\n") as o:
        for n, line in enumerate(f, 1):
            stats["lines"] += 1
            if '"kk"' not in line:  # cheap prefilter: skip the JSON parse for most lines
                continue
            stats["lines_with_kk"] += 1
            try:
                e = json.loads(line)
            except ValueError:
                stats["bad_json"] += 1
                continue
            word = e.get("word")
            if word not in needed or e.get("lang_code", "en") != "en":
                continue
            seen, tr = set(), []
            for t in kk_translations(e):
                k = (t["word"], t.get("sense", ""))
                if k in seen:
                    continue
                seen.add(k)
                tr.append({"word": t["word"], "sense": t.get("sense", ""),
                           "tags": t.get("tags", []), "english": t.get("english", "")})
            if not tr:
                continue
            pos = e.get("pos", "")
            o.write(json.dumps({"entry_id": f"{word}#{pos}@L{n}", "word": word, "pos": pos,
                                "translations": tr}, ensure_ascii=False) + "\n")
            stats["entries_kept"] += 1
            stats["translations_kept"] += len(tr)
    return stats


def load_extract(path=EXTRACT):
    index = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            index[rec["word"]].append(rec)
    return index


def peek(dump, n=3):
    shown = 0
    with _open(dump) as f:
        for line in f:
            if '"kk"' not in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ts = kk_translations(e)
            if ts:
                print(json.dumps({"word": e.get("word"), "pos": e.get("pos"),
                                  "lang_code": e.get("lang_code"), "kk": ts[:2]}, ensure_ascii=False, indent=1))
                shown += 1
                if shown >= n:
                    return
    if not shown:
        print("No kk translations found by kk_translations(); inspect the dump structure manually.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["peek", "extract"])
    ap.add_argument("--dump", required=True)
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "peek":
        return peek(a.dump, a.n)
    needed = needed_lemmas(load_scope())
    st = extract(a.dump, needed)
    print(json.dumps({"needed_lemmas": len(needed), **st}, indent=2))
    if st["translations_kept"] == 0:
        sys.exit("No translations extracted. Run `peek` and check the dump's structure.")


if __name__ == "__main__":
    main()