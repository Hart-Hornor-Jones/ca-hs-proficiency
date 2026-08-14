#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge the school-context measures (new_context_values.json, from
extend_panel_school_context.py) into the data CSVs and the PANEL blob in index.html.

The six year-varying measures join panel_long.csv / panel_wide.csv like any other.
The two constants (charter status, school size) are one value per school, so they
live in schools.csv rather than being repeated 32 times per school in the panel;
in the page they are stored as a single encoded row with a `k:1` marker."""
import json
import os
import pandas as pd

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + os.sep
blob = json.load(open('new_context_values.json', encoding='utf-8'))
vals, consts = blob['years'], blob['consts']

DEC = {'ctx_upp': 1, 'ctx_lcff': 0, 'ctx_sed': 1, 'ctx_el': 1, 'ctx_urg': 1,
       'ctx_tract_inc': 0, 'ctx_charter': 0, 'ctx_size': 0}

META = [
 ('ctx_upp', 'Unduplicated pupil percentage (student need)', 'School context', 'percent',
  'The share of the school\'s students who are low-income, English learners, or in foster care, counted once each - the state\'s own measure of concentrated student need, from the CUPC collection each October. This is the need figure UC and the state both use administratively. Available for 2017-25 school years.',
  'CDE CUPC collection (via the project\'s upp_lcff component)'),
 ('ctx_lcff', 'LCFF+ designation (need of 75% or more)', 'School context', 'yes / no',
  'Whether the school carries UC\'s LCFF+ designation, which switches on when the unduplicated pupil percentage reaches 75%. Shown as 1 for designated schools and 0 for the rest. The threshold is a sharp administrative line rather than a description of the school, which is exactly what makes it useful: schools just above and just below it are otherwise very similar. Available for 2017-25.',
  'CDE CUPC collection; UC\'s LCFF+ rule (UPP >= 75)'),
 ('ctx_sed', 'Socioeconomically disadvantaged share (grade 11)', 'School context', 'percent',
  'The share of the school\'s grade-11 students reported as socioeconomically disadvantaged, taken from the enrollment counts published alongside the CAASPP results. Measured on the tested grade rather than the whole school. Available 2016-25; not given in 2020.',
  'CAASPP research files, per-group reported enrollment'),
 ('ctx_el', 'English learner share (grade 11)', 'School context', 'percent',
  'The share of the school\'s grade-11 students classified as English learners, from the enrollment counts published alongside the CAASPP results. Available 2016-25; not given in 2020.',
  'CAASPP research files, per-group reported enrollment'),
 ('ctx_urg', 'Under-represented minority share', 'School context', 'percent',
  'The share of the school\'s grade 9-12 enrollment that is Hispanic, Black, or American Indian - the University of California\'s definition of under-represented groups. Measured on the school\'s own students, not on the surrounding neighborhood. School-years with fewer than 20 students enrolled are hidden. Available 2014-25.',
  'CDE per-school enrollment by race/ethnicity, grades 9-12'),
 ('ctx_tract_inc', 'Neighborhood median household income', 'School context', 'dollars',
  'The median household income of the census tract the school building sits in, from the American Community Survey. ⚠ This describes the neighborhood around the school, NOT the families of its students - magnets, commuters, and attendance boundaries pull the two apart, sometimes drastically. Compare it against the need measures rather than treating it as one of them. Available 2015-25; not given in 2020.',
  'American Community Survey 5-year estimates, school tract'),
 ('ctx_charter', 'Charter school', 'School context', 'yes / no',
  'Whether the school is a charter school (1) or not (0), from the California Department of Education public school directory. Treated as fixed over the whole period. Stored in schools.csv rather than the panel, since it does not vary by year.',
  'CDE public school directory'),
 ('ctx_size', 'School size (students per grade)', 'School context', 'students',
  'The approximate number of students per grade, used elsewhere on the page for the size-weighted trend line. Treated as fixed over the whole period. Stored in schools.csv rather than the panel, since it does not vary by year.',
  'CDE enrollment (grades 9-12, divided by four), with fallbacks'),
]
YEAR_IDS = ['ctx_upp', 'ctx_lcff', 'ctx_sed', 'ctx_el', 'ctx_urg', 'ctx_tract_inc']
CONST_IDS = ['ctx_charter', 'ctx_size']

def q(mid, v):
    return int(round(float(v) * 10 ** DEC[mid])) / 10 ** DEC[mid]

# ------------------------------------------------------------------ schools.csv gains charter
schools = pd.read_csv(REPO + 'data/schools.csv', dtype={'cds14': str})
if 'charter' in schools.columns:
    schools = schools.drop(columns='charter')
schools['charter'] = schools['cds14'].map(
    lambda c: ('' if c not in consts['ctx_charter'] else int(consts['ctx_charter'][c])))
schools.to_csv(REPO + 'data/schools.csv', index=False)
print('schools.csv: charter column added, %d of %d known'
      % (int((schools['charter'] != '').sum()), len(schools)))

# ------------------------------------------------------------------ long
long_df = pd.read_csv(REPO + 'data/panel_long.csv', dtype={'cds14': str})
long_df = long_df[~long_df['measure'].isin(YEAR_IDS)]
rows = []
for mid in YEAR_IDS:
    for y in sorted(vals[mid], key=int):
        for cds, v in vals[mid][y].items():
            rows.append((cds, int(y), mid, q(mid, v)))
nr = pd.DataFrame(rows, columns=['cds14', 'year', 'measure', 'value'])
allx = pd.concat([long_df, nr], ignore_index=True)

BASE = list(pd.unique(long_df['measure']))
ORDER = BASE + YEAR_IDS
allx['mo'] = allx['measure'].map({m: i for i, m in enumerate(ORDER)})
assert allx['mo'].notna().all(), 'unknown measure id'
allx = allx.sort_values(['mo', 'year', 'cds14']).drop(columns='mo')
assert not allx.duplicated(['cds14', 'year', 'measure']).any()
allx.to_csv(REPO + 'data/panel_long.csv', index=False)
print('panel_long.csv:', len(allx), 'rows (+%d)' % len(nr))

# ------------------------------------------------------------------ wide
wide = allx.pivot_table(index=['cds14', 'year'], columns='measure', values='value',
                        aggfunc='first').reset_index()
wide = wide.merge(schools[['cds14', 'school_name', 'county']], on='cds14', how='left')
wide = wide[['cds14', 'school_name', 'county', 'year'] + ORDER]
wide = wide.sort_values(['cds14', 'year'])
wide.to_csv(REPO + 'data/panel_wide.csv', index=False)
print('panel_wide.csv:', len(wide), 'rows x', len(wide.columns), 'cols')

# ------------------------------------------------------------------ measures.csv
ms = pd.read_csv(REPO + 'data/measures.csv')
ms = ms[~ms['measure'].isin(DEC)]
add = []
for mid, label, group, unit, desc, source in META:
    if mid in YEAR_IDS:
        yrs = sorted(int(y) for y in vals[mid])
        n = sum(len(vals[mid][str(y)]) for y in yrs)
        y0, y1 = yrs[0], yrs[-1]
    else:
        n = len(consts[mid]); y0, y1 = '', ''
    add.append({'measure': mid, 'label': label, 'group': group, 'unit': unit,
                'decimals': DEC[mid], 'first_year': y0, 'last_year': y1,
                'n_values': n, 'description': desc, 'source': source})
ms = pd.concat([ms, pd.DataFrame(add)], ignore_index=True)
ms.to_csv(REPO + 'data/measures.csv', index=False)
print('measures.csv:', len(ms), 'measures')

# ------------------------------------------------------------------ PANEL blob
h = open(REPO + 'index.html', encoding='utf-8').read()
i = h.find('var PANEL=')
j = h.find(';\n', i)
PANEL = json.loads(h[i + len('var PANEL='):j])
cds_order = list(schools['cds14'])
idx = {c: k for k, c in enumerate(cds_order)}
assert len(PANEL['names']) == len(cds_order)

for mid in YEAR_IDS:
    yrs = sorted(int(y) for y in vals[mid])
    y0, y1, dec = yrs[0], yrs[-1], DEC[mid]
    out = []
    for y in range(y0, y1 + 1):
        enc = [''] * len(cds_order)
        for cds, v in vals[mid].get(str(y), {}).items():
            enc[idx[cds]] = str(int(round(float(v) * 10 ** dec)))
        out.append(','.join(enc))
    PANEL['m'][mid] = {'y0': y0, 'y1': y1, 'dec': dec, 'rows': out}
for mid in CONST_IDS:
    dec = DEC[mid]
    enc = [''] * len(cds_order)
    for cds, v in consts[mid].items():
        enc[idx[cds]] = str(int(round(float(v) * 10 ** dec)))
    PANEL['m'][mid] = {'y0': 1994, 'y1': 2025, 'dec': dec, 'k': 1, 'rows': [','.join(enc)]}

newblob = 'var PANEL=' + json.dumps(PANEL, separators=(',', ':'), ensure_ascii=False)
h2 = h[:i] + newblob + h[j:]
open(REPO + 'index.html', 'w', encoding='utf-8').write(h2)
print('index.html PANEL: %d measures, page %.2f MB' % (len(PANEL['m']), len(h2) / 1e6))

# ------------------------------------------------------------------ cross-check
chk = nr.sample(300, random_state=3)
bad = 0
for r in chk.itertuples():
    m = PANEL['m'][r.measure]
    e = m['rows'][r.year - m['y0']].split(',')[idx[r.cds14]]
    if abs(int(e) / 10 ** m['dec'] - r.value) > 1e-9: bad += 1
cbad = 0
for mid in CONST_IDS:
    m = PANEL['m'][mid]
    for cds, v in list(consts[mid].items())[:200]:
        e = m['rows'][0].split(',')[idx[cds]]
        if abs(int(e) / 10 ** m['dec'] - q(mid, v)) > 1e-9: cbad += 1
print('blob vs long spot-check: %d/300 mismatches; constants: %d mismatches' % (bad, cbad))
