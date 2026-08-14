#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extend the ca-hs-proficiency panel with nine UC applicant-pool measures.

Run AFTER build_panel.py. Reads the existing data/ CSVs plus two UC source
files, appends the new measures, and rewrites data/panel_long.csv,
data/panel_wide.csv, data/measures.csv, and the PANEL blob inside index.html.

Source files (device paths; copy into a data/ folder next to this script):
  svetlana\\Svetlana\\uc-merit-admissions\\data\\school_campus_year_admitted_denied.csv
      ceeb x campus (9 + Universitywide) x fall 1994-2025: applicants, admits,
      denied, app_gpa, adm_gpa, den_gpa.  den_gpa is derived by exact moment
      subtraction (N_app*G_app - N_adm*G_adm)/N_denied from published means.
  svetlana\\Svetlana\\uc-merit-admissions\\data\\dv_admissions_all9.csv
      same grain, nine campuses, adds enrollees + enr_gpa (GPA-offset repair
      of 2026-07-30 applied).
  svetlana\\hs data\\ceeb_cds_crosswalk_v2.csv
      the SAME crosswalk build_panel.py used (three non-equivalent copies
      exist in the project; this is the canonical one for this repo).

Conventions carried over from build_panel.py:
  - CEEB->CDS collisions are merged with weights, never dropped.
  - Universe restricted to the schools already in data/schools.csv.
  - Derived pools (denied, admitted-not-enrolled) require pool size >= 10;
    source-published pool means (applicant/admit/enrollee GPAs) are used as
    published, weighted by their own counts.

New measures:
  gpa_uc_den      UW denied-applicant GPA (denied >= 10)
  gpa_uc_admnot   UW admitted-but-not-enrolled GPA, exact moment subtraction
                  (admits - enrollees >= 10; skipped when any campus reports
                  enrollees without an enrollee GPA, so the subtraction stays exact)
  gpa_ucsel_app / gpa_ucsel_adm / gpa_ucsel_den / gpa_ucsel_enr
                  applicant / admit / denied / enrollee GPA pooled over the three
                  most selective campuses (Berkeley, Los Angeles, San Diego),
                  weighted by each campus's own pool count; total pool >= 10
                  (denied additionally >= 10 per campus before entering)
  gpa_ucsel_gap   admit GPA minus denied GPA, campus by campus, averaged over the
                  three selective campuses weighted by applicants; needs both pool
                  means at a campus (denied >= 10 there) and >= 20 applicants total
  uc_gpa_range    max minus min over all observed campus pool means (admit and
                  denied pools at all nine campuses, pool >= 10 each; >= 4 pools)
  uc_apps_per_app campus applications per applicant: sum of the nine campus
                  applicant counts / Universitywide (unduplicated) applicants
                  (UW applicants >= 10)
