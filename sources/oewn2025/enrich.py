import pandas as pd
from wordfreq import zipf_frequency
from lemminflect import getAllInflections, getLemma

d = pd.read_csv('out/oewn2025-nouns.csv', keep_default_na=False, na_values=[])
pset = set(d['noun'])

d['zipf'] = [round(zipf_frequency(w, 'en'), 2) for w in d['noun']]

def tier(z):
    if z >= 5.0: return 'CORE'       # everyday, a child uses these
    if z >= 4.0: return 'COMMON'
    if z >= 3.0: return 'FAMILIAR'
    if z >= 2.0: return 'UNCOMMON'
    if z >  0.0: return 'RARE'
    return 'OBSCURE'                  # absent from the corpus entirely
d['tier'] = d['zipf'].map(tier)

# no distinct plural: NN form == NNS form. Covers BOTH uncountable mass nouns
# (abandonment, physics) and invariant/plural-only forms (scissors, sheep, trousers).
# Separating those two requires Wiktionary countability tags.
def invariant(w):
    try:
        inf = getAllInflections(w, upos='NOUN')
    except Exception:
        return False
    nn, nns = inf.get('NN'), inf.get('NNS')
    return bool(nn and nns and nn[0] == nns[0] == w)
d['no_distinct_plural'] = [invariant(w) for w in d['noun']]

# refined plural detection: is w the NNS of some singular that is also in the list?
def is_plural_of_listed(w):
    if not w.endswith('s') or len(w) < 4:
        return False
    try:
        lem = getLemma(w, upos='NOUN')
    except Exception:
        return False
    for l in lem:
        if l != w and l in pset:
            try:
                if w in (getAllInflections(l, upos='NOUN').get('NNS') or ()):
                    return True
            except Exception:
                pass
    return False
d['plural_of_listed'] = [is_plural_of_listed(w) for w in d['noun']]

cols = ['noun','start','end','length','zipf','tier','senses','lexfile','register','domain',
        'end_pressure','plural_suspect','plural_of_listed','no_distinct_plural',
        'also_proper_noun','in_wn30','definition']
d[cols].to_csv('out/oewn2025-nouns-v2.1.csv', index=False)

print('rows:', len(d))
print('\n--- tier ---');  print(d['tier'].value_counts().reindex(['CORE','COMMON','FAMILIAR','UNCOMMON','RARE','OBSCURE']).to_string())
print('\ninvariant_plural :', d['no_distinct_plural'].sum())
print('plural_of_listed  :', d['plural_of_listed'].sum(), '(morphology-confirmed; heuristic flagged', d['plural_suspect'].sum(),')')
print('\nconfirmed plurals sample:', ', '.join(d[d['plural_of_listed']]['noun'].head(25).tolist()))
print('\ninvariant sample     :', ', '.join(d[d['no_distinct_plural']]['noun'].head(25).tolist()))
