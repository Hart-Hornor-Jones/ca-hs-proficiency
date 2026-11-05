#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build six measures from three public repositories and write them to
new_levels_gap_ucsd_values.json (read by splice_levels_gap_ucsd_measures.py)
and a coverage report, levels_gap_ucsd_report.txt.

Sources (clone each repository; pass its folder with the matching option, or
leave the clones as siblings of this repository):

  Hart-Hornor-Jones/ca-sbac-math-levels      data/school_levels_grade11_math.csv
      caaspp_math_l4         share of grade-11 students at Level 4 in math, all students (group 1)
      caaspp_math_l1         share at Level 1 (Standard Not Met), all students
      caaspp_math_l4_sed     Level 4 share among socioeconomically disadvantaged students (group 31)
      caaspp_math_l4_notsed  Level 4 share among students not so classified (group 111)
  Hart-Hornor-Jones/caaspp-economic-status   data/schools_by_economic_status.csv
      caaspp_math_gap_sed    the within-school gap in met-or-above math: the not-disadvantaged
                             share minus the disadvantaged share (percentage points)
  Hart-Hornor-Jones/ucsd-local-preference    data/panel_long.csv (+ data/schools.csv for CEEB -> CDS)
      ucsd_adv               UCSD admit rate minus the rate predicted from the school's mean
                             applicant GPA (the repository's `ucsd_adv`; its dictionary labels
                             it "UCSD admit rate minus predicted (from GPA)" and the README
                             calls it the "advantage" measure, so it is unambiguous; the
                             variant `ucsd_adv2` also conditions on other-campus admit rates
                             and is not taken)

Rules
  * School codes are the 14-digit CDS code read as text. Only schools in this
    repository's data/schools.csv are kept (the visualizer's blob is indexed by
    that list); every dropped school is counted in the report.
  * Suppression is respected: a blank in the source stays blank, and nothing is
    imputed. Values are taken as published (the state's 2015 and 2016 school
    percentages are whole numbers; later years have one decimal in the levels
    file and two in the economic-status file).
  * Pooling happens in exactly one place: when two UC (CEEB) codes map to the
    same CDS school in the same year, their advantage values are averaged with
    each code's UCSD applicant count as the weight, which equals the pooled
    (admits - predicted admits) / applicants. For the CAASPP files no pooling
    is needed (one row per school x year x group); where the report checks
    that the two economic-status groups reproduce the all-students figure it
    weights by students_with_scores, as the levels file's documentation asks.
  * Years follow this repository's convention and need no shift: CAASPP years
    are the spring test year (2019 = 2018-19), the same convention as the
    existing caaspp_* measures; the UCSD panel's year is the fall the class
    entered college, the same keying as the existing UC measures (gpa_uc,
    elwr, ...). The UCSD panel's pooled eras (era_A..era_G) and constants are
    not year rows and are left out.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, '..') + os.sep

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument('--sbac', default=os.path.join(REPO, '..', 'ca-sbac-math-levels'))
ap.add_argument('--ses', default=os.path.join(REPO, '..', 'caaspp-economic-status'))
ap.add_argument('--ucsd', default=os.path.join(REPO, '..', 'ucsd-local-preference'))
ap.add_argument('--out', default=os.path.join(HERE, 'new_levels_gap_ucsd_values.json'))
ap.add_argument('--report', default=os.path.join(HERE, 'levels_gap_ucsd_report.txt'))
args = ap.parse_args()

lines = []


def log(s=''):
    print(s)
    lines.append(s)


schools = pd.read_csv(REPO + 'data/schools.csv', dtype={'cds14': str})
IDS = set(schools['cds14'])
wide = pd.read_csv(REPO + 'data/panel_wide.csv', dtype={'cds14': str})
values = {}       # measure -> {year(str) -> {cds -> value}}


