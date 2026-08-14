#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Provenance for proficiency_compare.html (built 2026-08-14, revised same day:
# +7 college-outcome measures, collapsible controls, style round).
# Source files (device paths):
#   svetlana\Svetlana\Panel Build 2026-06-07\components\caaspp_YYYY.csv   (CAASPP % met, means, n)
#   svetlana\Svetlana\caaspp_exceeded.csv                                  (Level 4 share + cross-check)
#   svetlana\Svetlana\uc-merit-admissions\data\ag_eligibility_cleaned.csv (A-G, cleaned)
#   svetlana\hs data\star-scores\panel\test_context_panel_v2.csv          (STAR, CAHSEE, AP, SAT, ACT)
#   svetlana\Svetlana\uc-merit-admissions\data\school_campus_year_admitted_denied.csv (UC applicant GPA, Universitywide)
#   svetlana\hs data\csu-gpa-harvest\csu_hs_gpa_v3_tidy.csv                (CSU freshman HS GPA + CSU GPA one year later)
#   svetlana\csu-hs-dashboard\out\csu_placement_by_cohort.csv              (GE math/writing placement at CSU entry)
#   svetlana\csu-hs-dashboard\out\csu_dash_school_crosswalk.csv            (dash_id -> CDS bridge)
#   svetlana\Svetlana\uc-merit-admissions\data\elwr_school_year_wide.csv  (UC ELWR satisfaction, enrollees)
#   svetlana\Svetlana\Correlation Matrix 2026-07-05\school_year_wide.csv    (UC retention/graduation; enrollment for dot size)
#   svetlana\hs data\ceeb_cds_crosswalk_v2.csv                              (CEEB->CDS bridge)
#   svetlana\hs data\star-scores\panel\census_achievement_spine.csv + historical lookup (names)
# To re-run locally, copy those into a data\ folder next to this script (see D below).

"""Build the school x year panel embedded in proficiency_compare.html."""
import json, sys
import pandas as pd, numpy as np

D = 'data/'
OUT_JS = 'panel.js'
YEAR0, YEAR1 = 1994, 2025
report = []

def log(s):
    print(s); report.append(str(s))

# ------------------------------------------------------------------
# 1. Value store: values[mid][year] = dict cds -> float
values = {}
def put(mid, year, series):
    """series: pandas Series indexed by cds14, float values; drops NaN."""
    s = series.dropna()
    if mid not in values: values[mid] = {}
    if year in values[mid]:
        raise SystemExit(f'duplicate put {mid} {year}')
    values[mid][year] = s.to_dict()

# ------------------------------------------------------------------
# 2. CAASPP (components: cds14, year, ela_pct_met, math_pct_met, ela_mean, math_mean, ela_n, math_n)
caaspp_n = {}   # cds -> max tested count (for size fallback)
for y in [2015,2016,2017,2018,2019,2021,2022,2023,2024,2025]:
    c = pd.read_csv(f'{D}panelbuild_components/caaspp_{y}.csv', dtype={'cds14':str})
    c = c.drop_duplicates('cds14').set_index('cds14')
    for col in ['ela_pct_met','math_pct_met','ela_mean','math_mean','ela_n','math_n']:
        c[col] = pd.to_numeric(c[col], errors='coerce')
    # skipna average of the subjects the school has (leal convention #2)
    put('caaspp',      y, c[['ela_pct_met','math_pct_met']].mean(axis=1, skipna=True))
    put('caaspp_math', y, c['math_pct_met'])
    put('caaspp_ela',  y, c['ela_pct_met'])
    dfs = pd.concat([c['ela_mean']-2583.0, c['math_mean']-2628.0], axis=1).mean(axis=1, skipna=True)
    put('caaspp_dfs',  y, dfs)
    n = c[['ela_n','math_n']].max(axis=1)
    for k,v in n.dropna().items():
        caaspp_n[k] = max(caaspp_n.get(k,0), v)

