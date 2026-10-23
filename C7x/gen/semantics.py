"""P-code semantics for the generated C7x constructors.

sem(mn, unit, skel, ops, sizes, r) returns the body of one constructor.
  skel  : dis7x operand skeleton, e.g. 'R,N,R', '*R++(N),R', 'R,R:R,*R(N)'  (atoms are R, N, L)
  ops   : per atom, the SLEIGH operand name (string) or ('CONST', text) for a fixed atom
  sizes : per atom, 8 (64-bit scalar register), 'V' (vector register, VLEN bytes),
          'N' (constant subtable, exports *[const]:8) or 'C' (fixed constant)

Real p-code is produced for scalar integer/float ALU ops, moves/constants, loads/stores (all
addressing modes), address arithmetic, predicate-register logic and the element-wise vector
ALU ops when they operate on 64-bit scalar registers (which the compiler does for ordinary
scalar code, e.g. VSHRW/VANDW on A registers).  Everything else becomes a named pcodeop that
still reads the source operands and writes the destination register(s).
"""
import re

PCODEOPS = set()
VLEN = 64            # set by gen.py per silicon (64 for C7100/C7120, 32 for C7504/C7524)

KEYWORDS = {'abs', 'sqrt', 'nan', 'int', 'float', 'trunc', 'ceil', 'floor', 'round', 'carry', 'scarry',
            'sborrow', 'zext', 'sext', 'popcount', 'lzcount', 'if', 'goto', 'call', 'return', 'build',
            'export', 'local', 'is', 'macro', 'define', 'delayslot', 'unimpl', 'with', 'cpool', 'newobject'}

def pop(name):
    n = name.lower()
    if n in KEYWORDS or re.match(r'^(b|s|r)\d', n) or re.match(r'^t[rnup]\d', n):
        n = n + '_op'
    PCODEOPS.add(n)
    return n

class Unsupported(Exception):
    pass

M64 = (1 << 64) - 1

# ------------------------------------------------------------------ operand helpers
class Ctx:
    def __init__(self, ops, sizes):
        self.ops, self.sizes = ops, sizes
        self.n = 0

    def size(self, i):
        s = self.sizes[i]
        return VLEN if s == 'V' else 8

    def raw(self, i):
        o = self.ops[i]
        if isinstance(o, tuple):
            return '%s:8' % hex(int(o[1], 0) & M64)
        return o

    def v8(self, i):
        """64-bit value of atom i"""
        if self.sizes[i] == 'V':
            return '%s:8' % self.ops[i]
        return self.raw(i)

    def tr(self, i, k):
        """low k bytes of atom i"""
        o = self.ops[i]
        if isinstance(o, tuple):
            return '%s:%d' % (hex(int(o[1], 0) & ((1 << (8 * k)) - 1)), k)
        if k == self.size(i) and self.sizes[i] != 'N':
            return o
        return '%s:%d' % (o, k)

    def v4(self, i):
        o = self.ops[i]
        if isinstance(o, tuple):
            return '%s:4' % hex(int(o[1], 0) & 0xffffffff)
        return '%s:4' % o

    def is_reg(self, i):
        return self.sizes[i] in (8, 'V')

    def tmp(self, size, expr):
        self.n += 1
        return 'local t%d:%d = %s;' % (self.n, size, expr), 't%d' % self.n

    def assign(self, i, expr, esize=8):
        """write expression of esize bytes to atom i"""
        if not self.is_reg(i):
            raise Unsupported('dst not reg')
        d = self.ops[i]
        ds = self.size(i)
        if ds == esize:
            return '%s = %s;' % (d, expr)
        if ds > esize:
            return '%s = zext(%s);' % (d, expr)
        return '%s = %s:%d;' % (d, '(%s)' % expr if not re.match(r'^\w+$', expr) else expr, ds)


def atoms_of(skel):
    """positions of atoms in skel -> list of (kind, startpos)"""
    return [(m.group(0), m.start()) for m in re.finditer(r'[RNL]', skel)]

def atom_index(skel, pos):
    return len(re.findall(r'[RNL]', skel[:pos]))

# ------------------------------------------------------------------ memory
ESZ = {'B': 1, 'H': 2, 'W': 4, 'D': 8, 'Q': 16}

def elem_size(mn):
    m = re.match(r'^(VSTP|VLD|VST|SLD|LD|ST)(.*)$', mn)
    rest = m.group(2) if m else mn
    rest = re.sub(r'^(DUPG|DUP|E|0K|K|U)?\d*', '', rest)
    if rest[:1] == 'U':
        rest = rest[1:]
    return ESZ.get(rest[:1], 1)

