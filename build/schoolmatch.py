# -*- coding: utf-8 -*-
"""Match free-text (school name, city) pairs to the panel's CDS codes.

Shared by extend_panel_csu_asd_nmsf.py. The target universe is the panel's own
school list (data/schools.csv) joined to the CDE public-school directory for the
postal city and county of each school. Private schools are never matched: they
are not in the panel, and a private school that fuzzy-matches a public one with
a similar name is exactly the failure this module is written to avoid.

Tiers, in order (the report lists every non-exact match by tier):
  exact             normalized name AND city agree
  county_unique     normalized name matches exactly one school in the city's county
  state_unique      normalized name matches exactly one school statewide
  city_fuzzy        same city, high string similarity with a clear margin
  city_tokens       same city, one name's tokens are a subset of the other's and
                    the extra tokens are only "junk" (a first name, an initial,
                    JOINT/UNION/CHARTER/SENIOR..., or the city name itself)
  (none)            left unmatched
Never matched across a CONFLICT token (BOYS vs GIRLS, MIDDLE, CONTINUATION,
ADULT, VIRTUAL, ...).
"""
import re
import difflib
import unicodedata
import pandas as pd

STOP = {'SCHOOL', 'THE', 'OF', 'AT', 'FOR', 'AND', '&'}
JUNK = {'HIGH', 'HI', 'SENIOR', 'JUNIOR', 'JOINT', 'UNION', 'UNIFIED', 'CHARTER', 'PUBLIC',
        'DR', 'MR', 'MRS', 'MS', 'INC', 'HS', 'SCHOOLS'}
# a query that is just "<Name> School" is almost always a private school
SCHOOL_ONLY = re.compile(r"\bSCHOOL$")
PUBLIC_WORDS = re.compile(r"\b(HIGH|H\.? ?S\.?|ACADEMY|CHARTER|ARTS|PUBLIC|UCSD|MAGNET|COLLEGIATE|COMMUNITY)\b")
CONFLICT = {'BOYS', 'GIRLS', 'MIDDLE', 'INTERMEDIATE', 'ELEMENTARY', 'CONTINUATION',
            'ADULT', 'VIRTUAL', 'ONLINE', 'INDEPENDENT', 'ALTERNATIVE', 'OPPORTUNITY',
            'DAY', 'CAMP', 'COURT', 'JUVENILE', 'SPECIAL', 'NPS', 'PRESCHOOL', 'PRIMARY',
            'NORTH', 'SOUTH', 'EAST', 'WEST', 'CENTRAL', 'COUNTY'}
PRIVATE_HINTS = re.compile(
    r"\b(CHRISTIAN|CATHOLIC|LUTHERAN|BAPTIST|ADVENTIST|JEWISH|HEBREW|YESHIVA|ISLAMIC|"
    r"ST\.?|STS\.?|SAINT|SACRED|HOLY|OUR LADY|BISHOP|ARCHBISHOP|CARDINAL|JESUIT|"
    r"NOTRE DAME|LOYOLA|BRETHREN|MENNONITE|CHURCH|PAROCHIAL|PRIORY|SEMINARY|CATH\.?|"
    r"COUNTRY DAY|DAY SCHOOL|HOMESCHOOL|HOME SCHOOL|WALDORF|MONTESSORI|LYCEE|"
    r"MILITARY|EPISCOPAL|PRESBYTERIAN|METHODIST|COVENANT|CALVARY|TRINITY|"
    r"SALESIAN|MARIANIST|BENEDICTINE|CARMELITE|DE LA SALLE|LA SALLE|MATER DEI)\b")

