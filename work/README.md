# `work/` — the working dataset and the open queues

Regenerated on every run. Nothing here is a human decision (those live in `reviews/`) and nothing
here is the deliverable (that is `sen-<date>.csv` in the root).

| file | rows | what it is |
| --- | ---: | --- |
| `sen-v4.csv` | 60,766 | **the working dataset the release is cut from**: `sen-v3.csv` with the obscure band opened and SCOWL's 12,148 nouns added, by `apply_scowl.py` |
| `sen-v3.csv` | 48,618 | the same 49 columns before that stage — every piece of evidence any rule was ever derived from. Keep it: it is what `apply_scowl.py` re-reads, so the widening is always re-derivable and always reversible |
| `gaps-scowl-noun.csv` | 1,473 | the gaps queue rows SCOWL also calls a common noun, ranked by SCOWL band then zipf. **The queue worth reading** |
| `gaps-scowl-nonnoun.csv` | 543 | gaps rows SCOWL calls something else — 342 adjectives, 99 verbs, 33 abbreviations. A disagreement that names what the word is instead |
| `gaps-scowl-absent.csv` | 3,678 | gaps rows SCOWL has never heard of at size ≤ 70. Names, slang, typos, dump noise |
| `sen-v3.csv.gaps.csv` | 5,694 | words Wiktionary has and OEWN lacks — **candidate additions**, ranked. 4,582 of them clean and below zipf 3.0 |
| `sen-v3.csv.unknown.csv` | 1,378 | the reverse: OEWN nouns Wiktionary has never heard of. All excluded, all marked for a human |
| `sen-v3.csv.variants.csv` | 2,509 | the spelling doublets. **Closed** — every pair ruled in `reviews/variants-reviewed.csv` |
| `sen-v3.csv.variants_ing.csv` | 99 | `-ing` doublets, split out because an `-ing` word is a potential verb first and a spelling second. **Closed** |
| `sen-v3.csv.uk_review.csv` | 0 | UK-flagged words the rules could not resolve. **Empty** |
| `sen-v3.csv.variants_suspect.csv` | 0 | regex-suspect doublets. **Empty** since `VARIANT_RE` was fixed |
| `sen-v3.csv.name_suspect.csv` | small | the name-suspect band; ruled in `reviews/name_suspect-reviewed.csv` |
| `sen-v3.csv.case_variant.csv` | — | the Title-case-`variant_of` band; ruled and folded into `gaps_verdicts.csv` |
| `probe-missing.csv` | varies | the last `probe.py` run's misses, with what each source knows and an empty `verdict` column. Overwritten per run; rule into `reviews/domains/` |
| `variants_review.csv` | 2,509 | the doublet sheet **with its evidence columns** (glosses, zipf, POS, edit distance) — the reviewable form of `reviews/variants-reviewed.csv` |

## How to use a queue

A queue file is a question. Answer it by writing a verdict into a file in `reviews/`, not by
editing the queue — the queue is overwritten on the next run.

`work/sen-v3.csv` is worth opening when a decision looks wrong: it carries `wikt_*` evidence
columns, the corpus counts, the name and plural suspicions and the rule that fired, so a verdict
can be traced without re-running anything.

## What is left open

1. **`gaps-scowl-noun.csv`, 1,473** — gaps words a second curated dictionary independently calls a
   noun. The best remaining vocabulary per row read, and the top 256 rows (SCOWL bands 35–50) are
   the densest part of it.
2. **`gaps-scowl-nonnoun.csv`, 543** — cheap to close: SCOWL names the part of speech, so these can
   be ruled in bulk rather than one at a time.
3. **`gaps-scowl-absent.csv`, 3,678** — two sources' worth of silence. Skimmable, not readable.
4. **`unknown.csv`, 1,378** — SCOWL confirms 239 and has never heard of 1,117, which corroborates
   the existing exclusion. Worth a pass only if the game wants WordNet's specialist tail.

`sen-v3.csv.gaps.csv` is still the file `rank_gaps.py` writes and the three `gaps-scowl-*.csv`
files are cut from it; rule into `reviews/`, never into any of the four.
