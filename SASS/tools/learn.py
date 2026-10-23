#!/usr/bin/env python3
"""Black-box encoding learner for 128-bit NVIDIA SASS (Volta and later), driven by nvdisasm.

Given a seed word the learner flips every display bit, compares the token lists
and derives a *form* (see sassmodel.py):

  1. "reveal": greedily flip bits that make hidden operands appear, so that as
     many value fields as possible are visible;
  2. find value slots (single token substitutions of the same class whose deltas
     are powers of two), re-seed with generic slot values, analyse again;
  3. group the remaining bits by overlapping token regions and enumerate every
     group exhaustively; bits that change the base mnemonic, bits that make the
     word illegal, and bits whose group would grow too large become fixed;
  4. probe special slot values (zero / all-ones / negative) and record how they
     change the surrounding text;
  5. validate the form on random words and report agreement.

Everything is inferred from nvdisasm output only.
"""
import sys, os, re, json, random, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import nvd
from sassmodel import (tokenize, classify, mnem_of, render, render_tokens, same_text, fmt_value,
                       slot_raw, slot_value, flt_match, FLTFMT, REGZ, RenderConflict, bit, group_value, render_items)

OPC_BITS = list(range(0, 12))
LEARN_BITS = list(range(12, 105)) + [122, 123, 124, 125]
CTRL_MASK = sum(1 << b for b in list(range(105, 122)) + [126, 127])
CTRL_STD = (0x000fe4 << 104) & CTRL_MASK    # stall 2, no barriers: lets nvdisasm show .reuse
GUARD_BITS = [12, 13, 14, 15]
REUSE_BITS = [122, 123, 124, 125]
SHIFT_MULT = 1          # physical/logical address ratio of the oracle (64-bit bundles: 4)
MAXG = 10

def set_profile(arch):
    """Select the bit layout for 128-bit (Volta+) or 64-bit (Maxwell/Pascal) encodings."""
    global OPC_BITS, LEARN_BITS, CTRL_MASK, CTRL_STD, GUARD_BITS, REUSE_BITS, SHIFT_MULT
    if nvd.isz_of(arch) == 8:
        OPC_BITS = []
        LEARN_BITS = list(range(0, 64))
        CTRL_MASK = 0
        CTRL_STD = 0
        GUARD_BITS = [18, 19, 20, 21] if arch in nvd.KEPLER else [16, 17, 18, 19]
        REUSE_BITS = []
        SHIFT_MULT = nvd.bundle_of(arch)[0]
    else:
        OPC_BITS = list(range(0, 12))
        LEARN_BITS = list(range(12, 105)) + [122, 123, 124, 125]
        CTRL_MASK = sum(1 << b for b in list(range(105, 122)) + [126, 127])
        CTRL_STD = (0x000fe4 << 104) & CTRL_MASK    # stall 2, no barriers: lets nvdisasm show .reuse
        GUARD_BITS = [12, 13, 14, 15]
        REUSE_BITS = [122, 123, 124, 125]
        SHIFT_MULT = 1
# Modifiers that p-code semantics depend on: for these mnemonics, groups that
# print one of the listed modifiers are fixed (each value becomes its own form).
_CMP = {'.F', '.LT', '.EQ', '.LE', '.GT', '.NE', '.GE', '.T', '.NUM', '.NAN', '.LTU', '.EQU', '.LEU',
        '.GTU', '.NEU', '.GEU', '.AND', '.OR', '.XOR', '.U32', '.EX'}
_SIZE = {'.U8', '.S8', '.U16', '.S16', '.64', '.128', '.U.128', '.32'}
CORE_MODS = {
    'IADD3': {'.X'}, 'UIADD3': {'.X'},
    'IMAD': {'.WIDE', '.HI', '.X', '.U32', '.MOV', '.SHL', '.IADD'},
    'UIMAD': {'.WIDE', '.HI', '.X', '.U32', '.MOV', '.SHL', '.IADD'},
    'LOP3': {'.LUT', '.PAND'}, 'ULOP3': {'.LUT', '.PAND'}, 'PLOP3': {'.LUT'}, 'UPLOP3': {'.LUT'},
    'SHF': {'.L', '.R', '.W', '.U32', '.S32', '.U64', '.S64', '.HI'},
    'USHF': {'.L', '.R', '.W', '.U32', '.S32', '.U64', '.S64', '.HI'},
    'ISETP': _CMP, 'UISETP': _CMP, 'FSETP': _CMP, 'DSETP': _CMP,
    'LEA': {'.HI', '.X', '.SX32'}, 'ULEA': {'.HI', '.X', '.SX32'},
    'IMNMX': {'.U32'}, 'UIMNMX': {'.U32'},
    'LDG': _SIZE, 'STG': _SIZE, 'LD': _SIZE, 'ST': _SIZE, 'LDS': _SIZE, 'STS': _SIZE,
    'LDL': _SIZE, 'STL': _SIZE, 'LDC': _SIZE, 'ULDC': _SIZE,
}
STDW = {'R': 8, 'UR': 6, 'P': 3, 'UP': 3, 'B': 4}

def word_set(w, bits, v):
    for i, b in enumerate(bits):
        w = (w & ~(1 << b)) | (((v >> i) & 1) << b)
    return w

class Oracle:
    def __init__(self, arch, jobs=4):
        self.arch = arch
        self.n = 0
        self.jobs = jobs
        self.mem = {}
        self.rebase = True
    def text(self, words):
        todo = list({w for w in words if w not in self.mem})
        self.n += len(todo)
        if todo:
            if len(self.mem) > 400000:
                self.mem.clear()
            for w, t in zip(todo, nvd.disasm(self.arch, todo, batch=2048, jobs=self.jobs, use_cache=False, rebase=self.rebase)):
                self.mem[w] = t
        return [self.mem[w] for w in words]
    def toks(self, words):
        return [None if t is None else tokenize(t) for t in self.text(words)]
    def at(self, w, base):
        r, _ = nvd._exec(self.arch, [w], base, nvd.isz_of(self.arch), nvd.os.path.join(nvd.WORK, 'tmp'))
        return None if r is None else r[0]

