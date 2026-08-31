# SEN — the Single English Nouns dataset

**`sen-2026-09-01.csv` — 61,524 rows, 51,881 of them playable.**

A word list for a word-chain game, built from Open English WordNet 2025, the full Wiktextract dump
of English Wiktionary and the SCOWL / English Speller Database, with a corpus of 2.26M POS-tagged
tokens as a fourth opinion, 3,647 hand rulings on top, and 282 words typed in by hand because no
source had them.

Its one unusual design decision: **rejected words stay in the file.** A game that only ships the
playable words can say "not in the database" and nothing more. This one can say *why* a word is not
allowed and *what to play instead* — 9,643 rejected rows, every one with a reason, 2,089 of them
naming a replacement.

    allowed=False  reason="british/commonwealth spelling variant"   suggest_instead="plow"
    allowed=False  reason="adjective (not a noun)"
    allowed=False  reason="spelling variant of another word (reviewed)"  suggest_instead="yogurt"

The second decision: **doubt is written down, not acted on.** The `marks` column carries what the
dataset could not resolve, and it is present on *allowed* rows too (19,069 of them). Whether
`bollocks` (possible plural) or `federal` (usually an adjective) is a legal answer is a **game**
rule. The dataset refuses to decide it for you and tells you what it knows instead.

The third, added in this release: **frequency is not a verdict.** 9,670 words were rejected for the
single reason that `wordfreq` scores them 0.0. They are real nouns that passed every other test and
then hit a floor — which is a game's call about how wide its vocabulary should be, not a fact about
English. They are now playable, tiered `OBSCURE`, and carry `marks = "obscure"`. Cut them out with
one filter if you want a friendly list.

## Columns

| column | meaning |
| --- | --- |
| `noun` | the word, lowercase |
| `start`, `end`, `length` | first letter, last letter, length — what a chain game indexes on |
| `zipf` | Zipf frequency (`wordfreq`), 0–8 |
| `tier` | `CORE` · `COMMON` · `FAMILIAR` · `UNCOMMON` · `RARE` · `OBSCURE`, banded from `zipf` |
| `allowed` | play it or don't |
| `reason` | why not. Never empty when `allowed` is false |
| `marks` | `; `-separated doubts; see below. Empty for most words |
| `suggest_instead` | the word to play instead, when one exists |
| `pos_tags`, `lemma` | lemminflect's reading (`NOUN;VERB`, base form) |
| `is_plural` | the word is a listed plural of another entry |
| `lexfile` | WordNet lexicographer file (`noun.animal`, `noun.artifact`, …) |
| `definition` | one gloss, for showing the player |
| `source` | `oewn2025` (42,586) · `scowl` (12,147) · `pos-auto` (4,333) · `gaps-review` (1,551) · `manual-entry` (142) · `domain:initialisms` (99) · `domain:bioinformatics` (84) · `domain:electronics` (37) |

## Playable words, by tier

| tier | words |
| --- | ---: |
| CORE | 615 |
| COMMON | 2,804 |
| FAMILIAR | 7,308 |
| UNCOMMON | 11,736 |
| RARE | 13,028 |
| OBSCURE | 15,732 |

Three cuts, and the file is built so that picking one is a filter, not a rebuild:

* **friendly** — `tier` in CORE/COMMON/FAMILIAR: **10,727 words**. Barely moved this release, which
  is the point: almost everything added landed below it.
* **defensible** — everything except OBSCURE: **35,491 words**.
* **extra-wide** — all **51,223**, including the OBSCURE band. `wordfreq` has never seen these,
  which for `tokenomics` and `lootbox` means the frequency table is older than the word, and for
  `ophicleide` and `quitrent` means the word is genuinely rare. Both are in the same band and both
  carry `marks = "obscure"`; the dataset does not pretend to tell them apart.

## Why words are rejected

| reason | rows |
| --- | ---: |
| verb (not a noun) | 3,070 |
| spelling variant of another word (reviewed) | 1,628 |
| adjective (not a noun) | 1,163 |
| proper noun or other non-noun (reviewed) | 1,011 |
| inflected form (Wiktionary) | 916 |
| british/commonwealth spelling variant | 707 |
| not in Wiktionary | 411 |
| not a usable common noun (reviewed) | 98 |
| initialism, not a common noun (reviewed) | 99 |
| plural-only (Wiktionary) | 219 |
| adjective (reviewed) | 155 |
| function word (not a noun) | 18 |
| adjective/verb, adjective/adverb, adverb, … | 261 |

`obscure` is gone from this table. It was the largest reason in the previous release, at 9,670
rows, and it was never really a reason — see the third design decision above.

`function word (not a noun)` is new and small: SCOWL tags `all`, `if`, `she` and `you` as nouns,
because English does nominalise them ("the whys and hows") and Wiktionary duly glosses them.
`rank_gaps.py` already carried the closed list of determiners, pronouns, conjunctions,
prepositions and auxiliaries for exactly this; `apply_scowl.py` reuses it.

## Marks