MEMRE = re.compile(r'\*R(\+\+)?(?:\(([RN])\))?')

def mem_ea(c, skel, mn, access):
    """returns (code, ea_name, memstart_atom_index, nat) for the memory operand in skel"""
    m = MEMRE.search(skel)
    if not m:
        raise Unsupported('no mem')
    bi = atom_index(skel, m.start())
    base = c.ops[bi]
    post = bool(m.group(1))
    sh = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[elem_size(mn)]
    code = []
    off = None
    if m.group(2) == 'N':
        off = c.raw(bi + 1)
    elif m.group(2) == 'R':
        o = c.ops[bi + 1]
        off = '(sext(%s:4) << %d)' % (o, sh) if sh else 'sext(%s:4)' % o
    elif post:
        off = '%d:8' % access
    bexpr = c.v8(bi)
    if post:
        s, ea = c.tmp(8, bexpr)
        code.append(s)
        upd = c.assign(bi, '%s + %s' % (bexpr, off)) if c.sizes[bi] == 8 else '%s = %s + %s;' % (base, bexpr, off)
        return code, ea, upd, bi, 1 + (1 if m.group(2) else 0)
    s, ea = c.tmp(8, '%s + %s' % (bexpr, off) if off else bexpr)
    code.append(s)
    return code, ea, '', bi, 1 + (1 if m.group(2) else 0)

SCALAR_LD = {'LDB': (1, 's'), 'LDUB': (1, 'z'), 'LDH': (2, 's'), 'LDUH': (2, 'z'), 'LDW': (4, 's'),
             'LDUW': (4, 'z'), 'LDD': (8, 'z')}
SCALAR_ST = {'STB': 1, 'STH': 2, 'STW': 4, 'STD': 8}

def sem_load(mn, skel, c):
    base_mn = mn[1:] if mn.startswith('SLD') else mn
    if base_mn in SCALAR_LD:
        size, ext = SCALAR_LD[base_mn]
        code, ea, upd, bi, nat = mem_ea(c, skel, mn, size)
        d = len(c.ops) - 1
        v = '*:%d %s' % (size, ea)
        if size < 8:
            s, t = c.tmp(8, '%s(%s)' % ('sext' if ext == 's' else 'zext', v))
        else:
            s, t = c.tmp(8, v)
        code.append(s)
        code.append(upd)
        code.append(c.assign(d, t))
        return ' '.join(x for x in code if x)
    m = re.match(r'^(LD)(DSWAPW|WSWAPH|HSWAPB)$', mn)
    if m:
        size = {'D': 8, 'W': 4, 'H': 2}[m.group(2)[0]]
        code, ea, upd, bi, nat = mem_ea(c, skel, mn, size)
        d = len(c.ops) - 1
        s, t = c.tmp(size, '%s(*:%d %s)' % (pop(mn.lower() + '_swap'), size, ea))
        code += [s, upd, c.assign(d, t, size)]
        return ' '.join(x for x in code if x)
    m = re.match(r'^VLD(\d+)([BHWD])$', mn)
    d = len(c.ops) - 1
    if m:
        nbytes = int(m.group(1)) * ESZ[m.group(2)]
        code, ea, upd, bi, nat = mem_ea(c, skel, mn, nbytes)
        ds = c.size(d)
        acc = min(nbytes, ds)
        s, t = c.tmp(acc, '*:%d %s' % (acc, ea))
        code += [s, upd, c.assign(d, t, acc)]
        return ' '.join(x for x in code if x)
    # other vector loads (dup/unpack/swap): address and base update are real, data is a pcodeop
    code, ea, upd, bi, nat = mem_ea(c, skel, mn, VLEN)
    ds = c.size(d)
    s, t = c.tmp(ds, '%s(%s)' % (pop(mn), ea))
    code += [s, upd, c.assign(d, t, ds)]
    return ' '.join(x for x in code if x)

