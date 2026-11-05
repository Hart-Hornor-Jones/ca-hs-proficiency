#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Internal-consistency checks for the California high-school proficiency panel.

Runs with the standard library plus pandas only, on Windows, macOS or Linux:

    python tests/check_data.py            # from anywhere; the repo root is found
    python tests/check_data.py --repo X   # or point it at a checkout explicitly

Every file is opened with encoding='utf-8'. The script collects every failure
instead of stopping at the first one, prints a PASS/FAIL line per check, and
exits 1 if anything failed.

What is asserted (all against the files as committed; nothing is rewritten):

  files        the four data files, the README and index.html exist and decode as UTF-8
  columns      each CSV has exactly the expected columns, in order
  keys         no duplicate keys: schools (cds14), measures (measure),
               panel_long (cds14, year, measure), panel_wide (cds14, year)
  cds14        every school code is 14 digits, and the three files name the same schools
  dictionary   measures.csv lists exactly the measures present in panel_long / panel_wide,
               plus the two fixed school attributes that live in schools.csv;
               n_values, first_year, last_year and decimals agree with the data
  long = wide  panel_wide is exactly the pivot of panel_long (same cells, same values)
  ranges       percentages within 0-100, GPAs within 0-5, flags in {0, 1}, test scores
               within their published scales, counts non-negative
  identities   caaspp is the mean of its ELA and Math parts; the Level 4 share never
               exceeds met-or-exceeded; nmsf_rate = 100 * nmsf / students per grade and is
               hidden exactly when the school has under 20 students per grade;
               ctx_lcff switches on at an unduplicated pupil percentage of 75
  page data    the PANEL blob embedded in index.html carries the same schools, sizes,
               measures, year ranges, decimals and cells as the CSVs, with values equal
               to within one unit of the last decimal (see KNOWN_ROUNDING_TIES below)
  page table   the MEASURES table in the page's JavaScript names every dictionary measure
               with the same decimals and years, and its skip lists are exactly the gap
               years of each series
  README       the counts and year span the README states match the data
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

# The page and the CSVs were rounded by different routines, which split exact
# .5 ties differently. This many cells (of about 850,000) differ by exactly one
# unit in the last decimal; the test allows that many and no more, and no cell
# may differ by more than one unit. Lower the number if a rebuild removes them.
KNOWN_ROUNDING_TIES = 3332

PANEL_MEASURE_COUNT = 52            # measures carried by year in panel_long / panel_wide
FIXED_ATTRIBUTES = {                # dictionary measures stored once per school in schools.csv
    "ctx_charter": "charter",
    "ctx_size": "students_per_grade",
}
YEAR0, YEAR1 = 1994, 2025
GROUPS = {"High-school measure", "Application behavior", "College outcome", "School context"}

MEASURE_COLUMNS = ["measure", "label", "group", "unit", "decimals", "first_year",
                   "last_year", "n_values", "description", "source"]
SCHOOL_COLUMNS = ["cds14", "school_name", "county", "students_per_grade", "charter"]
LONG_COLUMNS = ["cds14", "year", "measure", "value"]
WIDE_KEY_COLUMNS = ["cds14", "school_name", "county", "year"]

# Allowed value range by the dictionary's unit string.
UNIT_RANGES = {
    "percent": (0, 100),
    "per 100 students in a grade": (0, 100),
    "yes / no": (0, 1),
    "GPA (weighted, capped a-g)": (0, 5),
    "GPA (a-g)": (0, 5),
    "GPA": (0, 5),
    "GPA points (difference)": (-5, 5),
    "score, 1-5": (1, 5),
    "score, 1-36": (1, 36),
    "points, 400-1600": (400, 1600),
    "points, 600-2400": (600, 2400),
    # The dictionary says "campuses (1-9)", but 98 school-years sit between 0.5 and 1
    # because UC's application and applicant counts come from different tables.
    # The values are kept as published; the check only requires 0 < value <= 9.
    "campuses (1-9)": (0, 9),
    "students": (0, math.inf),
    "dollars": (0, math.inf),
    "scale-score points": (-math.inf, math.inf),
}


