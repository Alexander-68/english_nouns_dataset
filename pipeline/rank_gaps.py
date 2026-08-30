#!/usr/bin/env python3
"""
rank_gaps.py — POS-aware re-ranking of sen-v3.csv.gaps.csv

Problem (WIKTEXTRACT-JOIN-REPORT.md, "Next steps" #1):
    gaps.csv ranks candidate words purely by overall zipf frequency. That
    frequency is for the WORD FORM across all its uses, not for its noun
    sense specifically. Wiktionary legitimately records a noun sense for
    words like "made" (dialectal: a grub or maggot), "went" (archaic: a
    path), "seen" (the Arabic letter seen) and "washington" (a board-game
    synonym) -- real dictionary entries, correctly extracted -- but their
    high zipf score comes almost entirely from a completely different,
    non-noun use (main verb, function word, proper-noun homograph). Ranking
    by raw zipf floats that non-noun frequency to the top and buries the
    modern nouns the file exists to surface (wifi, hoodie, chatbot, ...).

This script does not delete or re-score anything upstream. It reads the
gaps file wx_join.py already produced, adds evidence columns explaining
*why* a candidate's zipf is misleading, and re-sorts so the queue is
usable top-to-bottom. Every row is kept -- flagged rows just sort lower,
exactly like `excluded_because` in sen-v3.csv keeps rather than deletes.

Two closed, citable sources back the flags (no corpus / POS-tagger
download required, so this runs fully offline):

  1. CLOSED_CLASS  - English's closed grammatical classes: determiners,
     pronouns, conjunctions, prepositions, auxiliary/modal verbs, and the
     standard set of function adverbs/discourse connectives. These classes
     are finite by definition, so a word landing in one of them being
     "recommended by frequency" as a chain noun is a category error, not a
     borderline case.
  2. IRREGULAR_VERB_FORMS - the past-tense/past-participle spellings from
     the standard table of ~100 English irregular verbs (e.g. went, seen,
     bought, written). Deliberately excludes unmarked forms (cut, set,
     read, cast, spread, put, hit, ...) where the same spelling is also a
     perfectly good, common, independent noun -- flagging those would be
     the wrong call, not a safe one.

A third, data-driven flag reuses a column already on disk: a word whose
Wiktionary `variant_of` starts with a capital letter is a lower-cased form
of a proper noun (e.g. india -> "India ...", indian -> "Indian"). OEWN
2025 moved proper nouns to a separate Namenet (see WIKTEXTRACT-JOIN-REPORT
finding), so these don't belong in a common-noun gap queue regardless of
whether their capitalised canonical happens to be a row in the dataset.

Anything not caught by one of the three flags keeps its original zipf
rank and floats to the top of `likely_noun` rows -- that's the reviewable
list. Words flagged but carrying 3+ Wiktionary noun senses are called out
separately: multiple independent senses is some evidence the flag might
be too aggressive for that particular word, so they're worth a human
glance rather than being trusted blindly either way.

Usage
-----
    python3 rank_gaps.py sen-v3.csv.gaps.csv wiktionary-nouns.csv [modernvocabularyprobe.csv]

Rewrites sen-v3.csv.gaps.csv in place (same columns as before, plus
`variant_of`, `flag_reason`, `likely_noun`), sorted by (likely_noun desc,
zipf desc). Prints a summary; if a probe file is given, cross-checks that
none of its known-good modern words got mis-flagged.
"""
import sys, re
import pandas as pd

# Lower-cased proper nouns, built by build_name_list.py from Namenet and the
# 2024 Wikipedia list. Missing file is not an error -- the name tier is simply
# not applied.
NAME_LIST_PATH = 'sources/names-lowercase.csv'

# Human rulings on individual gap candidates, accumulated as they are reviewed.
# `verdict` is one of: noun | name | verb | adj. A ruling here beats every
# automatic flag and every tag below -- same principle as PROBE_PATH and
# UK_REVIEWED_PATH in wx_join.py. Missing file is not an error.
VERDICTS_PATH = 'reviews/gaps_verdicts.csv'

# Dominant part of speech measured on 1.26M POS-tagged tokens (pos_freq.py).
# This is the source the project repeatedly parked as unavailable: morphology
# and lemminflect both answer "can this be a noun?", and for `political`,
# `federal`, `international` and `hot` the honest answer is yes -- they have
# nominalised senses. What they cannot answer is "is it one in practice?".
# A corpus can, and disagrees: 0 of 339 `political` tokens are nouns.
POS_DOMINANCE_PATH = 'sources/pos-dominance.csv'

