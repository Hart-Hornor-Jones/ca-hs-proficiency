#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Splice the nine new UC-pool measures (new_values.json, from
extend_panel_uc_pools.py) into data/panel_long.csv, data/panel_wide.csv,
data/measures.csv, and the PANEL blob inside index.html."""
import json
import pandas as pd
import numpy as np

import os
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + os.sep
vals = json.load(open('new_values.json', encoding='utf-8'))
vals['uc_apps_per_applicant'] = vals.pop('uc_apps_per_app')

DEC = {m: 2 for m in vals}

NEW_META = [
 ('gpa_uc_den', 'HS GPA - UC denied applicants', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA (the weighted, capped a-g GPA) of this school\'s students who applied to UC as freshmen and were not admitted to any campus. Not published directly: it is recovered exactly from the published applicant and admit averages and counts ((applicants x applicant GPA - admits x admit GPA) / denied). Shown only when at least 10 students were denied.',
  'UC admissions-by-school data (derived by exact moment subtraction)'),
 ('gpa_uc_admnot', 'HS GPA - UC admitted, not enrolled', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA of this school\'s students who were admitted to at least one UC campus but enrolled at none of them - most went to other universities instead. Recovered exactly from the systemwide admit average and the campus enrollee averages, so it appears only when every campus that enrolled the school\'s students published an enrollee GPA and at least 10 admits did not enroll - a minority of school-years, mostly larger schools.',
  'UC admissions-by-school data (derived by exact moment subtraction)'),
 ('gpa_ucsel_app', 'HS GPA - selective-UC applicants', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA of this school\'s applicants to UC\'s three most selective campuses - Berkeley, UCLA, and San Diego - averaging the three campus figures, each weighted by how many of the school\'s students applied there. A student who applied to two of the three is counted in both pools. Shown when the pools total at least 10 applications.',
  'UC admissions-by-school data (campus rows)'),
 ('gpa_ucsel_adm', 'HS GPA - selective-UC admits', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA of this school\'s students admitted to Berkeley, UCLA, or San Diego, averaging the three campus figures weighted by each campus\'s admit count. A student admitted to two of the three is counted in both pools. Shown when the pools total at least 10 admits.',
  'UC admissions-by-school data (campus rows)'),
 ('gpa_ucsel_den', 'HS GPA - selective-UC denied', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA of this school\'s students denied at Berkeley, UCLA, or San Diego, averaging the three campus figures weighted by each campus\'s denial count. Each campus figure is recovered exactly from that campus\'s published applicant and admit averages, and a campus enters only when it denied at least 10 of the school\'s students; the pools must total at least 10.',
  'UC admissions-by-school data (derived by exact moment subtraction, campus rows)'),
 ('gpa_ucsel_enr', 'HS GPA - selective-UC enrollees', 'High-school measure', 'GPA (weighted, capped a-g)',
  'The average high-school GPA of this school\'s students who enrolled as freshmen at Berkeley, UCLA, or San Diego, weighted by each campus\'s enrollee count. Each student enrolls at exactly one campus, so nobody is double-counted. Shown when at least 10 enrolled across the three.',
  'UC admissions-by-school data (campus rows)'),
 ('gpa_ucsel_gap', 'Admit-denied GPA gap at selective UC', 'High-school measure', 'GPA points (difference)',
  'At each of Berkeley, UCLA, and San Diego: the average GPA of the school\'s admitted students minus the average GPA of its denied students; the three campus gaps are then averaged, weighted by applications. A large gap means the campus\'s decisions cut sharply along the GPA scale within this school; a small gap means its admits and denials carried similar GPAs, so the decisions turned on other things. A campus counts only when both pool averages exist (at least 10 denials there), and the school needs 20+ applications in all.',
  'UC admissions-by-school data (derived, campus rows)'),
 ('uc_gpa_range', 'Spread across UC GPA pools', 'High-school measure', 'GPA points (difference)',
  'The full stretch of average GPAs across every UC pool observed for this school in a year: each of the nine campuses\' admitted-student average and denied-student average (pools of 10 or more) is collected, and the measure is the highest minus the lowest. In a typical school the bottom is the average of students denied at the least selective campuses and the top the average of students admitted at Berkeley or UCLA. Needs at least 4 observed pools.',
  'UC admissions-by-school data (derived, campus rows)'),
 ('uc_apps_per_applicant', 'UC campuses applied to per applicant', 'Application behavior', 'campuses (1-9)',
  'How many UC campuses the school\'s applicants tried, on average: the school\'s total applications to the nine campuses divided by its count of distinct UC applicants. Runs from 1 (each applicant tried a single campus) toward 9; it has drifted upward over the decades systemwide. Shown when at least 10 students applied.',
  'UC admissions-by-school data (campus counts / Universitywide unduplicated count)'),
]

ORDER = ['gpa_uc','gpa_uc_adm','gpa_uc_den','gpa_uc_admnot','gpa_uc_enr',
         'gpa_ucsel_app','gpa_ucsel_adm','gpa_ucsel_den','gpa_ucsel_enr','gpa_ucsel_gap',
         'uc_gpa_range','uc_apps_per_applicant','gpa_csu',
         'caaspp','caaspp_ela','caaspp_math','caaspp_l4','caaspp_dfs','ag',
         'star','star_math','cahsee','cahsee_math','ap','ap3',
         'sat1600','sat2400','sat_bench','act_avg','act21',
         'gpa_csu1','csu_math_ready','csu_wc_ready','elwr','uc_ret1','uc_grad4','uc_grad6']

# ------------------------------------------------------------------ long
long_df = pd.read_csv(REPO + 'data/panel_long.csv', dtype={'cds14': str})
new_rows = []
for mid in vals:
    for y in sorted(vals[mid], key=int):
        for cds, v in vals[mid][y].items():
            new_rows.append((cds, int(y), mid, int(round(float(v) * 10**DEC[mid])) / 10**DEC[mid]))
nr = pd.DataFrame(new_rows, columns=['cds14', 'year', 'measure', 'value'])
alllong = pd.concat([long_df, nr], ignore_index=True)
alllong['mo'] = alllong['measure'].map({m: i for i, m in enumerate(ORDER)})
assert alllong['mo'].notna().all(), 'unknown measure id in long'
alllong = alllong.sort_values(['mo', 'year', 'cds14']).drop(columns='mo')
assert not alllong.duplicated(['cds14', 'year', 'measure']).any()
alllong.to_csv(REPO + 'data/panel_long.csv', index=False)
print('panel_long.csv:', len(alllong), 'rows (+%d)' % len(nr))

# ------------------------------------------------------------------ wide
schools = pd.read_csv(REPO + 'data/schools.csv', dtype={'cds14': str})
wide = alllong.pivot_table(index=['cds14', 'year'], columns='measure', values='value',
                           aggfunc='first').reset_index()
wide = wide.merge(schools[['cds14', 'school_name', 'county']], on='cds14', how='left')
wide = wide[['cds14', 'school_name', 'county', 'year'] + ORDER]
wide = wide.sort_values(['cds14', 'year'])
wide.to_csv(REPO + 'data/panel_wide.csv', index=False)
print('panel_wide.csv:', len(wide), 'rows x', len(wide.columns), 'cols')

# ------------------------------------------------------------------ measures.csv
ms = pd.read_csv(REPO + 'data/measures.csv')
rows = []
for mid, label, group, unit, desc, source in NEW_META:
    yrs = sorted(int(y) for y in vals[mid])
    n = sum(len(vals[mid][str(y)]) for y in yrs)
    rows.append({'measure': mid, 'label': label, 'group': group, 'unit': unit,
                 'decimals': DEC[mid], 'first_year': yrs[0], 'last_year': yrs[-1],
                 'n_values': n, 'description': desc, 'source': source})
ms = pd.concat([ms, pd.DataFrame(rows)], ignore_index=True)
ms['mo'] = ms['measure'].map({m: i for i, m in enumerate(ORDER)})
ms = ms.sort_values('mo').drop(columns='mo')
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
for mid in vals:
    yrs = sorted(int(y) for y in vals[mid])
    y0, y1 = yrs[0], yrs[-1]
    dec = DEC[mid]
    scale = 10 ** dec
    rows_out = []
    for y in range(y0, y1 + 1):
        vy = vals[mid].get(str(y), {})
        enc = [''] * len(cds_order)
        for cds, v in vy.items():
            enc[idx[cds]] = str(int(round(float(v) * scale)))
        rows_out.append(','.join(enc))
    PANEL['m'][mid] = {'y0': y0, 'y1': y1, 'dec': dec, 'rows': rows_out}
blob = 'var PANEL=' + json.dumps(PANEL, separators=(',', ':'), ensure_ascii=False)
h2 = h[:i] + blob + h[j:]
open(REPO + 'index.html', 'w', encoding='utf-8').write(h2)
print('index.html PANEL: %d measures, %.2f MB total page' % (len(PANEL['m']), len(h2) / 1e6))

# cross-check: re-read long, compare a handful of cells against the blob
chk = nr.sample(300, random_state=1)
bad = 0
for r in chk.itertuples():
    m = PANEL['m'][r.measure]
    enc = m['rows'][r.year - m['y0']].split(',')[idx[r.cds14]]
    v = int(enc) / 10 ** m['dec']
    if abs(v - r.value) > 1e-9: bad += 1
print('blob vs long spot-check: %d/300 mismatches' % bad)
