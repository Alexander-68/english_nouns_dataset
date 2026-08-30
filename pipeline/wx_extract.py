#!/usr/bin/env python3
"""
wx_extract.py — stream the kaikki.org Wiktextract dump and emit a compact
English-noun table.

The raw dump is ~22.9 GB uncompressed (2.6 GB gzipped) and contains every
language. This script never loads it into memory: it streams line by line,
cheaply pre-filters on a substring before parsing any JSON, and writes CSV
at the end. It reads the .gz directly, so you never need the 22.9 GB
uncompressed form on disk - only the 2.6 GB download.

Expect roughly 10-30 minutes and 1-2 GB RAM (it holds one row per distinct
English noun in order to merge separate etymology sections of the same word).

Usage
-----
    python3 wx_extract.py raw-wiktextract-data.jsonl.gz wiktionary-nouns.csv
    python3 wx_extract.py raw-wiktextract-data.jsonl    wiktionary-nouns.csv

Get the dump (~2.6 GB, resumable):
    curl -L -C - -o raw-wiktextract-data.jsonl.gz \
      https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz

Optional:  pip install orjson
    The substring pre-filter rejects most lines before any parsing, so the
    bottleneck is gzip decompression and orjson buys little. Harmless either way.

Schema notes — verified against live kaikki.org entries, 2026-08-27:
  * inflected forms  "cats" -> form_of: [{"word": "cat"}], tags ["form_of","plural"]
  * plural-only      "scissors" -> sense tag "plural-only"; head tag "plural only"
  * countability     sense tags "countable" / "uncountable"
  * spelling variant NOT in alt_of for most words. "colour" and "gaol" carry it
                     only in the gloss ("...standard spelling of color.") plus
                     regional categories. We regex the gloss and say so.
"""
import sys, csv, gzip, re, io

try:
    import orjson
    def loads(b): return orjson.loads(b)
    FAST = True
except ImportError:
    import json
    def loads(b): return json.loads(b)
    FAST = False

# gloss patterns that express "this word is a variant of that word".
#
# These glosses are FORMULAIC and they OPEN with the formula:
#     "Alternative spelling of colour."      "Obsolete form of gaol."
#     "Misspelling of separate."             "(British) Standard spelling of colour."
# Ordinary prose mentions the same words mid-sentence and means nothing by it:
#     "A form of argument in which..."   ->  NOT a variant of "argument"
#     "the acute form of a disorder"     ->  NOT a variant of "a"
# So the match is anchored to the start of the gloss, the filler between the
# qualifier and "spelling|form of" is bounded to two words, and a bare
# "Form of X" opening is labelled 'unqualified' rather than dressed up as a
# confident 'spelling'.
KINDS = (r'alternative|alternate|archaic|obsolete|dated|nonstandard|non-standard|'
         r'standard|british|american|commonwealth|canadian|australian|irish|'
         # Wiktionary writes the regional note either way round, and
         # "US standard spelling of humour" was being missed entirely,
         # which is how humor/humour, favorite/favourite, neighbor and
         # catalog all ended up in the doublets queue instead of being
         # resolved as regional spellings.
         r'us|u\.s\.|uk|u\.k\.|canada|ireland|scotland|scottish|england|'
         r'new\s+zealand|australia|india|indian|'
         r'scottish|eye|informal|colloquial|rare|uncommon|dialectal|dialect|'
         r'proscribed|superseded|deprecated|pronunciation|plural|singular|'
         r'attributive|abbreviated|contracted|clipped|censored|euphemistic|'
         r'archaic\s+or\s+dialectal|obsolete\s+or\s+dialectal')
MISSPELL = r'(?:common\s+)?miss?spellings?'

VARIANT_RE = re.compile(
    r'\A\s*'                                # anchored: the formula opens the gloss
    r'(?:\([^)]{0,40}\)\s*)?'                # optional leading "(British)" qualifier
    r'(?:'
      r'(?P<kind>' + KINDS + r')\b'          # qualifier ...
      r'(?:[\s,-]+\w+){0,5}?'                # ... at most five filler words ...
      r'[\s,-]+(?:spellings?|forms?)\s+of'   # ... then the formula
      r'|(?P<misspell>' + MISSPELL + r')\s+of'
      r'|(?P<bare>spellings?|forms?)\s+of'   # bare "Form of X" -> 'unqualified'
    r")\s+(?P<target>[A-Za-z][A-Za-z'\-]*)",
    re.IGNORECASE)


def variant_kind_of(m):
    """Label for a VARIANT_RE match. Never invent confidence we do not have."""
    if m.group('kind'):
        return re.sub(r'\s+', ' ', m.group('kind')).strip().lower()
    if m.group('misspell'):
        return 'misspelling'
    return 'unqualified'


# a bare "Form of X" opening is often prose ("Form of the verb sing"), so a
# target that is a function word is noise, not a variant pair.
VARIANT_STOP_TARGETS = {
    'a','an','the','this','that','these','those','it','its','his','her','their',
    'any','some','one','two','something','someone','and','or','of','to','in','on',
    'at','is','was','are','be','being','been','used','which','what','who','when',
    'where','how','not','no','each','other','another','same','such','many','most',
    'all','both','either','neither','several','various','certain','more','less'}

REGION_TAGS = {'UK','US','British','American','Australia','Canada','Ireland',
               'New-Zealand','India','South-Africa','Scotland','Commonwealth'}

