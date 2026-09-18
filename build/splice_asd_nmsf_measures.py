#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge the CSU archived-report measures and the National Merit measures
(new_asd_nmsf_values.json, from extend_panel_csu_asd_nmsf.py) into the data CSVs
and into index.html - both the PANEL data blob and the page's measure menus
(MEASURES, MEASURE_ORDER, FAM_OF, FAMS, UNIT_NAMES) and its data footnote.

Safe to re-run: every step removes what an earlier run added before adding it
again. Run from the build/ folder."""
import json
import os
import re
import pandas as pd

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..') + os.sep
vals = json.load(open('new_asd_nmsf_values.json', encoding='utf-8'))['years']

DEC = {'gpa_csu_asd': 2, 'sat_csu_asd': 0, 'csu_math_ready_asd': 1, 'csu_wc_ready_asd': 1,
       'csu_ret1_asd': 1, 'gpa_csu1_asd': 2, 'csu_asd_ftf': 0, 'nmsf': 0, 'nmsf_rate': 2}
NEW_IDS = list(DEC)

# ---- measures.csv rows: (id, label, group, unit, description, source)
META = [
 ('gpa_csu_asd', 'HS GPA - CSU freshmen (archived reports)', 'High-school measure', 'GPA (a-g)',
  "Average high-school GPA of the school's graduates who entered CSU as regularly admitted first-time freshmen that fall, from CSU's archived school-by-school reports (asd.calstate.edu, recovered from the Internet Archive). The older counterpart of gpa_csu. Shown when at least 10 students were reported. Fall 1995-97 for most schools; a few dozen schools in 1999-2000.",
  'CSU Analytic Studies school reports (Wayback Machine), Table 3'),
 ('sat_csu_asd', 'SAT total - CSU freshmen (1600 scale)', 'High-school measure', 'points, 400-1600',
  "Average SAT verbal + math total of the school's regularly admitted CSU freshmen, on the pre-2006 1600-point scale, from the archived CSU reports. The pool is students who went to CSU, not all test takers. Shown when at least 10 students were reported. Fall 1995-97 (a few schools 1999-2000).",
  'CSU Analytic Studies school reports (Wayback Machine), Table 3'),
 ('csu_asd_ftf', 'Freshmen entering CSU (archived reports)', 'Application behavior', 'students',
  "Number of the school's graduates who entered a CSU campus as regularly admitted first-time freshmen that fall, from the archived CSU reports (Table 1 through 1997; the ELM/EPT summary pages afterwards). A raw count. Fall 1995-2001, 2005-07, 2009, 2013, 2015-17; most schools appear only through 2005.",
  'CSU Analytic Studies school reports (Wayback Machine)'),
 ('nmsf', 'National Merit semifinalists', 'High-school measure', 'students',
  "Number of the school's seniors named National Merit semifinalists (about the top 0.5% of PSAT takers in the state, by a California cutoff score on the PSAT taken in October of junior year), counted from NMSC's California press-release lists. Schools not on the list are 0 when they had grade-11 CAASPP results that year (2019 stands in for 2020). Classes of 2016, 2018, 2020, 2022 only. The class of 2022 took the PSAT in October 2020, when many public schools were closed and could not give it.",
  'National Merit Scholarship Corporation semifinalist press releases (California), parsed from PDF'),
 ('nmsf_rate', 'National Merit semifinalists per 100 students', 'High-school measure', 'per 100 students in a grade',
  "The semifinalist count divided by the school's approximate students per grade (schools.csv), times 100. Schools under 20 students per grade hidden. Same source and caveats as nmsf.",
  'NMSC semifinalist lists / CDE enrollment'),
 ('gpa_csu1_asd', 'CSU GPA one year after entry (archived reports)', 'College outcome', 'GPA',
  "Average CSU GPA after one year for the school's regularly admitted CSU freshmen, from the archived CSU reports (Table 6). The older counterpart of gpa_csu1. School-years with fewer than 10 freshmen hidden. Fall 1995-97 entering classes (a few schools 1999-2000).",
  'CSU Analytic Studies school reports (Wayback Machine), Table 6'),
 ('csu_math_ready_asd', 'Math proficiency at CSU entry (ELM era)', 'College outcome', 'percent',
  "Share of the school's regularly admitted CSU freshmen who did not need remedial math at entry: exempt from the Entry Level Mathematics test by test score or passed it. 100 minus the published percent not proficient. The ancestor of csu_math_ready under CSU's old placement rules (the ELM scale and passing score changed in 2002). Fewer than 10 freshmen hidden. Fall 1995-2001, 2005-07, 2009, 2015-17.",
  'CSU Analytic Studies school reports (Wayback Machine), Table 4 and ELM summary pages'),
 ('csu_wc_ready_asd', 'English proficiency at CSU entry (EPT era)', 'College outcome', 'percent',
  "Same as the math measure, for the English Placement Test: share who did not need remedial English at entry. Fewer than 10 freshmen hidden. Fall 1995-2001, 2005-07, 2009, 2015-17.",
  'CSU Analytic Studies school reports (Wayback Machine), Table 5 and EPT summary pages'),
 ('csu_ret1_asd', 'CSU one-year continuation (archived reports)', 'College outcome', 'percent',
  "Share of the school's regularly admitted CSU freshmen still enrolled at CSU one year later, from the archived CSU reports (Table 6). The CSU counterpart of uc_ret1. Fewer than 10 freshmen hidden. Fall 1995-97 entering classes (a few schools 1999-2000).",
  'CSU Analytic Studies school reports (Wayback Machine), Table 6'),
]


def q(mid, v):
    return int(round(float(v) * 10 ** DEC[mid])) / 10 ** DEC[mid]


def years_of(mid):
    ys = sorted(int(y) for y in vals[mid])
    skip = [y for y in range(ys[0], ys[-1] + 1) if y not in ys]
    return ys[0], ys[-1], skip


schools = pd.read_csv(REPO + 'data/schools.csv', dtype={'cds14': str})

# ------------------------------------------------------------------ long
long_df = pd.read_csv(REPO + 'data/panel_long.csv', dtype={'cds14': str})
long_df = long_df[~long_df['measure'].isin(NEW_IDS)]
rows = []
for mid in NEW_IDS:
    for y in sorted(vals[mid], key=int):
        for cds, v in vals[mid][y].items():
            rows.append((cds, int(y), mid, q(mid, v)))
nr = pd.DataFrame(rows, columns=['cds14', 'year', 'measure', 'value'])
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
h = open(REPO + 'index.html', encoding='utf-8').read()
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

HS_ENTRIES = (
 js_entry('gpa_csu_asd', True, None, 'gpa', 'HS GPA — CSU freshmen (1990s reports)',
  'Avg HS GPA — CSU entering freshmen (archived reports)',
  'The average high-school GPA of this school’s graduates who entered a CSU campus as regularly admitted freshmen that fall, from CSU’s own school-by-school reports of the late 1990s, recovered from the Internet Archive. The older counterpart of the 2021–25 measure. Shown when at least 10 students were reported. Available for fall 1995–97 for most schools, and for a few dozen schools in 1999–2000.') +
 js_entry('sat_csu_asd', True, None, 'sat0', 'SAT total — CSU freshmen (1600 scale)',
  'Avg SAT verbal+math — CSU entering freshmen (of 1600)',
  'The average SAT verbal + math total of this school’s regularly admitted CSU freshmen, on the old 1600-point scale, from the same archived CSU reports. This pool is the students who went on to CSU, not everyone at the school who took the test — compare it with the all-takers SAT average from CDE, which is on the same scale for 1999–2005. Shown when at least 10 students were reported. Available fall 1995–97, plus a few schools in 1999–2000.') +
 js_entry('nmsf_rate', False, None, 'per100', 'National Merit semifinalists per 100 students',
  'National Merit semifinalists per 100 students in a grade',
  'How many of the school’s seniors were named National Merit semifinalists, per 100 students in a grade. Semifinalists are roughly the top half-percent of PSAT takers in the state, chosen by a California cutoff score on the PSAT taken in October of junior year; the counts come from NMSC’s California press-release lists, divided by the school’s approximate students per grade. A school not on the list is shown as zero if it had grade-11 CAASPP results that year, so the many zeros are real. Schools under 20 students per grade are hidden. Available for the classes of 2016, 2018, 2020 and 2022 only. Read 2022 with care: its PSAT was given in October 2020, when many public schools were closed and did not give it. NMSC itself cautions that semifinalist counts measure individual students, not schools.') +
 js_entry('nmsf', True, None, 'nmsf', 'National Merit semifinalists (count)',
  'National Merit semifinalists (class of the year)',
  'The number of the school’s seniors named National Merit semifinalists that year — the raw count behind the per-100-students measure, with the same source and caveats. Larger schools have more. Available for the classes of 2016, 2018, 2020 and 2022.') +
 js_entry('csu_asd_ftf', True, None, 'nstud', 'Freshmen entering CSU (1995–2017 reports)',
  'Number of the school’s graduates entering CSU as freshmen',
  'How many of this school’s graduates entered a CSU campus as regularly admitted first-time freshmen that fall, from CSU’s archived school reports. A raw count — larger schools send more — mainly useful for seeing how many students the other archived CSU measures rest on. Available fall 1995–2001, 2005–07, 2009, 2013 and 2015–17; most schools appear only through 2005.')
)
OUT_ENTRIES = (
 js_entry('gpa_csu1_asd', False, 'out', 'gpa', 'CSU GPA one year later (1990s reports)',
  'Avg CSU GPA one year after entry (archived reports)',
  'The average college GPA at CSU after one year for this school’s regularly admitted CSU freshmen, from CSU’s archived school reports — the older counterpart of the 2021–24 measure. School-years with fewer than 10 freshmen are hidden. Available for the fall 1995–97 entering classes, plus a few schools in 1999–2000.') +
 js_entry('csu_math_ready_asd', False, 'out', 'pct', 'Math proficiency at CSU entry (ELM era)',
  '% of CSU freshmen not needing remedial math (ELM era)',
  'Of this school’s regularly admitted CSU freshmen, the share who did not need remedial math at entry: they were exempt from CSU’s Entry Level Mathematics test by their SAT, ACT or AP score, or they passed it. The rest were placed in remedial math. This is the direct ancestor of the 2021–25 math-readiness measure, under CSU’s old placement rules; the ELM scale and passing score changed in 2002. School-years with fewer than 10 freshmen are hidden. Available fall 1995–2001, 2005–07, 2009 and 2015–17, with only a few dozen schools in the later years.') +
 js_entry('csu_wc_ready_asd', False, 'out', 'pct', 'English proficiency at CSU entry (EPT era)',
  '% of CSU freshmen not needing remedial English (EPT era)',
  'The same measure for English: the share of this school’s regularly admitted CSU freshmen who did not need remedial English at entry — exempt from the English Placement Test by test score, or passed it. The ancestor of the 2021–25 writing-readiness measure. School-years with fewer than 10 freshmen are hidden. Available fall 1995–2001, 2005–07, 2009 and 2015–17.') +
 js_entry('csu_ret1_asd', False, 'out', 'pct', 'CSU 1-year continuation (1990s reports)',
  '% of CSU freshmen enrolled a year later (archived reports)',
  'Of this school’s regularly admitted CSU freshmen, the share still enrolled at CSU one year later, from CSU’s archived school reports — the CSU counterpart of UC 1-year retention. School-years with fewer than 10 freshmen are hidden. Available for the fall 1995–97 entering classes, plus a few schools in 1999–2000.')
)

# remove entries from an earlier run, then insert
h = re.sub(r" \{id:'(%s)',.*?\},\n" % '|'.join(NEW_IDS), '', h, flags=re.S)
mark_out = ' /* -------- college outcomes (what happened after enrollment) -------- */\n'
mark_ctx = ' /* -------- school context: what kind of school it is, not how it did --------'
assert h.count(mark_out) == 1 and h.count(mark_ctx) == 1
h = h.replace(mark_out, HS_ENTRIES + mark_out)
h = h.replace(mark_ctx, OUT_ENTRIES + mark_ctx)

# MEASURE_ORDER (edit only inside the array)
a = h.index('var MEASURE_ORDER=['); b = h.index('];', a)
mo = h[a:b]
for mid in NEW_IDS:
    mo = mo.replace("'%s'," % mid, '')
mo = mo.replace("'uc_gpa_range','gpa_csu','ag',", "'uc_gpa_range','gpa_csu','gpa_csu_asd','ag',")
mo = mo.replace("'star','star_math','cahsee','cahsee_math','sat1600',", "'star','star_math','cahsee','cahsee_math','sat_csu_asd','sat1600',")
mo = mo.replace("'ap','ap3','uc_apps_per_applicant',\n", "'ap','ap3','nmsf_rate','nmsf','uc_apps_per_applicant','csu_asd_ftf',\n")
mo = mo.replace(" 'gpa_csu1','csu_math_ready','csu_wc_ready','elwr',",
                " 'gpa_csu1','gpa_csu1_asd','csu_math_ready','csu_math_ready_asd','csu_wc_ready','csu_wc_ready_asd','csu_ret1_asd','elwr',")
for mid in NEW_IDS:
    assert mo.count("'%s'," % mid) == 1, mid
h = h[:a] + mo + h[b:]

# FAM_OF
h = re.sub(r"gpa_csu_asd:'gpa',|sat_csu_asd:'satact',|nmsf_rate:'nm',nmsf:'nm',|csu_asd_ftf:'appbeh',", '', h)
h = h.replace(" gpa_ucsel_gap:'gpa',uc_gpa_range:'gpa',gpa_csu:'gpa',", " gpa_ucsel_gap:'gpa',uc_gpa_range:'gpa',gpa_csu:'gpa',gpa_csu_asd:'gpa',")
h = h.replace(" sat1600:'satact',", " sat_csu_asd:'satact',sat1600:'satact',")
h = h.replace(" uc_apps_per_applicant:'appbeh',", " nmsf_rate:'nm',nmsf:'nm',uc_apps_per_applicant:'appbeh',csu_asd_ftf:'appbeh',")
# FAMS: a National Merit family after the admissions tests
h = h.replace(" {k:'nm',     label:'National Merit (PSAT)'},\n", '')
h = h.replace(" {k:'ap',     label:'AP exams'},\n", " {k:'ap',     label:'AP exams'},\n {k:'nm',     label:'National Merit (PSAT)'},\n")
assert h.count("k:'nm'") == 1
# UNIT_NAMES
h = h.replace(", nmsf:'semifinalists', per100:'semifinalists per 100 students', nstud:'students'", '')
h = h.replace("usd:'dollars', flag:'yes/no', stud:'students per grade'",
              "usd:'dollars', flag:'yes/no', stud:'students per grade', nmsf:'semifinalists', per100:'semifinalists per 100 students', nstud:'students'")
assert h.count("per100:'semifinalists per 100 students'") == 1

# data footnote
OLD = 'and average GPAs of CSU entering freshmen from CSU’s Student Origins dashboards.'
NEW = ('average GPAs of CSU entering freshmen from CSU’s Student Origins dashboards; CSU’s own archived school reports for 1995–2017 (asd.calstate.edu, recovered from the Internet Archive), which give each school’s CSU freshmen’s high-school GPA, SAT, placement-test results, first-year GPA and one-year continuation; and National Merit semifinalist counts from NMSC’s California press releases for the classes of 2016, 2018, 2020 and 2022.')
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
# MEASURES entries present exactly once and JS parses (a bracket sanity check)
for mid in NEW_IDS:
    assert h.count("{id:'%s'," % mid) == 1, mid
# same-school, different-era comparisons as a plausibility check
w = wide
def corr(a, b, ya, yb):
    x = w.loc[w.year == ya, ['cds14', a]].dropna().merge(w.loc[w.year == yb, ['cds14', b]].dropna(), on='cds14')
    return len(x), x[a].corr(x[b])
for a, b, ya, yb in [('csu_math_ready_asd', 'csu_math_ready', 2016, 2021), ('csu_wc_ready_asd', 'csu_wc_ready', 2016, 2021),
                     ('gpa_csu_asd', 'gpa_uc', 1997, 1997), ('sat_csu_asd', 'sat1600', 2000, 2000),
                     ('csu_math_ready_asd', 'caaspp_math', 2016, 2016), ('nmsf_rate', 'caaspp_l4', 2022, 2021),
                     ('nmsf_rate', 'gpa_ucsel_adm', 2020, 2020)]:
    n, r = corr(a, b, ya, yb)
    print('  r(%s %d, %s %d) = %.2f on %d schools' % (a, ya, b, yb, r, n))