# Level 4 (standard exceeded) share
ex = pd.read_csv(f'{D}caaspp_exceeded.csv', dtype={'cds14':str})
ex['exceeded_pct'] = pd.to_numeric(ex['exceeded_pct'], errors='coerce')
ex['met_above_pct'] = pd.to_numeric(ex['met_above_pct'], errors='coerce')
for y,g in ex.groupby('year'):
    y = int(y)
    g = g.drop_duplicates('cds14').set_index('cds14')
    put('caaspp_l4', y, g['exceeded_pct'])
    # cross-check: met_above_pct in this file vs components' skipna average
    both = g['met_above_pct'].dropna()
    comp = pd.Series(values['caaspp'].get(y, {}))
    j = both.index.intersection(comp.index)
    diff = (both.loc[j] - comp.loc[j]).abs()
    if len(j) and diff.max() > 0.06:
        log(f'WARN caaspp cross-check {y}: max diff {diff.max():.3f} on {len(j)} schools ({int((diff>0.06).sum())} over)')
    else:
        log(f'caaspp cross-check {y}: OK ({len(j)} schools, max diff {0 if not len(j) else diff.max():.3f})')

# ------------------------------------------------------------------
# 3. A-G completion (cleaned): rate = 100 * ag_met_clean / cohort
ag = pd.read_csv(f'{D}ag_eligibility_cleaned.csv', dtype={'cds14':str})
for col in ['year','cohort','ag_met_clean']:
    ag[col] = pd.to_numeric(ag[col], errors='coerce')
ag = ag[(ag['ag_met_clean'].notna()) & (ag['cohort'] >= 10)]
ag['rate'] = 100.0*ag['ag_met_clean']/ag['cohort']
ag = ag[(ag['rate']>=0)&(ag['rate']<=100)]
ag_cohort = {}
for y,g in ag.groupby('year'):
    g = g.drop_duplicates('cds14').set_index('cds14')
    put('ag', int(y), g['rate'])
    for k,v in g['cohort'].items():
        ag_cohort[k] = max(ag_cohort.get(k,0), v)
log(f'A-G years: {sorted(values["ag"].keys())}')

# ------------------------------------------------------------------
# 4. Test-context panel v2: STAR, CAHSEE, AP, SAT, ACT.  display year = year_start + 1 (spring)
cols = ['cds14','year_start','is_high_school','school_name','district_name','county_name','grade_12_enrollment',
        'sat_total_avg','sat_total_composite','sat_pct_both_bench','act_composite_avg','act_pct_ge_21',
        'ap_s1','ap_s2','ap_s3','ap_s4','ap_s5',
        'star_ela_hs_pct_prof_plus','star_math_hs_pct_prof_plus',
        'cahsee_ela_pct_passed_census','cahsee_math_pct_passed_census']
t = pd.read_csv(f'{D}test_context_panel_v2.csv', usecols=cols, dtype={'cds14':str})
t = t[t['is_high_school'] != False]
for c in cols[6:] + ['year_start']:
    t[c] = pd.to_numeric(t[c], errors='coerce')
t = t[t['year_start'].notna()]
t['yr'] = (t['year_start']+1).astype(int)

names_tcp, county_tcp, g12 = {}, {}, {}
for r in t.itertuples():
    if isinstance(r.school_name,str) and r.school_name.strip():
        names_tcp[r.cds14] = r.school_name.strip()
    if isinstance(r.county_name,str) and r.county_name.strip():
        county_tcp[r.cds14] = r.county_name.strip()
    if not np.isnan(r.grade_12_enrollment) and r.grade_12_enrollment>0:
        g12[r.cds14] = r.grade_12_enrollment   # ends at latest year seen (file is year-ordered)

