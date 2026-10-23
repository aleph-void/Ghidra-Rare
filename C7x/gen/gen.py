#!/usr/bin/env python3
"""Generate SLEIGH for the C7x from the black-box encoding database produced by infer.py/refine.py
and the constant-extension rules from probe_ext.py/anaext.py.

Usage: gen.py db.json ext_rules.json out_dir [SIL]
Writes: c7x_gen_SIL.sinc (tokens fields, subtables, instruction constructors)
        c7x_regs.sinc (register definitions that depend on observed names)
"""
import sys, json, re, os, collections
import semantics, c7parse

DB = json.load(open(sys.argv[1]))
EXT = json.load(open(sys.argv[2]))
OUT = sys.argv[3]
SIL = sys.argv[4] if len(sys.argv) > 4 else '7100'
semantics.VLEN = 32 if SIL.startswith('75') else 64

M64 = (1 << 64) - 1

# ---------------------------------------------------------------- token fields
FIELDS = {}          # name -> (lo, hi, signed, attach list or None)
EXTRA_FIELDS = [(0, 4), (0, 6), (0, 31), (8, 26), (5, 31), (5, 7), (5, 9), (8, 31), (8, 26), (10, 13), (14, 23),
                (27, 27), (27, 31), (0, 9), (14, 27), (28, 31), (24, 27), (20, 23), (16, 19), (12, 15), (8, 11), (7, 7), (1, 4)]

def fld(lo, hi, signed=False):
    name = '%s%d_%d' % ('s' if signed else 'b', lo, hi)
    FIELDS.setdefault(name, (lo, hi, signed, None))
    return name

ATTACH = {}          # (lo,hi,tuple(names)) -> fieldname
def attfld(lo, hi, names):
    key = (lo, hi, tuple(names))
    if key not in ATTACH:
        nm = 'r%d_%d_%s' % (lo, hi, re.sub(r'\d+$', '', names[0]) + re.search(r'\d+$', names[0]).group())
        while nm in FIELDS: nm += 'x'
        ATTACH[key] = nm
        FIELDS[nm] = (lo, hi, False, list(names))
    return ATTACH[key]

def runs(bits):
    """split sorted bit positions into contiguous runs [(lo,hi,firstindex)]"""
    out = []
    for n, b in enumerate(bits):
        if out and out[-1][1] == b - 1:
            out[-1][1] = b
        else:
            out.append([b, b, n])
    return out

def cons(bits, value):
    """constraint string for bits (list, ascending, value bit n = bits[n])"""
    parts = []
    for lo, hi, n in runs(sorted(bits)):
        # value bits for this run
        v = 0
        for i, b in enumerate(range(lo, hi + 1)):
            idx = bits.index(b)
            if value >> idx & 1: v |= 1 << i
        parts.append('%s=0x%x' % (fld(lo, hi), v))
    return ' & '.join(parts)

def mask_cons(mask, val):
    bits = [i for i in range(32) if mask >> i & 1]
    v = 0
    for n, b in enumerate(bits):
        if val >> b & 1: v |= 1 << n
    return cons(bits, v) if bits else ''

# ---------------------------------------------------------------- registers
REGNAMES = set()
def regbase(n):
    return n[:-2] if n.endswith('++') else n

def is_regname(n):
    return re.match(r'^[A-Z][A-Z0-9_]*$', n) is not None

# ---------------------------------------------------------------- subtables
TABLES = {}          # signature -> (name, [constructor lines])
COVER = {}           # table name -> list of conjunctions covering its matches (None = all)
def table(prefix, sig, build):
    if sig in TABLES:
        return TABLES[sig][0]
    name = '%s%d' % (prefix, len([1 for v in TABLES.values() if v[0].startswith(prefix)]))
    lines = build(name)
    TABLES[sig] = (name, lines)
    return name

REGSEQ = re.compile(r'^([A-Z]+)(\d+)$')

VECRE = re.compile(r'^(VB|VBL|VBM)\d+$|^SE\d|^CUCR\d+')
def rsize(x):
    return 'V' if VECRE.match(x) else 8

def build_rtables(bits, tab):
    """split by export size -> list of (tablename, size)"""
    out = []
    for sz in (8, 'V'):
        t = {v: (x if x is not None and rsize(x) == sz else None) for v, x in tab.items()}
        if any(x is not None for x in t.values()):
            out.append((build_rtable(bits, t), sz))
    return out

