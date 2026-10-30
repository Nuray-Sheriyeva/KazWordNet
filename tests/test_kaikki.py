import gzip, json

from kazwn.b0_coverage import compute_coverage
from kazwn.kaikki import extract, load_extract, needed_lemmas

LINES = [
    {"word": "book", "lang_code": "en", "pos": "noun", "translations": [
        {"lang_code": "kk", "word": "кітап", "sense": "bound collection"},
        {"lang_code": "kk", "word": "кітап", "sense": "bound collection"},  # duplicate
        {"lang_code": "ru", "word": "книга"}]},
    {"word": "book", "lang_code": "en", "pos": "verb",
     "senses": [{"translations": [{"code": "kk", "word": "брондау"}]}]},      # old key + sense-level
    {"word": "run", "lang_code": "en", "pos": "noun", "translations": [{"lang_code": "kk", "word": "жүгіру"}]},
    {"word": "ice cream", "lang_code": "en", "pos": "noun", "translations": [{"lang_code": "ru", "word": "мороженое"}]},
    {"word": "table", "lang_code": "en", "pos": "noun", "translations": [{"lang_code": "kk", "word": "үстел"}]},  # not needed
    {"word": "cat", "lang_code": "en", "pos": "noun", "translations": [{"lang_code": "kk", "word": "cat"}]},     # latin -> rejected
]
ROWS = [
    {"synset_id": "1-n", "pos": "n", "lemmas_en": "book"},
    {"synset_id": "2-v", "pos": "v", "lemmas_en": "book"},
    {"synset_id": "3-v", "pos": "v", "lemmas_en": "run"},          # kk only on the noun entry
    {"synset_id": "4-n", "pos": "n", "lemmas_en": "ice_cream"},    # underscore multiword, no kk
    {"synset_id": "5-n", "pos": "n", "lemmas_en": "cat"},          # only a Latin-script translation
]


def make_dump(tmp_path, gz=False):
    text = "\n".join(json.dumps(x, ensure_ascii=False) for x in LINES) + "\n\nnot json \"kk\"\n"
    p = tmp_path / ("d.jsonl.gz" if gz else "d.jsonl")
    if gz:
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        p.write_text(text, encoding="utf-8")
    return p


def test_needed_lemmas_replaces_underscore():
    assert needed_lemmas(ROWS) == {"book", "run", "ice cream", "cat"}


def test_extract_and_index(tmp_path):
    for gz in (False, True):
        out = tmp_path / "x.jsonl"
        st = extract(make_dump(tmp_path, gz), needed_lemmas(ROWS), out)
        assert st["bad_json"] == 1 and st["entries_kept"] == 4  # book n, book v, run n, cat n
        idx = load_extract(out)
        assert "table" not in idx
        book_n = [r for r in idx["book"] if r["pos"] == "noun"][0]
        assert [t["word"] for t in book_n["translations"]] == ["кітап"]  # deduplicated
        assert book_n["entry_id"].startswith("book#noun@L")
        assert [t["word"] for r in idx["book"] if r["pos"] == "verb" for t in r["translations"]] == ["брондау"]


def test_coverage_strict_vs_loose(tmp_path):
    out = tmp_path / "x.jsonl"
    extract(make_dump(tmp_path), needed_lemmas(ROWS), out)
    rep, unc = compute_coverage(ROWS, load_extract(out))
    assert rep["n_synsets"] == 5
    assert rep["coverage_strict"] == 0.4      # 1-n and 2-v
    assert rep["coverage_loose"] == 0.6       # + 3-v via the noun entry
    assert rep["per_pos"]["v"]["strict"] == 1 and rep["per_pos"]["v"]["loose"] == 2
    assert rep["rejected_translation_strings"] >= 1   # 'cat' (latin_script)
    assert {r["synset_id"] for r in unc} == {"3-v", "4-n", "5-n"}