for y,g in t.groupby('yr'):
    y=int(y)
    g = g.drop_duplicates('cds14').set_index('cds14')
    # STAR spring 2003-2013
    if 2003 <= y <= 2013:
        put('star',      y, g[['star_ela_hs_pct_prof_plus','star_math_hs_pct_prof_plus']].mean(axis=1, skipna=True))
        put('star_math', y, g['star_math_hs_pct_prof_plus'])
    # CAHSEE spring 2002-2015 (census column already excludes the voluntary 2001 sitting)
    if 2002 <= y <= 2015:
        cah = g[['cahsee_ela_pct_passed_census','cahsee_math_pct_passed_census']].mean(axis=1, skipna=True)
        if cah.notna().sum()>0:
            put('cahsee', y, cah)
            put('cahsee_math', y, g['cahsee_math_pct_passed_census'])
    # AP spring 1999-2020, require >= 20 exams
    s = g[['ap_s1','ap_s2','ap_s3','ap_s4','ap_s5']]
    tot = s.sum(axis=1, min_count=1)
    ok = tot >= 20
    if ok.sum()>0:
        mean_score = (s['ap_s1']+2*s['ap_s2']+3*s['ap_s3']+4*s['ap_s4']+5*s['ap_s5'])/tot
        put('ap',  y, mean_score.where(ok))
        put('ap3', y, (100.0*(s['ap_s3']+s['ap_s4']+s['ap_s5'])/tot).where(ok))
    # SAT 1600 era: spring 1999-2005; zeros/garbage -> missing
    if 1999 <= y <= 2005:
        v = g['sat_total_avg'].where(g['sat_total_avg']>=400)
        put('sat1600', y, v)
    # SAT 2400 era: spring 2006-2016
    if 2006 <= y <= 2016:
        v = g['sat_total_composite'].where(g['sat_total_composite']>=600)
        put('sat2400', y, v)
    # SAT both benchmarks: spring 2017-2018
    if 2017 <= y <= 2018:
        put('sat_bench', y, g['sat_pct_both_bench'])
    # ACT composite average: spring 1999-2013; ACT >=21 share: 1999-2020
    if 1999 <= y <= 2013:
        put('act_avg', y, g['act_composite_avg'].where(g['act_composite_avg']>=5))
    put('act21', y, g['act_pct_ge_21'])
# prune empty act21 years
values['act21'] = {y:v for y,v in values['act21'].items() if len(v)>0}
log(f'act21 years: {min(values["act21"])}-{max(values["act21"])}')

# ------------------------------------------------------------------
# 5. UC applicant GPA (Universitywide), ceeb -> cds via crosswalk v2.
xw = pd.read_csv(f'{D}ceeb_cds_crosswalk_v2.csv', dtype={'ceeb':str,'cds14':str})
xw = xw[xw['cds14'].notna() & (xw['cds14'].str.len()==14)]
ceeb2cds = dict(zip(xw['ceeb'], xw['cds14']))
uc = pd.read_csv(f'{D}school_campus_year_admitted_denied.csv', dtype={'ceeb':str})
uc = uc[uc['campus']=='Universitywide'].copy()
for c in ['year','applicants','app_gpa']:
    uc[c] = pd.to_numeric(uc[c], errors='coerce')
uc['cds14'] = uc['ceeb'].map(ceeb2cds)
uc = uc[uc['cds14'].notna() & uc['app_gpa'].notna() & (uc['app_gpa']>0) & (uc['app_gpa']<=5)]
# CEEB->CDS collisions: weight by applicants, never drop (pooled-panel trap #2)
uc['w'] = uc['applicants'].fillna(1).clip(lower=1)
coll = uc.groupby(['cds14','year'])['ceeb'].nunique()
log(f'UC GPA: {len(uc)} rows; cds-year cells with >1 CEEB merged: {(coll>1).sum()}')
gg = uc.groupby(['cds14','year']).apply(
    lambda d: np.average(d['app_gpa'], weights=d['w']), include_groups=False)
for y in sorted(uc['year'].unique()):
    y=int(y)
    put('gpa_uc', y, gg.xs(y, level='year'))

# ------------------------------------------------------------------
# 5b. UC admit GPA (Universitywide) + UC enrollee GPA (enrollment-weighted
#     across the nine campuses — each enrollee attends exactly one campus,
#     so the weighted mean IS the systemwide enrollee GPA, no duplication).
ad = pd.read_csv(f'{D}school_campus_year_admitted_denied.csv', dtype={'ceeb':str})
ad = ad[ad['campus']=='Universitywide'].copy()
for c in ['year','admits','adm_gpa']:
    ad[c] = pd.to_numeric(ad[c], errors='coerce')
