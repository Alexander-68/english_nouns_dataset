# `reviews/` — the human rulings

**These files are the authority. Nothing here is generated, and nothing here should ever be
regenerated.** Every other file in the repo can be rebuilt from the dump in about twenty minutes;
these took a person reading words one at a time.

Every reader treats a missing file as "no rulings" rather than an error, so a deleted sheet does
not crash anything — it just silently changes the output. Check the counts after a re-run.

| file | rows | what it rules | read by |
| --- | ---: | --- | --- |
| `gaps_verdicts.csv` | 1,092 | `noun` / `name` / `verb` / `adj` / `noise`, for words **not** in the dataset | `wx_join.py`, `rank_gaps.py` |
| `sen_word_verdicts.csv` | 63 | the same verdicts, for words that **are** in it | `wx_join.py` |
| `variants-reviewed.csv` | 2,509 | `variant` / `reverse` / `plural` / `unrelated`, per spelling doublet | `wx_join.py` |
| `variants_ing-reviewed.csv` | 99 | which side of an `-ing` doublet is British | `wx_join.py` |
| `uk_reviewed.csv` | 157 | words wrongly flagged as British spellings; keep them | `wx_join.py` |
| `name_suspect-reviewed.csv` | 462 | confirmed non-nouns from the name-suspect band | `wx_join.py` |
| `modernvocabularyprobe.csv` | — | human-vetted modern vocabulary; exempt from the frequency cutoff | `wx_join.py`, `rank_gaps.py` |
| `manual-entry.csv` | 145 | words typed in by hand: modern vocabulary no source has, plus four corrections to rows the build gets wrong | `wx_join.py` |
| `domains/initialisms.csv` | 99 | lowercase initialisms, rejected as non-nouns, each with its expansion as the definition | `wx_join.py` |
| `domains/bioinformatics.csv` | 85 | bioinformatics and molecular-biology nouns, plus four file-format names ruled `name` | `wx_join.py` |
| `domains/electronics.csv` | 37 | electronics-engineering nouns no source had ruled | `wx_join.py` |
| `bioinformatics-probe.csv` | 210 | not a ruling sheet: the domain word list `probe.py` found the hole with | `probe.py` |
| `electronics-probe.csv` | 285 | not a ruling sheet: a domain word list to run against a release with `probe.py` | `probe.py` |
| `abbreviation-expansions.csv` | 56 | the words where an abbreviation exclusion is right because the definition IS the expansion | `wx_join.py` |
| `scowl-glosses.csv` | 168 | the SCOWL words no dictionary in the build could gloss: a verdict, and for the 112 ruled `noun`, a definition written by hand | `apply_scowl.py` |
| `manual_reviews.csv` | 3,479 | the **log**: `date, sheet, item, verdict, note` — one line per ruling | nothing; it is the record |

## `manual-entry.csv` is the strongest authority in the build

The other sheets rule on words some queue put in front of a person. This one is the opposite
direction: a person puts the word in. It exists because both sources are dated — OEWN 2025 and a
Wiktionary dump have no `deepfake`, `kombucha`, `microplastic` or `sysadmin` — and no automatic
rule can add a word nobody wrote down.

Same three columns and the same verdict vocabulary. A `noun` here is **playable whatever the rules
say**: it survives the OBSCURE cutoff (`wordfreq` scores `tokenomics` and `lootbox` at 0, being
older than both words) and the missing-from-Wiktionary exclusion (`devops`, `youtuber`, `tiktoker`
have no Wiktionary noun entry), and it overrides an earlier automatic reading — `gamer` was
excluded as an adjective and `spork` as a proper noun. Every other verdict adds a rejected row with
its reason, so a word ruled `noise` answers "not a usable common noun", not "not in the database".
(`usb` and `api` are that case: ruled `noise` here, re-ruled `initialism` by `domains/initialisms.csv`, which is a better reason for the same rejection.)