def build_rtable(bits, tab):
    """tab: {value: name or None}"""
    def b(name):
        lines = []
        done = set()
        contiguous = bits == list(range(bits[0], bits[-1] + 1))
        n = len(bits)
        if contiguous:
            for k in range(min(4, n), 0, -1):
                size = 1 << k
                for start in range(0, 1 << n, size):
                    if any(v in done for v in range(start, start + size)): continue
                    names = [tab.get(v) for v in range(start, start + size)]
                    if any(x is None for x in names): continue
                    m = [REGSEQ.match(x) for x in names]
                    if not all(m): continue
                    if len(set(x.group(1) for x in m)) != 1: continue
                    nums = [int(x.group(2)) for x in m]
                    if nums != list(range(nums[0], nums[0] + size)): continue
                    f = attfld(bits[0], bits[0] + k - 1, names)
                    c = []
                    if k < n:
                        c.append('%s=0x%x' % (fld(bits[0] + k, bits[-1]), start >> k))
                    c.append(f)
                    lines.append('%s: %s is %s { export %s; }' % (name, f, ' & '.join(c), f))
                    for x in names: REGNAMES.add(x)
                    done.update(range(start, start + size))
        for v in sorted(tab):
            x = tab[v]
            if x is None or v in done: continue
            rb = regbase(x)
            if rb == 'PC':      # PC-relative addressing uses the fetch-packet address
                lines.append('%s: "%s" is %s { local fp:8 = inst_start & 0xffffffffffffffc0; export fp; }' % (name, x, cons(bits, v)))
                continue
            REGNAMES.add(rb)
            lines.append('%s: "%s" is %s { export %s; }' % (name, x, cons(bits, v), rb))
        return lines
    sig = ('R', tuple(bits), tuple(sorted((v, x) for v, x in tab.items() if x is not None)))
    name = table('tR', sig, b)
    if name not in COVER:
        vals = [v for v, x in tab.items() if x is not None]
        bl = blocks(list(bits), vals)
        COVER[name] = None if (None in bl or '' in bl or not bl) else bl
    return name

# ---------- numeric tables -> decision tree of linear leaves
def linear(bits, entries):
    """entries: {x: value} complete over all 2^n x. returns (c, weights) or None"""
    n = len(bits)
    c = entries.get(0)
    if c is None: return None
    w = []
    for i in range(n):
        v = entries.get(1 << i)
        if v is None: return None
        w.append((v - c) & M64)
    for x, v in entries.items():
        s = c
        for i in range(n):
            if x >> i & 1: s += w[i]
        if (s & M64) != v: return None
    return c, w

def dtree(bits, entries, fixed, depth=0):
    """entries over 'bits' (free bits); fixed: dict bit->val. returns list of leaves (fixed, bits, c, w)"""
    valid = {x: v for x, v in entries.items() if v is not None}
    if not valid: return []
    if len(valid) == len(entries):
        lf = linear(bits, entries)
        if lf: return [(dict(fixed), list(bits), lf[0], lf[1])]
    if not bits: return [(dict(fixed), [], list(valid.values())[0], [])]
    if depth > 7: return None
    best = None
    for i in range(len(bits)):
        halves = []
        score = 0
        for bv in (0, 1):
            sub = {}
            for x, v in entries.items():
                if (x >> i & 1) == bv:
                    lo = x & ((1 << i) - 1); hi = x >> (i + 1)
                    sub[lo | (hi << i)] = v
            halves.append(sub)
            vv = {x: v for x, v in sub.items() if v is not None}
            if not vv: score += 2
            elif len(vv) == len(sub) and linear(bits[:i] + bits[i + 1:], sub): score += 2
        if best is None or score > best[0]:
            best = (score, i, halves)
    _, i, halves = best
    out = []
    for bv in (0, 1):
        f2 = dict(fixed); f2[bits[i]] = bv
        r = dtree(bits[:i] + bits[i + 1:], halves[bv], f2, depth + 1)
        if r is None: return None
        out += r
    return out

def expr_for(bits, c, w):
    """SLEIGH expression for c + sum w_i*bit_i, grouping runs with doubling weights.
    returns (expr, operands) where operands are field names used"""
    terms = []
    flds = []
    i = 0
    while i < len(bits):
        if w[i] == 0:
            i += 1; continue
        j = i
        while j + 1 < len(bits) and bits[j + 1] == bits[j] + 1 and w[j + 1] == (w[j] * 2) & M64:
            j += 1
        lo, hi = bits[i], bits[j]
        base = w[i]
        # signed run: top weight is negative (i.e. -2^k * base)
        signed = False
        if j > i and w[j] == (-(w[j - 1] * 2)) & M64:
            pass
        f = fld(lo, hi)
        flds.append(f)
        if base == 1: terms.append(f)
        elif base & (base - 1) == 0: terms.append('(%s << %d)' % (f, base.bit_length() - 1))
        else: terms.append('(%s * 0x%x)' % (f, base))
        i = j + 1
    return terms, flds

