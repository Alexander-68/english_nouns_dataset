#!/usr/bin/env python3
"""
apply_scowl.py -- sen-v3 + SCOWL -> sen-v4, and open the obscure band.

Two changes, both of them widenings, both reversible by not running this stage.

1. The obscure band becomes playable, marked
-------------------------------------------
`wx_join.py` rejects 9,670 words with `excluded_because = 'obscure'`. Every one
of them is a real noun that survived every other test and then hit a frequency
floor: `wordfreq` scores it 0.0, so `tier()` returns OBSCURE, so it is out.

That was the dataset making a game decision on the game's behalf, which is the
one thing this project keeps saying it will not do. The mark mechanism already
exists for exactly this: a word the dataset doubts is kept and labelled, and
the game chooses. So these rows flip to `allowed`, keep their tier of OBSCURE,
and carry `marks = 'obscure'`.

A game that wants a friendly list still cuts at FAMILIAR and never sees them.
A game that wants the widest defensible vocabulary takes them and shows the
player the mark. Nothing is lost either way, and the reason no longer has to
double as a verdict.

2. SCOWL's nouns are added
--------------------------
`scowl_pos.py` produces 45k common nouns at size <= 70 from the English Speller
Database. 12,148 of them are in no SEN row at all. They arrive here as new rows
built the same way `manual-entry.csv` rows are, and are ruled by the same
policies the rest of the dataset already follows -- this stage adds vocabulary,
it does not change any rule:

  * a closed-class function word -> rejected. SCOWL tags `all`, `if`, `she`
    and `you` as nouns because English does nominalise them ("the whys and
    hows"), and Wiktionary glosses them, so nothing else in the chain catches
    them. `rank_gaps.CLOSED_CLASS` is the closed list already written for this
  * not standard-American spelling  -> rejected, 'british/commonwealth spelling
    variant', with the American form suggested where it can be derived
  * Wiktionary lists it, but with no noun sense -> rejected, naming the part of
    speech Wiktionary gives instead
  * Wiktionary lists it as an inflected or plural-only form -> rejected as such
  * ruled by `reviews/scowl-glosses.csv` -> that ruling wins over all of the
    above, because a person read the word
  * otherwise -> allowed, marked with whatever SCOWL and the corpus still doubt

Definitions
-----------
A word with no gloss cannot be shown to a player, so every added word gets one:

  * 11,760 from Wiktionary's first sense, the same source the rest of the
    dataset uses
  * 168 have no Wiktionary entry at all and are hand-ruled in
    `reviews/scowl-glosses.csv` -- 112 with a definition written for them, 56
    ruled out as taxonomic genera, misspellings in SCOWL's own data, Latin and
    French words that never naturalised, or one dated slur

`reviews/scowl-glosses.csv` is a human ruling file. Like every other file in
`reviews/`, it is the authority and is never regenerated.

Usage
-----
    python3 pipeline/apply_scowl.py                       # work/sen-v3.csv -> work/sen-v4.csv
    python3 pipeline/apply_scowl.py --no-open-obscure     # only add SCOWL's nouns
"""
import argparse
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_join import (  # noqa: E402  -- the rules live there; do not restate them
    UK_US_IRREGULAR, UK_US_SUFFIXES, corpus_mark, tier,
)
from rank_gaps import CLOSED_CLASS, NAME_LIST_PATH  # noqa: E402

DEFAULT_IN = 'work/sen-v3.csv'
DEFAULT_OUT = 'work/sen-v4.csv'
SCOWL_PATH = 'sources/scowl-pos.csv'
WIKT_NOUNS = 'sources/wiktionary-nouns.csv'
WIKT_POS = 'sources/wiktionary-pos.csv'
POS_DOMINANCE = 'sources/pos-dominance.csv'
GLOSSES_PATH = 'reviews/scowl-glosses.csv'

SOURCE = 'scowl'


def truthy(v):
    """Source tables disagree on how they spell a boolean.

    `scowl-pos.csv` round-trips real bools through pandas, the Wiktionary
    extracts use 0/1 ints, and a hand-edited sheet may hold the strings. All
    three mean the same thing, and comparing any one of them to `'True'` is how
    this stage silently added nothing on its first run.
    """
    return v in (True, 1) or (isinstance(v, str) and v.strip() in ('True', 'true', '1'))