def region(base, t):
    """Single contiguous edit region: base[lo:hi] -> t[lo:len(t)-(len(base)-hi)]."""
    n, m = len(base), len(t)
    cp = 0
    while cp < n and cp < m and base[cp] == t[cp]:
        cp += 1
    cs = 0
    while cs < n - cp and cs < m - cp and base[n - 1 - cs] == t[m - 1 - cs]:
        cs += 1
    return cp, n - cs, t[cp:m - cs]

def overlaps(a, b):
    (alo, ahi), (blo, bhi) = a, b
    if alo == ahi and blo == bhi:
        return alo == blo
    if alo == ahi:
        return blo < alo < bhi
    if blo == bhi:
        return alo < blo < ahi
    return alo < bhi and blo < ahi

def units(toks):
    """Operand unit id per token: -2 guard, -1 mnemonic part, k operand k, None separator."""
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
    """Region [lo,hi) includes the separator between mnemonic and operands."""
    for i in range(max(0, lo), min(hi, len(U))):
        if U[i] is None and i > 0 and U[i - 1] is not None and U[i - 1] < 0:
            return True
    return False

def vcls(tok):
    c = classify(tok)
    return c[0] if c else None

def count_values(toks):
    return sum(1 for t in toks if classify(t))

class Learner:
    def __init__(self, arch, rng=None, verbose=False, jobs=4):
        set_profile(arch)
        self.arch = arch
        self.O = Oracle(arch, jobs)
        self.rng = rng or random.Random(1)
        self.verbose = verbose

    def log(self, *a):
        if self.verbose:
            print(*a, file=sys.stderr)

    # ------------------------------------------------------------ flips
    def flips(self, w):
        ws = [w] + [w ^ (1 << b) for b in LEARN_BITS]
        r = self.O.toks(ws)
        return r[0], dict(zip(LEARN_BITS, r[1:]))

    def reveal(self, w, base):
        """Flip bits that make value tokens appear (without changing mnemonic)."""
        for _ in range(8):
            b0, fl = self.flips(w)
            if b0 is None:
                return w
            mn = mnem_of(b0)
            best = None
            nv0 = count_values(b0)
            for b, t in fl.items():
                if b in GUARD_BITS or t is None or mnem_of(t) != mn:
                    continue
                d = count_values(t) - nv0
                if d > 0 and len(t) > len(b0):
                    lo, hi, out = region(b0, t)
                    # never change the mnemonic / modifiers while revealing operands
                    U0 = units(b0)
                    def mpart(tk):
                        u = units(tk)
                        return [x for x, uu in zip(tk, u) if uu is not None and uu < 0]
                    if mpart(t) != mpart(b0):
                        continue
                    if any(u is not None and u < 0 for u in U0[lo:hi]) or (lo < len(U0) and U0[lo] is not None and U0[lo] < 0) \
                            or (lo == hi and lo > 0 and U0[lo - 1] is not None and U0[lo - 1] < 0):
                        continue
                    # prefer pure insertions; accept others only if all old values survive
                    old = [x for x in b0[lo:hi] if classify(x)]
                    if all(x in out for x in old):
                        sc = d + (0.5 if hi == lo else 0)
                        if best is None or sc > best[0]:
                            best = (sc, b)
            if best is None:
                return w
            w ^= 1 << best[1]
        return w

    # ------------------------------------------------------------ analysis
    def analyze(self, w, force=()):
        base, fl = self.flips(w)
        if base is None:
            return None
        mn = mnem_of(base)
        U = units(base)
        info = {}
        vbits = collections.defaultdict(list)   # pos -> [(bit, new_tok)]
        for b, t in fl.items():
            if b in force:
                info[b] = ('struct',)
            elif t is None:
                info[b] = ('inv',)
            elif t == base:
                info[b] = ('dc',)
            elif mnem_of(t) != mn:
                info[b] = ('struct',)
            else:
                lo, hi, out = region(base, t)
                if hi - lo == 1 and len(out) == 1 and vcls(base[lo]) and vcls(base[lo]) == vcls(out[0]) \
                        and b not in GUARD_BITS:
                    vbits[lo].append((b, out[0]))
                    info[b] = ('val', lo)
                elif b not in GUARD_BITS and len({x for x in U[lo:hi] if x is not None}) > 1:
                    info[b] = ('struct',)
                else:
                    info[b] = ('enum', lo, hi, tuple(out))
        slots = []
        for pos in sorted(vbits):
            s = self.make_slot(w, base, pos, vbits[pos])
            if s is None:
                for b, nt in vbits[pos]:
                    info[b] = ('enum', pos, pos + 1, (nt,))
            else:
                slots.append(s)
        return dict(word=w, base=base, info=info, slots=slots, mn=mn)

    def make_slot(self, w, base, pos, obs):
        tok = base[pos]
        cls, v0 = classify(tok)
        if cls == 'flt':
            return self.make_flt_slot(w, base, pos, obs)
        ws = []
        for b, nt in obs:
            c = classify(nt)
            d = c[1] - v0
            ws.append((b, d if not bit(w, b) else -d))
        ws.sort(key=lambda x: abs(x[1]))
        scale = abs(ws[0][1])
        if scale == 0:
            return None
        bits = []
        signed = False
        strict = True
        for k, (b, wt) in enumerate(ws):
            if abs(wt) != scale << k or (wt < 0 and k != len(ws) - 1):
                strict = False
                break
            if wt < 0:
                signed = True
            bits.append(b)
        if not strict:
            # positional model with holes: weight = scale * 2^(b - bmin)
            byb = sorted(ws)
            b0 = byb[0][0]; b1 = byb[-1][0]
            sc = abs(dict(ws)[b0])
            signed = False
            for b, wt in byb:
                exp = sc << (b - b0)
                if abs(wt) != exp or (wt < 0 and b != b1):
                    return None
                if wt < 0:
                    signed = True
            if b1 - b0 + 1 > 64:
                return None
            bits = list(range(b0, b1 + 1))
            scale = sc
            ws = [(b, (-(sc << (b - b0)) if (signed and b == b1) else (sc << (b - b0)))) for b in bits]
        add = v0 - sum(wt for b, wt in ws if bit(w, b))
        if signed:
            # value = add + scale * signed(raw); signed(raw) = raw - 2^n when top bit set
            pass
        s = dict(pos=pos, cls=cls, bits=bits, scale=scale, signed=signed, add=add)
        stdw = STDW.get(cls)
        if stdw and not signed and bits == list(range(bits[0], bits[0] + len(bits))) and scale & (scale - 1) == 0:
            j = scale.bit_length() - 1
            nb = list(range(bits[0] - j, bits[0])) + bits
            top = nb[-1]
            while len(nb) < stdw and top + 1 < 105:
                top += 1; nb.append(top)
            if len(nb) == stdw and nb[0] >= 12:
                s2 = dict(s, bits=nb, scale=1, add=0)
                if slot_value(s2, w) == v0:
                    s = s2
        # sanity: reproduce seed value
        if slot_value(s, w) != v0:
            return None
        return s

    def make_flt_slot(self, w, base, pos, obs):
        bits = sorted(b for b, _ in obs)
        lo0, hi0 = bits[0], bits[-1]
        tries = []
        for width, fmts in ((32, ('f32', 'f64hi')), (16, ('f16',)), (64, ('f64',))):
            if hi0 - lo0 + 1 > width:
                continue
            for lo in range(max(12, hi0 - width + 1), lo0 + 1):
                if lo + width > 105:
                    continue
                tries.append((lo, width, fmts))
        # prefer windows starting at the lowest observed bit, then aligned ones
        tries.sort(key=lambda t: (t[0] != lo0, t[0] % 16 != 0, t[1]))
        for lo, width, fmts in tries:
            s = dict(pos=pos, cls='flt', bits=list(range(lo, lo + width)), scale=1, signed=False, add=0)
            for f in fmts:
                s['fmt'] = f
                ok = flt_match(base[pos], f, slot_raw(s, w))
                for b, nt in obs:
                    if not ok:
                        break
                    ok = flt_match(nt, f, slot_raw(s, w ^ (1 << b)))
                if ok:
                    return dict(s)
        return None

    def genericize(self, a):
        """Choose slot values that avoid special encodings."""
        w = a['word']
        tries = []
        for _ in range(12):
            x = w
            for s in a['slots']:
                n = len(s['bits'])
                if s['cls'] == 'flt':
                    base_ = {'f32': 0x3e800000, 'f64hi': 0x3fd00000, 'f16': 0x3400, 'f64': 0x3fd0000000000000}[s['fmt']]
                    mant = {'f32': 23, 'f64hi': 20, 'f16': 10, 'f64': 52}[s['fmt']]
                    v = base_ | self.rng.getrandbits(mant)
                    x = word_set(x, s['bits'], v)
                    continue
                if n <= 1:
                    continue
                for _ in range(50):
                    v = self.rng.getrandbits(n)
                    pc = bin(v).count('1')
                    if v == 0 or v == (1 << n) - 1 or pc > max(1, n - 2) or (s.get('signed') and (v >> (n - 1)) & 1):
                        continue
                    if n >= 4 and pc < 2:
                        continue
                    break
                x = word_set(x, s['bits'], v)
            tries.append(x)
        res = self.O.toks(tries)
        b0 = a['base']
        skel0 = [t if not classify(t) else '#' for t in b0]
        for x, t in zip(tries, res):
            if t is None:
                continue
            if [u if not classify(u) else '#' for u in t] != skel0:
                continue
            vals = [u for u in t if classify(u) and classify(u)[0] not in ('P', 'UP', 'flt')]
            if len(set(vals)) != len(vals):
                continue
            return x
        return w

    # ------------------------------------------------------------ groups
    def build_groups(self, a, fixed):
        info = a['info']
        regs = {}
        for b, i in info.items():
            if i[0] == 'enum' and b not in fixed:
                regs[b] = (i[1], i[2])
        return self.merge(regs, fixed)

    def numeric_groups(self, groups, a, w):
        """Groups whose every output is one hex/register token that is a linear function
        of the group value are really value slots (the seed made them look enumerated)."""
        out = []
        for g in groups:
            if set(g['bits']) & set(GUARD_BITS) or g['hi'] - g['lo'] != 1:
                out.append(g); continue
            vals = {}
            cls = None
            ok = True
            for v, o in g['table'].items():
                if o is None or len(o) != 1 or not classify(o[0]) or classify(o[0])[0] in ('flt',):
                    ok = False; break
                c = classify(o[0])
                if cls is None: cls = c[0]
                if c[0] != cls:
                    ok = False; break
                vals[v] = c[1]
            if not ok or len(vals) < (1 << len(g['bits'])) or 0 not in vals:
                out.append(g); continue
            c0 = vals[0]
            wts = [vals[1 << i] - c0 for i in range(len(g['bits']))]
            if any(vals[v] != c0 + sum(wts[i] for i in range(len(wts)) if (v >> i) & 1) for v in vals):
                out.append(g); continue
            order = sorted(range(len(wts)), key=lambda i: abs(wts[i]))
            sc = abs(wts[order[0]])
            if sc == 0 or any(abs(wts[i]) != sc << k or (wts[i] < 0 and k != len(order) - 1) for k, i in enumerate(order)):
                out.append(g); continue
            signed = wts[order[-1]] < 0
            s = dict(pos=g['lo'], cls=cls, bits=[g['bits'][i] for i in order], scale=sc, signed=signed, add=c0)
            if signed:
                s['add'] = c0
            a['slots'].append(s)
            a['slots'].sort(key=lambda x: x['pos'])
            a['base'][g['lo']] = fmt_value(s, w) if cls != 'flt' else a['base'][g['lo']]
        return out

    def merge(self, regs, fixed):
        groups = []   # [lo, hi, bits]
        gb = [b for b in GUARD_BITS if b in regs]
        regs = {b: r for b, r in regs.items() if b not in GUARD_BITS}
        for b in sorted(regs, key=lambda b: regs[b]):
            r = regs[b]
            hit = [g for g in groups if overlaps((g[0], g[1]), r)]
            if not hit:
                groups.append([r[0], r[1], [b]])
            else:
                for g in hit:
                    groups.remove(g)
                lo = min([r[0]] + [g[0] for g in hit]); hi = max([r[1]] + [g[1] for g in hit])
                bits = [b] + [x for g in hit for x in g[2]]
                groups.append([lo, hi, bits])
            # re-merge transitively
            changed = True
            while changed:
                changed = False
                for g1, g2 in itertools.combinations(groups, 2):
                    if overlaps((g1[0], g1[1]), (g2[0], g2[1])):
                        groups.remove(g1); groups.remove(g2)
                        groups.append([min(g1[0], g2[0]), max(g1[1], g2[1]), g1[2] + g2[2]])
                        changed = True
                        break
        if gb:
            groups.append([0, 0, gb])
        return groups

    def enum_groups(self, a, fixed):
        """Enumerate all groups; expand regions on leaks; return groups or raise."""
        w = a['word']; base = a['base']
        regs = {b: (i[1], i[2]) for b, i in a['info'].items() if i[0] == 'enum' and b not in fixed}
        width0 = {b: r[1] - r[0] for b, r in regs.items()}
        for it in range(8):
            groups = self.merge(regs, fixed)
            big = [g for g in groups if len(g[2]) > MAXG]
            if big:
                # make the bits with the widest regions fixed
                for g in big:
                    bs = sorted(g[2], key=lambda b: -width0[b])
                    while len(bs) > MAXG:
                        b = bs.pop(0)
                        fixed.add(b); regs.pop(b)
                continue
            words = []
            index = []
            for gi, g in enumerate(groups):
                bits = sorted(g[2])
                g[2] = bits
                for v in range(1 << len(bits)):
                    words.append(word_set(w, bits, v)); index.append((gi, v))
            res = self.O.toks(words)
            tables = [dict() for _ in groups]
            leaked = False
            for (gi, v), t in zip(index, res):
                g = groups[gi]
                if t is None:
                    tables[gi][v] = None
                    continue
                lo, hi, out = region(base, t)
                if t == base:
                    tables[gi][v] = base[g[0]:g[1]]
                    continue
                if g[2] == GUARD_BITS or [b for b in g[2] if b in GUARD_BITS]:
                    tables[gi][v] = t[:len(t) - len(base)] if t[len(t) - len(base):] == base else ['?']
                    continue
                if lo < g[0] or hi > g[1]:
                    # change outside the group's region: widen it
                    nlo, nhi = min(lo, g[0]), max(hi, g[1])
                    self.log('leak', g[2], v, (g[0], g[1]), (lo, hi), ''.join(t))
                    for b in g[2]:
                        regs[b] = (nlo, nhi)
                    leaked = True
                    continue
                n = len(base)
                tables[gi][v] = t[g[0]:len(t) - (n - g[1])]
            if leaked:
                continue
            out = []
            for g, tb in zip(groups, tables):
                out.append(dict(bits=g[2], lo=g[0], hi=g[1], table=tb))
            return out
        raise RuntimeError('group enumeration did not converge')

    # ------------------------------------------------------------ slot refs
    def mtoks(self, form, x):
        """Model tokens for x; float slots holding the seed value print as the seed text."""
        r = render_tokens(form, x)
        if r is None:
            return None
        w = int(form['seed'], 16)
        fl = {fmt_value(s, w): form['toks'][s['pos']] for s in form['slots'] if s['cls'] == 'flt'}
        return [fl.get(t, t) for t in r]

    def refify(self, form, w, lo, hi, out):
        """Replace tokens in out by references to the slots located in [lo,hi) (in order)."""
        ks = [k for k, s in enumerate(form['slots']) if lo <= s['pos'] < hi]
        return self.map_slots(form, w, ks, out)

    def map_slots(self, form, x, ks, out):
        res = list(out)
        ks = sorted(ks, key=lambda k: form['slots'][k]['pos'])
        i = 0
        for k in ks:
            s = form['slots'][k]
            t = form['toks'][s['pos']] if s['cls'] == 'flt' else fmt_value(s, x)
            j = i
            while j < len(res) and res[j] != t:
                j += 1
            if j < len(res):
                res[j] = k
                i = j + 1
        return res

    # ------------------------------------------------------------ specials
    def specials(self, form, w):
        """Probe special slot values; regions are relative to the anchor slot marker."""
        from sassmodel import render_items
        slots = form['slots']
        base_items = render_items(dict(form, specials=[]), w)
        def anchor(k):
            return base_items.index(('s', k))
        def kword(x, k, kd):
            s = slots[k]; n = len(s['bits'])
            if kd == 'max': return word_set(x, s['bits'], (1 << n) - 1)
            if kd == 'zero': return word_set(x, s['bits'], 0)
            return word_set(x, s['bits'], (1 << (n - 1)) | (0x5 & ((1 << (n - 1)) - 1)))
        probes = []
        for k, s in enumerate(slots):
            n = len(s['bits'])
            if s['cls'] == 'flt' or ('s', k) not in base_items:
                continue
            kinds = []
            if n >= 2:
                kinds.append('max')
            kinds.append('zero')
            if s.get('signed') and n >= 2:
                kinds.append('neg')
            for kd in kinds:
                probes.append((k, kd, kword(w, k, kd)))
        res = self.O.toks([p[2] for p in probes])
        single = collections.defaultdict(dict)   # k -> kind -> (lo, hi) absolute in base items
        mn_changed = {}
        def mpart(tk):
            u = units(tk)
            return [a for a, b in zip(tk, u) if b is not None and b < 0]
        for (k, kd, x), t in zip(probes, res):
            if t is not None:
                mn_changed[(k, kd)] = mpart(t) != mpart(form['toks'])
            m = self.mtoks(dict(form, specials=[]), x)
            if m is None:
                continue
            p = anchor(k)
            if t is None:
                single[k][kd] = (p, p + 1)
                continue
            if t == m:
                continue
            lo, hi, out = region(m, t)
            single[k][kd] = (min(lo, p), max(hi, p + 1))
        # a special value that changes the mnemonic (e.g. RZ base -> different modifiers)
        # cannot be expressed per operand; leave it out instead of merging everything
        Ub = units(form['toks'])
        for k in list(single):
            for kd in list(single[k]):
                lo_, hi_ = single[k][kd]
                us = {u for u in Ub[max(0, lo_):hi_] if u is not None}
                if (-1 in us and len(us) > 1) or (crosses_sep(Ub, lo_, hi_) and mn_changed.get((k, kd))):
                    del single[k][kd]
                    slots[k].setdefault('xspec', []).append(kd)
            if not single[k]:
                del single[k]
        if not single:
            return []
        items = []
        for k, d in single.items():
            lo = min(r[0] for r in d.values()); hi = max(r[1] for r in d.values())
            items.append([lo, hi, [k]])
        changed = True
        while changed:
            changed = False
            for a_, b_ in itertools.combinations(items, 2):
                if a_[0] < b_[1] and b_[0] < a_[1]:
                    items.remove(a_); items.remove(b_)
                    items.append([min(a_[0], b_[0]), max(a_[1], b_[1]), a_[2] + b_[2]])
                    changed = True
                    break
        out = []
        for lo, hi, ks in items:
            ks = sorted(ks, key=anchor)
            kinds = [[None] + sorted(single[k]) for k in ks]
            combos = [c for c in itertools.product(*kinds) if any(c)][:64]
            words = []
            for c in combos:
                x = w
                for k, kd in zip(ks, c):
                    if kd:
                        x = kword(x, k, kd)
                words.append(x)
            res = self.O.toks(words)
            cases = {}
            for _ in range(3):
                regionok = True
                for c, x, t in zip(combos, words, res):
                    key = ','.join(kd or '-' for kd in c)
                    if t is None:
                        cases[key] = None
                        continue
                    m = self.mtoks(dict(form, specials=[]), x)
                    if m is None:
                        continue
                    n = len(m)
                    if t[:lo] != m[:lo] or t[len(t) - (n - hi):] != m[hi:]:
                        lo2, hi2, _ = region(m, t)
                        lo, hi = min(lo, lo2), max(hi, hi2)
                        regionok = False
                        break
                    ks_in = [it[1] for it in base_items[lo:hi] if isinstance(it, tuple)]
                    cases[key] = self.map_slots(form, x, ks_in, t[lo:len(t) - (n - hi)])
                if regionok:
                    break
            a0 = anchor(ks[0])
            for k in ks:
                slots[k]['spec'] = sorted(set(slots[k].get('spec', [])) | set(single[k]))
            sp = dict(slots=ks, rlo=lo - a0, rhi=hi - a0, cases=cases)
            gsp = self.group_special(form, w, ks, combos, lo, hi)
            out.append(gsp if gsp is not None else sp)
        return out

    def group_special(self, form, w, ks, combos, lo, hi):
        """If the special region overlaps modifier groups, record the special text for every
        value of those groups (region in base-token coordinates; replaces the groups)."""
        base = form['toks']
        n = len(base)
        Ub_ = units(base)
        Ureg_ = {u for u in Ub_[lo:hi] if u is not None}
        gis = []
        for _ in range(4):
            new = [gi for gi, g in enumerate(form['groups']) if gi not in gis and not set(g['bits']) & set(GUARD_BITS)
                   and (overlaps((g['lo'], g['hi']), (lo, hi)) or (lo < g['lo'] and g['hi'] < hi)
                        or (g['lo'] == g['hi'] == lo and lo < n and Ub_[lo] is not None and Ub_[lo] in Ureg_))]
            if not new:
                break
            gis += new
            for gi in new:
                g = form['groups'][gi]
                lo, hi = min(lo, g['lo']), max(hi, g['hi'])
        if not gis:
            return None
        gvals = [[v for v, o in form['groups'][gi]['table'].items() if o is not None] for gi in gis]
        total = len(combos)
        for x in gvals:
            total *= len(x)
        if total > 512:
            return None
        words, keys = [], []
        for gv in itertools.product(*gvals):
            x0 = w
            for gi, v in zip(gis, gv):
                x0 = word_set(x0, form['groups'][gi]['bits'], v)
            for c in combos:
                x = x0
                for k, kd in zip(ks, c):
                    if kd:
                        s = form['slots'][k]; nb = len(s['bits'])
                        val = {'max': (1 << nb) - 1, 'zero': 0, 'neg': (1 << (nb - 1)) | (0x5 & ((1 << (nb - 1)) - 1))}[kd]
                        x = word_set(x, s['bits'], val)
                words.append(x)
                keys.append(','.join(kd or '-' for kd in c) + '|' + ','.join(map(str, gv)))
        res = self.O.toks(words)
        for _ in range(3):
            cases = {}
            ok = True
            for key, x, t in zip(keys, words, res):
                if t is None:
                    cases[key] = None
                    continue
                if t[:lo] != base[:lo] or t[len(t) - (n - hi):] != base[hi:]:
                    l2, h2, _ = region(base, t)
                    lo, hi = min(lo, l2), max(hi, h2)
                    ok = False
                    break
                ks_in = [k for k, s in enumerate(form['slots']) if lo <= s['pos'] < hi]
                cases[key] = self.map_slots(form, x, ks_in, t[lo:len(t) - (n - hi)])
            if ok:
                break
        else:
            return None
        # other groups must not intrude into the widened region
        for gi, g in enumerate(form['groups']):
            if gi not in gis and not set(g['bits']) & set(GUARD_BITS) and overlaps((g['lo'], g['hi']), (lo, hi)):
                return None
        return dict(slots=ks, gis=gis, lo=lo, hi=hi, cases=cases)

    def refify_items(self, items, lo, hi, out, form, w):
        res = list(out)
        for it in items[lo:hi]:
            if isinstance(it, tuple):
                k = it[1]
                s_ = form['slots'][k]
                t = fmt_value(s_, w) if s_['cls'] != 'flt' else form['toks'][s_['pos']]
                for i, x in enumerate(res):
                    if x == t:
                        res[i] = k
                        break
        return res

    # ------------------------------------------------------------ interactions
    def interactions(self, form, w, fixed):
        """Merge groups whose joint effect is not the composition of their single effects,
        and fold don't-care bits that matter for non-seed group values into their group."""
        base = form['toks']
        changed = True
        rounds = 0
        while changed and rounds < 6:
            changed = False
            rounds += 1
            gs = [g for g in form['groups'] if not set(g['bits']) & set(GUARD_BITS)]
            # pairwise group check
            tests = []
            for gi, gj in itertools.combinations(range(len(gs)), 2):
                a, b = gs[gi], gs[gj]
                va = [v for v, o in a['table'].items() if o is not None and v != group_value(a, w)]
                vb = [v for v, o in b['table'].items() if o is not None and v != group_value(b, w)]
                if len(va) * len(vb) > 48:
                    va = self.rng.sample(va, min(len(va), 7)); vb = self.rng.sample(vb, min(len(vb), 7))
                for x in va:
                    for y in vb:
                        tests.append((gi, gj, word_set(word_set(w, a['bits'], x), b['bits'], y)))
            # dc-bit check
            dcb = [b for b in form['dc'] if b not in fixed]
            for gi, g in enumerate(gs):
                vals = [v for v, o in g['table'].items() if o is not None and v != group_value(g, w)]
                vals = self.rng.sample(vals, min(len(vals), 4))
                for v in vals:
                    x = word_set(w, g['bits'], v)
                    for d in dcb:
                        tests.append((gi, ('dc', d), x ^ (1 << d)))
            res = self.O.toks([t[2] for t in tests])
            bad = collections.Counter()
            for (gi, gj, x), t in zip(tests, res):
                if t is None:
                    continue
                m = self.mtoks(form, x)
                if m != t:
                    bad[(gi, gj)] += 1
            if not bad:
                break
            (gi, gj), _ = bad.most_common(1)[0]
            a = gs[gi]
            if isinstance(gj, tuple):
                newbits = sorted(set(a['bits']) | {gj[1]})
                others = [a]
                form['dc'] = [d for d in form['dc'] if d != gj[1]]
            else:
                b = gs[gj]
                newbits = sorted(set(a['bits']) | set(b['bits']))
                others = [a, b]
            U = units(base)
            lo = min(g['lo'] for g in others); hi = max(g['hi'] for g in others)
            crosses = len({u for u in U[lo:hi] if u is not None}) > 1 or (-1 in U[lo:hi] and lo < hi and any(u is not None and u >= 0 for u in U[lo:hi]))
            if len(newbits) > MAXG or crosses:
                # cannot merge: fix the smaller side
                victim = min(others, key=lambda g: len(g['bits'])) if len(others) > 1 else None
                if isinstance(gj, tuple):
                    fixed.add(gj[1])
                    form['dc'] = [d for d in form['dc'] if d != gj[1]]
                    form['struct'].append(gj[1])
                else:
                    for bb in victim['bits']:
                        fixed.add(bb); form['struct'].append(bb)
                    form['groups'].remove(victim)
                    # victim bits now fixed at seed values: re-derive mask
                    form['mask'] |= sum(1 << bb for bb in victim['bits'])
                    form['val'] = w & form['mask']
                if isinstance(gj, tuple):
                    form['mask'] |= 1 << gj[1]; form['val'] = w & form['mask']
                changed = True
                continue
            # merge: enumerate the union
            g = self.enum_one(w, base, newbits, lo, hi, form)
            if g is None:
                for bb in newbits:
                    pass
                victim = min(others, key=lambda g: len(g['bits']))
                for bb in victim['bits']:
                    fixed.add(bb); form['struct'].append(bb)
                form['groups'].remove(victim)
                form['mask'] |= sum(1 << bb for bb in victim['bits']); form['val'] = w & form['mask']
                changed = True
                continue
            for o in others:
                form['groups'].remove(o)
            form['groups'].append(g)
            changed = True

    def enum_one(self, w, base, bits, lo, hi, form):
        """Enumerate one group over region [lo,hi); widen region if needed (within limits)."""
        words = [word_set(w, bits, v) for v in range(1 << len(bits))]
        res = self.O.toks(words)
        n = len(base)
        U = units(base)
        for _ in range(4):
            table = {}
            ok = True
            for v, t in enumerate(res):
                if t is None:
                    table[v] = None; continue
                if t == base:
                    table[v] = base[lo:hi]; continue
                if t[:lo] != base[:lo] or t[len(t) - (n - hi):] != base[hi:]:
                    l2, h2, _ = region(base, t)
                    lo, hi = min(lo, l2), max(hi, h2)
                    ok = False
                    break
                table[v] = t[lo:len(t) - (n - hi)]
            if ok:
                break
        else:
            return None
        if not ok:
            return None
        us = {u for u in U[lo:hi] if u is not None}
        if -1 in us and len(us) > 1:
            return None
        # other groups inside the widened region would conflict
        for g in form['groups']:
            if set(g['bits']) & set(bits):
                continue
            if overlaps((g['lo'], g['hi']), (lo, hi)) or (lo < g['lo'] < hi):
                return None
        for v, o in table.items():
            if o is not None:
                table[v] = self.refify(form, w, lo, hi, o)
        return dict(bits=bits, lo=lo, hi=hi, table=table)

    # ------------------------------------------------------------ main
    def prepare(self, seed):
        # pc-relative operands need position-independent (rebased) disassembly
        t1, t2 = self.O.at(seed, 0), self.O.at(seed, 0x100000)
        self.O.mem.clear()
        self.O.rebase = (t1 != t2)
        w = (seed & ~CTRL_MASK) | CTRL_STD
        t0 = self.O.toks([w])[0]
        if t0 is None:
            w = seed
            t0 = self.O.toks([w])[0]
            if t0 is None:
                return None, None
        # unguarded, no reuse
        w1 = word_set(w, GUARD_BITS, 7)
        w1 = word_set(w1, REUSE_BITS, 0)
        if self.O.toks([w1])[0] is not None:
            w = w1
        w = self.reveal(w, t0)
        a = self.analyze(w)
        if a is None:
            return None, None
        for _ in range(3):
            w2 = self.genericize(a)
            if w2 == w:
                break
            a2 = self.analyze(w2)
            if a2 is None or sum(len(x['bits']) for x in a2['slots']) < sum(len(x['bits']) for x in a['slots']):
                break
            a, w = a2, w2
        return w, a

    def build(self, w, a, force):
        """Build a form from analysis a of word w; bits in force are fixed."""
        if force:
            a = self.analyze(w, force)
        fixed = set(OPC_BITS) | set(force)
        for b, i in a['info'].items():
            if i[0] in ('inv', 'struct'):
                fixed.add(b)
        groups = self.enum_groups(a, fixed)
        groups = self.numeric_groups(groups, a, w)
        mask = sum(1 << b for b in fixed)
        form = dict(arch=self.arch, mn=a['mn'], seed='%x' % w, text=''.join(a['base']),
                    mask=mask, val=w & mask, toks=a['base'], slots=a['slots'], groups=groups, specials=[])
        for g in groups:
            for v, o in g['table'].items():
                if o is not None:
                    g['table'][v] = self.refify(form, w, g['lo'], g['hi'], o)
        for s in form['slots']:
            if s['cls'] == 'hex':
                t = self.O.at(w, 0x10000 // SHIFT_MULT)
                if t:
                    tk = tokenize(t)
                    if len(tk) > s['pos'] and classify(tk[s['pos']]) and classify(tk[s['pos']])[0] == 'hex':
                        if classify(tk[s['pos']])[1] - slot_value(s, w) == 0x10000:
                            s['pcrel'] = True
        form['struct'] = sorted(set(b for b, i in a['info'].items() if i[0] == 'struct') | set(force))
        form['dc'] = sorted(b for b, i in a['info'].items() if i[0] == 'dc')
        self.interactions(form, w, fixed)
        form['mask'] = sum(1 << b for b in fixed) | form['mask']
        form['val'] = w & form['mask']
        form['specials'] = self.specials(form, w)
        form['struct'] = sorted(set(form['struct']))
        return form

    def learn(self, seed, max_split=5):
        w, a = self.prepare(seed)
        if w is None:
            return None
        force = set()
        best = None
        spawn = []
        core = CORE_MODS.get(a['mn'])
        for it in range(max_split + 1):
            form = self.build(w, a, force)
            if core:
                U = units(form['toks'])
                extra = []
                for g in form['groups']:
                    if set(g['bits']) & set(GUARD_BITS) or g['lo'] >= len(U) or (U[g['lo']] != -1 and not (g['lo'] == g['hi'] and g['lo'] > 0 and U[g['lo'] - 1] == -1)):
                        continue
                    toks = {t for o in g['table'].values() if o for t in o if isinstance(t, str)}
                    if toks & core:
                        extra.append(g)
                if extra:
                    for g in extra:
                        force |= set(g['bits'])
                        sv = group_value(g, w)
                        for v, o in g['table'].items():
                            if o is not None and v != sv:
                                spawn.append(word_set(w, g['bits'], v))
                    form = self.build(w, a, force)
            st, bad, samples = self.validate(form, n=240, detail=True)
            good = st.get('ok', 0)
            nb = st.get('bad', 0) + st.get('under', 0)
            form['score'] = dict(st)
            if best is None or good / max(1, good + nb) > best[0]:
                best = (good / max(1, good + nb), form)
            if nb <= max(1, (good + nb) // 100) or it == max_split:
                break
            cand = self.split_candidate(form, w, samples)
            if cand is None:
                break
            kind, bits, sw = cand
            self.log('split', form['mn'], kind, bits)
            force |= set(bits)
            if sw is not None:
                spawn.append(sw)
        f = best[1]
        for g in f['groups']:
            if set(g['bits']) & set(GUARD_BITS):
                continue
            n = 0
            for v, o in g['table'].items():
                if o and any(isinstance(t, str) and classify(t) for t in o) and n < 3:
                    spawn.append(word_set(w, g['bits'], v)); n += 1
        f['spawn'] = ['%x' % x for x in spawn]
        return f

    def split_candidate(self, form, w, samples):
        """Pick the group bit, dc bit or special slot whose deviation from the seed
        best predicts validation failures."""
        cands = []
        for g in form['groups']:
            if set(g['bits']) & set(GUARD_BITS):
                continue
            for b in g['bits']:
                cands.append(('bit', [b], lambda x, b=b: bit(x, b) == bit(w, b), w ^ (1 << b)))
        for b in form.get('dc', []):
            cands.append(('bit', [b], lambda x, b=b: bit(x, b) == bit(w, b), w ^ (1 << b)))
        for k, s in enumerate(form['slots']):
            raw = slot_raw(s, w); n = len(s['bits'])
            if s['cls'] == 'flt' or n < 2:
                continue
            if raw in (0, (1 << n) - 1):
                gen = word_set(w, s['bits'], 0x15 & ((1 << n) - 2) or 1)
                cands.append(('slot', list(s['bits']), lambda x, s=s, raw=raw: slot_raw(s, x) == raw, gen))
        best = None
        for kind, bits, cond, sw in cands:
            bt = bf = nt = nf = 0
            for x, ok in samples:
                if cond(x):
                    nt += 1; bt += (not ok)
                else:
                    nf += 1; bf += (not ok)
            if bf == 0 or nf == 0:
                continue
            score = (bf / nf) - 2.0 * (bt / max(1, nt))
            if bt > 0 and bt / max(1, nt) > 0.05:
                continue
            if best is None or score > best[0]:
                best = (score, kind, bits, sw)
        if best is None or best[0] <= 0:
            return None
        return best[1], best[2], best[3]

    def respecial(self, form):
        """Recompute the specials of an existing form (after learner improvements)."""
        w = int(form['seed'], 16)
        self.O.rebase = any(s.get('pcrel') for s in form['slots'])
        for s in form['slots']:
            s.pop('spec', None); s.pop('xspec', None)
        form['specials'] = self.specials(dict(form, specials=[]), w)
        return form

    def validate(self, form, n=200, extra=(), detail=False):
        w = int(form['seed'], 16)
        free = [b for b in LEARN_BITS if not (form['mask'] >> b) & 1]
        slotbits = {b for s in form['slots'] for b in s['bits']}
        words = []
        for i in range(n):
            x = w
            for b in free:
                if i % 2 and b in slotbits:
                    continue
                if self.rng.random() < 0.5:
                    x ^= 1 << b
            words.append(x)
        words += list(extra)
        res = self.O.text(words)
        st = collections.Counter()
        bad = []
        samples = []
        for x, t in zip(words, res):
            m = render(form, x)
            if t is None and m is None:
                st['both_invalid'] += 1
                continue
            elif t is None:
                st['over'] += 1
                continue
            elif m is None:
                st['under'] += 1; bad.append((x, t, m))
            elif same_text(m, t):
                st['ok'] += 1; samples.append((x, True))
                continue
            else:
                st['bad'] += 1; bad.append((x, t, m))
            samples.append((x, False))
        if detail:
            return st, bad, samples
        return st, bad

def show(form):
    print(form['mn'], '|', form['text'], '| seed', form['seed'])
    print('  fixed:', [b for b in range(128) if (form['mask'] >> b) & 1 and b >= 12])
    for k, s in enumerate(form['slots']):
        print('  slot%d pos=%d %s bits=%s..%s n=%d scale=%d signed=%s add=%d %s %s' % (
            k, s['pos'], s['cls'], s['bits'][0], s['bits'][-1], len(s['bits']), s['scale'], s['signed'], s['add'],
            s.get('fmt', ''), 'pcrel' if s.get('pcrel') else ''), s.get('spec', ''))
    for g in form['groups']:
        tb = {v: (None if o is None else ''.join(str(x) if isinstance(x, str) else '$%d' % x for x in o)) for v, o in g['table'].items()}
        print('  group bits=%s region=[%d,%d) %s' % (g['bits'], g['lo'], g['hi'], tb if len(tb) <= 16 else str(tb)[:300]))
    for sp in form['specials']:
        if 'gis' in sp:
            print('  gspecial slots=%s groups=%s [%d,%d) %s' % (sp['slots'], sp['gis'], sp['lo'], sp['hi'], str(sp['cases'])[:300]))
        else:
            print('  special slots=%s rel[%d,%d) %s' % (sp['slots'], sp['rlo'], sp['rhi'], sp['cases']))

if __name__ == '__main__':
    arch = sys.argv[1]
    L = Learner(arch, verbose=True)
    for x in sys.argv[2:]:
        f = L.learn(int(x, 16))
        if f is None:
            print('invalid seed', x); continue
        show(f)
        st, bad = L.validate(f)
        print('  spawn', f.get('spawn'))
        print('  validate', dict(st))
        for x_, t, m in bad[:8]:
            print('    %032x\n      nv: %s\n      md: %s' % (x_, t, m))
        print('  oracle words', L.O.n)