ad['cds14'] = ad['ceeb'].map(ceeb2cds)
ad = ad[ad['cds14'].notna() & ad['adm_gpa'].notna() & (ad['adm_gpa']>0) & (ad['adm_gpa']<=5)]
ad['w'] = ad['admits'].fillna(1).clip(lower=1)
ga = ad.groupby(['cds14','year']).apply(
    lambda d: np.average(d['adm_gpa'], weights=d['w']), include_groups=False)
for y in sorted(ad['year'].unique()):
    y=int(y)
    put('gpa_uc_adm', y, ga.xs(y, level='year'))
log(f'UC admit GPA: {sum(len(v) for v in values["gpa_uc_adm"].values())} cells, {min(values["gpa_uc_adm"])}-{max(values["gpa_uc_adm"])}')

dv9 = pd.read_csv(f'{D}dv_admissions_all9.csv', usecols=['ceeb','campus','year','enrollees','enr_gpa'],
                  dtype={'ceeb':str})
for c in ['year','enrollees','enr_gpa']:
    dv9[c] = pd.to_numeric(dv9[c], errors='coerce')
dv9 = dv9[dv9['enr_gpa'].notna() & (dv9['enr_gpa']>0) & (dv9['enr_gpa']<=5)
          & dv9['enrollees'].notna() & (dv9['enrollees']>=1)]
per = dv9.groupby(['ceeb','year']).apply(
    lambda d: pd.Series({'g': np.average(d['enr_gpa'], weights=d['enrollees']),
                         'n': float(d['enrollees'].sum())}), include_groups=False).reset_index()
per['cds14'] = per['ceeb'].map(ceeb2cds)
per = per[per['cds14'].notna()]
ge9 = per.groupby(['cds14','year']).apply(
    lambda d: np.average(d['g'], weights=d['n']), include_groups=False)
for y in sorted(per['year'].unique()):
    y=int(y)
    put('gpa_uc_enr', y, ge9.xs(y, level='year'))
log(f'UC enrollee GPA: {sum(len(v) for v in values["gpa_uc_enr"].values())} cells, {min(values["gpa_uc_enr"])}-{max(values["gpa_uc_enr"])}')

# ------------------------------------------------------------------
# 6. CSU freshman HS GPA, school-level = headcount-weighted mean across campuses
csu = pd.read_csv(f'{D}csu_hs_gpa_v3_tidy.csv', dtype={'cds14':str,'ceeb':str})
for c in ['year','headcount','hs_gpa']:
    csu[c] = pd.to_numeric(csu[c], errors='coerce')
csu = csu[csu['hs_gpa'].notna() & csu['headcount'].notna() & csu['cds14'].notna()
          & (csu['cds14'].str.len()==14) & (csu['hs_gpa']>0) & (csu['hs_gpa']<=5)]
csu_n = csu.groupby(['cds14','year'])['headcount'].sum()
csw = csu.groupby(['cds14','year']).apply(
    lambda d: np.average(d['hs_gpa'], weights=d['headcount']), include_groups=False)
for y in sorted(csu['year'].unique()):
    y=int(y)
    put('gpa_csu', y, csw.xs(y, level='year'))
log(f'CSU GPA school-years: {len(csw)}; schools/yr: ' +
    str({int(y): int(csu[csu["year"]==y]["cds14"].nunique()) for y in sorted(csu["year"].unique())}))

# ------------------------------------------------------------------
# 6b. CSU GPA one year later (same file, csu_gpa_1yr; source rounds to 1 dp per cell)
c1 = pd.read_csv(f'{D}csu_hs_gpa_v3_tidy.csv', dtype={'cds14':str,'ceeb':str})
for c in ['year','headcount','csu_gpa_1yr']:
    c1[c] = pd.to_numeric(c1[c], errors='coerce')
c1 = c1[c1['csu_gpa_1yr'].notna() & c1['headcount'].notna() & c1['cds14'].notna()
        & (c1['cds14'].str.len()==14) & (c1['csu_gpa_1yr']>0) & (c1['csu_gpa_1yr']<=4.0)]