| mark | rows |
| --- | ---: |
| obscure | 16,226 |
| verb (not a noun) | 3,039 |
| possible name | 2,169 |
| spelling variant of *word* | 1,831 |
| manual - not in Wiktionary, is it a real noun? | 1,378 |
| possible abbreviation or clipping | 1,357 |
| adjective (not a noun) | 1,061 |
| usually a verb (corpus) | 875 |
| usually an adjective (corpus) | 872 |
| UK/Commonwealth spelling | 758 |
| possible plural | 617 |
| usually a name (corpus) | 443 |
| also a verb (SCOWL) | 252 |
| also an adjective (SCOWL) | 214 |
| noun in SCOWL, not in Wiktionary | 167 |
| not in Wiktionary, glossed by hand | 112 |
| initialism | 100 |

`usually an X (corpus)` is a frequency fact, not a dictionary one: `political` and `federal` do have
noun senses, and 0 of 339 `political` tokens in a tagged corpus are nouns.

`also a verb (SCOWL)` and `also an adjective (SCOWL)` are the multi-usage marks: the word is in as a
noun and SCOWL lists another reading for it too. Whether `barre` or `powerdown` is a legal answer
when the player means the verb is, again, a game rule.

`obscure` is the widest mark and the one to filter on first: 16,226 rows, every one of them a word
`wordfreq` scores at 0.0.

## Initialisms

`usb`, `led`, `pcb`, `dna`, `gps`, `html`, `mosfet` and 92 others are **rejected, lowercase, and
marked `initialism`**, with the expansion as the definition:

    noun=usb  allowed=False  marks="initialism"  definition="Universal Serial Bus."
              reason="initialism, not a common noun (reviewed)"

An initialism is not a common noun and is not a legal answer, but a game that only knows "not in
the database" cannot say so. The rows exist to be rejected with their expansion attached. Words
that finished becoming ordinary words -- `laser`, `radar`, `scuba` -- are in the dictionaries as
nouns and are playable from those rows, not from this sheet.

Three things made the list a decision rather than an oversight. SEN is a lowercase dataset and the
sources file these words under their capitals (`LED`, `PCB`, `MOSFET`), so nothing in the join ever
saw them. Blanket case-folding is not the fix: 8,751 uppercase-only Wiktionary noun entries have no
lowercase row here and the tail of that list is `AABNCP` and `AACOMS`. And English gives no rule for
where the line falls — `laser` and `radar` finished becoming words, `usb` is most of the way there,
`aabncp` never will be.

So the list is hand-written, in `reviews/domains/initialisms.csv`, and the mark is there for a
game that wants to allow them anyway. The definition is the expansion because a player shown
Wiktionary's own gloss for lowercase `dna` reads "Alternative form of DNA.", which helps nobody.

## A short word can be two things

`ide` is a freshwater fish of the Cyprinidae. It is also an initialism for Integrated Development
Environment, and on that basis it was excluded as "not a usable common noun" — while still carrying
the fish gloss, so the game could neither play it nor explain it. `wat` (a Buddhist temple), `sai`
(a martial-arts weapon), `zhou` (rice porridge), `xu` (a Vietnamese coin), `al` (the Indian mulberry)
and 155 others were lost the same way.

The rule, in one line: **an abbreviation ruling may not exclude a word that carries a definition of
its own.** Such a word stays playable, keeps its definition, and gains the
`possible abbreviation or clipping` mark. 155 rows were rescued this way, and
`not a usable common noun (reviewed)` fell from 252 rejections to 98.

An `initialism` verdict is the exception, for the same reason `abbreviation-expansions.csv` is: the
row's definition IS the expansion, so there is nothing to rescue.

The "unless" cannot be automated. `ft` is glossed "a linear unit of length equal to 12 inches",
which *is* what the abbreviation stands for; `al` is glossed "the Indian mulberry", which is not.
Both are short words with a dictionary gloss and no string test tells them apart. So the exceptions
are listed by hand in `reviews/abbreviation-expansions.csv` — 56 unit symbols, letter names and
clippings glossed by the word they clip — and everything else is protected by default. That default
is deliberate: the failure being fixed is a real noun going missing, where a wrongly kept
abbreviation is only a marked row a game can filter.

## Regional spellings

American is the kept form; the British spelling stays as a rejected row pointing at it. That is a
project decision, applied consistently: `color` plays, `colour` does not and says `suggest_instead
= color`. 2,336 rows work this way — 1,628 from the hand review of Wiktionary's doublet list, 230
caught by region tags, and 478 new ones caught by SCOWL's per-dialect spelling codes, which state
the fact outright rather than inferring it from a suffix:

    A Cv DV: color  <n>      standard American, a variant in Canadian and Australian
    B C D:   colour <n>      standard British, Canadian and Australian

That is also the check that validated the existing policy: of the 230 rows the old region-tag rule
rejected as British, SCOWL independently agrees with 202 and has never heard of 19.

## Rebuilding

The dump is ~2.6 GB and lives outside the repo (re-downloadable from kaikki.org). From the repo
root:

```bash
DUMP=~/Downloads/raw-wiktextract-data.jsonl.gz
python pipeline/wx_extract.py "$DUMP" sources/wiktionary-nouns.csv    # ~7 min
python pipeline/wx_pos.py     "$DUMP" sources/wiktionary-pos.csv      # ~7 min
python pipeline/pos_freq.py                                           # ~1 min
python pipeline/wx_join.py sources/oewn2025nounsv2.1.csv sources/wiktionary-nouns.csv work/sen-v3.csv
python pipeline/rank_gaps.py work/sen-v3.csv.gaps.csv sources/wiktionary-nouns.csv reviews/modernvocabularyprobe.csv
python pipeline/scowl_pos.py                          # downloads scowl-pre.txt on first run
python pipeline/scowl_gaps.py                         # splits the gaps queue three ways
python pipeline/apply_scowl.py                        # sen-v3 -> sen-v4: obscure opened, SCOWL added
python pipeline/release_sen.py work/sen-v4.csv        # writes sen-<today>.csv
```

Needs `pandas`, `wordfreq`, `lemminflect`, `nltk` (brown, conll2000, treebank, masc_tagged,
switchboard, nps_chat, universal_tagset), `orjson`. `pos_freq.py` also downloads the UD English
EWT and GUM treebanks into `sources/ud/` on its first run (~46 MB, once).

## Layout

| folder | what is in it |
| --- | --- |
| `pipeline/` | the scripts, in dependency order. See `pipeline/README.md` |
| `reviews/` | human rulings — the authority, never regenerated |
| `sources/` | derived source tables (big, all rebuildable) |
| `work/` | the working dataset and the open review queues |
| `docs/` | the full build report and the next-session plan |
| `references/` | background reading on the chain problem itself, not on the dataset |

## Where the words come from

| source | rows | what it contributes |
| --- | ---: | --- |
| Open English WordNet 2025 | 42,586 | the spine: senses, lexfiles, glosses |
| SCOWL / English Speller Database | 12,148 | a curated dictionary aggregate (12dicts, ENABLE2K, COCA) with POS, commonality bands and per-dialect spelling codes. New in this release |
| `pos-auto` | 4,334 | words recovered by the POS pass |
| `gaps-review` | 1,551 | ruled by hand out of the Wiktionary-only queue |
| `manual-entry` | 142 | typed in because no source had them |
| `domain:bioinformatics` | 84 | one subject area, probed and ruled sheet by sheet |
| `domain:initialisms` | 98 | `reviews/domains/initialisms.csv` — see below |
| `domain:electronics` | 37 | `reviews/domains/electronics.csv` |

SCOWL is cut at **size ≤ 70**, which is both where its quality falls off and where its licence
changes; `sources/README.md` has the copyright notice and the reasoning. The released
`hunspell-en_US-large-*.zip` is *not* a substitute — it is 76,958 base forms with affix flags and no
part of speech at all, so it cannot tell a noun from a verb.

## Where it could get better

1. **`work/gaps-scowl-noun.csv` — 1,473 candidates two curated sources both call nouns.** The
   replacement for the old 4,582-row queue: same source file, sorted by whether a second dictionary
   agrees. Densest at the top, where SCOWL's bands 35–50 put 256 rows.
2. **`work/gaps-scowl-nonnoun.csv` — 543 rows SCOWL calls something else**, naming what. Rulable in
   bulk rather than one at a time.
3. **`work/sen-v3.csv.unknown.csv` — 1,378 WordNet nouns Wiktionary has never heard of.** All
   excluded, all marked `manual - not in Wiktionary, is it a real noun?`. SCOWL confirms 239 and has
   never heard of 1,117, which corroborates leaving them out.
4. **Spelling variants are still rejected, not marked.** The project keeps American and rejects
   British with a `suggest_instead`, and this release applied that policy to 478 new SCOWL words
   rather than changing it. If the game would rather accept `colour` and show a mark, that is a
   one-line change in `apply_scowl.py` plus a re-run of `wx_join.py` — but it is a policy change and
   was deliberately not made here.
5. **The corpus can mark only 11% of the playable list, and the gap widened this release.** It is
   about marks, not membership — `blockchain` and `cryptocurrency` are playable, they just have no
   tagged tokens to derive a `usually a verb (corpus)` mark from. Adding SCOWL and opening the
   obscure band tripled the playable list without adding one tagged token.
   **See `sources/README.md`, "The corpus tables and their limits", for the numbers.**
6. **The abbreviation mark is noisy.** It fires on `ad`, `gym`, `laser` and `pc` as well as on `st`
   and `mp`, because Wiktionary's "short for …" covers both clippings that became ordinary words
   and ones that did not. Advisory only; do not promote it to an exclusion without a second signal.
7. **`variant_of` still comes from the first sense that yields one**, which for `plough` is
   `snowplough`. `variant_sense` records which sense it came from, so it can be filtered — nothing
   downstream does yet.
8. **No plural forms.** The dataset is singular nouns by design. A game that wants to accept
   plurals has to generate them (`lemminflect` does this well) and decide what to do with the 616
   `possible plural` marks.
9. **`definition` is one gloss, sometimes a bad one.** It is the first sense, which for a word with
   an obscure first sense reads oddly to a player. Picking the most frequent sense needs
   sense-frequency data WordNet does not ship.