def sem_store(mn, skel, c):
    m = MEMRE.search(skel)
    bi = atom_index(skel, m.start())
    srcs = list(range(0, bi))
    if mn in SCALAR_ST or mn in ('STDSWAPW', 'STWSWAPH', 'STHSWAPB', 'STKW', 'STKD', 'ST0KW', 'ST0KD'):
        size = SCALAR_ST.get(mn) or {'D': 8, 'W': 4, 'H': 2}[mn[-1] if mn.startswith('ST') and 'K' in mn else mn[2]]
        code, ea, upd, _, nat = mem_ea(c, skel, mn, size)
        if mn.startswith('ST0K'):
            val = '0:%d' % size
        else:
            v = c.v8(srcs[0])
            if 'SWAP' in mn:
                s, t = c.tmp(size, '%s(%s)' % (pop(mn.lower() + '_swap'), c.tr(srcs[0], size)))
                code.append(s); val = t
            else:
                val = c.tr(srcs[0], size)
        code.append('*:%d %s = %s;' % (size, ea, val))
        code.append(upd)
        return ' '.join(x for x in code if x)
    m2 = re.match(r'^VST(\d+)([BHWD])$', mn)
    if m2:
        nbytes = int(m2.group(1)) * ESZ[m2.group(2)]
        code, ea, upd, _, nat = mem_ea(c, skel, mn, nbytes)
        s0 = srcs[-1]
        ss = c.size(s0)
        if ss == nbytes:
            val = c.ops[s0]
        elif ss > nbytes:
            val = '%s:%d' % (c.ops[s0], nbytes)
        else:
            s, val = c.tmp(nbytes, 'zext(%s)' % c.ops[s0]); code.append(s)
        code.append('*:%d %s = %s;' % (nbytes, ea, val))
        code.append(upd)
        return ' '.join(x for x in code if x)
    m2 = re.match(r'^VST(0K|K)(\d+)W$', mn)
    if m2:
        n = int(m2.group(2))
        code, ea, upd, _, nat = mem_ea(c, skel, mn, 4 * n)
        val = '0:4' if m2.group(1) == '0K' else c.v4(srcs[0])
        if m2.group(1) == 'K':
            s, val = c.tmp(4, val); code.append(s)
        for i in range(n):
            code.append('*:4 (%s + %d) = %s;' % (ea, 4 * i, val))
        code.append(upd)
        return ' '.join(x for x in code if x)
    # predicated / packing / interleaving vector stores
    code, ea, upd, _, nat = mem_ea(c, skel, mn, VLEN)
    args = [ea] + [c.raw(i) for i in srcs]
    code.append('%s(%s);' % (pop(mn), ', '.join(args)))
    code.append(upd)
    return ' '.join(x for x in code if x)

def sem_pfs(mn, skel, c):
    code, ea, upd, _, nat = mem_ea(c, skel, mn, 0)
    code.append('%s(%s);' % (pop(mn), ea))
    code.append(upd)
    return ' '.join(x for x in code if x)

def sem_atomic(mn, skel, c):
    # ASW/ASD/CASW/CASD *R(N),src,dst
    code, ea, upd, bi, nat = mem_ea(c, skel, mn, 8)
    rest = [i for i in range(bi + nat, len(c.ops))]
    d = rest[-1]
    args = [ea] + [c.raw(i) for i in rest[:-1]]
    s, t = c.tmp(8, '%s(%s)' % (pop(mn), ', '.join(args)))
    code += [s, upd, c.assign(d, t)]
    return ' '.join(x for x in code if x)

# ------------------------------------------------------------------ scalar ALU
BIN64 = {'ADDD': '{a} + {b}', 'SUBD': '{a} - {b}', 'SUBRD': '{b} - {a}', 'ANDD': '{a} & {b}',
         'ANDND': '{a} & ~{b}', 'ORD': '{a} | {b}', 'ORND': '{a} | ~{b}', 'XORD': '{a} ^ {b}',
         'XNORD': '~({a} ^ {b})', 'NANDD': '~({a} & {b})', 'NORD': '~({a} | {b})',
         'SHLD': '{a} << ({b} & 0x3f)', 'SHRD': '{a} s>> ({b} & 0x3f)', 'SHRUD': '{a} >> ({b} & 0x3f)',
         'MPYDD': '{a} * {b}',
         'CMPEQD': 'zext({a} == {b})', 'CMPGTD': 'zext({a} s> {b})', 'CMPGTUD': 'zext({a} > {b})',
         'CMPGED': 'zext({a} s>= {b})', 'CMPGEUD': 'zext({a} >= {b})',
         'LANDD': 'zext(({a} != 0) && ({b} != 0))', 'LORD': 'zext(({a} != 0) || ({b} != 0))',
         'LANDND': 'zext(({a} != 0) && ({b} == 0))',
         'ADDDP': '{a} f+ {b}', 'SUBDP': '{a} f- {b}', 'MPYDP': '{a} f* {b}',
         'CMPEQDP': 'zext({a} f== {b})', 'CMPLTDP': 'zext({a} f< {b})', 'CMPLEDP': 'zext({a} f<= {b})',
         'DIVDW': '{a} s/ sext({b4})', 'DIVUDW': '{a} / zext({b4})',
         'MODDW': '{a} s% sext({b4})', 'MODUDW': '{a} % zext({b4})',
         # predicate-register logic (.P unit)
         'AND': '{a} & {b}', 'ANDN': '{a} & ~{b}', 'OR': '{a} | {b}', 'ORN': '{a} | ~{b}', 'XOR': '{a} ^ {b}',
         'XNOR': '~({a} ^ {b})', 'NAND': '~({a} & {b})', 'NOR': '~({a} | {b})',
         'ADDAB': '{a} + sext({b4})', 'ADDAH': '{a} + (sext({b4}) << 1)', 'ADDAW': '{a} + (sext({b4}) << 2)',
         'ADDAD': '{a} + (sext({b4}) << 3)', 'SUBAB': '{a} - sext({b4})', 'SUBAH': '{a} - (sext({b4}) << 1)',
         'SUBAW': '{a} - (sext({b4}) << 2)', 'SUBAD': '{a} - (sext({b4}) << 3)'}
