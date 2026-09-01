#!/usr/bin/env python3
"""
wx_join.py — join the Wiktextract noun table onto the OEWN 2025 SEN dataset.

Produces seven files:

  <out>                      v3 dataset: v2.1 + Wiktionary evidence columns
                             + a `recommended` verdict per word
  <out>.gaps.csv             nouns Wiktionary has that OEWN lacks, frequency
                             ranked — the candidate-additions list
  <out>.variants.csv         British/American and other spelling doublets where
                             both members are in the dataset
  <out>.variants_ing.csv     doublets where either side is an -ing form — a
                             potential verb first, a spelling variant second
  <out>.variants_suspect.csv doublets whose only evidence is the loose gloss
                             regex (variant_kind == 'spelling'); mostly noise
  <out>.uk_review.csv        UK/British-region-flagged words that could not be
                             auto-resolved as a spelling variant — manual
                             review queue, not an answer (see below)
  <out>.unknown.csv          SEN nouns Wiktionary has no entry for at all —
                             the inverse of the gaps file. All excluded from
                             the dataset by project decision; this file is the
                             audit trail of what that decision removed.

Usage
-----
    python3 wx_join.py oewn2025-nouns-v2.1.csv wiktionary-nouns.csv sen-v3.csv

Requires: pandas, wordfreq, lemminflect
    (pip install pandas wordfreq lemminflect)

What each verdict means
-----------------------
`recommended` is True when the word is a defensible Word Chain answer:
  * Wiktionary does not call it an inflected form of something else
  * Wiktionary does not call it plural-only
  * it is not flagged as a plural of another listed word
  * its frequency tier is not OBSCURE
  * Wiktionary has an entry for it at all (project decision, 2026-08-29 --
    see `.unknown.csv` below)
  * it is not a British/Commonwealth spelling variant of another listed word
    (see below — the American spelling is kept, the British one excluded)
A human keep-list (`UK_REVIEWED_PATH`, the outcome of the manual
`.uk_review.csv` pass) overrides all of the above: a word on it is
`recommended` whatever the automatic rules say, and carries `human_kept`.
Everything else stays in the file with the evidence attached, so you can
re-derive a different rule without re-running anything.

Why rejected words are kept
---------------------------
This dataset is a rejection-reason lexicon, not a filtered word list. A word
being absent and a word being disallowed are different facts, and only the
second one can be explained to a player. So words that are NOT valid answers
are kept as rows carrying the reason:

    "not allowed -- this is most probably a name"        (name_suspect)
    "not allowed -- British spelling, use `plow` instead" (suggest_instead)

rather than being dropped, which leaves a game able to say only "not in the
database". Two columns carry it: `excluded_because` names the reason, and
`suggest_instead` names the replacement where one exists (populated for every
British/Commonwealth variant). This is also why reviewed proper nouns are
ADDED to the dataset from the gaps queue rather than discarded -- see
NAME_SUSPECT_REVIEWED_PATH.

Rows are therefore not all OEWN nouns any more; `source` says where each came
from (`oewn2025` or `gaps-name-review`).

British/American spelling variants
-----------------------------------
Wiktionary's `variant_of` field is a regex over the gloss text, not a
structured field (see WIKTEXTRACT-JOIN-REPORT.md) — it also catches
unrelated word pairs the regex mismatched (e.g. "beach" -> "bitch", an
extraction artifact, not a spelling variant). Region tags alone (`UK`,
`British`) are not enough evidence either.

So a row is only auto-excluded as a British/Commonwealth variant when ONE of:
  (a) Wiktionary itself editorially tags it `british` or `commonwealth`
      (a deliberate human tag, trusted outright — e.g. "grey" -> gray), or
  (b) its region is UK/British-only AND it matches a known, well-documented
      BrE -> AmE spelling correspondence (`UK_US_SUFFIXES` below, plus the
      ae/oe -> e digraph reduction) — e.g. "colour" -> color, "organisation"
      -> organization, "encyclopaedia" -> encyclopedia.
A mirror-image case is also handled: some words carry no tag themselves but
are pointed at by an editorially-tagged American row (e.g. "tranquillity"
is plain, but "tranquility" says "American spelling of tranquillity") —
those get excluded too, recorded in `wikt_american_equivalent`.

Anything UK/British-region-flagged that matches neither test — no editorial
tag, no recognised pattern — is NOT excluded automatically. It goes to
`<out>.uk_review.csv` for a human to accept or reject case by case, exactly
like `variants.csv` already works for the rest of the alt-spelling data.
"""
import os
from collections import Counter
import sys, re
import pandas as pd

from rank_gaps import (load_pos_dominance, load_wikt_pos,
                       lowercase_common_noun)

# Human-vetted modern vocabulary. Words listed here are exempt from the gaps
# frequency cutoff (see the gaps section below). Missing file is not an error.
PROBE_PATH = 'reviews/modernvocabularyprobe.csv'

# Outcome of the manual pass over `.uk_review.csv`: nouns a human decided
# belong in the dataset. Kept regardless of what the automatic rules say, on
# the same principle PROBE_PATH already uses -- a human who looked at the word
# outranks a derived rule. Missing file is not an error.
UK_REVIEWED_PATH = 'reviews/uk_reviewed.csv'

# Outcome of the manual pass over `.variants_ing.csv` (97 doublets, ruled
# 2026-08-29). Columns: variant, canonical, verdict, note. The verdict names
# which SIDE is British, which is the one thing the automatic rules could not
# work out for this family: Wiktionary tags `modelling` -> `modeling` as
# regional but leaves `colouring` -> `coloring` and `counselling` ->
# `counseling` with no region at all, so both sides were being recommended.
#     british       -> `variant` is the British spelling, `canonical` the American
#     american      -> the reverse: `canonical` is the British one
#     spelling_pair -> a real doublet with no regional direction; keep both
#     noise         -> not a variant pair at all; the gloss regex mispaired them
ING_REVIEWED_PATH = 'reviews/variants_ing-reviewed.csv'

# Outcome of the manual pass over `.variants.csv` (2,509 doublets, ruled
# 2026-08-29). Same shape as the -ing sheet and the same four verdicts:
#     variant   -> the `variant` column is the nonstandard spelling; exclude
#                  it and point it at `canonical`
#     reverse   -> the other way round
#     plural    -> one side is a plural of the other (stoke/stokes,
#                  pamper/pampers); mark it, do not exclude it
#     unrelated -> the pair is gloss-regex noise (wild/weald, car/cat); drop
#                  the link so no later rule acts on it
VARIANTS_REVIEWED_PATH = 'reviews/variants-reviewed.csv'

# Rulings on words that are ALREADY in the dataset -- as opposed to
# `gaps_verdicts.csv`, which rules on candidates that are not. Both sheets
# use the same verdict vocabulary; this one exists because a verdict on an
# existing row has to change that row rather than add one.
SEN_VERDICTS_PATH = 'reviews/sen_word_verdicts.csv'

# Outcome of the manual pass over the gaps `name_suspect` band: words a human
# confirmed are NOT common nouns -- proper nouns (people, places, trade names)
# plus a few adjectives and verbs. They are ADDED to the dataset rather than
# left out; see "Why rejected words are kept" in the module docstring.
NAME_SUSPECT_REVIEWED_PATH = 'reviews/name_suspect-reviewed.csv'

