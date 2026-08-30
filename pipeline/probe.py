#!/usr/bin/env python3
"""
probe.py -- run a domain word list against a SEN release and report coverage.

A release's own counts say how many words it has, never which words it is
missing. The only way to find a hole is to bring a list from outside and ask.
`reviews/modernvocabularyprobe.csv` did this for modern vocabulary and is why
`microplastic` survives the frequency cutoff; this script generalises it so any
domain can be checked in one command.

Every probe word lands in exactly one of four buckets:

  playable   in the release, `allowed`
  rejected   in the release, not allowed -- the reason is printed, and a
             rejection is not automatically a bug: `pcb` really is an
             abbreviation, `si` really is a symbol
  absent     no row at all. The gap worth acting on
  not a word the probe should contain -- caught by the assertions below, not
             a bucket: multi-word entries, capitals and duplicates fail early,
             because a probe that quietly drops half its rows reports a
             coverage number that is too good

For every absent word the report says what the upstream sources know, which is
what decides the fix:

  SCOWL n / Wiktionary noun -> add it: the join missed it or the size cut hid it
  Wiktionary only           -> a gaps-queue ruling away
  uppercase only            -> the sources have it, as `LED` or `PCB`. SEN is a
                               lowercase dataset and nothing folds case, so an
                               initialism that has become an ordinary word is
                               invisible to the join. Deliberate for `AABNCP`,
                               wrong for `LED`
  neither                   -> too new or too specialist for any source; it
                               belongs in `reviews/manual-entry.csv`, by hand

Usage
-----
    python3 pipeline/probe.py reviews/electronics-probe.csv
    python3 pipeline/probe.py words.txt --release sen-2026-08-30.csv --out work/probe-missing.csv

The probe file may be a one-word-per-line text file, or a CSV with a `word`
column and optionally a `group` column to break the report down by section.
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict

WORD_RE = re.compile(r'[a-z]+')
DEFAULT_RELEASE_GLOB = 'sen-*.csv'


def latest_release():
    import glob
    files = sorted(glob.glob(DEFAULT_RELEASE_GLOB))
    if not files:
        sys.exit(f'no {DEFAULT_RELEASE_GLOB} in the current directory')
    return files[-1]


def load_probe(path):
    """-> [(word, group)]. Accepts a CSV with a `word` column, or a word list."""
    with open(path, encoding='utf-8') as fh:
        head = fh.readline()
        fh.seek(0)
        if ',' in head and 'word' in head:
            rows = [(r['word'].strip().lower(), r.get('group', '').strip())
                    for r in csv.DictReader(fh)]
        else:
            rows = [(line.strip().lower(), '') for line in fh if line.strip()]

    bad = [w for w, _ in rows if not WORD_RE.fullmatch(w)]
    assert not bad, (f'{path}: {len(bad)} entries are not single lowercase '
                     f'words, so the coverage number would be wrong: {bad[:8]}')
    dupes = [w for w, n in Counter(w for w, _ in rows).items() if n > 1]
    assert not dupes, f'{path}: duplicate words inflate the count: {dupes[:8]}'
    return rows


def load_csv_column(path, key):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        return {r[key]: r for r in csv.DictReader(fh)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('probe')
    ap.add_argument('--release', default=None,
                    help='default: the highest-sorting sen-*.csv here')
    ap.add_argument('--scowl', default='sources/scowl-pos.csv')
    ap.add_argument('--wikt', default='sources/wiktionary-nouns.csv')
    ap.add_argument('--out', default='work/probe-missing.csv',
                    help='where to write the absent words, with their evidence')
    args = ap.parse_args(argv)

    release = args.release or latest_release()
    sen = load_csv_column(release, 'noun')
    probe = load_probe(args.probe)
    scowl = load_csv_column(args.scowl, 'word')
    wikt = load_csv_column(args.wikt, 'word')

    buckets = defaultdict(list)
    for word, group in probe:
        row = sen.get(word)
        if row is None:
            buckets['absent'].append((word, group))
        elif row['allowed'] == 'True':
            buckets['playable'].append((word, group))
        else:
            buckets['rejected'].append((word, group))

    total = len(probe)
    print(f'{args.probe}: {total} words against {release}\n')
    for name in ('playable', 'rejected', 'absent'):
        n = len(buckets[name])
        print(f'  {name:9s} {n:4d}  ({n / total * 100:5.1f}%)')

    if any(g for _, g in probe):
        print('\nby group:')
        groups = sorted({g for _, g in probe})
        for g in groups:
            counts = {k: sum(1 for _, gg in v if gg == g) for k, v in buckets.items()}
            n = sum(counts.values())
            print(f'  {g:16s} {counts.get("playable", 0):3d} playable  '
                  f'{counts.get("rejected", 0):3d} rejected  '
                  f'{counts.get("absent", 0):3d} absent   (of {n})')

    if buckets['rejected']:
        print('\nrejected, and why:')
        for word, _ in sorted(buckets['rejected']):
            row = sen[word]
            extra = f'  -> {row["suggest_instead"]}' if row['suggest_instead'] else ''
            print(f'  {word:18s} {row["reason"]}{extra}')

    if buckets['absent']:
        print('\nabsent, and what the sources know:')
        fields = ['word', 'group', 'scowl_pos', 'scowl_noun_size',
                  'wikt_noun', 'wikt_gloss', 'verdict']
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8', newline='') as fh:
            out = csv.DictWriter(fh, fieldnames=fields)
            out.writeheader()
            for word, group in sorted(buckets['absent']):
                s, w = scowl.get(word), wikt.get(word)
                s_noun = s is not None and s['scowl_is_noun'] == 'True'
                w_noun = w is not None and bool(w['first_gloss'])
                # Wiktionary files `LED` and `PCB` under their capitals, and
                # SEN is lowercase throughout, so without this the report says
                # "no source has it" about a word both sources carry.
                upper = wikt.get(word.upper())
                if not (s_noun or w_noun) and upper is not None and upper['first_gloss']:
                    why = 'Wiktionary has it only as uppercase ' + word.upper()
                elif s_noun and w_noun:
                    why = 'both sources have it -- the join missed it'
                elif s_noun:
                    why = 'SCOWL only'
                elif w_noun:
                    why = 'Wiktionary only -- rule it in the gaps queue'
                elif s is not None or w is not None:
                    why = 'known, but not as a noun'
                else:
                    why = 'no source has it -- needs manual-entry.csv'
                print(f'  {word:18s} {why}')
                out.writerow({
                    'word': word, 'group': group,
                    'scowl_pos': s['scowl_pos'] if s else '',
                    'scowl_noun_size': s['scowl_noun_size'] if s else '',
                    'wikt_noun': w_noun,
                    'wikt_gloss': ((w or upper)['first_gloss'][:200]
                                   if (w or upper) else ''),
                    'verdict': '',
                })
        print(f'\n  -> {args.out} ({len(buckets["absent"])} rows, '
              f'`verdict` column empty and waiting)')


if __name__ == '__main__':
    main()
