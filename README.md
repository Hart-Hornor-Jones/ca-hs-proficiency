# California high schools: measures of academic proficiency, 1994-2025

A school-level panel of **4,424 California public high schools** across **45 measures
and 32 years**, assembled entirely from public records, plus an interactive visualizer.

**The visualizer** (`index.html`) is a self-contained page - open it in any browser, no
server or installation needed. Every dot is one school; pick a measure for each axis and a
year, tag schools to follow them across views, fit trend lines, and switch any axis to a
change-over-time reading. If GitHub Pages is enabled for this repository, it runs at the
repository's Pages URL.

**The data** (`data/`) is the same panel as plain CSVs, ready for R, Python, Stata, or a
spreadsheet.

## Files

| file | what it is |
|---|---|
| `index.html` | the interactive visualizer (all data embedded; works offline) |
| `data/panel_long.csv` | tidy long form - one row per school x year x measure (810,764 rows): `cds14, year, measure, value` |
| `data/panel_wide.csv` | one row per school x year (71,485 rows), one column per measure |
| `data/schools.csv` | school directory: `cds14`, display name, county, approximate students per grade, charter flag |
| `data/measures.csv` | the measure dictionary: label, unit, years covered, description, source - **read this first** |
| `build/build_panel.py` | the script that built the original 28-measure panel (source files listed in its header) |
| `build/extend_panel_uc_pools.py` | the script that added the nine UC applicant-pool measures (denied, non-enrolling, selective-campus pools, spread, applications per applicant) |
| `build/splice_new_measures.py` | merges the nine new measures into the CSVs and the visualizer |
| `build/extend_panel_school_context.py` | builds the eight school-context measures (student need, LCFF+, disadvantaged and English-learner shares, under-represented share, neighborhood income, charter, size) |
| `build/splice_context_measures.py` | merges those into the CSVs and the visualizer |
| `build/context_report.txt` | coverage and checks for the school-context measures |
| `build/extend_report.txt` | coverage and checks for the nine added measures |
| `build/panel_report.txt` | per-measure coverage and the cross-checks run at build time |

## Quick start

R:
```r
library(tidyverse)
panel    <- read_csv("data/panel_long.csv", col_types = cols(cds14 = "c"))
measures <- read_csv("data/measures.csv")
schools  <- read_csv("data/schools.csv", col_types = cols(cds14 = "c"))

panel |>
  filter(measure %in% c("gpa_uc", "uc_grad4"), year == 2020) |>
  pivot_wider(names_from = measure, values_from = value) |>
  left_join(schools, by = "cds14") |>
  ggplot(aes(gpa_uc, uc_grad4)) + geom_point()
```

Python:
```python
import pandas as pd
wide = pd.read_csv("data/panel_wide.csv", dtype={"cds14": str})
wide[wide.year == 2020].plot.scatter("gpa_uc", "uc_grad4")
```

**Always read `cds14` as text** - it is a 14-character school code with leading zeros, and
numeric parsing destroys it.

## What the measures are

Two families, spelled out fully in `data/measures.csv`:

**High-school measures.** Census tests taken by (nearly) every student - CAASPP (2015-25),
its predecessors STAR/CST (2003-13) and CAHSEE (2002-15); course-taking - A-G completion
(2017-25); self-selected college-entrance tests - AP (1999-2020), SAT (1999-2016 in two
non-comparable scale eras, benchmarks 2017-18), ACT (1999-2020); and average high-school
GPAs of the school's UC applicant pools (1994-2025) and CSU entering freshmen (2021-25).
The UC GPA family now covers seven pools - applicants, admits, denied applicants,
admits who enrolled elsewhere, and enrollees systemwide, plus the applicant/admit/
denied/enrollee pools at the three most selective campuses (Berkeley, UCLA, San
Diego) - and three derived readings: the admit-minus-denied GPA gap at those
campuses, the full spread between a school's highest and lowest observed pool
average, and the average number of campuses each applicant applied to.

