#!/usr/bin/env python3
"""
wx_pos.py — the part-of-speech inventory of every English word in the dump.

`wx_extract.py` keeps only `pos == "noun"` entries, which makes one class of
question unanswerable: what ELSE is this word? The top of the gap queue is
full of words whose problem is not that they are rare but that they are not
nouns at all -- `oh` and `ha` (interjections), `de` and `pre` (prefixes),
`st` and `al` (abbreviations), `ve` and `na` (contraction fragments).
Wiktionary knows all of that; wx_extract just throws it away.

This pass keeps every English entry and records the POS set with a sense
count per POS, plus the head-word senses that mark a word as an abbreviation
or initialism.

Output: wiktionary-pos.csv

    word, pos_list, n_pos, noun_senses, total_senses, abbrev

`pos_list` is `pos:senses` pairs, most senses first (`noun:12;verb:3`), so a
consumer can ask both "is noun among them" and "is noun the biggest".
`abbrev` is 1 when any sense is tagged abbreviation/initialism/acronym or
its gloss opens with one of those words.

Usage:  python3 wx_pos.py raw-wiktextract-data.jsonl.gz wiktionary-pos.csv
"""
import sys, csv, re
from collections import defaultdict

from wx_extract import open_maybe_gz, loads, FAST

ABBREV_TAGS = {'abbreviation', 'initialism', 'acronym', 'contraction'}
ABBREV_RE = re.compile(r'\A\s*(?:\([^)]{0,40}\)\s*)?'
                       r'(?:an?\s+)?(?:abbreviation|initialism|acronym|'
                       r'contraction|clipping|short\s+for)\b', re.IGNORECASE)


def main(src, dst):
    n_lines = n_en = 0
    pos_counts = defaultdict(lambda: defaultdict(int))
    abbrev = set()
    with open_maybe_gz(src) as fh:
        for line in fh:
            n_lines += 1
            if n_lines % 1_000_000 == 0:
                print(f'  ...{n_lines:,} lines, {n_en:,} English entries',
                      file=sys.stderr, flush=True)
            if '"lang_code": "en"' not in line and '"lang_code":"en"' not in line:
                continue
            try:
                e = loads(line)
            except Exception:
                continue
            if e.get('lang_code') != 'en':
                continue
            word, pos = e.get('word'), e.get('pos')
            if not word or not pos:
                continue
            n_en += 1
            senses = e.get('senses') or []
            pos_counts[word][pos] += max(1, len(senses))
            for s in senses:
                if ABBREV_TAGS & set(s.get('tags') or []):
                    abbrev.add(word)
                    break
                g = (s.get('glosses') or [''])[0]
                if g and ABBREV_RE.match(g):
                    abbrev.add(word)
                    break

    with open(dst, 'w', newline='', encoding='utf-8') as out:
        wr = csv.writer(out)
        wr.writerow(['word', 'pos_list', 'n_pos', 'noun_senses',
                     'total_senses', 'abbrev'])
        for w in sorted(pos_counts):
            c = pos_counts[w]
            ordered = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
            wr.writerow([w, ';'.join(f'{p}:{n}' for p, n in ordered), len(c),
                         c.get('noun', 0), sum(c.values()), int(w in abbrev)])

    print(f'\nlines read     : {n_lines:,}', file=sys.stderr)
    print(f'English entries: {n_en:,} -> {len(pos_counts):,} distinct words',
          file=sys.stderr)
    print(f'abbreviations  : {len(abbrev):,}', file=sys.stderr)
    print(f'written        : {dst}', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