BIN32 = {'ADDW': '{a4} + {b4}', 'SUBW': '{a4} - {b4}', 'SUBRW': '{b4} - {a4}', 'ANDW': '{a4} & {b4}',
         'ANDNW': '{a4} & ~{b4}', 'ORW': '{a4} | {b4}', 'ORNW': '{a4} | ~{b4}', 'XORW': '{a4} ^ {b4}',
         'XNORW': '~({a4} ^ {b4})', 'NANDW': '~({a4} & {b4})', 'NORW': '~({a4} | {b4})',
         'SHLW': '{a4} << ({b4} & 0x1f)', 'SHRW': '{a4} s>> ({b4} & 0x1f)', 'SHRUW': '{a4} >> ({b4} & 0x1f)',
         'MPYWW': '{a4} * {b4}', 'DIVW': '{a4} s/ {b4}', 'DIVUW': '{a4} / {b4}', 'MODW': '{a4} s% {b4}',
         'MODUW': '{a4} % {b4}',
         'CMPEQW': 'zext({a4} == {b4})', 'CMPGTW': 'zext({a4} s> {b4})', 'CMPGTUW': 'zext({a4} > {b4})',
         'CMPGEW': 'zext({a4} s>= {b4})', 'CMPGEUW': 'zext({a4} >= {b4})',
         'ADDSP': '{a4} f+ {b4}', 'SUBSP': '{a4} f- {b4}', 'MPYSP': '{a4} f* {b4}',
         'CMPEQSP': 'zext({a4} f== {b4})', 'CMPLTSP': 'zext({a4} f< {b4})', 'CMPLESP': 'zext({a4} f<= {b4})'}

def fmt(t, c, a, b):
    def p(x): return '(%s)' % x if not re.match(r'^[\w:]+$', x) else x
    return t.format(a=p(c.v8(a)), b=p(c.v8(b)), a4=c.v4(a), b4=c.v4(b),
                    a2=c.tr(a, 2), b2=c.tr(b, 2))

# element-wise vector ops implemented exactly when every operand is a 64-bit scalar register
LANEOPS = {'VADD': '{a} + {b}', 'VSUB': '{a} - {b}', 'VSUBR': '{b} - {a}', 'VMPY': '{a} * {b}',
           'VSHL': '{a} << {b}', 'VSHR': '{a} s>> {b}', 'VSHRU': '{a} >> {b}',
           'VMAX': '{a} * zext({a} s>= {b}) + {b} * zext({a} s< {b})',
           'VMAXU': '{a} * zext({a} >= {b}) + {b} * zext({a} < {b})',
           'VMIN': '{a} * zext({a} s<= {b}) + {b} * zext({a} s> {b})',
           'VMINU': '{a} * zext({a} <= {b}) + {b} * zext({a} > {b})'}
BITOPS = {'VANDW': '{a} & {b}', 'VANDNW': '{a} & ~{b}', 'VORW': '{a} | {b}', 'VORNW': '{a} | ~{b}',
          'VXORW': '{a} ^ {b}', 'VNANDW': '~({a} & {b})', 'VNORW': '~({a} | {b})', 'VXNORW': '~({a} ^ {b})'}

