# Judging guidelines (fixed before judging)

Judge each row: is `lemma_kk` an acceptable Kazakh lemma for the *sense* given by `gloss` (and the row's POS)?
Put 1 or 0 in `correct`. For every 0, choose one `error_category`.

correct = 1 if a native speaker would accept the word or fixed phrase as a normal Kazakh expression of that
sense, in dictionary (citation) form, in standard spelling.

correct = 0 otherwise, with one category:
- wrong_sense: a real Kazakh word, but for another sense of the English lemma.
- calque: a literal rendering that is not used in Kazakh.
- russian_loan: a Russian loanword where a standard native/established Kazakh word exists.
  (A loanword that IS the standard Kazakh word is correct.)
- variant: non-standard spelling, dialectal or obsolete variant of an otherwise correct word. 
- form: not in citation form (verb not ending in -у/-ю, stem or finite form, unwanted plural/case ending).
- other: anything else (descriptive phrase, untranslated or garbled string).

Rules
- Judge each row on its own. Do not try to guess which system produced it.
- Do not open data/eval/dev_judging_key.tsv until every row is judged.
- A multiword candidate is correct only if it is an established expression; a free description is 0 / other.
- If unsure, ask whether you would put it in a dictionary entry for that sense; note doubts in `notes`.
- Do not change a judgment after seeing any results.
- If several categories apply, choose the first that fits in this order: other, wrong_sense, calque, russian_loan, variant, form. Mention the secondary problem in `notes`.
- If the sense is unclear to you even after looking it up, leave `correct` blank and start `notes` with `UNSURE:`. Do not guess.
- A literal rendering of the English lemma's parts that Kazakh speakers do not use is `calque`. A descriptive paraphrase of the gloss, or a garbled or untranslated string, is `other`. Judge against the gloss, not the lemma's wording.

## Clarifications recorded after dev judging (2026-10-31)
These document rules applied during dev judging. They were stated in chat while judging but were not yet written in this file.
- A word narrower (hyponym) or broader (hypernym) than the gloss is incorrect: category wrong_sense, with "narrower" or "broader" in notes. Only words that can stand for the whole concept are correct.
- All acceptable synonyms are correct (1). Missing synonyms are not penalized.
- Variant rule applied: variants counted incorrect, category variant.