def field(row, name, default=''):
    """`row[name]` when `row` is a present pandas Series, else `default`.

    A Series has no usable truth value, so `(row or {}).get(name, '')` raises
    rather than falling back the way it reads.
    """
    return default if row is None else row[name]

# Hand rulings in reviews/scowl-glosses.csv -> (reason, mark). Same shape and
# same wording as wx_join.VERDICT_REASON, so a rejected SCOWL row reads
# identically to a rejected gaps-review row.
GLOSS_VERDICT = {
    'noun':    ('', ''),
    'name':    ('proper noun or other non-noun (reviewed)', ''),
    'noise':   ('not a usable common noun (reviewed)', ''),
    'verb':    ('verb (reviewed)', ''),
    'adj':     ('adjective (reviewed)', ''),
    'variant': ('spelling variant of another word (reviewed)', ''),
}

# Wiktionary's dominant part of speech -> the reason wx_join already uses for
# it. Only consulted when Wiktionary has the word but gives it no noun sense.
WIKT_POS_REASON = {
    'adj': 'adjective (not a noun)',
    'verb': 'verb (not a noun)',
    'adv': 'adverb (not a noun)',
    'name': 'proper noun or other non-noun (reviewed)',
}


def american_form(word, have):
    """Best guess at the American spelling of `word`, or '' if none lands.

    Same two sources wx_join uses, in the same order: the hand-checked
    irregular table first, then the suffix correspondences. A guess that is not
    itself a word in the dataset is discarded rather than suggested.
    """
    guess = UK_US_IRREGULAR.get(word, '')
    if not guess:
        for uk, us in UK_US_SUFFIXES:
            if word.endswith(uk):
                guess = word[:-len(uk)] + us
                break
    return guess if guess in have and guess != word else ''


def load_glosses(path):
    if not os.path.exists(path):
        print(f'note: {path} missing; SCOWL words with no Wiktionary gloss '
              f'will be rejected as unglossed', file=sys.stderr)
        return {}
    df = pd.read_csv(path, keep_default_na=False, na_values=[])
    unknown = set(df['verdict']) - set(GLOSS_VERDICT)
    assert not unknown, f'{path}: unknown verdicts {unknown}'
    return {r['word']: r for _, r in df.iterrows()}


def open_obscure(sen):
    """Flip `excluded_because == 'obscure'` to allowed, marked 'obscure'."""
    band = sen['excluded_because'] == 'obscure'
    sen.loc[band, 'recommended'] = True
    sen.loc[band, 'excluded_because'] = ''
    # Prepend, so the widest-cut signal reads first in a `; `-joined list.
    sen.loc[band, 'marks'] = ('obscure; ' + sen.loc[band, 'marks']).str.rstrip('; ')
    return int(band.sum())


