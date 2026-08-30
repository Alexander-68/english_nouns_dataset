# How to add a domain sheet

A domain sheet is a hand-written list of subject-area words with a verdict on each. It is read by
`pipeline/wx_join.py`, which globs `reviews/domains/*.csv` in filename order **after**
`reviews/manual-entry.csv`, so a domain sheet overrides a general ruling on the same word and a
later sheet overrides an earlier one. Adding a field is adding a file: no code change, no new
pipeline stage. Every row it produces carries `source = domain:<filename-without-.csv>`.

Read `reviews/README.md` first for what the sheets are and why they are the authority. This file is
the procedure and the line-by-line rules.

## The file

`reviews/domains/<field>.csv`, UTF-8, header exactly:

    word,verdict,note,marks

* `word` — lowercase, single word, no spaces, no hyphens, no capitals. One row per word.
* `verdict` — one of the vocabulary below.
* `note` — **the definition**, or empty. See "The note is the definition".
* `marks` — usually empty; appended to the row's `marks` column verbatim.

Sort rows alphabetically by `word`. Quote any note containing a comma. A word that already appears
in an earlier domain sheet should be fixed there, not re-ruled in a new one — the override exists
for correcting `manual-entry.csv`, not for keeping two sheets disagreeing.

## Verdict vocabulary

| verdict | playable? | reason written on the row |
| --- | --- | --- |
| `noun` | **yes** | — |
| `name` | no | `proper noun or other non-noun (reviewed)` |
| `verb` | no | `verb form (reviewed)` |
| `adj` | no | `adjective (reviewed)` |
| `adv` | no | `adverb (reviewed)` |
| `noise` | no | `not a usable common noun (reviewed)` |
| `initialism` | no | `initialism, not a common noun (reviewed)` |

Aliases accepted: `adjective`/`adjectival` → `adj`, `verbal` → `verb`, `proper noun`/`propernoun` →
`name`, `nouns` → `noun`. Anything else is **silently skipped** — a typo in this column loses the
row without an error, so check the added-word count after a re-run.

A `noun` here is playable whatever the automatic rules say: it survives the OBSCURE band, the
missing-from-Wiktionary exclusion and an earlier automatic reading. That is the whole point of the
sheet. Every other verdict still adds a row, so the game can reject the word *with a reason* instead
of saying "not in the database".

## Initialisms

**A word whose letters stand for something is `initialism`, never `noun`.** `mosfet`, `crispr`,
`asic`, `bjt`, `fpga`, `dna` are not common nouns and are not legal answers. Rule them
`initialism`, mark them `initialism`, and write the **expansion** as the note:

    mosfet,initialism,Metal-Oxide-Semiconductor Field-Effect Transistor.,initialism

Put them in `initialisms.csv`, not in the field sheet — that keeps one policy in one place. A field
sheet whose section in `reviews/README.md` notes "`crispr` is an acronym and went to
`domains/initialisms.csv` instead" is the right paper trail.

Three exceptions, all judgement calls no rule can make:

* **Finished words stay out of the sheet entirely.** `laser`, `radar`, `scuba`, `sonar` became
  ordinary nouns and are already playable from their dictionary rows. Adding an initialism row would
  break a good word.
* **A word carrying a different real sense is left out.** `ram` is a tool and an animal, `dram` a
  weight, `prom` a dance, `ide` a fish, `eta` a Greek letter. An initialism row would replace a good
  definition with a worse one.
* **Borderline cases go in.** `usb` is most of the way to being a word and is still ruled
  `initialism`; the `initialism` mark exists so a game that disagrees can allow them all with one
  filter.

## Likely non-nouns

Same principle: **rule it and let it be rejected with a reason. Do not leave it out.** A word left
out of the sheet is a word the game cannot explain.

* An `-ing` form that is the act, not a thing — rule `verb`, unless the field genuinely uses it as a
  count noun. `backtracking` and `basecalling` are `noun` in `bioinformatics.csv` because they name
  techniques; a bare gerund of an ordinary verb is not.
