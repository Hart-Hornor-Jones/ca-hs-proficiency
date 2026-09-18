#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add two new families of measures to the ca-hs-proficiency panel:

  A. CSU's archived school reports, 1995-2017 (asd.calstate.edu, recovered from
     the Wayback Machine - see Svetlana\\CSU ASD Wayback Harvest 2026-09-15\\README.txt).
     Seven measures at school x entering-fall grain:
       csu_asd_ftf          first-time freshmen entering CSU from the school (regular admits)
       gpa_csu_asd          their average high-school GPA
       sat_csu_asd          their average SAT verbal + math (1600 scale)
       csu_math_ready_asd   share proficient in math at entry (100 - % not proficient on the ELM)
       csu_wc_ready_asd     share proficient in English at entry (100 - % not proficient on the EPT)
       csu_ret1_asd         share still enrolled at CSU one year later
       gpa_csu1_asd         their average CSU GPA after one year
     These are the older cousins of gpa_csu / csu_math_ready / csu_wc_ready /
     gpa_csu1 (2021-25, from CSU's current dashboards).

  B. National Merit semifinalists, from NMSC's California press-release lists for
     the 2016, 2018, 2020 and 2022 programs (hs data\\national-merit\\*.pdf, parsed
     by parse_nmsf.py into nmsf_semifinalists_by_school.csv):
       nmsf                 semifinalists at the school (class of that year)
       nmsf_rate            semifinalists per 100 students in a grade

School identification. The CSU reports carry a 6-digit school code that is the
first six digits of the school's 7-digit CDS school code (verified on ~900
schools by name); the code is joined to schools.csv and the name is checked.
Codes that fail the name check, and schools whose code is not CDS-derived
(newer LAUSD schools, most charters), fall back to a name + city match against
the CDE directory (schoolmatch.py). NMSC lists give school name and city only,
so they use the name + city match throughout. Private schools are never matched
- they are not in the panel - and every non-exact match is listed in the report.

Inputs (device paths; copy into build/data/ next to this script):
  Svetlana\\CSU ASD Wayback Harvest 2026-09-15\\wayback_asd\\compiled\\school_year_panel.csv
      -> data/csu_asd_school_year_panel.csv
  hs data\\ca_school_context_out\\cde_public_schools_districts_current_clean.csv
      -> data/cde_public_schools_districts_current_clean.csv   (CDE directory: city per CDS)
  data/nmsf_semifinalists_by_school.csv   (from parse_nmsf.py)