def build_rows(new_words, scowl, wnouns, wpos, dom, glosses, names, have, zipf_of):
    rows = []
    for word in sorted(new_words):
        s = scowl[word]
        wn = wnouns.get(word)
        wp = wpos.get(word)
        gl = glosses.get(word)
        d = dom.get(word)

        z = zipf_of(word)
        marks, reason, suggest = [], '', ''

        definition = wn['first_gloss'] if wn is not None else ''
        if not definition and gl is not None:
            definition = gl['definition']

        # ---- rule the word, most authoritative signal last ---------------
        if word in CLOSED_CLASS:
            reason = 'function word (not a noun)'
        elif not truthy(s['scowl_american_standard']):
            reason = 'british/commonwealth spelling variant'
            suggest = american_form(word, have)
            marks.append('UK/Commonwealth spelling')
        elif wn is not None and truthy(wn['plural_only']):
            reason = 'plural-only (Wiktionary)'
        elif wn is not None and truthy(wn['is_inflected_form']):
            reason = 'inflected form (Wiktionary)'
        elif wn is None and wp is not None:
            # Wiktionary knows the word and gives it no noun sense at all.
            # SCOWL disagreeing is exactly the kind of doubt worth recording,
            # so the word is rejected AND marked with the disagreement.
            head = (wp['pos_list'].split(':')[0] or '').strip()
            reason = WIKT_POS_REASON.get(head, 'not a usable common noun (reviewed)')
            marks.append('noun in SCOWL, not in Wiktionary')
        elif not definition and gl is None:
            # No gloss from anywhere and nobody ruled on it. Never silently
            # allowed: a word a player cannot be shown is not playable.
            reason = 'not in Wiktionary'
            marks.append('noun in SCOWL, unglossed')

        # A person who read the word outranks every derived rule above, which
        # is the same precedence manual-entry.csv already has in wx_join.
        if gl is not None:
            reason, extra = GLOSS_VERDICT[gl['verdict']]
            suggest = gl['suggest_instead'] or suggest
            if extra:
                marks.append(extra)
            if gl['marks']:
                marks.append(gl['marks'])
            if gl['verdict'] != 'noun':
                marks = [m for m in marks if m != 'noun in SCOWL, unglossed']

        # ---- marks: everything still in doubt ----------------------------
        if z <= 0.0:
            marks.append('obscure')
        if ({'name', 'upper'} & set(s['scowl_subtypes'].split(';'))
                or word in names):
            # A name-list hit MARKS and never rejects, the same call
            # rank_gaps.py documents: most of these are ordinary obscure nouns
            # that merely coincide with a name -- `solidago`, `psalter`,
            # `bodhisattva`, `torah`.
            marks.append('possible name')
        pos_heads = {p.split(':')[0] for p in s['scowl_pos'].split(';') if p}
        if 'v' in pos_heads:
            marks.append('also a verb (SCOWL)')
        if 'aj' in pos_heads:
            marks.append('also an adjective (SCOWL)')
        marks.append(corpus_mark(d))
        if wn is None and gl is not None and gl['verdict'] == 'noun':
            marks.append('not in Wiktionary, glossed by hand')

        seen, uniq = set(), []
        for m in marks:
            if m and m not in seen:
                seen.add(m)
                uniq.append(m)

        rows.append({
            'noun': word, 'start': word[0], 'end': word[-1], 'length': len(word),
            'zipf': z, 'tier': tier(z), 'senses': 1,
            'lexfile': '', 'register': '', 'domain': '', 'end_pressure': 0.0,
            'plural_suspect': False, 'plural_of_listed': False,
            'no_distinct_plural': False, 'also_proper_noun': False,
            'in_wn30': False, 'definition': definition,
            'name_suspect': 'possible name' in uniq, 'pos_overlap': '',
            'pos_tags': '', 'lemma': '', 'verdict_reason': '',
            'source': SOURCE, 'human_kept': False,
            'wikt_known': wn is not None or wp is not None,
            'wikt_countable': wn is not None and truthy(wn['countable']),
            'wikt_uncountable': wn is not None and truthy(wn['uncountable']),
            'wikt_plural_only': wn is not None and truthy(wn['plural_only']),
            'wikt_inflected': wn is not None and truthy(wn['is_inflected_form']),
            'wikt_form_of': field(wn, 'form_of'),
            'wikt_variant_of': field(wn, 'variant_of'),
            'wikt_variant_kind': field(wn, 'variant_kind'),
            'wikt_regions': field(wn, 'regions'),
            'wikt_american_equivalent': '', 'wikt_uk_residue_rule': '',
            'wikt_british_variant': reason == 'british/commonwealth spelling variant',
            'wikt_ing_reviewed_us': '', 'reviewed_variant_of': suggest,
            'reviewed_spelling_variant': bool(gl is not None
                                              and gl['verdict'] == 'variant'),
            'reviewed_plural': False, 'reviewed_variant_kept': '',
            'recommended': reason == '', 'suggest_instead': suggest,
            'excluded_because': reason,
            'corpus_dominant': d.dominant if d is not None else '',
            'corpus_n': int(d.n) if d is not None else 0,
            'corpus_noun_share': float(d.noun_share) if d is not None else '',
            'wikt_pos_list': field(wp, 'pos_list'),
            'wikt_abbrev': wp is not None and truthy(wp['abbrev']),
            'marks': '; '.join(uniq),
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sen', default=DEFAULT_IN)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--scowl', default=SCOWL_PATH)
    ap.add_argument('--no-open-obscure', action='store_true',
                    help='leave the obscure band rejected')
    ap.add_argument('--no-add-words', action='store_true',
                    help='open the obscure band but add no SCOWL words')
    args = ap.parse_args(argv)

    from wordfreq import zipf_frequency

    sen = pd.read_csv(args.sen, keep_default_na=False, na_values=[])
    before_allowed = int(sen['recommended'].sum())

    opened = 0 if args.no_open_obscure else open_obscure(sen)
    print(f'obscure band opened: {opened:,} rows now allowed, marked "obscure"')

    added = pd.DataFrame()
    if not args.no_add_words:
        scowl = {r['word']: r for _, r in
                 pd.read_csv(args.scowl, keep_default_na=False, na_values=[]).iterrows()}
        have = set(sen['noun'])
        new_words = [w for w, r in scowl.items()
                     if truthy(r['scowl_is_noun']) and w not in have]

        wanted = set(new_words)
        wnouns, wpos = {}, {}
        for _, r in pd.read_csv(WIKT_NOUNS, keep_default_na=False,
                                na_values=[]).iterrows():
            if r['word'] in wanted:
                wnouns[r['word']] = r
        for _, r in pd.read_csv(WIKT_POS, keep_default_na=False,
                                na_values=[]).iterrows():
            if r['word'] in wanted:
                wpos[r['word']] = r
        dom = {r.word: r for r in pd.read_csv(POS_DOMINANCE).itertuples()
               if r.word in wanted}
        glosses = load_glosses(GLOSSES_PATH)

        try:
            names = set(pd.read_csv(NAME_LIST_PATH)['name'])
        except (FileNotFoundError, KeyError):
            names = set()
        rows = build_rows(new_words, scowl, wnouns, wpos, dom, glosses, names,
                          have | wanted,
                          lambda w: round(zipf_frequency(w, 'en'), 2))
        added = pd.DataFrame(rows, columns=sen.columns)
        if len(added):
            added = added.astype(sen.dtypes.to_dict())
            sen = pd.concat([sen, added], ignore_index=True)

    # ---- gates ---------------------------------------------------------
    assert sen['noun'].is_unique, 'duplicate nouns after the merge'
    bad = sen['recommended'] & (sen['excluded_because'] != '')
    assert not bad.any(), f'allowed rows with a reason: {list(sen.loc[bad, "noun"][:5])}'
    missing = (~sen['recommended']) & (sen['excluded_because'] == '')
    assert not missing.any(), f'rejected rows with no reason: {list(sen.loc[missing, "noun"][:5])}'
    # The point of the definitions pass: nothing playable is unshowable.
    blank = sen['recommended'] & (sen['definition'] == '')
    assert not blank.any(), \
        f'allowed rows with no definition: {list(sen.loc[blank, "noun"][:8])}'

    sen.to_csv(args.out, index=False)

    now_allowed = int(sen['recommended'].sum())
    print(f'\n{args.out}: {len(sen):,} rows, {now_allowed:,} allowed '
          f'(was {before_allowed:,} of {len(sen) - len(added):,})')
    if len(added):
        n_ok = int(added['recommended'].sum())
        print(f'  SCOWL words added: {len(added):,}, {n_ok:,} allowed')
        print('  added, by rejection reason:')
        for r, n in added.loc[~added['recommended'], 'excluded_because'] \
                .value_counts().items():
            print(f'    {r:48s} {n:,}')
        print('  added, by tier (allowed only):')
        print(added[added['recommended']]['tier'].value_counts()
              .reindex(['CORE', 'COMMON', 'FAMILIAR', 'UNCOMMON', 'RARE', 'OBSCURE'])
              .dropna().to_string())
        tally = Counter(m for ms in added['marks'] if ms for m in ms.split('; '))
        print('  added, by mark:')
        for m, n in tally.most_common():
            print(f'    {m:48s} {n:,}')


if __name__ == '__main__':
    main()
