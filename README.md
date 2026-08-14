# California high schools: measures of academic proficiency, 1994-2025

A school-level panel of **4,424 California public high schools** across **28 measures
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
| `data/panel_long.csv` | tidy long form - one row per school x year x measure (499,238 rows): `cds14, year, measure, value` |
| `data/panel_wide.csv` | one row per school x year (65,569 rows), one column per measure |
| `data/schools.csv` | school directory: `cds14`, display name, county, approximate students per grade |
| `data/measures.csv` | the measure dictionary: label, unit, years covered, description, source - **read this first** |
| `build/build_panel.py` | the script that built the panel (source files listed in its header) |
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
GPAs of the school's UC applicants, admits, and enrollees (1994-2025) and CSU entering
freshmen (2021-25).

**College outcomes.** What happened to the school's graduates after they enrolled: CSU GPA
one year in, math and writing readiness at CSU entry (the complement is the share needing
supported instruction, formerly "remediation"), UC's Entry Level Writing Requirement,
and UC retention and four/six-year graduation by entering class.

## Reading the panel honestly - six things to know

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

## Sources

CAASPP results, A-G completion, and the STAR, CAHSEE, AP, SAT, and ACT school reports are
from the California Department of Education; average GPAs of UC applicants, admits, and
enrollees, ELWR rates, and retention/graduation by high school are from UC's
admissions-by-school and outcomes data; CSU freshman GPAs, first-year GPAs, and entry
placement are from CSU's Student Origins dashboards and high-school dashboard. Schools are
matched across the UC (CEEB) and state (CDS) identifier systems with a hand-verified
crosswalk. `build/build_panel.py` documents the exact input files and every aggregation
rule; `build/panel_report.txt` records coverage and the cross-checks run at build time.
