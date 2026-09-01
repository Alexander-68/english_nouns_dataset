#!/usr/bin/env python3
"""
release_sen.py — cut a dated, game-facing release of the SEN dataset.

`sen-v3.csv` is the working file: 39 columns, every piece of evidence any rule
was ever derived from, so a verdict can be re-derived without re-running the
pipeline. A game does not need any of that. This writes the subset a game
actually consumes, with the columns renamed to what they mean at the point of
use.

The release is one file, not two, on purpose. Shipping only the playable words
would throw away the thing the last several passes were built to provide: the
ability to say WHY a word is rejected, and what to use instead. Rejected rows
are the point, not overhead.

    allowed = False, reason = "adjective (not a noun)"
    allowed = False, reason = "british/commonwealth spelling variant",
              suggest_instead = "plow"
    allowed = True,  same_word_as = "whiskey"   (whisky: playable, but the
              same word for a game that must not accept both in one chain)

`marks` is the other half of the same idea, and it applies to ALLOWED words
too: it is the doubt the dataset could not resolve, written down instead of
silently acted on -- "possible plural", "possible name", "usually a verb
(corpus)", "possible abbreviation or clipping", "manual - not in Wiktionary,
is it a real noun?". A game may ignore marks, warn on them, or filter by
them; that is a game decision, and this file refuses to make it for you.

Usage
-----
    python3 release_sen.py [sen-v3.csv] [YYYY-MM-DD]

Writes sen-<date>.csv. Defaults to today.
"""
import sys
from datetime import date
import pandas as pd

COLUMNS = {
    'noun': 'noun',
    'start': 'start',
    'end': 'end',
    'length': 'length',
    'zipf': 'zipf',
    'tier': 'tier',
    'recommended': 'allowed',
    'excluded_because': 'reason',
    'marks': 'marks',
    'suggest_instead': 'suggest_instead',
    'reviewed_variant_kept': 'same_word_as',
    'pos_tags': 'pos_tags',
    'lemma': 'lemma',
    'plural_of_listed': 'is_plural',
    'lexfile': 'lexfile',
    'definition': 'definition',
    'source': 'source',
}


def main(sen_path='work/sen-v3.csv', stamp=None):
    stamp = stamp or date.today().isoformat()
    sen = pd.read_csv(sen_path, keep_default_na=False, na_values=[])

    # Integrity gates. A release that contradicts itself is worse than no
    # release, and both of these are cheap to check and impossible to eyeball.
    assert sen['noun'].is_unique, 'duplicate nouns'
    bad = sen['recommended'] & (sen['excluded_because'] != '')
    assert not bad.any(), f'allowed rows carrying a reason: {list(sen.loc[bad, "noun"][:5])}'
    missing = (~sen['recommended']) & (sen['excluded_because'] == '')
    assert not missing.any(), f'rejected rows with no reason: {list(sen.loc[missing, "noun"][:5])}'

    out = sen[list(COLUMNS)].rename(columns=COLUMNS).sort_values('noun')
    # A suggestion the player cannot play is worse than none: `aunty` said
    # "play auntie", and `auntie` was itself rejected. The pipeline only ever
    # checked that the suggested word HAS a row, which it does. Checked here
    # because this is where `allowed` is final -- the human keep-list flips
    # rows after the suggestion is chosen.
    playable = set(out.loc[out['allowed'], 'noun'])
    dangling = (out['suggest_instead'] != '') & ~out['suggest_instead'].isin(playable)
    if dangling.any():
        print(f'  suggestions dropped (target not playable): {int(dangling.sum()):,}')
        out.loc[dangling, 'suggest_instead'] = ''
    path = f'sen-{stamp}.csv'
    out.to_csv(path, index=False)

    n_allowed = int(out['allowed'].sum())
    print(f'{path}: {len(out):,} rows, {len(out.columns)} columns')
    print(f'  allowed  : {n_allowed:,} ({n_allowed / len(out) * 100:.1f}%)')
    print(f'  rejected : {len(out) - n_allowed:,}, every one with a reason')
    print(f'  with a replacement suggestion: {int((out["suggest_instead"] != "").sum()):,}')
    marked = out['marks'] != ''
    print(f'  carrying at least one mark   : {int(marked.sum()):,} '
          f'({int((marked & out["allowed"]).sum()):,} of them allowed)')
    print()
    print('marks (a row may carry several):')
    from collections import Counter
    # "spelling variant of colour" is 1,600 distinct marks; count them as one
    # kind, since the interesting number is how many words carry the mark.
    tally = Counter(('spelling variant of another word'
                     if m.startswith('spelling variant of ') else m)
                    for ms in out.loc[marked, 'marks'] for m in ms.split('; '))
    for m, n in tally.most_common():
        print(f'    {m:48s} {n:,}')
    print('\nrejection reasons:')
    for r, n in out.loc[~out['allowed'], 'reason'].value_counts().items():
        print(f'    {r:44s} {n:,}')
    print('\ntier (allowed only):')
    print(out[out['allowed']]['tier'].value_counts()
          .reindex(['CORE', 'COMMON', 'FAMILIAR', 'UNCOMMON', 'RARE', 'OBSCURE'])
          .dropna().to_string())


if __name__ == '__main__':
    main(*sys.argv[1:])
