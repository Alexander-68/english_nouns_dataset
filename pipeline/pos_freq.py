#!/usr/bin/env python3
"""
pos_freq.py — build a dominant-part-of-speech table from POS-tagged corpora.

The one question the pipeline could never answer from morphology is which
part of speech a word USUALLY is. `political` and `federal` have noun senses
("a political agent"), so every "can it be a noun?" lookup says yes, and
lemminflect agrees; but in running text they are adjectives ~99% of the time.
That is a frequency fact, and it needs a tagged corpus, not a dictionary.

Proper nouns are counted separately (`propn`). The universal tagset folds
them into NOUN, which is exactly the distinction needed to tell `madison` and
`joe` from `madness` and `job`, so the corpora are read with their native tags
and mapped here instead.

Sources. Two families, both hand-tagged, no licence problem:

  nltk (downloaded by nltk.download, see the names in NLTK_CORPORA)
    brown        1,161,192 tokens, balanced American English, 1961
    conll2000      259,104 tokens, Wall Street Journal, 1989
    treebank       100,676 tokens, Wall Street Journal, 1989
    masc_tagged    592,536 tokens, Open ANC: blogs, email, essays, 2000s
    switchboard     82,792 tokens, telephone speech, 1990s
    nps_chat        45,010 tokens, internet chat, 2006

  Universal Dependencies .conllu files in sources/ud/ (fetched by fetch_ud())
    en_ewt         254,000 tokens, English Web Treebank: reviews, blogs,
                   email, question-answer, newsgroups, 2010s
    en_gum         200,000 tokens, GUM: reddit, how-to, vlogs, academic,
                   still being extended

The old three are all pre-1990 written American English, which is why the
table said nothing about `email`, `website` or `browser`; the newer five are
here for exactly those. It still says nothing about `blockchain` — no
hand-tagged corpus is big or new enough for the 2015+ tail, and a word the
corpus has never seen produces no mark rather than a wrong one.

UD gives both a universal tag (column 4) and a Penn tag (column 5). We read
the Penn one, so a single `coarse()` handles every source.

Output: pos-dominance.csv — one row per lowercased word type

    word, n, noun, propn, adj, verb, adv, other, dominant, noun_share

`dominant` is the tag with the most occurrences; `noun_share` is nouns over
all occurrences. Downstream should trust this only where `n` is large enough
to mean anything - a word seen three times says nothing.

Usage:  python3 pos_freq.py [pos-dominance.csv]
"""
import sys, csv, os, urllib.request
from collections import defaultdict

import nltk

NLTK_CORPORA = ('brown', 'conll2000', 'treebank',
                'masc_tagged', 'switchboard', 'nps_chat')

UD_DIR = 'sources/ud'
UD_BASE = 'https://raw.githubusercontent.com/UniversalDependencies'
UD_FILES = [(f'{repo}/master/en_{code}-ud-{split}.conllu',
             f'en_{code}-{split}.conllu')
            for repo, code in (('UD_English-EWT', 'ewt'),
                               ('UD_English-GUM', 'gum'))
            for split in ('train', 'dev', 'test')]


def coarse(tag):
    """Brown and Penn tags -> the five buckets we care about."""
    t = tag.split('-')[0].split('+')[0].upper()
    if t.startswith('NP') or t.startswith('NNP'):
        return 'PROPN'
    if t.startswith('NN') or t.startswith('NR'):
        return 'NOUN'
    if t.startswith('JJ'):
        return 'ADJ'
    if t.startswith('VB'):
        return 'VERB'
    if t.startswith('RB'):
        return 'ADV'
    return 'OTHER'


def fetch_ud(dirname=UD_DIR):
    """Download the UD .conllu files once. Present file = nothing to do."""
    os.makedirs(dirname, exist_ok=True)
    for path, name in UD_FILES:
        dst = os.path.join(dirname, name)
        if os.path.exists(dst):
            continue
        print(f'  fetching {name}', file=sys.stderr)
        urllib.request.urlretrieve(f'{UD_BASE}/{path}', dst)


def ud_tagged_words(dirname=UD_DIR):
    """(word, penn_tag) from every .conllu file in dirname.

    Skips comments, blank lines, and the multiword/empty-node rows whose ID
    carries a `-` or a `.` — those repeat tokens that are also listed
    individually, and counting both double-counts them.
    """
    for name in sorted(os.listdir(dirname)):
        if not name.endswith('.conllu'):
            continue
        with open(os.path.join(dirname, name), encoding='utf-8') as fh:
            for line in fh:
                if line.startswith('#'):
                    continue
                col = line.rstrip('\n').split('\t')
                if len(col) < 5 or '-' in col[0] or '.' in col[0]:
                    continue
                yield col[1], col[4]


def counts():
    tally = defaultdict(lambda: defaultdict(int))
    fetch_ud()
    for name in NLTK_CORPORA + ('ud',):
        try:
            words = (ud_tagged_words() if name == 'ud'
                     else getattr(nltk.corpus, name).tagged_words())
        except Exception as exc:                    # missing download
            print(f'  skipped {name}: {exc}', file=sys.stderr)
            continue
        n = 0
        for w, t in words:
            # masc_tagged carries a few untagged tokens (t is None).
            if t is None or not w.isalpha():
                continue
            tally[w.lower()][coarse(t)] += 1
            n += 1
        print(f'  {name:10s} {n:,} alphabetic tokens', file=sys.stderr)
    return tally


def main(dst='sources/pos-dominance.csv'):
    tally = counts()
    keep = ('NOUN', 'PROPN', 'ADJ', 'VERB', 'ADV')
    with open(dst, 'w', newline='', encoding='utf-8') as fh:
        wr = csv.writer(fh)
        wr.writerow(['word', 'n', 'noun', 'propn', 'adj', 'verb', 'adv',
                     'other', 'dominant', 'noun_share'])
        for word in sorted(tally):
            c = tally[word]
            total = sum(c.values())
            row = [c.get(t, 0) for t in keep]
            other = total - sum(row)
            dominant = max(c, key=lambda t: (c[t], t == 'NOUN'))
            wr.writerow([word, total, *row, other, dominant,
                         f'{row[0] / total:.3f}'])
    print(f'{dst}: {len(tally):,} word types', file=sys.stderr)


SELFTEST = """# text = I don't like the browser.
1	I	I	PRON	PRP	_	3	nsubj	_	_
2-3	don't	_	_	_	_	_	_	_	_
2	do	do	AUX	VBP	_	4	aux	_	_
3	n't	not	PART	RB	_	4	advmod	_	_
4	like	like	VERB	VB	_	0	root	_	_
5	the	the	DET	DT	_	6	det	_	_
6	browser	browser	NOUN	NN	_	4	obj	_	_
7	.	.	PUNCT	.	_	4	punct	_	_
"""


def selftest():
    """The .conllu reader: Penn tags out, multiword rows not double-counted."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'x.conllu'), 'w', encoding='utf-8') as fh:
            fh.write(SELFTEST)
        got = list(ud_tagged_words(tmp))
    assert got == [('I', 'PRP'), ('do', 'VBP'), ("n't", 'RB'), ('like', 'VB'),
                   ('the', 'DT'), ('browser', 'NN'), ('.', '.')], got
    # the 2-3 multiword row is dropped, so "don't" is counted once, as two parts
    assert [w for w, _ in got].count("don't") == 0
    assert coarse('NN') == 'NOUN' and coarse('NNP') == 'PROPN'
    print('selftest ok')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        selftest()
    else:
        main(*sys.argv[1:])