# Individual rulings on gap candidates (see rank_gaps.py). Every verdict other
# than `noun` names a word that is not a valid answer, so those words join the
# dataset carrying that reason -- the rejection-reason principle again.
VERDICTS_PATH = 'reviews/gaps_verdicts.csv'
# Words whose exclusion note says "abbreviation" or "initialism" AND whose
# definition really is the expansion, so the exclusion is right. See
# abbreviation_collision() -- this file is the exception list to that rule, and
# it is small on purpose: unit symbols, letter names, and clippings glossed by
# the word they clip.
ABBREV_EXPANSIONS_PATH = 'reviews/abbreviation-expansions.csv'
# An exclusion note that turns on the word being short rather than on what it
# means. These are the rulings abbreviation_collision() re-examines.
ABBREV_NOTE_RE = re.compile(r'initialis|initializ|acronym|abbreviat', re.I)
# A gloss that only points at another form, and so is not a definition of
# anything: "Initialism of ...", "Clipping of ...", "Alternative form of ...".
STUB_GLOSS_RE = re.compile(
    r'^\s*(initialism|acronym|abbreviation|alternative\s+(letter-case\s+)?form'
    r'|alternative\s+spelling|clipping|short\s+for)\b', re.I)

# Words entered by hand rather than found by any queue: modern vocabulary the
# 2025 sources simply do not have (`deepfake`, `kombucha`, `sysadmin`), plus a
# few rulings on words the dataset already has and gets wrong. Same three
# columns and the same verdict vocabulary as the sheets above.
#
# It is the strongest authority in the build, and deliberately so -- a person
# typing a word into this file has looked at that word, which no derived rule
# has. A `noun` here is playable whatever the rules say: it survives the
# OBSCURE cutoff (`wordfreq` has never heard of `doomscrolling` either) and the
# missing-from-Wiktionary exclusion. Every other verdict adds or corrects a
# REJECTED row, so the game can say what the word is instead of not knowing it.
MANUAL_ENTRY_PATH = 'reviews/manual-entry.csv'
# One sheet per subject area, all read the same way as MANUAL_ENTRY_PATH and
# all applied after it, so a later domain sheet can correct an earlier general
# ruling. Adding a field means adding a file here and nothing else -- no code
# change, no new stage. Sheets take `word,verdict,note` and an optional
# `marks` column that the general sheet does not have.
DOMAIN_SHEETS_GLOB = 'reviews/domains/*.csv'
# Verdict spellings are normalised so a hand-edited file is not silently
# ignored: `adjective` and `adj` mean the same thing, as do `proper noun` and
# `name`. Unknown values are left as-is and simply match no rule.
VERDICT_ALIASES = {'adjective': 'adj', 'adjectival': 'adj', 'verbal': 'verb',
                   'proper noun': 'name', 'propernoun': 'name', 'nouns': 'noun'}


def load_abbrev_rulings(paths=(VERDICTS_PATH, SEN_VERDICTS_PATH, MANUAL_ENTRY_PATH)):
    """Words excluded by a ruling whose stated reason was "it is an abbreviation".

    Read out of the note column, not inferred: only a sheet that says so counts.
    """
    out = set()
    for path in paths:
        try:
            m = pd.read_csv(path, keep_default_na=False, na_values=[])
        except FileNotFoundError:
            continue
        if 'note' not in m.columns:
            continue
        for word, verdict, note in zip(m['word'], m['verdict'], m['note']):
            if (normalise_verdict(verdict) != 'noun'
                    and ABBREV_NOTE_RE.search(str(note))):
                out.add(str(word).strip().lower())
    return out


def load_abbrev_expansions(path=ABBREV_EXPANSIONS_PATH):
    try:
        return set(pd.read_csv(path, keep_default_na=False,
                               na_values=[])['word'].str.strip().str.lower())
    except (FileNotFoundError, KeyError):
        return set()


def abbreviation_collision(sen, abbrev_ruled, expansions):
    """Protect a real noun from being excluded for being spelled like an initialism.

    A short word can be two things at once, and the dataset kept losing the
    better one. `ide` is a freshwater fish of the Cyprinidae AND an initialism
    for Integrated Development Environment; it was excluded as "not a usable
    common noun" while still carrying the fish gloss, so the game could neither
    play it nor explain it. `wat` (a Buddhist temple), `sai` (a martial-arts
    weapon), `zhou` (rice porridge), `xu` (a Vietnamese coin) and 150-odd others
    were lost the same way.

    The rule, in one line: **an abbreviation ruling may not exclude a word that
    carries a definition of its own.** It applies when all three hold --

      1. the word was excluded by a ruling whose note said abbreviation or
         initialism (`load_abbrev_rulings`, read from the sheets, never guessed),
      2. the row carries a definition that is not a pointer to another form
         (`STUB_GLOSS_RE`: "Initialism of ...", "Clipping of ..." are not
         definitions),
      3. the word is not in `abbreviation-expansions.csv`.

    Point 3 is the "unless" the rule needs, and it cannot be automated: `ft` is
    glossed "a linear unit of length equal to 12 inches", which IS what the
    abbreviation stands for, while `al` is glossed "the Indian mulberry", which
    is not. Both are three letters with a dictionary gloss and no string test
    separates them. So the exceptions are listed by hand -- unit symbols, letter
    names, and clippings glossed by the word they clip -- and everything else is
    protected by default. That default is the point: the failure being fixed is
    a real noun going missing, and a wrongly kept abbreviation is merely a
    marked row a game can filter.

    Returns the rescued words. Their rows keep the definition they already had,
    and gain the `possible abbreviation or clipping` mark.
    """
    protected = (sen['noun'].isin(abbrev_ruled)
                 & ~sen['noun'].isin(expansions)
                 & (sen['definition'].str.strip() != '')
                 & ~sen['definition'].str.match(STUB_GLOSS_RE))
    sen.loc[protected, 'verdict_reason'] = ''
    return set(sen.loc[protected, 'noun'])


def load_manual_entries(path=MANUAL_ENTRY_PATH, domains=DOMAIN_SHEETS_GLOB):
    """(verdict, note, marks, source) per word, from every hand-entry sheet.

    The note doubles as the gloss: these words often have no Wiktionary entry
    to take a definition from, and a row the game shows a player is better off
    with the sentence the person who added it wrote. For an initialism the note
    is the expansion -- `usb` -> "Universal Serial Bus." -- which is the only
    thing a player can be shown that is any use at all.

    `reviews/manual-entry.csv` is read first and every `reviews/domains/*.csv`
    after it, in filename order, so a subject-area sheet overrides a general
    ruling on the same word. That is how `usb` and `api` stop being rejected
    initialisms and become playable ones: the general sheet ruled them `noise`
    before there was a policy for initialisms, and `domains/initialisms.csv`
    now rules them `noun` and marks them.

    A missing file or a missing folder is not an error, as everywhere else.
    """
    import glob
    verdicts, notes, marks, source = {}, {}, {}, {}
    sheets = [(path, 'manual-entry')]
    sheets += [(p, 'domain:' + os.path.splitext(os.path.basename(p))[0])
               for p in sorted(glob.glob(domains))]
    for sheet, label in sheets:
        try:
            m = pd.read_csv(sheet, keep_default_na=False, na_values=[])
        except FileNotFoundError:
            continue
        has_marks = 'marks' in m.columns
        for i, (word, verdict, note) in enumerate(zip(m['word'], m['verdict'],
                                                      m['note'])):
            verdict = normalise_verdict(verdict)
            if verdict not in VERDICT_REASON:
                continue
            word = str(word).strip().lower()
            verdicts[word] = verdict
            notes[word] = str(note).strip()
            marks[word] = str(m['marks'].iloc[i]).strip() if has_marks else ''
            source[word] = label
    return verdicts, notes, marks, source