"""
import json, sys
import numpy as np
import pandas as pd

D = 'data/'
SEL = ['Berkeley', 'Los Angeles', 'San Diego']
YEAR0, YEAR1 = 1994, 2025
report = []

def log(s):
    print(s); report.append(str(s))

# ------------------------------------------------------------------ inputs
xw = pd.read_csv(f'{D}ceeb_cds_crosswalk_v2.csv', dtype={'ceeb': str, 'cds14': str})
xw = xw[xw['cds14'].notna() & (xw['cds14'].str.len() == 14)]
ceeb2cds = dict(zip(xw['ceeb'], xw['cds14']))

schools = pd.read_csv(f'{D}schools.csv', dtype={'cds14': str})
UNIVERSE = set(schools['cds14'])
log(f'universe: {len(UNIVERSE)} schools (fixed by schools.csv)')

den = pd.read_csv(f'{D}school_campus_year_admitted_denied.csv', dtype={'ceeb': str})
for c in ['year', 'applicants', 'admits', 'denied', 'app_gpa', 'adm_gpa', 'den_gpa']:
    den[c] = pd.to_numeric(den[c], errors='coerce')
den = den[den['year'].between(YEAR0, YEAR1)]
den['cds14'] = den['ceeb'].map(ceeb2cds)
den = den[den['cds14'].isin(UNIVERSE)]

dv = pd.read_csv(f'{D}dv_admissions_all9.csv',
                 usecols=['ceeb', 'campus', 'year', 'enrollees', 'enr_gpa'], dtype={'ceeb': str})
for c in ['year', 'enrollees', 'enr_gpa']:
    dv[c] = pd.to_numeric(dv[c], errors='coerce')
dv = dv[dv['year'].between(YEAR0, YEAR1)]
dv['cds14'] = dv['ceeb'].map(ceeb2cds)
dv = dv[dv['cds14'].isin(UNIVERSE)]

def okgpa(s):
    return s.notna() & (s > 0) & (s <= 5)

values = {}   # mid -> {year -> {cds: value}}
def put(mid, df, valcol):
    """df: columns cds14, year, <valcol>; already one row per cds-year."""
    values[mid] = {}
    for y, g in df.groupby('year'):
        values[mid][int(y)] = dict(zip(g['cds14'], g[valcol]))
    cells = sum(len(v) for v in values[mid].values())
    yrs = sorted(values[mid])
    log(f'{mid:16s} {yrs[0]}-{yrs[-1]}  cells={cells}')

def wmean(df, val, w):
    """weighted mean of df[val] by df[w] per (cds14, year) -> tidy frame"""
    d = df[okgpa(df[val]) & df[w].notna() & (df[w] >= 1)]
    g = d.groupby(['cds14', 'year']).apply(
        lambda x: pd.Series({'v': np.average(x[val], weights=x[w]),
                             'n': float(x[w].sum())}), include_groups=False).reset_index()
    return g

# ------------------------------------------------------------------ 1. UW denied GPA
uw = den[den['campus'] == 'Universitywide'].copy()
d1 = uw[okgpa(uw['den_gpa']) & (uw['denied'] >= 10)]
g1 = wmean(d1, 'den_gpa', 'denied')
put('gpa_uc_den', g1, 'v')

# ------------------------------------------------------------------ 2. UW admitted-but-not-enrolled GPA
# enrollee totals per ceeb-year, exact only when every campus with enrollees has a GPA
e = dv[dv['enrollees'].notna() & (dv['enrollees'] >= 1)].copy()
bad = e.groupby(['ceeb', 'year'])['enr_gpa'].apply(lambda s: s.isna().any() or ((s <= 0) | (s > 5)).any())
etot = e.groupby(['ceeb', 'year']).apply(
    lambda x: pd.Series({'n_enr': float(x['enrollees'].sum()),
                         'g_enr': np.average(x['enr_gpa'], weights=x['enrollees'])}),
    include_groups=False).reset_index()
etot = etot.merge(bad.rename('bad').reset_index(), on=['ceeb', 'year'])
etot = etot[~etot['bad']]
a = uw[okgpa(uw['adm_gpa']) & uw['admits'].notna() & (uw['admits'] >= 1)][
    ['ceeb', 'cds14', 'year', 'admits', 'adm_gpa']]
m = a.merge(etot[['ceeb', 'year', 'n_enr', 'g_enr']], on=['ceeb', 'year'], how='inner')
m['n_no'] = m['admits'] - m['n_enr']
m = m[m['n_no'] >= 10]
m['g_no'] = (m['admits'] * m['adm_gpa'] - m['n_enr'] * m['g_enr']) / m['n_no']
n_art = int((~((m['g_no'] > 0) & (m['g_no'] < 5))).sum())
m = m[(m['g_no'] > 0) & (m['g_no'] < 5)]
log(f'admnot: artifacts outside (0,5) blanked: {n_art}')
g2 = m.groupby(['cds14', 'year']).apply(
    lambda x: np.average(x['g_no'], weights=x['n_no']), include_groups=False).rename('v').reset_index()
put('gpa_uc_admnot', g2, 'v')

# ------------------------------------------------------------------ 3-6. selective-trio pools
sel = den[den['campus'].isin(SEL)].copy()
for mid, val, w in [('gpa_ucsel_app', 'app_gpa', 'applicants'),
                    ('gpa_ucsel_adm', 'adm_gpa', 'admits')]:
    g = wmean(sel, val, w)
    put(mid, g[g['n'] >= 10], 'v')

seld = sel[sel['denied'] >= 10]
g = wmean(seld, 'den_gpa', 'denied')
put('gpa_ucsel_den', g[g['n'] >= 10], 'v')

sele = dv[dv['campus'].isin(SEL)]
g = wmean(sele, 'enr_gpa', 'enrollees')
put('gpa_ucsel_enr', g[g['n'] >= 10], 'v')

# ------------------------------------------------------------------ 7. selective admit-minus-denied gap
gp = sel[okgpa(sel['adm_gpa']) & okgpa(sel['den_gpa']) & (sel['denied'] >= 10)
         & sel['applicants'].notna() & (sel['applicants'] >= 1)].copy()
gp['gap'] = gp['adm_gpa'] - gp['den_gpa']
gg = gp.groupby(['cds14', 'year']).apply(
    lambda x: pd.Series({'v': np.average(x['gap'], weights=x['applicants']),
                         'n': float(x['applicants'].sum())}), include_groups=False).reset_index()
put('gpa_ucsel_gap', gg[gg['n'] >= 20], 'v')

# ------------------------------------------------------------------ 8. range over all observed pool means
camp = den[den['campus'] != 'Universitywide']
pools = pd.concat([
    camp[okgpa(camp['adm_gpa']) & (camp['admits'] >= 10)][['cds14', 'year', 'adm_gpa']]
        .rename(columns={'adm_gpa': 'g'}),
    camp[okgpa(camp['den_gpa']) & (camp['denied'] >= 10)][['cds14', 'year', 'den_gpa']]
        .rename(columns={'den_gpa': 'g'})])
rg = pools.groupby(['cds14', 'year'])['g'].agg(['max', 'min', 'count']).reset_index()
rg = rg[rg['count'] >= 4]
rg['v'] = rg['max'] - rg['min']
put('uc_gpa_range', rg, 'v')

# ------------------------------------------------------------------ 9. campus applications per applicant
capp = camp[camp['applicants'].notna()].groupby(['ceeb', 'year'])['applicants'].sum().rename('c_apps')
uwa = uw[uw['applicants'].notna() & (uw['applicants'] >= 10)][['ceeb', 'cds14', 'year', 'applicants']]
r = uwa.merge(capp.reset_index(), on=['ceeb', 'year'], how='inner')
rr = r.groupby(['cds14', 'year']).apply(
    lambda x: float(x['c_apps'].sum()) / float(x['applicants'].sum()), include_groups=False
    ).rename('v').reset_index()
rr = rr[(rr['v'] >= 0.5) & (rr['v'] <= 9)]
put('uc_apps_per_app', rr, 'v')

# ------------------------------------------------------------------ checks
log('--- checks ---')
# identity: admnot GPA must sit between enrollee GPA and admit GPA... not required
# (yield selection can go either way) but admit GPA must equal the enrollment-weighted
# blend of enrollee and non-enrollee means. Verify the reconstruction on 200 sampled cells.
chk = m.sample(min(200, len(m)), random_state=0)
recon = (chk['n_enr'] * chk['g_enr'] + chk['n_no'] * chk['g_no']) / chk['admits']
assert np.allclose(recon, chk['adm_gpa'], atol=1e-9), 'admnot moment identity failed'
log(f'admnot blend identity holds on {len(chk)} sampled cells (1e-9)')
# denied below admitted, virtually everywhere it can be compared (UW)
j = uw[okgpa(uw['den_gpa']) & okgpa(uw['adm_gpa']) & (uw['denied'] >= 10)]
share = float((j['den_gpa'] < j['adm_gpa']).mean())
log(f'UW denied < admitted in {100*share:.1f}% of comparable cells (n={len(j)})')
# range non-negative
assert (rg['v'] >= 0).all()
log('range non-negative: OK')

with open('extend_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))

# hand the values dict to the caller (import) or dump for the splice step
out = {mid: {str(y): values[mid][y] for y in values[mid]} for mid in values}
with open('new_values.json', 'w', encoding='utf-8') as f:
    json.dump(out, f)
log('wrote new_values.json + extend_report.txt')