ABBR = [(r"\bH\.?\s*S\.?(?=\s|$)", " HIGH "), (r"\bHS\b", " HIGH "), (r"\bSR\.?\b", " SENIOR "),
        (r"\bJR\.?\b", " JUNIOR "), (r"\bMT\.?\b", " MOUNT "), (r"\bST\.?\b", " SAINT "),
        (r"\bCONT\.?\b", " CONTINUATION "), (r"\bACAD\.?\b", " ACADEMY "),
        (r"\bPREP\.?\b", " PREPARATORY "), (r"\bTECH\.?\b", " TECHNOLOGY "),
        (r"\bELEM\.?\b", " ELEMENTARY "), (r"\bINTL\.?\b", " INTERNATIONAL "),
        (r"\bCTR\.?\b", " CENTER "), (r"\bCOMM\.?\b", " COMMUNITY "),
        (r"\bMATH\b", " MATHEMATICS "), (r"\bSCI\b", " SCIENCE "), (r"\bJT\.?\b", " JOINT ")]


def deaccent(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c))


def norm(s):
    s = deaccent(s or '').upper()
    s = s.replace('’', "'").replace('-', ' ').replace('/', ' ')
    s = re.sub(r"\(.*?\)", " ", s)              # "(Continuation)", "(Santa Clara)"
    s = re.sub(r"\[\d+\]", " ", s)             # "[1]" disambiguators in the panel names
    for pat, rep in ABBR:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\bSENIOR HIGH\b", "HIGH", s)
    s = re.sub(r"\bHIGH SCHOOL\b", "HIGH", s)
    toks = [t for t in s.split() if t not in STOP]
    return ' '.join(toks)


def norm_city(c):
    c = deaccent(c or '').upper().strip()
    c = re.sub(r"[^A-Z ]", " ", c)
    c = re.sub(r"\s+", " ", c).strip()
    return c