def normalise_verdict(v):
    v = str(v).strip().lower()
    return VERDICT_ALIASES.get(v, v)


# verdict -> (exclusion reason, pos_overlap mark). An empty reason means the
# word is PLAYABLE: a human read it and said it is an ordinary common noun
# that OEWN simply does not have. That is how modern vocabulary -- `app`,
# `download`, `selfie`, `blockchain`, `cybersecurity`, `midfielder` -- gets
# into the dataset at all; every other verdict adds a row the game can reject
# with a reason instead of failing to recognise the word.
VERDICT_REASON = {
    'noun':  ('', ''),
    'name':  ('proper noun or other non-noun (reviewed)', ''),
    'verb':  ('verb form (reviewed)', 'verb (reviewed)'),
    'adj':   ('adjective (reviewed)', 'adjective (reviewed)'),
    'adv':   ('adverb (reviewed)', 'adverb (reviewed)'),
    'noise': ('not a usable common noun (reviewed)', ''),
    # A lowercase initialism (`pcb`, `mosfet`, `usb`): kept as a row so the
    # game can expand it, never playable. Its note IS the expansion, which is
    # why load_initialisms() feeds abbreviation_collision's exception list --
    # otherwise the collision rule would rescue every one of them straight back.
    'initialism': ('initialism, not a common noun (reviewed)', ''),
}


def tier(z):
    """Frequency tier, same thresholds as enrich.py."""
    if z >= 5.0: return 'CORE'
    if z >= 4.0: return 'COMMON'
    if z >= 3.0: return 'FAMILIAR'
    if z >= 2.0: return 'UNCOMMON'
    if z >  0.0: return 'RARE'
    return 'OBSCURE'

# ---------------------------------------------------------------------------
# British -> American spelling-variant detection.
# Closed, citable list of well-documented BrE -> AmE suffix correspondences.
# Order matters: longer/more specific suffixes are checked first.
# ---------------------------------------------------------------------------
UK_US_SUFFIXES = [
    ('isation', 'ization'), ('isability', 'izability'), ('iser', 'izer'),
    ('isable', 'izable'), ('yse', 'yze'), ('yser', 'yzer'),
    ('ogue', 'og'), ('ence', 'ense'), ('our', 'or'), ('re', 'er'),
]


# ---------------------------------------------------------------------------
# Second-pass BrE -> AmE evidence, applied ONLY to the `.uk_review.csv` residue
# (UK-region-tagged rows the primary UK_US_SUFFIXES test could not resolve).
# Kept separate from UK_US_SUFFIXES on purpose: several of these patterns are
# broad enough (`ll->l`, `ou->o`, `e->`) to misfire if let loose on the whole
# dataset, and the primary rule's 174 auto-exclusions are already settled. Here
# they are safe, because the residue is 64 hand-inspected rows that a human has
# already ruled on -- the American side of every pair is in UK_REVIEWED_PATH.
#
# Substitution may occur anywhere in the word, not just the suffix: "coloured"
# -> "colored" and "ploughman" -> "plowman" are stem-internal.
# ---------------------------------------------------------------------------
UK_US_RESIDUE_SUBS = [
    ('ough', 'ow'), ('quer', 'cker'), ('xion', 'ction'), ('centre', 'center'),
    ('mme', 'm'), ('our', 'or'), ('gg', 'g'), ('ph', 'f'), ('sc', 'sk'),
    ('gh', 'g'), ('ll', 'l'), ('ou', 'o'),
]

# Irregular BrE/AmE doublets with no derivable pattern. A closed, hand-checked
# list, in the same spirit as rank_gaps.py's CLOSED_CLASS and
# IRREGULAR_VERB_FORMS: each entry was read against both dictionaries.
UK_US_IRREGULAR = {
    'beigel': 'bagel', 'cypher': 'cipher', 'enquiry': 'inquiry',
    'fount': 'font', 'furore': 'furor', 'gipsy': 'gypsy', 'gramme': 'gram',
    'hullo': 'hello', 'kiddy': 'kiddie', 'macintosh': 'mackintosh',
    'pedlar': 'peddler', 'pewit': 'peewit', 'plough': 'plow', 'soya': 'soy',
    'speciality': 'specialty', 'swathe': 'swath',
    'tranquilliser': 'tranquilizer', 'whizz': 'whiz', 'yack': 'yak',
}


def uk_us_residue_pattern(word, canonical, have_nouns=frozenset()):
    """Second-pass BrE->AmE match for the uk_review residue, or None.

    Returns the rule that fired, so every exclusion is traceable to a named
    correspondence rather than a similarity score. A fuzzy string-distance
    test was tried first and rejected: at any threshold it both accepted real
    word pairs ("broach"/"brooch", "frank"/"franc", "chapiter"/"chapter") and
    rejected genuine spellings ("plough"/"plow", "chequer"/"checker",
    "pedlar"/"peddler"), because BrE/AmE distance and semantic distance are
    unrelated quantities.
    """
    american = UK_US_IRREGULAR.get(word)
    if american == canonical:
        return 'irregular pair'
    # The hand-curated table outranks a bad `variant_of`. "plough" is the case
    # that forced this: the gloss regex made its canonical "snowplough", not
    # "plow", so the pair never matched -- while "ploughman", "ploughwoman",
    # "ploughwright" and "snowplough" all resolved normally. If the table names
    # an American form and that form is itself a dataset row, trust the table.
    if american and american in have_nouns:
        return 'irregular pair (canonical from table)'
    for uk, us in UK_US_RESIDUE_SUBS:
        if uk in word and word.replace(uk, us, 1) == canonical:
            return f'{uk}->{us}'
    return None


def uk_us_pattern(word, canonical):
    """Return the matched BrE->AmE suffix pattern name, or None."""
    for uk_suf, us_suf in UK_US_SUFFIXES:
        if (word.endswith(uk_suf) and canonical.endswith(us_suf)
                and word[:-len(uk_suf)] == canonical[:-len(us_suf)]):
            return f'{uk_suf}->{us_suf}'
    if word.replace('ae', 'e') == canonical or word.replace('oe', 'e') == canonical:
        return 'ae/oe->e'
    return None


def region_is_britishy(regions):
    toks = set(t for t in regions.split(';') if t)
    return bool(toks) and toks.issubset({'UK', 'British'})


try:
    from lemminflect import getAllLemmas
except ImportError:
    getAllLemmas = None

POS_WORD = {'ADJ': 'adjective', 'VERB': 'verb', 'ADV': 'adverb'}


def gap_candidates(wx, have):
    """Wiktionary nouns the dataset lacks -- the shared candidate filter.

    Used twice: once to auto-classify non-nouns into the dataset, once to write
    gaps.csv. One definition so the two can never drift apart.
    """
    return wx[(~wx['word'].isin(have))
              & (wx['word'].str.match(r'^[a-z]+$', na=False))
              & (wx['is_inflected_form'] == 0)
              & (wx['plural_only'] == 0)
              & (~wx['variant_of'].isin(have - {''}))].copy()


