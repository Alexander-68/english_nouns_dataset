#!/usr/bin/env python3
"""
build_name_list.py — assemble the lower-cased proper-noun list from sources
already in this repo.

Why this exists
---------------
Lower-cased proper nouns kept surfacing as noise in three separate places
(see WIKTEXTRACT-JOIN-REPORT.md): the gaps review queue (`waterhouse`,
`garnett`, `pimlico`), the `unknown.csv` queue (`sherlock`, `waterloo`,
`marseille`), and the dataset's own `also_proper_noun` column. `rank_gaps.py`
could only catch them when Wiktionary's `variant_of` happened to be Title-case,
which is a small fraction of them.

Sources — both already on disk, no download (this environment's egress policy
blocks the OEWN XML and any corpus):

  1. `oewn2025/oewn2025names.csv` — Open English Namenet, the proper-noun half
     of the OEWN 2025 split. 25,905 entries, ~10.6k of them single alphabetic
     tokens. This is the same source the dataset's `also_proper_noun` column
     comes from.
  2. `wordchain2024/names-wiki.csv` — the 2024 project's Wikipedia-derived
     name list, 6,555 entries, ~6.5k single tokens.

Output: `names-lowercase.csv`, one row per lower-cased single-token name, with
provenance kept per row so a consumer can weight the sources differently or
drop one.

The `also_oewn_noun` column is the important one, and this script deliberately
does NOT apply it as a filter. A word being both a name and a common noun
(`bacon`, `atlas`, `angel`, `adonis`, `badger`) means different things to
different consumers: for `gaps.csv` it is a reason to distrust the name match,
for `unknown.csv` every row is an OEWN noun by construction so filtering on it
would empty the file. Ship the flag, let each caller decide.

Known limitation, stated rather than hidden: neither source is a general
gazetteer. `sherlock`, `laguna`, `ramona`, `cochin`, `eldorado` and `magdalen`
are in none of them. This list raises recall, it does not close the problem.

Usage
-----
    python3 build_name_list.py            # writes names-lowercase.csv
"""
import pandas as pd

NAMENET = 'oewn2025/oewn2025names.csv'
WIKI = 'wordchain2024/names-wiki.csv'
OEWN_NOUNS = 'oewn2025/oewn2025nouns.csv'
OUT = 'sources/names-lowercase.csv'


def single_tokens(series):
    """Lower-cased single alphabetic Title-case tokens.

    Title-case is required so ALL-CAPS acronyms (AARP, ABB, DNA) are left out —
    they behave as ordinary lower-case common nouns in running text, the same
    call rank_gaps.py already makes for its `variant_of` check.
    """
    out = set()
    for x in series:
        x = str(x).strip()
        if x.isalpha() and x.istitle():
            out.add(x.lower())
    return out


def main():
    namenet = single_tokens(pd.read_csv(NAMENET, keep_default_na=False, na_values=[])['name'])
    wiki = single_tokens(pd.read_csv(WIKI, keep_default_na=False, na_values=[])['name'])
    common = set(pd.read_csv(OEWN_NOUNS, keep_default_na=False, na_values=[])['noun'].str.lower())

    words = sorted(namenet | wiki)
    df = pd.DataFrame({
        'name': words,
        'in_namenet': [w in namenet for w in words],
        'in_wikipedia': [w in wiki for w in words],
        'also_oewn_noun': [w in common for w in words],
    })
    df.to_csv(OUT, index=False)

    print(f'namenet single tokens  : {len(namenet):,}')
    print(f'wikipedia single tokens: {len(wiki):,}')
    print(f'union                  : {len(words):,} -> {OUT}')
    print(f'  in both sources      : {int((df["in_namenet"] & df["in_wikipedia"]).sum()):,}')
    print(f'  also an OEWN common noun (caller decides): '
          f'{int(df["also_oewn_noun"].sum()):,}')


if __name__ == '__main__':
    main()
