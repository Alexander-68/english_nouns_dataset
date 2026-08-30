#!/usr/bin/env python3
"""
build_variant_review.py — turn `.variants.csv` into a reviewable sheet.

`.variants.csv` is 2,509 pairs that Wiktionary links with `alt_of` or a
variant gloss. The link means "these two entries are related", which is not
the question the dataset needs answered. Four different things are mixed in:

    zombi / zombie        a real spelling doublet -- keep `zombie`, keep
                          `zombi` as a MARKED variant pointing at it
    stoke / stokes        not a doublet at all: one is a plural of the other
    cozier / cosier       a doublet, but both sides are adjectives
    wild / weald          two unrelated words the gloss regex paired up

So the sheet carries a pre-filled `verdict` for the RELATIONSHIP and two
optional per-side verdicts for what each word IS. Guesses are there to be
overwritten -- the same contract as every other review sheet in this repo.

    verdict     variant | reverse | plural | unrelated
    *_verdict   (blank) | noun | name | adj | verb | adv | noise

`variant`   the `variant` column is the nonstandard spelling; exclude it and
            point it at `canonical`, exactly as British spellings are handled.
`reverse`   the same, the other way round: `canonical` is the odd one.
`plural`    one side is a plural of the other; mark, do not exclude.
`unrelated` not a pair; drop the link and leave both words alone.

Usage:  python3 build_variant_review.py [variants.csv] [out.csv]
"""
import sys

import pandas as pd

from rank_gaps import load_pos_dominance, load_wikt_pos
from wx_extract import VARIANT_RE, variant_kind_of
from wx_join import UK_US_IRREGULAR, uk_us_pattern

NAME_LIST_PATH = 'sources/names-lowercase.csv'
WIKT_NOUNS = 'sources/wiktionary-nouns.csv'