def put(mid, df, col):
    """Store df[col] by (cds14, year), dropping blanks and schools not in schools.csv."""
    d = df[['cds14', 'year', col]].dropna(subset=[col])
    keep = d['cds14'].isin(IDS)
    dropped = d.loc[~keep, 'cds14'].nunique()
    d = d[keep]
    assert not d.duplicated(['cds14', 'year']).any(), mid
    out = {}
    for y, g in d.groupby('year'):
        out[str(int(y))] = {c: float(v) for c, v in zip(g['cds14'], g[col])}
    values[mid] = out
    log('%-22s %6d values, %4d schools, years %s; %d school(s) not in schools.csv dropped (%d values)'
        % (mid, len(d), d['cds14'].nunique(), ','.join(str(int(y)) for y in sorted(out)), dropped, int((~keep).sum())))


# ----------------------------------------------------------------- SBAC levels
log('== ca-sbac-math-levels: data/school_levels_grade11_math.csv')
L = pd.read_csv(os.path.join(args.sbac, 'data', 'school_levels_grade11_math.csv'), dtype={'cds': str})
assert L['cds'].str.fullmatch(r'\d{14}').all()
L = L.rename(columns={'cds': 'cds14'})
log('rows %d, years %s, groups in file %d' % (len(L), sorted(L['year'].unique()), L['group_code'].nunique()))
assert not L.duplicated(['cds14', 'year', 'group_code']).any()
g1 = L[L['group_code'] == 1]
g31 = L[L['group_code'] == 31]
g111 = L[L['group_code'] == 111]
blank_but_big = int((g1['pct_level4'].isna() & (g1['students_with_scores'] >= 11)).sum())
log('all-students rows with blank levels: %d (suppressed; %d of them have 11+ students with scores)'
    % (int(g1['pct_level4'].isna().sum()), blank_but_big))
put('caaspp_math_l4', g1, 'pct_level4')
put('caaspp_math_l1', g1, 'pct_level1')
put('caaspp_math_l4_sed', g31, 'pct_level4')
put('caaspp_math_l4_notsed', g111, 'pct_level4')

# ----------------------------------------------------------------- economic-status gap
log('')
log('== caaspp-economic-status: data/schools_by_economic_status.csv')
E = pd.read_csv(os.path.join(args.ses, 'data', 'schools_by_economic_status.csv'), dtype={'cds_code': str})
assert E['cds_code'].str.fullmatch(r'\d{14}').all()
E = E[(E['subject'] == 'math') & (E['grade'] == 11)].rename(columns={'cds_code': 'cds14'})
assert not E.duplicated(['cds14', 'year', 'economic_status']).any()
P = E.pivot_table(index=['cds14', 'year'], columns='economic_status', values='pct_met_or_exceeded', aggfunc='first')
P = P.rename(columns={'All students': 'all', 'Economically disadvantaged': 'sed', 'Not economically disadvantaged': 'notsed'})
P['gap'] = P['notsed'] - P['sed']          # blank whenever either group is suppressed
P = P.reset_index()
log('math school-years %d; with both groups published %d (the gap is blank when either is suppressed)'
    % (len(P), int(P['gap'].notna().sum())))
put('caaspp_math_gap_sed', P, 'gap')

# ----------------------------------------------------------------- UCSD advantage
log('')
log('== ucsd-local-preference: data/panel_long.csv, measure ucsd_adv (CEEB -> CDS via data/schools.csv)')
U = pd.read_csv(os.path.join(args.ucsd, 'data', 'panel_long.csv'), dtype={'ceeb': str, 'period': str})
US = pd.read_csv(os.path.join(args.ucsd, 'data', 'schools.csv'), dtype={'ceeb': str, 'cds14': str})
assert US['ceeb'].is_unique
n_era = int((~U['period'].str.fullmatch(r'\d{4}')).sum())
U = U[U['period'].str.fullmatch(r'\d{4}')].copy()
U['year'] = U['period'].astype(int)
X = U[U['measure'].isin(['ucsd_adv', 'ucsd_apps', 'ucsd_admit', 'ucsd_exp'])] \
    .pivot_table(index=['ceeb', 'year'], columns='measure', values='value', aggfunc='first').reset_index()
