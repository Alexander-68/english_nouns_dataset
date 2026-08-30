# SEN Dataset v2 — extracted from Open English WordNet 2025

Built 2026-08-27. Replaces `nouns240123.csv` (NLTK Princeton WordNet 3.0, 2006 vintage).

**Source:** Open English WordNet 2025 edition, `english-wordnet-2025.xml.gz`
(GitHub release `2025-edition`), plus `english-wordnet-2025-plus.xml.gz` for the proper-noun split.
**Licence:** CC BY 4.0 — attribution only, no share-alike. Safe to redistribute.
**Reproduce:** `python3 parse_oewn.py <xml.gz> <pkl>` then `python3 build_csv.py`.

## Files

| File | Rows | What it is |
|---|---:|---|
| `oewn2025-nouns.csv` | 42,586 | The playable list — single-token, `^[a-z]+$`. Successor to nouns240123.csv. |
| `oewn2025-nouns-full.csv` | 98,179 | Every noun lemma with reversible filter flags. Nothing deleted. |
| `oewn2025-names.csv` | 25,905 | Proper nouns, from the 2025+ / 2025 delta (Open English Namenet). |

## Columns

`noun` · `start` · `end` · `length` — as before.

**`senses`** — number of WordNet senses. Polysemy is a decent free proxy for commonness: a 6-sense word is everyday, a 1-sense word is usually specialist.

**`lexfile`** — the WordNet lexicographer file: a 26-way supersense assigned by hand by lexicographers (`noun.artifact`, `noun.animal`, `noun.person`, `noun.food`…). This is the classification the 2024 notebook tried to get from spaCy. It was in the source data all along.

**`register`** — derived bucket for the difficulty tiers: `GENERAL` 33,800 · `BIO` 5,075 · `SPECIAL` 1,827 · `MED` 1,361 · `TEC` 523. Computed from `domain` first, then `lexfile` (animal/plant → BIO, body → MED).

**`domain`** — raw `domain_topic` label(s) from OEWN: `medicine`, `chemistry`, `law`, `botany`, `computer science`, `social media` … 404 distinct values, up to 3 per word. Ground truth; `register` is derived from it, so you can re-derive differently.

**`end_pressure`** — demand ÷ supply for the word's final letter, computed over this list. How hard the word is for your opponent to answer. `y` = 29.4 (brutal), `n` = 5.2, `e` = 4.3, `p` = 0.17 (a gift).

**`plural_suspect`** — 460 entries ending in *-s* whose singular is also present. Flagged, not deleted; Wiktextract's countability tags are the proper fix.

**`also_proper_noun`** — 1,042 entries that also exist as proper nouns in Namenet (*amazon*, *atlas*, *bacon*, *babel*). They stay in the list because their common-noun sense is real; the flag lets you exclude them per game rules.

**`in_wn30`** — was this word in the 2024 WordNet 3.0 extraction. 1,171 rows are new.

**`definition`** — first-sense gloss. No empty values.

Flag columns in the `-full` file: `playable` 42,586 · `is_multiword` 49,002 · `has_hyphen` 3,851 · `has_capital` 16,892 · `has_digit` 390 · `has_other_punct` 1,233.

## What changed vs WordNet 3.0

41,415 shared · **1,171 added** · **51 removed**.

Added, characteristically: `coronavirus`, `crowdfunding`, `manga`, `superfood`, `dumpster`, `hotline`, `microsensor`, `badass`, `swiftie`, plus a large batch of feminine and gender-neutral agent nouns (`alderwoman`, `huntswoman`, `plainswoman`, `deliverywoman`) reflecting OEWN's 2024 editorial pass.

Removed, and this is the quality story: nearly all 51 are the exact error classes flagged in the August audit —
- **misspellings corrected**: `fuschia`, `paroxetime`, `flunitrazepan`, `haemitin`, `decentalisation`, `thalmencephalon`, `nitril`, `rijstaffel`
- **proper nouns moved to Namenet**: `cummings`, `saratoga`, `peter`, `oreo`, `ladino`
- **plurals removed**: `deserts`, `tropics`, `pampas`, `amphibia`, `penetralia`, `polyzoa`

## Known limitations — read before using

1. **Modern vocabulary is better but not fixed.** The 68-word spot check went 40/68 → **51/68**. Still absent: *selfie, chatbot, bitcoin, blockchain, wifi, app, broadband, smartwatch, pilates, triathlon, hoodie, ecommerce, earbud, telehealth, microplastic, heatwave*. OEWN is still WordNet lineage and edits conservatively. **Wiktextract remains necessary** for this — it is roadmap step 3, not optional.
2. **`domain` coverage is sparse.** Only ~6,400 synsets carry a `domain_topic` relation, so `TEC` is badly undercounted — `thermocouple` lands in `GENERAL`. Treat `register` as high-precision, low-recall: trust a `MED`/`TEC` tag, do not trust the absence of one.
3. **No age-of-acquisition tier yet.** The 05Y/10Y/50Y axis needs the Kuperman norms joined on lemma. `senses` is the interim proxy. Nothing here was guessed by a language model.
4. **British/American doublets are still separate rows.** OEWN has no variant-linking field exposed here. Wiktextract resolves this.
5. `nan` and `null` are real nouns and are present. Read with `keep_default_na=False, na_values=[]`.