def fix_signed(bits, c, w):
    """detect sign bit: a weight that is -(2*prev) -> rewrite as run with sign: returns adjusted
    (bits,c,w) where negative top weight becomes positive weight and constant adjusted.
    value = c + ... + wtop*b ; with wtop = -2^k*s.  We keep mod-2^64 arithmetic so no change needed."""
    return bits, c, w

def leaf_expr(bits, c, w):
    terms, flds = expr_for(bits, c, w)
    e = ' + '.join(terms) if terms else ''
    if c:
        e = ('0x%x + ' % c) + e if e else '0x%x' % c
    if not e: e = '0'
    return e, flds

def build_ntable(bits, tab, extinfo, unitbase, signed5=False):
    entries = {}
    for v, x in tab.items():
        entries[int(v)] = None if x is None else (int(x, 16) if x.startswith('0x') else int(x)) & M64
    leaves = dtree(list(bits), entries, {})
    sig = ('N', tuple(bits), tuple(sorted(entries.items(), key=lambda t: t[0])), json.dumps(extinfo, sort_keys=True), signed5)
    def b(name):
        lines = []
        if leaves is None:
            # explicit
            for x, v in sorted(entries.items()):
                if v is None: continue
                lines.append('%s: "0x%x" is %s { export *[const]:8 0x%x; }' % (name, v, cons(bits, x), v))
            return lines
        for fixed, fb, c, w in leaves:
            fc = [cons([bb], vv) for bb, vv in sorted(fixed.items())]
            e, flds = leaf_expr(fb, c, w)
            pats = fc + [f for f in flds]
            simple = (len(flds) == 1 and e == flds[0])
            for f in flds: FIELDS[f] = FIELDS[f]
            patt = ' & '.join(pats) if pats else fld(0, 0)
            if simple and signed5 and FIELDS[flds[0]][1] - FIELDS[flds[0]][0] == 4:
                # 5-bit scalar constants are sign-extended by the hardware; dis7x prints them unsigned
                lines.append('%s: %s is %s { local sv:8 = (%s ^ 0x10) - 0x10; export sv; }' % (name, flds[0], patt, flds[0]))
            elif simple:
                lines.append('%s: %s is %s { export *[const]:8 %s; }' % (name, flds[0], patt, flds[0]))
            else:
                lines.append('%s: val is %s [ val = %s; ] { export *[const]:8 val; }' % (name, patt, e))
            # constant extension variants
            for ex in extinfo:
                n = ex['n']; det = ex['det']; form = ex['form']
                if any(int(bb) in fixed and fixed[int(bb)] != vv for bb, vv in det):
                    continue
                dc = []
                for bb, vv in det:
                    if int(bb) in fixed: continue
                    xn = 'x%d_%d' % (int(bb), int(bb))
                    FIELDS.setdefault(xn, (int(bb), int(bb), False, None))
                    dc.append('%s=0x%x' % (xn, vv))
                if form == 'mvk64':
                    continue
                sh, kind = form
                low = '(%s) & 0x%x' % (e, (1 << sh) - 1)
                hi = '(cx%d << %d)' % (n, sh)
                if kind == 's':
                    top = 27 + sh - 1
                    ve = '((%s | (%s)) ^ 0x%x) - 0x%x' % (hi, low, 1 << top, 1 << top)
                elif kind == 'u32':
                    ve = '(%s | (%s)) & 0xffffffff' % (hi, low)
                else:
                    ve = '%s | (%s)' % (hi, low)
                p2 = pats + dc + ['cx%dv=1' % n, 'cx%d' % n]
                lines.append('%s: val is %s [ val = %s; ] { export *[const]:8 val; }' % (name, ' & '.join(p2), ve))
        # MVK64 special
        if any(ex['form'] == 'mvk64' for ex in extinfo) and leaves and len(leaves) == 1:
            fixed, fb, c, w = leaves[0]
            fc = [cons([bb], vv) for bb, vv in sorted(fixed.items())]
            e, flds = leaf_expr(fb, c, w)
            pats = fc + flds
            low = '((%s) & 0x3ff)' % e
            lines.append('%s: val is %s & cx0v=1 & cx0 & cx1v=0 [ val = (cx0 << 10) | %s; ] { export *[const]:8 val; }' % (name, ' & '.join(pats), low))
            lines.append('%s: val is %s & cx0v=0 & cx1v=1 & cx1 [ val = (cx1 << 37) | %s; ] { export *[const]:8 val; }' % (name, ' & '.join(pats), low))
            lines.append('%s: val is %s & cx0v=1 & cx0 & cx1v=1 & cx1 [ val = (cx1 << 37) | (cx0 << 10) | %s; ] { export *[const]:8 val; }' % (name, ' & '.join(pats), low))
        return lines
    name = table('tN', sig, b)
    if name not in COVER:
        if leaves is None:
            bl = blocks(list(bits), [x for x, v in entries.items() if v is not None])
        else:
            bl = [(' & '.join(cons([bb], vv) for bb, vv in sorted(fx.items())) or None) for fx, fb, c, w in leaves]
        COVER[name] = None if (None in bl or '' in bl or not bl) else bl
    return name