X = X.merge(US[['ceeb', 'cds14']], on='ceeb', how='left')
A = X[X['ucsd_adv'].notna()].copy()
log('%d era/constant rows left out; %d school-years with ucsd_adv across %d CEEB codes; %d lack a CDS code'
    % (n_era, len(A), A['ceeb'].nunique(), int(A['cds14'].isna().sum())))
ident = (A['ucsd_adv'] - (A['ucsd_admit'] - A['ucsd_exp'])).abs()
log('check: ucsd_adv = ucsd_admit - ucsd_exp within 0.1 (published rounding): max |diff| %.2f on %d rows'
    % (ident.max(), len(A)))
assert ident.max() <= 0.1 + 1e-9
A = A[A['cds14'].notna()]
assert A['ucsd_apps'].notna().all() and (A['ucsd_apps'] > 0).all()
dup = A.duplicated(['cds14', 'year'], keep=False)
log('CEEB codes sharing one CDS school in the same year: %d school-years (%d rows), pooled with ucsd_apps as the weight'
    % (A[dup].groupby(['cds14', 'year']).ngroups, int(dup.sum())))
for (c, y), g in A[dup].groupby(['cds14', 'year']):
    log('   %s %d: ' % (c, y) + '; '.join('CEEB %s apps %d adv %+.1f' % (r.ceeb, r.ucsd_apps, r.ucsd_adv) for r in g.itertuples()))
A['w'] = A['ucsd_apps']
A['wv'] = A['ucsd_adv'] * A['w']
G = A.groupby(['cds14', 'year']).agg(wv=('wv', 'sum'), w=('w', 'sum')).reset_index()
G['ucsd_adv'] = G['wv'] / G['w']
put('ucsd_adv', G, 'ucsd_adv')

# ----------------------------------------------------------------- checks
log('')
log('== checks')
def frame(mid):
    rows = [(c, int(y), v) for y, d in values[mid].items() for c, v in d.items()]
    return pd.DataFrame(rows, columns=['cds14', 'year', mid])

l4 = frame('caaspp_math_l4'); l1 = frame('caaspp_math_l1')
j = l4.merge(wide[['cds14', 'year', 'caaspp_math', 'caaspp_l4']], on=['cds14', 'year'], how='left')
both = j.dropna(subset=['caaspp_math'])
over = both[both['caaspp_math_l4'] > both['caaspp_math'] + 0.1 + 1e-9]
log('caaspp_math_l4 <= caaspp_math (+0.1 rounding) where both exist: %d of %d violate' % (len(over), len(both)))
assert over.empty
log('caaspp_math_l4 school-years without an existing caaspp_math value: %d (the levels file carries more school-years than the panel\'s met-or-above source, mostly 2024-25); caaspp_math without a Level 4 value: %d'
    % (int(j['caaspp_math'].isna().sum()), int(wide['caaspp_math'].notna().sum() - both.shape[0])))
r = both['caaspp_math_l4'].corr(both['caaspp_l4'])
log('r(caaspp_math_l4, caaspp_l4 [ELA+Math average]) = %.3f on %d school-years' % (r, int(both['caaspp_l4'].notna().sum())))
jj = l4.merge(l1, on=['cds14', 'year'])
s = jj['caaspp_math_l4'] + jj['caaspp_math_l1']
log('caaspp_math_l4 + caaspp_math_l1 <= 102 (the four rounded levels add to 99-102): max %.1f, %d over 102' % (s.max(), int((s > 102).sum())))
assert (s <= 102 + 1e-9).all()