# Wiktionary's own part-of-speech inventory for every English word (wx_pos.py).
# wx_extract.py keeps only `pos == "noun"` entries, which is why the top of
# this queue filled up with `oh`, `ha`, `ya`, `de` and `ve`: the pipeline had
# no way to see that Wiktionary files them as interjections, particles and
# pronouns that happen to carry one noun sense each.
WIKT_POS_PATH = 'sources/wiktionary-pos.csv'

# Only the closed classes are trusted to FLAG. Wiktionary sense counts are
# generous with obsolete verb senses (`fridge` is verb:5/noun:2, `piano` is
# verb:4/noun:1), so "more verb senses than noun senses" is not evidence that
# a word is not a noun. Being filed mainly as an interjection or a pronoun
# is, because nothing generates spurious interjection senses.
FUNCTION_POS = {'intj', 'particle', 'pron', 'prep', 'conj', 'det', 'article',
                'num', 'prefix', 'suffix', 'infix', 'symbol', 'punct',
                'contraction', 'character', 'phrase', 'proverb'}
FUNCTION_POS_MAX_NOUN_SHARE = 0.5

# Evidence thresholds. Deliberately conservative in both directions: a word
# seen a handful of times says nothing, and a word with any real noun use is
# left in the queue for a human rather than flagged away.
CORPUS_MIN_N = 20            # occurrences needed before the corpus may flag
CORPUS_MAX_NOUN_SHARE = 0.02  # ... and essentially no common-noun use
CORPUS_TAG_MIN_N = 5         # weaker evidence -> an advisory tag, not a flag
CORPUS_NAME_SHARE = 0.90     # proper-noun share that makes a word a name

# Verdict spellings are normalised so a hand-edited file is not silently
# ignored: `adjective` and `adj` mean the same thing, as do `proper noun` and
# `name`. Unknown values are left as-is and simply match no rule.
VERDICT_ALIASES = {'adjective': 'adj', 'adjectival': 'adj', 'verbal': 'verb',
                   'proper noun': 'name', 'propernoun': 'name', 'nouns': 'noun'}


def normalise_verdict(v):
    v = str(v).strip().lower()
    return VERDICT_ALIASES.get(v, v)


# ---------------------------------------------------------------------------
# Part-of-speech overlap, marked rather than judged.
#
# The project rule (2026-08-29): a noun that can be -- or originally was -- an
# adjective or a verb gets TAGGED, not excluded, so the game rule can decide
# later whether to allow it. `political`, `federal` and `hot` have real
# nominalised senses; `endangering` and `channeling` are verb forms with noun
# uses. Which of those a game accepts is a game question, not a data question.
#
# These suffix rules are the FALLBACK. lemminflect's lexicon answers first
# (see pos_lookup below); this only runs for words it has no entry for. The
# tag then says "this word has the SHAPE of a verb/adjective", and is advisory
# by design. Being over-broad is acceptable for a tag in a way it would never
# be for an exclusion.
# ---------------------------------------------------------------------------
ADJ_SUFFIXES = ('ous', 'ive', 'ical', 'ic', 'al', 'ly', 'able', 'ible',
                'ful', 'less', 'ish', 'ary')

# -ing/-ed words that are established common nouns in their own right, not
# verb forms. Short, closed, and checked by hand -- the morphological test
# cannot see the difference.
NOT_VERB_FORMS = {
    'thing', 'king', 'ring', 'string', 'wing', 'spring', 'sing', 'bring',
    'ceiling', 'building', 'morning', 'evening', 'meeting', 'painting',
    'shilling', 'sterling', 'herring', 'gelding', 'pudding', 'darling',
    'lightning', 'awning', 'bed', 'shed', 'weed', 'seed', 'speed', 'creed',
    'breed', 'deed', 'need', 'reed', 'feed', 'greed', 'steed', 'tweed',
}


# Endings that look like a plural -s but are not: Latin/Greek singulars
# (bogus, modus, lapis, polis, mythos, nitrous), adverbs (alas, amiss) and
# double-s words (diss). Stripping the -s from these produces a real word by
# accident -- bog, mod, lap, pol, myth, nitro, ala, ami, dis -- so the guard
# runs before the singular lookup, not after.
NOT_PLURAL_ENDINGS = ('ss', 'us', 'is', 'os', 'as')