# ---------- unit (crosspath X) tables
def blocks(bits, values):
    """cover a set of values over bits with aligned blocks -> list of constraint strings"""
    n = len(bits)
    vs = set(values)
    out = []
    contiguous = bits == list(range(bits[0], bits[-1] + 1)) if bits else False
    done = set()
    for k in range(n, -1, -1):
        size = 1 << k
        for start in range(0, 1 << n, size):
            blk = set(range(start, start + size))
            if blk <= vs and not (blk & done):
                if contiguous and k > 0:
                    if k == n:
                        out.append(None)  # always
                    else:
                        out.append('%s=0x%x' % (fld(bits[0] + k, bits[-1]), start >> k))
                elif k == 0:
                    out.append(cons(bits, start))
                else:
                    # non-contiguous: fix upper (by index) bits
                    hb = bits[k:]
                    out.append(cons(hb, start >> k))
                done |= blk
    return out

def build_utable(unitbase, xinfo):
    sig = ('U', unitbase, json.dumps(xinfo, sort_keys=True))
    def b(name):
        if xinfo == 'always':
            return ['%s: "%sX" is %s {}' % (name, unitbase, fld(0, 0))]
        lines = ['%s: "%s" is %s {}' % (name, unitbase, fld(0, 0))]
        per = []
        for bits, vals in xinfo:
            per.append([c for c in blocks(bits, vals)])
        # single and combination constructors (to resolve overlaps)
        import itertools
        seen = set()
        for r in range(1, len(per) + 1):
            for combo in itertools.combinations(range(len(per)), r):
                for prod in itertools.product(*[per[i] for i in combo]):
                    cs = [c for c in prod if c]
                    key = tuple(sorted(cs))
                    if key in seen or not cs: continue
                    seen.add(key)
                    lines.append('%s: "%sX" is %s {}' % (name, unitbase, ' & '.join(cs)))
        return lines
    return table('tU', sig, b)

# ---------- predicate tables
CCSLOT = {'.L1': (0, 'ccL1'), '.L2': (0, 'ccL2'), '.S1': (0, 'ccS1'), '.S2': (0, 'ccS2'),
          '.D1': (0, 'ccD1'), '.D2': (0, 'ccD2'), '.M1': (1, 'ccM1'), '.M2': (1, 'ccM2'),
          '.C2': (1, 'ccC'), '.P2': (1, 'ccP'), '.N1': (1, 'ccN1'), '.N2': (1, 'ccN2')}
PREDNAME = re.compile(r'^(!?)A([0-5])$')

def pred_sem(txt):
    m = PREDNAME.match(txt)
    neg, r = m.group(1), m.group(2)
    return 'if (A%s %s 0) goto inst_next;' % (r, '!=' if neg else '==')

def build_ptable(unitbase, ptab):
    """ptab: None (no embedded predicate) or (bits, {v: text})"""
    sig = ('P', unitbase, json.dumps(ptab, sort_keys=True))
    def b(name):
        lines = []
        slot = CCSLOT.get(unitbase)
        emb = ''
        if slot:
            w, nib = slot
            emb = ' & cc%dv=0' % w
            lines.append('%s: is cc%dv=1 & %s=0 {}' % (name, w, nib))
            for v in range(2, 14):
                txt = '%sA%d' % ('!' if v & 1 else '', (v >> 1) - 1)
                lines.append('%s: "[%s]" is cc%dv=1 & %s=%d { %s }' % (name, txt, w, nib, v, pred_sem(txt)))
        if ptab is None:
            lines.append('%s: is %s%s {}' % (name, fld(0, 0), emb))
        else:
            bits, tab = ptab
            for v, t in sorted(tab.items(), key=lambda x: int(x[0])):
                if t is None and int(v) == 0:
                    t = ''          # creg 0 = unconditional (dis7x then shows the un-predicated key)
                if t is None: continue
                c = cons(bits, int(v))
                if t == '':
                    lines.append('%s: is %s%s {}' % (name, c, emb))
                else:
                    lines.append('%s: "[%s]" is %s%s { %s }' % (name, t, c, emb, pred_sem(t)))
        return lines
    return table('tP', sig, b)