The `note` column doubles as the gloss: where Wiktionary has no entry to take a definition from,
the sentence written here is what the game shows the player. Write it as a definition, not as an
argument.

It applies to words already in the dataset as well as new ones, which no other sheet does in the
`noun` direction — `sen_word_verdicts.csv` can only exclude.

## `scowl-glosses.csv` — where a definition had to be written, not found

SCOWL contributed 12,148 words the dataset had never seen. 11,980 of them take their definition
from Wiktionary's first sense, like every other row. 168 have no Wiktionary entry at all, and a
word with no gloss cannot be put in front of a player — so each one was read and ruled:

| verdict | rows | what it means |
| --- | ---: | --- |
| `noun` | 112 | a real, if obscure, common noun. The `definition` column is written for it |
| `variant` | 22 | a nonstandard spelling; `suggest_instead` names the standard one |
| `noise` | 22 | SCOWL's own misspellings (`prothalmion`, `hospholipase`, `dateset`), unnaturalised Latin and French (`haeres`, `avion`), function notation (`tanh`, `coth`), one dated slur |
| `name` | 11 | taxonomic genera and proper nouns (`aedes`, `ciliophora`, `medicaid`) |
| `verb` | 1 | `sulfatize` |

Columns: `word, verdict, definition, suggest_instead, marks, note`. `marks` adds a mark to the
resulting row (`possible name`); `note` records why a word was ruled out and is not published.
Definitions are written as definitions — one sentence, no hedging, no argument — because the game
shows them verbatim. A `noun` here is playable whatever the frequency says, the same authority
`manual-entry.csv` has.

## `abbreviation-expansions.csv` — the exception list to a protective rule

`wx_join.py` will not let an abbreviation ruling exclude a word that carries a definition of its
own; see the root README. This sheet is the "unless": the words where the exclusion is right because
the gloss is the expansion rather than a separate sense.

| kind | rows | examples |
| --- | ---: | --- |
| `unit` | 26 | `ft` (foot), `lb` (pound), `mm`, `sec`, `yr`, `mo` (moment), `ms` (manuscript) |
| `letter` | 18 | `f`, `n`, `p`, `v`, `w`, `y`, `eth`, `eng`, `che`, `ge` |
| `clipping` | 11 | `ep` (episode), `univ`, `txt`, `nic`, `tri`, `vt` |
| `inflection` | 1 | `fishes` |

Written by hand because nothing else can do it: `ft` glossed "a linear unit of length equal to 12
inches" and `al` glossed "the Indian mulberry" are both short words with dictionary glosses, and
only a reader knows the first gloss is *foot* and the second is a tree. Add a row here when a new
abbreviation is wrongly rescued; leave it alone otherwise, because the default protects nouns.

## `domains/` — one sheet per subject area

`manual-entry.csv` is general vocabulary. `domains/*.csv` is the same mechanism split by field, so
a specialist list can be added without touching a general one. `wx_join.py` globs the folder, reads
the sheets in filename order **after** `manual-entry.csv`, and adding a field means adding a file —
no code change, no new pipeline stage.

Columns are `word,verdict,note` plus an optional `marks`, whose contents are appended to the row's
marks verbatim.

Two differences from `manual-entry.csv`, both deliberate:

* **The note IS the definition, and it beats Wiktionary.** In `manual-entry.csv` the note is a
  justification for the ruling ("the clipping is the ordinary form"), so Wiktionary's fuller gloss
  is the better text and wins. In a domain sheet the note is written as the definition, so it wins.
  Initialisms are why: Wiktionary glosses lowercase `dna` as "Alternative form of DNA." and `ufo` as
  "A UFO.", which tells a player nothing, where the sheet says "Deoxyribonucleic Acid."
* **A domain sheet overrides a general ruling on the same word.** `usb` and `api` were ruled `noise`
  in `manual-entry.csv` before there was a policy for initialisms; `domains/initialisms.csv` now
  rules them `initialism` and marks them, and the later, more specific sheet wins.