COLUMNS = ['word','countable','uncountable','plural_only','is_inflected_form',
           'form_of','variant_of','variant_kind','variant_sense','variant_gloss',
           'regions','n_senses','first_gloss']


def open_maybe_gz(path):
    if path.endswith('.gz'):
        return io.TextIOWrapper(gzip.open(path, 'rb'), encoding='utf-8', errors='replace')
    return open(path, 'r', encoding='utf-8', errors='replace')


def extract(entry):
    """Return a row dict for an English noun entry, or None."""
    if entry.get('lang_code') != 'en' or entry.get('pos') != 'noun':
        return None
    word = entry.get('word')
    if not word:
        return None

    senses = entry.get('senses') or []
    head_tags = set(entry.get('tags') or [])

    countable = uncountable = plural_only = False
    is_form = False
    form_of = ''
    variant_of = ''
    variant_kind = ''
    variant_sense = ''
    variant_gloss = ''
    regions = set()
    first_gloss = ''

    # head-level plural-only is written with a space; sense-level with a hyphen
    if 'plural only' in head_tags or 'plural-only' in head_tags:
        plural_only = True

    for si, s in enumerate(senses):
        tags = set(s.get('tags') or [])
        if 'countable' in tags:   countable = True
        if 'uncountable' in tags: uncountable = True
        if 'plural-only' in tags or 'plural only' in tags: plural_only = True
        regions |= (tags & REGION_TAGS)

        # inflected-form sense: structured, reliable
        fo = s.get('form_of')
        if fo:
            is_form = True
            if not form_of:
                w = fo[0].get('word') if isinstance(fo[0], dict) else fo[0]
                form_of = w or ''

        # alt_of when present (rarer than the docs imply)
        ao = s.get('alt_of')
        if ao and not variant_of:
            w = ao[0].get('word') if isinstance(ao[0], dict) else ao[0]
            if w:
                variant_of, variant_kind = w, 'alt_of'
                variant_sense = si

        glosses = s.get('glosses') or s.get('raw_glosses') or []
        if glosses:
            if not first_gloss:
                first_gloss = glosses[0]
            if not variant_of:
                m = VARIANT_RE.match(glosses[0])
                if m and m.group('target'):
                    tgt = m.group('target')
                    if (tgt.lower() != word.lower()
                            and tgt.lower() not in VARIANT_STOP_TARGETS):
                        variant_of = tgt
                        variant_kind = variant_kind_of(m)
                        variant_sense = si
                        variant_gloss = glosses[0][:200]

    # categories carry regional info that tags miss (e.g. "Commonwealth English")
    for c in (entry.get('categories') or []):
        name = c.get('name') if isinstance(c, dict) else c
        if not name: continue
        for r in ('British English','American English','Commonwealth English',
                  'Irish English','Australian English','Canadian English'):
            if r in name:
                regions.add(r.split()[0])

    return {
        'word': word,
        'countable': int(countable),
        'uncountable': int(uncountable),
        'plural_only': int(plural_only),
        'is_inflected_form': int(is_form),
        'form_of': form_of,
        'variant_of': variant_of,
        'variant_kind': variant_kind,
        'variant_sense': variant_sense,
        'variant_gloss': variant_gloss,
        'regions': ';'.join(sorted(regions)),
        'n_senses': len(senses),
        'first_gloss': (first_gloss or '')[:200],
    }


def main(src, dst):
    n_lines = n_en_noun = 0
    seen = {}
    with open_maybe_gz(src) as fh:
        for line in fh:
            n_lines += 1
            if n_lines % 1_000_000 == 0:
                print(f'  ...{n_lines:,} lines read, {n_en_noun:,} English nouns',
                      file=sys.stderr, flush=True)
            # cheap pre-filter: skip ~95% of lines without parsing JSON
            if '"lang_code": "en"' not in line and '"lang_code":"en"' not in line:
                continue
            if '"noun"' not in line:
                continue
            try:
                entry = loads(line)
            except Exception:
                continue
            row = extract(entry)
            if row is None:
                continue
            n_en_noun += 1
            w = row['word']
            if w in seen:            # merge duplicate etymology sections
                p = seen[w]
                for k in ('countable','uncountable','plural_only','is_inflected_form'):
                    p[k] = max(p[k], row[k])
                for k in ('form_of','variant_of','variant_kind','variant_sense',
                          'variant_gloss'):
                    p[k] = p[k] or row[k]
                p['n_senses'] += row['n_senses']
                p['regions'] = ';'.join(sorted(set(filter(None,
                    (p['regions'] + ';' + row['regions']).split(';')))))
                p['first_gloss'] = p['first_gloss'] or row['first_gloss']
            else:
                seen[w] = row

    with open(dst, 'w', newline='', encoding='utf-8') as out:
        wr = csv.DictWriter(out, fieldnames=COLUMNS)
        wr.writeheader()
        for w in sorted(seen):
            wr.writerow(seen[w])

    print(f'\nlines read      : {n_lines:,}', file=sys.stderr)
    print(f'English nouns   : {n_en_noun:,} entries -> {len(seen):,} distinct words',
          file=sys.stderr)
    print(f'json parser     : {"orjson" if FAST else "json (pip install orjson to speed up)"}',
          file=sys.stderr)
    print(f'written         : {dst}', file=sys.stderr)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
