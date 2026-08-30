#!/usr/bin/env python3
"""
scowl_pos.py -- turn the SCOWL/ESDB master file into a POS evidence table.

Fourth opinion, after Open English WordNet, Wiktionary and the tagged corpus.
SCOWL (now "English Speller Database", en-wl/wordlist, branch `v2`) publishes
`data/scowl-pre.txt`: 245k entries, each carrying a part of speech, a
commonality band, per-dialect spelling codes and its own inflections. It is the
only one of our sources that is a *curated dictionary aggregate* -- 12dicts,
ENABLE2K, COCA -- rather than a crowd edit history or a parse of running text,
so it is the right tie-breaker for "is this word real, and is it a noun".

What a line looks like
----------------------
    35 [12dicts] 40 [3esl] 70 [3of6] 80 [enable]: box <n> {container}: boxes
    35 [12dicts] ...                            : - <n> {container}: box's
    50 [12dicts] 70 [5d+2a] 85 [ukacd]: A Bv C: abettor <n>: abettors
    70 [moby] 85 [ukacd]: aalii <n>: aaliis
    50 [name] 70 [5d+2a] [moby]: Aachen <n/name?>: Aachen's
    85 [ukacd]: aband

    ^ sizes+sources    ^ dialect codes  ^ word ^pos ^sense    ^ inflections

  * sizes      -- smallest band the word appears in. 35 = in 11 of 12 source
                  dictionaries, 85 = crossword/Scrabble tail. Lower is commoner.
  * dialect    -- A American, B British, C Canadian, D Australian, Z -ize.
                  A lowercase `v` (or uppercase `V`) on a code marks that
                  spelling as a *variant* in that dialect: `A Bv C` = standard
                  in American and Canadian, a variant in British.
  * pos        -- n, aj, v, av, abbr, pre (prefix), suf (suffix), and friends.
                  A `/subtype` narrows a noun: place, name, surname, person,
                  demonym, trademark, upper (capitalised), abbr. A trailing `?`
                  is SCOWL's own uncertainty and is kept as-is.
  * `- ` as the word repeats the last headword *in the same dialect group*,
    which is NOT always the line above: a doublet interleaves its groups, so
    `A Cv DV: - <n>: color's` continues `color`, three lines up, while the
    line directly above it continues `colour`.
  * `{sense}` disambiguates homographs (box the container vs box the shrub).
  * A line with no `<pos>` at all is an untagged entry (11,987 of them). Most
    are multi-word or the 80/85 tail; ~800 are single lowercase words below
    size 80, and those are inflections and adjectives SCOWL never tagged, not
    noun evidence. All are counted and dropped; the self-check bounds them.

Two things this parser got wrong on the first pass, both now asserted against:
  1. `{sense}` braces sit BETWEEN the pos and the inflection colon, so a regex
     that expects `<pos>: infl` silently drops every homograph -- `box`, `tire`,
     `ox`, `beef` all vanished.
  2. Subtypes must be judged per ENTRY, not unioned per word. `president` has a
     plain `<n>` sense and a `<n/upper>` one; unioning them buries the common
     noun under the capitalised one.
  3. A `-` continuation must resume the last headword sharing its dialect
     group. Resuming the previous LINE instead credits `color's` and `colors`
     to `colour`, which then looks like it has an American spelling.

Size cut
--------
Default `--max-size 70`, for two reasons that happen to coincide:

  * Quality. Above 70 is ENABLE2K and the UK Advanced Cryptics Dictionary --
    `assuefaction`, `cunette`, `costeaning`. 30k words no player will type.
  * Licence. SCOWL's Copyright file: a *generated word list larger than 80*
    carries the additional UKACD copyright. Staying at or below 70 means only
    Kevin Atkinson's notice applies. See `sources/README.md`.

Usage
-----
    python3 pipeline/scowl_pos.py                    # writes sources/scowl-pos.csv
    python3 pipeline/scowl_pos.py --max-size 85      # accepts the UKACD terms
    python3 pipeline/scowl_pos.py --self-check       # runs the assertions only
"""
import argparse
import csv
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict

