# `pipeline/` — the scripts

Run them from the **repo root**, not from this folder; every path constant inside is written
relative to the root (`reviews/…`, `sources/…`, `work/…`).

## Order

| # | script | in | out | time |
| --- | --- | --- | --- | --- |
| 1 | `wx_extract.py` | the 2.6 GB Wiktextract dump | `sources/wiktionary-nouns.csv` (819,280 English nouns) | ~7 min |
| 2 | `wx_pos.py` | the same dump | `sources/wiktionary-pos.csv` (1,385,953 words, POS inventory) | ~7 min |
| 3 | `pos_freq.py` | nltk corpora + `sources/ud/` | `sources/pos-dominance.csv` (61,957 types) | ~1 min |
| 4 | `wx_join.py` | OEWN + 1 + reviews | `work/sen-v3.csv` and its queues | ~2 min |
| 5 | `rank_gaps.py` | the gaps queue + 1,2,3 | rewrites `work/sen-v3.csv.gaps.csv` | ~1 min |
| 6 | `scowl_pos.py` | `sources/scowl/scowl-pre.txt` (downloaded) | `sources/scowl-pos.csv` (70,865 words at size ≤ 70) | seconds |
| 7 | `scowl_gaps.py` | the gaps queue + 6 | `work/gaps-scowl-{noun,nonnoun,absent}.csv` | seconds |
| 8 | `apply_scowl.py` | `work/sen-v3.csv` + 6 + reviews | `work/sen-v4.csv` | ~1 min |
| 9 | `release_sen.py` | `work/sen-v4.csv` | `sen-<date>.csv` in the root | seconds |

Steps 1–3 and 6 only need re-running when their source changes. Steps 4, 5, 7, 8, 9 are the loop
you run after every review.

## What each one is for

**`wx_extract.py`** — streams the dump (never loads it), keeps `lang_code == en` + `pos == noun`,
and records countability, plural-only, inflected-form, region tags and spelling-variant links. The
variant link is the delicate part: it comes from `alt_of` when Wiktionary provides one and from a
regex over the gloss when it does not. `VARIANT_RE` is anchored to the *start* of the gloss and
bounded, because "A **form of** argument" and "the acute **form of a** disorder" are prose, not
lexicography — an earlier unanchored version put 796 words down as variants of `a`.

**`wx_pos.py`** — the same dump, but keeping *every* English entry rather than only nouns, so the
pipeline can see that `oh` is an interjection with one noun sense and `de` is a prefix. Only the
closed classes are trusted to exclude anything: Wiktionary is generous with obsolete verb senses
(`fridge` is verb:5/noun:2), so "more verb senses than noun senses" is not evidence.

**`pos_freq.py`** — dominant part of speech over 2.26M tagged tokens, with proper nouns kept
separate from common ones. Answers the one question a dictionary cannot: not *can this be a noun*
but *is it one in practice*. Six nltk corpora (brown, conll2000, treebank, masc_tagged,
switchboard, nps_chat) plus the UD English EWT and GUM treebanks, which it downloads into
`sources/ud/` on first run and reuses after. UD rows are read by their **Penn** tag (column 5), not
the universal one, so a single `coarse()` covers every source.

**`wx_join.py`** — the core. Also reads `reviews/manual-entry.csv` and every `reviews/domains/*.csv`
sheet: they add the words no source has, and a `noun` verdict there overrides every exclusion rule,
including the frequency cutoff and the missing-from-Wiktionary rule. Domain sheets are read after
the general one, may carry a `marks` column, and their note is used as the definition in preference
to Wiktionary's gloss — see `reviews/README.md` for why those two differ.

Joins OEWN against the Wiktionary table, applies every rule and every human ruling, decides
`recommended` / `excluded_because` / `suggest_instead` / `marks`, and writes the review queues. Longest file here and the one to read first; the module docstring lists every
output.

