"""Parse NMSC state semifinalist press-release PDFs (California) into a
school x program-year table of semifinalist counts.

Layout: 4 columns per page; a city name sits at the column's left edge, a
school name 6pt in, and each semifinalist is a 3-digit code + "Last, First".
A school whose list runs past the bottom of a column continues at the top of
the next column (or page) with no repeated heading.

Needs `pdftotext` (poppler) on the PATH. Usage:
    python parse_nmsf.py [folder-with-the-pdfs]
Default folder: ..\..\..\hs data\national-merit (relative to this script).
Writes data/nmsf_semifinalists_by_school.csv (year, city, school, n).
The output is shipped with the repo, so this only needs re-running when a
new year's list is added (add it to FILES below).
"""
import re, html, subprocess, sys, collections, json
from pathlib import Path

CODE = re.compile(r'^\d{3}(\s|$)')

def lines_of(pdf):
    xml = subprocess.run(['pdftotext', '-bbox-layout', str(pdf), '-'],
                         capture_output=True, text=True).stdout
    pages = re.split(r'<page ', xml)[1:]
    out = []
    for pno, pg in enumerate(pages, 1):
        for m in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>(.*?)</line>', pg, re.S):
            words = re.findall(r'<word[^>]*>(.*?)</word>', m.group(3))
            txt = html.unescape(' '.join(words)).strip()
            out.append((pno, float(m.group(1)), float(m.group(2)), txt))
    return out

def parse(pdf, year):
    L = lines_of(pdf)
    # column bases: the x of city lines. Cluster all xs, take the 4 most common
    # "left-edge" values: those with many lines at x and at x+6.
    xs = collections.Counter(round(x) for _, x, _, _ in L)
    bases = sorted(x for x in xs if xs[x] >= 3 and xs.get(x + 6, 0) >= 5)
    # keep bases that are >= 100 apart (dedupe near-duplicates)
    keep = []
    for b in bases:
        if not keep or b - keep[-1] > 60:
            keep.append(b)
    bases = keep
    recs = []        # (page, col, y, kind, text)
    skipped = []
    for pno, x, y, txt in L:
        rx = round(x)
        col = None; kind = None
        for i, b in enumerate(bases):
            if abs(rx - b) <= 2: col, kind = i, 'city'; break
            if abs(rx - (b + 6)) <= 2: col, kind = i, 'school'; break
        if col is None:
            # name-only continuation of a split student line, or page furniture
            if not CODE.match(txt):
                skipped.append((pno, rx, txt))
            continue
        if CODE.match(txt):
            kind = 'student'
        recs.append((pno, col, y, kind, txt))
    recs.sort(key=lambda r: (r[0], r[1], r[2]))
    rows = []
    city = school = None; n = 0
    prev_kind = None
    def flush():
        nonlocal n
        if school is not None and n:
            rows.append({'year': year, 'city': city, 'school': school, 'n': n})
        n = 0
    for pno, col, y, kind, txt in recs:
        if kind == 'city':
            if txt in ('CALIFORNIA',) or txt.startswith('Semifinalists') or txt.startswith('Merit Scholarship') or '(continued)' in txt:
                continue   # page furniture: does not interrupt a school that spans columns/pages
            flush(); city = txt; school = None
        elif kind == 'school':
            if prev_kind == 'school':      # wrapped school name
                school = school + ' ' + txt
            else:
                flush(); school = txt
        else:
            n += 1
        prev_kind = kind
    flush()
    return rows, skipped

if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else (here / '..' / '..' / '..' / 'hs data' / 'national-merit')
    files = {2016: '279815462-California-National-Merit-Semifinalists.pdf',
             2018: 'nationalmerit.pdf',
             2020: '425455623-California-National-Merit-Semifinalists.pdf',
             2022: '22-ca-semifinalists-natlmeritprogram.pdf'}
    allrows = []
    for yr, f in files.items():
        rows, skipped = parse(src / f, yr)
        tot = sum(r['n'] for r in rows)
        print(yr, f, 'schools', len(rows), 'semifinalists', tot, 'skipped-lines', len(skipped))
        odd = [s for s in skipped if not re.match(r'^[A-Z][A-Za-z\'\-\. ]+,', s[2]) and not s[2].isdigit()]
        print('   non-name skipped:', odd[:15])
        allrows += rows
    import csv
    (here / 'data').mkdir(exist_ok=True)
    with open(here / 'data' / 'nmsf_semifinalists_by_school.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['year', 'city', 'school', 'n']); w.writeheader(); w.writerows(allrows)