def edit_distance(a, b, cap=3):
    """Levenshtein, given up on past `cap` -- we only care about near-misses."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


# Which side of a regional pair the dataset keeps is a project decision
# (keep the American), and it does not depend on which side Wiktionary hung
# the note on. `humor` says "US standard spelling of humour" and `colour`
# says "Commonwealth ... spelling of color"; both mean keep the American.
AMERICAN_KINDS = {'us', 'u.s.', 'american', 'canada', 'canadian'}

# British -> American spelling rewrites, applied ANYWHERE in the word, not
# just at the end. `uk_us_pattern` in wx_join.py is suffix-anchored, which is
# right for the words it judges but misses `favourite`/`favorite`,
# `colourlessness`/`colorlessness` and every `-isation`/`-ization` pair --
# and those are exactly the ones where Wiktionary hangs the note on the
# American side, so the naive reading would exclude the spelling the project
# has decided to keep.
BRIT_TO_AM = [
    ('isation', 'ization'), ('isations', 'izations'), ('iser', 'izer'),
    ('isers', 'izers'), ('ised', 'ized'), ('ising', 'izing'), ('ise', 'ize'),
    ('yse', 'yze'), ('our', 'or'), ('ae', 'e'), ('oe', 'e'),
    ('logue', 'log'), ('gramme', 'gram'), ('mme', 'm'),
]


def to_american(word):
    """Best-effort American respelling; only used to compare two known forms."""
    out = [word]
    for uk, us in BRIT_TO_AM:
        out = [w.replace(uk, us) for w in out]
    w = out[0]
    for uk, us in (('tre', 'ter'), ('bre', 'ber'), ('cre', 'cer')):
        if w.endswith(uk):
            w = w[:-len(uk)] + us
    return w


def british_side(a, b):
    """Which of the two is the British spelling of the other, or ''."""
    if a == b:
        return ''
    if to_american(a) == b:
        return 'a'
    if to_american(b) == a:
        return 'b'
    return ''


def says_variant_of(gloss, other):
    """The declared kind if this gloss calls itself a variant of `other`."""
    m = VARIANT_RE.match(gloss or '')
    if m and m.group('target').lower() == other.lower():
        return variant_kind_of(m)
    return None


def plural_link(a, b):
    """'stoke'/'stokes' -> which side is the plural, or ''."""
    for x, y, side in ((a, b, 'canonical'), (b, a, 'variant')):
        if y in (x + 's', x + 'es') or (x.endswith('y') and y == x[:-1] + 'ies'):
            return side
    return ''


def main(src='work/sen-v3.csv.variants.csv', dst='work/variants_review.csv',
         sen_path='work/sen-v3.csv'):
    v = pd.read_csv(src, keep_default_na=False, na_values=[])
    sen = pd.read_csv(sen_path, keep_default_na=False, na_values=[],
                      low_memory=False).set_index('noun')
    wx = pd.read_csv(WIKT_NOUNS, keep_default_na=False, na_values=[],
                     low_memory=False).drop_duplicates('word').set_index('word')
    dom = load_pos_dominance()
    wpos = load_wikt_pos(words=set(v['variant']) | set(v['canonical']))
    try:
        nl = pd.read_csv(NAME_LIST_PATH, keep_default_na=False, na_values=[])
        names = set(nl.loc[~nl['also_oewn_noun'].astype(bool), 'name'])
    except FileNotFoundError:
        names = set()

    def side(w):
        z = float(sen.loc[w, 'zipf']) if w in sen.index else 0.0
        d = dom.get(w)
        return {
            'zipf': z,
            'pos': sen.loc[w, 'pos_tags'] if w in sen.index else '',
            'wikt_pos': wpos.get(w, ('',))[0][:20],
            'corpus': f'{d.dominant}:{d.n}' if d is not None else '',
            'name': w in names or (d is not None and d.dominant == 'PROPN'),
            'adj': d is not None and d.dominant == 'ADJ' and d.n >= 10,
            'gloss': wx.loc[w, 'first_gloss'][:70] if w in wx.index else '',
            'gloss_full': wx.loc[w, 'first_gloss'] if w in wx.index else '',
        }

    rows = []
    for r in v.itertuples(index=False):
        a, b = side(r.variant), side(r.canonical)
        pl = plural_link(r.variant, r.canonical)
        dist = edit_distance(r.variant, r.canonical)
        # The decisive evidence is the word's OWN gloss naming the other side
        # ("Alternative spelling of colour."). Edit distance is not evidence:
        # `car`/`cat`, `beach`/`bitch` and `wild`/`weald` are all one edit
        # apart and none of them is a spelling of the other.
        if pl:
            verdict = 'plural'
        elif british_side(r.variant, r.canonical) == 'a':
            verdict = 'variant'          # the variant column is the British one
        elif british_side(r.variant, r.canonical) == 'b':
            verdict = 'reverse'
        else:
            a_kind = says_variant_of(a['gloss_full'], r.canonical)
            b_kind = says_variant_of(b['gloss_full'], r.variant)
            if a_kind is not None:
                verdict = 'reverse' if a_kind in AMERICAN_KINDS else 'variant'
            elif b_kind is not None:
                verdict = 'variant' if b_kind in AMERICAN_KINDS else 'reverse'
            else:
                verdict = 'unrelated'
        # A gloss saying "alternative spelling of X" does not say which side
        # the DATASET should keep. For a British/American pair the project
        # answer is fixed -- keep the American -- and Wiktionary writes the
        # relation from whichever side happens to carry the note, so
        # `labor -> labour` and `colour -> color` both appear. Flip the ones
        # that would exclude the American spelling.
        if verdict in ('variant', 'reverse'):
            drop = r.variant if verdict == 'variant' else r.canonical
            keep = r.canonical if verdict == 'variant' else r.variant
            if (uk_us_pattern(keep, drop)
                    or UK_US_IRREGULAR.get(keep) == drop):
                verdict = 'reverse' if verdict == 'variant' else 'variant'
        rows.append({
            'variant': r.variant, 'canonical': r.canonical, 'verdict': verdict,
            'variant_verdict': ('name' if a['name'] else
                                'adj' if a['adj'] else ''),
            'canonical_verdict': ('name' if b['name'] else
                                  'adj' if b['adj'] else ''),
            'note': '',
            'dist': dist, 'plural_side': pl,
            'v_zipf': a['zipf'], 'c_zipf': b['zipf'],
            'v_pos': a['pos'], 'c_pos': b['pos'],
            'v_wikt': a['wikt_pos'], 'c_wikt': b['wikt_pos'],
            'v_corpus': a['corpus'], 'c_corpus': b['corpus'],
            'v_gloss': a['gloss'], 'c_gloss': b['gloss'],
        })

    out = pd.DataFrame(rows).sort_values(['v_zipf', 'c_zipf'], ascending=False)
    out.to_csv(dst, index=False)
    print(f'{dst}: {len(out):,} pairs')
    print(out['verdict'].value_counts().to_string())
    print(f"pre-marked sides: name {int((out['variant_verdict'] == 'name').sum() + (out['canonical_verdict'] == 'name').sum()):,}, "
          f"adj {int((out['variant_verdict'] == 'adj').sum() + (out['canonical_verdict'] == 'adj').sum()):,}")


if __name__ == '__main__':
    main(*sys.argv[1:])