class Matcher:
    def __init__(self, schools, directory, overrides=None, active=None):
        """schools: panel schools.csv (cds14, school_name, county).
        directory: CDE directory (cds_code, cde_school, cde_city, cde_county).
        overrides: {(norm(name), norm_city(city)): cds14} hand adjudications."""
        d = directory[['cds_code', 'cde_school', 'cde_city', 'cde_county']].copy()
        d = d.rename(columns={'cds_code': 'cds14'})
        u = schools[['cds14', 'school_name', 'county']].merge(d, on='cds14', how='left')
        rows = []
        for r in u.itertuples(index=False):
            city = norm_city(r.cde_city) if isinstance(r.cde_city, str) else ''
            for nm in {r.school_name, r.cde_school if isinstance(r.cde_school, str) else None} - {None}:
                rows.append((r.cds14, nm, norm(nm), city, r.county))
        self.cand = pd.DataFrame(rows, columns=['cds14', 'name', 'nname', 'city', 'county'])
        self.by_city = {c: g for c, g in self.cand.groupby('city')}
        self.by_county = {c: g for c, g in self.cand.groupby('county')}
        self.city_county = {}          # from the WHOLE directory, so towns with no HS still resolve
        for r in directory[['cde_city', 'cde_county']].dropna().drop_duplicates().itertuples(index=False):
            self.city_county.setdefault(norm_city(r.cde_city), set()).add(r.cde_county)
        self.active = set(active or [])
        self.exact = {}
        self.by_name = {}
        for r in self.cand.itertuples(index=False):
            self.exact.setdefault((r.nname, r.city), set()).add(r.cds14)
            self.by_name.setdefault(r.nname, {})[r.cds14] = r.county
        self.overrides = overrides or {}

    def pick(self, cds_set, tier, name):
        """Several panel records share one name (a school re-coded over the years):
        prefer the record that still carries recent data."""
        act = [c for c in cds_set if c in self.active]
        if len(act) == 1:
            return act[0], tier + '_active', name
        return None, 'ambiguous(same name x%d)' % len(cds_set), None

    def city_key(self, nc):
        """Resolve a city label to the directory's spelling: exact, else the unique
        directory city that is a prefix of it or that it is a prefix of
        ('LA CANADA FLINTRIDGE' -> 'LA CANADA')."""
        if nc in self.city_county:
            return nc
        cands = [c for c in self.city_county if c and (nc.startswith(c + ' ') or c.startswith(nc + ' '))]
        return cands[0] if len(cands) == 1 else nc

    def county_of(self, city, county=None):
        if county:
            return county
        cs = self.city_county.get(self.city_key(norm_city(city)), set())
        return next(iter(cs)) if len(cs) == 1 else None

    def match(self, name, city, county=None):
        """Return (cds14, tier, matched_name) or (None, reason, None)."""
        nn, nc = norm(name), norm_city(city)
        if (nn, nc) in self.overrides:
            return self.overrides[(nn, nc)], 'override', name
        nc = self.city_key(nc)
        up = deaccent(name).upper().strip()
        if PRIVATE_HINTS.search(up):
            return None, 'private_hint', None
        school_only = bool(SCHOOL_ONLY.search(up)) and not PUBLIC_WORDS.search(up)
        hit = self.exact.get((nn, nc)) if nc else None
        if hit:
            if len(hit) == 1:
                return next(iter(hit)), 'exact', name
            return self.pick(hit, 'exact', name)
        cty = self.county_of(city, county)
        same = self.by_name.get(nn, {})
        held = None
        if cty:
            inc = [c for c, k in same.items() if k == cty]
            if len(inc) == 1:
                if inc[0] in self.active or not self.active:
                    return inc[0], 'county_unique', name
                held = (inc[0], 'county_unique', name)   # an older record; look for a live one
            if len(inc) > 1:
                return self.pick(set(inc), 'county', name)
        if school_only:
            return held or (None, 'school_only_no_exact', None)
        if not nc:
            return held or (None, 'no_city', None)      # never fuzzy-match without a city
        pool = self.by_city.get(nc)
        if pool is None or pool.empty:
            return held or (None, 'no_city', None)
        r = self._fuzzy(nn, nc, pool)
        if held and (r[0] is None or r[0] not in self.active):
            return held
        return r

    def _fuzzy(self, nn, nc, pool):
        qt = [t for t in nn.split()]; city_toks = set(nc.split())
        best = []
        for r in pool.drop_duplicates(['cds14', 'nname']).itertuples(index=False):
            ct = r.nname.split()
            if (set(qt) ^ set(ct)) & CONFLICT:
                continue
            ratio = difflib.SequenceMatcher(None, nn, r.nname).ratio()
            core_q = [t for t in qt if t not in JUNK and t not in city_toks and len(t) > 2]
            core_c = [t for t in ct if t not in JUNK and len(t) > 2]
            subset = False
            if core_q and core_c:
                if core_q == core_c:
                    subset = True
                else:
                    short, long_ = (core_q, core_c) if len(core_q) < len(core_c) else (core_c, core_q)
                    if long_[-len(short):] == short:      # "Patrick Henry" vs "Henry"
                        subset = all(t.isalpha() for t in long_[:-len(short)])
            best.append((ratio, subset, r.cds14, r.name))
        if not best:
            return None, 'no_candidates', None
        best.sort(reverse=True)
        top = best[0]
        second = next((b for b in best[1:] if b[2] != top[2]), None)
        margin = top[0] - (second[0] if second else 0)
        if top[0] >= 0.86 and (second is None or margin >= 0.06):
            return top[2], 'city_fuzzy', top[3]
        if top[0] >= 0.86 and second is not None and second[0] >= 0.86:
            return self.pick({b[2] for b in best if b[0] >= 0.86}, 'city_fuzzy', top[3])
        subs = [b for b in best if b[1]]
        if subs:
            cds_set = {b[2] for b in subs}
            if len(cds_set) == 1:
                return subs[0][2], 'city_tokens', subs[0][3]
            return self.pick(cds_set, 'city_tokens', subs[0][3])
        return None, 'ambiguous(%.2f %s | %s)' % (top[0], top[3], second[3] if second else '-'), None