def not_a_noun(word):
    """('adjective (not a noun)', 'ADJ', lemma) when lemminflect knows the word
    and has no NOUN reading for it, else None.

    Only the lexicon's own verdict is used here -- never the suffix heuristic.
    These words are written into the dataset automatically, and a morphological
    guess is not evidence enough for that; it stays a tag on the gaps queue.
    """
    tags = getAllLemmas(word) if getAllLemmas else {}
    if not tags or 'NOUN' in tags:
        return None
    others = [POS_WORD[t] for t in ('ADJ', 'VERB', 'ADV') if t in tags]
    if not others:
        return None
    lemma = next(iter(tags.values()))[0]
    return ('/'.join(others) + ' (not a noun)', ';'.join(sorted(tags)),
            lemma if lemma != word else '')


# Corpus marks are advisory, so the bar is lower than the flag in
# rank_gaps.py -- but still high enough that a handful of tokens cannot
# produce a mark on a perfectly ordinary noun.
CORPUS_MARK_MIN_N = 10
CORPUS_MARK_MAX_NOUN_SHARE = 0.20
CORPUS_MARK_WORD = {'ADJ': 'an adjective', 'VERB': 'a verb', 'ADV': 'an adverb',
                    'PROPN': 'a name'}


def corpus_mark(d, wordnet_noun=False):
    """'usually a name (corpus)' & co. from one pos-dominance row, or ''.

    The PROPN case is not symmetrical with the others. `federal` tagged ADJ is
    the word `federal` being an adjective; `Ray` tagged PROPN is a DIFFERENT
    word that the lowercased table folded into this row. So the name mark is
    withheld on either of two kinds of counter-evidence:

      * the corpus shows the word in lowercase common-noun use --
        `lowercase_common_noun`, which covers `ray`, `ruby`, `china`, `pearl`;
      * WordNet has a common-noun sense for it (`wordnet_noun`, i.e. the row
        has a lexfile). `sparrow` is a bird, `berlin` is a limousine, `john`
        is a toilet and `mike` is a microphone -- 230 capitalised `Sparrow`s
        in a corpus are Jack Sparrow, and say nothing about the bird. Names
        live in NameNet, not in the noun lexfiles, so a lexfile IS the
        dictionary saying "common noun".

    Name doubt for those words is not lost: it belongs to `possible name`,
    which comes from an actual name list. 96 of the 184 carry it already, and
    the rest are that list's documented recall gap, not this mark's business.

    `adam`, `alaska`, `santa` and `joe` have neither kind of counter-evidence
    and keep the mark.
    """
    if d is None or d.n < CORPUS_MARK_MIN_N:
        return ''
    usually = CORPUS_MARK_WORD.get(d.dominant)
    if not usually or d.noun_share > CORPUS_MARK_MAX_NOUN_SHARE:
        return ''
    if d.dominant == 'PROPN' and (wordnet_noun or lowercase_common_noun(d)):
        return ''
    return f'usually {usually} (corpus)'


