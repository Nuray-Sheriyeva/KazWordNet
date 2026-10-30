import json

from kazwn.b0_dict import build_b0
from kazwn.kaikki import extract, load_extract, needed_lemmas

LINES = [
    {"word": "book", "lang_code": "en", "pos": "noun", "translations": [
        {"lang_code": "kk", "word": "кітап", "sense": "bound collection", "tags": ["dialectal"]}]},
    {"word": "book", "lang_code": "en", "pos": "verb", "translations": [{"lang_code": "kk", "word": "брондау"}]},
    {"word": "volume", "lang_code": "en", "pos": "noun", "translations": [{"lang_code": "kk", "word": "кітап"}]},
    {"word": "big", "lang_code": "en", "pos": "adj", "translations": [{"lang_code": "kk", "word": "үлкен"}]},
    {"word": "cat", "lang_code": "en", "pos": "noun", "translations": [
        {"lang_code": "kk", "word": "мысық"}, {"lang_code": "kk", "word": "мышық"}, {"lang_code": "kk", "word": "cat"}]},
]
ROWS = [
    {"synset_id": "1-n", "pos": "n", "lemmas_en": "book|volume"},
    {"synset_id": "2-n", "pos": "n", "lemmas_en": "book"},            # same lemma, other sense
    {"synset_id": "3-v", "pos": "v", "lemmas_en": "book"},
    {"synset_id": "4-s", "pos": "s", "lemmas_en": "big"},             # satellite -> adj
    {"synset_id": "5-n", "pos": "n", "lemmas_en": "cat"},
]


def build(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in LINES) + "\n", encoding="utf-8")
    out = tmp_path / "x.jsonl"
    extract(p, needed_lemmas(ROWS), out)
    return build_b0(ROWS, load_extract(out), "2026-10-01")


def test_sense_blind_and_pos_aware(tmp_path):
    c, r = build(tmp_path)
    by = {}
    for x in c:
        by.setdefault(x.synset_id, set()).add(x.lemma_kk)
    assert by["1-n"] == by["2-n"] == {"кітап"}   # sense-blind: both noun synsets get it
    assert by["3-v"] == {"брондау"}               # verb synset only gets the verb entry
    assert by["4-s"] == {"үлкен"}                 # 's' behaves as adjective
    assert by["5-n"] == {"мысық", "мышық"}        # both spellings kept
    assert [x.reason for x in r] == ["latin_script"]


def test_evidence_and_merge(tmp_path):
    from kazwn.candidates import merge
    c, _ = build(tmp_path)
    rows = [x for x in c if x.synset_id == "1-n" and x.lemma_kk == "кітап"]
    assert len(rows) == 2                         # one per source entry (book, volume) before merging
    m = merge(rows)
    assert len(m) == 1 and m[0].lemma_en == "book|volume" and len(m[0].evidence) == 2
    ev = [e for e in m[0].evidence if e["entry_id"].startswith("book#")][0]
    assert ev["dict"] == "kaikki" and ev["dump"] == "2026-10-01"
    assert ev["sense"] == "bound collection" and ev["tags"] == ["dialectal"]