Writes new_asd_nmsf_values.json (splice_asd_nmsf_measures.py merges it into the
CSVs and the page), asd_nmsf_report.txt, and the two match tables
match_csu_asd.csv / match_nmsf.csv for inspection.
"""
import json
import difflib
import numpy as np
import pandas as pd
from schoolmatch import Matcher, norm, norm_city, PRIVATE_HINTS, deaccent

D = 'data/'
MIN_N = 10           # smallest pool whose average is shown (same rule as the UC pools)
MIN_SCHOOLS = 15     # a measure-year with fewer matched schools than this is dropped
report = []


def log(s):
    print(s); report.append(str(s))


schools = pd.read_csv('../data/schools.csv', dtype={'cds14': str})
UNIVERSE = set(schools['cds14'])
name_of = dict(zip(schools['cds14'], schools['school_name']))
county_of_code = (schools.assign(cc=schools['cds14'].str[:2]).groupby('cc')['county']
                  .agg(lambda s: s.mode().iloc[0]).to_dict())
panel_years = pd.read_csv('../data/panel_long.csv', dtype={'cds14': str}, usecols=['cds14', 'year', 'measure'])
active = set(panel_years.loc[panel_years['year'] >= 2015, 'cds14'])
directory = pd.read_csv(f'{D}cde_public_schools_districts_current_clean.csv', dtype=str)
log(f'universe: {len(UNIVERSE)} schools; {len(active)} with data since 2015')

# hand adjudications: (normalized name, normalized city) -> cds14
OVERRIDES = {
    (norm('SAN DIEGO MET H. S.'), norm_city('SAN DIEGO')): '37683380107482',   # San Diego Metro Career and Tech
}
M = Matcher(schools, directory, overrides=OVERRIDES, active=active)

values = {}      # mid -> {year -> {cds: value}}


def put(mid, df, vcol, lo=None, hi=None):
    d = df[df[vcol].notna() & df['cds14'].isin(UNIVERSE)].copy()
    d[vcol] = pd.to_numeric(d[vcol], errors='coerce')
    d = d[d[vcol].notna()]
    if lo is not None: d = d[d[vcol] >= lo]
    if hi is not None: d = d[d[vcol] <= hi]
    d = d.drop_duplicates(['cds14', 'year'])
    values[mid] = {}
    dropped = []
    for y, g in d.groupby('year'):
        if len(g) < MIN_SCHOOLS:
            dropped.append(f'{int(y)}:{len(g)}'); continue
        values[mid][int(y)] = dict(zip(g['cds14'], g[vcol].astype(float)))
    yrs = sorted(values[mid])
    cells = sum(len(v) for v in values[mid].values())
    per = ' '.join(f'{y}:{len(values[mid][y])}' for y in yrs)
    log(f'{mid:20s} {yrs[0]}-{yrs[-1]}  cells={cells:6d}  per year {per}'
        + (f'  [dropped thin years {", ".join(dropped)}]' if dropped else ''))


# ================================================================ A. CSU archived reports
p = pd.read_csv(f'{D}csu_asd_school_year_panel.csv', dtype={'campus_code': str})
p = p.rename(columns={'fall': 'year', 'county': 'city'})       # the compile step's "county" column holds the CITY
p['city'] = p['city'].where(p['city'].notna(), '')
log(f'CSU archived panel: {len(p)} school-years, {p["campus_code"].nunique()} schools, falls {p["year"].min()}-{p["year"].max()}')

# --- code join: CSU code = first six digits of the 7-digit CDS school code
key = schools[~schools['school_name'].str.contains('Students in NPS', regex=False)].copy()
key['key'] = key['cds14'].str[7:13]
bykey = key.groupby('key')['cds14'].apply(list).to_dict()
JUNKTOK = {'HIGH', 'SENIOR', 'CHARTER', 'ACADEMY', 'SCHOOL', 'JUNIOR', 'HS'}


def name_ok(a, b):
    """Is the panel record's name plausibly the same school as the CSU label?"""
    ratio = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    ta = set(norm(a).split()) - JUNKTOK
    tb = set(norm(b).split()) - JUNKTOK
    overlap = len(ta & tb) / max(1, min(len(ta), len(tb)))
    return ratio, overlap, (ratio >= 0.6 or overlap >= 0.5)


rows = []
u = p.groupby('campus_code', as_index=False).agg(school=('school', 'first'), city=('city', 'first'),
                                                  n_years=('year', 'size'), ftf=('csu_ftf_regular', 'sum'))
for r in u.itertuples(index=False):
    best = None
    for c in bykey.get(r.campus_code, []):
        ratio, ov, ok = name_ok(r.school, name_of[c])
        if best is None or ratio > best[1]:
            best = (c, ratio, ov, ok)
    if best and best[3]:
        rows.append((r.campus_code, r.school, r.city, r.n_years, r.ftf, best[0], 'code+name', name_of[best[0]], round(best[1], 2)))
        continue
    county = county_of_code.get(r.campus_code[:2])
    cds, tier, mn = M.match(r.school, r.city, county=county)
    if cds is None and best:
        tier = f'code_name_conflict({best[1]:.2f} {name_of[best[0]]})'
    rows.append((r.campus_code, r.school, r.city, r.n_years, r.ftf, cds, tier, mn, ''))
mt = pd.DataFrame(rows, columns=['csu_code', 'csu_school', 'csu_city', 'n_years', 'ftf_sum', 'cds14', 'tier', 'matched_name', 'name_ratio'])
mt.to_csv('match_csu_asd.csv', index=False, encoding='utf-8')
mt['t'] = mt['tier'].str.split('(').str[0]
log('--- CSU archived reports: school matching (schools / school-years / freshmen) ---')
for t, g in mt.groupby('t'):
    log(f'  {t:22s} {len(g):5d} {int(g.n_years.sum()):6d} {int(g.ftf_sum.sum()):8d}')
matched = mt[mt['cds14'].notna()]
log(f'  matched: {len(matched)} of {len(mt)} schools; {int(matched.n_years.sum())} of {int(mt.n_years.sum())} school-years '
    f'({100*matched.n_years.sum()/mt.n_years.sum():.1f}%); freshmen {100*matched.ftf_sum.sum()/mt.ftf_sum.sum():.1f}%')
log('  unmatched with the most freshmen (private schools are expected here):')
for r in mt[mt['cds14'].isna()].sort_values('ftf_sum', ascending=False).head(25).itertuples():
    log(f'    {r.csu_code} {r.csu_school[:45]:45s} {r.csu_city[:18]:18s} ftf={int(r.ftf_sum):5d}  {r.tier[:60]}')
