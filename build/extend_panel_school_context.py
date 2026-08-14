#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add eight school-context measures to the ca-hs-proficiency panel.

These are NOT measures of academic proficiency, so they are deliberately kept
off the X and Y axes of the visualizer: they are selectable only as the dot
colour and as the measure a residual is compared against. They answer "what
kind of school is this?", not "how did it do?".

Run after build_panel.py and extend_panel_uc_pools.py. Writes new_context_values.json,
which splice_context_measures.py merges into the CSVs and the page.

Source files (device paths; copy into a data/ folder next to this script):
  svetlana\\Svetlana\\uc-merit-admissions\\data\\components\\upp_lcff.csv
      CUPC unduplicated pupil percentage + UC's LCFF+ designation, by school year.
      ⚠ `cupc_year` "2016-2017" is the OCTOBER 2016 collection = school year 2016-17
      = spring 2017, so the panel year is the SECOND number. Verified against
      Correlation Matrix 2026-07-05\\school_year_wide.csv: 10,086/10,086 rows agree
      under that alignment, 17/10,086 under the other.
  svetlana\\Svetlana\\uc-merit-admissions\\data\\components\\school_group_context.csv
      Grade-11 socioeconomically-disadvantaged and English-learner shares, parsed
      from the CAASPP research files' per-group reported enrollment. Its `year` is
      already the CAASPP spring year (2016-2025, no 2020) - no shift.
  svetlana\\Svetlana\\uc-merit-admissions\\data\\components\\school_race_context.csv
      CDE per-school enrollment by race/ethnicity, grades 9-12. `start_year` is a
      FALL year, so the panel year is start_year + 1. `race_urg_pct` uses UC's
      under-represented definition (Hispanic + Black + American Indian).
  svetlana\\Svetlana\\uc-merit-admissions\\data\\components\\tract_context.csv
      ACS tract context for the school's own location. `year` is the school spring
      year (2015-2025, no 2020). ⚠ this describes the NEIGHBORHOOD, not the students.
  svetlana\\Svetlana\\Lott Walkthrough 2026-07-09\\charter_flags.csv
      CDS -> charter yes/no from the CDE public school directory. Time-invariant.