g1 = c1.groupby(['cds14','year']).apply(
    lambda d: np.average(d['csu_gpa_1yr'], weights=d['headcount']), include_groups=False)
for y in sorted(c1['year'].unique()):
    y=int(y)
    put('gpa_csu1', y, g1.xs(y, level='year'))
log(f'CSU GPA 1yr: years {sorted(values["gpa_csu1"].keys())}, cells {sum(len(v) for v in values["gpa_csu1"].values())}')

# ------------------------------------------------------------------
# 6c. CSU GE placement at entry (partners dashboard flatten).
#     Systemwide (zz), hs tier via the dash crosswalk, Freshmen, cohorts 2021-2025
#     (2018-20 exist for only ~15 schools - dropped to avoid a misleading sparse view).
#     ready = fulfilled before entry (cat 1) + placed without supported instruction (cat 2).
dxw = pd.read_csv(f'{D}csu_dash_school_crosswalk.csv', dtype={'dash_id':str,'cds14':str})
dxw = dxw[dxw['cds14'].notna() & (dxw['cds14'].str.len()==14)]
dash2cds = dict(zip(dxw['dash_id'], dxw['cds14']))
pl = pd.read_csv(f'{D}csu_placement_by_cohort.csv', dtype={'dash_id':str,'campus_code':str,'value':str})
pl = pl[(pl['school_type']=='hs')&(pl['student_type']=='Freshmen')&(pl['campus_code']=='zz')]
pl = pl[pl['metric'].isin(['nEnrolled','nMpr1','nMpr2','nWc1','nWc2'])]
pl['value'] = pd.to_numeric(pl['value'], errors='coerce')
pl['cds14'] = pl['dash_id'].map(dash2cds)
pl = pl[pl['cds14'].notna() & pl['cohort'].between(2021,2025)]
w = pl.pivot_table(index=['cds14','cohort'], columns='metric', values='value', aggfunc='sum')
w = w[w['nEnrolled'].fillna(0) >= 10]
w['math_ready'] = 100.0*(w['nMpr1'].fillna(0)+w['nMpr2'].fillna(0))/w['nEnrolled']
w['wc_ready']   = 100.0*(w['nWc1'].fillna(0)+w['nWc2'].fillna(0))/w['nEnrolled']
w = w[(w['math_ready']<=100.5)&(w['wc_ready']<=100.5)]
w['math_ready'] = w['math_ready'].clip(upper=100); w['wc_ready'] = w['wc_ready'].clip(upper=100)
for y in sorted({c for _,c in w.index}):
    y=int(y)
    put('csu_math_ready', y, w.xs(y, level='cohort')['math_ready'])
    put('csu_wc_ready',   y, w.xs(y, level='cohort')['wc_ready'])
log(f'CSU placement: cells math {sum(len(v) for v in values["csu_math_ready"].values())}, years {sorted(values["csu_math_ready"].keys())}')

# ------------------------------------------------------------------
# 6d. UC ELWR satisfied at entry (UC enrollees), CEEB-keyed, 1994-2025
el = pd.read_csv(f'{D}elwr_school_year_wide.csv', dtype={'school_code':str})
for c in ['academic_year','pct_enrolled_met_requirement','enrolled']:
    el[c] = pd.to_numeric(el[c], errors='coerce')
el['cds14'] = el['school_code'].map(ceeb2cds)
el = el[el['cds14'].notna() & el['pct_enrolled_met_requirement'].notna()
        & el['pct_enrolled_met_requirement'].between(0,100)]
el['w'] = el['enrolled'].fillna(1).clip(lower=1)
ge = el.groupby(['cds14','academic_year']).apply(
    lambda d: np.average(d['pct_enrolled_met_requirement'], weights=d['w']), include_groups=False)
for y in sorted(el['academic_year'].unique()):
    y=int(y)
    put('elwr', y, ge.xs(y, level='academic_year'))
log(f'ELWR: {sum(len(v) for v in values["elwr"].values())} cells, {min(values["elwr"])}-{max(values["elwr"])}')

