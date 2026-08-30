import pickle, re, csv, collections, unicodedata

syn, ent = pickle.load(open('oewn2025.pkl','rb'))
syn_p, ent_p = pickle.load(open('oewn2025plus.pkl','rb'))

def lemma_of(sid, S):
    m = S.get(sid,{}).get('members') or []
    return m[0].rsplit('-',1)[0].replace('oewn-','').replace('_',' ') if m else ''

# ---------- domain -> register ----------
MED = {'medicine','pathology','anatomy','physiology','surgery','dentistry','pharmacology',
 'psychiatry','neurology','immunology','obstetrics','ophthalmology','orthopedics','otology',
 'radiology','toxicology','epidemiology','veterinary medicine','embryology','endocrinology',
 'histology','psychotherapy','psychoanalysis','drug','narcotic','operation','pregnancy',
 'virology','bacteriology','neurophysiology','neuroscience','diet','health food','body waste','growth'}
BIO = {'biology','botany','zoology','genetics','microbiology','entomology','ichthyology','ecology',
 'evolution','molecular biology','cytology','paleontology','bacteria','fungus','insect','mammal',
 'plant','animal','organism','microorganism','invertebrate','vertebrate','quadruped','ruminant',
 'cell','virus','living thing','biochemistry','animal husbandry','game bird','muscle','vegetation',
 'celestial body','forestry','livestock','stud','anthropology','archeology'}
TEC = {'physics','chemistry','mathematics','computer science','engineering','electronics',
 'electrical engineering','statistics','mechanics','metallurgy','astronomy','geology','optics',
 'thermodynamics','nuclear physics','particle physics','crystallography','aeronautics',
 'telecommunication','computer','programming','machine learning','information science','cryogenics',
 'geometry','algebra','arithmetic','logic','quantum theory','relativity','cosmology','meteorology',
 'oceanography','geochemistry','mineralogy','hydrostatics','physical chemistry','chemical analysis',
 'psychophysics','acoustics','microscopy','simulation','computer graphics','computer technology',
 'matrix algebra','game theory','numeration system','mining','mineral extraction','quarrying',
 'construction','electricity','navigation','spaceflight','science','internet','World Wide Web',
 'broadcasting','radio','television','telephone','telegraphy','photography','printing','recording',
 'shipbuilding','jet engine','transmission','communications','social media','computer game'}

def register(lexfile, domains):
    for d in domains:
        if d in MED: return 'MED'
    for d in domains:
        if d in BIO: return 'BIO'
    for d in domains:
        if d in TEC: return 'TEC'
    if lexfile in ('noun.animal','noun.plant'): return 'BIO'
    if lexfile == 'noun.body': return 'MED'
    if domains: return 'SPECIAL'
    return 'GENERAL'

# ---------- collect noun lemmas ----------
def collect(entries, S):
    d = collections.defaultdict(list)
    for form, pos, sids in entries:
        if pos == 'n':
            d[form].extend(sids)
    return d

nouns_25  = collect(ent, syn)
nouns_25p = collect(ent_p, syn_p)
proper_only = set(nouns_25p) - set(nouns_25)          # Namenet delta = proper nouns
print('OEWN 2025 noun lemmas:', len(nouns_25))
print('OEWN 2025+ noun lemmas:', len(nouns_25p))
print('proper nouns (2025+ minus 2025):', len(proper_only))

# ---------- old WordNet 3.0 list for the in_wn30 flag ----------
import pandas as pd
old = pd.read_csv('nouns240123.csv', keep_default_na=False, na_values=[])
old_set = set(old['noun'])

PLAYABLE = re.compile(r'^[a-z]+$')

rows = []
for form, sids in nouns_25.items():
    sl = [syn[s] for s in sids if s in syn]
    if not sl: continue
    first = sl[0]
    lexfile = first['lexfile'] or ''
    doms = []
    for s in sl:
        for dsid in s['domains']:
            L = lemma_of(dsid, syn)
            if L and L not in doms: doms.append(L)
    playable = bool(PLAYABLE.match(form))
    rows.append({
        'noun': form,
        'playable': playable,
        'is_multiword': ' ' in form,
        'has_hyphen': '-' in form,
        'has_capital': any(c.isupper() for c in form),
        'has_digit': any(c.isdigit() for c in form),
        'has_other_punct': bool(re.search(r"[^A-Za-z0-9 \-]", form)),
        'start': form[0].lower(),
        'end': form[-1].lower(),
        'length': len(form),
        'senses': len(sids),
        'lexfile': lexfile,
        'register': register(lexfile, doms),
        'domain': ';'.join(doms[:3]),
        'also_proper_noun': form in proper_only or form.capitalize() in nouns_25p,
        'in_wn30': form in old_set,
        'definition': first['defn'],
    })

df = pd.DataFrame(rows).sort_values('noun', key=lambda s: s.str.lower())
print('\ntotal noun lemma rows:', len(df))
print('playable (^[a-z]+$):', df['playable'].sum())

# ---------- plural suspect on playable set ----------
play = df[df['playable']]
pset = set(play['noun'])
def plural_suspect(n):
    if not n.endswith('s') or len(n) < 4: return False
    return (n[:-1] in pset) or (n.endswith('es') and n[:-2] in pset) or \
           (n.endswith('ies') and n[:-3]+'y' in pset)
df['plural_suspect'] = df.apply(lambda r: bool(r['playable']) and plural_suspect(r['noun']), axis=1)
print('plural_suspect flagged:', df['plural_suspect'].sum())

# ---------- letter economy on the playable set ----------
sup = play['start'].value_counts(); dem = play['end'].value_counts()
def pressure(L):
    s = sup.get(L,0); d = dem.get(L,0)
    return round(d/s, 2) if s else 999.0
df['end_pressure'] = df['end'].map(pressure)

cols = ['noun','start','end','length','senses','lexfile','register','domain',
        'end_pressure','plural_suspect','also_proper_noun','in_wn30','definition']
flags = ['playable','is_multiword','has_hyphen','has_capital','has_digit','has_other_punct']

df[cols + flags].to_csv('out/oewn2025-nouns-full.csv', index=False)
df[df['playable']][cols].to_csv('out/oewn2025-nouns.csv', index=False)

# ---------- names file ----------
nrows = []
for form in sorted(proper_only):
    sids = nouns_25p[form]
    sl = [syn_p[s] for s in sids if s in syn_p]
    if not sl: continue
    first = sl[0]
    nrows.append({'name': form, 'start': form[0].lower(), 'end': form[-1].lower(),
                  'length': len(form), 'senses': len(sids),
                  'lexfile': first['lexfile'] or '', 'definition': first['defn']})
pd.DataFrame(nrows).to_csv('out/oewn2025-names.csv', index=False)
print('names rows:', len(nrows))
