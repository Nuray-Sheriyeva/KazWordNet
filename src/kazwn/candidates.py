"""S1: shared candidate contract and normalizer.

One TSV per source (dict, mt, llm), one row per (synset_id, lemma_kk, source).
Rejected strings go to a separate <source>_rejected.tsv so nothing disappears.
"""
import csv, json, re, unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND_DIR = ROOT / "data" / "candidates"
SOURCES = ("dict", "mt", "llm")
FILES = {"dict": "b0_dict", "mt": "mt", "llm": "llm"}

CAND_COLS = ["synset_id", "lemma_en", "lemma_kk", "lemma_raw", "pos", "source", "evidence", "flags"]
REJ_COLS = ["synset_id", "lemma_en", "lemma_raw", "pos", "source", "reason", "evidence"]

# 42-letter Kazakh Cyrillic alphabet (lowercase)
KK_LETTERS = set("абвгғдеёжзийкқлмнңопрстуұүфхһцчшщъыіьэюя" + "әө")
ALLOWED = KK_LETTERS | {"-", " "}
LOAN_LETTERS = set("вёфцщъьэч")  # hint only, never a filter

# Latin (or schwa) letters that render like a Kazakh Cyrillic letter -> that letter
LOOKALIKE = {
    "a": "\u0430", "c": "\u0441", "e": "\u0435", "o": "\u043e", "p": "\u0440",
    "x": "\u0445", "y": "\u0443", "i": "\u0456", "k": "\u043a", "h": "\u04bb",
    "\u0259": "\u04d9",  # Latin schwa -> Cyrillic ә
}

_ZW = {ord(c): None for c in "\u200b\u200c\u200d\u2060\ufeff\u00ad"}
_NOTE = re.compile(r"\([^)]*\)|\[[^\]]*\]")


@dataclass
class NormResult:
    ok: bool
    lemma: str = ""
    flags: list = field(default_factory=list)
    reason: str = ""


@dataclass
class Candidate:
    synset_id: str
    lemma_en: str
    lemma_kk: str
    lemma_raw: str
    pos: str
    source: str
    evidence: list = field(default_factory=list)  # [{"dict": ..., "entry_id": ...}, ...]
    flags: list = field(default_factory=list)


@dataclass
class Rejected:
    synset_id: str
    lemma_en: str
    lemma_raw: str
    pos: str
    source: str
    reason: str
    evidence: list = field(default_factory=list)


def _script(ch):
    name = unicodedata.name(ch, "")
    return "LATIN" if name.startswith("LATIN") else "CYRILLIC" if name.startswith("CYRILLIC") else ""


def normalize(raw, pos=""):
    s = unicodedata.normalize("NFC", raw).translate(_ZW)
    s = _NOTE.sub(" ", re.sub(r"\s+", " ", s))
    s = re.sub(r"\s+", " ", s).strip(" -").lower()
    if not s:
        return NormResult(False, reason="empty")

    fixed, out = False, []
    for w in re.split(r"([ -])", s):
        if not w or w in (" ", "-"):
            out.append(w)
            continue
        scripts = {_script(c) for c in w}
        if "LATIN" in scripts:
            if "CYRILLIC" not in scripts:
                return NormResult(False, reason="latin_script")
            if any(_script(c) == "LATIN" and c not in LOOKALIKE for c in w):
                return NormResult(False, reason="mixed_script_unfixable")
            w = "".join(LOOKALIKE.get(c, c) for c in w)
            fixed = True
        out.append(w)
    s = re.sub(r"\s+", " ", "".join(out)).strip(" -")

    bad = sorted({c for c in s if c not in ALLOWED})
    if bad:
        return NormResult(False, reason="invalid_char:" + "".join(bad))

    flags = []
    if fixed:
        flags.append("lookalike_fixed")
    if " " in s:
        flags.append("multiword")
    if LOAN_LETTERS & set(s):
        flags.append("loan_letters")
    if pos == "v" and not s.split(" ")[-1].endswith(("у", "ю")):
        flags.append("verb_form_check")
    return NormResult(True, s, flags)