SCOWL_URL = 'https://raw.githubusercontent.com/en-wl/wordlist/v2/data/scowl-pre.txt'
DEFAULT_INPUT = 'sources/scowl/scowl-pre.txt'
DEFAULT_OUTPUT = 'sources/scowl-pos.csv'
DEFAULT_MAX_SIZE = 70

# Noun subtypes that mean "not an ordinary common noun". A trailing `?` is
# SCOWL hedging and is stripped before the test -- `n/name?` is still a name.
NAMEY = {'place', 'name', 'surname', 'person', 'demonym', 'trademark',
         'upper', 'abbr'}

# `35 [12dicts] 40 [3esl] [moby]:` -- one or more size-then-sources groups, or
# a bare source group. Everything up to the first colon.
HEADER_RE = re.compile(
    r'^(?P<sizes>(?:\d+\s*(?:\[[^\]]*\]\s*)*|\[[^\]]*\]\s*)+):\s*(?P<rest>.*)$')
# `A Bv C:` dialect codes, or `_:` / `_~:` accent markers, or a bare `+ = -`.
GROUP_RE = re.compile(r'^(?P<code>[A-Z][A-Za-z=.\- ]*|_[~\-]?|[+=\-])\s*:\s*(?P<rest>.*)$')
# `word <pos> {sense}: inflections`, all but the word optional.
BODY_RE = re.compile(
    r'^(?P<word>.*?)\s+<(?P<pos>[^>]*)>(?:\s*\{(?P<sense>[^}]*)\})?'
    r'(?::\s*(?P<infl>.*))?$')
# A dialect code letter with its variant modifiers: `A`, `Bv`, `CV`, `A.`
DIALECT_RE = re.compile(r'\b([ABCDZ])([vV=.\-]*)')

LOWER_WORD_RE = re.compile(r'[a-z]+')


def parse(path):
    """Yield one dict per tagged entry. One word produces many entries."""
    # Keyed by dialect-group code, because doublets interleave their groups.
    prev_word = {}
    stats = Counter()
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.split('#')[0].rstrip()
            if not line.strip():
                continue
            stats['lines'] += 1
            header = HEADER_RE.match(line)
            if not header:
                stats['no_header'] += 1
                continue
            sizes = [int(n) for n in re.findall(r'\b(\d\d)\b', header['sizes'])]
            rest = header['rest']

            # Strip any number of leading group codes. Only treat a colon-led
            # token as a group when what follows still holds a `<pos>` -- a
            # multi-word headword can contain a colon of its own.
            codes = []
            while True:
                m = GROUP_RE.match(rest)
                if not (m and '<' in m['rest']):
                    break
                codes.append(m['code'].strip())
                rest = m['rest']

            body = BODY_RE.match(rest)
            if not body:
                stats['untagged'] += 1
                # Most untagged entries are multi-word (`able seawoman`,
                # `as soon as`) or the 80/85 tail. The ones that are neither
                # are counted separately: they are the only untagged rows that
                # could have been evidence, and the self-check bounds them.
                head = rest.split(':')[0].strip()
                if LOWER_WORD_RE.fullmatch(head) and (min(sizes) if sizes else 99) < 80:
                    stats['untagged_single_below_80'] += 1
                continue

            group = ' '.join(codes)
            word = body['word'].strip()
            if word == '-':
                word = prev_word.get(group)   # continue this group's headword
            else:
                word = word.lstrip('!+=~').strip()
                if word.startswith('-') and len(word) > 1:
                    word = word[1:]           # `-bicolour`, a combining form
                prev_word[group] = word
            if not word:
                stats['orphan_continuation'] += 1
                continue

            stats['entries'] += 1
            head, *subs = body['pos'].split('/')
            yield {
                'word': word,
                'pos': head,
                'subtypes': {s.rstrip('?') for s in subs if s},
                'size': min(sizes) if sizes else 99,
                'codes': ' '.join(codes),
                'sense': body['sense'] or '',
                'infl': body['infl'] or '',
            }
    parse.stats = stats