def main(sen_path, wikt_path, out_path):
    sen = pd.read_csv(sen_path, keep_default_na=False, na_values=[])
    wx  = pd.read_csv(wikt_path, keep_default_na=False, na_values=[])
    sen['name_suspect'] = False
    sen['pos_overlap'] = ''
    sen['pos_tags'] = ''
    sen['lemma'] = ''
    sen['verdict_reason'] = ''
    sen['source'] = 'oewn2025'

    # ---- reviewed name suspects join the dataset as rejectable rows -------
    # These are words Wiktionary has and OEWN lacks, which a human confirmed
    # are not common nouns. Adding them (rather than leaving them out) is what
    # lets the game answer "not allowed, this is probably a name" instead of
    # "not in the database". Evidence comes from the Wiktionary table; the
    # OEWN-only columns have no value for them and are left empty.
    tags = {}
    try:
        for x in pd.read_csv(NAME_SUSPECT_REVIEWED_PATH, keep_default_na=False,
                             na_values=[]).iloc[:, 0].str.strip():
            if x:
                tags.setdefault(x, 'name')
    except FileNotFoundError:
        pass
    try:
        v = pd.read_csv(VERDICTS_PATH, keep_default_na=False, na_values=[])
        for word, verdict in zip(v['word'], v['verdict']):
            verdict = normalise_verdict(verdict)
            if verdict in VERDICT_REASON:
                tags[word.strip()] = verdict
    except (FileNotFoundError, KeyError):
        pass

    # Hand-entered words, read last so they win among the verdict sheets.
    manual, manual_notes, manual_marks, manual_source = load_manual_entries()
    tags.update(manual)
    existing = set(sen['noun'])

    # ---- auto-classified non-nouns join too -------------------------------
    # Project rule (2026-08-29): words that are adjectives, verbs or adverbs
    # and NOT nouns are still added, marked with what they actually are, so the
    # game can answer "'pretty' is an adjective" instead of "not in the
    # database". Only lemminflect's own verdict qualifies a word for this --
    # the suffix heuristic in rank_gaps.py is a tag on the queue, never grounds
    # for writing a row. A human verdict already recorded always wins.
    auto = {}
    if getAllLemmas is not None:
        wx_dedup = wx.drop_duplicates(subset='word', keep='first')
        for word in gap_candidates(wx_dedup, existing)['word']:
            if word in tags:
                continue
            hit = not_a_noun(word)
            if hit:
                auto[word] = hit
        print(f'auto-classified non-nouns (lemminflect): {len(auto):,}')

    suspects = [x for x in tags if x not in existing] + list(auto)
    if suspects:
        from wordfreq import zipf_frequency as _zipf
        wx_first = wx.drop_duplicates(subset='word', keep='first').set_index('word')
        rows = []
        for word in suspects:
            z = round(_zipf(word, 'en'), 2)
            ev = wx_first.loc[word] if word in wx_first.index else None
            rows.append({
                'noun': word, 'start': word[0], 'end': word[-1], 'length': len(word),
                'zipf': z, 'tier': tier(z),
                'senses': int(ev['n_senses']) if ev is not None else 0,
                'lexfile': '', 'register': '', 'domain': '',
                # end_pressure is demand/supply over the playable list; these
                # rows are never playable, so it is left at 0 rather than
                # recomputed, which would shift every existing value.
                'end_pressure': 0.0,
                'plural_suspect': False, 'plural_of_listed': False,
                'no_distinct_plural': False, 'also_proper_noun': False,
                'in_wn30': False,
                # A domain sheet's note IS the definition and wins over
                # Wiktionary; `manual-entry.csv`'s note is a justification for
                # the ruling ("the clipping is the ordinary form") and does
                # not, so there Wiktionary's gloss is still the better text.
                # The difference matters most for initialisms: Wiktionary
                # glosses lowercase `dna` as "Alternative form of DNA." and
                # `ufo` as "A UFO.", which tells a player nothing, where the
                # sheet says "Deoxyribonucleic Acid."
                'definition': (manual_notes[word]
                               if manual_source.get(word, '').startswith('domain:')
                               and manual_notes.get(word)
                               else ev['first_gloss'] if ev is not None
                               else manual_notes.get(word, '')),
                'name_suspect': tags.get(word) == 'name',
                'pos_overlap': (VERDICT_REASON[tags[word]][1] if word in tags
                                and tags[word] != 'name' else
                                auto[word][0] if word in auto else ''),
                'pos_tags': auto[word][1] if word in auto else '',
                'lemma': auto[word][2] if word in auto else '',
                'verdict_reason': (VERDICT_REASON[tags[word]][0] if word in tags
                                   else auto[word][0]),
                'source': (manual_source[word] if word in manual else
                           'gaps-review' if word in tags else 'pos-auto'),
            })
        sen = pd.concat([sen, pd.DataFrame(rows)], ignore_index=True)
        by_sheet = Counter(r['source'] for r in rows
                           if r['source'] == 'manual-entry'
                           or r['source'].startswith('domain:'))
        print(f'hand-entered words added: {sum(by_sheet.values()):,} '
              f'of {len(manual):,} ruled across all sheets'
              + (' -> ' + ', '.join(f'{k}:{n}' for k, n in sorted(by_sheet.items()))
                 if by_sheet else ''))
        added = pd.Series([tags.get(r['noun'], '') for r in rows])
        print(f'reviewed gap words added: {len(rows):,}'
              + (' -> ' + ', '.join(f'{k}:{int(n)}' for k, n
                                    in added.value_counts().items())
                 if len(added) else ''))
    # Outcome of the manual .uk_review.csv pass, loaded early because it feeds
    # two things: the verdict override below, and the review queue itself --
    # a word a human has already ruled on should not be asked about again.
    # The file is a plain word list, so duplicates in it are simply deduped.
    try:
        kept = set(pd.read_csv(UK_REVIEWED_PATH, keep_default_na=False,
                               na_values=[])['noun'].str.strip())
    except (FileNotFoundError, KeyError):
        kept = set()
    sen['human_kept'] = sen['noun'].isin(kept)

    print(f'SEN rows        : {len(sen):,}')
    print(f'Wiktionary rows : {len(wx):,}')

    wx = wx.drop_duplicates(subset='word', keep='first')
    w = wx.set_index('word')

    def col(name, default):
        s = sen['noun'].map(w[name]) if name in w.columns else pd.Series(default, index=sen.index)
        return s.fillna(default)

    sen['wikt_known']         = sen['noun'].isin(w.index)
    sen['wikt_countable']     = col('countable', 0).astype(int).astype(bool)
    sen['wikt_uncountable']   = col('uncountable', 0).astype(int).astype(bool)
    sen['wikt_plural_only']   = col('plural_only', 0).astype(int).astype(bool)
    # `is_inflected_form` is true when ANY sense of the entry is a form-of
    # sense, which on its own rejects good words: `pen` carries one dialect
    # sense that is a form of `pan`, `sheet` one of `shit`, `circle` one of
    # `words`, and 301 rows -- `chicken`, `opera`, `scissors`, `economics` --
    # were excluded as inflected forms while their first and main sense is an
    # ordinary noun. The word is an inflected form only when every etymology
    # section of it LEADS with the form-of sense (`lead_form`), which is how
    # Wiktionary writes a word that exists only as an inflection. That keeps
    # irregular plurals out: `bacteria`, `algae`, `cocci`, `kine`, `sands` and
    # `people` all lead with `plural of ...` and stay rejected, where a count of
    # form senses would have let them in alongside their own singulars.
    sen['wikt_inflected']     = col('is_inflected_form', 0).astype(int).astype(bool)
    if 'lead_form' in w.columns:          # older extracts do not carry it
        sen['wikt_inflected'] &= col('lead_form', 1).astype(int).astype(bool)
    sen['wikt_form_of']       = col('form_of', '')
    sen['wikt_variant_of']    = col('variant_of', '')
    sen['wikt_variant_kind']  = col('variant_kind', '')
    sen['wikt_regions']       = col('regions', '')

    # ---- british/commonwealth spelling variants (keep American) --------
    have_nouns = set(sen['noun'])
    has_target = (sen['wikt_variant_of'] != '') & sen['wikt_variant_of'].isin(have_nouns)
    is_editorial_uk = sen['wikt_variant_kind'].isin(['british', 'commonwealth'])
    is_region_uk = sen['wikt_regions'].apply(region_is_britishy)
    pattern = [uk_us_pattern(w_, c) if c else None
               for w_, c in zip(sen['noun'], sen['wikt_variant_of'])]
    has_pattern = pd.Series(pattern, index=sen.index).notna()

    # Direction A: this row IS the British/Commonwealth spelling.
    british_a = has_target & (is_editorial_uk | (is_region_uk & has_pattern))

    # Direction B: this row is the plain/base spelling, but some OTHER row
    # is editorially tagged 'american' and points at it.
    american_rows = sen[(sen['wikt_variant_kind'] == 'american') & has_target]
    american_equivalent = dict(zip(american_rows['wikt_variant_of'], american_rows['noun']))
    british_b = sen['noun'].isin(american_equivalent)
    sen['wikt_american_equivalent'] = sen['noun'].map(american_equivalent).fillna('')

    # Rows a human already ruled on drop out of the queue -- it means "still
    # needs a decision", not "was once a candidate".
    residue = (has_target & is_region_uk & ~is_editorial_uk & ~has_pattern
               & ~sen['human_kept'])

    # Second pass over that residue (project decision, 2026-08-29: exclude the
    # British spelling, keep the American). Only rows matching a named
    # correspondence are excluded; the rest stay in the queue, because the
    # residue also holds gloss-regex noise where `variant_of` points at an
    # unrelated word -- "dead" -> "deadlift", "lob" -> "fraud", "skittles" ->
    # "chess". Excluding on region tag alone would delete ordinary English
    # words like `dead`, `do`, `melt`, `par` and `lit`.
    residue_pattern = pd.Series(
        [uk_us_residue_pattern(w_, c, have_nouns) if r_ else None
         for w_, c, r_ in zip(sen['noun'], sen['wikt_variant_of'], residue)],
        index=sen.index)
    sen['wikt_uk_residue_rule'] = residue_pattern.fillna('')
    residue_resolved = residue & residue_pattern.notna()

    sen['wikt_british_variant'] = british_a | british_b | residue_resolved

    # A human read all 97 -ing doublets and said which side is British. That
    # ruling beats every rule above, in both directions: it EXCLUDES the pairs
    # the region tags missed (colouring, counselling, savouring) and it does
    # not touch the pairs a human called noise or a non-regional doublet.
    ing_uk = {}
    try:
        ing_reviewed = pd.read_csv(ING_REVIEWED_PATH, keep_default_na=False,
                                   na_values=[])
        for v, c, verdict in zip(ing_reviewed['variant'],
                                 ing_reviewed['canonical'],
                                 ing_reviewed['verdict']):
            if verdict == 'british':
                ing_uk[v] = c
            elif verdict == 'american':
                ing_uk[c] = v
    except FileNotFoundError:
        ing_reviewed = None
    # Only when the American side is actually in the dataset -- excluding a
    # word while pointing at a replacement that does not exist is worse than
    # keeping it.
    ing_uk = {k: v for k, v in ing_uk.items() if v in have_nouns}
    sen['wikt_ing_reviewed_us'] = sen['noun'].map(ing_uk).fillna('')
    ing_british = sen['wikt_ing_reviewed_us'] != ''
    sen['wikt_british_variant'] = sen['wikt_british_variant'] | ing_british

    # ---- reviewed spelling doublets --------------------------------------
    # A human read all 2,509 pairs. `variant`/`reverse` name the side to
    # drop; `plural` and `unrelated` are explicitly NOT exclusions, and say
    # so, which is the point of ruling them at all.
    drop_to, plural_side, unrelated = {}, set(), set()
    try:
        vr = pd.read_csv(VARIANTS_REVIEWED_PATH, keep_default_na=False,
                         na_values=[])
        for a, b, verdict in zip(vr['variant'], vr['canonical'], vr['verdict']):
            if verdict == 'variant':
                drop_to[a] = b
            elif verdict == 'reverse':
                drop_to[b] = a
            elif verdict == 'plural':
                plural_side.add(b if b.startswith(a) else a)
            else:
                unrelated.add(a)
                unrelated.add(b)
    except FileNotFoundError:
        vr = None
    # Never point a rejected word at a replacement the dataset does not have.
    drop_to = {k: v for k, v in drop_to.items()
               if v in have_nouns and k in have_nouns and k != v}
    sen['reviewed_variant_of'] = sen['noun'].map(drop_to).fillna('')
    sen['reviewed_spelling_variant'] = sen['reviewed_variant_of'] != ''
    sen['reviewed_plural'] = sen['noun'].isin(plural_side)
    # A pair ruled unrelated must not keep driving the automatic rules that
    # were reading the same bogus link.
    bogus = sen['noun'].isin(unrelated) & ~sen['reviewed_spelling_variant']
    sen.loc[bogus & ~sen['wikt_british_variant'], 'wikt_variant_of'] = ''

    uk_review = sen[residue & ~residue_resolved]
    uk_review[['noun', 'wikt_variant_of', 'wikt_variant_kind', 'wikt_regions', 'zipf', 'tier']] \
        .to_csv(out_path + '.uk_review.csv', index=False)

    # ---- rulings on words already in the dataset --------------------------
    # `gaps_verdicts.csv` can only add rows; a word OEWN already has needs its
    # existing row changed instead. Same vocabulary, applied in place.
    try:
        wv = pd.read_csv(SEN_VERDICTS_PATH, keep_default_na=False, na_values=[])
        ruled = {w.strip(): normalise_verdict(v)
                 for w, v in zip(wv['word'], wv['verdict'])}
    except (FileNotFoundError, KeyError):
        ruled = {}
    if ruled:
        why = sen['noun'].map({w: VERDICT_REASON[v][0] for w, v in ruled.items()
                               if v in VERDICT_REASON}).fillna('')
        mark = sen['noun'].map({w: VERDICT_REASON[v][1] for w, v in ruled.items()
                                if v in VERDICT_REASON}).fillna('')
        hit = why != ''
        sen.loc[hit, 'verdict_reason'] = why[hit]
        sen.loc[mark != '', 'pos_overlap'] = mark[mark != '']
        sen.loc[sen['noun'].isin([w for w, v in ruled.items() if v == 'name']),
                'name_suspect'] = True
        print(f'rulings on existing rows ({SEN_VERDICTS_PATH}): '
              f'{int(hit.sum())} of {len(ruled)}')

    # The hand-entry sheets apply in place too. Their rows are written above
    # only for words the dataset does not have, so before this a `name`, `adj`
    # or `initialism` ruling on a word OEWN already ships was read, counted and
    # silently dropped -- `cgs` stayed playable as "system of measurement based
    # on centimeters and grams" however many times it was ruled an initialism.
    # A `noun` is not applied here: it is forced playable further down, which
    # is the same answer by a different route.
    manual_existing = {w: v for w, v in manual.items() if v != 'noun'}
    if manual_existing:
        why = sen['noun'].map({w: VERDICT_REASON[v][0]
                               for w, v in manual_existing.items()}).fillna('')
        mark = sen['noun'].map({w: VERDICT_REASON[v][1]
                                for w, v in manual_existing.items()}).fillna('')
        hit = (why != '') & sen['noun'].isin(existing)
        sen.loc[hit, 'verdict_reason'] = why[hit]
        sen.loc[(mark != '') & hit, 'pos_overlap'] = mark[(mark != '') & hit]
        sen.loc[hit & sen['noun'].isin(
            [w for w, v in manual_existing.items() if v == 'name']),
            'name_suspect'] = True
        # A domain sheet's note is the definition, on an existing row as much
        # as on an added one: `cgs` is shown as "Centimetre-Gram-Second." and
        # not as OEWN's "system of measurement based on centimeters and grams",
        # which reads like a playable word.
        # `hit` is only the rows this ruling rejects; the gloss applies to a
        # hand `noun` on an existing row as well -- `yule` was carrying
        # "Alternative letter-case form of Yule." as its definition.
        gloss = sen['noun'].map({w: manual_notes[w] for w in manual
                                 if manual_source.get(w, '').startswith('domain:')
                                 and manual_notes.get(w)}).fillna('')
        on_row = (gloss != '') & sen['noun'].isin(existing)
        sen.loc[on_row, 'definition'] = gloss[on_row]
        print(f'hand-entry rulings on existing rows: {int(hit.sum())}')

    # ---- verdict -------------------------------------------------------
    # `~wikt_known` is a project decision (2026-08-29), not a derived rule: a
    # noun with no Wiktionary entry at all does not belong in the final SEN
    # dataset. See WIKTEXTRACT-JOIN-REPORT.md for the review that led to it --
    # 70% of these rows are OEWN's specialist tail and were already excluded as
    # OBSCURE, and the reviewable remainder is dominated by -ing nominalisations
    # (leaving, causing), unit symbols (km, kg) and -ed participles (wounded).
    # The rows stay in the file with the evidence attached, as always.
    bad = (sen['wikt_inflected'] | sen['wikt_plural_only']
           | sen['plural_of_listed'].astype(bool) | (sen['tier'] == 'OBSCURE')
           | sen['wikt_british_variant'] | ~sen['wikt_known']
           | sen['reviewed_spelling_variant']
           | (sen['verdict_reason'] != ''))
    sen['recommended'] = ~bad

    reason = pd.Series('', index=sen.index)
    # Masked first so every later criterion overrides it: a word that is both
    # unknown to Wiktionary and OBSCURE reads better as 'obscure', and this
    # keeps the existing exclusion counts unchanged. Only rows with no other
    # reason are labelled here.
    reason = reason.mask(~sen['wikt_known'], 'not in Wiktionary')
    reason = reason.mask(sen['tier'] == 'OBSCURE', 'obscure')
    reason = reason.mask(sen['plural_of_listed'].astype(bool), 'plural of listed word')
    reason = reason.mask(sen['wikt_plural_only'], 'plural-only (Wiktionary)')
    reason = reason.mask(sen['wikt_inflected'], 'inflected form (Wiktionary)')
    reason = reason.mask(sen['reviewed_spelling_variant'],
                         'spelling variant of another word (reviewed)')
    reason = reason.mask(sen['wikt_british_variant'], 'british/commonwealth spelling variant')
    reason = reason.mask(sen['verdict_reason'] != '', sen['verdict_reason'])

    # ---- what to suggest instead ------------------------------------------
    # The point of keeping a rejected word is being able to say WHY, and where
    # a replacement exists, to name it. For a British spelling that is the
    # American form: the curated table first (it is right where the gloss regex
    # is wrong -- "plough" -> "plow", not "snowplough"), then the variant_of
    # canonical, then an American row pointing back at this one.
    suggest = sen['reviewed_variant_of'].copy()           # human ruling first
    suggest = suggest.mask(suggest == '', sen['wikt_ing_reviewed_us'])
    suggest = suggest.mask(suggest == '', sen['noun'].map(UK_US_IRREGULAR).fillna(''))
    suggest = suggest.where(sen['wikt_british_variant']
                            | sen['reviewed_spelling_variant'], '')
    fallback = sen['wikt_variant_of'].where(sen['wikt_british_variant'], '')
    suggest = suggest.mask(suggest == '', fallback)
    suggest = suggest.mask(suggest == '', sen['wikt_american_equivalent'])
    # Never suggest a word the dataset does not have, or the word itself.
    ok = suggest.isin(set(sen['noun'])) & (suggest != sen['noun'])
    sen['suggest_instead'] = suggest.where(ok, '')

    # ---- human keep-list overrides every automatic exclusion --------------
    # Applied last, so it wins. These words were read one by one during the
    # manual `.uk_review.csv` pass; a human looking at the word beats a derived
    # rule, the same call the gaps cutoff already makes for PROBE_PATH.
    # ... except where a LATER human pass ruled on the same word. The
    # keep-list answers one question -- "is this wrongly flagged as a British
    # spelling?" -- and it was written before the doublet review and the
    # word-verdict sheet existed. Those two are explicit rulings on the word
    # itself, so they win: `gaol`, `kerb`, `annexe` and `acknowledgement` are
    # spelling variants, and `t` and `y` are not nouns, whatever an older
    # sheet built for a different question says.
    # A hand-entered `noun` is the last word on that word, and beats the lot:
    # the OBSCURE cutoff (`wordfreq` scores `doomscrolling` at 0), the
    # missing-from-Wiktionary rule, an older sheet's ruling, and lemminflect's
    # reading -- `gamer` was excluded as an adjective, `spork` as a proper
    # noun. Rows it adds keep their marks; only the exclusion is lifted.
    manual_noun = sen['noun'].isin([w for w, v in manual.items() if v == 'noun'])
    sen['recommended'] = sen['recommended'] | manual_noun
    sen['verdict_reason'] = sen['verdict_reason'].mask(manual_noun, '')
    reason = reason.mask(manual_noun, '')
    print(f'hand-entered nouns forced playable: {int(manual_noun.sum())}')

    # Applied before the keep-list, and before `excluded_because` is frozen: a
    # word rescued here has no exclusion left to explain.
    rescued = abbreviation_collision(
        sen, load_abbrev_rulings(),
        load_abbrev_expansions()
        | {w for w, v in manual.items() if v == 'initialism'})
    if rescued:
        sen['recommended'] = sen['recommended'] | sen['noun'].isin(rescued)
        reason = reason.mask(sen['noun'].isin(rescued), '')
        print(f'abbreviation collisions rescued: {len(rescued)} '
              f'(a real noun spelled like an initialism keeps its definition)')

    later_ruling = sen['reviewed_spelling_variant'] | (sen['verdict_reason'] != '')
    effective_keep = sen['human_kept'] & ~later_ruling
    overridden = effective_keep & ~sen['recommended']
    sen['recommended'] = sen['recommended'] | effective_keep
    reason = reason.mask(effective_keep, '')
    sen['excluded_because'] = reason

    # ---- marks: everything the dataset doubts, said out loud --------------
    # Project rule (see the report): a word in doubt is KEPT and MARKED, not
    # dropped. `excluded_because` answers "may I play this?"; `marks` answers
    # "what else might this word be?", and a game is free to ignore it, warn
    # on it, or filter by it. Marks are advisory and never change
    # `recommended` -- an allowed word can and does carry them.
    dom = load_pos_dominance()
    wpos = load_wikt_pos(words=set(sen['noun']))
    sen['corpus_dominant'] = [dom[w].dominant if w in dom else ''
                              for w in sen['noun']]
    sen['corpus_n'] = [int(dom[w].n) if w in dom else 0 for w in sen['noun']]
    sen['corpus_noun_share'] = [float(dom[w].noun_share) if w in dom else ''
                                for w in sen['noun']]
    sen['wikt_pos_list'] = [wpos[w][0] if w in wpos else '' for w in sen['noun']]
    sen['wikt_abbrev'] = [bool(wpos[w][3]) if w in wpos else False
                          for w in sen['noun']]

    def marks_for(row):
        out = []
        if row['pos_overlap']:
            out.append(row['pos_overlap'])
        w = row['noun']
        d = dom.get(w)
        mark = corpus_mark(d, wordnet_noun=bool(row['lexfile']))
        if mark:
            out.append(mark)
        if row['reviewed_spelling_variant']:
            out.append('spelling variant of ' + row['reviewed_variant_of'])
        if row['reviewed_plural']:
            out.append('possible plural')
        if row['name_suspect'] or row['also_proper_noun']:
            out.append('possible name')
        if (row['plural_suspect'] or row['plural_of_listed']
                or row['wikt_plural_only']):
            out.append('possible plural')
        # Only the words the pipeline actually judged to be the British
        # SPELLING of an American word. A UK region tag on some sense is a
        # different fact entirely -- `abbey`, `abbot` and `absentee` all carry
        # one and none of them is a spelling variant of anything.
        if row['wikt_british_variant']:
            out.append('UK/Commonwealth spelling')
        if row['wikt_abbrev'] or w in rescued:
            out.append('possible abbreviation or clipping')
        # ...unless a person entered the word by hand, which is that question
        # already answered. `devops` and `youtuber` have no Wiktionary noun
        # entry and do not need asking about.
        if not row['wikt_known'] and w not in manual:
            out.append('manual - not in Wiktionary, is it a real noun?')
        # A mark written on a hand-entry sheet. `initialism` is the one this
        # exists for: `usb` and `led` are playable AND worth labelling, and no
        # derived rule can tell an initialism that became a word (`laser`,
        # `radar`) from one that has not.
        if manual_marks.get(w):
            out.extend(manual_marks[w].split('; '))
        seen, uniq = set(), []
        for m in out:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        return '; '.join(uniq)

    sen['marks'] = [marks_for(r) for _, r in sen.iterrows()]

    sen.to_csv(out_path, index=False)

    # ---- gaps: Wiktionary has it, OEWN does not ------------------------
    try:
        from wordfreq import zipf_frequency
        cand = gap_candidates(wx, set(sen['noun']))
        cand['zipf'] = [round(zipf_frequency(x, 'en'), 2) for x in cand['word']]
        # Cutoff chosen from the band analysis in threshold_bands.py, not by
        # feel: 2.0 recovers chatbot/earbud/telehealth/podcaster from
        # modernvocabularyprobe.csv, and stops just above the 1.5-2.0 band where
        # misspellings and clinical jargon start to dominate. See
        # WIKTEXTRACT-JOIN-REPORT.md, "zipf threshold band analysis".
        ZIPF_MIN = 2.0
        # modernvocabularyprobe.csv is the project's human-vetted list of modern
        # words that belong in the dataset, so its words are exempt from the
        # cutoff -- a human already vouched for them, which outranks a frequency
        # score. Only "microplastic" (zipf 1.61) actually needs the exemption
        # today; without it, every re-run silently drops that word back out.
        try:
            probe = set(pd.read_csv(PROBE_PATH)['word'])
        except (FileNotFoundError, KeyError):
            probe = set()
        keep = (cand['zipf'] >= ZIPF_MIN) | cand['word'].isin(probe)
        rescued = sorted(cand.loc[keep & (cand['zipf'] < ZIPF_MIN), 'word'])
        cand = cand[keep].sort_values('zipf', ascending=False)
        cand[['word','zipf','countable','uncountable','n_senses','first_gloss']] \
            .to_csv(out_path + '.gaps.csv', index=False)
        print(f'\ncandidate additions (zipf >= {ZIPF_MIN}): {len(cand):,} -> {out_path}.gaps.csv')
        print('  top 30:', ', '.join(cand['word'].head(30).tolist()))
        if rescued:
            print(f'  kept below the cutoff, vouched for by {PROBE_PATH}: '
                  f'{", ".join(rescued)}')
    except ImportError:
        print('\n(wordfreq not installed - skipping the gaps file)')

    # ---- spelling doublets where both sides are in the dataset ---------
    have = set(sen['noun'])
    v = sen[(sen['wikt_variant_of'] != '') & (sen['wikt_variant_of'].isin(have))] \
        [['noun', 'wikt_variant_of', 'wikt_variant_kind', 'wikt_regions', 'zipf', 'tier']] \
        .rename(columns={'noun': 'variant', 'wikt_variant_of': 'canonical'})

    # Rows where either side is an -ing form come out into their own table.
    # They are a different question from the rest of the doublets: an -ing word
    # is a potential verb first and a spelling variant second, so leaving them
    # in asks the reviewer two questions at once. Split here per the
    # 2026-08-29 decision, reviewed separately.
    ing = v['variant'].str.endswith('ing') | v['canonical'].str.endswith('ing')
    v_ing = v[ing].copy()
    if len(v_ing):
        from difflib import SequenceMatcher
        both = (v_ing['variant'].str.endswith('ing')
                & v_ing['canonical'].str.endswith('ing'))
        ratio = [SequenceMatcher(None, a, b).ratio()
                 for a, b in zip(v_ing['variant'], v_ing['canonical'])]
        pos, lemma = [], []
        for word in v_ing['variant']:
            t = getAllLemmas(word) if getAllLemmas else {}
            pos.append(';'.join(sorted(t)))
            lemma.append(next(iter(t.values()))[0] if t else '')
        v_ing['variant_pos'] = pos
        v_ing['variant_lemma'] = lemma
        # Pre-filled guess, to be overwritten. A pair that is -ing on both
        # sides AND near-identical is a real spelling doublet (ageing/aging,
        # counselling/counseling); an -ing word whose "canonical" is an
        # unrelated word is the gloss-regex noise seen throughout this file
        # (drawing -> "a", popcorn -> "brainstorming").
        v_ing['verdict'] = ['spelling_pair' if bo and r >= 0.8
                            else 'verb' if 'VERB' in p
                            else 'noise'
                            for bo, r, p in zip(both, ratio, pos)]
        v_ing['note'] = ''
        v_ing[['variant', 'canonical', 'verdict', 'note', 'variant_pos',
               'variant_lemma', 'wikt_variant_kind', 'zipf', 'tier']] \
            .to_csv(out_path + '.variants_ing.csv', index=False)

    # `variant_kind == 'spelling'` is not a kind, it is the DEFAULT label
    # wx_extract.py applies when its gloss regex matched but no lexicographic
    # keyword ("alternative", "archaic", "British", ...) was present. That
    # regex has `[a-z\s]*` between the optional keyword and `spelling|form of`,
    # runs case-insensitively and is unanchored, so it also fires on ordinary
    # prose: "a form of argument" makes abduction -> argument, "the acute form
    # of a disorder" makes acute -> a. 137 rows point at "a".
    #
    # Every other kind is trustworthy by contrast -- `alt_of` comes from
    # Wiktionary's structured field, and the keyword kinds required a real
    # lexicographic word. Measured on the undecided rows: median variant/
    # canonical similarity 0.83-0.93 for every other kind, 0.25 for
    # 'spelling', which holds all 137 of the "a" rows.
    #
    # Splitting on that one column keeps the doublet queue reviewable. The
    # proper fix is an anchored regex in wx_extract.py, which needs the raw
    # dump re-downloaded (2.6 GB, deleted as reproducible).
    suspect = v['wikt_variant_kind'] == 'spelling'
    v[~ing & suspect].to_csv(out_path + '.variants_suspect.csv', index=False)
    v[~ing & ~suspect].to_csv(out_path + '.variants.csv', index=False)

    # ---- SEN nouns Wiktionary has never heard of -----------------------
    # The inverse of the gaps file: OEWN has these, Wiktionary does not. All of
    # them are now excluded (see the verdict section above), so this file is the
    # audit trail of that decision rather than a pending review queue -- the
    # rows keep their evidence so the call can be re-derived or reversed.
    # Hand entries are left out: `devops` and `youtuber` have no Wiktionary
    # entry either, but a person already answered the question this file asks.
    unknown = sen[~sen['wikt_known'] & ~sen['noun'].isin(manual)]         .sort_values(['zipf', 'noun'], ascending=[False, True])
    unknown[['noun', 'zipf', 'tier', 'senses', 'lexfile', 'register', 'domain',
             'in_wn30', 'also_proper_noun', 'recommended', 'excluded_because',
             'definition']] \
        .to_csv(out_path + '.unknown.csv', index=False)

    # ---- report --------------------------------------------------------
    print(f'\nmatched in Wiktionary : {sen["wikt_known"].sum():,} / {len(sen):,} '
          f'({sen["wikt_known"].mean()*100:.1f}%)')
    print(f'plural-only flagged   : {sen["wikt_plural_only"].sum():,}')
    print(f'inflected forms found : {sen["wikt_inflected"].sum():,}')
    print(f'uncountable only      : {(sen["wikt_uncountable"] & ~sen["wikt_countable"]).sum():,}')
    print(f'spelling doublets     : {int((~ing).sum()):,} -> {out_path}.variants.csv')
    print(f'  -ing forms split out: {len(v_ing):,} -> {out_path}.variants_ing.csv')
    print(f'  regex-suspect split out: {int((~ing & suspect).sum()):,} '
          f'-> {out_path}.variants_suspect.csv')
    if ing_reviewed is not None:
        print(f'reviewed -ing doublets ({ING_REVIEWED_PATH}): '
              f'{len(ing_reviewed):,} rulings, '
              f'{int(ing_british.sum()):,} British sides excluded')
    print(f'british/commonwealth spelling variants excluded (American kept): '
          f'{sen["wikt_british_variant"].sum():,}')
    print(f'  direction A (this row is the UK spelling)  : {british_a.sum():,}')
    print(f'  direction B (an American row points here)  : {british_b.sum():,}')
    print(f'  residue resolved by second-pass rules       : {int(residue_resolved.sum()):,}')
    print(f'unresolved UK-flagged, needs manual review   : {len(uk_review):,} '
          f'-> {out_path}.uk_review.csv')
    print(f'unknown to Wiktionary, all excluded          : {len(unknown):,} '
          f'-> {out_path}.unknown.csv')
    print(f'  keep-list entries a later ruling overrides: '
          f'{int((sen["human_kept"] & later_ruling).sum()):,}')
    print(f'human keep-list ({UK_REVIEWED_PATH}): {len(kept):,} words, '
          f'{int(sen["human_kept"].sum()):,} matched in the dataset, '
          f'{int(overridden.sum()):,} exclusions overridden')
    if overridden.any():
        print('  overridden:', ', '.join(sen.loc[overridden, 'noun'].tolist()))
    print(f'\nRECOMMENDED           : {sen["recommended"].sum():,} '
          f'({sen["recommended"].mean()*100:.1f}%)')
    print('excluded, by reason:')
    for k, n in sen.loc[~sen['recommended'], 'excluded_because'].value_counts().items():
        print(f'    {k:38s} {n:,}')
    print(f'\nwritten: {out_path}')

if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