def split_translations(field_text):
    """Split a dictionary translation field on ; , / outside (...) and [...]."""
    parts, buf, depth = [], [], 0
    for ch in field_text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and ch in ";,/":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def process_field(synset_id, lemma_en, pos, field_text, source, evidence, extra_flags=()):
    """Split a translation field, normalize each part -> (candidates, rejected)."""
    assert source in SOURCES, source
    cands, rejs = [], []
    for raw in split_translations(field_text):
        raw = re.sub(r"[\t\r\n]+", " ", raw)
        r = normalize(raw, pos)
        if r.ok:
            flags = sorted(set(r.flags) | set(extra_flags))
            cands.append(Candidate(synset_id, lemma_en, r.lemma, raw, pos, source, list(evidence), flags))
        else:
            rejs.append(Rejected(synset_id, lemma_en, raw, pos, source, r.reason, list(evidence)))
    return cands, rejs


def _ev_key(e):
    return json.dumps(e, sort_keys=True, ensure_ascii=False)


def merge(cands):
    """Collapse duplicates on (synset_id, lemma_kk, source), unioning evidence/flags/lemma_en."""
    groups = {}
    for c in sorted(cands, key=lambda c: (c.synset_id, c.lemma_kk, c.source, c.lemma_raw)):
        groups.setdefault((c.synset_id, c.lemma_kk, c.source), []).append(c)
    out = []
    for (sid, lk, src), g in groups.items():
        ev = {_ev_key(e): e for c in g for e in c.evidence}
        out.append(Candidate(
            sid, "|".join(sorted({x for c in g for x in c.lemma_en.split("|") if x})), lk,
            g[0].lemma_raw, g[0].pos, src,
            [ev[k] for k in sorted(ev)], sorted({f for c in g for f in c.flags})))
    return out


def _path(source, rejected=False):
    return CAND_DIR / (FILES[source] + ("_rejected" if rejected else "") + ".tsv")


def _write_rows(path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)


def write_candidates(source, cands, path=None):
    assert source in SOURCES, source
    for c in cands:
        if c.source != source:
            raise ValueError(f"candidate source {c.source!r} != file source {source!r}")
        if normalize(c.lemma_kk, c.pos).lemma != c.lemma_kk:
            raise ValueError(f"lemma_kk not normalized: {c.lemma_kk!r}")
    merged = merge(cands)
    _write_rows(Path(path) if path else _path(source), CAND_COLS,
                [[c.synset_id, c.lemma_en, c.lemma_kk, c.lemma_raw, c.pos, c.source,
                  json.dumps(c.evidence, ensure_ascii=False, sort_keys=True), "|".join(c.flags)] for c in merged])
    return merged


def read_candidates(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [Candidate(r["synset_id"], r["lemma_en"], r["lemma_kk"], r["lemma_raw"], r["pos"],
                          r["source"], json.loads(r["evidence"]), [x for x in r["flags"].split("|") if x])
                for r in csv.DictReader(f, delimiter="\t")]


def write_rejected(source, rejs, path=None):
    assert source in SOURCES, source
    rows = sorted(rejs, key=lambda r: (r.synset_id, r.lemma_raw, r.reason))
    _write_rows(Path(path) if path else _path(source, True), REJ_COLS,
                [[r.synset_id, r.lemma_en, r.lemma_raw, r.pos, r.source, r.reason,
                  json.dumps(r.evidence, ensure_ascii=False, sort_keys=True)] for r in rows])
    return rows


def read_rejected(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [Rejected(r["synset_id"], r["lemma_en"], r["lemma_raw"], r["pos"], r["source"],
                         r["reason"], json.loads(r["evidence"]))
                for r in csv.DictReader(f, delimiter="\t")]