# ---------------------------------------------------------------- per key
def ext_for(key, atomidx):
    """extension info for atom (0-based atom index) of key"""
    out = []
    forms = {}
    for e in EXT.get(key, EXT.get(key.split('#')[0], [])):
        if e['atom'] != atomidx: continue
        fm = e['form']
        if not fm or 'None' in fm[0]: continue
        f = eval(fm[0])[1]
        forms[e['n']] = (e, f)
    if 0 in forms and 1 in forms and forms[0][1][0] == 10:
        return [dict(n=0, det=[], form='mvk64')]
    for n, (e, f) in forms.items():
        out.append(dict(n=n, det=[[int(a), b] for a, b in e['det']], form=list(f)))
    return out

# mnemonics implemented by hand in c7x.sinc (unit-less group, indirect branch/call)
HANDWRITTEN = {'NOP', 'IDLE', 'PROTCLR', 'TICK', 'EHDL', 'IINVAL', 'MTAG', 'DHDL', 'PROT', 'UNPROT', 'DSWBP',
               'ESWBP', 'DDBG', 'MARK', 'EDBG', 'MFENCE', 'MFENCEST', 'BA', 'CALLA', 'MVCI', 'RET', 'RETS', 'B', 'BE', 'CALL', 'CALLE', 'BNL'}

SIGNED5 = re.compile(r'^V?(ADD|SUB|SUBR|AND|ANDN|OR|ORN|XOR|XNOR|NAND|NOR|CMP|MPY|MAX|MIN|SADD|SSUB)')

CSTX_CLASH = [(0x1e, 0x16), (0x1e, 0x1e), (0x7e, 0x1c), (0x7e, 0x5c)]