log('  every non-code match, for review:')
for r in mt[mt['cds14'].notna() & (mt['t'] != 'code+name')].itertuples():
    log(f'    {r.csu_code} {r.csu_school[:40]:40s} {r.csu_city[:16]:16s} -> {r.matched_name[:40]:40s} [{r.tier}]')
# a code that maps to two CSU labels (both matched to the same CDS) is fine: aggregate by cds14 below
dup = matched[matched.duplicated('cds14', keep=False)].sort_values('cds14')
if len(dup):
    log(f'  {dup.cds14.nunique()} CDS codes receive two CSU labels (kept: the panel is aggregated by CDS, first non-null value wins):')
    for c, g in dup.groupby('cds14'):
        log(f'    {c} <- ' + ' | '.join(f'{a} {b}' for a, b in zip(g.csu_code, g.csu_school)))

p = p.merge(mt[['csu_code', 'cds14']].rename(columns={'csu_code': 'campus_code'}), on='campus_code', how='inner')
for c in ['csu_ftf_regular', 'hs_gpa_n', 'hs_gpa_mean', 'sat_verbal_mean', 'sat_math_mean',
          'pct_not_proficient_math', 'pct_not_proficient_english', 'continuation_pct', 'first_year_csu_gpa']:
    p[c] = pd.to_numeric(p[c], errors='coerce')
p = p.sort_values(['cds14', 'year', 'csu_ftf_regular'], ascending=[True, True, False])
p = p.groupby(['cds14', 'year'], as_index=False).first()     # two labels -> one row per CDS-year

p['csu_asd_ftf'] = p['csu_ftf_regular']
big = p['hs_gpa_n'] >= MIN_N
p['gpa_csu_asd'] = p['hs_gpa_mean'].where(big)
p['sat_csu_asd'] = (p['sat_verbal_mean'] + p['sat_math_mean']).where(big)
bigf = p['csu_ftf_regular'] >= MIN_N
p['csu_math_ready_asd'] = (100 - p['pct_not_proficient_math']).where(bigf)
p['csu_wc_ready_asd'] = (100 - p['pct_not_proficient_english']).where(bigf)
p['csu_ret1_asd'] = p['continuation_pct'].where(bigf)
p['gpa_csu1_asd'] = p['first_year_csu_gpa'].where(bigf)

put('csu_asd_ftf', p, 'csu_asd_ftf', 1, 5000)
put('gpa_csu_asd', p, 'gpa_csu_asd', 1.0, 4.5)
put('sat_csu_asd', p, 'sat_csu_asd', 400, 1600)
put('csu_math_ready_asd', p, 'csu_math_ready_asd', 0, 100)
put('csu_wc_ready_asd', p, 'csu_wc_ready_asd', 0, 100)
put('csu_ret1_asd', p, 'csu_ret1_asd', 0, 100)
put('gpa_csu1_asd', p, 'gpa_csu1_asd', 0.5, 4.0)

# ================================================================ B. National Merit semifinalists
nm = pd.read_csv(f'{D}nmsf_semifinalists_by_school.csv')
YEARS_NM = sorted(nm['year'].unique())
log(f'National Merit lists: programs {YEARS_NM}; ' + ', '.join(f'{y}: {int(nm[nm.year==y].n.sum())} semifinalists at {int((nm.year==y).sum())} schools' for y in YEARS_NM))
u = nm.groupby(['school', 'city'], as_index=False)['n'].sum()
rows = []
for r in u.itertuples(index=False):
    cds, tier, mn = M.match(r.school, r.city)
    rows.append((r.school, r.city, r.n, cds, tier, mn))
mn_t = pd.DataFrame(rows, columns=['nmsc_school', 'nmsc_city', 'semifinalists_all_years', 'cds14', 'tier', 'matched_name'])
mn_t.to_csv('match_nmsf.csv', index=False, encoding='utf-8')
mn_t['t'] = mn_t['tier'].str.split('(').str[0]
log('--- National Merit: school matching (schools / semifinalists, all four lists) ---')
for t, g in mn_t.groupby('t'):
    log(f'  {t:22s} {len(g):5d} {int(g.semifinalists_all_years.sum()):6d}')
mm = mn_t[mn_t['cds14'].notna()]
log(f'  matched {len(mm)} of {len(mn_t)} school labels; {int(mm.semifinalists_all_years.sum())} of {int(mn_t.semifinalists_all_years.sum())} '
    f'semifinalists ({100*mm.semifinalists_all_years.sum()/mn_t.semifinalists_all_years.sum():.1f}%) - the rest are at private schools or home-schooled')