def lane_op(mn, c):
    m = re.match(r'^(VADD|VSUBR|VSUB|VMPY|VSHL|VSHRU|VSHR|VMAXU|VMAX|VMINU|VMIN)([BHWD])\2?$', mn)
    if not m or len(c.ops) != 3:
        return None
    fam, t = m.group(1), m.group(2)
    if fam == 'VMPY' and not re.match(r'^VMPY(BB|HH|WW|DD)$', mn):
        return None
    if not (c.sizes[0] == 8 and c.sizes[2] == 8 and c.sizes[1] in (8, 'N', 'C')):
        return None
    lw = ESZ[t]; n = 8 // lw
    a, b = c.v8(0), c.v8(1)
    code = []
    lanes = []
    shiftmask = lw * 8 - 1
    for i in range(n):
        if i:
            s0, ta = c.tmp(8, '%s >> %d' % (a, 8 * lw * i)); code.append(s0); sa = '%s:%d' % (ta, lw)
        else:
            sa = c.tr(0, lw)
        if c.sizes[1] in ('N', 'C'):
            sb = c.tr(1, lw)                # scalar constant applies to every lane
        else:
            if i:
                s0, tb = c.tmp(8, '%s >> %d' % (b, 8 * lw * i)); code.append(s0); sb = '%s:%d' % (tb, lw)
            else:
                sb = c.tr(1, lw)
        if fam in ('VSHL', 'VSHR', 'VSHRU'):
            sb = '(%s & %d)' % (sb, shiftmask)
        expr = LANEOPS[fam].format(a=sa, b=sb)
        s, tn = c.tmp(lw, expr)
        code.append(s); lanes.append(tn)
    if n == 1:
        val = lanes[0]
    else:
        val = ' | '.join('(zext(%s) << %d)' % (l, 8 * lw * i) if i else 'zext(%s)' % l for i, l in enumerate(lanes))
    code.append(c.assign(2, val))
    return ' '.join(code)

def bit_op(mn, c):
    if mn not in BITOPS or len(c.ops) != 3:
        return None
    if c.sizes[1] in ('N', 'C'):
        if c.sizes[0] != 8 or c.sizes[2] != 8:
            return None
        s, b = c.tmp(8, '(%s & 0xffffffff) * 0x100000001' % c.raw(1))
        return s + ' ' + c.assign(2, BITOPS[mn].format(a=c.v8(0), b=b))
    if c.sizes[0] == c.sizes[1] == c.sizes[2]:
        return c.assign(2, BITOPS[mn].format(a=c.ops[0], b=c.ops[1]), c.size(2))
    return None

# ------------------------------------------------------------------ generic
NODST = {'SEOPEN', 'SEOPENSC', 'SAOPEN', 'SEBRK', 'SABRK', 'SERSTR', 'NLCINIT', 'HWAOPEN', 'LUTINIT',
         'LUTWR', 'BLKCMO', 'BLKPLD', 'WHIST', 'MARK', 'REVT', 'SYSCALL', 'SECCALL', 'ROOTCALL'}

def generic(mn, skel, c):
    regs = [i for i in range(len(c.ops)) if c.is_reg(i)]
    if not regs or mn in NODST or MEMRE.search(skel) or skel.rstrip().endswith('N') or skel.endswith('L'):
        args = ', '.join(c.raw(i) for i in range(len(c.ops)))
        return '%s(%s);' % (pop(mn), args)
    # destination: last atom, or last pair 'R:R'
    last = len(c.ops) - 1
    if skel.endswith('R:R'):
        hi, lo = last - 1, last
        srcs = [i for i in range(len(c.ops)) if i not in (hi, lo)]
        args = ', '.join(c.raw(i) for i in srcs)
        s1, t1 = c.tmp(c.size(lo), '%s(%s)' % (pop(mn), args))
        s2, t2 = c.tmp(c.size(hi), '%s(%s)' % (pop(mn + '_hi'), args))
        return ' '.join([s1, s2, '%s = %s;' % (c.ops[lo], t1), '%s = %s;' % (c.ops[hi], t2)])
    srcs = list(range(last))
    args = ', '.join(c.raw(i) for i in srcs)
    s, t = c.tmp(c.size(last), '%s(%s)' % (pop(mn), args))
    return s + ' ' + '%s = %s;' % (c.ops[last], t)