def plural_of(word, have):
    """The singular this word looks like a plural of, or '' if none.

    Tag, not a verdict, on the same principle as pos_overlap: "bollocks" has a
    singular "bollock", so it is marked as a potential plural and the game rule
    decides whether plurals are legal answers. Nothing is excluded here.
    """
    if len(word) < 4 or not word.endswith('s') or word.endswith(NOT_PLURAL_ENDINGS):
        return ''
    if word.endswith('ies') and word[:-3] + 'y' in have:
        return word[:-3] + 'y'
    for stem in (word[:-1], word[:-2] if word.endswith('es') else None):
        if stem and len(stem) > 2 and stem in have:
            return stem
    return ''


try:
    from lemminflect import getAllLemmas
except ImportError:                      # morphology-only fallback
    getAllLemmas = None

POS_WORD = {'ADJ': 'adjective', 'VERB': 'verb', 'ADV': 'adverb'}


def pos_lookup(word):
    """(pos_tags, lemma, overlap_label) for one word.

    lemminflect is a real POS lexicon and is consulted first -- it answers the
    cases morphology cannot see at all: `pretty`/`easy`/`hot` are adjectives,
    `learn`/`follow`/`eat` are verbs, `higher` is the comparative of `high`.
    None of those has a suffix to match on.

    A word lemminflect does not know falls back to the suffix rules below. That
    is not a failure mode so much as a second signal: its lexicon covers
    ordinary English, so `oh`, `lol`, `http`, `san`, `kinda` and `haha` being
    absent says something true about them.

    `overlap_label` is empty when the word is a plain noun and nothing else --
    there is nothing to warn a game about.
    """
    tags = getAllLemmas(word) if getAllLemmas else {}
    if not tags:
        return '', '', pos_morphology(word)
    pos = ';'.join(sorted(tags))
    lemma = next(iter(tags.values()))[0]
    lemma = lemma if lemma != word else ''
    others = [POS_WORD[t] for t in ('ADJ', 'VERB', 'ADV') if t in tags]
    if not others:
        label = ''                                    # NOUN only
    elif 'NOUN' in tags:
        label = 'noun, also ' + '/'.join(others)
    else:
        label = '/'.join(others) + ' (not a noun)'
    return pos, lemma, label


def pos_morphology(word):
    """Suffix-shape guess, used only when lemminflect has no entry."""
    if word in NOT_VERB_FORMS:
        return ''
    if word.endswith('ing') and len(word) > 5:
        return 'verb form (-ing, morphology)'
    if word.endswith('ed') and len(word) > 4:
        return 'verb form (-ed, morphology)'
    if word.endswith(ADJ_SUFFIXES) and len(word) > 5:
        return 'adjective-like (morphology)'
    return ''

# ---------------------------------------------------------------------------
# 1. Closed grammatical classes (finite by definition -- not a judgement call)
# ---------------------------------------------------------------------------
DETERMINERS = {
    'a', 'an', 'the', 'this', 'that', 'these', 'those', 'some', 'any', 'no',
    'every', 'each', 'either', 'neither', 'both', 'all', 'another', 'such',
    'own', 'other', 'more', 'most', 'less', 'least', 'much', 'many',
    'several', 'enough',
}
PRONOUNS = {
    'i', 'me', 'you', 'he', 'him', 'she', 'her', 'it', 'we', 'us', 'they',
    'them', 'my', 'mine', 'your', 'yours', 'his', 'its', 'our', 'ours',
    'their', 'theirs', 'myself', 'yourself', 'himself', 'herself', 'itself',
    'ourselves', 'yourselves', 'themselves', 'who', 'whom', 'whose', 'which',
    'what', 'someone', 'somebody', 'something', 'anyone', 'anybody',
    'anything', 'everyone', 'everybody', 'everything', 'nobody', 'nothing',
    'none', 'one',
}
CONJUNCTIONS = {
    'and', 'but', 'or', 'nor', 'so', 'yet', 'for', 'because', 'although',
    'though', 'while', 'whereas', 'if', 'unless', 'until', 'since', 'as',
    'than', 'whether',
}
PREPOSITIONS = {
    'in', 'on', 'at', 'by', 'with', 'about', 'against', 'between', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from',
    'up', 'down', 'off', 'over', 'under', 'again', 'further', 'once',
    'here', 'there', 'near', 'across', 'via', 'beyond', 'within', 'without',
    'among', 'along', 'around', 'behind', 'beside', 'beneath', 'besides',
    'despite', 'except', 'inside', 'outside', 'throughout', 'toward',
    'towards', 'upon', 'versus', 'per',
}
AUXILIARIES_MODALS = {
    'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
    'had', 'having', 'do', 'does', 'did', 'doing', 'will', 'would', 'shall',
    'should', 'can', 'could', 'may', 'might', 'must', 'ought', 'cannot',
}
FUNCTION_ADVERBS = {
    'not', 'only', 'just', 'too', 'very', 'also', 'still', 'even', 'well',
    'now', 'then', 'always', 'never', 'ever', 'often', 'sometimes',
    'usually', 'quite', 'rather', 'almost', 'already', 'why', 'how', 'when',
    'where', 'perhaps', 'maybe', 'whatever', 'however', 'therefore', 'thus',
    'hence', 'indeed', 'instead', 'otherwise', 'meanwhile', 'nonetheless',
    'nevertheless', 'moreover', 'furthermore', 'anyway', 'anyhow',
}
CLOSED_CLASS = (DETERMINERS | PRONOUNS | CONJUNCTIONS | PREPOSITIONS
                | AUXILIARIES_MODALS | FUNCTION_ADVERBS)