def gen_key(k, r, out):
    if r['unitbase'] == '.B1' and any(a.get('manual') for a in r['atom'].values()):
        return False
    if k.startswith('B|.B1||') or k.startswith('CALL|.B1||') or k.startswith('BNL|.B1||'):
        return False
    if r['mn'] in HANDWRITTEN:
        return 'handwritten'
    kinds = r['kinds']
    skel = r['skel']
    ex_atoms = c7parse.parse(r['example'])['atoms']
    ops = []          # per atom: list of alternatives (operand, sizeclass)
    for j in range(2, len(kinds)):
        a = r['atom'].get(str(j))
        kind = kinds[j]
        if a is None:
            ops.append([(('CONST', ex_atoms[j - 2][1]), 'C')])
            continue
        if a.get('manual'):
            return 'manual'
        if len(a['bits']) > 10 and kind == 'R':
            return 'bigR'
        tab = a['table']
        t = {int(v): (e[0] if e else None) for v, e in tab.items()}
        if kind == 'R':
            alts = build_rtables(a['bits'], t)
            if not alts: return 'emptyR'
            ops.append(alts)
        elif kind == 'N':
            ops.append([(build_ntable(a['bits'], t, ext_for(k, j - 2), r['unitbase'],
                                      bool(SIGNED5.match(r['mn']))), 'N')])
        else:
            return 'label'
    # EXT/EXTU/REPLACE/VREPLACE with E=1: csta = field | (cstx & 1) << 5, cstb = (cstx >> 1) & 0x3f
    if r['mn'] in ('EXT', 'EXTU', 'REPLACE', 'VREPLACE') and len(kinds) == 6 and '3' in r['atom'] \
            and '4' not in r['atom']:
        for e in EXT.get(k, []):
            if not (e['form'] and 'None' in e['form'][0]): continue
            if not all((r['fixed_mask'] >> int(b)) & 1 and ((r['fixed_val'] >> int(b)) & 1) == v for b, v in e['det']):
                continue
            n = e['n']; bits = r['atom']['3']['bits']
            f = fld(bits[0], bits[-1])
            def ba(name, f=f, n=n):
                return ['%s: %s is %s & cx%dv=0 { export *[const]:8 %s; }' % (name, f, f, n, f),
                        '%s: val is %s & cx%dv=1 & cx%d [ val = %s | ((cx%d & 1) << 5); ] { export *[const]:8 val; }'
                        % (name, f, n, n, f, n)]
            def bb(name, n=n):
                return ['%s: "0" is cx%dv=0 { export 0:8; }' % (name, n),
                        '%s: val is cx%dv=1 & cx%d [ val = (cx%d >> 1) & 0x3f; ] { export *[const]:8 val; }' % (name, n, n, n)]
            ops[1] = [(table('tXA', ('XA', f, n), ba), 'N')]
            ops[2] = [(table('tXB', ('XB', n), bb), 'N')]
            break
    # EXTV/EXTUV with E=1 (bit 25): the 2nd and 3rd constants come only from the extension slot:
    # c2 = cstx & 0x3f, c3 = (cstx >> 8) & 0x3f   (.L2 -> CSTX1, .S2 -> CSTX0)
    if r['mn'] in ('EXTV', 'EXTUV') and len(kinds) == 7 and '4' not in r['atom'] and '5' not in r['atom'] \
            and (r['fixed_mask'] >> 25) & 1 and (r['fixed_val'] >> 25) & 1:
        n = 1 if r['unitbase'] in ('.L2', '.L1') else 0
        for idx, (sh, nm) in ((2, (0, 'tVA')), (3, (8, 'tVB'))):
            def bv(name, n=n, sh=sh):
                return ['%s: "0" is cx%dv=0 { export 0:8; }' % (name, n),
                        '%s: val is cx%dv=1 & cx%d [ val = (cx%d >> %d) & 0x3f; ] { export *[const]:8 val; }'
                        % (name, n, n, n, sh)]
            ops[idx] = [(table(nm, (nm, n), bv), 'N')]
    # store-a-constant: the data constant comes entirely from a constant-extension slot
    # (.D1 -> CSTX0, .D2 -> CSTX1), sign-extended from 27 bits; 0 without one
    if re.match(r'^V?STK\d*[WD]$', r['mn']) and kinds[2] == 'N' and '2' not in r['atom']:
        n = 0 if r['unitbase'] == '.D1' else 1
        def bk(name, n=n):
            return ['%s: "0" is cx%dv=0 { export 0:8; }' % (name, n),
                    '%s: val is cx%dv=1 & cx%d [ val = (cx%d ^ 0x4000000) - 0x4000000; ] { export *[const]:8 val; }'
                    % (name, n, n, n)]
        ops[0] = [(table('tSK', ('SK', n), bk), 'N')]
    # unit
    uname = None
    if r['unitbase']:
        xinfo = []
        anyx = False
        for j in range(2, len(kinds)):
            a = r['atom'].get(str(j))
            if a is None: continue
            xs = [int(v) for v, e in a['table'].items() if e and e[1]]
            if xs:
                anyx = True
                xinfo.append((a['bits'], sorted(xs)))
        allx = anyx and all(e is None or e[1] for j in range(2, len(kinds)) if str(j) in r['atom']
                            for e in r['atom'][str(j)]['table'].values())
        ex_unit = c7parse.parse(r['example'])['unit']
        if ex_unit.endswith('X') and not anyx:
            # X flags were not observed: infer them from the register side (operand names)
            opp = r'^(B|BL|BM|VB|VBL|VBM)\d+$' if r['unitbase'].endswith('1') else r'^(A|AL|AM)\d+$'
            for j in range(2, len(kinds)):
                a = r['atom'].get(str(j))
                if a is None or kinds[j] != 'R': continue
                xs = [int(v) for v, e in a['table'].items() if e and re.match(opp, e[0])]
                if xs:
                    anyx = True
                    xinfo.append((a['bits'], sorted(xs)))
            if not anyx and not any(e for j in range(2, len(kinds)) if str(j) in r['atom']
                                    for e in r['atom'][str(j)].get('table', {}).values()):
                xinfo = 'always'
        elif allx:
            xinfo = 'always'
        uname = build_utable(r['unitbase'], xinfo)
    # predicate
    ptab = None
    if r['haspred']:
        a = r['atom'].get('1')
        if a is None or a.get('manual'):
            return 'pred'
        ptab = (a['bits'], {v: (e[0] if e else None) for v, e in a['table'].items()})
    pname = build_ptable(r['unitbase'], ptab)
    mn = r['mn']
    fm, fv = r['fixed_mask'], r['fixed_val']
    base_patt = []
    mc = mask_cons(fm, fv)
    if mc: base_patt.append(mc)
    for m, v in CSTX_CLASH:
        if (fm & m) == m and (fv & m) == v:
            base_patt.append('pbit=0')
    base_patt.append(pname)
    if uname: base_patt.append(uname)
    # an un-predicated key must not match words of its predicated sibling: constrain the sibling's
    # predicate field to the values seen in this key's samples (those the sibling has no name for)
    if not r['haspred']:
        base = k.split('#')[0]
        used = set(b for a in r['atom'].values() for b in a.get('bits', []))
        for pk in PRED_SIBLINGS.get(base + 'P', []):
            a = DB[pk]['atom'].get('1')
            if not a or a.get('manual'): continue
            pb = a['bits']
            if any(b in used for b in pb): continue
            seen = set()
            for w in r['samples']:
                seen.add(sum(((w >> b) & 1) << i for i, b in enumerate(pb)))
            if any(a['table'].get(str(v)) for v in seen): continue
            alts = ['(%s)' % cons(pb, v) for v in sorted(seen)]
            base_patt.append(alts[0][1:-1] if len(alts) == 1 else '(' + ' | '.join(alts) + ')')
            break
    import itertools
    for choice in itertools.product(*ops):
        disp = []
        pieces = re.split(r'([RNL])', skel)
        ai = 0
        opnames = []
        seen = collections.Counter()
        for pc in pieces:
            if pc in ('R', 'N', 'L'):
                t = choice[ai][0]; ai += 1
                if isinstance(t, tuple):
                    disp.append('"%s"' % t[1]); opnames.append((None, t)); continue
                seen[t] += 1
                opn = t if seen[t] == 1 else '%s_%d' % (t, seen[t])
                opnames.append((opn, t))
                disp.append(opn)
            elif pc:
                disp.append('"%s"' % pc)
        head = '%s^"%s"' % (pname, mn)
        if uname: head += ' ' + uname
        if disp: head += ' ' + '^'.join(disp)
        patt = base_patt + [o for o, t in opnames if o]
        body = semantics.sem(mn, r['unitbase'], skel, [o if o else t for o, t in opnames],
                             [c[1] for c in choice], r)
        out.append(dict(mn=mn, opnames=opnames, head=head, patt=patt, pname=pname, body=body, fm=fm, fv=fv,
                        pb0=('pbit=0' in patt)))
    return True