def dialects(codes):
    """`A Bv C` -> ({'A','B','C'}, {'B'}). Second set is where it is a variant."""
    present, variant = set(), set()
    for letter, mods in DIALECT_RE.findall(codes):
        present.add(letter)
        if 'v' in mods or 'V' in mods:
            variant.add(letter)
    return present, variant


def collate(entries, max_size):
    """Fold entries into one row per lowercase single-token word."""
    words = defaultdict(lambda: {
        'size': 99, 'noun_size': 99, 'pos': Counter(), 'subtypes': set(),
        'codes': set(), 'senses': set(), 'infl': set(),
        'dialects': set(), 'variant_in': set(), 'american_standard': False,
    })
    for e in entries:
        if not LOWER_WORD_RE.fullmatch(e['word']):
            continue                      # capitalised, spaced or punctuated
        if e['size'] > max_size:
            continue
        w = words[e['word']]
        w['size'] = min(w['size'], e['size'])
        w['pos'][e['pos']] += 1
        w['subtypes'] |= e['subtypes']
        if e['codes']:
            w['codes'].add(e['codes'])
        if e['sense']:
            w['senses'].add(e['sense'])
        if e['infl']:
            w['infl'].add(e['infl'])

        present, variant = dialects(e['codes'])
        w['dialects'] |= present
        w['variant_in'] |= variant
        # A common noun sense is what qualifies the word, and it must be judged
        # on this entry alone: `president` is a common noun because ONE of its
        # entries is a bare `<n>`, whatever the `<n/upper>` sibling says.
        if e['pos'] == 'n' and not (e['subtypes'] & NAMEY):
            w['noun_size'] = min(w['noun_size'], e['size'])
        # Standard-American if any entry either carries no dialect code at all
        # (dialect-neutral) or marks A without a variant modifier.
        if not present or ('A' in present and 'A' not in variant):
            w['american_standard'] = True
    return words


def write_csv(words, path):
    fields = ['word', 'scowl_size', 'scowl_pos', 'scowl_is_noun',
              'scowl_noun_size', 'scowl_subtypes', 'scowl_dialects',
              'scowl_variant_in', 'scowl_american_standard', 'scowl_senses',
              'scowl_inflections', 'scowl_codes']
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        out = csv.DictWriter(fh, fieldnames=fields)
        out.writeheader()
        for word in sorted(words):
            w = words[word]
            out.writerow({
                'word': word,
                'scowl_size': w['size'],
                # `n:3;v:1` -- the count is how many senses, which is a rough
                # but useful signal of which reading dominates.
                'scowl_pos': ';'.join(f'{p}:{n}' for p, n in w['pos'].most_common()),
                'scowl_is_noun': w['noun_size'] < 99,
                'scowl_noun_size': w['noun_size'] if w['noun_size'] < 99 else '',
                'scowl_subtypes': ';'.join(sorted(w['subtypes'])),
                'scowl_dialects': ''.join(sorted(w['dialects'])),
                'scowl_variant_in': ''.join(sorted(w['variant_in'])),
                'scowl_american_standard': w['american_standard'],
                'scowl_senses': ';'.join(sorted(w['senses'])),
                'scowl_inflections': ' | '.join(sorted(w['infl'])),
                'scowl_codes': ';'.join(sorted(w['codes'])),
            })
    return fields


def fetch(path):
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    print(f'downloading {SCOWL_URL}')
    urllib.request.urlretrieve(SCOWL_URL, path)
    return path


