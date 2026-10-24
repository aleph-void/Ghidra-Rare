#!/usr/bin/env python3
"""Generate SLEIGH (.sinc) for one 128-bit SASS architecture from a learned spec.

  gen_sleigh.py spec/SM80.json data/languages/sass_SM80.sinc

Every learned form (see sassmodel.py / learn.py) becomes one or more root
constructors.  The form's token skeleton is split into

  * literal text,
  * slot sub-tables (registers, immediates, floats, pc-relative targets), and
  * segments: sub-tables enumerating the values of modifier groups and the
    special-value states of the slots they cover, with the exact text the
    model renders for each case.  A segment inside an operand is widened to the
    whole operand, so each of its constructors can also export the operand's
    value for the p-code.

semantics.py decides per operand which role (destination, source, address, ...)
it plays and supplies the instruction body.
"""
import sys, os, json, re, itertools, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sassmodel import from_json, render_items, group_value, slot_state, REGZ, classify, is64
import semantics as SEM

GUARD_BITS = [12, 13, 14, 15]
SEG_MAX = int(os.environ.get('SASS_SEG_MAX', '1024'))
KEEP_NESTED = os.environ.get('SASS_KEEP_NESTED', '0') == '1'
EXC_BITS = int(os.environ.get('EXC_BITS', '8'))
CUBE_CAP = int(os.environ.get('SASS_CUBE_CAP', '100000'))
RSIZE = {'d4': 4, 'd8': 8, 'd16': 16, 's4': 4, 's8': 8, 's16': 16, 'f4': 4, 'f8': 8, 'p': 1, 'pd': 1,
         'a': 8, 'h': 2, 'cb1': 1, 'cb2': 2, 'cb4': 4, 'cb8': 8, 'cb16': 16, 'sr': 4, 't': 8}

def runs(bits):
    """Contiguous runs of bit positions; never crossing the 64-bit boundary of the
    128-bit token (SLEIGH extracts such fields incorrectly)."""
    out = []
    for b in sorted(bits):
        if out and out[-1][1] == b - 1 and b != 64:
            out[-1][1] = b
        else:
            out.append([b, b])
    return [tuple(r) for r in out]

def units(toks):
    u = []
    i = 0
    n = len(toks)
    if toks and toks[0] == '@':
        while i < n and toks[i] != ' ':
            u.append(-2); i += 1
        if i < n:
            u.append(-2); i += 1
    while i < n and toks[i] != ' ':
        u.append(-1); i += 1
    if i < n:
        u.append(None); i += 1
    k = 0
    while i < n:
        if toks[i] == ', ':
            u.append(None); k += 1
        else:
            u.append(k)
        i += 1
    return u

def crosses_sep(U, lo, hi):
    for i in range(max(0, lo), min(hi, len(U))):
        if U[i] is None and i > 0 and U[i - 1] is not None and U[i - 1] < 0:
            return True
    return False

def srname(t):
    return re.sub(r'\W', '_', t)

class Unsupported(Exception):
    pass

def specialize(form, gi, v):
    """Copy of form with group gi fixed to value v: the group's text is spliced into the
    token skeleton and its bits become fixed bits."""
    g = form['groups'][gi]
    out = g['table'][v]
    lo, hi = g['lo'], g['hi']
    toks = form['toks']
    delta = len(out) - (hi - lo)
    newtoks = list(toks[:lo])
    slots = [dict(s) for s in form['slots']]
    for x in out:
        if isinstance(x, int):
            slots[x]['pos'] = len(newtoks)
            newtoks.append(toks[form['slots'][x]['pos']])
        else:
            newtoks.append(x)
    newtoks += toks[hi:]
    inside = {k for k, s in enumerate(form['slots']) if lo <= s['pos'] < hi}
    shown = {x for x in out if isinstance(x, int)}
    for k, s in enumerate(form['slots']):
        if k in inside:
            continue
        if s['pos'] >= hi:
            slots[k]['pos'] = s['pos'] + delta
    def mv(p, end=False):
        if p > lo or (p == lo and end and hi > lo):
            return p + delta if p >= hi else p
        return p
    groups = []
    for j, h in enumerate(form['groups']):
        if j == gi:
            continue
        h = dict(h)
        if h['lo'] >= hi:
            h['lo'] += delta; h['hi'] += delta
        elif h['hi'] <= lo:
            pass
        else:
            return None        # overlapping groups: cannot splice
        groups.append(h)
    specials = []
    gmap = {j: (j if j < gi else j - 1) for j in range(len(form['groups'])) if j != gi}
    for sp in form.get('specials', []):
        sp = dict(sp)
        if any(k in inside and k not in shown for k in sp['slots']):
            continue
        if 'gis' in sp:
            gis = sp['gis']
            if gi in gis:
                i = gis.index(gi)
                cases = {}
                for key, o in sp['cases'].items():
                    st, gv = key.split('|')
                    gvs = gv.split(',')
                    if gvs[i] != str(v):
                        continue
                    rest = [x for j2, x in enumerate(gvs) if j2 != i]
                    cases[st + '|' + ','.join(rest)] = o
                sp['cases'] = cases
                gis = [x for x in gis if x != gi]
            if sp['lo'] >= hi:
                sp['lo'] += delta; sp['hi'] += delta
            elif sp['hi'] > lo:
                return None
            sp['gis'] = [gmap[x] for x in gis]
            if not sp['gis']:
                # no groups left: becomes a plain relative special anchored at its first slot
                a = slots[sp['slots'][0]]['pos']
                cases = {key.split('|')[0]: o for key, o in sp['cases'].items()}
                sp = dict(slots=sp['slots'], rlo=sp['lo'] - a, rhi=sp['hi'] - a, cases=cases)
        specials.append(sp)
    f = dict(form)
    f['toks'] = newtoks
    f['slots'] = slots
    f['groups'] = groups
    f['specials'] = specials
    m = f['mask']; val = f['val']
    for i, b in enumerate(g['bits']):
        m |= 1 << b
        val = (val & ~(1 << b)) | (((v >> i) & 1) << b)
    f['mask'] = m; f['val'] = val
    w = int(form['seed'], 16)
    for i, b in enumerate(g['bits']):
        w = (w & ~(1 << b)) | (((v >> i) & 1) << b)
    f['seed'] = '%x' % w
    f['text'] = ''.join(str(x) for x in newtoks)
    return f