# ---------------------------------------------------------------------------
# 2. Standard irregular-verb past/past-participle forms.
#    Unmarked forms deliberately omitted (cut, set, read, cast, spread,
#    put, hit, cost, hurt, burst, bet, let, shut, split) -- same spelling
#    as the base verb AND a perfectly good independent common noun.
# ---------------------------------------------------------------------------
IRREGULAR_VERB_FORMS = {
    'went', 'gone', 'done', 'seen', 'saw', 'made', 'said', 'took', 'taken',
    'given', 'gave', 'known', 'knew', 'thought', 'found', 'told', 'became',
    'begun', 'brought', 'built', 'bought', 'caught', 'chose', 'chosen',
    'came', 'drew', 'drawn', 'drove', 'driven', 'ate', 'eaten', 'fell',
    'fallen', 'felt', 'fought', 'forgot', 'forgotten', 'forgave', 'forgiven',
    'got', 'gotten', 'grew', 'grown', 'heard', 'held', 'hid', 'hidden',
    'kept', 'laid', 'led', 'left', 'lent', 'lay', 'lain', 'lost', 'meant',
    'met', 'paid', 'rode', 'ridden', 'rang', 'rung', 'rose', 'risen', 'ran',
    'sang', 'sung', 'sat', 'sold', 'sent', 'shone', 'shot', 'showed',
    'shown', 'shrank', 'shrunk', 'sank', 'sunk', 'slept', 'slid', 'spoke',
    'spoken', 'spent', 'stood', 'stole', 'stolen', 'stuck', 'stung',
    'struck', 'swore', 'sworn', 'swam', 'swum', 'swept', 'swelled',
    'swollen', 'taught', 'tore', 'torn', 'thrown', 'threw', 'understood',
    'woke', 'woken', 'wore', 'worn', 'won', 'wound', 'wrote', 'written',
    'wept', 'dealt', 'dug', 'drank', 'drunk', 'flew', 'flown', 'forbade',
    'forbidden', 'froze', 'frozen', 'hung', 'kneeled', 'knelt', 'leapt',
    'learnt', 'spelled', 'spelt', 'spilled', 'spilt', 'burnt', 'dreamt',
    'smelt', 'leaned', 'leant', 'lit', 'bit', 'bitten', 'bled', 'blew',
    'blown', 'broke', 'broken', 'bound', 'bred', 'crept', 'decided',
}


# The gloss says it outright often enough to be worth reading. A gap
# candidate whose FIRST sense is "Initialism of ...", "Clipping of ..." or
# "Alternative letter-case form of ..." is not a word the dataset wants; it
# is a shorthand for one it already has. Anchored, for the same reason
# wx_extract.py's VARIANT_RE is: mid-sentence prose means nothing by it.
GLOSS_FLAGS = [
    (re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                r'(?:an?\s+)?(?:initialism|acronym|abbreviation|abbrev\.)\b',
                re.IGNORECASE), 'initialism or abbreviation (Wiktionary gloss)'),
    (re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                r'(?:an?\s+)?(?:clipping|short\s+form|shortening)\s+of\b',
                re.IGNORECASE), 'clipping (Wiktionary gloss)'),
    (re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                r'alternative\s+letter[- ]case\s+form\s+of\b',
                re.IGNORECASE), 'letter-case variant (Wiktionary gloss)'),
    (re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                r'(?:common\s+)?miss?spellings?\s+of\b',
                re.IGNORECASE), 'misspelling (Wiktionary gloss)'),
    (re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                r'(?:alternative|alternate|archaic|obsolete|dated|nonstandard|'
                r'standard|british|american|commonwealth|eye\s+dialect|informal)'
                r'(?:[\s-]+\w+){0,3}?[\s-]+(?:spellings?|forms?)\s+of\b',
                re.IGNORECASE), 'spelling variant of another word (Wiktionary gloss)'),
]