**School context.** What kind of school it is rather than how it did: the state's
unduplicated pupil percentage (student need) and UC's LCFF+ designation, the
socioeconomically-disadvantaged and English-learner shares of grade 11, the
under-represented minority share of the student body, the median household income of
the school's census tract, charter status, and school size. These are deliberately
kept OFF the two axes of the visualizer - they can color the dots and a residual can
be compared against them, but they are not achievement measures and putting them on
an axis would invite reading them as one. In the CSVs they are ordinary columns.

**College outcomes.** What happened to the school's graduates after they enrolled: CSU GPA
one year in, math and writing readiness at CSU entry (the complement is the share needing
supported instruction, formerly "remediation"), UC's Entry Level Writing Requirement,
and UC retention and four/six-year graduation by entering class.

## Reading the panel honestly - eight things to know

1. **A missing value means the source published nothing** (small-cell suppression, a school
   not yet open or already closed, or a series that does not cover that year). Nothing is
   imputed or zero-filled.
2. **The year is the spring of the school year** (2024 = 2023-24). GPA and college-outcome
   measures are keyed to the fall the class entered college, which is the same class of
   seniors.
3. **The two SAT series are different tests.** `sat1600` (verbal+math, through 2005) and
   `sat2400` (reading+math+writing, 2006-16) must never be spliced into one series.
4. **Census and self-selected measures are not interchangeable.** CAASPP/STAR/CAHSEE cover
   every student; AP/SAT/ACT and the GPA measures cover only students who took the test or
   applied. Across schools the two kinds correlate around 0.8, not 1.
5. **Known soft spots**: CAASPP participation in 2021 was far below normal; CAHSEE is a low
   bar and compresses differences among strong schools; `gpa_csu1` is built from cells the
   source rounds to one decimal; AP school-years with under 20 exams and CSU-readiness
   school-years with under 10 enrollees are excluded as too noisy.
6. **College outcomes are conditional on enrollment.** `uc_grad4` describes the school's
   students who enrolled at UC - a selected group whose size and composition differ by
   school and year.
7. **The denied and non-enrolling GPA pools are derived, and their meaning is genuinely
   ambiguous.** They are recovered exactly from published pool averages and counts
   ((applicants x applicant GPA - admits x admit GPA) / denied, and the analogous
   subtraction for admits minus enrollees), so the arithmetic is not in question - but
   who lands in each pool is: a "denied" pool mixes reaches and near-misses, and the
   non-enrolling pool mixes students lured elsewhere with students UC placed at a
   campus they did not want. Pools under 10 students are hidden. Read these as
   descriptions of pools, not judgments of students.
8. **Neighborhood is not student body.** `ctx_tract_inc` describes the census tract the
   school building sits in. Magnets, commuters and attendance boundaries pull that apart
   from who actually attends - sometimes drastically. The need measures (`ctx_upp`,
   `ctx_sed`) are measured on the students; the tract measure is not.

## Sources

CAASPP results, A-G completion, and the STAR, CAHSEE, AP, SAT, and ACT school reports are
from the California Department of Education; average GPAs of UC applicants, admits, and
enrollees, ELWR rates, and retention/graduation by high school are from UC's
admissions-by-school and outcomes data (denied-pool and non-enrolling-pool averages
derived by exact moment subtraction from the published figures); CSU freshman GPAs, first-year GPAs, and entry
placement are from CSU's Student Origins dashboards and high-school dashboard. Schools are
matched across the UC (CEEB) and state (CDS) identifier systems with a hand-verified
crosswalk. School context comes from the state's CUPC need collection, the enrollment counts
published alongside CAASPP, the CDE enrollment-by-race files, the CDE public school
directory, and American Community Survey tract estimates. Each build script documents
the exact input files and every aggregation
rule; `build/panel_report.txt` records coverage and the cross-checks run at build time.
