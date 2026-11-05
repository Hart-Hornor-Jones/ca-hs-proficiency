#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge the six measures built by extend_panel_levels_gap_ucsd.py
(new_levels_gap_ucsd_values.json) into data/panel_long.csv, data/panel_wide.csv,
data/measures.csv and index.html - the PANEL data blob, the page's measure
menus (MEASURES, MEASURE_ORDER, FAM_OF, FAMS, UNIT_NAMES) and its data footnote.

Before writing anything the script snapshots every existing measure (its long
rows, dictionary row, PANEL blob entry and MEASURES menu entry) and, after
writing, re-reads the files and asserts that all of them are reproduced exactly.
tests/check_measures_unchanged.py runs the same comparison against a git
baseline on the committed files.

Safe to re-run: every step removes what an earlier run added before adding it
again. Run from the build/ folder."""
import json
import os
import re
import pandas as pd

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + os.sep
vals = json.load(open('new_levels_gap_ucsd_values.json', encoding='utf-8'))['years']

DEC = {'caaspp_math_l4': 1, 'caaspp_math_l1': 1, 'caaspp_math_l4_sed': 1, 'caaspp_math_l4_notsed': 1,
       'caaspp_math_gap_sed': 2, 'ucsd_adv': 1}
NEW_IDS = list(DEC)
assert set(vals) == set(NEW_IDS), sorted(vals)

# ---- measures.csv rows: (id, label, group, unit, description, source)
META = [
 ('caaspp_math_l4', 'CAASPP Math Level 4 share', 'High-school measure', 'percent',
  "Share of the school's grade-11 students scoring Standard Exceeded (Level 4, the top of four levels) on the CAASPP mathematics test, all students. Census test. As published: whole numbers in 2015-16, one decimal afterwards; blank where the state suppressed the result (fewer than 11 students). Available 2015-25; not given in 2020, and 2021 participation was far below normal.",
  'CAASPP research files (CDE), via Hart-Hornor-Jones/ca-sbac-math-levels school_levels_grade11_math.csv (group 1)'),
 ('caaspp_math_l1', 'CAASPP Math Level 1 share', 'High-school measure', 'percent',
  "Share of the school's grade-11 students scoring Standard Not Met (Level 1, the lowest of four levels) on the CAASPP mathematics test, all students. The bottom of the distribution, where the met-or-above bar says nothing. Same source, rounding and suppression as caaspp_math_l4. Available 2015-25; not given in 2020.",
  'CAASPP research files (CDE), via Hart-Hornor-Jones/ca-sbac-math-levels school_levels_grade11_math.csv (group 1)'),
 ('caaspp_math_l4_sed', 'CAASPP Math Level 4 share - socioeconomically disadvantaged', 'High-school measure', 'percent',
  "Share of the school's socioeconomically disadvantaged grade-11 students (CDE student group 31: eligible for free or reduced-price meals, parents without a high-school diploma, or migrant, homeless or foster youth) scoring Level 4 on the CAASPP mathematics test. Blank where the group had fewer than 11 students with scores. The group's definition widened in 2022-23. Available 2015-25; not given in 2020.",
  'CAASPP research files (CDE), via Hart-Hornor-Jones/ca-sbac-math-levels school_levels_grade11_math.csv (group 31)'),
 ('caaspp_math_l4_notsed', 'CAASPP Math Level 4 share - not socioeconomically disadvantaged', 'High-school measure', 'percent',
  "Share of the school's grade-11 students who are not socioeconomically disadvantaged (CDE student group 111, the complement of group 31) scoring Level 4 on the CAASPP mathematics test. Blank where the group had fewer than 11 students with scores, which hides it at many high-need schools. Available 2015-25; not given in 2020.",
  'CAASPP research files (CDE), via Hart-Hornor-Jones/ca-sbac-math-levels school_levels_grade11_math.csv (group 111)'),
 ('caaspp_math_gap_sed', 'CAASPP Math met-or-above gap by economic status', 'High-school measure', 'percentage points (difference)',
  "Within the school: the share of not-socioeconomically-disadvantaged grade-11 students scoring Standard Met or better on the CAASPP mathematics test minus the same share among socioeconomically disadvantaged students, in percentage points. Positive means the non-disadvantaged students scored higher. Blank whenever either group is suppressed (fewer than 11 students), so it appears only at schools with a sizeable number of each. Computed from the two published shares with no rounding beyond the source's. Available 2015-25; not given in 2020.",
  'CAASPP research files (CDE), via Hart-Hornor-Jones/caaspp-economic-status schools_by_economic_status.csv (math, grade 11)'),
 ('ucsd_adv', 'UCSD admit rate minus expected', 'Application behavior', 'percentage points (difference)',
  "The share of the school's freshman applicants to UC San Diego who were admitted that fall, minus the admit rate predicted for the school from its mean UCSD-applicant GPA (a binomial fit of admits on a cubic in mean applicant GPA, estimated each year on schools outside San Diego and Imperial counties). Positive means more of the school's applicants were admitted than its applicants' GPAs would predict - the measure built to show UCSD's local-preference eras. Where two UC school codes share one CDS code in a year the two values are averaged, weighted by applicants. Year = the fall of admission, the same class of seniors as the UC GPA measures. Available 1994-2025.",
  "UC admissions-by-school data, via Hart-Hornor-Jones/ucsd-local-preference panel_long.csv (measure ucsd_adv, 'UCSD admit rate minus predicted (from GPA)')"),
]


def q(mid, v):
    return int(round(float(v) * 10 ** DEC[mid])) / 10 ** DEC[mid]


def years_of(mid):
    ys = sorted(int(y) for y in vals[mid])
    skip = [y for y in range(ys[0], ys[-1] + 1) if y not in ys]
    return ys[0], ys[-1], skip


def js_entries(h):
    """id -> the full text of its MEASURES entry."""
    return {m.group(1): m.group(0) for m in re.finditer(r" \{id:'([a-z0-9_]+)',.*?\},?\n", h, flags=re.S)}


schools = pd.read_csv(REPO + 'data/schools.csv', dtype={'cds14': str})

# ------------------------------------------------------------------ snapshot of what exists
long_before = pd.read_csv(REPO + 'data/panel_long.csv', dtype=str, keep_default_na=False)
long_before = long_before[~long_before['measure'].isin(NEW_IDS)]
ms_before = pd.read_csv(REPO + 'data/measures.csv', dtype=str, keep_default_na=False)
ms_before = ms_before[~ms_before['measure'].isin(NEW_IDS)]
h0 = open(REPO + 'index.html', encoding='utf-8').read()
i0 = h0.find('var PANEL='); j0 = h0.find(';\n', i0)
PANEL0 = json.loads(h0[i0 + len('var PANEL='):j0])
blob_before = {k: v for k, v in PANEL0['m'].items() if k not in NEW_IDS}
entries_before = {k: v for k, v in js_entries(h0[j0:]).items() if k not in NEW_IDS}
EXISTING = sorted(ms_before['measure'])
print('existing measures snapshotted: %d (%d by year in panel_long, %d menu entries, %d blob entries)'
      % (len(EXISTING), long_before['measure'].nunique(), len(entries_before), len(blob_before)))

# ------------------------------------------------------------------ long
long_df = pd.read_csv(REPO + 'data/panel_long.csv', dtype={'cds14': str})
long_df = long_df[~long_df['measure'].isin(NEW_IDS)]
rows = []
for mid in NEW_IDS:
    for y in sorted(vals[mid], key=int):
        for cds, v in vals[mid][y].items():
            rows.append((cds, int(y), mid, q(mid, v)))
nr = pd.DataFrame(rows, columns=['cds14', 'year', 'measure', 'value'])
assert nr['cds14'].isin(set(schools['cds14'])).all()
allx = pd.concat([long_df, nr], ignore_index=True)
BASE = list(pd.unique(long_df['measure']))
ORDER = BASE + NEW_IDS
allx['mo'] = allx['measure'].map({m: i for i, m in enumerate(ORDER)})
assert allx['mo'].notna().all(), 'unknown measure id'
allx = allx.sort_values(['mo', 'year', 'cds14']).drop(columns='mo')
assert not allx.duplicated(['cds14', 'year', 'measure']).any()
allx.to_csv(REPO + 'data/panel_long.csv', index=False)
print('panel_long.csv:', len(allx), 'rows (+%d)' % len(nr))

# ------------------------------------------------------------------ wide
wide = allx.pivot_table(index=['cds14', 'year'], columns='measure', values='value', aggfunc='first').reset_index()
wide = wide.merge(schools[['cds14', 'school_name', 'county']], on='cds14', how='left')
wide = wide[['cds14', 'school_name', 'county', 'year'] + ORDER]
wide = wide.sort_values(['cds14', 'year'])
wide.to_csv(REPO + 'data/panel_wide.csv', index=False)
print('panel_wide.csv:', len(wide), 'rows x', len(wide.columns), 'cols')

# ------------------------------------------------------------------ measures.csv
ms = pd.read_csv(REPO + 'data/measures.csv')
ms = ms[~ms['measure'].isin(NEW_IDS)]
add = []
for mid, label, group, unit, desc, source in META:
    y0, y1, _ = years_of(mid)
    add.append({'measure': mid, 'label': label, 'group': group, 'unit': unit, 'decimals': DEC[mid],
                'first_year': y0, 'last_year': y1, 'n_values': sum(len(v) for v in vals[mid].values()),
                'description': desc, 'source': source})
ms = pd.concat([ms, pd.DataFrame(add)], ignore_index=True)
ms.to_csv(REPO + 'data/measures.csv', index=False)
print('measures.csv:', len(ms), 'measures')

# ------------------------------------------------------------------ index.html: PANEL blob
h = h0
i = h.find('var PANEL=')
j = h.find(';\n', i)
PANEL = json.loads(h[i + len('var PANEL='):j])
cds_order = list(schools['cds14'])
idx = {c: k for k, c in enumerate(cds_order)}
assert len(PANEL['names']) == len(cds_order)
for mid in NEW_IDS:
    y0, y1, _ = years_of(mid)
    dec = DEC[mid]
    out = []
    for y in range(y0, y1 + 1):
        enc = [''] * len(cds_order)
        for cds, v in vals[mid].get(str(y), {}).items():
            enc[idx[cds]] = str(int(round(float(v) * 10 ** dec)))
        out.append(','.join(enc))
    PANEL['m'][mid] = {'y0': y0, 'y1': y1, 'dec': dec, 'rows': out}
newblob = 'var PANEL=' + json.dumps(PANEL, separators=(',', ':'), ensure_ascii=False)
h = h[:i] + newblob + h[j:]

# ------------------------------------------------------------------ index.html: measure menus
def js_entry(mid, adv, grp, unit, label, axis, desc):
    y0, y1, skip = years_of(mid)
    g = (" grp:'%s'," % grp) if grp else ''
    return (" {id:'%s', adv:%s,%s unit:'%s', dec:%d, y0:%d, y1:%d, skip:[%s],\n  label:'%s',\n  axis:'%s',\n  desc:'%s'},\n"
            % (mid, 'true' if adv else 'false', g, unit, DEC[mid], y0, y1, ','.join(map(str, skip)),
               label.replace("'", "’"), axis.replace("'", "’"), desc.replace("'", "’")))

CAASPP_ENTRIES = (
 js_entry('caaspp_math_l4', True, None, 'pct', 'CAASPP Math Level 4 share',
  'CAASPP Math % Standard Exceeded (Level 4)',
  'The share of the school’s grade-11 students scoring “Standard Exceeded” — the top of CAASPP’s four levels — on the mathematics test, all students. Separates high-scoring schools much more sharply than the met-or-exceeded bar; the ELA+Math version is under “CAASPP Level 4 share”. As published by the state (whole numbers in 2015–16, one decimal afterwards), blank where fewer than 11 students had scores. Available 2015–25; not given in 2020, and 2021 participation was far below normal.') +
 js_entry('caaspp_math_l1', True, None, 'pct', 'CAASPP Math Level 1 share',
  'CAASPP Math % Standard Not Met (Level 1)',
  'The share of the school’s grade-11 students scoring “Standard Not Met” — the lowest of CAASPP’s four levels — on the mathematics test, all students. This reads the bottom of the distribution, where the met-or-exceeded bar says nothing; a high value means many students far below standard. Same source, rounding and suppression as the Level 4 share. Available 2015–25; not given in 2020.') +
 js_entry('caaspp_math_l4_sed', True, None, 'pct', 'CAASPP Math Level 4 — disadvantaged students',
  'CAASPP Math % at Level 4, socioeconomically disadvantaged students',
  'Among the school’s grade-11 students the state classes as socioeconomically disadvantaged (eligible for free or reduced-price meals, parents without a high-school diploma, or migrant, homeless or foster youth), the share scoring Level 4 on the CAASPP mathematics test. Blank where the group had fewer than 11 students with scores. The state widened the group’s definition in 2022–23. Available 2015–25; not given in 2020.') +
 js_entry('caaspp_math_l4_notsed', True, None, 'pct', 'CAASPP Math Level 4 — not disadvantaged',
  'CAASPP Math % at Level 4, students not socioeconomically disadvantaged',
  'Among the school’s grade-11 students who are not classed as socioeconomically disadvantaged, the share scoring Level 4 on the CAASPP mathematics test. Blank where the group had fewer than 11 students with scores, which hides it at many high-need schools. Put this on one axis and the disadvantaged-students share on the other to see how far the two groups sit apart within the same school. Available 2015–25; not given in 2020.') +
 js_entry('caaspp_math_gap_sed', True, None, 'pctd', 'CAASPP Math gap by economic status',
  'CAASPP Math % met: not disadvantaged − disadvantaged (points)',
  'Within the school: the share of not-disadvantaged grade-11 students scoring “Standard Met” or better on the CAASPP mathematics test minus the same share among socioeconomically disadvantaged students, in percentage points. Positive means the non-disadvantaged students scored higher; the statewide figure runs around 25–30 points, and most schools sit well below that because the two groups within one school are more alike than the two groups statewide. Blank whenever either group is suppressed (fewer than 11 students), so it appears only at schools with a sizeable number of each. Available 2015–25; not given in 2020.')
)
UCSD_ENTRIES = (
 js_entry('ucsd_adv', True, None, 'pctd', 'UCSD admit rate minus expected',
  'UCSD admit rate − rate expected from applicant GPA (points)',
  'Of the school’s freshman applicants to UC San Diego, the share admitted that fall, minus the admit rate predicted for the school from its applicants’ mean GPA — a binomial fit of admits on a cubic in mean applicant GPA, estimated each year on schools outside San Diego and Imperial counties. Positive means UCSD admitted more of the school’s applicants than their GPAs alone would predict. Built to show UCSD’s local-preference eras: the local schools sit above zero in 1997–98, in 1999–2004 for the low-proficiency schools the Local 4% Plan bound, in 2018–21 broadly, and in 2022–24 for Sweetwater and Imperial County, and below it in 2005–10. Schools with UCSD applicants only. The year is the fall of admission, the same class of seniors as the UC GPA measures. Available 1994–2025.')
)

# remove entries from an earlier run, then insert
h = re.sub(r" \{id:'(%s)',.*?\},\n" % '|'.join(NEW_IDS), '', h, flags=re.S)
dfs_entry = re.search(r" \{id:'caaspp_dfs',.*?\},\n", h, flags=re.S)
assert dfs_entry
h = h[:dfs_entry.end()] + CAASPP_ENTRIES + h[dfs_entry.end():]
mark_out = ' /* -------- college outcomes (what happened after enrollment) -------- */\n'
assert h.count(mark_out) == 1
h = h.replace(mark_out, UCSD_ENTRIES + mark_out)

# MEASURE_ORDER (edit only inside the array)
a = h.index('var MEASURE_ORDER=['); b = h.index('];', a)
mo = h[a:b]
for mid in NEW_IDS:
    mo = mo.replace("'%s'," % mid, '')
assert mo.count("'caaspp_l4','caaspp_dfs',") == 1 and mo.count("'csu_asd_ftf',") == 1
mo = mo.replace("'caaspp_l4','caaspp_dfs',",
                "'caaspp_l4','caaspp_dfs','caaspp_math_l4','caaspp_math_l1','caaspp_math_l4_sed','caaspp_math_l4_notsed','caaspp_math_gap_sed',")
mo = mo.replace("'csu_asd_ftf',", "'csu_asd_ftf','ucsd_adv',")
for mid in NEW_IDS:
    assert mo.count("'%s'," % mid) == 1, mid
h = h[:a] + mo + h[b:]

# FAM_OF
h = re.sub(r"caaspp_math_l4:'caaspp',caaspp_math_l1:'caaspp',caaspp_math_l4_sed:'caaspp',caaspp_math_l4_notsed:'caaspp',caaspp_math_gap_sed:'caaspp',|ucsd_adv:'ucsd',", '', h)
old = " caaspp:'caaspp',caaspp_ela:'caaspp',caaspp_math:'caaspp',caaspp_l4:'caaspp',caaspp_dfs:'caaspp',"
assert h.count(old) == 1
h = h.replace(old, old + "caaspp_math_l4:'caaspp',caaspp_math_l1:'caaspp',caaspp_math_l4_sed:'caaspp',caaspp_math_l4_notsed:'caaspp',caaspp_math_gap_sed:'caaspp',")
old = "uc_apps_per_applicant:'appbeh',csu_asd_ftf:'appbeh',"
assert h.count(old) == 1
h = h.replace(old, old + "ucsd_adv:'ucsd',")
# FAMS: a UC San Diego family after application behavior
h = h.replace(",\n {k:'ucsd',   label:'UC San Diego admissions'}\n", '\n')
old = " {k:'appbeh', label:'Application behavior'}\n"
assert h.count(old) == 1
h = h.replace(old, " {k:'appbeh', label:'Application behavior'},\n {k:'ucsd',   label:'UC San Diego admissions'}\n")
assert h.count("k:'ucsd'") == 1
# UNIT_NAMES: a percentage-point difference (so the equality line and residual readings name it correctly)
h = h.replace(", pctd:'percentage points (already a difference)'", '')
old = "gpad:'GPA points (already a difference)',"
assert h.count(old) == 1
h = h.replace(old, old + " pctd:'percentage points (already a difference)',")

# data footnote
OLD = 'and National Merit semifinalist counts from NMSC’s California press releases for the classes of 2016, 2018, 2020 and 2022.'
NEW = ('National Merit semifinalist counts from NMSC’s California press releases for the classes of 2016, 2018, 2020 and 2022; '
       'the CAASPP mathematics achievement-level shares (all students and by economic status) and the within-school gap by economic status, '
       'from the state’s research files as released in the ca-sbac-math-levels and caaspp-economic-status repositories; '
       'and UC San Diego’s admit rate against the rate expected from applicant GPA, from the ucsd-local-preference repository’s panel.')
if NEW not in h:
    assert h.count(OLD) == 1
    h = h.replace(OLD, NEW)

open(REPO + 'index.html', 'w', encoding='utf-8').write(h)
print('index.html: PANEL has %d measures; page %.2f MB' % (len(PANEL['m']), len(h) / 1e6))

# ------------------------------------------------------------------ cross-checks
chk = nr.sample(400, random_state=5)
bad = 0
for r in chk.itertuples():
    m = PANEL['m'][r.measure]
    e = m['rows'][r.year - m['y0']].split(',')[idx[r.cds14]]
    if e == '' or abs(int(e) / 10 ** m['dec'] - r.value) > 1e-9: bad += 1
print('blob vs long spot-check: %d/400 mismatches' % bad)
assert bad == 0
for mid in NEW_IDS:
    assert h.count("{id:'%s'," % mid) == 1, mid

# ------------------------------------------------------------------ every existing measure reproduced exactly
long_after = pd.read_csv(REPO + 'data/panel_long.csv', dtype=str, keep_default_na=False)
long_after = long_after[~long_after['measure'].isin(NEW_IDS)]
key = ['measure', 'year', 'cds14']
a_ = long_before.sort_values(key).reset_index(drop=True)
b_ = long_after.sort_values(key).reset_index(drop=True)
assert a_.equals(b_), 'panel_long.csv: existing measures changed'
ms_after = pd.read_csv(REPO + 'data/measures.csv', dtype=str, keep_default_na=False)
ms_after = ms_after[~ms_after['measure'].isin(NEW_IDS)].reset_index(drop=True)
assert ms_before.reset_index(drop=True).equals(ms_after), 'measures.csv: existing rows changed'
h1 = open(REPO + 'index.html', encoding='utf-8').read()
i1 = h1.find('var PANEL='); j1 = h1.find(';\n', i1)
PANEL1 = json.loads(h1[i1 + len('var PANEL='):j1])
assert PANEL1['names'] == PANEL0['names'] and PANEL1['sizes'] == PANEL0['sizes']
assert {k: v for k, v in PANEL1['m'].items() if k not in NEW_IDS} == blob_before, 'PANEL blob: existing entries changed'
entries_after = {k: v for k, v in js_entries(h1[j1:]).items() if k not in NEW_IDS}
assert entries_after == entries_before, 'MEASURES menu: existing entries changed'
wide_after = pd.read_csv(REPO + 'data/panel_wide.csv', dtype={'cds14': str})
pv = long_after.assign(value=long_after['value'].astype(float), year=long_after['year'].astype(int)) \
    .pivot(index=['cds14', 'year'], columns='measure', values='value')
EXISTING_BY_YEAR = [m for m in EXISTING if m in pv.columns]
wa = wide_after.set_index(['cds14', 'year'])[EXISTING_BY_YEAR]
pv = pv.reindex(index=wa.index, columns=wa.columns)
assert ((pv.to_numpy() == wa.to_numpy()) | (pv.isna().to_numpy() & wa.isna().to_numpy())).all(), 'panel_wide.csv: existing columns changed'
print('existing measures reproduced exactly: %d dictionary rows, %d by-year measures (%d long rows), %d blob entries, %d menu entries'
      % (len(ms_before), len(EXISTING_BY_YEAR), len(long_before), len(blob_before), len(entries_before)))

# plausibility: same-year correlations with existing measures
w = wide_after
def corr(a, b, ya, yb):
    x = w.loc[w.year == ya, ['cds14', a]].dropna().merge(w.loc[w.year == yb, ['cds14', b]].dropna(), on='cds14')
    return len(x), x[a].corr(x[b])
for a, b, ya, yb in [('caaspp_math_l4', 'caaspp_l4', 2019, 2019), ('caaspp_math_l4', 'caaspp_math', 2024, 2024),
                     ('caaspp_math_l1', 'caaspp_math', 2024, 2024), ('caaspp_math_l4_sed', 'caaspp_math_l4_notsed', 2024, 2024),
                     ('caaspp_math_gap_sed', 'ctx_sed', 2024, 2024), ('ucsd_adv', 'gpa_ucsel_adm', 2020, 2020)]:
    n, r = corr(a, b, ya, yb)
    print('  r(%s %d, %s %d) = %.2f on %d schools' % (a, ya, b, yb, r, n))
