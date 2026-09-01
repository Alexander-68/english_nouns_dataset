# `sources/` — derived source tables

Everything here is **rebuildable** and none of it is a human decision. Safe to delete if disk is
tight; regenerating costs about fifteen minutes plus a 2.6 GB download.

The dump itself is deliberately **not** in the repo. Get it from
`https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz` (~2.6 GB gzipped, ~22.9 GB
uncompressed — the scripts read the `.gz` directly and never need the expanded form).

| file | rows | built by | what it is |
| --- | ---: | --- | --- |
| `wiktionary-nouns.csv` | 819,280 | `wx_extract.py` | English **noun** entries: countability, plural-only, inflected-form, region tags, spelling-variant links, first gloss |
| `wiktionary-pos.csv` | 1,385,953 | `wx_pos.py` | **every** English word's POS inventory with sense counts (`intj:10;noun:3`) plus an abbreviation flag |
| `pos-dominance.csv` | 61,957 | `pos_freq.py` | dominant POS over 2.26M tagged tokens, proper nouns counted separately |
| `ud/` | 6 files | `pos_freq.py` (`fetch_ud`) | UD English EWT + GUM `.conllu`, downloaded on first run |
| `scowl-pos.csv` | 70,865 | `scowl_pos.py` | SCOWL/ESDB at size ≤ 70: POS with sense counts, noun subtypes, commonality band, dialect and variant codes, inflections. 45,268 of the rows are common nouns |
| `scowl/scowl-pre.txt` | 246,039 lines | downloaded | the SCOWL master file, from `en-wl/wordlist` branch `v2`. Re-downloadable; see the licence note below |
| `names-lowercase.csv` | — | `build_name_list.py` | OEWN names ∪ a Wikipedia name list, with an "also an OEWN common noun" column |
| `oewn2025nounsv2.1.csv` | 47,656 | `oewn2025/` | the starting dataset: Open English WordNet 2025 nouns with frequency, tier and lexfile |
| `oewn2025/` | — | — | the OEWN parse: `parse_oewn.py`, `build_csv.py` and their outputs, plus `READMEoewn2025.md` |
| `wordchain2024/` | — | — | the previous generation of this project, kept for reference: 2024 noun lists, a name list, the audit PDF and design notes |

## Why two Wiktionary tables

`wiktionary-nouns.csv` keeps only `pos == "noun"` entries, which is right for the join and wrong for
everything else: it cannot see that `oh` is mostly an interjection, `de` a prefix and `ve` a
pronoun fragment, because those words also carry one noun sense each and nothing else survives the
filter. `wiktionary-pos.csv` is the second pass that keeps the rest.

## The corpus tables and their limits

**The corpus-coverage numbers live here and nowhere else.** The root README and
`docs/NEXT-SESSION-PLAN.md` point at this section rather than restating it; they used to
carry their own copies and all three drifted out of date together.

`pos-dominance.csv` comes from six nltk corpora — `brown` (1961, balanced American English),
`conll2000` and `treebank` (Wall Street Journal, 1989), `masc_tagged` (blogs, email and essays,
2000s), `switchboard` (telephone speech) and `nps_chat` (2006) — plus the UD English **EWT** and
**GUM** treebanks in `ud/`, which are web text from the 2010s on. Together 2.26M tokens, 62k types.
It answers *is this word a noun in practice* — `political` has a real noun sense and 0 of its 339
corpus tokens are nouns.

The last three columns — `n_low`, `noun_low`, `propn_low` — count only the tokens **written
lowercase**. The table is keyed on the lowercased type, so `Ray` and `ray` share a row and `propn`
measures the name, not the word; the lowercase columns are what tell the two apart. Evidence FOR a
common noun only: sentence-initial nouns are capitalised, so a zero there proves nothing.

It is no longer only pre-1990 American prose, which is what made it silent on `email`, `website`
and `browser` — those now have 281, 126 and 22 tagged tokens. It is still **small relative to the
dataset**, and more so every time the dataset grows: of 51,241 playable words, 34,702 have no tagged
token at all, and 45,557 sit under the 10-token floor `CORPUS_MARK_MIN_N` requires, so only 5,684
words (11%) can carry a corpus mark. `smartphone` and `selfie` have 2 tokens each — real, but under
the floor; `blockchain` and `cryptocurrency` have none.

Coverage is about **marks, not membership**: all four of those words are playable. A word the corpus
has never seen produces **no mark**, never a wrong one.

The `ud/` files are fetched from raw.githubusercontent.com on the first run of `pos_freq.py` and
reused after; delete the folder to force a refresh.

## SCOWL, and why the cut is at size 70

`scowl-pre.txt` is the master file of the English Speller Database (formerly SCOWL), the source
behind the hunspell and aspell English dictionaries. It is the only source here that is a *curated
dictionary aggregate* — 12dicts, ENABLE2K, COCA — rather than a crowd edit history, a WordNet
release or a parse of running text, and it is the only one that ships a part of speech, a
commonality band and per-dialect spelling codes on the same line.

Do **not** substitute the released `hunspell-en_US-large-*.zip` for it. That file is this file with
everything useful stripped: 76,958 base forms with affix flags (`S` plural, `M` possessive, `G`
`-ing`) and no part of speech at all, so `slam/S` and `tomboy/MS` are indistinguishable. It cannot
answer "is this a noun".

`scowl_pos.py` cuts at **size 70** by default. Two independent reasons land in the same place:

* **Quality.** Above 70 is ENABLE2K and the UK Advanced Cryptics Dictionary — 30k words like
  `assuefaction`, `cunette` and `costeaning`.
* **Licence.** From SCOWL's `Copyright` file: *"If you are using a generated word list larger than
  80, the copyright after '=== UKACD' applies."* At or below 70 only Kevin Atkinson's notice
  applies, which asks that the copyright notice travel with any word list derived from it:

      Copyright 2000-2026 by Kevin Atkinson

      Permission to use, copy, modify, distribute, and sell any part of the English
      Speller Database (ESDB, previously known as SCOWLv2), or word lists created
      from it, is hereby granted without fee, provided that the above copyright
      notice appears in all copies and that both the above copyright notice and
      this notice appear in supporting documentation. Kevin Atkinson makes no
      representations about the suitability of this database for any purpose. It
      is provided "as is" without express or implied warranty.

  Australian English (`D` code) carries an additional notice; the dataset keeps American spellings,
  so it does not rely on that data. `--max-size 85` is available and prints a warning.