# the two economic-status groups, weighted by students_with_scores, reproduce the all-students Level 4 share
w3 = L[L['group_code'].isin([1, 31, 111]) & L['cds14'].isin(IDS)]
pv = w3.pivot_table(index=['cds14', 'year'], columns='group_code', values=['pct_level4', 'students_with_scores'], aggfunc='first')
pv.columns = ['%s_%d' % (a, b) for a, b in pv.columns]
pv = pv.dropna(subset=['pct_level4_1', 'pct_level4_31', 'pct_level4_111'])
pooled = (pv['pct_level4_31'] * pv['students_with_scores_31'] + pv['pct_level4_111'] * pv['students_with_scores_111']) \
    / (pv['students_with_scores_31'] + pv['students_with_scores_111'])
d = (pooled - pv['pct_level4_1']).abs()
log('pooling the disadvantaged and not-disadvantaged Level 4 shares (weight students_with_scores) reproduces the all-students share: max |diff| %.2f points, %d of %d school-years over 0.6'
    % (d.max(), int((d > 0.6).sum()), len(d)))

# gap vs the levels file's met shares for groups 31 and 111 (an independent extraction of the same state files)
q = L[L['group_code'].isin([31, 111])].pivot_table(index=['cds14', 'year'], columns='group_code', values='pct_met', aggfunc='first')
q['gap_levels'] = q[111] - q[31]
gp = frame('caaspp_math_gap_sed').merge(q['gap_levels'].reset_index(), on=['cds14', 'year'], how='left')
dd = (gp['caaspp_math_gap_sed'] - gp['gap_levels']).abs()
log('caaspp_math_gap_sed vs the same gap from the levels file (pct_met of groups 111 and 31): %d of %d school-years compared, max |diff| %.2f, %d differ by more than 0.1 (the two files round the 2015-16 figures differently)'
    % (int(dd.notna().sum()), len(gp), dd.max(), int((dd > 0.1 + 1e-9).sum())))
gm = frame('caaspp_math_gap_sed')
log('caaspp_math_gap_sed: mean %+.1f, median %+.1f, 10th-90th pct %+.1f to %+.1f points; %d of %d school-years negative'
    % (gm.iloc[:, 2].mean(), gm.iloc[:, 2].median(), gm.iloc[:, 2].quantile(.1), gm.iloc[:, 2].quantile(.9), int((gm.iloc[:, 2] < 0).sum()), len(gm)))
ua = frame('ucsd_adv')
log('ucsd_adv: mean %+.1f, median %+.1f, min %+.1f, max %+.1f points over %d school-years' % (ua['ucsd_adv'].mean(), ua['ucsd_adv'].median(), ua['ucsd_adv'].min(), ua['ucsd_adv'].max(), len(ua)))
jx = ua.merge(wide[['cds14', 'year', 'gpa_ucsel_adm']], on=['cds14', 'year'])
log('r(ucsd_adv, gpa_ucsel_adm) = %.2f on %d school-years (expected near zero: the advantage is a residual from GPA)'
    % (jx['ucsd_adv'].corr(jx['gpa_ucsel_adm']), int(jx['gpa_ucsel_adm'].notna().sum())))

# ----------------------------------------------------------------- coverage table
log('')
log('== coverage (values = school-years)')
log('%-22s %8s %8s %s' % ('measure', 'values', 'schools', 'years'))
for mid in values:
    f = frame(mid)
    ys = sorted(int(y) for y in values[mid])
    log('%-22s %8d %8d %d-%d (%d years%s)' % (mid, len(f), f['cds14'].nunique(), ys[0], ys[-1], len(ys),
                                             '' if len(ys) == ys[-1] - ys[0] + 1 else '; none in ' + ','.join(str(y) for y in range(ys[0], ys[-1] + 1) if y not in ys)))
log('')
log('per year:')
yrs = sorted({int(y) for m in values for y in values[m]})
log('%-22s ' % 'measure' + ' '.join('%5d' % y for y in yrs))
for mid in values:
    log('%-22s ' % mid + ' '.join('%5s' % (len(values[mid][str(y)]) if str(y) in values[mid] else '') for y in yrs))

json.dump({'years': values}, open(args.out, 'w', encoding='utf-8'), separators=(',', ':'))
open(args.report, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('wrote', args.out, 'and', args.report)
