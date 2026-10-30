from kazwn.candidates import (KK_LETTERS, Candidate, Rejected, normalize, process_field,
                              read_candidates, read_rejected, split_translations,
                              write_candidates, write_rejected)


def test_alphabet_has_42_letters():
    assert len(KK_LETTERS) == 42


def test_latin_i_lookalike_fixed():
    r = normalize("к\u0069тап", "n")
    assert r.ok and r.lemma == "к\u0456тап" and "lookalike_fixed" in r.flags


def test_schwa_lookalike_fixed():
    r = normalize("\u0259лем", "n")
    assert r.ok and r.lemma == "\u04d9лем"


def test_pure_latin_rejected():
    r = normalize("book", "n")
    assert not r.ok and r.reason == "latin_script"


def test_unfixable_mixed_rejected():
    r = normalize("кі\u0062ап", "n")
    assert not r.ok and r.reason == "mixed_script_unfixable"


def test_zero_width_and_case_and_nfc():
    assert normalize("жа\u200bзу", "v").lemma == "жазу"
    assert normalize("КІТАП", "n").lemma == "кітап"
    assert normalize("а\u0438\u0306", "n").lemma == "ай"  # decomposed й


def test_parenthetical_stripped():
    assert normalize("жүгіру (to run)", "v").lemma == "жүгіру"


def test_invalid_char_and_empty():
    r = normalize("кітап1", "n")
    assert not r.ok and r.reason.startswith("invalid_char")
    assert normalize("(note)", "n").reason == "empty"


def test_verb_form_check():
    assert "verb_form_check" in normalize("жаз", "v").flags
    assert "verb_form_check" not in normalize("сүю", "v").flags
    r = normalize("оқып шығу", "v")
    assert "multiword" in r.flags and "verb_form_check" not in r.flags
    assert "verb_form_check" not in normalize("жаз", "n").flags


def test_loan_letters_includes_ch():
    assert "loan_letters" in normalize("чемпион", "n").flags
    assert "loan_letters" not in normalize("мектеп", "n").flags


def test_split_respects_brackets():
    assert split_translations("жүгіру (fast, quickly); жарысу") == ["жүгіру (fast, quickly)", "жарысу"]
    assert len(split_translations("кітап; дәптер, оқулық / хат")) == 4


def test_process_field_splits_and_rejects():
    ev = [{"dict": "kaikki", "entry_id": "book#1"}]
    c, r = process_field("1-n", "book", "n", "кітап; book", "dict", ev)
    assert [x.lemma_kk for x in c] == ["кітап"] and [x.reason for x in r] == ["latin_script"]


def test_roundtrip_merges_duplicates(tmp_path):
    a = Candidate("1-n", "book", "кітап", "кітап", "n", "dict", [{"dict": "kaikki", "entry_id": "a"}], [])
    b = Candidate("1-n", "volume", "кітап", "Кітап", "n", "dict", [{"dict": "kaikki", "entry_id": "b"}], ["loan_letters"])
    p = tmp_path / "d.tsv"
    merged = write_candidates("dict", [b, a], p)
    assert len(merged) == 1
    back = read_candidates(p)
    assert back == merged
    assert back[0].lemma_en == "book|volume" and len(back[0].evidence) == 2 and back[0].flags == ["loan_letters"]


def test_write_rejects_wrong_source_and_unnormalized(tmp_path):
    import pytest
    bad_src = Candidate("1-n", "x", "кітап", "кітап", "n", "mt")
    with pytest.raises(ValueError):
        write_candidates("dict", [bad_src], tmp_path / "x.tsv")
    unnorm = Candidate("1-n", "x", "КІТАП", "КІТАП", "n", "dict")
    with pytest.raises(ValueError):
        write_candidates("dict", [unnorm], tmp_path / "y.tsv")


def test_rejected_roundtrip(tmp_path):
    r = Rejected("1-n", "book", "book", "n", "dict", "latin_script", [{"dict": "kaikki", "entry_id": "a"}])
    p = tmp_path / "r.tsv"
    write_rejected("dict", [r], p)
    assert read_rejected(p) == [r]