* A word that only ever modifies something — `adj`. If the noun sense is a nominalisation
  ("the digitals"), it is still `adj`.
* File formats, protocols, tools, standards, organisations, taxonomic genera, brands — `name`.
  `fasta`, `fastq`, `bedgraph`, `newick` are `name` for exactly this reason: not playable, but a
  player who types one is told what it is.
* Symbols, unit abbreviations, letter names, clippings that never became words — `noise`.
* Anything you would not accept from an opponent in the game — not `noun`. Where the field's own
  usage is a verb or an adjective and the noun reading exists only in a dictionary, the honest
  verdict is `verb`/`adj`.

If you cannot decide, rule the conservative verdict and say why in the note. A wrongly rejected word
is a marked row someone can find; a wrongly playable one is a bad answer in a game.

## The note is the definition

In `manual-entry.csv` the note argues for the ruling and Wiktionary's fuller gloss wins. **In a
domain sheet the note IS the definition and it beats Wiktionary.** So:

* Write one sentence, as a definition. No hedging, no argument, no "probably", no "see also". The
  game shows it to a player verbatim.
* **Leave it empty when Wiktionary already has a usable gloss.** An empty note means the row takes
  Wiktionary's first sense, which is right for most rows: 78 of the 83 absent words in
  `bioinformatics.csv` were missing only because of the frequency cutoff, and the sheet does not
  retype 78 definitions to say the same thing.
* Write one only where the source has nothing, where its gloss is a pointer ("Alternative form of
  side chain"), or where it is the wrong sense for the field.
* For an `initialism`, the note is always the expansion, capitalised as the expansion is, ending in
  a full stop.
* For a `name` or a corrected row, a note is worth writing even where Wiktionary has a gloss — it is
  what the player is shown when the word is refused.

## Marks

Leave empty unless there is a specific mark to add. `initialism` is the only one a domain sheet uses
today. Whatever is written here is appended to the row's `marks` verbatim, so it must be a mark a
game can filter on, not a comment.

## Procedure for a new field

1. **Write a probe list.** `reviews/<field>-probe.csv` — the field's vocabulary, lowercase, single
   words, no duplicates. `probe.py` asserts all three and fails early rather than quietly dropping
   rows.
2. **Run it against the current release.**

   ```bash
   python pipeline/probe.py reviews/<field>-probe.csv --out work/probe-<field>.csv
   ```

   Every word lands in one bucket: `playable`, `rejected` (with the reason — often correct), or
   `absent`. For each absent word the report says what the upstream sources know, which decides the
   fix: SCOWL or Wiktionary has it (the join missed it, or the size cut hid it), Wiktionary only
   (a gaps-queue ruling away), uppercase only (an initialism), neither (too new or too specialist —
   a hand row).
3. **Rule the absent words and the wrongly rejected ones** into `reviews/domains/<field>.csv`.
   A rejection is not automatically a bug: `pcb` really is an abbreviation, `si` really is a symbol.
4. **Re-run the join and re-probe.** Absent should reach 0; check the printed
   `domain:<field>:<n>` count matches the number of rows you wrote — a smaller count means a row was
   skipped for an unrecognised verdict.
5. **Log the rulings** in `reviews/manual_reviews.csv` (`date, sheet, item, verdict, note`) and add
   a short section for the sheet to `reviews/README.md`: how many rows, where they came from, and
   any row that corrects something the build got wrong.

## Corrections belong here too

A domain sheet is the right place to fix a word the build read wrongly, and each such row is worth a
note saying what was wrong: `homolog` excluded as the British side of a doublet (it is the American
one), `biostatistics` excluded as an inflected form (the `-ics` is a field name), `backtracking`
excluded as a verb. These are the highest-value rows in a sheet — they fix a live error, not just a
gap.