class Gen:
    def __init__(self, arch, forms):
        global GUARD_BITS
        self.arch = arch
        self.wide = not is64(arch)
        if not self.wide:
            GUARD_BITS = [18, 19, 20, 21] if arch in ('SM35', 'SM37') else [16, 17, 18, 19]
        self.forms = forms
        self.fields = {}
        self.stats = collections.Counter()
        for f in forms:
            self.repair_gis(f)
        self.attach = {}
        self.tables = collections.OrderedDict()
        self.tabkey = {}
        self.roots = []
        self.pcodeops = set(['sass_exit'])
        self.used_forms = []
        self.srs = set()

    def repair_gis(self, f):
        """Specials refer to groups by index; specs processed by an older
        fix_reuse.py could have the groups reordered.  Re-point an index whose group
        is outside the special's token range (or is the guard) at the unique
        group that fits."""
        G = f['groups']
        keep = []
        for sp in f.get('specials', []):
            if 'gis' not in sp:
                keep.append(sp); continue
            try:
                # case keys: "<slot states>|<group values>", each part comma separated
                vals = [{int(k.split('|')[1].split(',')[n]) for k in sp['cases']} for n in range(len(sp['gis']))]
            except (IndexError, ValueError):
                keep.append(sp); continue
            def fits(k, n):
                g = G[k] if 0 <= k < len(G) else None
                return (g is not None and not set(g['bits']) & set(GUARD_BITS) and sp['lo'] <= g['lo'] and g['hi'] <= sp['hi']
                        and vals[n] <= {int(x) for x in g['table']})
            gis = list(sp['gis'])
            ok = True
            for n, k in enumerate(gis):
                if fits(k, n):
                    continue
                cand = [j for j in range(len(G)) if j not in gis and fits(j, n)]
                if len(cand) == 1:
                    gis[n] = cand[0]; self.stats['gis_repaired'] += 1
                else:
                    ok = False
            if ok:
                sp['gis'] = gis; keep.append(sp)
            else:
                self.stats['gis_dropped'] += 1
        f['specials'] = keep

    # ------------------------------------------------------------ fields
    def field(self, lo, hi, signed=False):
        n = 'f%d_%d%s' % (lo, hi, 's' if signed else '')
        self.fields[n] = (lo, hi, signed)
        return n

    def regfield(self, cls, lo, hi):
        n = '%s%d_%d' % (cls.lower(), lo, hi)
        self.fields[n] = (lo, hi, False)
        self.attach[n] = cls
        return n

    def cons_bits(self, bits, value):
        parts = []
        pos = {b: i for i, b in enumerate(bits)}
        for lo, hi in runs(bits):
            v = 0
            for b in range(lo, hi + 1):
                v |= ((value >> pos[b]) & 1) << (b - lo)
            parts.append('%s=%d' % (self.field(lo, hi), v))
        return parts

    def cons_mask(self, mask, val):
        bits = [b for b in range(128) if (mask >> b) & 1]
        parts = []
        for lo, hi in runs(bits):
            v = (val >> lo) & ((1 << (hi - lo + 1)) - 1)
            parts.append('%s=%d' % (self.field(lo, hi), v))
        return parts

    def table(self, prefix, conslist):
        key = hashlib.sha1(('\n'.join(conslist)).encode()).hexdigest()[:12]
        if key in self.tabkey:
            return self.tabkey[key]
        name = '%s_%s' % (prefix, key[:8])
        self.tabkey[key] = name
        self.tables[name] = [c.replace('@@', name) for c in conslist]
        return name

    # ------------------------------------------------------------ slots
    def value_expr(self, s):
        bits = s['bits']
        terms = []
        pos = 0
        rr = runs(bits) if bits == sorted(bits) else None
        if rr is None:
            if s.get('signed'):
                raise Unsupported('irregular signed slot')
            for i, b in enumerate(bits):
                terms.append('(%s << %d)' % (self.field(b, b), i))
            raw = ' + '.join(terms)
        else:
            for k, (lo, hi) in enumerate(rr):
                last = k == len(rr) - 1
                fn = self.field(lo, hi, signed=bool(s.get('signed')) and last)
                terms.append('(%s << %d)' % (fn, pos) if pos else fn)
                pos += hi - lo + 1
            raw = ' + '.join(terms)
        sc = s.get('scale', 1)
        add = s.get('add', 0)
        e = raw if sc == 1 else '(%s) * %d' % (raw, sc)
        if add:
            e = '%s + %d' % (e, add) if add > 0 else '%s - %d' % (e, -add)
        if re.fullmatch(r'f\d+_\d+s?', e):
            e = e + ' + 0'
        return e

    def slot_table(self, s, role):
        """Sub-table that displays a slot value and exports it according to role."""
        cls = s['cls']
        bits = s['bits']
        rr = runs(bits)
        if cls in ('R', 'UR', 'P', 'UP', 'B'):
            if not (len(rr) == 1 and s.get('scale', 1) == 1 and s.get('add', 0) == 0):
                return self.slot_numeric(s, role)
            lo, hi = rr[0]
            f = self.regfield(cls, lo, hi)
            raw = self.field(lo, hi)
            n = len(bits)
            z = REGZ.get(cls)
            zero = z is not None and z[0] == (1 << n) - 1
            regbase = {'R': 0, 'UR': 0x400, 'P': 0x500, 'UP': 0x508, 'B': 0x600}[cls]
            if role in ('s8', 'f8', 's16', 'd8', 'd16') and cls in ('R', 'UR'):
                w = RSIZE[role]
                name = 'S%s%d_%d_%d%s' % (cls, lo, hi, w, 'd' if role[0] == 'd' else '')
                if name not in self.tables:
                    cs = []
                    if zero and role[0] != 'd':
                        if w <= 8:
                            cs.append('%s: %s is %s=%d & %s { export %d:%d; }' % (name, f, raw, z[0], f, 0, w))
                        else:
                            cs.append('%s: %s is %s=%d & %s { local z:%d = zext(0:8); export z; }' % (name, f, raw, z[0], f, w))
                    fw = self.regfield({('R', 8): 'RD', ('R', 16): 'RQ', ('UR', 8): 'URD', ('UR', 16): 'URQ'}[(cls, w)], lo, hi)
                    cs.append('%s: %s is %s & %s { export %s; }' % (name, f, f, fw, fw))
                    self.tables[name] = cs
                return name
            src = role in ('s4', 'f4', 'p', 'x')
            name = 'S%s%d_%d%s' % (cls, lo, hi, '' if src else 'd')
            if name not in self.tables:
                cs = []
                if src and zero and cls in ('R', 'UR'):
                    cs.append('%s: %s is %s=%d & %s { export 0:4; }' % (name, f, raw, z[0], f))
                elif src and zero and cls in ('P', 'UP'):
                    cs.append('%s: %s is %s=%d & %s { export 1:1; }' % (name, f, raw, z[0], f))
                cs.append('%s: %s is %s { export %s; }' % (name, f, f, f))
                self.tables[name] = cs
            return name
        return self.slot_numeric(s, role)

    def slot_numeric(self, s, role):
        cls = s['cls']
        e = self.value_expr(s)
        key = '%s|%s|%s' % (cls, e, s.get('fmt', '') + ('pc' if s.get('pcrel') else ''))
        h = hashlib.sha1(key.encode()).hexdigest()[:8]
        if cls == 'flt':
            name = 'SF_%s' % h
            fmt = s['fmt']
            mt = re.match(r'f(32|64)t(\d+)$', fmt)
            if mt:
                # top bits of an f32/f64: show and export the full IEEE pattern
                wd, nt = int(mt.group(1)), int(mt.group(2))
                cons = '%s: v is epsilon [ v = (%s) << %d; ] { export *[const]:%d v; }' % (name, e, wd - nt, wd // 8)
            elif fmt == 'f64hi':
                cons = '%s: v is epsilon [ v = %s; ] { local t:8 = v; t = t << 32; export t; }' % (name, e)
            elif fmt == 'f16':
                cons = '%s: v is epsilon [ v = %s; ] { export *[const]:2 v; }' % (name, e)
            elif fmt == 'f64':
                cons = '%s: v is epsilon [ v = %s; ] { export *[const]:8 v; }' % (name, e)
            else:
                cons = '%s: v is epsilon [ v = %s; ] { export *[const]:4 v; }' % (name, e)
        elif s.get('pcrel'):
            name = 'ST_%s' % h
            if not self.wide:
                # 64-bit encodings were learned with the instruction at offset 8 of its bundle
                e = '(%s) - 8' % e
            cons = '%s: v is epsilon [ v = inst_start + %s; ] { export *:8 v; }' % (name, e)
        elif s.get('signed') and s.get('scale', 1) > 0:
            # print negative values as -0x.. (Ghidra would show the 64-bit two's complement)
            name = 'SI_%s' % h
            top = s['bits'][-1]
            tf = self.field(top, top)
            flds = sorted(set(re.findall(r'\bf\d+_\d+s?\b', e)))
            pat = ' & '.join(flds) if flds else 'epsilon'
            ws_ = 8 if len(s['bits']) + max(0, s.get('scale', 1).bit_length() - 1) > 32 else 4
            self.tables.setdefault(name, [
                '%s: v is %s & %s=0 [ v = %s; ] { export *[const]:%d v; }' % (name, pat, tf, e, ws_),
                '%s: "-"^nv is %s & %s=1 [ nv = 0 - (%s); ] { local t:%d = 0 - nv; export t; }' % (name, pat, tf, e, ws_)])
            return name
        else:
            name = 'SI_%s' % h
            wide = len(s['bits']) + max(0, s.get('scale', 1).bit_length() - 1) > 32
            cons = '%s: v is epsilon [ v = %s; ] { export *[const]:%d v; }' % (name, e, 8 if wide else 4)
        flds = sorted(set(re.findall(r'\bf\d+_\d+s?\b', e)))
        pat = ' & '.join(flds) if flds else 'epsilon'
        cons = cons.replace(' is epsilon ', ' is %s ' % pat)
        self.tables.setdefault(name, [cons])
        return name

    def slot_state_cons(self, s, state, kinds):
        bits = s['bits']
        rr = runs(bits)
        if state == 'max':
            return ['%s=%d' % (self.field(lo, hi), (1 << (hi - lo + 1)) - 1) for lo, hi in rr]
        if state == 'zero':
            return ['%s=0' % self.field(lo, hi) for lo, hi in rr]
        if state == 'neg':
            top = bits[-1]
            return ['%s=1' % self.field(top, top)]
        # generic state: no constraint - SLEIGH prefers the more specific special constructors
        return []

    # ------------------------------------------------------------ operand evaluation
    def eval_operand(self, items, role, form, pre):
        """items: operand items (str / ('s',k)).  Returns (slot tables, unused, value expr);
        p-code needed to compute the value is appended to pre."""
        slots = form['slots']
        shape = ''
        ks = []
        for it in items:
            if isinstance(it, tuple):
                shape += '$%d' % it[1]; ks.append(it[1])
            else:
                shape += it
        shape = shape.replace('.reuse', '').strip()
        tabs = {}
        def tab(k, r):
            t = self.slot_table(slots[k], r)
            tabs[k] = t
            return t
        def rest(skip=()):
            for k in ks:
                if k not in tabs and k not in skip:
                    tab(k, 'x')
        if role is None or role == 'x':
            rest()
            return tabs, [], None
        lit = shape.strip()
        if re.fullmatch(r'-?0x[0-9a-f]+', lit) and role in ('s4', 's8'):
            rest()
            v = int(lit, 16)
            return tabs, [], '0x%x:%d' % (v & ((1 << (8 * RSIZE[role])) - 1), RSIZE[role])
        if lit in ('RZ', 'URZ', 'PT', 'UPT', '!PT', '!UPT'):
            rest()
            if role in ('d4', 'd8', 'd16', 'pd'):
                return tabs, [], {1: 'DUMMYP', 4: 'DUMMY4', 8: 'DUMMY8', 16: 'DUMMY16'}[RSIZE[role]]
            if role == 'p':
                return tabs, [], '0:1' if lit.startswith('!') else '1:1'
            if role in ('s4', 's8', 'f4', 'f8'):
                return tabs, [], '0:%d' % RSIZE[role]
            return tabs, [], None
        if role in ('d4', 'd8', 'd16', 'pd'):
            m = re.fullmatch(r'\$(\d+)(\.[A-Z0-9_]+)*', shape)
            if not m:
                rest()
                return tabs, [], None
            k = int(m.group(1))
            v = tab(k, role if slots[k]['cls'] in ('R', 'UR', 'P', 'UP') else 'x')
            if role == 'pd' and slots[k]['cls'] not in ('P', 'UP'):
                return tabs, [], None
            if role != 'pd' and slots[k]['cls'] not in ('R', 'UR'):
                return tabs, [], None
            return tabs, [], v
        if role == 't':
            pk = [k for k in ks if slots[k].get('pcrel')]
            if pk:
                v = tab(pk[0], 't')
                rest()
                return tabs, [], v
            rest()
            return tabs, [], None
        if role == 'h':
            m = re.fullmatch(r'\$(\d+)', shape)
            if m and slots[int(m.group(1))]['cls'] == 'flt' and slots[int(m.group(1))].get('fmt') == 'f16':
                return tabs, [], tab(int(m.group(1)), 'x')
            rest()
            return tabs, [], None
        if role == 'sr':
            rest()
            m = re.fullmatch(r'(SR_[A-Z0-9_.]+|SRZ)', shape)
            if not m:
                return tabs, [], None
            if shape == 'SRZ':
                return tabs, [], '0:4'
            self.srs.add(srname(shape))
            return tabs, [], srname(shape)
        if role == 'a':
            m = re.fullmatch(r'(?:desc\[\$\d+\])?\[(.*)\]', shape)
            if not m:
                rest()
                return tabs, [], None
            terms = []
            for part in m.group(1).split('+'):
                if not part:
                    continue
                pm = re.fullmatch(r'(-?)\$(\d+)((?:\.[A-Z0-9_]+)*)', part)
                if not pm:
                    rest()
                    return tabs, [], None
                k = int(pm.group(2)); sfx = pm.group(3); c = slots[k]['cls']
                if c in ('R', 'UR'):
                    if '.64' in sfx:
                        terms.append(tab(k, 's8'))
                    else:
                        v = 'zext(%s)' % tab(k, 's4')
                        sc = re.search(r'\.X(\d+)', sfx)
                        if sc:
                            v = '(%s * %d)' % (v, int(sc.group(1)))
                        terms.append(v)
                elif c == 'hex':
                    terms.append('sext(%s)' % tab(k, 's4'))
                else:
                    rest()
                    return tabs, [], None
            rest()
            if not terms:
                terms = ['0:8']
            v = 'oa%d' % len(pre)
            pre.append('local %s:8 = %s;' % (v, ' + '.join(terms)))
            return tabs, [], v
        # sources with decorations
        m = re.fullmatch(r'(-?)(\|?)([~!]?)(.*?)(\|?)', shape)
        neg, ab, nt, core = m.group(1), m.group(2), m.group(3), m.group(4)
        core = re.sub(r'(\.(H0_H0|H1_H1|H0|H1|F32|B0|B1|B2|B3|U8|S8|U16|S16))+$', '', core)
        w = RSIZE.get(role, 4)
        isf = role in ('f4', 'f8')
        if role.startswith('cb'):
            w = int(role[2:]); isf = False
        cm = re.fullmatch(r'cx?\[\$(\d+)\] ?\[(.*)\]', core)
        if cm:
            kb = int(cm.group(1))
            terms = []
            for p in [p for p in cm.group(2).split('+') if p]:
                pm = re.fullmatch(r'\$(\d+)', p)
                if not pm:
                    rest()
                    return tabs, [], None
                terms.append(tab(int(pm.group(1)), 's4'))
            b = tab(kb, 's4')
            rest()
            v = 'oc%d' % len(pre)
            pre.append('local %sa:4 = %s * 0x10000 + %s;' % (v, b, ' + '.join(terms) if terms else '0'))
            pre.append('local %s:%d = *[cbank]:%d %sa;' % (v, w, w, v))
            val, vs = v, w
        else:
            km = re.fullmatch(r'\$(\d+)((?:\.[A-Z0-9_]+)*)', core)
            if not km:
                rest()
                return tabs, [], None
            k = int(km.group(1)); c = slots[k]['cls']
            if c in ('R', 'UR'):
                vs = 8 if w == 8 else (16 if w == 16 else 4)
                val = tab(k, {4: 's4', 8: 's8', 16: 's16'}[vs])
            elif c in ('P', 'UP'):
                val = tab(k, 'p'); vs = 1
            elif c == 'hex':
                val = tab(k, 's4'); vs = 4
            elif c == 'flt':
                fm = slots[k]['fmt']
                vs = {'f32': 4, 'f64hi': 8, 'f16': 2, 'f64': 8}.get(fm) or int(re.match(r'f(32|64)', fm).group(1)) // 8
                val = tab(k, 'x')
            else:
                val = tab(k, 'x'); vs = 4
            rest()
        if role.startswith('cb'):
            return tabs, [], val
        if role == 'p':
            if vs != 1:
                return tabs, [], None
            if nt == '!':
                v = 'op%d' % len(pre); pre.append('local %s:1 = !%s;' % (v, val)); val = v
            return tabs, [], val
        if vs == 1:
            return tabs, [], None
        if vs != w:
            v = 'oz%d' % len(pre)
            if vs < w:
                pre.append('local %s:%d = %s(%s);' % (v, w, 'zext' if isf else 'sext', val))
            else:
                pre.append('local %s:%d = %s:%d;' % (v, w, val, w))
            val = v
        if ab:
            v = 'ob%d' % len(pre)
            if isf:
                pre.append('local %s:%d = abs(%s);' % (v, w, val))
            else:
                pre.append('local %s:%d = sass_iabs(%s);' % (v, w, val))
                self.pcodeops.add('sass_iabs')
            val = v
        if nt:
            v = 'on%d' % len(pre)
            pre.append('local %s:%d = ~%s;' % (v, w, val)); val = v
        if neg:
            v = 'om%d' % len(pre)
            pre.append('local %s:%d = %s%s;' % (v, w, 'f- ' if isf else '-', val)); val = v
        return tabs, [], val

    # ------------------------------------------------------------ display
    def display_parts(self, items, slotnames):
        parts = []
        for it in items:
            if isinstance(it, tuple):
                parts.append(slotnames[it[1]] if it[0] == 's' else it[1])
            else:
                it = it.replace(', ', ',')
                if parts and parts[-1].startswith('"'):
                    parts[-1] = parts[-1][:-1] + it + '"'
                else:
                    parts.append('"%s"' % it)
        return parts

    # ------------------------------------------------------------ forms
    def segments(self, form):
        base = form['toks']
        U = units(base)
        n = len(base)
        slotpos = {k: s['pos'] for k, s in enumerate(form['slots'])}
        regs = []
        for gi, g in enumerate(form['groups']):
            if set(g['bits']) & set(GUARD_BITS):
                continue
            regs.append([g['lo'], g['hi'], [gi], []])
        Uall = units(base)
        for si, sp in enumerate(form.get('specials', [])):
            if 'gis' in sp:
                lo, hi = sp['lo'], sp['hi']
            else:
                a = slotpos[sp['slots'][0]]
                lo, hi = a + sp['rlo'], a + sp['rhi']
            us = {u for u in Uall[max(0, lo):hi] if u is not None}
            mchg = False
            if crosses_sep(Uall, lo, hi):
                for out in sp['cases'].values():
                    for t in (out or []):
                        if t == ' ':
                            break
                        if isinstance(t, str) and t.startswith('.'):
                            mchg = True
            if (-1 in us and len(us) > 1) or mchg:
                # special value changes the mnemonic: not representable as a segment
                self.stats['special_dropped'] += 1
                continue
            regs.append([lo, hi, list(sp.get('gis', [])), [si]])
        span = {}
        for i, u in enumerate(U):
            if u is not None and u >= 0:
                lo, hi = span.get(u, (i, i + 1))
                span[u] = (min(lo, i), max(hi, i + 1))
        def seg_units(lo, hi):
            if lo == hi:
                if lo < n and U[lo] is not None:
                    return {U[lo]}
                if lo > 0 and U[lo - 1] is not None:
                    return {U[lo - 1]}
                return set()
            return {u for u in U[lo:hi] if u is not None}
        def combos(r):
            t = 1
            for gi in r[2]:
                t *= max(1, sum(1 for o in form['groups'][gi]['table'].values() if o is not None))
            for si in r[3]:
                for k in form['specials'][si]['slots']:
                    t *= 1 + len(form['slots'][k].get('spec', []))
            return t
        # widen segments to whole operands, unless the operand would need too many constructors
        byunit = collections.defaultdict(list)
        for r in regs:
            us = seg_units(r[0], r[1])
            if len(us) == 1:
                u = next(iter(us))
                if u >= 0:
                    byunit[u].append(r)
        for u, rs in byunit.items():
            tot = 1
            for r in rs:
                tot *= combos(r)
            if tot <= 1024:
                for r in rs:
                    r[0] = min(r[0], span[u][0]); r[1] = max(r[1], span[u][1])
        def ov(a, b):
            (alo, ahi), (blo, bhi) = a, b
            if alo == ahi and blo == bhi:
                return alo == blo
            if alo == ahi:
                return blo < alo < bhi
            if blo == bhi:
                return alo < blo < ahi
            return alo < bhi and blo < ahi
        changed = True
        while changed:
            changed = False
            for a, b in itertools.combinations(regs, 2):
                if ov((a[0], a[1]), (b[0], b[1])):
                    regs.remove(a); regs.remove(b)
                    regs.append([min(a[0], b[0]), max(a[1], b[1]), a[2] + b[2], a[3] + b[3]])
                    changed = True
                    break
        return sorted(regs, key=lambda r: (r[0], r[1])), U, span

    def big_segment(self, form):
        """Index of the largest group of a segment needing more than SEG_MAX constructors."""
        try:
            segs, U, span = self.segments(form)
        except Exception:
            return None
        for lo, hi, gis, sis in segs:
            gis = sorted(set(gis))
            tot = 1
            for gi in gis:
                tot *= max(1, sum(1 for o in form['groups'][gi]['table'].values() if o is not None))
            for si in set(sis):
                for k in form['specials'][si]['slots']:
                    tot *= 1 + len(form['slots'][k].get('spec', []))
            if tot > SEG_MAX and gis:
                return max(gis, key=lambda gi: sum(1 for o in form['groups'][gi]['table'].values() if o is not None))
        return None

    def seg_table(self, form, seg, role):
        lo, hi, gis, sis = seg
        gis = sorted(set(gis)); sis = sorted(set(sis))
        n = len(form['toks'])
        w0 = int(form['seed'], 16)
        groups = [form['groups'][i] for i in gis]
        specs = [form['specials'][i] for i in sis]
        sslots = sorted({k for sp in specs for k in sp['slots']})
        kinds = {k: form['slots'][k].get('spec', []) for k in sslots}
        gvals = [[v for v, o in g['table'].items() if o is not None] for g in groups]
        svals = [[None] + list(kinds[k]) for k in sslots]
        total = 1
        for x in gvals + svals:
            total *= len(x)
        if total > SEG_MAX:
            raise Unsupported('segment too large')
        recs = []
        for gv in itertools.product(*gvals):
            for sv in itertools.product(*svals):
                w = w0
                c = []
                for g, v in zip(groups, gv):
                    for i, b in enumerate(g['bits']):
                        w = (w & ~(1 << b)) | (((v >> i) & 1) << b)
                    c += self.cons_bits(g['bits'], v)
                for k, st in zip(sslots, sv):
                    s = form['slots'][k]
                    nb = len(s['bits'])
                    val = {'max': (1 << nb) - 1, 'zero': 0, 'neg': (1 << (nb - 1)) | (0x5 & ((1 << (nb - 1)) - 1))}.get(st)
                    if val is not None:
                        for i, b in enumerate(s['bits']):
                            w = (w & ~(1 << b)) | (((val >> i) & 1) << b)
                    c += self.slot_state_cons(s, st, kinds[k])
                try:
                    items = render_items(form, w)
                except Exception:
                    items = None
                if items is None:
                    continue
                seg_items = items[lo:len(items) - (n - hi)]
                refs = [x for x in seg_items if isinstance(x, tuple)]
                if len(refs) != len(set(refs)):
                    self.stats['dup_slot_case'] += 1
                    continue
                pre = []
                op_items = list(seg_items)
                while op_items and op_items[0] in (', ', ' '):
                    op_items.pop(0)
                while op_items and op_items[-1] in (', ', ' '):
                    op_items.pop()
                tabs, _, val = self.eval_operand(op_items, role, form, pre)
                slotnames = dict(tabs)
                for it in seg_items:
                    if isinstance(it, tuple) and it[1] not in slotnames:
                        slotnames[it[1]] = self.slot_table(form['slots'][it[1]], 'x')
                parts = self.display_parts(seg_items, slotnames)
                ops = list(dict.fromkeys(p for p in parts if not p.startswith('"')))
                if parts and parts[-1].startswith('"') and parts[-1].endswith(' "'):
                    parts.append('GNUL'); ops.append('GNUL')
                if parts and parts[0].startswith('" '):
                    parts.insert(0, 'GNUL2'); ops.insert(0, 'GNUL2')
                disp = '^'.join(parts) if parts else '""'
                body = ' '.join(pre)
                if role is not None and role != 'x':
                    sz = RSIZE[role]
                    if val is None:
                        if role[0] == 'd' or role == 'pd':
                            val = {1: 'DUMMYP', 4: 'DUMMY4', 8: 'DUMMY8', 16: 'DUMMY16'}[sz]
                        else:
                            val = '0:%d' % sz
                    if re.fullmatch(r'(0x[0-9a-f]+|\d+):\d+', val):
                        if sz > 8:
                            body += ' local ex:%d = zext(%s:8); export ex;' % (sz, val.split(':')[0])
                        else:
                            body += ' local ex:%d = %s; export ex;' % (sz, val.split(':')[0])
                    else:
                        body += ' export %s;' % val
                recs.append((gv, sv, disp, c, ops, body))
        cons = self.collapse_numeric(groups, recs)
        if not cons:
            raise Unsupported('empty segment')
        return self.table('G', cons)

    def collapse_numeric(self, groups, recs):
        """Constructors of a segment that differ only in one hex literal which is a
        linear function of a large group's raw value (an immediate the learner kept
        as a modifier group) become one constructor computing the value."""
        def plain(r):
            gv, sv, disp, c, ops, body = r
            pat = ' & '.join(c + ops) if (c + ops) else 'epsilon'
            return '@@: %s is %s { %s }' % (disp, pat, body)
        big = [] if os.environ.get('SASS_NO_COLLAPSE') else [j for j, g in enumerate(groups) if len(g['bits']) >= 5 and sum(1 for o in g['table'].values() if o is not None) >= 32]
        if not big:
            return [plain(r) for r in recs]
        j = max(big, key=lambda j: len(groups[j]['bits']))
        g = groups[j]
        gcons = set(self.cons_bits(g['bits'], 0))
        gfields = {x.split('=')[0] for x in gcons}
        HEX = re.compile(r'-?0x[0-9a-f]+')
        EXP = re.compile(r'local ex:(\d+) = (0x[0-9a-f]+|\d+); export ex;')
        classes = collections.defaultdict(list)
        for k, r in enumerate(recs):
            gv, sv, disp, c, ops, body = r
            ms = list(HEX.finditer(disp))
            for i, m in enumerate(ms):
                tmpl = disp[:m.start()] + '#' + disp[m.end():]
                h = int(m.group(0), 16)
                be = EXP.search(body)
                btmpl = EXP.sub('#EX', body)
                rest = tuple(x for x in c if x.split('=')[0] not in gfields)
                key = (tuple(v for q, v in enumerate(gv) if q != j), sv, i, tmpl, btmpl, rest, tuple(ops),
                       be.group(1) if be else None)
                classes[key].append((gv[j], h, be, k))
        used = set()
        out = []
        for key, mem in sorted(classes.items(), key=lambda kv: -len(kv[1])):
            mem = [x for x in mem if x[3] not in used]
            if len(mem) < 16:
                continue
            mem.sort()
            (v0, h0, _, _), (v1, h1, _, _) = mem[0], mem[1]
            if (h1 - h0) % (v1 - v0):
                continue
            sc = (h1 - h0) // (v1 - v0); a = h0 - sc * v0
            if sc == 0 or any(h != a + sc * v for v, h, _, _ in mem):
                self.stats['collapse_nonlinear'] += 1
                continue
            neg = h0 < 0
            if any((h < 0) != neg for _, h, _, _ in mem):
                continue
            # the general constructor must not match more values than before: restrict
            # it to the cube of values the class shares, all of which must be valid
            nb = len(g['bits'])
            vals = [v for v, _, _, _ in mem]
            cm = (1 << nb) - 1
            for v in vals:
                cm &= ~(v ^ vals[0])
            cv = vals[0] & cm
            if any(g['table'].get(x, g['table'].get(str(x))) is None for x in range(1 << nb) if (x & cm) == cv):
                self.stats['collapse_invalid_cube'] += 1
                continue
            imask = ival = 0
            for i, b in enumerate(g['bits']):
                if (cm >> i) & 1:
                    imask |= 1 << b
                    ival |= ((cv >> i) & 1) << b
            sz = key[7]
            if sz is not None:
                msk = (1 << (8 * int(sz))) - 1
                if int(sz) > 8 or any(int(be.group(2), 0) != (h & msk) for _, h, be, _ in mem):
                    continue
            raw = self.value_expr({'bits': g['bits'], 'scale': 1, 'add': 0})
            fs = sorted(set(re.findall(r'f\d+_\d+s?', raw)))
            # magnitude shown: |a + sc*v|
            ms_, ma = (-sc, -a) if neg else (sc, a)
            e = '(%s)' % raw
            if ms_ < 0:
                e = '0 - %s * %d' % (e, -ms_)
            elif ms_ != 1:
                e = '%s * %d' % (e, ms_)
            if ma:
                e = '%s %s %d' % (e, '+' if ma > 0 else '-', abs(ma))
            r0 = recs[mem[0][3]]
            gvx, sv, disp, c, ops, body = r0
            tmpl, btmpl, rest = key[3], key[4], key[5]
            d = tmpl.replace('#', ('-' if neg else '') + '"^gnv^"', 1)
            d = re.sub(r'(^|\^)""(\^|$)', lambda m_: '^' if m_.group(1) and m_.group(2) else '', d).strip('^')
            act = '[ gnv = %s; ]' % e
            if sz is None:
                b = btmpl
            elif neg:
                b = btmpl.replace('#EX', 'local ex:%s = 0 - gnv; export ex;' % sz)
            else:
                b = btmpl.replace('#EX', 'export *[const]:%s gnv;' % sz)
            pat = ' & '.join(list(rest) + self.cons_mask(imask, ival) + list(ops) + fs)
            out.append('@@: %s is %s %s { %s }' % (d, pat, act, b))
            for x in mem:
                used.add(x[3])
            self.stats['numeric_collapsed'] += 1
        out += [plain(r) for k, r in enumerate(recs) if k not in used]
        return out

    def guard_table(self, g):
        cons = []
        for v, o in sorted(g['table'].items()):
            if o is None:
                continue
            txt = ''.join(o).strip()
            c = ' & '.join(self.cons_bits(g['bits'], v))
            if not txt:
                cons.append('@@: is %s { }' % c)
                continue
            m = re.match(r'^@(!?)(U?P)(\d|T)$', txt)
            if not m:
                raise Unsupported('guard %r' % txt)
            reg = m.group(2) + m.group(3)
            if m.group(1):
                sem = 'if (%s != 0) goto inst_next;' % reg if m.group(3) != 'T' else 'goto inst_next;'
            else:
                sem = 'if (%s == 0) goto inst_next;' % reg
            cons.append('@@: "%s "^GNUL is %s & GNUL { %s }' % (txt, c, sem))
        return self.table('GD', cons)

    def form_constructors(self, fid, form, cubes):
        base = form['toks']
        slots = form['slots']
        segs, U, span = self.segments(form)
        nops = max([u for u in U if u is not None] + [-1]) + 1
        slotpos = {s['pos']: k for k, s in enumerate(slots)}
        ops = []
        for u in range(nops):
            lo, hi = span[u]
            cov = [s for s in segs if s[0] <= lo and hi <= s[1]]
            shape = ''
            ks = []
            for i in range(lo, hi):
                if i in slotpos:
                    shape += '$%d' % slotpos[i]; ks.append(slotpos[i])
                else:
                    shape += base[i]
            shape = shape.replace('.reuse', '')
            ops.append(dict(shape=shape, slots=ks, classes=[slots[k]['cls'] for k in ks],
                            pcrel=any(slots[k].get('pcrel') for k in ks), seg=cov[0] if cov else None))
        # only modifiers that are literal in this form (not produced by a modifier group,
        # whose value varies) may drive the semantics
        ingroup = set()
        for g in form['groups']:
            if set(g['bits']) & set(GUARD_BITS):
                continue
            ingroup |= set(range(g['lo'], g['hi']))
        mnem = ''.join(base[i] for i, u in enumerate(U) if u == -1 and i not in ingroup)
        mods = re.findall(r'\.[A-Z0-9_?]+', mnem)
        info = dict(mn=form['mn'], mods=mods, ops=ops, text=form['text'])
        R = SEM.roles(info)
        if R is None or len(R) != len(ops):
            R = [None] * len(ops)
        segname = {}
        for si, seg in enumerate(segs):
            us = {u for u in U[seg[0]:seg[1]] if u is not None and u >= 0}
            role = None
            if len(us) == 1:
                u = next(iter(us))
                if span[u][0] >= seg[0] and span[u][1] <= seg[1]:
                    role = R[u]
            segname[si] = (self.seg_table(form, seg, role), role)
        guard = None
        for g in form['groups']:
            if set(g['bits']) & set(GUARD_BITS):
                guard = self.guard_table(g)
        # root items
        items = []
        segat = collections.defaultdict(list)
        for si, seg in enumerate(segs):
            segat[seg[0]].append((seg[1], si))
        i = 0
        n = len(base)
        while True:
            if i in segat:
                lst = sorted(segat.pop(i))
                jumped = False
                for hi, si in lst:
                    items.append(('T', segname[si][0]))
                    if hi > i:
                        i = hi; jumped = True
                        break
                if jumped:
                    continue
            if i >= n:
                break
            items.append(('s', slotpos[i]) if i in slotpos else base[i])
            i += 1
        # operand values
        pre = []
        opv = [None] * len(ops)
        slotnames = {}
        for u, o in enumerate(ops):
            lo, hi = span[u]
            if o['seg'] is not None:
                name, role = segname[segs.index(o['seg'])]
                if role is not None:
                    opv[u] = name
                continue
            if any(sg[0] < hi and lo < sg[1] or (sg[0] == sg[1] and lo < sg[0] < hi) for sg in segs):
                # operand only partially covered by a segment: no value for the p-code
                continue
            its = [('s', slotpos[i]) if i in slotpos else base[i] for i in range(lo, hi)]
            tabs, _, val = self.eval_operand(its, R[u], form, pre)
            slotnames.update(tabs)
            opv[u] = val
        for it in items:
            if isinstance(it, tuple) and it[0] == 's' and it[1] not in slotnames:
                slotnames[it[1]] = self.slot_table(slots[it[1]], 'x')
        try:
            sp = items.index(' ')
        except ValueError:
            sp = len(items)
        mparts = self.display_parts(items[:sp], slotnames)
        oparts = self.display_parts(items[sp + 1:], slotnames)
        if guard:
            mparts.insert(0, guard)
        if not mparts:
            raise Unsupported('no mnemonic')
        opnames = list(dict.fromkeys(p for p in mparts + oparts if not p.startswith('"')))
        disp = (':' if mparts[0].startswith('"') else ':^') + '^'.join(mparts)
        if oparts:
            disp += ' ' + '^'.join(oparts)
        body, op = SEM.pcode(info, opv, R)
        if op:
            self.pcodeops.add(op)
        self.pcodeops.update(re.findall(r'\b(sass_\w+)\(', body))
        sem = ' '.join(pre + [body])
        out = []
        for cube in cubes:
            pat = ' & '.join(self.cons_mask(*cube) + ([] if self.wide else ['ctl=0']) + opnames)
            out.append('%s is %s\n{ %s }' % (disp, pat, sem))
        self.stats['sem:' + ('generic' if op else ('none' if not body else 'real'))] += 1
        return out

    # ------------------------------------------------------------ dispatch
    def resolve(self):
        byop = collections.defaultdict(list)
        for i, f in enumerate(self.forms):
            byop[0 if is64(self.arch) else f['val'] & 0xfff].append(i)
        cubes = {}
        for op, ids in byop.items():
            def prio(i):
                f = self.forms[i]
                sc = f.get('score', {})
                tot = (sc.get('ok', 0) + sc.get('bad', 0) + sc.get('under', 0)) or 1
                acc = sc.get('ok', 0) / tot
                ok, bad = f.get('evidence', [0, 0])
                eacc = ok / (ok + bad) if ok + bad else 0.5
                return (-round(eacc, 2), -round(acc, 2), -ok, -bin(f['mask']).count('1'))
            ids.sort(key=prio)
            ids = [i for i in ids if not (self.forms[i].get('evidence', [0, 0])[1] > 2 * self.forms[i].get('evidence', [0, 0])[0])]
            placed = []
            for i in ids:
                f = self.forms[i]
                mine = [(f['mask'], f['val'])]
                for (m2, v2) in placed:
                    nxt = []
                    for (m, v) in mine:
                        common = m & m2
                        if (v & common) != (v2 & common):
                            nxt.append((m, v)); continue
                        if m != m2 and (m2 & ~m) == 0:
                            nxt.append((m, v)); continue
                        if m != m2 and (m & ~m2) == 0 and (KEEP_NESTED or bin(m2 & ~m).count('1') >= EXC_BITS):
                            # the placed cube is more specific: SLEIGH prefers it (nesting is
                            # re-checked after all forms are placed)
                            nxt.append((m, v)); continue
                        if m == m2:
                            continue
                        extra = [b for b in range(128) if (m2 >> b) & 1 and not (m >> b) & 1]
                        mm, vv = m, v
                        for b in extra:
                            nxt.append((mm | (1 << b), vv | (((~v2 >> b) & 1) << b)))
                            mm |= 1 << b
                            vv |= ((v2 >> b) & 1) << b
                        if bin(m & ~m2).count('1') >= EXC_BITS:
                            # a value-specific exception (alias with a fixed immediate,
                            # RZ operand ...): its overlap with the placed cube is strictly
                            # more specific than that cube, so SLEIGH prefers it there
                            nxt.append((mm, vv))
                    mine = nxt
                    if len(mine) > CUBE_CAP:
                        mine = mine[:CUBE_CAP]
                        self.stats['cube_cap'] += 1
                ev_ok = f.get('evidence', [0, 0])[0]
                if (len(mine) > 32 and ev_ok == 0) or (len(mine) > 96 and ev_ok < 500):
                    # an exotic form (never seen in real code or probes) that would need many
                    # root constructors to stay out of the way of better forms: leave it out
                    self.stats['dropped_exotic'] += 1
                    mine = []
                pset = {(m, v & m) for m, v in placed}
                mine = [(m, v) for m, v in mine if (m, v & m) not in pset]
                placed.extend(mine)
                cubes[i] = mine
                if not mine:
                    self.stats['dropped'] += 1
            # fix-up: a cube kept whole because a higher-priority cube was nested inside it
            # may have been split later so that the two only partly overlap; subtract then
            order = [(i, c) for i in ids for c in cubes.get(i, [])]
            for _ in range(4):
                changed = False
                new = {i: [] for i in ids}
                done = []
                for i, (m, v) in order:
                    pieces = [(m, v)]
                    for j, (m2, v2) in done:
                        if j == i:
                            continue
                        nxt = []
                        for (pm, pv) in pieces:
                            common = pm & m2
                            if (pv & common) != (v2 & common):
                                nxt.append((pm, pv)); continue
                            if pm == m2:
                                changed = True
                                continue    # identical to an earlier cube: drop
                            if (m2 & ~pm) == 0 or (pm & ~m2) == 0:
                                nxt.append((pm, pv)); continue
                            changed = True
                            extra = [b for b in range(128) if (m2 >> b) & 1 and not (pm >> b) & 1]
                            mm, vv = pm, pv
                            for b in extra:
                                nxt.append((mm | (1 << b), vv | (((~v2 >> b) & 1) << b)))
                                mm |= 1 << b
                                vv |= ((v2 >> b) & 1) << b
                        pieces = nxt
                    for p in pieces:
                        new[i].append(p)
                        done.append((i, p))
                seen = set()
                for i in ids:
                    u = []
                    for (pm, pv) in new[i]:
                        k = (pm, pv & pm)
                        if k not in seen:
                            seen.add(k); u.append((pm, pv))
                    new[i] = u
                order = [(i, c) for i in ids for c in new[i]]
                for i in ids:
                    cubes[i] = new[i]
                if not changed:
                    break
        return cubes

    def generate(self):
        keep = []
        for f in self.forms:
            def fltgroup(g):
                outs = [o for o in g['table'].values() if o]
                nf = sum(1 for o in outs if any(isinstance(t, str) and classify(t) and classify(t)[0] == 'flt'
                                                and not re.fullmatch(r'\d+', t) for t in o))
                return len(g['table']) > 16 and nf * 2 > len(outs)
            if any(fltgroup(g) for g in f['groups']):
                self.stats['skip_float_group'] += 1
                continue
            keep.append(f)
        # forms whose segments would need too many constructors are split on their
        # largest modifier group (each value becomes a root-level form)
        out = []
        work = list(keep)
        while work:
            f = work.pop()
            big = self.big_segment(f)
            if big is None:
                out.append(f)
                continue
            gi = big
            subs = []
            for v, o in sorted(f['groups'][gi]['table'].items()):
                if o is None:
                    continue
                sf = specialize(f, gi, v)
                if sf is None:
                    subs = None
                    break
                subs.append(sf)
            budget = f.get('_budget', 64)
            if subs is None or len(subs) > budget:
                out.append(f)
                continue
            for sf in subs:
                sf['_budget'] = budget // len(subs)
                sf['_root'] = f.get('_root', f)
            self.stats['split_forms'] += 1
            work.extend(subs)
        self.forms = out
        # forms whose constructors cannot be generated are left out and the patterns
        # resolved again, so that they do not leave holes in the forms they overlap
        for attempt in range(3):
            cubes = self.resolve()
            built = {}
            failed = []
            for i, f in enumerate(self.forms):
                if not cubes.get(i):
                    continue
                try:
                    built[i] = self.form_constructors(i, f, cubes[i])
                except Unsupported as e:
                    failed.append((i, 'unsupported:' + str(e)[:30]))
                except Exception as e:
                    failed.append((i, 'error:' + type(e).__name__))
            if not failed or attempt == 2:
                break
            bad = {i for i, _ in failed}
            self.forms = [f for i, f in enumerate(self.forms) if i not in bad]
            self.tables.clear(); self.tabkey.clear()
        for _, why in failed:
            self.stats[why] += 1
        for i, f in enumerate(self.forms):
            if i not in built:
                continue
            cs = built[i]
            self.stats['forms'] += 1
            self.used_forms.append(f)
            self.stats['constructors'] += len(cs)
            self.roots.append('# %s  [%s]\n' % (f['text'], f['seed']) + '\n'.join(cs))

    def emit(self, path):
        o = []
        o.append('# Generated by tools/gen_sleigh.py from spec/%s.json - do not edit.\n' % self.arch)
        if not self.wide:
            self.fields['f0_63'] = (0, 63, False)
        o.append('define token w128(128)' if self.wide else 'define token w64(64)')
        for n, (lo, hi, sg) in sorted(self.fields.items(), key=lambda x: (x[1][0], x[1][1], x[0])):
            o.append('  %s = (%d,%d)%s' % (n, lo, hi, ' signed' if sg else ''))
        o.append('  GNUL0 = (0,0)')
        o.append(';\n')
        if self.srs:
            o.append('define register offset=0x2000 size=4 [ %s ];' % ' '.join(sorted(self.srs)))
        for p in sorted(self.pcodeops):
            o.append('define pcodeop %s;' % p)
        for n, cls in sorted(self.attach.items()):
            o.append('attach variables [ %s ] [ %s ];' % (n, ' '.join(regnames(cls, self.fields[n][1] - self.fields[n][0] + 1))))
        o.append('GNUL: "" is GNUL0 { }')
        o.append('GNUL2: "" is GNUL0 { }')
        o.append('')
        for name, cs in self.tables.items():
            o.extend(cs)
        o.append('')
        if not self.wide:
            o.append('# scheduling control word at the start of every bundle')
            o.append('CTLW: v is f0_63 [ v = f0_63 + 0; ] { export *[const]:8 v; }')
            o.append(':"SCHED" CTLW is ctl=1 & CTLW { }')
        o.extend(self.roots)
        open(path, 'w').write('\n'.join(o) + '\n')

def regnames(cls, width):
    n = 1 << width
    out = []
    if cls in ('RD', 'RQ', 'URD', 'URQ'):
        for i in range(n):
            if cls == 'RD':
                out.append('RD%d' % i if i < 255 else 'RDZ')
            elif cls == 'RQ':
                out.append('RQ%d' % i if i <= 252 else 'RQZ')
            elif cls == 'URD':
                out.append('URD%d' % i if i < 63 else 'URDZ')
            else:
                out.append('URQ%d' % i if i % 4 == 0 and i <= 60 else 'RQZ')
        return out
    z = REGZ.get(cls)
    for i in range(n):
        if z and i == z[0]:
            out.append(z[1])
        elif cls == 'R' or (cls == 'UR' and i < 63) or (cls in ('P', 'UP') and i < 7) or (cls == 'B' and i < 16):
            out.append('%s%d' % (cls, i))
        else:
            out.append('_')
    return out

def main():
    from sassmodel import load_spec
    spec = load_spec(sys.argv[1])
    forms = [from_json(f) for f in spec['forms']]
    g = Gen(spec['arch'], forms)
    g.generate()
    g.emit(sys.argv[2])
    print(dict(g.stats), 'tables', len(g.tables), 'fields', len(g.fields))

if __name__ == '__main__':
    main()
