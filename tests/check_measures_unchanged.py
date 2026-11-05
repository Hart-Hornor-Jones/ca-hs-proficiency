#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that adding measures left every existing measure exactly as it was.

    python tests/check_measures_unchanged.py                    # against origin/main
    python tests/check_measures_unchanged.py --base main
    python tests/check_measures_unchanged.py --base <commit> --new id1,id2,...

Reads the baseline's data/measures.csv, data/schools.csv, data/panel_long.csv,
data/panel_wide.csv and index.html with `git show <base>:<path>` and compares
them with the working copy. Every measure named in the baseline dictionary must
be reproduced exactly: the same dictionary row, the same long rows (as text),
the same panel_wide cells, the same PANEL blob entry in index.html, and the same
MEASURES menu entry. The measures passed with --new (default: the six added by
build/splice_levels_gap_ucsd_measures.py) are the only ones allowed to be new;
anything else present in the working copy but not the baseline fails. Needs
pandas and git. Exit status 1 on any failure.
"""
import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

DEFAULT_NEW = ['caaspp_math_l4', 'caaspp_math_l1', 'caaspp_math_l4_sed', 'caaspp_math_l4_notsed',
               'caaspp_math_gap_sed', 'ucsd_adv']
FILES = ['data/measures.csv', 'data/schools.csv', 'data/panel_long.csv', 'data/panel_wide.csv', 'index.html']


def git_show(repo, ref, path):
    out = subprocess.run(['git', '-C', str(repo), 'show', '%s:%s' % (ref, path)], capture_output=True)
    if out.returncode != 0:
        raise SystemExit('git show %s:%s failed: %s' % (ref, path, out.stderr.decode('utf-8', 'replace').strip()))
    return out.stdout.decode('utf-8')


def panel_and_entries(html):
    i = html.find('var PANEL=')
    j = html.find(';\n', i)
    panel = json.loads(html[i + len('var PANEL='):j])
    entries = {m.group(1): m.group(0) for m in re.finditer(r" \{id:'([a-z0-9_]+)',.*?\},?\n", html[j:], flags=re.S)}
    return panel, entries


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', default='origin/main', help='git ref holding the earlier files (default origin/main)')
    ap.add_argument('--new', default=','.join(DEFAULT_NEW), help='comma-separated measure ids allowed to be new')
    ap.add_argument('--repo', help='repository root (default: found from this file)')
    args = ap.parse_args()
    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parent.parent
    new_ids = set(s for s in args.new.split(',') if s)
    fails = []

    def check(ok, name, detail=''):
        print(('PASS  ' if ok else 'FAIL  ') + name + ('' if ok or not detail else '\n      ' + str(detail)))
        if not ok:
            fails.append(name)

    old = {p: git_show(repo, args.base, p) for p in FILES}
    new = {p: (repo / p).read_text(encoding='utf-8') for p in FILES}
    rd = lambda s: pd.read_csv(io.StringIO(s), dtype=str, keep_default_na=False)

    ms0, ms1 = rd(old['data/measures.csv']), rd(new['data/measures.csv'])
    base_ids = list(ms0['measure'])
    extra = sorted(set(ms1['measure']) - set(base_ids) - new_ids)
    missing = sorted(set(base_ids) - set(ms1['measure']))
    check(not extra and not missing, 'dictionary: the working copy adds only the declared new measures and drops none',
          'unexpected: %s; missing: %s' % (extra, missing))
    m1 = ms1[ms1['measure'].isin(base_ids)].set_index('measure').reindex(base_ids)
    m0 = ms0.set_index('measure')
    same = list(m0.columns) == list(m1.columns) and m0.equals(m1)
    check(same, 'dictionary: every baseline row (%d) is reproduced exactly' % len(base_ids),
          '' if same else 'differing: %s' % [m for m in base_ids if not m0.loc[m].equals(m1.loc[m])][:10])

    check(old['data/schools.csv'] == new['data/schools.csv'], 'schools.csv: identical to the baseline')

    l0, l1 = rd(old['data/panel_long.csv']), rd(new['data/panel_long.csv'])
    l1b = l1[~l1['measure'].isin(new_ids)]
    key = ['measure', 'year', 'cds14']
    a = l0.sort_values(key).reset_index(drop=True)
    b = l1b.sort_values(key).reset_index(drop=True)
    check(a.equals(b), 'panel_long.csv: every baseline row (%d, %d measures) is reproduced exactly as text' % (len(l0), l0['measure'].nunique()),
          'baseline %d rows, working copy %d rows outside the new measures' % (len(l0), len(l1b)))

    w0, w1 = rd(old['data/panel_wide.csv']), rd(new['data/panel_wide.csv'])
    cols0 = list(w0.columns)
    extra_cols = [c for c in w1.columns if c not in cols0 and c not in new_ids]
    check(not extra_cols and all(c in w1.columns for c in cols0), 'panel_wide.csv: baseline columns kept, only the new measures added', extra_cols)
    k0 = w0.set_index(['cds14', 'year'])
    k1 = w1.set_index(['cds14', 'year'])
    common = k0.index.intersection(k1.index)
    check(len(common) == len(k0), 'panel_wide.csv: every baseline school-year row is still present',
          '%d of %d' % (len(common), len(k0)))
    cols = [c for c in cols0 if c not in ('cds14', 'year')]
    meas = [c for c in cols if c not in ('school_name', 'county')]
    same = k0.loc[common, cols].equals(k1.loc[common, cols])
    check(same, 'panel_wide.csv: every baseline cell (%d rows x %d columns) is reproduced exactly as text' % (len(common), len(cols)))
    added_rows = k1.index.difference(k0.index)
    blank_old = (k1.loc[added_rows, meas] == '').all(axis=1).all() if len(added_rows) else True
    check(blank_old, 'panel_wide.csv: the %d added school-year rows carry only new-measure values' % len(added_rows))

    p0, e0 = panel_and_entries(old['index.html'])
    p1, e1 = panel_and_entries(new['index.html'])
    check(p0['names'] == p1['names'] and p0['sizes'] == p1['sizes'], 'index.html: PANEL names and sizes unchanged')
    diff = [m for m in p0['m'] if p1['m'].get(m) != p0['m'][m]]
    check(not diff, 'index.html: every baseline PANEL blob entry (%d) is identical' % len(p0['m']), diff[:10])
    extra_blob = sorted(set(p1['m']) - set(p0['m']) - new_ids)
    check(not extra_blob, 'index.html: PANEL blob adds only the declared new measures', extra_blob)
    diff = [m for m in e0 if e1.get(m) != e0[m]]
    check(not diff, 'index.html: every baseline MEASURES menu entry (%d) is identical' % len(e0), diff[:10])

    print('')
    print('%s against %s' % ('ALL PASS' if not fails else 'FAILED: ' + '; '.join(fails), args.base))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