### `domains/initialisms.csv`

102 lowercase initialisms — `usb`, `led`, `pcb`, `dna`, `gps`, `html`, `mosfet`, `fpga`, and
`cgs`, `emf`, `rpm`, which OEWN ships as ordinary rows and the game was offering as playable words.
**None is playable**: the verdict is `initialism`, the reason reads `initialism, not a common noun
(reviewed)`, and each row carries the expansion as its definition so a game can say what the letters
stand for instead of "not in the database". The `initialism` mark is there for a game that wants to
allow them anyway. Initialisms that finished becoming words (`laser`, `radar`, `scuba`) are
playable from their ordinary dictionary rows and are not in this sheet.

Because the note is the expansion rather than a definition, an `initialism` verdict is also fed to
`abbreviation_collision()` as an exception — otherwise the collision rule, which protects `ide` the
fish, would rescue all 99 straight back to playable.

The list is hand-written because no rule can draw the line. SEN is lowercase and the sources file
these under capitals, so the join never saw them; but case-folding wholesale would drag in 8,751
uppercase-only Wiktionary entries whose tail is `AABNCP` and `AACOMS`. `laser` and `radar` finished
becoming words, `usb` is most of the way, `aabncp` never will be, and only a person can say which.

Words already carrying a different real sense are deliberately **left out**: `ram` is a tool and an
animal, `dram` a weight, `prom` a dance, `ide` a fish, `eta` a Greek letter. Adding an initialism
row for those would replace a good definition with a worse one.

### `domains/bioinformatics.csv`

85 rows, from running `reviews/bioinformatics-probe.csv` (210 words, 8 groups) through
`pipeline/probe.py`: 124 playable, 3 wrongly rejected, 83 absent. After the sheet, 205 playable and
0 absent.

Most rows leave `note` empty on purpose. 78 of the 83 absent words were already in Wiktionary with
a usable gloss and were missing only because they fall under the frequency cutoff — `contig`,
`exome`, `spliceosome`, `metagenomics`, `synapomorphy`. An empty note means the row takes
Wiktionary's first sense, so the sheet does not retype 78 definitions to say the same thing. A note
is written only where the source has nothing (`demultiplexing`), where its gloss is a pointer
("Alternative form of side chain") or where it is the wrong sense (`protomer`).

Three rows correct words the build already had and got wrong: `homolog` was excluded as the British
side of the `homolog`/`homologue` doublet (it is the American one), `biostatistics` as an inflected
form (the `-ics` is a field name), `backtracking` as a verb.

Four file formats — `fasta`, `fastq`, `bedgraph`, `newick` — are ruled `name`, not `noun`. They are
format names, so they are not playable, but a player who types one is told what it is rather than
that it does not exist. `crispr` is an acronym and went to `domains/initialisms.csv` instead.

### `domains/electronics.csv`

37 electronics-engineering nouns — `triac`, `memristor`, `optocoupler`, `heatsink`, `snubber`,
`switchgear`. Found by running `reviews/electronics-probe.csv` through `pipeline/probe.py`: 33 were
words Wiktionary had and nothing had ruled, 4 no source had at all.

### `domains/medical_imaging.csv`

45 rows, from running `reviews/medical_imaging-probe.csv` (184 words, 8 groups) through
`pipeline/probe.py`: 135 playable, 8 rejected, 41 absent. After the sheet, 178 playable and 0
absent.