log('  every non-exact match, for review:')
for r in mn_t[mn_t['cds14'].notna() & (mn_t['t'] != 'exact')].itertuples():
    log(f'    {r.nmsc_school[:42]:42s} {r.nmsc_city[:20]:20s} -> {name_of[r.cds14][:40]:40s} [{r.tier}]')
log('  unmatched labels with 5+ semifinalists (expected: private schools):')
for r in mn_t[mn_t['cds14'].isna() & (mn_t.semifinalists_all_years >= 5)].sort_values('semifinalists_all_years', ascending=False).itertuples():
    log(f'    {r.nmsc_school[:42]:42s} {r.nmsc_city[:20]:20s} n={int(r.semifinalists_all_years):3d}  {r.tier[:50]}')

nm = nm.merge(mn_t[['nmsc_school', 'nmsc_city', 'cds14']].rename(columns={'nmsc_school': 'school', 'nmsc_city': 'city'}),
              on=['school', 'city'], how='inner')
cnt = nm.groupby(['cds14', 'year'], as_index=False)['n'].sum()

# zeros: a public high school that tested grade 11 that year (a CAASPP value in the
# panel; 2019 stands in for 2020, when the test was not given) and is not on the list
# had zero semifinalists. The lists are complete for the state, so the zero is real.
has = panel_years[panel_years['measure'] == 'caaspp'].groupby('year')['cds14'].apply(set).to_dict()
size = pd.to_numeric(schools.set_index('cds14')['students_per_grade'], errors='coerce')
rows = []
for y in YEARS_NM:
    present = has.get(y if y != 2020 else 2019, set())
    listed = dict(zip(cnt.loc[cnt.year == y, 'cds14'], cnt.loc[cnt.year == y, 'n']))
    for c in present | set(listed):
        rows.append((c, y, float(listed.get(c, 0))))
nmv = pd.DataFrame(rows, columns=['cds14', 'year', 'nmsf'])
nmv['sz'] = nmv['cds14'].map(size)
nmv['nmsf_rate'] = (100 * nmv['nmsf'] / nmv['sz']).where(nmv['sz'] >= 20)
put('nmsf', nmv, 'nmsf', 0, 500)
put('nmsf_rate', nmv, 'nmsf_rate', 0, 100)
for y in YEARS_NM:
    v = nmv[nmv.year == y]
    log(f'  {y}: {len(v)} schools in the panel, {int((v.nmsf>0).sum())} with 1+ semifinalists, '
        f'{int(v.nmsf.sum())} semifinalists placed; top: '
        + ', '.join(f'{name_of[c]} {int(n)}' for c, n in v.sort_values("nmsf", ascending=False).head(4)[['cds14', 'nmsf']].values))

# ================================================================ checks
log('--- checks ---')
anchors = {}
for cds, nm_ in name_of.items():
    for want in ['Berkeley High', 'Lowell High', 'Mission High (San Francisco)', 'Mission San Jose High', 'Compton High']:
        if nm_ == want:
            anchors[want] = cds
for want, cds in sorted(anchors.items()):
    bits = []
    for mid in ['csu_asd_ftf', 'gpa_csu_asd', 'sat_csu_asd', 'csu_math_ready_asd', 'csu_wc_ready_asd', 'csu_ret1_asd', 'gpa_csu1_asd']:
        ys = [y for y in values[mid] if cds in values[mid][y]]
        if ys:
            y = min(ys); bits.append(f'{mid}({y})={values[mid][y][cds]:g}')
    for y in YEARS_NM:
        if y in values['nmsf'] and cds in values['nmsf'][y]:
            bits.append(f'nmsf({y})={values["nmsf"][y][cds]:g}')
    log(f'  {want}: ' + '; '.join(bits))
# the modern and archived CSU readiness measures should correlate across schools (different eras, same schools)
for a, b, ya, yb in [('csu_math_ready_asd', 'csu_math_ready', 2016, 2021), ('gpa_csu_asd', 'gpa_csu', 1997, 2021)]:
    pass   # cross-era correlations need the merged panel; see the splice script's report
sat = values['sat_csu_asd']
for y in sorted(sat)[:3]:
    log(f'  sat_csu_asd {y}: median {np.median(list(sat[y].values())):.0f} (CA CSU-freshman mean that year was about 985)')

out = {'years': {m: {str(y): values[m][y] for y in values[m]} for m in values}}
with open('new_asd_nmsf_values.json', 'w', encoding='utf-8') as f:
    json.dump(out, f)
with open('asd_nmsf_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
log('wrote new_asd_nmsf_values.json + asd_nmsf_report.txt + match_csu_asd.csv + match_nmsf.csv')