**`rank_gaps.py`** — takes the "Wiktionary has it, OEWN does not" queue and sorts it into something
a human can review top-to-bottom: flags closed-class words, corpus-attested non-nouns, and glosses
that describe themselves ("Initialism of …", "Clipping of …"). Every row is kept; flagged ones just
sort lower.

**`scowl_pos.py`** — parses the SCOWL / English Speller Database master file into a fourth POS
opinion: part of speech, commonality band, per-dialect spelling codes and inflections, for 70,865
words. Defaults to `--max-size 70`, which is both the quality line (above it is ENABLE2K and
crossword filler) and the licence line (a generated list larger than 80 carries the UKACD
copyright). Ships its own `--self-check`; run it after any change, because two of the three parser
bugs it has had were silent — dropped homographs and a doublet crediting `color`'s inflections to
`colour`.

**`scowl_gaps.py`** — splits the 5,694-row gaps queue by what SCOWL says: 1,473 confirmed nouns
(worth reading, ranked by SCOWL band then zipf), 543 that SCOWL calls an adjective or verb, and
3,678 SCOWL has never heard of at size ≤ 70. Rules nothing; it decides reading order.

**`apply_scowl.py`** — the widening stage, and the only one that changes what is playable without a
human ruling. Two things: it opens the `obscure` band (9,670 rows flip to allowed and carry
`marks = "obscure"`, because a frequency floor is a game decision, not a dictionary one), and it
adds SCOWL's 12,148 unseen nouns, ruling each by the policies already in `wx_join.py` — British
spelling, closed-class function word, Wiktionary non-noun, plural-only, inflected. Every added word
gets a definition, from Wiktionary's first sense or from `reviews/scowl-glosses.csv`, and asserts
it: no allowed row may ship without one.

**`release_sen.py`** — cuts the game-facing file: 16 columns of the 40-odd, renamed to what they
mean at the point of use, with integrity assertions (no duplicate nouns, no allowed row carrying a
reason, no rejected row without one).

**`probe.py`** — runs a domain word list against a release and reports what is missing, with what
the upstream sources know about each miss, which is what decides the fix. Not part of the build; run
it when you suspect a subject area is thin. `reviews/bioinformatics-probe.csv` is the second one: 124 of 210
playable, 83 absent, and after `domains/bioinformatics.csv`, 205 of 210 with nothing absent.
`reviews/electronics-probe.csv` was the first: it
started at 216 of 285 playable and found both the 33-word electronics hole and the whole initialism
problem. It asserts its input is single lowercase words with no duplicates, because a probe that
silently drops rows reports a coverage number that is too good — that assertion caught a duplicate
in the first list written for it.

**`build_variant_review.py`** — one-shot sheet builder for the doublet review. Kept because the
next queue will want the same treatment: pre-fill a verdict from evidence, hand the sheet to a
human, read the corrected file back in.

**`build_name_list.py`** — builds `sources/names-lowercase.csv` from OEWN names plus a Wikipedia
list. Rarely re-run.

**`threshold_bands.py`**, **`enrich.py`** — analysis one-offs kept for the record. `threshold_bands`
is where the `zipf >= 2.0` cutoff came from; it is not part of the build.

**`fixture.jsonl`** / **`fixtureexpectedoutput.csv`** — a 13-line dump fixture for `wx_extract.py`.
Run it after touching the regex:

```bash
python pipeline/wx_extract.py pipeline/fixture.jsonl /tmp/fx.csv
```

`colour`, `gaol` and `aluminium` must come out with the right `variant_of`; `cat` and `water` with
none.

## Two traps

* **Backslashes in regexes.** Several of these files were edited through shells that collapse `\`;
  a `\b` became a literal backspace character more than once and silently broke a pattern. If a
  regex stops matching for no reason, `grep -c $'\x08' file.py` first.
* **A missing review file is not an error.** Every reader treats one as "no rulings", so a deleted
  or renamed sheet shows up only as counts moving. Check `reviews/` after any re-run.
