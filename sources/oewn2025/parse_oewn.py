import gzip, re, sys, pickle
from lxml import etree

def parse(path):
    syn = {}       # id -> dict(lexfile, defn, domains=[synset ids])
    entries = []   # (writtenForm, pos, [synset ids])
    ctx = etree.iterparse(gzip.open(path,'rb'), events=('end',), tag=('Synset','LexicalEntry'))
    for _, el in ctx:
        if el.tag == 'Synset':
            d = el.find('Definition')
            syn[el.get('id')] = {
                'lexfile': el.get('lexfile'),
                'defn': (d.text or '').strip() if d is not None else '',
                'domains': [r.get('target') for r in el.findall('SynsetRelation')
                            if r.get('relType') == 'domain_topic'],
                'members': (el.get('members') or '').split(),
            }
        else:
            lem = el.find('Lemma')
            if lem is not None:
                entries.append((lem.get('writtenForm'), lem.get('partOfSpeech'),
                                [s.get('synset') for s in el.findall('Sense')]))
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]
    return syn, entries

if __name__ == '__main__':
    syn, entries = parse(sys.argv[1])
    pickle.dump((syn, entries), open(sys.argv[2],'wb'))
    print(sys.argv[1], '-> synsets:', len(syn), 'lexical entries:', len(entries))
    print('noun entries:', sum(1 for e in entries if e[1]=='n'))