# ------------------------------------------------------------------
# 6e. UC systemwide retention / graduation by entering class (school_year_wide)
sy = pd.read_csv(f'{D}school_year_wide.csv',
                 usecols=['ceeb','cds14','year','uc_enrollees','uc_retention_1yr','uc_grad_4yr','uc_grad_6yr'],
                 dtype={'ceeb':str,'cds14':str})
for c in ['year','uc_enrollees','uc_retention_1yr','uc_grad_4yr','uc_grad_6yr']:
    sy[c] = pd.to_numeric(sy[c], errors='coerce')
sy = sy[sy['cds14'].notna() & (sy['cds14'].str.len()==14)]
sy['w'] = sy['uc_enrollees'].fillna(1).clip(lower=1)
for mid, col, ylo, yhi in [('uc_ret1','uc_retention_1yr',1999,2024),
                           ('uc_grad4','uc_grad_4yr',1999,2021),
                           ('uc_grad6','uc_grad_6yr',1999,2019)]:
    d = sy[sy[col].notna() & sy[col].between(0,100) & sy['year'].between(ylo,yhi)]
    gg2 = d.groupby(['cds14','year']).apply(
        lambda dd: np.average(dd[col], weights=dd['w']), include_groups=False)
    for y in sorted(d['year'].unique()):
        y=int(y)
        put(mid, y, gg2.xs(y, level='year'))
    log(f'{mid}: {sum(len(v) for v in values[mid].values())} cells, {min(values[mid])}-{max(values[mid])}')

# ------------------------------------------------------------------
# 7. Names / county / size registries
spine = pd.read_csv(f'{D}census_achievement_spine.csv',
                    usecols=['cds14','school_name','year_start'], dtype={'cds14':str})
spine = spine.sort_values('year_start')
names_spine = {r.cds14: r.school_name for r in spine.itertuples()
               if isinstance(r.school_name,str) and r.school_name.strip()}

hist = pd.read_csv(f'{D}historical_school_name_cds_lookup.csv', dtype={'cds14':str})
names_hist, county_hist = {}, {}
for r in hist.itertuples():
    if isinstance(r.school_name,str) and r.school_name.strip():
        names_hist.setdefault(r.cds14, r.school_name.strip())
    if isinstance(r.county_name,str) and r.county_name.strip():
        county_hist.setdefault(r.cds14, r.county_name.strip())

names_csu, county_csu = {}, {}
for r in csu.drop_duplicates('cds14').itertuples():
    nm = r.school
    if isinstance(nm,str):
        nm = nm.split(',')[0].strip()
        names_csu[r.cds14] = nm
    if isinstance(r.county,str): county_csu[r.cds14] = r.county.strip()

# dv names (uppercase) keyed by ceeb -> cds
dv = pd.read_csv(f'{D}dv_admissions_all9.csv', usecols=['ceeb','school_name','county'],
                 dtype={'ceeb':str}).drop_duplicates('ceeb')
names_dv, county_dv = {}, {}
for r in dv.itertuples():
    cds = ceeb2cds.get(r.ceeb)
    if cds:
        if isinstance(r.school_name,str): names_dv.setdefault(cds, r.school_name.strip())
        if isinstance(r.county,str): county_dv.setdefault(cds, r.county.strip())

# size: enroll_9_12 / 4 (latest), fallbacks g12, caaspp n, ag cohort
syw = pd.read_csv(f'{D}school_year_wide.csv', usecols=['cds14','year','enroll_9_12'],
                  dtype={'cds14':str})
syw['enroll_9_12'] = pd.to_numeric(syw['enroll_9_12'], errors='coerce')
syw = syw[syw['cds14'].notna() & syw['enroll_9_12'].notna()].sort_values('year')
enroll = {r.cds14: r.enroll_9_12 for r in syw.itertuples()}   # last (latest) wins

def titlecase(s):
    small={'of','the','and','at','for','in','on','del','de','la','los','las'}
    out=[]
    for i,w in enumerate(s.lower().split()):
        out.append(w if (w in small and i>0) else w.capitalize())
    return ' '.join(out)

