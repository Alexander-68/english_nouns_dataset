#!/usr/bin/env python3
"""
threshold_bands.py — pick the gaps.csv zipf cutoff from evidence, not a guess.

Problem (WIKTEXTRACT-JOIN-REPORT.md, "Next steps" #2):
    wx_join.py cuts the candidate-additions list at `zipf >= 2.5`. That number
    was never chosen deliberately, and it costs five words from
    modernvocabularyprobe.csv, the project's own human-vetted modern-vocabulary
    list (earbud, telehealth, chatbot, podcaster, microplastic). Lowering it
    was blocked on "Next steps" #1, because at the time every extra row also
    dragged in more high-frequency function words. #1 is now done —
    rank_gaps.py flags those — so the retune is unblocked.

This script rebuilds the pre-threshold candidate set exactly as wx_join.py
builds it (same four filters, same wordfreq scores), applies rank_gaps.py's
flags to it, and reports what each candidate cutoff actually buys and costs.
It writes nothing except its report: choosing the number is a human call, this
just puts the numbers in front of it.

Usage
-----
    python3 threshold_bands.py sen-v3.csv wiktionary-nouns.csv modernvocabularyprobe.csv
"""
import sys
import pandas as pd
from wordfreq import zipf_frequency

from rank_gaps import flag_reason

CUTOFFS = [3.0, 2.5, 2.25, 2.0, 1.5, 1.0]


def build_candidates(sen_path, wikt_path):
    """The gaps candidate set as wx_join.py defines it, minus the zipf cutoff."""
    sen = pd.read_csv(sen_path, keep_default_na=False, na_values=[])
    wx = pd.read_csv(wikt_path, keep_default_na=False, na_values=[])
    have = set(sen['noun'])
    cand = wx[(~wx['word'].isin(have))
              & (wx['word'].str.match(r'^[a-z]+$', na=False))
              & (wx['is_inflected_form'] == 0)
              & (wx['plural_only'] == 0)
              & (~wx['variant_of'].isin(have - {''}))].copy()
    cand = cand.drop_duplicates(subset='word', keep='first')
    cand['zipf'] = [round(zipf_frequency(x, 'en'), 2) for x in cand['word']]
    return cand[cand['zipf'] > 0].copy()


def main(sen_path, wikt_path, probe_path):
    cand = build_candidates(sen_path, wikt_path)
    probe = pd.read_csv(probe_path, keep_default_na=False, na_values=[])
    probe_words = set(probe['word'])

    cand['flag_reason'] = [flag_reason(w, v)
                           for w, v in zip(cand['word'], cand['variant_of'])]
    # Same probe override as rank_gaps.py: human ground truth beats the auto-flag.
    cand.loc[cand['word'].isin(probe_words), 'flag_reason'] = ''
    cand['likely_noun'] = cand['flag_reason'] == ''

    print(f'candidate pool with any zipf > 0: {len(cand):,}\n')

    print('per-band (zipf in [lo, hi)) — what each band ADDS as you lower the cutoff')
    print(f'{"band":>12}  {"rows":>7}  {"likely":>7}  {"flagged":>7}  {"flag%":>6}  probe words gained')
    bands = list(zip([99.0] + CUTOFFS, CUTOFFS))
    for hi, lo in bands:
        b = cand[(cand['zipf'] >= lo) & (cand['zipf'] < hi)]
        n, lk = len(b), int(b['likely_noun'].sum())
        fl = n - lk
        gained = sorted(set(b['word']) & probe_words)
        print(f'{lo:5.2f}–{hi if hi < 99 else float("inf"):<6.2f} {n:7,}  {lk:7,}  {fl:7,}  '
              f'{fl / n * 100 if n else 0:5.1f}%  {", ".join(gained) or "—"}')

    print('\ncumulative (zipf >= cutoff) — the actual decision')
    print(f'{"cutoff":>7}  {"rows":>7}  {"likely":>7}  {"flagged":>7}  {"flag%":>6}  {"probe":>7}  probe recovered vs 2.5')
    base = set(cand.loc[cand['zipf'] >= 2.5, 'word']) & probe_words
    for c in CUTOFFS:
        b = cand[cand['zipf'] >= c]
        n, lk = len(b), int(b['likely_noun'].sum())
        fl = n - lk
        hit = set(b['word']) & probe_words
        new = sorted(hit - base)
        print(f'{c:7.2f}  {n:7,}  {lk:7,}  {fl:7,}  {fl / n * 100 if n else 0:5.1f}%  '
              f'{len(hit):3}/{len(probe_words):<3}  {", ".join(new) or "—"}')

    missing = sorted(probe_words - set(cand['word']))
    if missing:
        print(f'\nprobe words absent from the candidate pool at ANY cutoff '
              f'({len(missing)} — already in the dataset, or filtered out '
              f'upstream, not a threshold question):')
        print('  ' + ', '.join(missing))

    print('\nsample of newly admitted likely_noun rows, by band (eyeball the quality):')
    for hi, lo in bands[1:]:
        b = cand[(cand['zipf'] >= lo) & (cand['zipf'] < hi) & cand['likely_noun']]
        print(f'  {lo:.2f}–{hi:.2f} ({len(b):,}): '
              + ', '.join(b.sort_values("zipf", ascending=False)["word"].head(30).tolist()))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
