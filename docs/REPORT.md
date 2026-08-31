# Wiktextract join — run report

Run date: 2026-08-28. Supersedes `RUNBOOK.md` (deleted; its instructions are folded in below,
with two of its claims corrected).

## What was processed, and how

| step       | command                                                                                                     | outcome                                                                                 |
| ---------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| deps       | `pip install pandas wordfreq orjson`                                                                        | installed; `orjson` was picked up by the extractor                                      |
| smoke test | `python wx_extract.py fixture.jsonl fx.csv`                                                                 | 13 lines, 9 entries → 8 words; `diff` vs `fixtureexpectedoutput.csv` **byte-identical** |
| download   | `curl -L -C - -o raw-wiktextract-data.jsonl.gz https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz` | 2,826,618,017 bytes, size-verified against the `Content-Length`                         |
| extract    | `python wx_extract.py raw-wiktextract-data.jsonl.gz wiktionary-nouns.csv`                                   | 10,806,865 lines → 819,280 distinct nouns, ~2 min                                       |
| join       | `python wx_join.py oewn2025nounsv2.1.csv wiktionary-nouns.csv sen-v3.csv`                                   | run twice — before and after the variant-filter fix below                               |

Filenames on disk have no hyphens or dots (`oewn2025nounsv2.1.csv`, `modernvocabularyprobe.csv`,
`fixtureexpectedoutput.csv`), unlike the names used in the RUNBOOK and the task description.

### One operational trap worth remembering

A `nohup`-detached `curl` **survives** the harness reporting the background task as "completed".
A first detached download kept running invisibly while a second `curl -C -` resumed onto the same
path; two writers produced a 3,091,327,298-byte corrupt file (vs 2,826,618,017 expected). Fix:
never `nohup` the download, and always assert the byte count before consuming the file.

## Results

### Extract

```
lines read      : 10,806,865
English nouns   : 829,383 entries -> 819,280 distinct words
json parser     : orjson
```

Expectation was "several hundred thousand"; 819,280 clears the 100k red-flag floor by 8x.

### Join

```
SEN rows              : 42,586
Wiktionary rows       : 819,280
matched in Wiktionary : 41,208 / 42,586 (96.8%)     [expected >80%]

plural-only flagged   : 329
inflected forms found : 761
uncountable only      : 5,483
spelling doublets     : 3,089   -> sen-v3.csv.variants.csv
gap candidates        : 5,783   -> sen-v3.csv.gaps.csv

RECOMMENDED           : 31,077 (73.0%)
excluded, by reason:
    obscure                      10,614
    inflected form (Wiktionary)     761
    plural-only (Wiktionary)        134
```

The `recommended` / `excluded_because` numbers were unchanged by the fix — it only touches the
gaps file. Nothing is deleted from `sen-v3.csv`; every exclusion keeps its evidence columns.

### Fix applied to `wx_join.py`

The gaps filter dropped every candidate carrying a `variant_of` value:

```python
& (wx['variant_of'] == '')
```

That is wrong when the canonical form is not itself a dataset row — the word is then discarded
outright rather than deduplicated against something present, and the concept is lost. Changed to:

```python
& (~wx['variant_of'].isin(have - {''}))   # drop only if canonical is itself a dataset row
```

`have - {''}` guards the degenerate case where an empty noun string exists in the dataset, which
would otherwise drop every non-variant candidate.

Effect: gap candidates **4,873 → 5,783** (+910 recovered). Of the 1,606 zipf≥2.5 candidates the old
filter dropped, 910 had a canonical absent from the dataset.

### Modern-vocabulary probe — 12 of 17

`modernvocabularyprobe.csv` has 68 words; 40 present in both, 11 added by OEWN 2025, **17 missing
from OEWN**. This matches the RUNBOOK's "51/68 on the spot check".

Before the fix 8 of 17 surfaced in `gaps.csv`; after, **12**:
`app` `bitcoin` `wifi` `selfie` `broadband` `blockchain` `hoodie` `ecommerce` `triathlon` `pilates`
`heatwave` `smartwatch`.

Recovered by the fix (all were spacing/hyphenation/capitalisation doublets whose canonical is
multi-token or capitalised, so absent from the dataset):

| word      | variant_of   | zipf |
| --------- | ------------ | ---- |
| wifi      | `Wi-Fi`      | 3.94 |
| ecommerce | `e-commerce` | 3.30 |
| pilates   | `Pilates`    | 3.00 |
| heatwave  | `heat wave`  | 2.85 |

**Still missing — 5, all below the `zipf >= 2.5` cut, none of them a bug:**

| word         | zipf |
| ------------ | ---- |
| earbud       | 2.36 |
| telehealth   | 2.33 |
| chatbot      | 2.30 |
| podcaster    | 2.24 |
| microplastic | 1.61 |

All five are present in `wiktionary-nouns.csv`, are not inflected forms, and are not plural-only.
They are excluded solely by the frequency threshold.

## Next steps — TODO