Two measures are constants (one value per school, no year): charter status and
school size. They are stored with a `k:1` marker so the page reads a single row.
"""
import json
import numpy as np
import pandas as pd

D = 'data/'
YEAR0, YEAR1 = 1994, 2025
report = []

def log(s):
    print(s); report.append(str(s))

schools = pd.read_csv(f'{D}schools.csv', dtype={'cds14': str})
UNIVERSE = set(schools['cds14'])
log(f'universe: {len(UNIVERSE)} schools')

values = {}      # mid -> {year -> {cds: value}}
constants = {}   # mid -> {cds: value}

def put_year(mid, df, ycol, vcol, lo=None, hi=None):
    d = df[df[vcol].notna() & df['cds14'].isin(UNIVERSE)].copy()
    d[ycol] = pd.to_numeric(d[ycol], errors='coerce')
    d = d[d[ycol].between(YEAR0, YEAR1)]
    if lo is not None: d = d[d[vcol] >= lo]
    if hi is not None: d = d[d[vcol] <= hi]
    d = d.drop_duplicates(['cds14', ycol])
    values[mid] = {}
    for y, g in d.groupby(ycol):
        values[mid][int(y)] = dict(zip(g['cds14'], g[vcol].astype(float)))
    yrs = sorted(values[mid])
    cells = sum(len(v) for v in values[mid].values())
    per = [len(values[mid][y]) for y in yrs]
    log(f'{mid:16s} {yrs[0]}-{yrs[-1]}  cells={cells:6d}  per-year min/max {min(per)}/{max(per)}')

def put_const(mid, series):
    s = series[series.index.isin(UNIVERSE)].dropna()
    constants[mid] = {k: float(v) for k, v in s.items()}
    log(f'{mid:16s} CONSTANT      schools={len(constants[mid])}')

# ------------------------------------------------------------------ 1-2. UPP and LCFF+
u = pd.read_csv(f'{D}upp_lcff.csv', dtype={'cds14': str})
u['year'] = u['cupc_year'].str.split('-').str[1].astype(int)   # see docstring
u['upp_pct'] = pd.to_numeric(u['upp_pct'], errors='coerce')
put_year('ctx_upp', u, 'year', 'upp_pct', 0, 100)
u['lcff'] = (u['lcff_plus_flag'].astype(str).str.upper() == 'Y').astype(float)
# assignment must be deterministic on UPP >= 75 (UC's rule)
mis = int(((u['upp_pct'] >= 75) != (u['lcff'] == 1)).sum())
log(f'LCFF+ flag disagrees with UPP >= 75 on {mis} of {len(u)} school-years')
put_year('ctx_lcff', u, 'year', 'lcff')

# ------------------------------------------------------------------ 3-4. SED and EL (grade 11)
g = pd.read_csv(f'{D}school_group_context.csv', dtype={'cds14': str})
for c in ['sed_pct', 'el_pct']:
    g[c] = pd.to_numeric(g[c], errors='coerce')
put_year('ctx_sed', g, 'year', 'sed_pct', 0, 100)
put_year('ctx_el', g, 'year', 'el_pct', 0, 100)

# ------------------------------------------------------------------ 5. % under-represented (school)
r = pd.read_csv(f'{D}school_race_context.csv', dtype={'cds14': str})
r['year'] = pd.to_numeric(r['start_year'], errors='coerce') + 1     # fall -> spring
r['race_urg_pct'] = pd.to_numeric(r['race_urg_pct'], errors='coerce')
r = r[pd.to_numeric(r['enr_9_12_total'], errors='coerce') >= 20]
put_year('ctx_urg', r, 'year', 'race_urg_pct', 0, 100)

# ------------------------------------------------------------------ 6. neighborhood income
t = pd.read_csv(f'{D}tract_context.csv', dtype={'cds14': str})
t['inc'] = pd.to_numeric(t['inc'], errors='coerce')
put_year('ctx_tract_inc', t, 'year', 'inc', 1, 1e7)

# ------------------------------------------------------------------ 7-8. constants
ch = pd.read_csv(f'{D}charter_flags.csv', dtype={'cds14': str})
ch['v'] = (ch['charter'].astype(str).str.upper() == 'Y').astype(float)
put_const('ctx_charter', ch.drop_duplicates('cds14').set_index('cds14')['v'])

sz = pd.to_numeric(schools['students_per_grade'], errors='coerce')
sz = sz.where(sz > 0)
put_const('ctx_size', pd.Series(sz.values, index=schools['cds14']))

# ------------------------------------------------------------------ checks
log('--- checks ---')
# UPP: statewide median should sit near the ~71% recorded for the UC-feeder universe
for y in [2017, 2021, 2025]:
    v = list(values['ctx_upp'].get(y, {}).values())
    log(f'  UPP {y}: n={len(v)} median={np.median(v):.1f} mean={np.mean(v):.1f}')
# URG: statewide enrollment-weighted share should be ~60% in recent years
for y in [2015, 2020, 2025]:
    v = list(values['ctx_urg'].get(y, {}).values())
    if v: log(f'  URG {y}: n={len(v)} median={np.median(v):.1f} mean={np.mean(v):.1f}')
# LCFF+ share of schools
for y in [2017, 2025]:
    v = list(values['ctx_lcff'].get(y, {}).values())
    log(f'  LCFF+ {y}: {100*np.mean(v):.1f}% of {len(v)} schools designated')
log(f'  charter: {100*np.mean(list(constants["ctx_charter"].values())):.1f}% of '
    f'{len(constants["ctx_charter"])} schools')
# named anchors
name_of = dict(zip(schools['cds14'], schools['school_name']))
anchors = {}
for cds, nm in name_of.items():
    for want in ['Compton High', 'Piedmont High', 'Lowell High', 'Berkeley High', 'Mission High']:
        if nm.startswith(want.split(' High')[0]) and nm.endswith('High'):
            anchors.setdefault(want, cds)
for nm, cds in sorted(anchors.items()):
    log(f'  {nm:16s} URG2025={values["ctx_urg"].get(2025, {}).get(cds)} '
        f'UPP2025={values["ctx_upp"].get(2025, {}).get(cds)} '
        f'SED2025={values["ctx_sed"].get(2025, {}).get(cds)}')

out = {'years': {m: {str(y): values[m][y] for y in values[m]} for m in values},
       'consts': constants}
with open('new_context_values.json', 'w', encoding='utf-8') as f:
    json.dump(out, f)
with open('context_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
log('wrote new_context_values.json + context_report.txt')