def gloss_flag(gloss):
    for rx, reason in GLOSS_FLAGS:
        if rx.match(gloss or ''):
            return reason
    return ''


def flag_reason(word, variant_of):
    if word in CLOSED_CLASS:
        return 'closed-class function word'
    if word in IRREGULAR_VERB_FORMS:
        return 'irregular verb form'
    if variant_of and variant_of[0].isupper():
        # ALL-CAPS canonicals (DNA, CEO, GIF, LOL, COVID-19) are acronyms/
        # initialisms, not proper nouns -- they're everyday lowercase common
        # nouns in practice and stay in the review queue.
        if not variant_of.isupper():
            return 'case variant of a proper noun'
    return ''


CORPUS_POS_WORD = {'ADJ': 'adjective', 'VERB': 'verb', 'ADV': 'adverb',
                   'PROPN': 'name', 'NOUN': 'noun'}


def load_wikt_pos(path=WIKT_POS_PATH, words=None):
    """word -> (pos_list, dominant_pos, noun_share, abbrev), or {}."""
    try:
        d = pd.read_csv(path, keep_default_na=False, na_values=[])
    except FileNotFoundError:
        print(f'  (no {path}; run wx_pos.py to enable Wiktionary POS evidence)')
        return {}
    if words is not None:
        d = d[d['word'].isin(words)]
    out = {}
    for r in d.itertuples(index=False):
        dominant = r.pos_list.split(':')[0] if r.pos_list else ''
        share = r.noun_senses / r.total_senses if r.total_senses else 0.0
        out[r.word] = (r.pos_list, dominant, share, bool(r.abbrev))
    return out


def load_pos_dominance(path=POS_DOMINANCE_PATH):
    """word -> dict of corpus counts, or {} when the table is not built."""
    try:
        d = pd.read_csv(path, keep_default_na=False, na_values=[])
    except FileNotFoundError:
        print(f'  (no {path}; run pos_freq.py to enable corpus POS evidence)')
        return {}
    return {r.word: r for r in d.itertuples(index=False)}


def corpus_reading(row):
    """(flag_reason, advisory_tag, is_name) from one corpus row.

    Three outcomes, in descending order of confidence:
      * enough tokens and no common-noun use at all -> a flag, on the same
        footing as the closed-class list: the word is not a noun in practice.
      * proper-noun dominant -> a name, which is a SORT TIER, not a flag
        (standing decision: names stay visible in the queue).
      * anything else -> an advisory tag that changes nothing, or nothing.
    """
    n, share = row.n, row.noun_share
    if row.propn / n >= CORPUS_NAME_SHARE and n >= CORPUS_TAG_MIN_N:
        return '', 'name in practice (corpus)', True
    other = CORPUS_POS_WORD.get(row.dominant, '')
    if row.dominant in ('NOUN', 'PROPN') or not other:
        return '', '', False
    if n >= CORPUS_MIN_N and share <= CORPUS_MAX_NOUN_SHARE:
        return f'{other} in practice (corpus)', '', False
    if n >= CORPUS_TAG_MIN_N:
        return '', f'usually {other} (corpus)', False
    return '', '', False


