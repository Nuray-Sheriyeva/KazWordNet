"""Verifies step 4. Run: PYTHONPATH=src python -m kazwn.verify_freeze"""
import csv, hashlib, os, stat, sys
from pathlib import Path

from nltk.corpus import wordnet as wn
from kazwn.freeze import COLS, OUT, SHA, SRC, get_synset, sid_of

fails = []


def check(name, ok, detail=""):
    print("PASS" if ok else "FAIL", "-", name, detail)
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


rows, src = read(OUT), read(SRC)
check("header matches spec", list(rows[0].keys()) == COLS)
check("sha256 matches", hashlib.sha256(OUT.read_bytes()).hexdigest() == SHA.read_text().split()[0])
check("file is read-only", not (os.stat(OUT).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)))
check("1000 rows", len(rows) == 1000, str(len(rows)))
check("same ids and order as step 3", [r["synset_id"] for r in rows] == [r["synset_id"] for r in src])
check("no empty gloss", all(r["gloss"] for r in rows))
check("no empty lemmas", all(r["lemmas_en"] for r in rows))
check("lemmas match step 3", all(r["lemmas_en"] == s["lemmas_en"] for r, s in zip(rows, src)))
check("hypernym ids resolve and match lemmas",
      all(not r["hypernym_id"] or "|".join(get_synset(r["hypernym_id"]).lemma_names()) == r["hypernym_lemmas"] for r in rows))
check("hypernym id <-> lemmas both set or both empty", all(bool(r["hypernym_id"]) == bool(r["hypernym_lemmas"]) for r in rows))
check("nouns lack hypernym only at root", all(r["hypernym_id"] or get_synset(r["synset_id"]).name() == "entity.n.01"
                                              for r in rows if r["pos"] == "n"))
print("info: verbs without hypernym:", sum(1 for r in rows if r["pos"] == "v" and not r["hypernym_id"]),
      "| no examples:", sum(1 for r in rows if not r["examples"]),
      "| multi-lemma:", sum(1 for r in rows if "|" in r["lemmas_en"]))
print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)