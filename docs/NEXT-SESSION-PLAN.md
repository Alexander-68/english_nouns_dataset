# Next session — plan

Written 2026-08-30 at the end of the session that added SCOWL and opened the obscure band.
Background is in `WIKTEXTRACT-JOIN-REPORT.md`, last section. This file is the operating plan only.

## State

**The current release is `sen-2026-08-30.csv` — 60,896 rows, 51,086 allowed, 2,089 of the rejected
rows naming the word to play instead.** Playable vocabulary went from 30,114 to 51,086 and nothing
that was playable stopped being playable.

Three changes got it there. Two are in the new `apply_scowl.py` stage:

1. **The obscure band opened.** 9,670 rows whose only rejection reason was `obscure` — a `wordfreq`
   score of 0.0 — are now allowed, tiered OBSCURE, marked `obscure`. A frequency floor is a game's
   call about vocabulary width, not a fact about English, and the mark mechanism already existed to
   hand that call back to the game.
2. **SCOWL / the English Speller Database was added** as a fourth source: 12,148 new words, 11,166
   of them playable. It is a curated dictionary aggregate with a part of speech, a commonality band
   and per-dialect spelling codes on every line — see `sources/README.md` for the size-70 cut and
   its licence.

The third is `reviews/domains/`, a folder of subject-area hand-entry sheets read by `wx_join.py`
alongside `manual-entry.csv`. Two exist:

3. **`domains/initialisms.csv`, 99 rows.** `usb`, `led`, `pcb`, `dna`, `gps`, `html`, `mosfet` are
   rejected with `initialism, not a common noun (reviewed)`, marked `initialism`, defined by their
   expansion (2026-08-30: they were briefly playable; an initialism is not a noun). They were invisible
   before because SEN is lowercase and the sources file them under capitals, and case-folding
   wholesale is not an option: 8,751 uppercase-only Wiktionary entries have no lowercase row and the
   tail is `AABNCP`. The line has to be drawn by hand, so it is.
   **`domains/electronics.csv`, 37 rows.** Found by `pipeline/probe.py`.

The three cuts a game can take are now `FAMILIAR+` (10,628), everything-but-OBSCURE (35,375) and
all 51,086.

## Probing for holes

`pipeline/probe.py` runs a domain word list against a release and reports the misses with what each
upstream source knows about them. The first probe, `reviews/electronics-probe.csv` (285 words), went
from **216 playable to 282** across this session and found both gaps above. Worth writing one for
any field the game will lean on — medicine, cooking, sport, music, construction — before assuming
coverage. A subject area is not covered because the totals are large.

## Rebuild from scratch

```bash
# the dump lives outside the repo; ~2.6 GB, re-downloadable from kaikki.org
DUMP=~/Downloads/raw-wiktextract-data.jsonl.gz
python wx_extract.py "$DUMP" wiktionary-nouns.csv     # ~7 min, English nouns only
python wx_pos.py     "$DUMP" wiktionary-pos.csv       # ~7 min, POS of every English word
python pos_freq.py   pos-dominance.csv                # seconds, needs nltk brown/conll2000/treebank
python build_variant_review.py                        # only to re-cut the doublet sheet
python wx_join.py    oewn2025nounsv2.1.csv wiktionary-nouns.csv sen-v3.csv
python rank_gaps.py  sen-v3.csv.gaps.csv wiktionary-nouns.csv modernvocabularyprobe.csv
python release_sen.py sen-v3.csv                      # writes sen-<today>.csv
```

Requires `pandas`, `wordfreq`, `lemminflect`, `nltk`, `orjson`. The network is not restricted.

## What the game consumes

`sen-<date>.csv`, 16 columns. Three of them carry the whole design:

* `allowed` — play it or don't.
* `reason` — why not, for every one of the 17,748 rejected rows. Never empty when `allowed` is false.
* `marks` — what the dataset still doubts, `; `-separated, and **present on allowed rows too**
  (2,645 of them). `possible plural`, `possible name`, `usually an adjective (corpus)`,
  `UK/Commonwealth spelling`, `possible abbreviation or clipping`,
  `manual - not in Wiktionary, is it a real noun?`.