1. **`gaps.csv` is dominated by function words and is not yet usable as a review queue.**
   Top 30 by zipf: `and, is, that, you, it, on, this, be, as, not, but, or, an, all, they, me, if,
   just, up, what, when, were, who, her, would, she, how, them, other, only`. Wiktionary carries
   obscure noun senses for these, OEWN does not, and zipf ranking floats them to the top — burying
   the modern vocabulary the file exists to surface. Rank or filter by something POS-aware
   (dominant-POS share, or `n_senses` weighted against the word's non-noun frequency) before
   reviewing. Distribution today: 691 rows at zipf≥4, 2,355 at 3–4, 2,737 at 2.5–3.
2. **Decide the frequency threshold deliberately.** `zipf >= 2.5` is what costs the 5 probe words.
   Dropping to 2.0 recovers `earbud`/`telehealth`/`chatbot`/`podcaster` but not `microplastic`
   (1.61), and widens the function-word problem in step 1. Fix step 1 first, then retune.
3. **Review `variants.csv` (3,089 rows) by hand — it is a review queue, not an answer.**
   `variant_of` is a regex over the gloss, not a structured field: `colour` and `gaol` carry no
   `alt_of` at all, so the relationship is inferred from text like "Commonwealth and Ireland
   standard spelling of color." Expect false positives on glosses such as "a spelling of the
   name…". Use it to pick a canonical side for the `-isation`/`-ization` and `-our`/`-or` pairs.
4. **Re-derive the verdict rule if wanted, without re-running anything.** `sen-v3.csv` keeps all
   evidence columns, so a different `recommended` rule is a pandas expression over the existing
   file — the 10,614 `obscure` exclusions in particular are a tier judgement, not Wiktionary data.
5. **The 1,378 SEN nouns Wiktionary does not know (3.2%)** were not examined. Worth a glance —
   they are either OEWN-specific technical entries or candidates for removal.

## Files

| file                            | size   | what it is                                                              |
| ------------------------------- | ------ | ----------------------------------------------------------------------- |
| `wiktionary-nouns.csv`          | 65 MB  | 819,280 English nouns extracted from the dump                           |
| `sen-v3.csv`                    | 8.4 MB | v2.1 + 9 `wikt_*` evidence columns + `recommended` + `excluded_because` |
| `sen-v3.csv.gaps.csv`           | 352 KB | 5,783 candidate additions, frequency ranked — see TODO 1                |
| `sen-v3.csv.variants.csv`       | 125 KB | 3,089 spelling doublets — see TODO 3                                    |
| `sen-v3.csv.unknown.csv`        | 190 KB | 1,378 SEN nouns Wiktionary has no entry for — all excluded, audit trail  |
| `names-lowercase.csv`           | 320 KB | 11,516 lower-cased proper nouns, Namenet + Wikipedia — see name-list follow-up |
| `sen-2026-08-29.csv`            | 6.4 MB | **the release**: 47,636 rows, 15 game-facing columns                    |
| `NEXT-SESSION-PLAN.md`          | 5 KB   | operating plan for the fixed-regex re-extraction                        |
| `threshold_bands.py`            | 5 KB   | zipf cutoff band analysis for `gaps.csv` — see TODO 2 follow-up          |
| `raw-wiktextract-data.jsonl.gz` | 2.6 GB | source dump, re-downloadable; safe to delete                            |

## Follow-up — POS-aware ranking of gaps.csv (2026-08-28, later same day)

Addresses TODO 1 above. `rank_gaps.py` re-ranks `sen-v3.csv.gaps.csv` in place — no rows deleted,
same "keep the evidence" rule as `sen-v3.csv` itself.

Three flags, each backed by a closed/citable list rather than a judgement call, computed fully
offline (no corpus or POS-tagger download was attempted at the time — see the correction at the end
of this report; the egress assumption behind that choice was wrong):

1. **Closed-class function words** (determiners, pronouns, conjunctions, prepositions,
   auxiliary/modal verbs, function adverbs — closed by definition) — 67 words.
2. **Irregular verb past/past-participle forms** (went, seen, bought, written, ...) — 24 words.
   Unmarked forms (cut, set, read, put, ...) deliberately excluded since the same spelling is also
   a perfectly good independent noun.
3. **Case variants of proper nouns** — a word whose Wiktionary `variant_of` is Title-case (india ->
   "India ...", indian -> "Indian") — 195 words, after excluding ALL-CAPS canonicals (DNA, CEO,
   GIF, LOL, COVID-19), which are acronyms/initialisms, not proper nouns, and stay in the queue.

Validated against `modernvocabularyprobe.csv`, the project's own human-vetted modern-word list: the
first pass wrongly caught `wifi` (-> "Wi-Fi") and `pilates` (-> "Pilates") under flag 3 — genericised
trademarks, not proper nouns. Fixed by trusting the probe file as ground truth where it disagrees
with the auto-flag. Re-run confirms clean: all 12 probe words present in gaps.csv now rank as
`likely_noun`.

Result: 286 / 5,783 flagged (67 function words, 24 irregular-verb forms, 195 proper-noun/acronym
case variants), 5,497 unflagged and still ranked by zipf. The old top-30 (`and, is, that, you, it,
on, this, be, as, not, ...`) is gone from the front of the queue.

**What this does not fix, by design:** words whose only Wiktionary noun sense is a nominalised
adjective (`political` -> "a political agent", `federal` -> "a federal agent", `hot` -> "a hot
meal", `international` -> "someone capped for their country") or an informal verb-derived noun
(`tell` -> poker tell, `ask` -> a business ask, `send` -> a climbing send). These are genuinely
attested, defensible noun senses, not errors — nominal adjective and verb-noun conversion is
productive in English — so excluding them would be the wrong call, not a safe one, exactly like the
irregular-verb unmarked-forms exclusion above. They stay in the queue, ranked by zipf, for a human
to accept or reject case by case. There is no closed list for "words that are adjectives" the way
there is for pronouns or irregular verbs, so this residue can't be resolved the same way — it needs
either a real POS-frequency source (SUBTLEX, already on the resumption-plan roadmap) or manual review.

New columns on `sen-v3.csv.gaps.csv`: `variant_of`, `flag_reason` (empty if unflagged),
`likely_noun`. File re-sorted by `(likely_noun desc, zipf desc)` so it reads top-to-bottom as a
review queue, per the original ask.

## Follow-up — exclude British/Commonwealth spelling variants, keep American (2026-08-28)

`recommended` now has a fifth exclusion criterion. A noun is excluded as a British/Commonwealth
spelling variant — American kept — when:

  (a) Wiktionary editorially tags it `british` or `commonwealth` (a deliberate human tag on the
      Wiktionary entry itself, trusted outright — e.g. `grey` -> gray, `mould`/`modelling` ->
      mold/modeling, `manoeuvre` -> maneuver), or
  (b) its `regions` tag is UK/British-only (no other region mixed in, and specifically not `US`)
      **and** it matches a known BrE -> AmE spelling correspondence in `UK_US_SUFFIXES`
      (`wx_join.py`): `-isation/-ization`, `-iser/-izer`, `-isable/-izable`, `-yse/-yze`,
      `-yser/-yzer`, `-ogue/-og`, `-ence/-ense`, `-our/-or`, `-re/-er`, plus an `ae`/`oe` -> `e`
      digraph reduction (encyclopaedia -> encyclopedia, haemorrhage -> hemorrhage).

A mirror case is also handled: some plain headwords carry no tag of their own but are pointed at
by an editorially-tagged American row — e.g. `tranquillity` and `sceptre` are untagged, but
`tranquility` and `scepter` each say "American spelling of ...". Those get excluded too, and the
American word that superseded them is recorded in the new `wikt_american_equivalent` column.

**Why not just trust every UK-region-tagged `variant_of` row:** `variant_of` is a regex over the
gloss text (see the join section above), and region tags alone don't distinguish a real spelling
doublet from an extraction artifact. Spot-checking the raw UK-tagged rows turned up genuine
non-spelling noise sitting right next to the real pairs — `beach` -> "bitch", `lye` -> "lie",
`prawn` -> "porn", `frame` -> "knowledge", `lady`/`sister`/`tosh` -> "address" — Wiktionary
glosses that the regex latched onto for reasons unrelated to spelling. Requiring a recognised
suffix pattern (or an explicit editorial tag) keeps the auto-exclusion to cases with real evidence
behind them, rather than trusting the region tag alone.

**Result:** 174 excluded (164 direction-A, 10 direction-B), keeping the American spelling in every
pair — `colour`→color, `organisation`-family (84 words, the single biggest group) →-ization,
`haem-`/`oe-` medical terms (28) → hem-/e-, `grey`→gray, `armour`/`behaviour`/`favour`/`flavour`
→ -or, `centre`-style words → -er, `tranquillity`/`sceptre`/`accoutrement` → the American forms.

**What's deliberately left alone:** 121 UK-region-tagged rows that don't match any recognised
suffix pattern go to the new `sen-v3.csv.uk_review.csv` instead of being auto-excluded. Some are
real British/American pairs the suffix list doesn't cover — irregular ones like `kerb`/curb,
`cypher`/cipher, `programme`/program, doubled-consonant pairs like `counselling`/counseling —
and some are the same kind of regex-extraction noise described above (`set`→"sett" is an unrelated
word, not a spelling variant). Same "review queue, not an answer" rule as `variants.csv` and the
earlier `gaps.csv` pass: keep the evidence, let a human decide, never silently delete. `wx_join.py`'s
docstring and inline comments carry the full rationale for anyone re-running the pipeline later.

## Follow-up — zipf threshold band analysis for `gaps.csv` (2026-08-29)

Addresses TODO 2 above, which was explicitly blocked on TODO 1 ("fix step 1 first, then retune").
TODO 1 shipped, so the retune is unblocked. `threshold_bands.py` rebuilds the pre-threshold
candidate pool exactly as `wx_join.py` builds it — same four filters, same `wordfreq` scores — then
applies `rank_gaps.py`'s flags (imported, not duplicated) and reports what each cutoff buys.
It writes nothing: picking the number is a human call, the script just supplies the numbers.

Candidate pool with any `zipf > 0`: **31,740** words. Cumulative view:

| cutoff | rows   | likely_noun | flagged | flag % | probe hits | recovered vs 2.5                                |
| ------ | ------ | ----------- | ------- | ------ | ---------- | ----------------------------------------------- |
| 3.00   | 3,046  | 2,843       | 203     | 6.7%   | 11/68      | —                                               |
| 2.50   | 5,783  | 5,497       | 286     | 4.9%   | 12/68      | — (today's cutoff)                              |
| 2.25   | 7,820  | 7,487       | 333     | 4.3%   | 15/68      | chatbot, earbud, telehealth                     |
| 2.00   | 10,590 | 10,200      | 390     | 3.7%   | 16/68      | + podcaster                                     |
| 1.50   | 18,649 | 18,122      | 527     | 2.8%   | 17/68      | + microplastic                                  |
| 1.00   | 31,740 | 31,085      | 655     | 2.1%   | 17/68      | —                                               |

The function-word worry from TODO 2 ("widens the function-word problem in step 1") turns out to be
backwards now that the flags exist: closed-class words are *concentrated at the top*, so the flagged
share **falls** monotonically as the cutoff drops (6.7% → 2.1%). Function words are a high-frequency
phenomenon by definition — there are only ~67 of them and they all sit above zipf 3. Lowering the
cutoff does not admit more of them; it admits rarer words. So the flag rate is not the thing that
should decide this, and the real cost of going lower has to be read off the words themselves.

**Reading the newly admitted words band by band** (30-word samples per band, in the script output):

* **2.25–2.50** (1,990 likely_noun) — recognisable vocabulary: `kendo`, `cron`, `creationist`,
  `supergroup`, `masterplan`, `seasonality`, `lenticular`, `flyby`, `powerplay`. Usable.
* **2.00–2.25** (2,713) — still mostly real (`didgeridoo`, `cisgender`, `gaydar`, `halfling`,
  `treeline`, `compensator`, `contralateral`, `hairstyling`), with the first visible misspellings
  and fragments (`dinning`, `creat`, `cous`). Marginal but net positive.
* **1.50–2.00** (7,922) — the turn. Misspellings arrive in force (`amature`, `superheros`) alongside
  narrow technical terms (`methyltransferase`, `laminin`, `paratransit`, `trivalent`). 7,922 rows to
  review for one probe word.
* **1.00–1.50** (12,963) — specialist and clinical vocabulary almost throughout (`adapalene`,
  `octreotide`, `leukoencephalopathy`, `seroconversion`, `lognormal`, `subharmonic`). Not Word Chain
  answers.

**Recommendation: `zipf >= 2.0`.** It recovers 4 of the 5 probe words the current cutoff loses
(`chatbot`, `earbud`, `telehealth`, `podcaster`) for +4,807 rows, and stops right before the band
where misspellings and clinical jargon start to dominate. `microplastic` (zipf 1.61) stays out: it
alone costs another 8,059 rows, which is the wrong trade — better recovered by hand from the probe
file than by moving the cutoff.

**A residue this analysis surfaced, unrelated to the cutoff:** lower-cased proper nouns leak into
every band — `waterhouse`, `garnett`, `tait`, `luce`, `pimlico`, `westland`, `ghulam`, `wakeman`,
`francisca`, `alannah`. `rank_gaps.py`'s proper-noun flag only fires when Wiktionary's `variant_of`
is Title-case, and these carry no `variant_of` at all, so nothing catches them. It is the same shape
of problem as the nominalised-adjective residue already documented above — needs a name list or a
capitalisation-frequency source, not a threshold change.

**Applied (same day).** `wx_join.py` now cuts at `ZIPF_MIN = 2.0`, and the pipeline was re-run:
`wx_join.py`, then `rank_gaps.py` to restore the ranking columns. Counts came out exactly as the
band table predicted — 10,590 candidates, 10,200 `likely_noun`, 390 flagged (299 proper-noun case
variants, 67 function words, 24 irregular verb forms). `sen-v3.csv`, `variants.csv` and
`uk_review.csv` are byte-identical to the previous run, confirming the join is deterministic and
that the cutoff touches nothing but the gap queue.

`microplastic` (zipf 1.61) was appended to `gaps.csv` by hand, bringing it to 10,591 rows / 10,201
`likely_noun`. It is on `modernvocabularyprobe.csv` and reaching it by cutoff would have cost another
8,059 rows; all 17 probe words now in the queue rank as `likely_noun`. It is a queue entry like any
other — a human still accepts or rejects it. Note that a re-run of `wx_join.py` will drop it again,
since it sits below the cutoff by design.

**51 of the 68 probe words are absent from the candidate pool at any cutoff** (`algorithm`, `laptop`,
`podcast`, `vaccine`, ...) — they are already in the dataset or were filtered upstream by the
inflected/plural-only/variant tests. Not a threshold question, and worth remembering when reading the
`probe hits` column above: 68 is the whole probe file, not the number in play.

## Follow-up — `unknown.csv`, the SEN nouns Wiktionary has never heard of (2026-08-29)

Addresses TODO 5. `wx_join.py` now writes a fifth file, `<out>.unknown.csv` — the inverse of
`gaps.csv`: the **1,378** SEN nouns (3.2%) with no Wiktionary entry at all. It carries the OEWN-side
evidence for each (`zipf`, `tier`, `senses`, `lexfile`, `register`, `domain`, `in_wn30`,
`also_proper_noun`, `recommended`, `excluded_because`, `definition`), sorted by zipf descending, and
decides nothing — same review-queue rule as `variants.csv` and `uk_review.csv`.

**The file splits cleanly in two, and only one half needs a human.**

**967 rows (70%) are already excluded** as OBSCURE, and they are exactly the rows with `zipf == 0` —
words `wordfreq` has never seen either. Two independent sources not knowing a word is agreement, not
a conflict. This is OEWN's specialist tail: botanical and zoological binomials (`wingstem`, `dioon`,
`potamogale`, `compsognathus`, `diapheromera`, `neritina`), medical terms (`uratemia`,
`hyperpiesia`, `lipochondrodystrophy`, `photoretinitis`), and loanwords (`razbliuto`, `taichichuan`,
`ianfu`). `noun.plant` alone accounts for 269 of the 1,378. Nothing to do — the `recommended` rule
already handles them.

**411 rows are `recommended = True`** — currently valid Word Chain answers that no Wiktionary entry
backs. That is the reviewable list, and it sorts into four groups:

| group                     | n   | examples                                                             |
| ------------------------- | --- | -------------------------------------------------------------------- |
| `-ing` nominalisations    | 135 | leaving, causing, reducing, replacing, governing, solving, defining   |
| unit symbols, ≤2 chars    | 18  | km, cm, kg, cd, sr, dm, cl, hm, lm, hg, dg, hl, plus d, b, r, x, z, am |
| `-ed` participles         | 14  | wounded, defeated, pursued, damned, chased, baffled, bereaved, maimed |
| everything else           | 244 | much, few, lost, million, billion, thousand, sixteen, nowadays, kosher |

The first three groups are the strong removal candidates, and the reason Wiktionary lacks them is
informative rather than a gap in Wiktionary: it does not carry `leaving` or `wounded` as standalone
noun lemmas because they are productive derivations, and it does not carry `km` as an English noun
because it is a unit symbol, not a word. OEWN lists them; both frequency sources and Wiktionary
decline to treat them as nouns.

The 244-row remainder is genuinely mixed and needs eyes: real words (`kosher`, `halal`, `haggle`,
`kneel`, `timid`, `cautious`, `anatomical`, `audiovisual`), numerals (`million`, `thousand`,
`sixteen`, `seventy`), and a familiar face — **lower-cased proper nouns** (`sherlock`, `waterloo`,
`marseille`, `jonah`, `adonis`, `sodom`, `malacca`, `laguna`, `ramona`, `geordie`, `siamese`,
`benedictine`). That is the same residue flagged in the threshold band analysis above, arriving from
the opposite direction: `rank_gaps.py` can only catch proper nouns via a Title-case `variant_of`, and
these have no Wiktionary row at all to carry one. Third independent sighting of that problem — a name
list would resolve it in `gaps.csv`, in `unknown.csv`, and in the dataset's own `also_proper_noun`
column at once.

### Also fixed: the hand-added `microplastic` no longer washes away

The previous follow-up warned that re-running `wx_join.py` would drop the hand-appended
`microplastic` row. Generating `unknown.csv` required a re-run, so it did — immediately. Rather than
re-append it a second time, the cutoff now exempts any word listed in `modernvocabularyprobe.csv`
(`PROBE_PATH`): a human already vouched for those words, which outranks a frequency score. Only
`microplastic` (zipf 1.61) actually needs the exemption today, and the run prints which words it
rescued. `gaps.csv` is back to 10,591 rows / 17 probe words, now reproducibly rather than by hand,
and a missing probe file is not an error.

## Follow-up — the proper-noun name list (2026-08-29)

Lower-cased proper nouns had been flagged three times as unresolved residue. `build_name_list.py`
now assembles one from sources **already in this repo** — no download, which matters because this
environment's egress policy blocks the OEWN XML and every corpus:

  * `oewn2025/oewn2025names.csv` — Open English Namenet, the proper-noun half of the OEWN 2025
    split (25,905 entries, 10,640 single alphabetic tokens). Same source the dataset's
    `also_proper_noun` column comes from.
  * `wordchain2024/names-wiki.csv` — the 2024 project's Wikipedia-derived list (6,555 entries,
    6,486 single tokens).

Output `names-lowercase.csv`: **11,516** names, 5,610 in both sources, with `in_namenet`,
`in_wikipedia` and `also_oewn_noun` kept per row. ALL-CAPS entries (AARP, ABB, DNA) are excluded by
requiring Title-case, the same call `rank_gaps.py` already makes for `variant_of`.

`also_oewn_noun` (812 rows: `bacon`, `atlas`, `angel`, `adonis`, `badger`, `acre`, `army`) is
deliberately **not** applied as a filter inside the builder. It means opposite things to the two
consumers — for `gaps.csv` it is a reason to distrust the match, while every `unknown.csv` row is an
OEWN noun by construction, so filtering on it there would empty the file. The flag ships; each
caller decides.

### It is a sort tier, not an exclusion

The list finds 466 new suspects among the `likely_noun` rows in `gaps.csv`, and the sample shows
immediately why it cannot be trusted as a flag: `washington`, `canada`, `texas`, `peter`, `jones`,
`manchester` are names in essentially every use, but sitting right beside them are `nice` (Nice),
`tell` (William Tell), `teach` (Blackbeard), `begin` (Menachem Begin), `recent`, `handy`, `martial`
— ordinary adjectives and verbs that merely happen to also name a place or a person. Telling those
apart needs a POS or capitalisation-frequency source, and none is available offline. The name list
raises recall; it cannot supply the precision.

So a name-list hit does **not** set `flag_reason` and does **not** clear `likely_noun`. Burying
`tell` and `nice` among the function words would contradict the standing decision that nominalised
adjectives and verb-derived nouns stay in the queue for a human. Instead `gaps.csv` gains a
`name_suspect` column and sorts by `(likely_noun desc, name_suspect asc, zipf desc)` — a labelled
band directly beneath the clean rows. Visible, ranked, marked, nothing hidden and nothing deleted.

Queue today: **9,735 clean · 466 name_suspect · 390 flagged**. All 17 probe words remain clean.

### An idea that was tested and rejected

Before settling on the name list, a second signal was tried: pattern-matching Wiktionary's
`first_gloss` for the formulaic phrasing of name entries ("a surname", "a male given name", "a city
in ..."). It failed — only **6** of the 466 name-list hits had a matching gloss, because `gaps.csv`
stores the *first* noun sense, which for `washington` is the board-game synonym, not the name. The
matches it produced on its own were regex noise (`username` matching "name", ordinary definitions
matching "in the United States"). Dropped rather than shipped as a weak signal.

### Honest limit: it does nothing for `unknown.csv`

Zero of the 1,378 `unknown.csv` rows match. Every one is an OEWN common noun by construction, so the
Namenet half is already represented there by the existing `also_proper_noun` column — which catches
13 of the 18 proper-noun leaks spotted by eye (`troy`, `jonah`, `waterloo`, `marseille`, `siamese`,
`adonis`, `sodom`, `malacca`, `geordie`, `benedictine`, `bartlett`, `newmarket`, `magdalen`... ).
The 5 it misses — `sherlock`, `laguna`, `ramona`, `cochin`, `eldorado` — are in **neither** source.
Neither list is a general gazetteer, and no offline source here is. For `unknown.csv`, use
`also_proper_noun`; closing the remainder needs a real gazetteer, which is a download away and
currently blocked.

## Decision — nouns unknown to Wiktionary are excluded from the dataset (2026-08-29)

Project decision following the `unknown.csv` review above: **a noun with no Wiktionary entry at all
does not belong in the final SEN dataset.** `recommended` gains a sixth criterion, `wikt_known`, and
`unknown.csv` changes role — it is no longer a pending review queue but the audit trail of what this
decision removed.

This is a judgement call, recorded as one rather than dressed up as a derived rule. The evidence
behind it is in the follow-up above: 967 of the 1,378 rows (70%) were already excluded as OBSCURE
and are exactly the rows `wordfreq` scores at zipf 0, and the 411 that were still `recommended` are
dominated by 135 `-ing` nominalisations (`leaving`, `causing`, `governing`), 18 unit symbols and
single letters (`km`, `kg`, `cd`, `x`, `z`), and 14 `-ed` participles (`wounded`, `defeated`). Two
independent sources declining to treat a string as a noun is agreement, not a gap.

**Effect: `recommended` falls from 30,947 (72.7%) to 30,536 (71.7%)** — exactly the 411 rows, since
the other 967 were already out. Every other exclusion count is unchanged.

The new `not in Wiktionary` reason is masked **first** in the `excluded_because` chain, so every
other criterion overrides it. A word that is both unknown and OBSCURE still reads as `obscure`, the
existing counts stay comparable across runs, and the new label appears only on rows that had no
other reason. `unknown.csv` shows the split cleanly: 967 `obscure`, 411 `not in Wiktionary`, 0 still
recommended.

**Reversible, like every other verdict here.** No row was deleted from `sen-v3.csv`; `wikt_known` and
all the other evidence columns are still on every row, so dropping the criterion is a one-line edit
to `bad` in `wx_join.py`, or a pandas expression over the existing file. The 244-row mixed remainder
noted in the review — `kosher`, `halal`, `haggle`, `kneel`, `audiovisual` and the lower-cased proper
nouns — goes out with the rest under this decision; if any of those are wanted back later,
`unknown.csv` is where to find them.

## Applied — the manual `uk_review.csv` pass (2026-08-29)

`sen-v3.csv.uk_reviewed.csv` is the outcome of the human pass over the UK review queue: a plain
list of 137 rows / **136 distinct nouns** that belong in the dataset (`address` appeared twice).
`wx_join.py` now reads it as `UK_REVIEWED_PATH` and gives it a `human_kept` column.

**Nothing was appended.** All 136 were already rows in `sen-v3.csv` — the file names words the
dataset has, not new vocabulary — so "avoiding duplicates" resolved to two dedupes: the repeated
`address` inside the file, and the whole list against the existing dataset. The operation that
mattered was the verdict, not the insert.

**The keep-list overrides every automatic exclusion**, applied last so it wins, on the principle
`PROBE_PATH` already established for the gaps cutoff: a human who looked at the word outranks a
derived rule. 126 of the 136 were already `recommended`; **10 exclusions were overridden**:

  * `obscure` (8) — `abstractor`, `apophthegm`, `dueller`, `peewit`, `plowwoman`, `plowwright`,
    `shote`, `welsher`
  * `inflected form (Wiktionary)` (2) — `beach`, `brief`

`beach` is a satisfying one to see here: it is the exact example this report has used since the join
section for gloss-regex noise (`beach` -> "bitch"). The manual pass reached the same conclusion
independently.

**Effect: `recommended` 30,536 -> 30,546 (71.7%)**, exactly the 10. Excluded counts move only where
those rows left: `obscure` 10,571 -> 10,563, `inflected form` 760 -> 758.

**The queue shrank to match.** `uk_review.csv` now excludes `human_kept` rows and drops from 121 to
**64** — a review queue should mean "still needs a decision", not "was once a candidate". The 64
remaining are the British spellings whose American counterparts appear in the reviewed list
(`plough`/`plow`, `chequer`/`checker`, `connexion`/`connection`, `sceptic`/`skeptic`,
`programme`/`program`, `gramme`/`gram`, `waggon`, `yoghurt`, `sulphide`, `moulding`, ...).

**Deliberately not inferred:** listing only the American side is *suggestive* that the British side
should be excluded, but the reviewed file carries no verdict column, so that reading is not applied.
Those 64 stay in the queue awaiting an explicit call rather than being excluded on an inference —
the same rule this pipeline follows everywhere else. A `verdict` column on the reviewed file would
let both directions be applied in one pass.

## Applied — second pass over the UK residue: exclude British, keep American (2026-08-29)

Project decision: of the 64 rows left in `uk_review.csv`, exclude the British spelling and keep the
American. Applying it literally would have been a mistake, and the file says why — **21 of the 64
are not British spellings at all.** They are the gloss-regex noise documented since the join
section, where `variant_of` points at an unrelated word: `dead` -> "deadlift", `lob` -> "fraud",
`skittles` -> "chess", `t` -> "time", `y` -> "year", `do` -> "hairdo", `melt` -> "milt", `darter` ->
"daughter". A blanket exclusion would have deleted `dead`, `do`, `melt`, `par`, `lit`, `mag`, `mod`
and `frank` from the dataset.

So the decision is applied through named rules, and **43 of the 64 are excluded**.

### A similarity score was tried first and rejected

The obvious approach — `difflib` ratio between the word and its canonical — fails at every
threshold, because BrE/AmE distance and semantic distance are unrelated quantities. At 0.80 it
accepted `broach`/"brooch", `frank`/"franc" and `chapiter`/"chapter" (distinct words, all ≥ 0.80)
while rejecting `plough`/"plow", `chequer`/"checker", `pedlar`/"peddler" and `snowplough`/"snowplow"
(real spellings, all < 0.80). No cutoff separates the two sets. Dropped in favour of a closed list,
the same call made for `UK_US_SUFFIXES`, `CLOSED_CLASS` and `IRREGULAR_VERB_FORMS`.

### What replaced it

Two new tables in `wx_join.py`, applied **only** to the `uk_review` residue and deliberately kept
out of `UK_US_SUFFIXES`: several are broad enough (`ll->l`, `ou->o`) to misfire on the full dataset,
and the primary rule's 174 exclusions are settled. On 64 hand-inspected rows whose American side a
human has already vouched for, they are safe.

  * `UK_US_RESIDUE_SUBS` — `ough->ow`, `quer->cker`, `xion->ction`, `centre->center`, `mme->m`,
    `our->or`, `gg->g`, `ph->f`, `sc->sk`, `gh->g`, `ll->l`, `ou->o`. Substitution may occur
    anywhere in the word, not only at the suffix: `coloured` -> `colored`, `ploughman` -> `plowman`.
  * `UK_US_IRREGULAR` — 19 doublets with no derivable pattern: `beigel`/bagel, `cypher`/cipher,
    `enquiry`/inquiry, `fount`/font, `furore`/furor, `gipsy`/gypsy, `gramme`/gram, `hullo`/hello,
    `kiddy`/kiddie, `macintosh`/mackintosh, `pedlar`/peddler, `pewit`/peewit, `plough`/plow,
    `soya`/soy, `speciality`/specialty, `swathe`/swath, `tranquilliser`/tranquilizer, `whizz`/whiz,
    `yack`/yak.

Every exclusion records which rule fired, in the new `wikt_uk_residue_rule` column — traceable to a
named correspondence, never to a score.

**One case forced an extra rule.** `plough` — the flagship example — did not match, because the
gloss regex had set its canonical to `snowplough` rather than `plow`, while `ploughman`,
`ploughwoman`, `ploughwright` and `snowplough` all resolved normally. Leaving `plough` in while
excluding its own compounds would have been absurd, so when the hand-curated table names an American
form and that form is itself a dataset row, the table now outranks the bad `variant_of`. That is the
43rd exclusion.

**Effect:** `british/commonwealth spelling variant` 174 -> 217; `recommended` 30,546 -> 30,508
(71.6%). Excluded: `beigel, centrefold, chequer, chequerboard, coloured, connexion, cypher,
deflexion, discolouration, enquiry, fount, furore, gipsy, gramme, harbourage, hullo, humourist,
inflexion, kiddy, macintosh, moulding, pedlar, pewit, plough, ploughman, ploughwoman, ploughwright,
programme, reflexion, sceptic, scepticism, snowplough, soya, speciality, sulphide, swathe,
tranquilliser, waggon, waggoner, whizz, woollen, yack, yoghurt`.

**`uk_review.csv` is now 21 rows** — and it has changed character completely. It no longer holds
unresolved spelling questions; it holds gloss-regex noise: `broach, chapiter, darter, dead, delf,
do, frank, ki, lat, lats, lit, lob, mag, melt, mod, panto, par, rime, skittles, t, y`. These are
ordinary words whose `variant_of` extraction is simply wrong. They need no spelling decision — the
correct action for all 21 is to ignore the `variant_of` value, which is what leaving them
unexcluded already does. The queue is effectively closed.

## Principle change — the dataset is a rejection-reason lexicon (2026-08-29)

Design decision, and it changes what `sen-v3.csv` *is*. Until now every pass narrowed the file
toward "nouns only". That turned out to be the wrong target: it is too aggressive, and it throws
away the information a game most needs at the moment a player types a word.

**A word being absent and a word being disallowed are different facts, and only the second can be
explained.** A filtered list can answer a rejected word with "not in the database". A dataset that
keeps rejected words with their reason can answer:

    not allowed — this is most probably a name
    not allowed — British spelling, use `plow` instead

So rejected words are kept as rows carrying the reason, and reviewed proper nouns are **added** to
the dataset from the gaps queue rather than discarded. Two columns carry it: `excluded_because`
names the reason, `suggest_instead` names the replacement where one exists.

### What changed

**462 reviewed name suspects joined the dataset.** `sen-v3.csv.name_suspect-reviewed.csv` is the
outcome of the manual pass over the 466-row band — a human confirmed 462 are not common nouns
(people, places, trade names, plus some adjectives and verbs) and deleted 4 that are: `freon`,
`penicillium`, `plasticine`, `typhon`. The 462 are appended with `recommended = False`,
`excluded_because = 'proper noun or other non-noun (reviewed)'`, `name_suspect = True`, and their
Wiktionary evidence (`senses`, `definition`, `zipf`, `tier`). OEWN-only columns are empty because
these words were never in OEWN — a new `source` column says `gaps-name-review` rather than
`oewn2025`, since the file's rows are no longer all OEWN nouns.

`end_pressure` is left at 0 for them rather than recomputed: it is demand ÷ supply over the
*playable* list, these rows are never playable, and recomputing would shift every existing value.

**`suggest_instead` is populated for all 217 British/Commonwealth variants** — `colour` -> `color`,
`programme` -> `program`, `plough` -> `plow`. Resolution order matters: the curated
`UK_US_IRREGULAR` table is consulted first, because it is right exactly where the gloss regex is
wrong (`plough`'s extracted canonical was `snowplough`, not `plow`), then `variant_of`, then
`wikt_american_equivalent`. A suggestion is only emitted if the replacement is itself a dataset row
and is not the word itself.

### Effect

| | before | after |
| --- | ---: | ---: |
| rows | 42,586 | **43,048** |
| recommended | 30,508 (71.6%) | **30,508 (70.9%)** |
| gaps.csv candidates | 10,591 | **10,113** |
| name_suspect band | 466 | **4** |

`recommended` is unchanged in absolute terms — every added row is excluded by construction, so the
playable list did not move; only the denominator did. `gaps.csv` drops the 462 that became rows,
plus 16 more whose `variant_of` canonical is now a dataset row and so no longer qualifies as a gap.

The 4 words kept by the review stay in the `name_suspect` band, which is correct: they are
genericised trade names and genus names — the same shape as `wifi` and `pilates` in
`modernvocabularyprobe.csv`. The band is a sort tier, not an exclusion, so they remain live
candidates ranked below the clean rows.

`uk_review.csv` moved 21 -> 22: adding 462 words to the dataset made one more `variant_of` canonical
resolvable (`lido`). It is regex noise like the other 21, and needs no decision.

### The same treatment is now available for any other rejection class

`excluded_because` already distinguishes `obscure`, `inflected form (Wiktionary)`,
`plural-only (Wiktionary)`, `not in Wiktionary`, `british/commonwealth spelling variant` and
`proper noun or other non-noun (reviewed)`. Each is a different sentence a game can show. No message
templates are stored here on purpose — the columns are structured, and phrasing belongs to the game,
not to the dataset.

## Principle — part-of-speech overlap is tagged, not judged (2026-08-29)

Project rule, extending the rejection-reason principle above: **a noun that can be — or originally
was — an adjective or a verb gets marked, not excluded.** Whether `endangering`, `channeling`,
`political` or `hot` is a legal answer is a *game* question, decided by the game rule, not a data
question decided here. The dataset's job is to say what the word also is.

`rank_gaps.py` gains a `pos_overlap` column. **2,943 of the 10,113 gap candidates carry a tag:**

| tag | rows |
| --- | ---: |
| `verb form (-ing)` | 1,986 |
| `adjective-like` | 877 |
| `verb form (-ed)` | 78 |

The `-ing` group alone is 20% of the queue (`trying`, `missing`, `moving`, `becoming`, `changing`,
`operating`), which is why tagging it mechanically is worth more than reviewing it by hand.

**This is morphology, not a POS lookup, and the tag is advisory by design.** No tagger or corpus is
reachable offline — `lemminflect` was not installed at that point, and `nltk`'s data was believed
blocked (it is not; see the correction at the end of this report) — so the tag means "this word has the *shape* of a verb or adjective". Being over-broad is
acceptable for a tag in a way it would never be for an exclusion; that asymmetry is the whole reason
to tag rather than judge. A small closed `NOT_VERB_FORMS` list keeps established `-ing`/`-ed` nouns
(`thing`, `king`, `building`, `morning`, `seed`, `breed`) out of it.

## Human verdicts on gap candidates (2026-08-29)

`gaps_verdicts.csv` accumulates individual rulings — `word,verdict,note` with `verdict` one of
`noun | name | verb | adj`. A ruling beats every automatic flag and tag, the same principle
`PROBE_PATH` and `UK_REVIEWED_PATH` already follow. First 19 recorded:

  * **noun** (11) — `platonism`, `americanization`, `nazism`, `bedouin`, `neanderthal`, `darwinism`,
    `olympiad`, `islamophobia`, `merlot`, `bolshevism`, `toolkit`
  * **name** (6) — `frisbee`, `madeira`, `arcadia`, `vaseline`, `doppler`, `pegasus`
  * **verb** (2) — `endangering`, `channeling`

**These 19 exposed a real defect.** Sixteen of them sat in the *same* bucket, flagged
`case variant of a proper noun` — `nazism`, `darwinism`, `olympiad` and `merlot` were
indistinguishable from `pegasus` and `madeira` to the pipeline, because the flag fires on nothing
more than a Title-case `variant_of`. It cannot tell a name-*derived* ordinary noun from a name.
That bucket holds **283** unruled rows and is the single largest block of bad classification left.

### Next sheet: `sen-v3.csv.case_variant.csv`

Those 283 rows, with a pre-filled `verdict` guess: `noun` when the word carries a common-noun-forming
suffix (`-ism`, `-ist`, `-ology`, `-phobia`, `-iad`, `-ization`, `-ite`), `name` otherwise — 17 and
266 respectively. The guess is there to be overwritten, not trusted; `enter` is guessed `name` and
is obviously a verb. `zipf`, `variant_of` and `first_gloss` ride along so each call can be made
without opening another file. Correct the `verdict` column and the rows append to
`gaps_verdicts.csv`.

Queue after the 19 rulings: **9,729 clean · 10 name_suspect · 374 flagged**.

## Principle — potential plurals are tagged too (2026-08-29)

Same rule extended to number: `bollocks` has a singular `bollock`, so it is **marked** as a
potential plural and the game decides whether plurals are legal answers. `rank_gaps.py` gains a
`plural_of` column holding the singular (empty when there is none), so the tag carries its own
evidence — `bollocks` -> `bollock`, not just a boolean.

The singular may be a dataset row or another gap candidate, so both sides are in scope.
**27 of the 10,113 candidates are tagged**: `bollocks`, `headphones`, `dreadlocks`, `sideburns`,
`bagpipes`, `earmuffs`, `culottes`, `wellies`, `bygones`, `brickworks`, `comes`, `fishes`,
`narrows`, `attaches`, and a few misspellings (`companys`, `countrys`) that are correctly plural in
shape whatever else is wrong with them.

**A guard was necessary and is the interesting part.** Naive `-s` stripping finds a real word by
accident for Latin and Greek singulars, adverbs and double-s words: `bogus` -> "bog", `modus` ->
"mod", `lapis` -> "lap", `polis` -> "pol", `mythos` -> "myth", `nitrous` -> "nitro", `alas` ->
"ala", `amiss` -> "ami", `diss` -> "dis". `NOT_PLURAL_ENDINGS` (`ss`, `us`, `is`, `os`, `as`) runs
before the lookup, cutting 65 raw matches to 27 real ones.

On the `sen-v3.csv` side this was already the case: `plural_suspect` (460), `plural_of_listed` (321)
and `wikt_plural_only` (329) all exist as columns, and the two exclusions they drive
(`plural of listed word`, `plural-only (Wiktionary)`) keep the row with its reason rather than
deleting it — which is exactly what the rejection-reason principle asks for. No change needed there.

## Applied — the case-variant review, 283 verdicts (2026-08-29)

The reviewer accepted the pre-filled guesses unchanged: **266 `name`, 17 `noun`**. All 283 rows are
appended to `gaps_verdicts.csv`, which now carries **302 rulings** (272 name, 28 noun, 2 verb).

**`wx_join.py` now reads the verdicts directly**, replacing the single-purpose name-suspect file as
the sole source. Every verdict other than `noun` names a word that is not a valid answer, so those
words join the dataset carrying that reason — the rejection-reason principle, applied uniformly
rather than only to names. A `verdict_reason` column holds the text, and `pos_overlap` carries
`verb`/`adjective` for the non-name verdicts.

### Effect

| | before | after |
| --- | ---: | ---: |
| rows | 43,048 | **43,322** |
| added from review (`source = gaps-review`) | 462 | **736** |
| recommended | 30,508 | **30,508** |
| gaps.csv candidates | 10,113 | **9,837** |
| flagged in gaps | 374 | **91** |
| name_suspect band | 10 | **4** |

`recommended` is unchanged again — every added row is excluded by construction. The
`case variant of a proper noun` flag is now **empty**: all 283 of its rows were ruled on, which is
what dropped `flagged` from 374 to 91. New exclusion reasons in the dataset:
`proper noun or other non-noun (reviewed)` 734, `verb form (reviewed)` 2.

### Rows worth a second look, recorded rather than argued

The guesses were accepted wholesale, and the guess was a crude suffix test, so a handful of `name`
verdicts sit oddly against `noun` verdicts already recorded:

  * `darwinism` -> **noun**, but `darwinian` -> **name**; `nazism` -> **noun**, but `christianity`
    -> **name**. Same derivation, opposite verdicts.
  * `viking`, `oriental`, `terrestrial`, `riesling`, `gnostic`, `sapphic`, `praetorian` are
    ordinary common nouns or adjectives in most uses.
  * `enter` -> **name** is simply wrong; it is a verb. This was flagged before the review as the
    obvious defect in the guess, and came back unchanged.

**The cost of each of these is low, which is why they were applied as given.** Under the
rejection-reason principle a wrong `name` verdict does not delete the word — it becomes a dataset
row saying "probably a name". Correcting one later is a single line in `gaps_verdicts.csv` and a
re-run; the verdict file is the authority, so nothing has to be undone anywhere else.

## Applied — reviewer edits to `gaps_verdicts.csv` (2026-08-29)

Four verdicts changed, three of the six rows this report had flagged as worth a second look:

  * `bolshevik`, `pooper`, `decalogue` — `name` -> **noun**
  * `terrestrial` — `name` -> **adjective**

`terrestrial` is the first `adj` verdict, and it exercised the path end to end: it now sits in
`sen-v3.csv` with `excluded_because = 'adjective (reviewed)'` and `pos_overlap = 'adjective'`. The
other three left the dataset and returned to `gaps.csv` as clean candidates, which is the verdict
file working in both directions — a ruling can promote as well as reject.

**One fix was needed.** The edit spelled the verdict `adjective`, while the code matched `adj`, so
the row would have been silently ignored — the worst possible failure for a hand-edited file, since
nothing reports it. Both scripts now normalise verdict spellings through `VERDICT_ALIASES`
(`adjective`/`adjectival` -> `adj`, `verbal` -> `verb`, `proper noun`/`propernoun` -> `name`,
`nouns` -> `noun`), lower-cased and stripped. Unrecognised values are still left alone and match no
rule, but the spellings a person actually writes now work.

**Effect:** rows 43,322 -> 43,319; recommended unchanged at 30,508; gaps clean band 9,742 -> 9,745.
Dataset exclusion reasons from review: `proper noun or other non-noun (reviewed)` 730,
`verb form (reviewed)` 2, `adjective (reviewed)` 1.

`enter` was left as `name` and is unchanged.

## Closed — the `name_suspect` band is empty (2026-08-29)

The four words held back by the earlier name-suspect review are ruled `noun`: `penicillium` (genus
name in common use), `freon` and `plasticine` (genericised trademarks, the same shape as `wifi` and
`pilates` in the probe file), and `typhon` (an ordinary common noun — "a violent whirlwind" — that
merely shares its spelling with a mythological name).

**Both name-derived review queues are now empty:** `name_suspect` 4 -> **0** and the case-variant
sheet 0. `gaps.csv` clean band: **9,749**. The lower-cased proper-noun residue that surfaced four
separate times across this report is closed for the current data — not by a better classifier, but
by 306 recorded human verdicts sitting in front of one.

## Automatic part-of-speech classification (2026-08-29)

Yes — and with a real lexicon rather than more morphology. **`lemminflect` installs fine here.**
Every earlier pass in this report worked around "no POS source offline", but that was only ever
true of `nltk`'s *data* server: PyPI itself is reachable, and `lemminflect` ships its lexicon inside
the wheel. It was already a project dependency — `enrich.py` imports it — so this closes a gap that
had been assumed shut since the first ranking pass.

It answers exactly the cases suffix rules cannot see, because they have no suffix to match on:

| word | `pos_tags` | lemma | verdict |
| --- | --- | --- | --- |
| `pretty` | `ADJ;ADV` | | adjective/adverb (not a noun) |
| `beautiful` | `ADJ` | | adjective (not a noun) |
| `hot` | `ADJ;VERB` | | adjective/verb (not a noun) |
| `higher` | `ADJ;ADV` | high | adjective/adverb (not a noun) |
| `easy` | `ADJ;ADV` | | adjective/adverb (not a noun) |
| `learn`, `follow`, `eat` | `VERB` | | verb (not a noun) |
| `trying` | `VERB` | try | verb (not a noun) |

Three new columns carry it: `pos_tags` (the raw lexicon answer), `lemma` (base form when it
differs — `higher` -> `high`, `trying` -> `try`), and `pos_overlap` (the label).

### Marked and kept, not dropped

Per the rejection-reason principle, **4,317 auto-classified non-nouns were added to the dataset**
with `source = 'pos-auto'` and `recommended = False`, so the game can answer *"'pretty' is an
adjective"* rather than *"not in the database"*. New exclusion reasons:

| reason | rows |
| --- | ---: |
| `verb (not a noun)` | 3,021 |
| `adjective (not a noun)` | 1,080 |
| `adjective/verb (not a noun)` | 121 |
| `adjective/adverb (not a noun)` | 55 |
| `adverb (not a noun)` | 34 |
| others | 6 |

**Only the lexicon's own verdict qualifies a word for this.** The suffix heuristic stays a tag on
the gaps queue and never writes a row: a morphological guess is not evidence enough to add a word
to the dataset, and that asymmetry is deliberate. A recorded human verdict still beats both.

### The unknown words are a signal, not a hole

6,040 clean candidates had no lemminflect entry. That is not a coverage failure — the lexicon covers
ordinary English, so the absentees are `oh`, `lol`, `http`, `san`, `de`, `al`, `ya`, `kinda`,
`haha`, `facebook`: abbreviations, interjections, internet slang and names. Not knowing them is
informative. They fall back to the suffix tags, which now cover 815 rows rather than 2,930 —
everything else is answered by the lexicon.

### Effect

| | before | after |
| --- | ---: | ---: |
| rows | 43,319 | **47,636** |
| recommended | 30,508 | **30,508** |
| gaps.csv candidates | 9,837 | **6,542** |
| clean band | 9,749 | **6,506** |
| flagged in gaps | 91 | **36** |

`recommended` is unchanged for the fourth time running — every added row is excluded by
construction, so the playable list has never moved through any of this. What moved is how much the
dataset can *explain*. The review queue shrank by a third in one pass without a single manual
decision, and the 36 rows still flagged are all from the two closed lists (34 function words,
2 irregular verb forms) and need no review at all.

## Release — `sen-2026-08-29.csv` (2026-08-29)

`release_sen.py` cuts a dated, game-facing release. `sen-v3.csv` stays the working file — 39
columns, every piece of evidence any rule was derived from, so a verdict can be re-derived without
re-running anything. A game needs none of that, so the release is the 15 columns it actually
consumes, renamed to what they mean at the point of use: `recommended` -> `allowed`,
`excluded_because` -> `reason`, `plural_of_listed` -> `is_plural`.

**One file, not two, deliberately.** Shipping only the 30,508 playable words would throw away
exactly what the last several passes were built to provide. The rejected rows are the product:

    allowed=False  reason="adjective (not a noun)"                                  (pretty)
    allowed=False  reason="british/commonwealth spelling variant"  suggest="plow"   (plough)
    allowed=False  reason="proper noun or other non-noun (reviewed)"                (pegasus)

### Contents

**47,636 rows · 30,508 allowed (64.0%) · 17,128 rejected, every one with a reason ·
219 carrying a replacement.**

| reason | rows | | reason | rows |
| --- | ---: | --- | --- | ---: |
| obscure | 10,558 | | british/commonwealth spelling variant | 217 |
| verb (not a noun) | 3,021 | | plural-only (Wiktionary) | 134 |
| adjective (not a noun) | 1,080 | | adjective/verb (not a noun) | 121 |
| inflected form (Wiktionary) | 758 | | adjective/adverb (not a noun) | 55 |
| proper noun or other non-noun (reviewed) | 730 | | adverb (not a noun) | 34 |
| not in Wiktionary | 411 | | others (reviewed, adverb combos) | 9 |

Allowed words by tier: CORE 621 · COMMON 2,772 · FAMILIAR 6,980 · UNCOMMON 10,347 · RARE 9,780 ·
**OBSCURE 8**. Those 8 are not a leak: they are the human keep-list overriding the OBSCURE
exclusion (`abstractor`, `apophthegm`, `dueller`, `peewit`, `plowwoman`, `plowwright`, `shote`,
`welsher`), which is the keep-list working as designed.

### Integrity gates

The script asserts three things before writing, because a release that contradicts itself is worse
than no release and none of these is eyeballable at 47k rows: nouns are unique; no `allowed` row
carries a reason; no rejected row lacks one. All three pass. Row count and reason totals reconcile
exactly with the pipeline's own output.

## `variants.csv` cleanout — `-ing` forms split into their own table (2026-08-29)

Requested before the next manual pass over the doublets. An `-ing` word is a **potential verb
first and a spelling variant second**, so leaving those rows in `variants.csv` asks the reviewer two
different questions at once. They now go to `sen-v3.csv.variants_ing.csv`.

**148 rows moved. `variants.csv` drops 3,206 -> 3,058** (1,778 of them still undecided).

The split file carries a pre-filled `verdict` plus the lemminflect reading of the `-ing` side
(`variant_pos`, `variant_lemma`), so the two questions can be answered from one row:

| verdict | rows | what it means |
| --- | ---: | --- |
| `spelling_pair` | 89 | `-ing` on both sides and near-identical — a real doublet |
| `verb` | 32 | the `-ing` side is a verb form; the pairing is usually incidental |
| `noise` | 27 | neither — gloss-regex artifact |

`spelling_pair` is the British doubled-consonant family the report flagged earlier and the suffix
list never covered: `counselling`/`counseling`, `colouring`/`coloring`, `fuelling`/`fueling`,
`focussing`/`focusing`, `ageing`/`aging`, `flavouring`/`flavoring`, `centring`/`centering`,
`plowing`/`ploughing`.

`verb` catches the rows where the `-ing` word is genuinely verbal and the "canonical" is unrelated:
`breaking` -> "ornamentation", `dating` -> "romantic", `caning` -> "punishment", `lapping` ->
"fraud". The verdict is accurate about the word and says nothing kind about the pairing — which is
the point of separating the two questions.

`noise` is the familiar residue: `fingerspelling` -> "a", `mg` -> "meaning", `popcorn` ->
"brainstorming", `ling` -> "linguistics".

Guesses only — `verdict` is there to be overwritten, exactly like the case-variant sheet.
`variants.csv` is now ready for its own pass without the `-ing` question mixed in.

## Root cause found — `variant_kind == 'spelling'` is not a kind (2026-08-29)

Prompted by the question "where does `abduction,argument,spelling` come from?". It is not a data
oddity; it is a bug in `wx_extract.py`, and finding it made the doublet queue reviewable.

`VARIANT_RE` (wx_extract.py:48) is:

    (?P<kind>alternative|alternate|archaic|obsolete|dated|nonstandard|
       common\s+mis|mis|standard|british|american|commonwealth|eye|informal)?
    [a-z\s]*(?:spelling|form)\s+of\s+(?P<target>[A-Za-z][A-Za-z'\-]*)

Three faults compound. The `kind` group is **optional**; `[a-z\s]*` lets arbitrary words sit
between it and `spelling|form`; and the search is **unanchored** and case-insensitive. So the
pattern matches the everyday English phrase "form of X" anywhere in any sense's gloss, not just the
lexicographic formula "Alternative form of X" that opens a definition:

  * `abduction` -> "argument", from the logic sense, "... a **form of** argument ..."
  * `acute` -> "a", from "a person who has the acute **form of a** disorder"
  * `accident` -> "transportation", `abbreviation` -> "a", `absolution` -> "words"
  * **137 rows point at the word "a"**

And the aggravating detail: when the optional `kind` group does not match, `variant_kind` falls back
to the literal `'spelling'`. **The loosest matches are the ones labelled most confidently** — which
is exactly why `abduction,argument,spelling` reads as an assertion when nothing established it.

### That default label is a clean separator

Measured across the undecided doublets, the split is not marginal:

| `variant_kind` | rows | median variant/canonical similarity | canonical == "a" |
| --- | ---: | ---: | ---: |
| `alt_of` | 1,253 | **0.83** | 0 |
| `dated` | 16 | 0.85 | 0 |
| `american` | 8 | 0.93 | 0 |
| `alternative` / `standard` | 8 | 0.83–0.92 | 0 |
| **`spelling`** | **493** | **0.25** | **137** |

`alt_of` comes from Wiktionary's *structured* `alt_of` field — not the regex at all. The keyword
kinds required a real lexicographic word to be present. Only `spelling` means "the loose path fired
and nothing corroborated it", and 401 of its 493 rows sit below 0.5 similarity.

### The split

`wx_join.py` now writes three doublet files instead of one:

| file | rows | undecided | what it is |
| --- | ---: | ---: | --- |
| `variants.csv` | 2,446 | **1,285** | `alt_of` + keyword kinds — the reviewable queue |
| `variants_suspect.csv` | 612 | 493 | `variant_kind == 'spelling'` — mostly regex artifacts |
| `variants_ing.csv` | 148 | 73 | `-ing` on either side, with verdicts |

The review queue drops from 1,851 undecided rows to **1,285**, and what left was the part that was
28% noise.

**The proper fix is not available here.** It means anchoring the regex at the start of the gloss,
making the `kind` group mandatory for the `spelling|form of` path, and re-running `wx_extract.py` —
which needs `raw-wiktextract-data.jsonl.gz` re-downloaded (2.6 GB, deleted earlier as reproducible).
Recorded here so the next person with the dump in hand knows exactly what to change and why, rather
than rediscovering it from `abduction`.

## Handover — state at the end of 2026-08-29

The 2.6 GB dump is being re-downloaded so `VARIANT_RE` can be fixed and extraction re-run.
`NEXT-SESSION-PLAN.md` carries the operating plan: the three faults to fix, the command sequence,
the baseline numbers to diff against, and the open queues. This report stays the full history
behind it.

**Everything is committed and the tree is clean.** Pipeline re-runs end to end from committed
inputs.

### Where the data stands

| file | rows | note |
| --- | ---: | --- |
| `sen-v3.csv` | 47,636 | working file, 39 evidence columns; 30,508 recommended |
| `sen-2026-08-29.csv` | 47,636 | the release, 15 game-facing columns |
| `sen-v3.csv.gaps.csv` | 6,542 | 6,506 clean candidates, 36 flagged (closed lists) |
| `sen-v3.csv.variants.csv` | 2,446 | 1,285 undecided — next manual review |
| `sen-v3.csv.variants_suspect.csv` | 612 | expected to be largely obsoleted by the re-run |
| `sen-v3.csv.variants_ing.csv` | 148 | 73 undecided, verdicts pre-filled |
| `sen-v3.csv.unknown.csv` | 1,378 | closed — all excluded by decision |
| `sen-v3.csv.uk_review.csv` | 22 | closed — regex noise only |

### What each pass actually bought

`recommended` has been **30,508 for five consecutive passes**. That is the point rather than a
coincidence: every change since the rejection-reason decision has added *rejected* rows carrying an
explanation, not playable ones. The playable list stopped moving; what grew was how much of a
player's input the dataset can account for — 17,128 rejected rows, every one with a reason, 219 with
a replacement to suggest.

The review queues went the other way. Names: 466 -> 0. Case variants: 283 -> 0. Gap candidates:
10,591 -> 6,542. Doublets needing eyes: 1,851 -> 1,285. Two of those closed on 306 recorded human
verdicts, one on a real POS lexicon, one on finding the bug behind the noise.

### Still open

1. `variants.csv` — 1,285 undecided, waiting on the re-run so the review is against correct data.
2. `gaps.csv` clean band — ~6,500, the queue that actually adds vocabulary. Nothing blocks it.
3. `variants_ing.csv` — 73 undecided.

## Correction — the network was never blocked (2026-08-29)

Several passes in this report worked around "no POS source is reachable offline". **That premise was
wrong, and it was never tested.** Checked directly on the last day:

  * `pip install lemminflect` — works. Found earlier, which is what enabled the POS pass.
  * `pip install nltk` — works.
  * `raw.githubusercontent.com/nltk/nltk_data` — HTTP 200.
  * `nltk.download(...)` for `averaged_perceptron_tagger_eng`, `averaged_perceptron_tagger`,
    `punkt_tab`, `wordnet` — all four return `True`.

The claim originated as an assumption early on and was then repeated as established fact, including
in a note that said "confirmed by testing". It was not. It shaped at least three decisions: the
morphology-only `pos_overlap` tagging, the closed-list approach in `rank_gaps.py`, and the
"needs a real POS-frequency source, which we cannot have" framing of the nominalised-adjective
residue.

**What it does not change.** `nltk.pos_tag` is a *contextual* tagger; on isolated words it falls
back to suffix priors and is weaker than a lexicon — it reads `pretty` as `RB` and would tag every
unknown word `NN`. For "what parts of speech can this word be", lemminflect's lexicon remains the
right tool, so the POS work stands as built. `nltk`'s WordNet is 3.0, superseded by the OEWN 2025
data already in use.

**What it opens.** The nominalised-adjective residue (`political`, `federal`, `hot` — real noun
senses that no closed list can separate from ordinary adjectives) was parked as unresolvable
because it needs dominant-POS frequency, e.g. SUBTLEX. That is a download, and downloads work. It
is now a live option rather than a documented dead end.

**The lesson, recorded because it cost real work:** an untested environment assumption hardened into
a fact and then into a design constraint. It should have been one `pip install` early on.

## Session — the fixed regex, three new evidence sources, and a marked release (2026-08-29, later)

The dump was re-downloaded, so the plan in `NEXT-SESSION-PLAN.md` ran end to end. It then kept
going: with the network known to work, the two sources the project had repeatedly written off as
unavailable turned out to be one download and one extra pass over the dump away.

### 1. `VARIANT_RE`, fixed

`wx_extract.py`'s gloss regex now requires the formula to **open** the gloss (`\A`), bounds the
filler between the qualifier and `spelling|form of` to three words, and labels a bare "Form of X"
opening `unqualified` instead of `spelling`. A stop-list rejects function-word targets, because
"Form of the verb sing" is prose, not a variant pair.

| thing | before | after |
| --- | ---: | ---: |
| `variant_of == 'a'` | 796 | **1** |
| `variant_kind == 'spelling'` (the bogus label) | 7,392 | **0** |
| `variants_suspect.csv` | 612 | **0** |
| `recommended` | 30,508 | 30,506 |

`recommended` moved by two, which is the outcome the plan predicted and the check it asked for.
Two new columns, `variant_sense` and `variant_gloss`, record WHICH sense produced the match, so a
row's `variant_of` can be traced to the text that caused it.

### 2. A POS-tagged corpus — `pos_freq.py` -> `pos-dominance.csv`

45,234 word types over 1.26M tagged tokens from `brown` + `conll2000` + `treebank`, read with their
native tags so **proper nouns stay separate from common nouns** (the universal tagset folds them
together, which is exactly the distinction `joe` and `madison` need).

This answers the question parked as unanswerable since the beginning: not "can this be a noun?"
(`political`, `federal`, `hot` all can) but "is it one in practice?" — 0 of 339 `political` tokens
are nouns. 34 gap candidates are flagged on that evidence, and 1,565 SEN rows carry a
`usually an adjective/verb/adverb (corpus)` mark.

### 3. Wiktionary's full POS inventory — `wx_pos.py` -> `wiktionary-pos.csv`

`wx_extract.py` keeps only `pos == "noun"` entries and throws the rest away, which is why the top of
the gap queue was `oh`, `ha`, `ya`, `de`, `ve`, `na`. One more pass over the dump keeps **every**
English entry: 1,385,953 words with a POS-and-sense-count list (`intj:10;noun:3`) and an
abbreviation flag.

Only the **closed classes** are trusted to flag. Wiktionary is generous with obsolete verb senses —
`fridge` is verb:5/noun:2 and `piano` is verb:4/noun:1 — so "more verb senses than noun senses" is
not evidence. Being filed mainly as an interjection or a pronoun is: 66 flags, no false positives
found. The abbreviation flag is advisory only, because it catches `ad`, `gym`, `laser` and `pc`
alongside `st` and `mp`.

A fourth, free signal came with it: **the gloss often says what the word is.** "Initialism of ...",
"Clipping of ...", "Alternative letter-case form of ...", "Misspelling of ..." — 941 candidates
flagged by their own first sense.

### 4. `marks` — the dataset says what it doubts

New column, shipped in the release. `excluded_because` answers *may I play this?*; `marks` answers
*what else might this word be?*, and **it applies to allowed words too** — 2,645 of the 30,729
playable rows carry one.

| mark | rows |
| --- | ---: |
| `verb (not a noun)` | 3,040 |
| `possible name` | 2,034 |
| `manual - not in Wiktionary, is it a real noun?` | 1,378 |
| `possible abbreviation or clipping` | 1,209 |
| `adjective (not a noun)` | 1,080 |
| `usually an adjective (corpus)` | 648 |
| `usually a verb (corpus)` | 634 |
| `possible plural` | 613 |
| `UK/Commonwealth spelling` | 274 |
| `usually a name (corpus)` | 241 |

The UK mark is deliberately narrow: only words the pipeline judged to be the British **spelling** of
an American word. A UK region tag on some sense is a different fact — `abbey`, `abbot` and
`absentee` all carry one and none is a spelling variant of anything.

### 5. Manual review — 909 rulings, all recorded

`manual_reviews.csv` (`date,sheet,item,verdict,note`) is the new record of every hand ruling.

* **`uk_review.csv`, 22 rows — closed.** All 22 were regex noise: clippings (`lat`, `mag`, `panto`,
  `par`, `lit`, `mod`, `do`, `dead`, `t`, `y`) and ordinary distinct words (`broach`, `chapiter`,
  `darter`, `delf`, `frank`, `melt`, `rime`, `char`, `cos`). None is a British spelling of the word
  it was paired with. The queue is now empty.
* **`variants_ing.csv`, 99 rows — closed.** The verdict vocabulary was changed to name the *side*:
  `british` (37), `american` (26), `spelling_pair` (15, real doublets with no regional direction),
  `noise` (21). `wx_join.py` reads the result and it fixed a real hole — `colouring`, `savouring`,
  `counselling` and 60 others were being recommended alongside their American spellings because
  Wiktionary tags `modelling` regionally but not them.
* **`gaps.csv` clean band at zipf >= 3.0, 792 rows — closed.** 192 `noun`, 263 `name`, 183 `noise`,
  123 `adj`, 31 `verb`. `gaps_verdicts.csv` now holds 1,092 rulings.

### 6. What the rulings bought: modern vocabulary is finally in

A `noun` verdict previously did nothing but clear a flag on a queue. It now **adds the word to the
dataset as a playable row**, which is how OEWN's 2025-vintage blind spot gets fixed at all:

> `app`, `download`, `upload`, `selfie`, `screenshot`, `username`, `login`, `blockchain`, `bitcoin`,
> `covid`, `cybersecurity`, `blogging`, `podcast`-adjacent `audiobook`, `webinar`, `meetup`,
> `cosplay`, `hoodie`, `mixtape`, `midfielder`, `coworker`, `ceasefire`, `groundwater`,
> `entrepreneurship`, `outsourcing`, `motherboard`, `rollercoaster`, `smartwatch`, `ecommerce`

223 words joined as playable; `noise` verdicts joined as *rejectable* rows so the game can answer
"`kinda` is not a noun" instead of "not in the database".

### Where it landed

| file | rows | note |
| --- | ---: | --- |
| `sen-2026-08-29.csv` | 48,477 | 30,729 allowed, 17,748 rejected with a reason, 10,373 marked |
| `sen-v3.csv.gaps.csv` | 5,762 | 4,607 clean (was 6,542), 114 name band |
| `sen-v3.csv.variants.csv` | 2,509 | the next review queue |
| `sen-v3.csv.unknown.csv` | 1,378 | excluded, all marked for manual reading |
| `sen-v3.csv.uk_review.csv` | **0** | closed |
| `sen-v3.csv.variants_suspect.csv` | **0** | obsoleted by the regex fix |
| `manual_reviews.csv` | 909 | every ruling made today, with its reason |

## Applied — the `variants.csv` review, all 2,509 pairs (2026-08-29, later still)

The last queue over the manual-review threshold. Ruled in full, on the reviewer's own worked
examples: `y`/`year` (one side is not a noun), `stoke`/`stokes` (a plural, not a spelling),
`cozier`/`cosier` (both adjectives), `wild`/`weald` (two unrelated words), `win`/`wynn` (a name),
`wrap`/`rap` and `wog`/`polliwog` (keep both), and `zombi`/`zombie`, `resistent`/`resistant`,
`zikurat`/`ziggurat`, `yoghourt`/`yogurt` — **keep the standard spelling, keep the variant too and
mark it**, exactly as British spellings are handled.

### Scripted first, three times over

The pre-fill went through three versions, and the first two were wrong in ways worth recording.

**Edit distance is not evidence.** `car`/`cat`, `beach`/`bitch`, `wild`/`weald`, `birth`/`berth` and
`president`/`precedent` are all one or two edits apart and none is a spelling of the other. That
pre-fill called 1,998 pairs a doublet; most of the high-frequency ones were wrong.

**The word's own gloss is.** A real doublet OPENS by saying so — "Alternative spelling of colour."
Matching `wx_extract.py`'s (now fixed) `VARIANT_RE` against each side's first gloss and requiring
the target to be the other side of the pair got it right for 1,731 pairs and left the junk alone.

**But the gloss does not say which side to KEEP.** Wiktionary hangs the note on whichever side
carries it, so `colour -> color` and `humor -> humour` both exist and mean the same thing: keep the
American. Two fixes were needed:

1. `VARIANT_RE` never matched `US standard spelling of humour` at all — `us`, `uk`, `canada`,
   `ireland` and friends were missing from the qualifier list, and a comma in
   `Canada, US standard spelling of favourite` broke the filler. **Fixed in `wx_extract.py` and
   re-extracted**; `variant_kind` gains `uk` (104) and more `american` (29).
2. A `to_american()` rewrite (`-our`/`-or`, `-ise`/`-ize`, `-isation`/`-ization`, `ae`/`oe` -> `e`,
   `-re`/`-er`, `-logue`/`-log`) decides direction wherever the two forms map onto each other.
   `wx_join.py`'s `uk_us_pattern` is suffix-anchored and cannot see `favourite`/`favorite` or
   `colourlessness`/`colorlessness`.

### The verdicts

| verdict | pairs | what happens |
| --- | ---: | --- |
| `variant` | 1,690 | the `variant` column is dropped, pointed at `canonical` |
| `reverse` | 148 | the other way round |
| `unrelated` | 657 | not a pair; the link is deleted so no rule acts on it |
| `plural` | 14 | `stoke`/`stokes`, `pamper`/`pampers` — marked, never excluded |

**31 pairs were overridden by hand** against the script: `carrel`/`carol`, `moolah`/`mullah`,
`torr`/`tor`, `qi`/`chi`, `heckle`/`hackle`, `chapiter`/`chapter` and `gamedev`/`game` are not
doublets whatever the gloss says; `dialogue`/`dialog` and `mic`/`mike` had the direction backwards
(`dialogue` and `mic` are the modern standards); `none`/`nones`, `crap`/`craps`, `canvas`/`canvass`,
`puss`/`pus` and `buss`/`bus` are not plurals.

**63 side rulings** went to a new sheet, `sen_word_verdicts.csv` — rulings on words the dataset
ALREADY has, which `gaps_verdicts.csv` structurally cannot express (it only adds rows). `y`, `t`,
`ms`, `mm`, `ft`, `sec` and 26 more single letters and abbreviations are `noise`; `wynn`, `percy`,
`nancy`, `cory`, `corey` are `name`; `eager`, `staunch`, `nosy`, `cozier`, `cosier`, `mediaeval` and
19 more are `adj`; `here` is `adv`.

### One conflict, resolved in favour of the newer ruling

The old `uk_reviewed.csv` keep-list was written to answer one question — *is this wrongly flagged as
a British spelling?* — and it was overriding today's rulings on 22 words, resurrecting `gaol`,
`kerb`, `annexe`, `baulk`, `acknowledgement`, and even `t` and `y`. The keep-list now loses to an
explicit later ruling (`reviewed_spelling_variant`, or a verdict sheet) and keeps its authority
everywhere else. Nine words still ride on it: `beach`, `brief`, `chapiter`, `cos`, `dead`, `lats`,
`peewit`, `plowwoman`, `plowwright`.

### Effect

| | before | after |
| --- | ---: | ---: |
| allowed | 30,729 | **29,981** |
| rejected with a reason | 17,748 | 18,496 |
| ... as a reviewed spelling variant | 0 | 1,606 |
| rows with a replacement to suggest | 274 | **1,907** |
| rows carrying a mark | 10,373 | 11,951 |

The 748 words that stopped being playable did not leave the dataset: every one is a row that now
says *this is a spelling of that*, and names the word to play instead.


---

## Session 2026-08-29b — a bigger, newer POS corpus

`pos_freq.py` read three corpora, all pre-1990 written American English: `brown` (1961) and the two
Wall Street Journal sets. That is what the report above meant by "the corpus is old and small" —
it had never seen `email`, `website` or `browser`, so it could say nothing about them.

Six sources added, no new dependency and no licence question:

| source | tokens (alphabetic) | what it is |
| --- | ---: | --- |
| `masc_tagged` | 474,674 | Open ANC: blogs, email, essays, letters, 2000s |
| `switchboard` | 62,193 | telephone speech, 1990s |
| `nps_chat` | 34,297 | internet chat, 2006 |
| UD English **EWT** | ~250,000 | web reviews, blogs, email, newsgroups, 2010s |
| UD English **GUM** | ~178,000 | reddit, how-to, vlogs, academic, still growing |

The three nltk ones are `nltk.download` names. The two treebanks are `.conllu` files that
`fetch_ud()` downloads into `sources/ud/` on first run; their **Penn** tag (column 5) is read, not
the universal one, so the existing `coarse()` handles every source unchanged. Multiword and
empty-node rows (an ID containing `-` or `.`) are skipped, or tokens listed both ways get counted
twice. `masc_tagged` carries a few `None` tags; those are skipped.

**1,264,431 -> 2,264,455 alphabetic tokens. 45,234 -> 61,957 word types.**

### Effect on the dataset

`allowed`, `reason` and `suggest_instead` are **unchanged on all 48,477 rows** — corpus evidence
only ever produced marks, and the rebuild confirms it. 739 rows changed marks:

| mark | before | after |
| --- | ---: | ---: |
| usually a verb (corpus) | 634 | 865 |
| usually an adjective (corpus) | 648 | 842 |
| usually a name (corpus) | 241 | 402 |
| usually an adverb (corpus) | 42 | 55 |

Rows with any corpus evidence: 16,915 -> 20,209; rows above the `CORPUS_MARK_MIN_N = 10` threshold
where the mark can fire at all: 5,141 -> 7,011. Allowed rows carrying a mark: 2,586 -> 2,791.

79 rows **lost** a mark, and every one is a correction rather than a regression: the extra tokens
pushed `noun_share` past the 0.20 cutoff. `bear` went 0.200 -> 0.397 and stopped being "usually a
verb"; `curry` 0.091 -> 0.450 and stopped being "usually a name"; `alert`, `crude`, `atlas` and
`coordinate` the same way.

New name marks are mostly right — `facebook`, `google`, `amazon`, `jordan`, `victoria`, `kelly`
are all genuinely proper nouns in the new text. The noise to watch is capitalisation: MASC includes
title-case headings and chat capitalises freely, so `yep` (77 tokens, dominant PROPN) is marked a
name and is not one. Advisory, as before — nothing excludes on it.

### Still open

`blockchain`, `smartphone` and `selfie` have zero tokens across all 2.26M. No hand-tagged corpus is
large or recent enough for the 2015+ tail; that needs tagging a modern dump with a parser
(`spacy en_core_web_sm` over the Wiktionary example sentences in the dump would do it), which is
hours of work, not minutes. `zipf` already carries modern frequency, and a word the corpus has
never seen produces no mark rather than a wrong one, so this stays a gap and not a bug.


## Session 2026-08-29c — `manual-entry.csv`, the words no source has

The corpus work above fixed what the dataset *knows about* a word. It could not fix what neither
source contains at all: OEWN 2025 and the Wiktextract dump between them have no `deepfake`, no
`kombucha`, no `microplastic`, no `sysadmin`, and the frequency cutoff would have thrown out
`tokenomics` and `lootbox` even if they had.

`reviews/manual-entry.csv` is the answer, and it is a review sheet like the others — `word,
verdict, note`, same verdict vocabulary — pointed the other way. Every other sheet rules on words a
queue put in front of a person; this one is where a person puts the word in.

**145 rows: 133 `noun`, 4 `name`, 5 `adj`, 3 `noise`.** 141 are new rows; 4 are corrections to
words the dataset already had and got wrong.

### What it overrides, and why that is deliberate

A `noun` here is the last word on that word. It beats:

* **the OBSCURE cutoff.** `wordfreq` scores `tokenomics`, `lootbox` and `hotdesking` at 0.00 — it
  is older than the words. Nine playable OBSCURE rows now exist, all of them hand entries.
* **the missing-from-Wiktionary rule.** `devops`, `youtuber`, `tiktoker`, `carshare`, `reskilling`
  and `upskilling` have no Wiktionary noun entry. The rule exists because an OEWN row with no
  Wiktionary entry is usually specialist debris; a word a person typed in is not.
* **lemminflect's reading.** `gamer` was excluded as an adjective and `broadband` likewise;
  `ghosting` as a verb form. All three are ordinary nouns.
* **an earlier human ruling.** `spork` was ruled a proper noun in the name-suspect pass. It is a
  utensil. The precedence rule already in force — later and more specific wins — settles it.

The `manual - not in Wiktionary, is it a real noun?` mark is suppressed for these rows: that
question is what the sheet answers, so leaving it on `devops` would be the build asking itself.

The `note` column doubles as the gloss. 18 of the 145 have no Wiktionary entry to take a definition
from, and a row a game shows a player is better off with the sentence the person who added it
wrote than with nothing.

### Effect

| | before | after |
| --- | ---: | ---: |
| rows | 48,477 | **48,618** |
| playable | 29,981 | **30,114** |
| rejected with a reason | 18,496 | 18,504 |
| playable OBSCURE rows | 0 | 9 |

The three rejected verdicts earn their place the same way every other rejection does: `usb`, `api`
and `sdk` now answer "an initialism, not a playable common noun" instead of "not in the database",
and `bluetooth`, `kubernetes`, `crossfit` and `segway` answer "a trade name".

### How the list was chosen

Candidate modern vocabulary was checked against the release and the Wiktionary noun table first, so
nothing already present was re-entered: `blockchain`, `smartphone`, `selfie`, `podcast`, `emoji`,
`webinar`, `hackathon`, `cybersecurity` and most of the 2010s tech vocabulary were **already
playable**. What was missing splits into four groups — later coinages (`deepfake`, `metaverse`,
`stablecoin`, `mansplaining`), solid compounds Wiktionary lists but OEWN does not (`newsfeed`,
`whiteboard`, `heatwave`, `carpool`), loanword food and drink (`kimchi`, `bibimbap`, `matcha`,
`kombucha`, `cortado`), and job-and-practice nouns (`sysadmin`, `podcaster`, `coworking`,
`onboarding`).

Deliberately left out: plurals (`earbuds` — `earbud` is in), hyphenated and open compounds, and
words whose only reading is a brand. `stan` is in as a common noun and is the riskiest row in the
sheet: it collides with a given name, and the corpus marks it `usually a name (corpus)` — which is
exactly the doubt-written-down behaviour the dataset is built on.

### Still open

The sheet is a list, not a system. The next time the sources are rebuilt it will still be the only
place a 2024-and-later word can enter, and it will need extending by hand again. That is the
intended cost: it is 145 lines of judgement, and nothing derived can replace it.


## The inflected-form flag rejected 166 ordinary nouns, `pen` among them

`pen` came back from the game as *"a writing implement with a point from which ink flows —
[common] Not playable: inflected form (Wiktionary)."* The definition and the reason disagree, and
the reason was wrong.

**Cause.** `wx_extract.py` set `is_inflected_form` if **any** sense of an entry carried a
`form_of`. Wiktionary's `pen` has sixteen noun senses; one of them, a dialect sense, is a form of
`pan`. One sense out of sixteen rejected the word. The same OR rejected `sheet` (a sense is a form
of `shit`), `circle` (of `words`), `chicken`, `opera`, `news`, `thanks`, `offer`, `species`,
`economics`, `ethics`, `measles`, `gallows`, `molasses`, `dice`, `sweep` and 150 more.

**Fix.** The extractor now also writes `lead_form`: whether the etymology section's **first** sense
is the form-of one, merged across sections with `min`. That is how Wiktionary writes a word that
exists only as an inflection — `cats` leads with "plural of cat" and has nothing else to say, where
`pen` leads with the enclosure. `wx_join.py` requires `is_inflected_form` **and** `lead_form`
before it rejects. Two intermediate rules were tried and thrown away: counting form senses against
total senses let irregular plurals in beside their own singulars, and taking the first form sense's
index poisoned `pen` again, because that index is per-etymology-section and the minor section is
still one of the sections.

The extractor also writes `n_form_senses` and `form_sense`, which are what the two discarded rules
used. They stay in the file as evidence, unused by the join.

**Effect.** Inflected-form rejections fall from 914 to 329. **166 words become playable and none
becomes rejected** — `news`, `offer`, `thanks` (CORE), `pen`, `chicken`, `circle`, `sheet`,
`opera`, `agenda`, `species`, `economics`, `ethics`, `propaganda`, `habit`, `corps`, `crap`,
`freak`, `dive`, `trainer`, `sheep`.

**Latin plurals, deliberately kept.** A handful of irregular plurals ride in on the same change,
because they have a second sense that is not an inflection: `bacteria`, `algae`, `cocci`, `kine`,
`pleura`, `meninges`, `trivia`, `insignia`, `timpani`. Their singulars are playable too, so
`bacterium`/`bacteria` is now both. **This is a decision, not an oversight** (2026-08-31): the
words are too common to refuse, and a player typing `bacteria` does not know they have typed a
plural. `plural_of_listed` would not have caught them anyway — it reads `lemminflect`, which does
not know the Latin plurals.

## A hand ruling on a word the dataset already had did nothing

Found while ruling `cgs` an initialism and watching it stay playable, defined as "system of
measurement based on centimeters and grams".

**Cause.** `load_manual_entries()` is read into `tags`, and `tags` is used to write rows for
`suspects` — words *not* already in `sen`. For a word OEWN already ships, only two things applied:
`sen_word_verdicts.csv`, and a hand `noun`, which is forced playable further down. Every other
verdict on an existing word — `name`, `verb`, `adj`, `adv`, `noise`, `initialism` — was read,
counted in the sheet total and silently dropped. `reviews/RULES.md` and `reviews/README.md` both
describe the override as working; the code only implemented half of it.

**Fix.** `wx_join.py` now applies hand verdicts in place as well, the same way
`sen_word_verdicts.csv` is applied, and a domain sheet's note replaces the definition on an
existing row too — an initialism is shown as its expansion, which is the whole reason the sheet
carries one.

**Effect.** Four rows, all from `domains/initialisms.csv`: `cgs`, `emf` and `rpm` stop being
playable nouns, and `hr` keeps its rejection but gains "Human Resources." as its text. Playable
count 51,434 -> 51,431. `si` stays playable on purpose — it is also the seventh note of the scale,
the "different real sense" exception the initialisms sheet is built around.

## `yoyo` had no row at all: the hyphen gap

Asked whether `yoyo` is playable. It was not in the release in any form.

**Cause.** Two rules that are each right on their own. SEN carries no hyphenated entries, so
Wiktionary's headword `yo-yo` can never be a row. The unhyphenated `yoyo` exists in Wiktionary only
as "Alternative spelling of yo-yo", so the spelling-variant filter sent it to the gaps queue,
pointing at a target that is not in the dataset and never will be. The canonical form is excluded
by format and the writable form by rule.

**Scope.** 55 words, found by taking every gaps row whose `variant_of` is its own spelling with a
hyphen: `standalone`, `offseason`, `signup`, `warmup`, `shoutout`, `faceoff`, `hiphop`, `scifi`,
`todo`, `writeup`, `knowhow`, `halfpipe`, `byelection`, `timelapse`, `powerup`, `tipoff`. Several
are now the dominant spelling — `standalone` and `signup` are written solid far more often than
hyphenated.

**Fix.** `reviews/domains/everyday.csv`, 56 rows, hand-ruled: 43 `noun`, 11 `adj`, one `name`
(`autotune`), one `noise` (`tata`), plus `yule`. Every row carries a written definition because the
inherited one is "Alternative form of X" — a sentence naming a spelling the player cannot play.
The rule was left alone deliberately: dropping the variant filter for hyphenated targets would fix
all 55 at once and sweep in `fatass`, `popo` and `gaga` unread.

**Effect.** 43 newly playable, 0 newly rejected, playable count 51,431 -> 51,474. `yule` stops
being a proper noun and reads "the historical midwinter festival of the Germanic peoples" instead
of "Alternative letter-case form of Yule."

The same change extends the in-place hand ruling above: a domain sheet's note now replaces the
definition on an existing row for a `noun` verdict too, not only for a rejection. That is what
`yule` needed, and it also lets the four corrections in `domains/medical_imaging.csv` --
`aliasing`, `quench`, `shimming`, `thresholding` -- show the definition the sheet wrote for them
rather than the general one.

## Two letters the game kept running out of

`x_words.csv` (193 rows) and `y_words.csv` (47 rows) are not subject areas. They answer a supply
problem: a word-chain game hands off on the last letter, and the dataset had **58 playable words
beginning with `x`** and 156 beginning with `y` — so a player who ended on one of those letters was
often stuck, and the words they reached for (`yoyo`, `xylitol`, `yuzu`, `xenophile`) were not
there.

Both sheets were written across nine passes without a build, so this run is also the first check
RULES asks for: the printed per-sheet count must equal the row count, since a misspelt verdict is
dropped in silence. Both matched — `domain:x_words:193`, `domain:y_words:47` — and every one of the
561 domain rows was verified in the release: verdict honoured, playability as ruled, and the note
showing as the definition.

| | before | after |
| --- | ---: | ---: |
| rows | 61,075 | **61,313** |
| playable | 51,474 | **51,701** |
| playable words starting `x` | 58 | **239** |
| playable words starting `y` | 156 | **202** |

Three rows in the two sheets are corrections rather than additions: `yammer` was read as a verb
form, and `yuletide` was ruled a proper noun defined as "Alternative letter-case form of Yuletide"
— the same reading `yule` had before `everyday.csv` fixed it.

**What is thin about the x sheet.** Around thirty of its rows have no entry in Wiktionary, SCOWL or
OEWN — `xenoform`, `xylozyme`, `xanthopolycyst`, `xeroorganism` and the rest of the transparent
`xeno-`/`xylo-` compounds. They are in on the sheet's own authority, which is what a hand sheet is
for, but they are the rows to look at first if the x supply ever needs trimming rather than
extending.

## The gaps queue is a queue, and 4,126 rows had never been read

Asked why so many x- and y-words Wiktionary has never reached the dataset. Two answers, and the
second one is the reusable finding.

**The frequency cutoff.** 157 of the 240 sheet words had a Wiktionary noun entry. 150 of them score
below `ZIPF_MIN = 2.0` and 126 score exactly 0.00 -- `wordfreq` has never seen them in any corpus --
so they never entered `gaps.csv` at all. That is the cutoff working as designed; specialist
vocabulary is invisible to the automatic path, which is why domain sheets exist.

**The queue is a queue.** The other seven -- `yuko`, `yuzu`, `yair`, `yerba`, `xylitol` -- *were* in
`gaps.csv`, with an empty `verdict` column, and had been for every build. Clearing the cutoff makes
a word eligible, not present: a ruling in `reviews/gaps_verdicts.csv` is what turns a queue row into
a dataset row. `xylitol` sat at exactly 2.00, one ruling away, and was instead added by hand to
`domains/x_words.csv`.

**So the queue was sorted and read.** 5,598 rows, 4,126 of them unruled. About 800 carry a flag that
correctly parks them (spelling variant 521, initialism 137, interjection, clipping, function word).
Of the 3,314 unflagged, 1,455 are `name_suspect` -- sorting by frequency alone puts `english`,
`san`, `sam`, `tony`, `daniel` at the top, given names carrying an obscure common-noun sense
("tony: a simpleton"). Past those, the real material starts at zipf 2.99.

62 were ruled: modern compounds the cutoff let through but no one had read (`setlist`, `treehouse`,
`photoshoot`, `walkthrough`, `passcode`, `chipset`, `keychain`, `eyewear`, `stormwater`,
`homeschool`, `redistricting`, `licensure`), naturalised loanwords (`katana`, `gelato`, `bento`,
`ronin`, `futsal`, `biennale`, `mecha`), clippings that are now the ordinary form (`config`,
`collab`, `convo`, `croc`, `walkie`), and six vulgar but ordinary count nouns, which the dataset
does not censor -- it already ships `crap` and `fatass`. `overthinking` is ruled `verb`: the bare
gerund of an ordinary verb, the same call `smoothing` and `streaking` got.

Rows 61,313 -> 61,375; playable 51,701 -> 51,762.

**A second pass, 85 more.** The same read carried further down the ranking, to zipf 2.52: `codec`,
`otaku`, `kaiju`, `mojito`, `namespace`, `glyphosate`, `powertrain`, `showrunner`, `blogosphere`,
`biodiesel`, `fibromyalgia`, `oxycodone`, `photonics`, `bioavailability`, `microbiota`,
`streetwear`, `supercell`, `stormtrooper`, `metalcore`, `suplex`, `hammam`, `kundalini`, `gouda`.
Nine are ruled `verb` -- `rereading`, `cussing`, `chaining`, `rebooting`, `meowing`, `blotting`,
`romancing`, `goalscoring`, `embalming` -- all bare gerunds naming the act.

Words were skipped where the ruling would ship a bad definition, because a `gaps_verdicts.csv` note
argues for the ruling and does not replace the gloss: `gaslighting` is defined in Wiktionary as
"Illumination by burning gas", `lycra` as "Letter case form of Lycra". Those need a domain-sheet row
with a written note, not a queue ruling.

Rows 61,375 -> 61,460; playable 51,762 -> 51,838. `work/queue-misses.csv` keeps the ranked remainder
-- 1,716 rows that pass the same filters and are still unread.