# ------------------------------------------------------------------
# 8. Assemble universe + encode
all_cds = set()
for mid in values:
    for y in values[mid]:
        all_cds.update(values[mid][y].keys())
all_cds = {c for c in all_cds if isinstance(c,str) and len(c)==14}
log(f'universe: {len(all_cds)} schools')

def get_name(c):
    for src in (names_spine, names_csu, names_tcp, names_hist, names_dv):
        if c in src:
            n = src[c]
            if n.isupper(): n = titlecase(n)
            return n
    return 'School ' + c

def get_county(c):
    for src in (county_tcp, county_csu, county_hist, county_dv):
        if c in src:
            n=src[c]
            return titlecase(n) if n.isupper() else n
    return ''

def get_size(c):
    if c in enroll and enroll[c]>0: return int(round(enroll[c]/4.0))
    if c in g12 and g12[c]>0: return int(round(g12[c]))
    if c in caaspp_n and caaspp_n[c]>0: return int(round(caaspp_n[c]))
    if c in ag_cohort and ag_cohort[c]>0: return int(round(ag_cohort[c]))
    return 0

rows = sorted(all_cds)
names = [get_name(c) for c in rows]
counties = [get_county(c) for c in rows]
sizes = [get_size(c) for c in rows]
# disambiguate duplicate display names with county (then cds tail)
from collections import Counter
cnt = Counter(names)
disp = []
seen = Counter()
for n,co,c in zip(names,counties,rows):
    if cnt[n]>1:
        n2 = f'{n} ({co})' if co else n
        disp.append(n2)
    else:
        disp.append(n)
cnt2 = Counter(disp)
for i,(n,c) in enumerate(zip(disp,rows)):
    if cnt2[n]>1:
        seen[n]+=1
        disp[i] = f'{n} [{seen[n]}]'
idx = {c:i for i,c in enumerate(rows)}

MDEF = {  # dec = decimals kept
 'gpa_csu':2, 'gpa_uc':2, 'caaspp':1, 'caaspp_math':1, 'caaspp_ela':1,
 'ag':1, 'star':1, 'star_math':1, 'cahsee':1, 'cahsee_math':1,
 'ap':2, 'ap3':1, 'caaspp_l4':1, 'caaspp_dfs':0,
 'sat1600':0, 'sat2400':0, 'sat_bench':1, 'act_avg':1, 'act21':1,
 'gpa_uc_adm':2, 'gpa_uc_enr':2,
 'gpa_csu1':2, 'csu_math_ready':1, 'csu_wc_ready':1, 'elwr':1,
 'uc_ret1':1, 'uc_grad4':1, 'uc_grad6':1,
}
panel_measures = {}
total_cells = 0
for mid, dec in MDEF.items():
    yrs = sorted(values[mid].keys())
    y0, y1 = yrs[0], yrs[-1]
    scale = 10**dec
    rows_out = []
    n_present = 0
    for y in range(y0, y1+1):
        vy = values[mid].get(y, {})
        enc = []
        for c in rows:
            v = vy.get(c)
            if v is None or (isinstance(v,float) and np.isnan(v)):
                enc.append('')
            else:
                enc.append(str(int(round(v*scale))))
                n_present += 1
        rows_out.append(','.join(enc))
    panel_measures[mid] = {'y0':y0,'y1':y1,'dec':dec,'rows':rows_out}
    total_cells += n_present
    cover = {y: len(values[mid][y]) for y in yrs}
    log(f'{mid:12s} {y0}-{y1}  cells={n_present:7d}  per-year min/max = {min(cover.values())}/{max(cover.values())}')
log(f'total cells: {total_cells}')

PANEL = {'names':disp,'sizes':sizes,'m':panel_measures}
js = 'var PANEL=' + json.dumps(PANEL, separators=(',',':'), ensure_ascii=False) + ';\n'
with open(OUT_JS,'w',encoding='utf-8') as f:
    f.write(js)
log(f'wrote {OUT_JS}: {len(js)/1e6:.2f} MB')
with open('panel_report.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(report))