class Checker:
    def __init__(self):
        self.failures = []
        self.passes = 0

    def check(self, ok, name, detail=""):
        if ok:
            self.passes += 1
            print("PASS  " + name)
        else:
            self.failures.append(name + ("" if not detail else " -- " + str(detail)))
            print("FAIL  " + name + ("" if not detail else "\n      " + str(detail)))
        return ok


def find_repo(explicit):
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve().parent
    for cand in (here, here.parent):
        if (cand / "data" / "panel_long.csv").exists():
            return cand
    return Path.cwd().resolve()


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_panel_blob(html):
    """Return (PANEL dict, JavaScript after the blob) from index.html."""
    start = html.find("var PANEL=")
    if start < 0:
        return None, ""
    end = html.find(";\n", start)
    blob = html[start + len("var PANEL="):end]
    return json.loads(blob), html[end + 2:]


def parse_js_measures(js):
    """Parse the id/dec/y0/y1/skip fields of each entry in the page's MEASURES table."""
    pat = re.compile(
        r"\{id:'(?P<id>[a-z0-9_]+)',\s*adv:(?P<adv>true|false),\s*(?:grp:'(?P<grp>[a-z]+)',\s*)?"
        r"unit:'(?P<unit>[a-z0-9]+)',\s*dec:(?P<dec>\d+),\s*y0:(?P<y0>\d{4}),\s*y1:(?P<y1>\d{4}),"
        r"\s*skip:\[(?P<skip>[0-9, ]*)\]")
    out = {}
    for mt in pat.finditer(js):
        skip = [int(s) for s in mt.group("skip").replace(" ", "").split(",") if s]
        out[mt.group("id")] = {"dec": int(mt.group("dec")), "y0": int(mt.group("y0")),
                               "y1": int(mt.group("y1")), "skip": skip, "unit": mt.group("unit"),
                               "grp": mt.group("grp")}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", help="repository root (default: found from this file)")
    args = ap.parse_args()
    repo = find_repo(args.repo)
    data = repo / "data"
    c = Checker()
    print("repository: " + str(repo))

    # ------------------------------------------------------------ files
    needed = [data / "measures.csv", data / "schools.csv", data / "panel_long.csv",
              data / "panel_wide.csv", repo / "README.md", repo / "index.html"]
    missing = [str(p.relative_to(repo)) for p in needed if not p.exists()]
    if not c.check(not missing, "files: all data files, README.md and index.html present", missing):
        return finish(c)
    bad_utf8 = []
    for p in needed:
        try:
            read_text(p)
        except UnicodeDecodeError as exc:
            bad_utf8.append(str(p.relative_to(repo)) + ": " + str(exc)[:80])
    c.check(not bad_utf8, "files: every file decodes as UTF-8", bad_utf8)
    boms = [str(p.relative_to(repo)) for p in needed if open(p, "rb").read(3) == b"\xef\xbb\xbf"]
    c.check(not boms, "files: no UTF-8 byte-order mark", boms)

    measures = pd.read_csv(data / "measures.csv", encoding="utf-8")
    schools = pd.read_csv(data / "schools.csv", dtype={"cds14": str}, encoding="utf-8")
    long = pd.read_csv(data / "panel_long.csv", dtype={"cds14": str}, encoding="utf-8")
    wide = pd.read_csv(data / "panel_wide.csv", dtype={"cds14": str}, encoding="utf-8")

    # ------------------------------------------------------------ columns
    c.check(list(measures.columns) == MEASURE_COLUMNS, "columns: measures.csv", list(measures.columns))
    c.check(list(schools.columns) == SCHOOL_COLUMNS, "columns: schools.csv", list(schools.columns))
    c.check(list(long.columns) == LONG_COLUMNS, "columns: panel_long.csv", list(long.columns))
    wide_measures = [col for col in wide.columns if col not in WIDE_KEY_COLUMNS]
    c.check(list(wide.columns[:4]) == WIDE_KEY_COLUMNS,
            "columns: panel_wide.csv starts with cds14, school_name, county, year", list(wide.columns[:4]))
    c.check(len(wide_measures) == PANEL_MEASURE_COUNT,
            "columns: panel_wide.csv has %d measure columns" % PANEL_MEASURE_COUNT, len(wide_measures))

    # ------------------------------------------------------------ keys
    c.check(not schools["cds14"].duplicated().any(), "keys: schools.csv cds14 unique")
    c.check(not measures["measure"].duplicated().any(), "keys: measures.csv measure unique")
    c.check(not long.duplicated(["cds14", "year", "measure"]).any(),
            "keys: panel_long.csv (cds14, year, measure) unique")
    c.check(not wide.duplicated(["cds14", "year"]).any(), "keys: panel_wide.csv (cds14, year) unique")

    # ------------------------------------------------------------ cds14 and school sets
    c.check(schools["cds14"].str.fullmatch(r"\d{14}").all(), "cds14: 14 digits in schools.csv")
    c.check(long["cds14"].str.fullmatch(r"\d{14}").all(), "cds14: 14 digits in panel_long.csv")
    c.check(wide["cds14"].str.fullmatch(r"\d{14}").all(), "cds14: 14 digits in panel_wide.csv")
    s_set, l_set, w_set = set(schools["cds14"]), set(long["cds14"]), set(wide["cds14"])
    c.check(s_set == l_set == w_set, "cds14: schools.csv, panel_long and panel_wide name the same schools",
            "schools=%d long=%d wide=%d" % (len(s_set), len(l_set), len(w_set)))
    c.check(schools["school_name"].notna().all() and (schools["school_name"].str.strip() != "").all(),
            "schools: every school has a display name")
    c.check(set(schools["charter"].dropna().unique()) <= {0, 1}, "schools: charter is 0, 1 or blank",
            sorted(schools["charter"].dropna().unique()))
    spg = schools["students_per_grade"].dropna()
    c.check(((spg > 0) & (spg == spg.round())).all(), "schools: students_per_grade is a positive whole number")

    # ------------------------------------------------------------ long form basics
    c.check(long["value"].notna().all(), "long: no blank values (a missing value is an absent row)",
            int(long["value"].isna().sum()))
    c.check(long["year"].between(YEAR0, YEAR1).all() and long["year"].dtype.kind == "i",
            "long: year is an integer within %d-%d" % (YEAR0, YEAR1))
    c.check(long["year"].nunique() == YEAR1 - YEAR0 + 1, "long: every year %d-%d present" % (YEAR0, YEAR1),
            long["year"].nunique())

    # ------------------------------------------------------------ dictionary vs data
    dict_ids = list(measures["measure"])
    long_ids = sorted(long["measure"].unique())
    fixed = [m for m in dict_ids if m in FIXED_ATTRIBUTES]
    panel_ids = [m for m in dict_ids if m not in FIXED_ATTRIBUTES]
    c.check(sorted(fixed) == sorted(FIXED_ATTRIBUTES), "dictionary: the fixed attributes are ctx_charter and ctx_size", fixed)
    c.check(sorted(panel_ids) == long_ids, "dictionary: measures.csv lists exactly the measures in panel_long.csv",
            "only in dictionary: %s; only in long: %s" % (sorted(set(panel_ids) - set(long_ids)),
                                                           sorted(set(long_ids) - set(panel_ids))))
    c.check(sorted(panel_ids) == sorted(wide_measures), "dictionary: measures.csv lists exactly the measure columns of panel_wide.csv",
            "only in dictionary: %s; only in wide: %s" % (sorted(set(panel_ids) - set(wide_measures)),
                                                           sorted(set(wide_measures) - set(panel_ids))))
    c.check(set(measures["group"]) <= GROUPS, "dictionary: group is one of the four documented groups",
            sorted(set(measures["group"]) - GROUPS))
    for col in ("label", "unit", "description", "source"):
        c.check(measures[col].notna().all() and (measures[col].astype(str).str.strip() != "").all(),
                "dictionary: %s filled for every measure" % col)
    c.check(set(measures["unit"]) <= set(UNIT_RANGES), "dictionary: every unit string has a known range",
            sorted(set(measures["unit"]) - set(UNIT_RANGES)))
    c.check((measures["decimals"] >= 0).all() and measures["decimals"].dtype.kind == "i",
            "dictionary: decimals is a non-negative integer")

    md = measures.set_index("measure")
    grp = long.groupby("measure")
    stats = pd.DataFrame({"n": grp.size(), "y0": grp["year"].min(), "y1": grp["year"].max()})
    bad_n, bad_years, bad_round = [], [], []
    for mid in panel_ids:
        row, st = md.loc[mid], stats.loc[mid]
        if int(row["n_values"]) != int(st["n"]):
            bad_n.append("%s dict=%d data=%d" % (mid, row["n_values"], st["n"]))
        if (row["first_year"], row["last_year"]) != (st["y0"], st["y1"]):
            bad_years.append("%s dict=%s-%s data=%d-%d" % (mid, row["first_year"], row["last_year"], st["y0"], st["y1"]))
        vals = long.loc[long["measure"] == mid, "value"]
        if ((vals - vals.round(int(row["decimals"]))).abs() > 1e-9).any():
            bad_round.append(mid)
    c.check(not bad_n, "dictionary: n_values equals the number of values in panel_long.csv", bad_n)
    c.check(not bad_years, "dictionary: first_year/last_year equal the years spanned in panel_long.csv", bad_years)
    c.check(not bad_round, "dictionary: every value is rounded to the dictionary's decimals", bad_round)
    for mid, col in FIXED_ATTRIBUTES.items():
        row = md.loc[mid]
        c.check(pd.isna(row["first_year"]) and pd.isna(row["last_year"]),
                "dictionary: %s has blank first_year/last_year (fixed attribute)" % mid)
        c.check(int(row["n_values"]) == int(schools[col].notna().sum()),
                "dictionary: %s n_values equals non-blank %s in schools.csv" % (mid, col),
                "dict=%d schools=%d" % (row["n_values"], schools[col].notna().sum()))
        c.check("schools.csv" in str(row["description"]), "dictionary: %s description points to schools.csv" % mid)

    # ------------------------------------------------------------ long == wide
    pivot = long.pivot(index=["cds14", "year"], columns="measure", values="value")
    wide_idx = wide.set_index(["cds14", "year"])
    same_rows = set(pivot.index) == set(wide_idx.index)
    c.check(same_rows, "long = wide: panel_wide has one row per school-year present in panel_long",
            "pivot=%d wide=%d" % (len(pivot), len(wide_idx)))
    if same_rows:
        pv = pivot.reindex(index=wide_idx.index, columns=wide_measures)
        a, b = pv.to_numpy(), wide_idx[wide_measures].to_numpy()
        both_nan = pd.isna(a) & pd.isna(b)
        equal = (a == b) | both_nan
        c.check(bool(equal.all()), "long = wide: every cell of panel_wide equals the pivot of panel_long",
                "%d differing cells" % int((~equal).sum()))
    c.check(not wide[wide_measures].isna().all(axis=1).any(), "wide: no school-year row is entirely blank")
    merged = wide.merge(schools, on="cds14", how="left", suffixes=("", "_s"))
    name_ok = (merged["school_name"] == merged["school_name_s"]).all()
    county_ok = ((merged["county"] == merged["county_s"]) | (merged["county"].isna() & merged["county_s"].isna())).all()
    c.check(bool(name_ok and county_ok), "wide: school_name and county match schools.csv")

    # ------------------------------------------------------------ ranges
    out_of_range = []
    for mid in panel_ids:
        lo, hi = UNIT_RANGES[md.loc[mid, "unit"]]
        vals = wide[mid].dropna()
        n_bad = int(((vals < lo) | (vals > hi)).sum())
        if n_bad:
            out_of_range.append("%s: %d values outside [%s, %s] (min %s, max %s)" % (mid, n_bad, lo, hi, vals.min(), vals.max()))
    c.check(not out_of_range, "ranges: every value lies within its unit's range (percent 0-100, GPA 0-5, ...)", out_of_range)
    flag_ok = all(set(wide[mid].dropna().unique()) <= {0, 1} for mid in panel_ids if md.loc[mid, "unit"] == "yes / no")
    c.check(flag_ok, "ranges: yes/no measures hold only 0 and 1")
    c.check(long["value"].map(math.isfinite).all(), "ranges: every value is finite")

    # ------------------------------------------------------------ identities
    both = wide.dropna(subset=["caaspp_ela", "caaspp_math"])
    d_both = (both["caaspp"] - (both["caaspp_ela"] + both["caaspp_math"]) / 2).abs()
    only_ela = wide[wide["caaspp_ela"].notna() & wide["caaspp_math"].isna()]
    only_math = wide[wide["caaspp_math"].notna() & wide["caaspp_ela"].isna()]
    c.check(bool((d_both <= 0.1 + 1e-9).all()
                 and ((only_ela["caaspp"] - only_ela["caaspp_ela"]).abs() <= 1e-9).all()
                 and ((only_math["caaspp"] - only_math["caaspp_math"]).abs() <= 1e-9).all()
                 and not (wide["caaspp"].notna() & wide["caaspp_ela"].isna() & wide["caaspp_math"].isna()).any()),
            "identities: caaspp is the mean of caaspp_ela and caaspp_math (whichever are present), within rounding",
            "max difference %.3f" % d_both.max())
    l4 = wide.dropna(subset=["caaspp", "caaspp_l4"])
    over = l4[l4["caaspp_l4"] > l4["caaspp"] + 0.1 + 1e-9]
    c.check(over.empty, "identities: Level 4 share never exceeds met-or-exceeded by more than rounding (0.1)",
            over[["cds14", "year", "caaspp", "caaspp_l4"]].to_dict("records"))
    nm = wide.merge(schools[["cds14", "students_per_grade"]], on="cds14", how="left")
    has_rate = nm[nm["nmsf_rate"].notna()]
    no_rate = nm[nm["nmsf"].notna() & nm["nmsf_rate"].isna()]
    rate_diff = (has_rate["nmsf_rate"] - 100 * has_rate["nmsf"] / has_rate["students_per_grade"]).abs()
    c.check(bool(has_rate["nmsf"].notna().all() and (rate_diff <= 0.005 + 1e-9).all()),
            "identities: nmsf_rate = 100 * nmsf / students_per_grade, within rounding",
            "max difference %.4f" % rate_diff.max())
    c.check(bool((has_rate["students_per_grade"] >= 20).all()
                 and ((no_rate["students_per_grade"] < 20) | no_rate["students_per_grade"].isna()).all()),
            "identities: nmsf_rate is present exactly when the school has 20 or more students per grade")
    c.check(not (wide["nmsf_rate"].notna() & wide["nmsf"].isna()).any(), "identities: no nmsf_rate without nmsf")
    lc = wide.dropna(subset=["ctx_lcff", "ctx_upp"])
    on, off = lc[lc["ctx_lcff"] == 1], lc[lc["ctx_lcff"] == 0]
    c.check(bool((on["ctx_upp"] >= 75 - 0.05 - 1e-9).all() and (off["ctx_upp"] < 75 + 0.05 + 1e-9).all()),
            "identities: ctx_lcff is 1 exactly when ctx_upp reaches 75, within the one-decimal rounding of ctx_upp")
    c.check(not (wide["ctx_lcff"].notna() ^ wide["ctx_upp"].notna()).any(),
            "identities: ctx_lcff and ctx_upp are present for the same school-years")
    c.check(bool((wide["nmsf"].dropna() == wide["nmsf"].dropna().round()).all()
                 and (wide["csu_asd_ftf"].dropna() == wide["csu_asd_ftf"].dropna().round()).all()),
            "identities: nmsf and csu_asd_ftf are whole-number counts")

    # ------------------------------------------------------------ embedded page data
    html = read_text(repo / "index.html")
    panel, js = load_panel_blob(html)
    if not c.check(panel is not None, "page data: index.html contains a parseable 'var PANEL=' blob"):
        return finish(c)
    c.check(set(panel) == {"names", "sizes", "m"}, "page data: PANEL has names, sizes and m", sorted(panel))
    c.check(list(panel["names"]) == list(schools["school_name"]),
            "page data: PANEL.names equals schools.csv school_name, in order")
    # The page stores a missing size as 0 (schools.csv leaves it blank).
    sizes_ok = len(panel["sizes"]) == len(schools) and all(
        (pd.isna(b) and a == 0) or (not pd.isna(b) and float(a) == float(b))
        for a, b in zip(panel["sizes"], schools["students_per_grade"]))
    c.check(sizes_ok, "page data: PANEL.sizes equals schools.csv students_per_grade (0 where blank)")
    c.check(sorted(panel["m"]) == sorted(dict_ids), "page data: PANEL.m carries exactly the dictionary's measures",
            "only in page: %s; only in dictionary: %s" % (sorted(set(panel["m"]) - set(dict_ids)),
                                                           sorted(set(dict_ids) - set(panel["m"]))))
    cds_list = list(schools["cds14"])
    bad_meta, bad_cells, bad_const, ties, bad_rows = [], [], [], 0, []
    for mid in dict_ids:
        e = panel["m"].get(mid)
        if e is None:
            continue
        dec, scale = e["dec"], 10 ** e["dec"]
        if dec != int(md.loc[mid, "decimals"]):
            bad_meta.append("%s decimals page=%d dict=%d" % (mid, dec, md.loc[mid, "decimals"]))
        if mid in FIXED_ATTRIBUTES:
            if not e.get("k") or len(e["rows"]) != 1:
                bad_meta.append("%s should be a single constant row flagged k" % mid)
                continue
            parts = e["rows"][0].split(",")
            ref = schools[FIXED_ATTRIBUTES[mid]]
            ok = len(parts) == len(ref) and all(
                (p == "" and pd.isna(r)) or (p != "" and not pd.isna(r) and abs(int(p) / scale - float(r)) < 1e-9)
                for p, r in zip(parts, ref))
            if not ok:
                bad_const.append(mid)
            continue
        if (e["y0"], e["y1"]) != (int(md.loc[mid, "first_year"]), int(md.loc[mid, "last_year"])):
            bad_meta.append("%s years page=%d-%d dict=%s-%s" % (mid, e["y0"], e["y1"], md.loc[mid, "first_year"], md.loc[mid, "last_year"]))
        if len(e["rows"]) != e["y1"] - e["y0"] + 1:
            bad_rows.append(mid)
            continue
        csv_cells = {(k, y): v for k, y, v in wide[["cds14", "year", mid]].dropna(subset=[mid]).itertuples(index=False)}
        page_cells = {}
        for r, row in enumerate(e["rows"]):
            if row == "":
                continue
            parts = row.split(",")
            if len(parts) != len(cds_list):
                bad_rows.append("%s year %d has %d fields" % (mid, e["y0"] + r, len(parts)))
                continue
            for k, p in enumerate(parts):
                if p != "":
                    page_cells[(cds_list[k], e["y0"] + r)] = int(p)
        if set(page_cells) != set(csv_cells):
            bad_cells.append("%s: page has %d cells, csv %d" % (mid, len(page_cells), len(csv_cells)))
            continue
        for key, pv in page_cells.items():
            diff = abs(pv - int(round(csv_cells[key] * scale)))
            if diff == 1:
                ties += 1
            elif diff > 1:
                bad_cells.append("%s %s %d: page %s csv %s" % (mid, key[0], key[1], pv / scale, csv_cells[key]))
    c.check(not bad_meta, "page data: PANEL decimals and year ranges match measures.csv", bad_meta)
    c.check(not bad_rows, "page data: one row per year, one field per school", bad_rows)
    c.check(not bad_const, "page data: ctx_charter and ctx_size equal schools.csv charter and students_per_grade", bad_const)
    c.check(not bad_cells, "page data: every measure has exactly the CSV's cells, with no value off by more than one unit", bad_cells[:10])
    c.check(ties <= KNOWN_ROUNDING_TIES,
            "page data: cells differing by one unit in the last decimal (rounding ties) within the known %d" % KNOWN_ROUNDING_TIES,
            "found %d" % ties)
    print("      (%d of the page's cells round a .5 tie differently from the CSV; the CSVs are the reference)" % ties)

    # ------------------------------------------------------------ page measure table
    table = parse_js_measures(js)
    c.check(sorted(table) == sorted(dict_ids), "page table: the JavaScript MEASURES table names exactly the dictionary's measures",
            "only in table: %s; only in dictionary: %s" % (sorted(set(table) - set(dict_ids)), sorted(set(dict_ids) - set(table))))
    bad_table = []
    for mid, t in table.items():
        if mid not in md.index:
            continue
        if t["dec"] != int(md.loc[mid, "decimals"]):
            bad_table.append("%s dec table=%d dict=%d" % (mid, t["dec"], md.loc[mid, "decimals"]))
        if mid in FIXED_ATTRIBUTES:
            if (t["y0"], t["y1"], t["skip"]) != (YEAR0, YEAR1, []):
                bad_table.append("%s should span %d-%d with no skips" % (mid, YEAR0, YEAR1))
            continue
        y0, y1 = int(md.loc[mid, "first_year"]), int(md.loc[mid, "last_year"])
        if (t["y0"], t["y1"]) != (y0, y1):
            bad_table.append("%s years table=%d-%d dict=%d-%d" % (mid, t["y0"], t["y1"], y0, y1))
        present = set(long.loc[long["measure"] == mid, "year"])
        gaps = [y for y in range(y0, y1 + 1) if y not in present]
        if t["skip"] != gaps:
            bad_table.append("%s skip table=%s data gaps=%s" % (mid, t["skip"], gaps))
    c.check(not bad_table, "page table: decimals, years and skip lists agree with the CSVs", bad_table)
    order = re.search(r"var MEASURE_ORDER=\[(.*?)\];", js, re.S)
    order_ids = re.findall(r"'([a-z0-9_]+)'", order.group(1)) if order else []
    c.check(sorted(order_ids) == sorted(dict_ids), "page table: MEASURE_ORDER lists every measure exactly once",
            "only in order: %s; missing: %s" % (sorted(set(order_ids) - set(dict_ids)), sorted(set(dict_ids) - set(order_ids))))
    slider = re.search(r'<input type="range" id="year" min="(\d+)" max="(\d+)"', html)
    c.check(slider is not None and (int(slider.group(1)), int(slider.group(2))) == (YEAR0, YEAR1),
            "page: the year slider spans %d-%d" % (YEAR0, YEAR1))

    # ------------------------------------------------------------ README figures
    readme = read_text(repo / "README.md")
    def claimed(pattern):
        mt = re.search(pattern, readme)
        return int(mt.group(1).replace(",", "")) if mt else None
    c.check(claimed(r"\*\*([\d,]+) California public high schools\*\*") == len(schools),
            "README: school count matches schools.csv", "%s vs %d" % (claimed(r"\*\*([\d,]+) California public high schools\*\*"), len(schools)))
    c.check(claimed(r"\*\*(\d+) measures") == len(measures), "README: measure count matches measures.csv")
    c.check(claimed(r"(\d+) years\*\*") == YEAR1 - YEAR0 + 1, "README: year count matches the panel")
    c.check(claimed(r"panel_long\.csv`[^\n]*?\(([\d,]+) rows\)") == len(long), "README: panel_long row count",
            claimed(r"panel_long\.csv`[^\n]*?\(([\d,]+) rows\)"))
    c.check(claimed(r"panel_wide\.csv`[^\n]*?\(([\d,]+) rows\)") == len(wide), "README: panel_wide row count",
            claimed(r"panel_wide\.csv`[^\n]*?\(([\d,]+) rows\)"))
    c.check(re.search(r"^# .*%d-%d" % (YEAR0, YEAR1), readme, re.M) is not None, "README: title states %d-%d" % (YEAR0, YEAR1))
    return finish(c)


def finish(c):
    print("")
    print("%d checks passed, %d failed" % (c.passes, len(c.failures)))
    for f in c.failures:
        print("  FAIL " + f)
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
