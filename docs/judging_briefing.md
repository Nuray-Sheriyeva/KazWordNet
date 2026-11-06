# Judging briefing (one page)

**Task.** You get a sheet of Kazakh candidate words for English WordNet synsets. For each row, decide whether the Kazakh word is a correct word for that meaning.

**Columns.** `synset_id`, `pos` (n noun, v verb, a/s adjective), `lemma_en` (English word that produced the candidate; only a hint), `gloss` (the meaning; judge against this), `lemma_kk` (the word to judge). Fill in `correct`, `error_category` and, if needed, `notes`.

**How to judge.**
- `correct = 1` if a native speaker accepts the word, or an established phrase, as a normal, standard-spelling, citation-form expression of the meaning in the gloss and POS. All acceptable synonyms get 1; a missing synonym is not a problem.
- `correct = 0` otherwise, with exactly one `error_category`. If several apply, pick the first in this order: `other`, `wrong_sense`, `calque`, `russian_loan`, `variant`, `form`.
  - `wrong_sense`: the word means something else, or is narrower or broader than the gloss.
  - `calque`: word-for-word copy of the English that no one says in Kazakh.
  - `russian_loan`: a Russian loanword where a native Kazakh word exists.
  - `variant`: non-standard spelling, dialectal or obsolete form.
  - `form`: wrong citation form (verbs end in -у/-ю).
  - `other`: anything else, including paraphrases that are not established expressions.
- Multiword answers are correct only if they are established expressions.
- If you truly cannot decide, leave `correct` blank and write `UNSURE:` and a short reason in `notes`.

**Rules of the process.** Judge on your own. Do not look at anyone else's labels and do not discuss rows with the other judge until both of you have finished. Do not guess where the words came from. Judge each row by itself; several rows share one gloss on purpose. Save the sheet as tab-separated text (TSV, UTF-8).

Full rules: `docs/judging_guidelines.md`.