A mark is not a rejection. Whether `bollocks` (possible plural) or `federal` (usually an adjective)
is a legal answer is a **game** rule; the dataset refuses to decide it and says what it knows.

## Human decisions — never regenerated, all committed

| file | rows | what it rules |
| --- | ---: | --- |
| `gaps_verdicts.csv` | 1,092 | `noun` / `name` / `verb` / `adj` / `noise`, for words NOT in the dataset |
| `sen_word_verdicts.csv` | 63 | the same verdicts for words that ARE in it |
| `sen-v3.csv.variants-reviewed.csv` | 2,509 | `variant` / `reverse` / `plural` / `unrelated` per doublet |
| `manual_reviews.csv` | 3,479 | the log: date, sheet, item, verdict, reason |
| `sen-v3.csv.variants_ing-reviewed.csv` | 99 | which side of an `-ing` doublet is British |
| `sen-v3.csv.uk_reviewed.csv` | 157 | words wrongly UK-flagged; keep them |
| `sen-v3.csv.name_suspect-reviewed.csv` | 462 | confirmed non-nouns |
| `modernvocabularyprobe.csv` | — | human-vetted modern vocabulary |

Every one of these is read by `wx_join.py` or `rank_gaps.py`, and a missing file is not an error —
a deleted one shows up only as counts moving. Check them after any re-run.

## Open queues, largest first

The old "4,582 below zipf 3.0" framing is retired. `scowl_gaps.py` re-cuts the same 5,694-row queue
by whether a second curated dictionary agrees, which is a far better reading order than frequency:

1. **`gaps-scowl-noun.csv` — 1,473.** SCOWL lists the word with a common-noun sense, so two
   independent curated sources agree. Ranked by SCOWL band then zipf; the top 256 rows are bands
   35–50 and are the densest vocabulary left anywhere in the repo. **Start here.**
2. **`gaps-scowl-nonnoun.csv` — 543.** SCOWL calls it an adjective (342), a verb (99), an
   abbreviation (33) or a function word. These can be ruled in bulk: the sheet already names the
   part of speech, so the review is confirming rather than deciding.
3. **`gaps-scowl-absent.csv` — 3,678.** Absent from SCOWL at size ≤ 70. Names, slang, typos, dump
   noise. Skim for anything modern that both sources are simply too old for; do not read it row by
   row.
4. **`unknown.csv` — 1,378 nouns Wiktionary has never heard of.** SCOWL confirms 239 and has never
   heard of 1,117. The corroboration is strong enough that this queue can stay closed unless the
   game asks for WordNet's specialist tail.

**`variants.csv` is closed** — all 2,509 pairs ruled, see the report.

## The one policy question left open

Spelling variants are still **rejected with a `suggest_instead`**, not admitted with a mark. This
release applied the existing policy to 478 new SCOWL words rather than changing it, because the
policy is documented in the root README and 1,836 shipped rows already depend on it.

If the game would rather accept `colour` and show `marks = "UK/Commonwealth spelling"`, the change
is small and belongs in one place — the British branch of `build_rows()` in `apply_scowl.py`, plus
the equivalent in `wx_join.py` — but it is a project decision, not a bug, and should be made
deliberately.

## Known limits, honestly

* `pos-dominance.csv` can mark only 11% of the playable list, and the share fell this release
  because the dataset tripled and the corpus did not grow at all. Governs marks, not membership.
  Numbers in `sources/README.md`, "The corpus tables and their limits" — the one place they are
  maintained.
* SCOWL's parser has had three silent bugs, all of them shape bugs in the source format rather than
  logic errors: dropped `{sense}` homographs, subtypes unioned across senses, and `-` continuation
  lines credited to the wrong side of an interleaved doublet. `scowl_pos.py --self-check` asserts
  against all three plus a floor on the entry count. Run it after touching the parser or taking a
  new SCOWL release.
* The Wiktionary abbreviation flag is advisory because it fires on `ad`, `gym`, `laser` and `pc` as
  well as on `st` and `mp`. Do not promote it to an exclusion without a second signal.
* `wx_extract.py` still takes `variant_of` from the first sense that yields one, which for `plough`
  is `snowplough`. `variant_sense` now records which sense that was, so it can be filtered.