CRE = re.compile(r'\bb(\d+)_(\d+)=0x([0-9a-f]+)')
def forced(cv):
    """bits fixed to the same value by every alternative of a coverage list"""
    res = None
    for alt in cv:
        d = {}
        for m in CRE.finditer(alt):
            lo, hi, v = int(m.group(1)), int(m.group(2)), int(m.group(3), 16)
            for b in range(lo, hi + 1): d[b] = (v >> (b - lo)) & 1
        res = d if res is None else {b: v for b, v in res.items() if d.get(b) == v}
    return res or {}

PRED_SIBLINGS = collections.defaultdict(list)
for _k in sorted(DB):
    if _k.split('#')[0].endswith('|P'):
        PRED_SIBLINGS[_k.split('#')[0]].append(_k)

FIXED = {}
for f in ('A', 'AL', 'AM', 'D', 'B', 'BL', 'BM', 'VB', 'VBL', 'VBM'):
    for i in range(16): FIXED['%s%d' % (f, i)] = 1
for i in range(8): FIXED['P%d' % i] = 1
for i in range(4): FIXED['SA%d' % i] = 1
for n in ('SE0', 'SE1', 'PC', 'RP'): FIXED[n] = 1

def write_regs(path):
    names = set(REGNAMES) | set(FIXED)
    scal = []; vec = []
    for n in sorted(names):
        if re.match(r'^(A|AL|AM|D|B|BL|BM|VB|VBL|VBM)\d+$', n): continue
        if re.match(r'^(SE\d|CUCR\d+)$', n): vec.append(n)
        else: scal.append(n)
    L = ['# GENERATED by gen/gen.py -- register file']
    L.append('define register offset=0x0000 size=8 [ %s ];' % ' '.join('A%d' % i for i in range(16)))
    L.append('define register offset=0x0080 size=8 [ %s ];' % ' '.join('AL%d' % i for i in range(16)))
    L.append('define register offset=0x0100 size=8 [ %s ];' % ' '.join('AM%d' % i for i in range(16)))
    L.append('define register offset=0x0180 size=8 [ %s ];' % ' '.join('D%d' % i for i in range(16)))
    L.append('define register offset=0x20000 size=8 [ %s ];' % ' '.join(scal))
    for f, off in (('VB', 0x4000), ('VBL', 0x6000), ('VBM', 0x8000)):
        for i in range(16):
            L.append('define register offset=0x%x size=$(VLEN) [ %s%d ];' % (off + i * 0x40, f, i))
            L.append('define register offset=0x%x size=8 [ %s%d ];' % (off + i * 0x40, f[1:], i))
    for i, n in enumerate(vec):
        L.append('define register offset=0x%x size=$(VLEN) [ %s ];' % (0xa000 + i * 0x40, n))
    open(path, 'w').write('\n'.join(L) + '\n')

