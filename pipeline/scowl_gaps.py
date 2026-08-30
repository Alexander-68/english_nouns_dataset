#!/usr/bin/env python3
"""
scowl_gaps.py -- split the unruled gaps queue by what SCOWL says about it.

`work/sen-v3.csv.gaps.csv` is 5,694 words Wiktionary has and WordNet does not,
none of them ruled. The README calls it "the cheapest remaining vocabulary
win", and it was cheap only in the sense that nothing else was cheaper: the
yield of real nouns per row read drops sharply down the queue, and the queue is
sorted by a frequency that is often the frequency of a *different* part of
speech (see rank_gaps.py).

SCOWL is a fourth opinion that did not exist when the queue was cut, and it has
an opinion about most of it. This script does not rule anything -- it sorts the
queue into three buckets so a human reads the productive one first and never
reads the other two by hand at all:

  gaps-scowl-noun.csv     SCOWL lists the word with a common-noun sense.
                          Two independent curated sources now agree it is a
                          noun. This is the bucket worth reading.
  gaps-scowl-nonnoun.csv  SCOWL lists the word, but only as an adjective,
                          verb, adverb, abbreviation, prefix or suffix. A
                          disagreement, and the useful kind: it names what the
                          word is instead.
  gaps-scowl-absent.csv   SCOWL, at size <= 70, has never heard of it. Names,
                          slang, typos and dump noise: `dougie`, `herzog`,
                          `saas`, `ight`. Absence is weak evidence on its own
                          and strong evidence in bulk.

Ranking inside each bucket
--------------------------
Rows keep every column they had and gain four. The noun bucket sorts by SCOWL
size band first (35 = in 11 of 12 dictionaries, 70 = the specialist tail) and
zipf second, so the words a player might actually type come first regardless of
what `wordfreq` thinks. The other two buckets keep the incoming order, since
nothing in them is meant to be read top-to-bottom.

`--max-size` must match whatever `scowl_pos.py` was run with; the "absent"
bucket means "absent at that cut", not "absent from SCOWL".

Usage
-----
    python3 pipeline/scowl_gaps.py
    python3 pipeline/scowl_gaps.py --gaps work/sen-v3.csv.gaps.csv --out-dir work
"""
import argparse
import csv
import os
from collections import Counter

DEFAULT_GAPS = 'work/sen-v3.csv.gaps.csv'
DEFAULT_SCOWL = 'sources/scowl-pos.csv'
DEFAULT_OUT = 'work'

ADDED = ['scowl_verdict', 'scowl_size', 'scowl_pos', 'scowl_american_standard']


def load_scowl(path):
    with open(path, encoding='utf-8') as fh:
        return {r['word']: r for r in csv.DictReader(fh)}


def classify(word, scowl):
    """-> (bucket, size, pos, american). Size is '' when the word is absent."""
    row = scowl.get(word)
    if row is None:
        return 'absent', '', '', ''
    if row['scowl_is_noun'] == 'True':
        return 'noun', row['scowl_noun_size'], row['scowl_pos'], row['scowl_american_standard']
    return 'nonnoun', row['scowl_size'], row['scowl_pos'], row['scowl_american_standard']


def sort_key(row):
    """Commonest first: SCOWL band, then zipf descending."""
    try:
        size = int(row['scowl_size'])
    except (ValueError, KeyError):
        size = 99
    try:
        zipf = float(row['zipf'])
    except (ValueError, KeyError):
        zipf = 0.0
    return (size, -zipf, row['word'])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gaps', default=DEFAULT_GAPS)
    ap.add_argument('--scowl', default=DEFAULT_SCOWL)
    ap.add_argument('--out-dir', default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    scowl = load_scowl(args.scowl)
    with open(args.gaps, encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames + ADDED
        rows = list(reader)

    buckets = {'noun': [], 'nonnoun': [], 'absent': []}
    for row in rows:
        bucket, size, pos, american = classify(row['word'], scowl)
        row.update(scowl_verdict=bucket, scowl_size=size, scowl_pos=pos,
                   scowl_american_standard=american)
        buckets[bucket].append(row)
    buckets['noun'].sort(key=sort_key)

    os.makedirs(args.out_dir, exist_ok=True)
    for bucket, out_rows in buckets.items():
        path = os.path.join(args.out_dir, f'gaps-scowl-{bucket}.csv')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(out_rows)
        print(f'{path}: {len(out_rows):,} rows')

    total = len(rows)
    print(f'\n{total:,} unruled gaps ->')
    for bucket in ('noun', 'nonnoun', 'absent'):
        n = len(buckets[bucket])
        print(f'  {bucket:8s} {n:6,}  ({n / total * 100:4.1f}%)')
    bands = Counter(r['scowl_size'] for r in buckets['noun'])
    print('  noun bucket by SCOWL band: '
          + ', '.join(f'{b}:{bands[b]:,}' for b in sorted(bands, key=int)))
    # What the disagreements say the word is instead -- the reason this bucket
    # is worth writing out rather than just dropping.
    heads = Counter(r['scowl_pos'].split(':')[0] for r in buckets['nonnoun'])
    print('  nonnoun bucket, dominant SCOWL pos: '
          + ', '.join(f'{p}:{n:,}' for p, n in heads.most_common(8)))


if __name__ == '__main__':
    main()