Twenty-two rows leave `note` empty: those words were in Wiktionary with a usable gloss and were
missing only because of the frequency cutoff — `tomosynthesis`, `urography`, `cystography`,
`voxel`, `microbubble`, `echogenicity`, `nephrogram`. A note is written where the source has
nothing (`anechoicity`), where its gloss is a pointer (`backprojection` — "Alternative form of back
projection."; `sonographer` — "Synonym of ultrasonographer"; `volumetry` — "volumetric analysis"),
where it is the wrong sense for the field (`fluence` glossed as "Fluency", `radiopharmacy` as the
administration rather than the preparation of the drugs, `scintigraphy` narrowed to bone injuries)
and where a pair needs telling apart (`hyperdensity`/`hypodensity`, `hyperintensity`/
`hypointensity`, `dephasing`/`rephasing`, `radiolucent`/`radiopaque`).

Four rows correct words the build read as verbs, all of them count nouns in imaging: `aliasing`
(an artifact), `quench` (the boil-off of a magnet's cryogen), `shimming` and `thresholding`
(named techniques), on the same ground as `backtracking` in the bioinformatics sheet. `smoothing`
and `streaking` were left rejected — both are ordinary gerunds outside the field.

`radiolucent` and `radiopaque` are ruled `adj`, so a player who types one is told what it is rather
than that it does not exist. `bucky` and `doppler` were already correctly rejected as proper nouns
and are not re-ruled. `kerma` is an acronym by origin (kinetic energy released per unit mass) but,
like `laser` and `radar`, is written lowercase and used as an ordinary noun, so it is `noun` here
rather than a row in `domains/initialisms.csv`.

### `domains/everyday.csv`

58 rows for a gap that is not a subject area but a **format collision**. The dataset carries no
hyphenated rows at all, and Wiktionary files a good many everyday compounds under the hyphenated
headword: `yo-yo`, `stand-alone`, `sign-up`, `hip-hop`, `sci-fi`, `write-up`. The unhyphenated
spelling a player would type exists in Wiktionary only as "Alternative spelling of yo-yo", so the
variant filter sent it to the gaps queue. Canonical form excluded by format, variant excluded by
rule, and the word fell between them: `yoyo` had no row at all and the game answered "not in the
database".

55 of the rows are the words found that way — every unhyphenated form whose Wiktionary headword is
the hyphenated one. **43 are `noun`** (`yoyo`, `offseason`, `signup`, `warmup`, `shoutout`,
`faceoff`, `hiphop`, `scifi`, `writeup`, `knowhow`, `halfpipe`, `byelection`, `preamp`), **11 are
`adj`** (`standalone`, `midsize`, `freeform`, `braindead`, `nonbinary`, `kneejerk`), `autotune` is
a `name` and `tata` is `noise` — so a player who types one is told what it is.

Every row carries a written definition, which is not optional here: the inherited gloss is
"Alternative form of X" for all 55, which tells a player nothing and names a spelling they cannot
play.

The 56th row is `yule` — an existing row the build had ruled a proper noun, and whose definition
read "Alternative letter-case form of Yule." It is an ordinary common noun for the midwinter
festival, and the sheet gives it both the ruling and the sentence.

`nunchaku` and `nunchuk` (2026-09-01) are the same collision in a different guise: both are below
the frequency cutoff, so neither was ever in the queue, and `nunchuk`'s Wiktionary gloss is
"Alternative form of nunchaku". Both are ruled `noun` with the definition written out.

### `domains/x_words.csv`

193 rows, 181 of them `noun`, all beginning with `x` — `xylitol`, `xanthan`, `xylan`, `xenophile`,
`xeriscape`, `xylocarp`, `xystus`, `xanthopterin`, `xenocurrency`, `xiphopagus`, `xylotomist`,
`xenocracy`, `xylanase`, `xylopolist`. Four are ruled `name` — `xanthium`,
`xylocopa`, `xylophaga`, `xylaria`, `xiphosurida`, `xyletinus`, `xyleborus` and
`xenoceratopsian`, `xylobius` and `xenoceratite` are taxonomic names, and
`xyloid` and `xerarch` are adjectives, so they are not playable, and the sheet says what
they are rather than leaving a player unanswered. Not a subject area but a supply problem: a word-chain game
needs words starting with the letter it most often has to hand off to, and none of these was in the
dataset in any form. Words proposed for the sheet that the dataset already had — `xenotransplant`,
`xerophile`, `xeroradiography`, `xylophonist`, `xerophagy`, `xeranthemum`, `xeroma`, `xerosere`,
`xanthochroism`, `xenogenesis`, `xanthomonad`, `xiphisternum`, `xylosma` — were left out rather
than re-ruled. Every row carries a written definition.

The sheet is **not yet in a release** — it was added for the next build, not applied by re-running
the pipeline.

### `domains/y_words.csv`

64 rows, 63 of them `noun`, all beginning with `y` — the same supply problem as `x_words.csv`, for the
other letter a word-chain game runs short of. 17 were absent from the dataset in any form:
`yaffle`, `yohimbine`, `yardang`, `yatagan`, `yatter`, `yawp`, `yperite`, `yukata`, `yuzu`,
`yerba`, `yoctosecond`, `yttrialite`, `yttrocerite`, `yardland`, `yarner`, `yate`, `yelper`.

Two rows are corrections. `yammer`: the build read it as a verb form, and the noun — a loud
repetitive noise or complaint — is the ordinary sense. `yuletide` was ruled a proper noun and
defined as "Alternative letter-case form of Yuletide"; it is the ordinary word for the Christmas
season, and it follows `yule`, which `domains/everyday.csv` corrected the same way.

Eleven rows leave `note` empty and take Wiktionary's gloss, which is already a usable definition
— `yantra`, `yakiniku`, `yaksha`, `yellowware`, `yersiniosis`, `yuko`, `yair`. The rest are
written, either because no source has the word (`yaji`, `yarchagumba`, `yellowbark`) or because
the gloss is a pointer: "Alternative form of jelick" for `yelek`, "US spelling of yottalitre" for
`yottaliter`, "Work." for `yakka`.

Three rows override a source gloss that points at the wrong thing for a player: Wiktionary makes
`yelper` "a user of Yelp", `yate` an obsolete form of `gate`, and `yatagan` an alternative
spelling of `yataghan` (which the dataset already has playable, so both spellings now work).

Four rows added 2026-09-01, all reported from play and all below the frequency cutoff, so no
queue would ever have carried them: `yabby` (the Australian crayfish — the sheet already had
`yabbie`, which Wiktionary calls an alternative spelling of it, so the variant was in and the
lemma was not), `yomp`, `yuca` and `yutz`. `yack` was reported in the same batch and is not here:
it has a row already, and the fix belonged in `variants-reviewed.csv`.

Thirteen more added 2026-09-02, again all reported from play and all below the cutoff — `yex`,
`yerk`, `yowler`, `yeld`, `yett`, `yowie`, `ypsilon`, `yohimbe`, `youthquake`, `yachtie`,
`yarnbombing`, `yapock`, `yessotoxin`. Five of them exist in Wiktionary only as a pointer at a
spelling the dataset cannot use or does not want to show a player — `yapock` "Alternative spelling
of yapok", `yachtie` "of yachty", `yarnbombing` "of yarn bombing" (two words, and the file has no
spaces), `ypsilon` "of upsilon" — so those carry a written definition. `yeld` is in no source at
all. `yad` came in the same batch and is not here: at zipf 2.47 it was already in the gaps queue,
so it was ruled there.

`yeaning` is the one row that is not a `noun`: it is the bare gerund of `yean`, the act and not a
thing, so it is ruled `verb` and rejected with a reason rather than left unexplained.

### `domains/reported.csv`

The sheet for a word reported from play that belongs to no subject area and no scarce letter:
`earpick`, `nitrox`, `nitpick` (2026-09-02). It exists so the answer to "where does this one go?"
is never "a new sheet for its first letter" — `x_words`, `y_words` and `z_words` are letter sheets
because those three letters are what a chain game runs short of, and there is no supply argument
for `n` or `a`.

Two of the three need their note. `nitrox` has a Wiktionary entry whose first sense is an
industrial case-hardening process, not the diving gas a player means. `nitpick` is in Wiktionary
and SCOWL as a **verb only**, so the noun ("a minor nitpick") rests on the sheet alone — the
weakest evidence any playable row here has, and worth knowing.

### `domains/z_words.csv`

One row: `zax`, the slater's hatchet. Wiktionary has it with a usable gloss and scores it zipf 1.53,
below the cutoff, so it was never in a queue — the same miss as `yabby` and for the same reason, on
the third letter a word-chain game runs short of. The sheet exists so the next `z` word has a home;
`x_words.csv` and `y_words.csv` both started this way.

### `domains/typography.csv`

20 rows, all `noun`. 15 are words no source had — `ogonek`, `kerning`, `interpunct`, `pilcrow`,
`octothorpe`, `monospace`, `manicule`, `guillemet`, `letterform`, `smallcaps`, `sans`, `antiqua`,
`oldstyle`, `caron`.

Five are corrections, and they are why the sheet exists: the dataset had the word with a definition
from another field, which reads as nonsense to anyone who means the typographic sense. `glyph` was
"glyptic art in the form of a symbolic figure", `ligature` "a group of notes connected by a slur",
`ascender` "someone who ascends", `descender` "someone who descends", and `tittle` "a tiny or
scarcely detectable amount". `hinting` was rejected outright as a verb form; font hinting is a
thing, not an act.

`caron` came in from the gaps queue with Wiktionary's gloss, which is the single word "háček" — a
true synonym and a useless definition for a player. That is the case the sheet's note is for.

## The two verdict sheets are not interchangeable

A hand-entry sheet applies both ways: it adds a row for a word the dataset does not have, and it
rules in place on one it does. The second half was missing until 2026-08-31 — a `name`, `adj` or
`initialism` verdict on a word OEWN already ships was read, counted and dropped, which is why `cgs`
stayed playable as "system of measurement based on centimeters and grams" however it was ruled. On
an existing row a domain sheet's note replaces the definition too, so `cgs` now reads
"Centimetre-Gram-Second."

`gaps_verdicts.csv` can only *add* rows — it rules on candidate words the dataset does not have. A
ruling there on a word OEWN already ships does nothing at all. That is why
`sen_word_verdicts.csv` exists: `y`, `t`, `here`, `wynn` and `cozier` are already in the dataset and
needed their existing rows changed.

## Precedence

A ruling beats every automatic flag. Between rulings, **the later and more specific one wins**:
`manual-entry.csv` is the latest sheet and beats all of them. Below it, `uk_reviewed.csv` answers
one narrow question — *is this wrongly flagged as a British spelling?* —
and it was written before the doublet review existed, so an explicit `variants-reviewed.csv` or
verdict-sheet ruling now overrides it. Without that rule the old keep-list was resurrecting `gaol`,
`kerb`, `annexe` and even `t` and `y`.

## Verdict vocabulary

`noun` — an ordinary common noun; add it, or keep it playable.
`name` — a personal name, brand or place.
`verb` / `adj` / `adv` — that part of speech; any noun sense is a nominalisation.
`noise` — a letter name, abbreviation, interjection, foreign word or single obscure sense.

For doublets: `variant` (the `variant` column is the nonstandard spelling), `reverse` (the
`canonical` column is), `plural` (one side is a plural of the other — mark it, never exclude it),
`unrelated` (not a pair at all; drop the link), `both` (a real doublet the game wants on both
sides — playable, and still carrying `spelling variant of <canonical>` as a mark).

`both` is for the pair where US-first does not apply, or applies the other way. `adz` is the
AMERICAN spelling of `adze` — Wiktionary tags `adz` US and tags `adze` nothing — so ruling it
`variant` inverted the project's own policy, and cost the game a word ending in `z`. `whisky` is
the standard spelling for Scotch, Canadian and Japanese whisky and `whiskey` for Irish and
American: a real split, not a nonstandard spelling. `aunty`/`auntie` are both current.