def main(gaps_path, wikt_path, probe_path=None):
    gaps = pd.read_csv(gaps_path, keep_default_na=False, na_values=[])
    wx = pd.read_csv(wikt_path, keep_default_na=False, na_values=[])
    print(f'gap candidates (before) : {len(gaps):,}')

    variant_of = wx.drop_duplicates(subset='word', keep='first').set_index('word')['variant_of']
    gaps['variant_of'] = gaps['word'].map(variant_of).fillna('')

    gaps['flag_reason'] = [flag_reason(w, v) for w, v in zip(gaps['word'], gaps['variant_of'])]

    # ---- what the gloss says about itself ---------------------------------
    gl = pd.Series([gloss_flag(g) for g in gaps['first_gloss']], index=gaps.index)
    newly_gloss = (gaps['flag_reason'] == '') & (gl != '')
    gaps.loc[newly_gloss, 'flag_reason'] = gl[newly_gloss]
    if newly_gloss.any():
        print(f'flagged by their own gloss: {int(newly_gloss.sum()):,}')
        for r, n in gl[newly_gloss].value_counts().items():
            print(f'    {r:52s} {n:,}')

    # ---- Wiktionary's own part-of-speech inventory -------------------------
    wpos = load_wikt_pos(words=set(gaps['word']))
    if wpos:
        got = [wpos.get(w, ('', '', 0.0, False)) for w in gaps['word']]
        gaps['wikt_pos_list'] = [g[0] for g in got]
        gaps['wikt_dominant_pos'] = [g[1] for g in got]
        gaps['wikt_abbrev'] = [g[3] for g in got]
        fn = pd.Series([g[1] in FUNCTION_POS
                        and g[2] < FUNCTION_POS_MAX_NOUN_SHARE for g in got],
                       index=gaps.index)
        newly_fn = (gaps['flag_reason'] == '') & fn
        gaps.loc[newly_fn, 'flag_reason'] = [
            f'{d} in Wiktionary (not a noun)' for d in
            gaps.loc[newly_fn, 'wikt_dominant_pos']]
        print(f'Wiktionary POS evidence : {int((gaps["wikt_pos_list"] != "").sum()):,} '
              f'of {len(gaps):,} candidates')
        print(f'  flagged as function words / interjections: {int(newly_fn.sum()):,}')
        print(f'  tagged as abbreviations (advisory only)  : '
              f'{int(gaps["wikt_abbrev"].sum()):,}')

    # ---- corpus part-of-speech evidence -----------------------------------
    dom = load_pos_dominance()
    rows = [dom.get(w) for w in gaps['word']]
    gaps['corpus_n'] = [int(r.n) if r is not None else 0 for r in rows]
    gaps['corpus_dominant'] = [r.dominant if r is not None else '' for r in rows]
    gaps['corpus_noun_share'] = [float(r.noun_share) if r is not None else ''
                                 for r in rows]
    readings = [corpus_reading(r) if r is not None else ('', '', False)
                for r in rows]
    gaps['corpus_tag'] = [t for _, t, _ in readings]
    gaps['corpus_name'] = [nm for _, _, nm in readings]
    corpus_flag = pd.Series([f for f, _, _ in readings], index=gaps.index)
    newly = (gaps['flag_reason'] == '') & (corpus_flag != '')
    gaps.loc[newly, 'flag_reason'] = corpus_flag[newly]
    if len(dom):
        print(f'corpus POS evidence     : {int((gaps["corpus_n"] > 0).sum()):,} of '
              f'{len(gaps):,} candidates appear in the tagged corpora')
        print(f'  flagged by the corpus : {int(newly.sum()):,}')
        print(f'  advisory tags         : {int((gaps["corpus_tag"] != "").sum()):,}')

    probe_words_seen = set()

    # Override: modernvocabularyprobe.csv is the project's own human-vetted
    # list of modern words that belong in the dataset. If the automatic flag
    # disagrees with that ground truth (e.g. "wifi" -> Wi-Fi, "pilates" ->
    # Pilates -- genericised trademarks, not proper nouns), trust the human
    # call and clear the flag rather than silently keep excluding it.
    if probe_path:
        probe = pd.read_csv(probe_path, keep_default_na=False, na_values=[])
        probe_words = set(probe.iloc[:, 0]) if probe.shape[1] == 1 else set(probe['word'])
        overridden = gaps['word'].isin(probe_words) & (gaps['flag_reason'] != '')
        if overridden.any():
            print(f'probe override (trusted human ground truth over the auto-flag): '
                  f'{", ".join(gaps.loc[overridden, "word"].tolist())}')
        gaps.loc[overridden, 'flag_reason'] = ''
        probe_words_seen = probe_words

    gaps['likely_noun'] = gaps['flag_reason'] == ''

    # ---- name-list suspicion (a sort tier, deliberately NOT a flag) --------
    # names-lowercase.csv (build_name_list.py) is the Namenet + Wikipedia name
    # union. It is good evidence but not conclusive on its own: it cannot tell
    # "washington", which is a name in essentially every use, apart from "nice",
    # "tell", "teach" and "begin", which are ordinary adjectives and verbs that
    # merely happen to also name a place or a person. Separating those needs a
    # POS or capitalisation-frequency source, and none is available offline.
    #
    # So a name-list hit does NOT set flag_reason and does NOT clear
    # likely_noun. Burying these among the function words would contradict the
    # standing decision (see the report) that nominalised adjectives and
    # verb-derived nouns stay in the queue for a human. Instead they keep
    # likely_noun and sort as a labelled band directly beneath the clean rows:
    # visible, ranked, explicitly marked, nothing hidden.
    #
    # Words that are ALSO an OEWN common noun are not marked at all -- OEWN
    # itself vouching for a common-noun sense outranks a bare name match.
    try:
        nl = pd.read_csv(NAME_LIST_PATH, keep_default_na=False, na_values=[])
        name_words = set(nl.loc[~nl['also_oewn_noun'].astype(bool), 'name'])
    except FileNotFoundError:
        name_words = set()
    name_words -= probe_words_seen
    gaps['name_suspect'] = gaps['word'].isin(name_words) | gaps['corpus_name']
    looked = [pos_lookup(w) for w in gaps['word']]
    gaps['pos_tags'] = [x[0] for x in looked]
    gaps['lemma'] = [x[1] for x in looked]
    gaps['pos_overlap'] = [x[2] for x in looked]

    # Potential plurals: the singular may be a dataset row or another gap
    # candidate, so both sides are in scope.
    try:
        sen_nouns = set(pd.read_csv(gaps_path.replace('.gaps.csv', ''),
                                    keep_default_na=False, na_values=[])['noun'])
    except (FileNotFoundError, KeyError):
        sen_nouns = set()
    have_all = sen_nouns | set(gaps['word'])
    gaps['plural_of'] = [plural_of(w, have_all) for w in gaps['word']]

    # ---- human rulings beat every automatic flag and tag ------------------
    try:
        v = pd.read_csv(VERDICTS_PATH, keep_default_na=False, na_values=[])
        verdict = {w.strip(): normalise_verdict(d)
                   for w, d in zip(v['word'], v['verdict'])}
    except (FileNotFoundError, KeyError):
        verdict = {}
    gaps['verdict'] = gaps['word'].map(verdict).fillna('')
    ruled = gaps['verdict'] != ''
    if ruled.any():
        gaps.loc[ruled & (gaps['verdict'] == 'noun'),
                 ['flag_reason', 'name_suspect', 'pos_overlap']] = ['', False, '']
        gaps.loc[ruled & (gaps['verdict'] == 'name'), 'name_suspect'] = True
        gaps.loc[ruled & (gaps['verdict'] == 'name'), 'flag_reason'] = ''
        gaps.loc[ruled & (gaps['verdict'] == 'verb'), 'pos_overlap'] = 'verb (reviewed)'
        gaps.loc[ruled & (gaps['verdict'] == 'adj'), 'pos_overlap'] = 'adjective (reviewed)'
        # A ruling of verb/adj/noise is a decision about THIS QUEUE: the word
        # is not a common noun the dataset is missing. It leaves the clean
        # band. `name` deliberately does not -- names stay visible as their
        # own tier, which is the standing decision recorded in the report.
        for v, why in (('verb', 'verb (reviewed)'),
                       ('adj', 'adjective (reviewed)'),
                       ('noise', 'not a usable common noun (reviewed)')):
            gaps.loc[ruled & (gaps['verdict'] == v), 'flag_reason'] = why
        gaps['likely_noun'] = gaps['flag_reason'] == ''
        print(f'human verdicts applied ({VERDICTS_PATH}): {int(ruled.sum())} of {len(verdict)} '
              f'-> ' + ', '.join(f'{k}:{int(n)}' for k, n
                                 in gaps.loc[ruled, 'verdict'].value_counts().items()))

    gaps = gaps.sort_values(['likely_noun', 'name_suspect', 'zipf'],
                            ascending=[False, True, False]).reset_index(drop=True)
    gaps.to_csv(gaps_path, index=False)

    # ---- the name_suspect band as a bare review sheet ---------------------
    # One noun per line, zipf order, nothing else: the reviewer deletes the
    # lines that really are just proper nouns, and whatever survives is a
    # keep-list. Same shape as reviews/uk_reviewed.csv, which wx_join.py
    # already consumes that way, so the outcome wires in identically.
    band_path = gaps_path.replace('.gaps.csv', '.name_suspect.csv')
    band = gaps.loc[gaps['likely_noun'] & gaps['name_suspect'], ['word']]
    band.rename(columns={'word': 'noun'}).to_csv(band_path, index=False)
    print(f'\nname_suspect review sheet: {len(band):,} nouns -> {band_path}')

    # ---- the case-variant bucket, as a fillable review sheet --------------
    # This is the bucket that cannot be resolved mechanically: it mixes real
    # names (pegasus, madeira) with ordinary common nouns that merely derive
    # from one (nazism, darwinism, olympiad, merlot). Both have a Title-case
    # `variant_of`, so no rule separates them -- only a human does. The sheet
    # carries a pre-filled `verdict` guess for speed; correct it and append the
    # rows to gaps_verdicts.csv.
    cv_path = gaps_path.replace('.gaps.csv', '.case_variant.csv')
    cv = gaps[(gaps['flag_reason'] == 'case variant of a proper noun')
              & (gaps['verdict'] == '')].copy()
    # A name-derived word carrying a common-noun-forming suffix is far more
    # often an ordinary noun than a name, so guess `noun` for those and `name`
    # otherwise. A guess only -- it is there to be overwritten.
    NOUN_SUFFIXES = ('ism', 'ist', 'ology', 'ologist', 'ography', 'phobia',
                     'iad', 'ization', 'isation', 'ite', 'ana', 'ese')
    cv['verdict'] = ['noun' if w.endswith(NOUN_SUFFIXES) else 'name'
                     for w in cv['word']]
    cv['note'] = ''
    cv[['word', 'verdict', 'note', 'zipf', 'variant_of', 'first_gloss']] \
        .to_csv(cv_path, index=False)
    print(f'case-variant review sheet: {len(cv):,} rows -> {cv_path} '
          f'(guessed noun:{int((cv["verdict"]=="noun").sum())} '
          f'name:{int((cv["verdict"]=="name").sum())})')

    pl = gaps['plural_of'] != ''
    print(f'potential plurals tagged: {int(pl.sum()):,}')
    print('   ', ', '.join(f'{w}<-{p}' for w, p
                           in zip(gaps.loc[pl, 'word'], gaps.loc[pl, 'plural_of'])))

    tagged = gaps['pos_overlap'] != ''
    print(f'pos_overlap tagged: {int(tagged.sum()):,}')
    for t, n in gaps.loc[tagged, 'pos_overlap'].value_counts().items():
        print(f'    {t:24s} {n:,}')

    n_flagged = (~gaps['likely_noun']).sum()
    print(f'flagged (non-noun-dominant): {n_flagged:,}')
    for reason, n in gaps.loc[~gaps['likely_noun'], 'flag_reason'].value_counts().items():
        print(f'    {reason:32s} {n:,}')
    clean = gaps['likely_noun'] & ~gaps['name_suspect']
    print(f'likely_noun remaining      : {gaps["likely_noun"].sum():,}')
    print(f'    clean                        {int(clean.sum()):,}')
    print(f'    name_suspect (sorts below)   '
          f'{int((gaps["likely_noun"] & gaps["name_suspect"]).sum()):,}')

    borderline = gaps[(~gaps['likely_noun']) & (gaps['n_senses'] >= 3)]
    if len(borderline):
        print(f'\nflagged but 3+ noun senses -- worth a manual glance ({len(borderline)}):')
        print(', '.join(borderline['word'].tolist()))

    print('\ntop 40 of the re-ranked review queue (clean, by zipf):')
    print(', '.join(gaps[clean].head(40)['word'].tolist()))
    ns = gaps[gaps['likely_noun'] & gaps['name_suspect']]
    if len(ns):
        print(f'\ntop 40 of the name_suspect band ({len(ns):,} rows, sorts beneath the clean ones):')
        print(', '.join(ns.head(40)['word'].tolist()))

    if probe_path:
        probe = pd.read_csv(probe_path, keep_default_na=False, na_values=[])
        probe_words = set(probe.iloc[:, 0]) if probe.shape[1] == 1 else set(probe['word'])
        hit = gaps[gaps['word'].isin(probe_words)]
        mis = hit[~hit['likely_noun']]
        print(f'\nmodern-vocabulary-probe words present in gaps.csv: {len(hit)}')
        if len(mis):
            print(f'  of those, flagged as non-noun-dominant (check these!): {", ".join(mis["word"].tolist())}')
        else:
            print('  none of them got flagged -- clean.')

    print(f'\nrewritten: {gaps_path}')


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