def self_check(words, stats):
    """The assertions that would have caught both parser bugs.

    Each one is a fact about the source file, not about our data, so a future
    SCOWL release changing shape fails here rather than silently shrinking the
    evidence table.
    """
    # 1. Homographs survive. Every one of these carries a `{sense}` brace, the
    #    construct the first parser choked on.
    for w in ('box', 'tire', 'ox', 'beef', 'casino'):
        assert w in words, f'{w} missing: {{sense}} braces are being dropped'
        assert words[w]['noun_size'] <= 40, f'{w} not recognised as a common noun'

    # 2. Subtypes are judged per entry. Both of these have a capitalised
    #    sibling sense that must not bury the common noun.
    for w in ('president', 'red'):
        assert words[w]['noun_size'] <= 40, f'{w} buried by its /upper sibling'

    # 3. Names stay out.
    for w in ('aachen', 'american'):
        assert w not in words or words[w]['noun_size'] == 99, f'{w} leaked in as a noun'

    # 4. Dialect codes parse. `colour` is British-side, `color` American.
    assert not words['colour']['american_standard'], 'colour read as American'
    assert words['color']['american_standard'], 'color not read as American'
    assert not words['plough']['american_standard'], 'plough read as American'

    # 5. Continuations resume the right side of an interleaved doublet. If they
    #    do not, `colour` picks up `colors` and every doublet in the file is
    #    credited with both spellings' inflections.
    colour_infl = ' '.join(words['colour']['infl'])
    assert 'colours' in colour_infl, 'colour lost its own inflections'
    assert 'colors' not in colour_infl, \
        "colour credited with color's inflections: continuation tracking is off"

    # 6. Untagged lines are the low-quality tail only. If a future release
    #    starts dropping POS on common words, this fires instead of the table
    #    quietly losing them.
    # A float, not a fixed count: SCOWL genuinely ships ~800 single lowercase
    # words below size 80 with no POS at all -- plural-only inflections
    # (`aphides`, `apsides`), adjectives (`artisanal`, `aspirational`) and
    # adverbs (`accidently`). None of them is noun evidence being lost. The
    # ceiling is here to catch a future release that stops tagging in bulk.
    orphans = stats['untagged_single_below_80']
    assert orphans < 1500, f'{orphans} untagged single words below size 80'
    # The `{sense}` bug cost ~12k entries. A floor catches that class of
    # regression without pinning an exact count a new release would break.
    assert stats['entries'] > 230_000, f'only {stats["entries"]} entries parsed'
    print('self-check: ok')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input', default=DEFAULT_INPUT)
    ap.add_argument('--output', default=DEFAULT_OUTPUT)
    ap.add_argument('--max-size', type=int, default=DEFAULT_MAX_SIZE,
                    help='drop entries above this commonality band '
                         f'(default {DEFAULT_MAX_SIZE}; above 80 adds the '
                         'UKACD copyright)')
    ap.add_argument('--self-check', action='store_true',
                    help='run the parser assertions and exit')
    args = ap.parse_args(argv)

    if args.max_size > 80:
        print('note: --max-size above 80 pulls in the UKACD copyright; '
              'see sources/README.md', file=sys.stderr)

    entries = list(parse(fetch(args.input)))
    stats = parse.stats
    # Self-check always runs against the full file, so the size cut cannot hide
    # a parse regression in the common bands.
    self_check(collate(entries, 99), stats)
    if args.self_check:
        return

    words = collate(entries, args.max_size)
    write_csv(words, args.output)

    nouns = {w for w, v in words.items() if v['noun_size'] < 99}
    print(f'{args.input}: {stats["lines"]:,} lines, {stats["entries"]:,} tagged '
          f'entries, {stats["untagged"]:,} untagged')
    print(f'{args.output}: {len(words):,} words at size <= {args.max_size}, '
          f'{len(nouns):,} of them common nouns')
    bands = Counter(words[w]['noun_size'] for w in nouns)
    print('  common nouns by size band: '
          + ', '.join(f'{b}:{bands[b]:,}' for b in sorted(bands)))
    non_american = sum(1 for w in nouns if not words[w]['american_standard'])
    print(f'  not standard-American spelling: {non_american:,}')


if __name__ == '__main__':
    main()