def main():
    for lo, hi in EXTRA_FIELDS: fld(lo, hi)
    fld(8, 31, True); fld(8, 26, True)
    out = []
    skipped = collections.Counter()
    for k in sorted(DB):
        r = DB[k]
        res = gen_key(k, r, out)
        if res is not True:
            skipped[str(res)] += 1
    # constructors referencing the same subtable twice need aliases
    lines = []
    lines.append('# GENERATED by gen/gen.py from the dis7x-derived encoding database -- do not edit')
    lines.append('')
    sub_alias = set()
    instr_lines = []
    # constructors whose own fixed bits overlap another's: add explicit coverage constraints of
    # their subtable operands (SLEIGH does not reliably disambiguate through subtable patterns)
    overl = [False] * len(out)
    byunit = collections.defaultdict(list)
    for i, c in enumerate(out):
        byunit[(c['fv'] & 0x1e) if (c['fm'] & 0x1e) == 0x1e else None].append(i)
    groups = list(byunit.values())
    allidx = list(range(len(out)))
    for i, c in enumerate(out):
        cand = byunit[(c['fv'] & 0x1e) if (c['fm'] & 0x1e) == 0x1e else None] + byunit.get(None, [])
        if (c['fm'] & 0x1e) != 0x1e: cand = allidx
        for j in cand:
            if j == i: continue
            d = out[j]
            if (c['fv'] ^ d['fv']) & c['fm'] & d['fm'] & ~1: continue
            overl[i] = True; break
    nover = 0
    ndropped = 0
    for i, c in enumerate(out):
        patt = list(c['patt'])
        if overl[i]:
            nover += 1
            # drop constructors whose operand coverages force contradictory bit values
            fb = {b: (c['fv'] >> b) & 1 for b in range(32) if c['fm'] >> b & 1}
            bad = False
            for opn, t in c['opnames']:
                cv = COVER.get(t) if opn else None
                if not cv: continue
                for b, v in forced(cv).items():
                    if fb.setdefault(b, v) != v: bad = True
            if bad:
                ndropped += 1
                continue
            for opn, t in c['opnames']:
                if not opn: continue
                cv = COVER.get(t)
                if cv:
                    patt.insert(len(patt) - len(c['opnames']), '(' + ' | '.join('(%s)' % x for x in cv) + ')' if len(cv) > 1 else cv[0])
        for opn, t in c['opnames']:
            if opn and opn != t:
                sub_alias.add((opn, t))
        instr_lines.append('instr: %s is %s { build %s; %s }' % (c['head'], ' & '.join(patt), c['pname'], c['body']))
    print('overlapping constructors', nover, 'dropped (contradictory coverage)', ndropped, file=sys.stderr)
    # aliases: duplicate the table under a new name
    tabs = {v[0]: v[1] for v in TABLES.values()}
    for opn, t in sorted(sub_alias):
        tabs[opn] = [re.sub(r'^%s:' % t, '%s:' % opn, l) for l in tabs[t]]
    with open(os.path.join(OUT, 'c7x_gen_%s.sinc' % SIL), 'w') as f:
        f.write('\n'.join(lines) + '\n')
        for name in sorted(tabs):
            f.write('\n'.join(tabs[name]) + '\n')
        f.write('\n')
        f.write('\n'.join(instr_lines) + '\n')
    with open(os.path.join(OUT, 'c7x_fields_%s.sinc' % SIL), 'w') as f:
        f.write('# GENERATED by gen/gen.py -- token fields and register attachments\n')
        f.write('define token I(32)\n')
        f.write('  pbit=(0,0)\n')
        for name in sorted(FIELDS):
            lo, hi, s, att = FIELDS[name]
            f.write('  %s=(%d,%d)%s\n' % (name, lo, hi, ' signed' if s else ''))
        f.write(';\n')
        for name in sorted(FIELDS):
            lo, hi, s, att = FIELDS[name]
            if att:
                f.write('attach variables [ %s ] [ %s ];\n' % (name, ' '.join(att)))
    write_regs(os.path.join(OUT, 'c7x_regs_%s.sinc' % SIL))
    with open(os.path.join(OUT, 'c7x_ops_%s.sinc' % SIL), 'w') as f:
        f.write('# GENERATED by gen/gen.py -- pcodeops used by generated semantics\n')
        for op in sorted(semantics.PCODEOPS):
            f.write('define pcodeop %s;\n' % op)
    print('constructors', len(instr_lines), 'tables', len(tabs), 'skipped', dict(skipped), file=sys.stderr)

if __name__ == '__main__':
    main()