def _sem(mn, unit, skel, ops, sizes, r):
    c = Ctx(ops, sizes)
    n = len(ops)
    if mn == 'NOP':
        return ''
    if skel.startswith('*R') or (MEMRE.search(skel) and re.match(r'^(S?LD|VLD)', mn)):
        if re.match(r'^(S?LD|VLD)', mn):
            return sem_load(mn, skel, c)
        if mn in ('ASW', 'ASD', 'CASW', 'CASD'):
            return sem_atomic(mn, skel, c)
    if MEMRE.search(skel):
        if mn.startswith('ST') or mn.startswith('VST'):
            return sem_store(mn, skel, c)
        if mn == 'PFS':
            return sem_pfs(mn, skel, c)
        return generic(mn, skel, c)
    if mn == 'BA' and n == 1:
        return 'goto [%s];' % c.v8(0)
    if mn == 'CALLA' and n == 1:
        s, t = c.tmp(8, c.v8(0))
        return '%s RP = inst_next; call [%s];' % (s, t)
    if mn == 'RETE':
        return '%s(%s); return [RP];' % (pop(mn), ', '.join(c.raw(i) for i in range(n)))
    if mn in ('SYSCALL', 'SECCALL', 'ROOTCALL'):
        return 'software_call(%s);' % ', '.join(c.raw(i) for i in range(n))
    if n == 3 and skel in ('R,R,R', 'R,N,R'):
        if mn in BIN64:
            return c.assign(2, fmt(BIN64[mn], c, 0, 1))
        if mn in BIN32:
            e = fmt(BIN32[mn], c, 0, 1)
            if mn.startswith('CMP') and 'SP' not in mn:
                return c.assign(2, e)
            if mn.startswith('CMP'):
                return c.assign(2, e)
            return c.assign(2, 'zext(%s)' % e)
        if mn in ('MPYHW', 'MPYUHW', 'MPYSUHW'):
            e1 = 'zext' if mn == 'MPYUHW' else 'sext'
            e2 = 'sext' if mn == 'MPYHW' else 'zext'
            s1, t1 = c.tmp(4, '%s(%s)' % (e1, c.tr(0, 2)))
            s2, t2 = c.tmp(4, '%s(%s)' % (e2, c.tr(1, 2)))
            return '%s %s %s' % (s1, s2, c.assign(2, 'zext(%s * %s)' % (t1, t2)))
        r1 = lane_op(mn, c)
        if r1: return r1
        r1 = bit_op(mn, c)
        if r1: return r1
    if n == 2 and skel == 'R,R':
        if mn in ('MV', 'VMV', 'MVC'):
            if c.sizes[0] == c.sizes[1]:
                return '%s = %s;' % (ops[1], ops[0])
            return c.assign(1, c.v8(0))
        if mn == 'NOT':
            return c.assign(1, '~%s' % c.v8(0))
    if n == 2 and skel == 'N,R':
        if mn in ('MVK32', 'MVKU32', 'MVK64'):
            return c.assign(1, c.raw(0))
        if mn == 'ADDKPC':
            return c.assign(1, '(inst_start & 0xffffffffffffffc0) + %s' % c.raw(0))
        if mn in ('VDUPW', 'VMVK32') and c.sizes[1] == 8:
            return c.assign(1, '(%s & 0xffffffff) * 0x100000001' % c.raw(0))
        if mn == 'VDUPH' and c.sizes[1] == 8:
            return c.assign(1, '(%s & 0xffff) * 0x1000100010001' % c.raw(0))
        if mn == 'VDUPB' and c.sizes[1] == 8:
            return c.assign(1, '(%s & 0xff) * 0x101010101010101' % c.raw(0))
        if mn == 'VMVK64' and c.sizes[1] == 8:
            return c.assign(1, c.raw(0))
    if mn in ('EXT', 'EXTU') and skel == 'R,N,N,R':
        s, t = c.tmp(8, '%s << (%s & 0x3f)' % (c.v8(0), c.raw(1)))
        return s + ' ' + c.assign(3, '%s %s (%s & 0x3f)' % (t, 's>>' if mn == 'EXT' else '>>', c.raw(2)))
    return generic(mn, skel, c)

def sem(mn, unit, skel, ops, sizes, r):
    try:
        return _sem(mn, unit, skel, ops, sizes, r)
    except Unsupported:
        return generic(mn, skel, Ctx(ops, sizes)) if not MEMRE.search(skel) else \
            '%s(%s);' % (pop(mn), ', '.join(Ctx(ops, sizes).raw(i) for i in range(len(ops))))
