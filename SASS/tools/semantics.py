"""P-code semantics for generated 128-bit SASS constructors.

gen_sleigh.py describes every form as a mnemonic (base + literal modifiers) and
a list of operands.  Each operand has a *shape* (its text with slots replaced by
$k, e.g. '-$3', 'c[$4][$5]', '[$2.64+$6]', '$1') and the classes of its slots.

roles(form_info) chooses, per operand, how its value is materialized:
   'd4' 'd8' 'd16'   destination register (4/8/16 bytes)
   's4' 's8' 's16'   source value (register / immediate / constant bank)
   'f4' 'f8'         floating point source (negation/abs are float ops)
   'p'  'pd'         predicate source / destination
   'a'               memory address (64-bit for generic, 32-bit for shared/local)
   't'               branch target
   None              not used by the semantics
pcode(form_info, opnd) returns the p-code body, where opnd[i] is the varnode
expression for operand i (already evaluated by the generator).

Instructions without an explicit template get a named pcodeop that reads the
source operands and writes the first destination register.
"""
import re

CMP_INT = {'.EQ': '==', '.NE': '!=', '.LT': 's<', '.LE': 's<=', '.GT': 's>', '.GE': 's>='}
CMP_UNS = {'.EQ': '==', '.NE': '!=', '.LT': '<', '.LE': '<=', '.GT': '>', '.GE': '>='}
CMP_FLT = {'.EQ': 'f==', '.NE': 'f!=', '.LT': 'f<', '.LE': 'f<=', '.GT': 'f>', '.GE': 'f>=',
           '.EQU': 'f==', '.NEU': 'f!=', '.LTU': 'f<', '.LEU': 'f<=', '.GTU': 'f>', '.GEU': 'f>='}
BOOL = {'.AND': '&&', '.OR': '||', '.XOR': '^^'}
SIZE = {'.U8': (1, 'zext'), '.S8': (1, 'sext'), '.U16': (2, 'zext'), '.S16': (2, 'sext'),
        '.64': (8, None), '.128': (16, None), '.U.128': (16, None)}

LOADS = {'LDG': 'ram', 'LD': 'ram', 'LDS': 'shared', 'LDL': 'local'}
STORES = {'STG': 'ram', 'ST': 'ram', 'STS': 'shared', 'STL': 'local'}
NOOPS = {'NOP', 'BSSY', 'BSYNC', 'WARPSYNC', 'BMOV', 'DEPBAR', 'YIELD', 'NANOSLEEP', 'ERRBAR',
         'CCTL', 'MEMBAR', 'FENCE', 'BAR', 'BPT', 'PMTRIG', 'VOTEU', 'WARPGROUP', 'ACQBULK'}

def mods_of(info):
    return set(info['mods'])

def is_reg(info, i, cls=('R', 'UR')):
    o = info['ops'][i]
    return o['shape'] in ('$0',) or (len(o['slots']) == 1 and o['classes'][0] in cls and re.fullmatch(r'[-~!|]*\$\d+(\.reuse)?\|?', o['shape'] or ''))

def opkind(o):
    """Coarse operand kind from shape/classes."""
    sh = o['shape']
    if sh is None:
        return 'other'
    if o.get('pcrel'):
        return 'tgt'
    if sh in ('RZ', 'URZ'):
        return 'zero'
    if sh in ('PT', 'UPT'):
        return 'true'
    if sh in ('!PT', '!UPT'):
        return 'false'
    if re.fullmatch(r'-?0x[0-9a-f]+', sh):
        return 'imm'
    if re.search(r'\bc\[|\bcx\[', sh):
        return 'cbank'
    if sh.startswith('[') or 'desc[' in sh or sh.startswith('-['):
        return 'mem'
    if len(o['classes']) == 1 and re.fullmatch(r'[-~!|]*\$\d+(\.[A-Za-z0-9_]+)*\|?', sh):
        c = o['classes'][0]
        if c in ('R', 'UR'): return 'reg'
        if c in ('P', 'UP'): return 'pred'
        if c == 'hex': return 'tgt' if o.get('pcrel') else 'imm'
        if c == 'flt': return 'fimm'
        if c == 'B': return 'breg'
    return 'other'

def width(mods, default=4):
    for m in mods:
        if m in SIZE:
            return SIZE[m][0]
    return default

def roles(info):
    """Return list of roles (one per operand) or None for generic handling."""
    mn = info['mn']; mods = mods_of(info); ops = info['ops']
    n = len(ops)
    kinds = [opkind(o) for o in ops]
    info['kinds'] = kinds
    # literal RZ / PT operands behave like register / predicate sources
    kinds = ['reg' if k == 'zero' else ('pred' if k in ('true', 'false') else k) for k in kinds]
    R = [None] * n
    def regs_first(k):
        return k in ('reg',)
    base = mn[1:] if mn.startswith('U') and mn not in ('UMOV',) and mn[1:] in TEMPL else mn
    if mn == 'UMOV':
        base = 'MOV'
    t = TEMPL.get(base)
    if t is None:
        # generic: first operand destination register if any
        if n and kinds[0] in ('reg',) and mn not in STORES and mn not in NOOPS and not mn.startswith('ST') \
                and not mn.startswith('RED') and mn not in ('BRA', 'BRX', 'JMP', 'JMX', 'CALL', 'RET', 'EXIT'):
            R[0] = 'd4'
            for i in range(1, n):
                if kinds[i] in ('reg', 'imm', 'cbank', 'fimm'):
                    R[i] = 's4'
                elif kinds[i] == 'pred':
                    R[i] = 'p'
        elif n and kinds[0] == 'pred' and mn not in ('BRA',):
            R[0] = 'pd'
            for i in range(1, n):
                if kinds[i] in ('reg', 'imm', 'cbank', 'fimm'):
                    R[i] = 's4'
                elif kinds[i] == 'pred':
                    R[i] = 'p'
        return R
    try:
        r = t[0](info, kinds, mods)
    except (KeyError, IndexError, TypeError):
        r = None
    return r

# ------------------------------------------------------------------ templates
def _dst_src(info, kinds, mods, w=4, f=False):
    n = len(kinds)
    R = [None] * n
    if n == 0 or kinds[0] != 'reg':
        return R
    R[0] = 'd%d' % w
    for i in range(1, n):
        if kinds[i] in ('reg', 'imm', 'cbank', 'fimm'):
            R[i] = ('f%d' if f else 's%d') % w
        elif kinds[i] == 'pred':
            R[i] = 'p'
    return R

def r_mov(info, kinds, mods):
    return _dst_src(info, kinds, mods)

def p_mov(info, o, R):
    if len(o) >= 2 and o[0] and o[1]:
        return '%s = %s;' % (o[0], o[1])
    return None

def split_preds(kinds, start=1):
    """Leading predicate destination operands after operand 0."""
    i = start
    while i < len(kinds) and kinds[i] == 'pred':
        i += 1
    return i

def r_iadd3(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if kinds[0] != 'reg': return R
    R[0] = 'd4'
    j = split_preds(kinds)
    for i in range(1, j): R[i] = 'pd'
    srcs = list(range(j, min(j + 3, n)))
    for i in srcs:
        if kinds[i] in ('reg', 'imm', 'cbank'): R[i] = 's4'
    for i in range(j + 3, n):
        if kinds[i] == 'pred': R[i] = 'p'
    info['iadd'] = (list(range(1, j)), srcs, list(range(j + 3, n)))
    return R

def p_iadd3(info, o, R):
    pd, srcs, cin = info['iadd']
    if len(srcs) != 3 or not all(o[i] for i in srcs):
        return None
    a, b, c = (o[i] for i in srcs)
    L = []
    L.append('local s1:4 = %s + %s;' % (a, b))
    L.append('local s2:4 = s1 + %s;' % c)
    co = 'local co:1 = zext(carry(%s, %s)) + zext(carry(s1, %s));' % (a, b, c)
    if '.X' in mods_of(info) and cin:
        ci = ' + '.join('zext(%s)' % o[i] for i in cin if o[i])
        L.append('local s3:4 = s2 + %s;' % ci)
        res = 's3'
    else:
        res = 's2'
    if pd:
        L.append(co)
        for k, i in enumerate(pd):
            if o[i]:
                L.append('%s = co > %d;' % (o[i], k))
    L.append('%s = %s;' % (o[0], res))
    return ' '.join(L)

def r_imad(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if kinds[0] != 'reg': return R
    wide = '.WIDE' in mods
    R[0] = 'd8' if wide else 'd4'
    j = split_preds(kinds)
    for i in range(1, j): R[i] = 'pd'
    srcs = list(range(j, min(j + 3, n)))
    for k, i in enumerate(srcs):
        if kinds[i] in ('reg', 'imm', 'cbank'):
            R[i] = 's8' if (wide and k == 2) else 's4'
    for i in range(j + 3, n):
        if kinds[i] == 'pred': R[i] = 'p'
    info['iadd'] = (list(range(1, j)), srcs, list(range(j + 3, n)))
    return R

def p_imad(info, o, R):
    pd, srcs, cin = info['iadd']
    if len(srcs) != 3 or not all(o[i] for i in srcs):
        return None
    a, b, c = (o[i] for i in srcs)
    m = mods_of(info)
    ext = 'zext' if '.U32' in m else 'sext'
    ci = ''
    if '.X' in m and cin:
        ci = ' + ' + ' + '.join('zext(%s)' % o[i] for i in cin if o[i])
    if '.WIDE' in m:
        return 'local p:8 = %s(%s) * %s(%s); %s = p + %s%s;' % (ext, a, ext, b, o[0], c, ci.replace('zext(', 'zext(') )
    if '.HI' in m:
        return 'local p:8 = %s(%s) * %s(%s); local h:4 = p(4); %s = h + %s%s;' % (ext, a, ext, b, o[0], c, ci)
    return '%s = %s * %s + %s%s;' % (o[0], a, b, c, ci)

def r_lop3(info, kinds, mods):
    n = len(kinds); R = [None] * n
    # LOP3.LUT [Pd,] Rd, a, b, c, lut, Pq
    i0 = 0
    if kinds[0] == 'pred':
        R[0] = 'pd'; i0 = 1
    if i0 >= n or kinds[i0] != 'reg':
        return [None] * n
    R[i0] = 'd4'
    for i in range(i0 + 1, min(i0 + 5, n)):
        if kinds[i] in ('reg', 'imm', 'cbank'): R[i] = 's4'
    info['lop'] = i0
    return R

def p_lop3(info, o, R):
    i0 = info['lop']
    if len(o) < i0 + 5 or not all(o[i0 + k] for k in range(5)):
        return None
    d, a, b, c, lut = (o[i0 + k] for k in range(5))
    terms = []
    for i in range(8):
        x = a if (i >> 2) & 1 else '~%s' % a
        y = b if (i >> 1) & 1 else '~%s' % b
        z = c if i & 1 else '~%s' % c
        terms.append('((%s & %s & %s) & (0 - ((%s >> %d) & 1)))' % (x, y, z, lut, i))
    L = 'local r:4 = %s; %s = r;' % (' | '.join(terms), d)
    if i0 == 1 and o[0]:
        L += ' %s = r != 0;' % o[0]
    return L

def r_shf(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n < 4 or kinds[0] != 'reg': return R
    R[0] = 'd4'
    for i in (1, 2, 3):
        if kinds[i] in ('reg', 'imm', 'cbank'): R[i] = 's4'
    return R

def p_shf(info, o, R):
    if not all(o[:4]): return None
    m = mods_of(info)
    d, lo, s, hi = o[:4]
    sh = '(%s & 63)' % s if ('.U64' in m or '.S64' in m) else '(%s & 31)' % s
    L = 'local v:8 = (zext(%s) << 32) | zext(%s); ' % (hi, lo)
    if '.L' in m:
        if '.U64' in m or '.S64' in m:
            L += 'local r:8 = v << zext(%s); ' % sh
        else:
            L += 'local r:8 = zext(%s) << zext(%s); ' % (lo, sh) if '.HI' not in m else 'local r:8 = v << zext(%s); ' % sh
    else:
        if '.S64' in m:
            L += 'local r:8 = v s>> zext(%s); ' % sh
        elif '.S32' in m:
            L += 'local r:8 = sext(%s) s>> zext(%s); ' % (hi, sh) if '.HI' in m else 'local r:8 = v s>> zext(%s); ' % sh
        elif '.U32' in m and '.HI' in m:
            L += 'local r:8 = zext(%s) >> zext(%s); ' % (hi, sh)
        else:
            L += 'local r:8 = v >> zext(%s); ' % sh
    if '.HI' in m and not ('.R' in m and ('.U32' in m or '.S32' in m)):
        L += '%s = r(4);' % d
    else:
        L += '%s = r:4;' % d
    return L

def r_isetp(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n < 5 or kinds[0] != 'pred' or kinds[1] != 'pred': return R
    R[0] = R[1] = 'pd'
    for i in (2, 3):
        if kinds[i] in ('reg', 'imm', 'cbank', 'fimm'): R[i] = 's4'
    for i in range(4, n):
        if kinds[i] == 'pred': R[i] = 'p'
    return R

def p_isetp(info, o, R, flt=False, w=4):
    m = mods_of(info)
    if len(o) < 5 or not all(o[:5]):
        return None
    if '.EX' in m:
        return None
    cmp = None
    tab = CMP_FLT if flt else (CMP_UNS if '.U32' in m else CMP_INT)
    for k, v in tab.items():
        if k in m:
            cmp = v
    if '.T' in m: cmp = 'T'
    if '.F' in m: cmp = 'F'
    if cmp is None:
        return None
    bo = None
    for k, v in BOOL.items():
        if k in m: bo = v
    if bo is None:
        return None
    if cmp == 'T': c = '1:1'
    elif cmp == 'F': c = '0:1'
    else: c = '%s %s %s' % (o[2], cmp, o[3])
    return 'local c:1 = %s; %s = c %s %s; %s = (!c) %s %s;' % (c, o[0], bo, o[4], o[1], bo, o[4])

def r_fsetp(info, kinds, mods):
    R = r_isetp(info, kinds, mods)
    return [('f4' if r == 's4' else r) for r in R]

def r_dsetp(info, kinds, mods):
    R = r_isetp(info, kinds, mods)
    return [('f8' if r == 's4' else r) for r in R]

def r_sel(info, kinds, mods, f=False):
    n = len(kinds); R = [None] * n
    if n < 4 or kinds[0] != 'reg' or kinds[3] != 'pred': return R
    R[0] = 'd4'; R[1] = R[2] = 's4'; R[3] = 'p'
    return R

def p_sel(info, o, R):
    if not all(o[:4]): return None
    return 'if (%s) goto <t>; %s = %s; goto <e>; <t> %s = %s; <e>' % (o[3], o[0], o[2], o[0], o[1])

def r_lea(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if kinds[0] != 'reg': return R
    R[0] = 'd4'
    j = split_preds(kinds)
    for i in range(1, j): R[i] = 'pd'
    hi = '.HI' in mods and '.SX32' not in mods
    cnt = 4 if hi else 3
    for i in range(j + cnt, n):
        if kinds[i] == 'pred': R[i] = 'p'
    for i in range(j, min(j + cnt, n)):
        if kinds[i] in ('reg', 'imm', 'cbank'): R[i] = 's4'
    info['lea'] = (j, cnt)
    return R

def p_lea(info, o, R):
    j, cnt = info['lea']
    if len(o) < j + cnt or not all(o[j:j + cnt]):
        return None
    m = mods_of(info)
    n = len(o)
    cin = ''
    if '.X' in m:
        cp = [o[i] for i in range(j + cnt, n) if R[i] == 'p' and o[i]]
        if not cp:
            return None
        cin = ' + zext(%s)' % cp[0]
    if '.HI' in m:
        if '.SX32' in m:
            a, b, s = o[j:j + 3]
            # high part of (sext(a) << s): (a s>> (32 - s))
            return 'local v:8 = sext(%s) << zext(%s & 31); %s = %s + v(4)%s;' % (a, s, o[0], b, cin)
        a, b, c, s = o[j:j + 4]
        return 'local v:8 = (zext(%s) << 32) | zext(%s); local r:8 = v >> (32 - zext(%s & 31)); %s = %s + r:4%s;' % (c, a, s, o[0], b, cin)
    a, b, s = o[j:j + 3]
    return '%s = (%s << (%s & 31)) + %s%s;' % (o[0], a, s, b, cin)

def r_iabs(info, kinds, mods):
    return _dst_src(info, kinds, mods)

def p_iabs(info, o, R):
    if len(o) < 2 or not all(o[:2]): return None
    return 'local x:4 = %s; %s = x; if (x s>= 0) goto <e>; %s = -x; <e>' % (o[1], o[0], o[0])

def r_imnmx(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n < 4 or kinds[0] != 'reg' or kinds[3] != 'pred': return R
    R[0] = 'd4'; R[1] = R[2] = 's4'; R[3] = 'p'
    return R

def p_imnmx(info, o, R):
    if not all(o[:4]): return None
    lt = '<' if '.U32' in mods_of(info) else 's<'
    return ('local a:4 = %s; local b:4 = %s; local mn:4 = a; local mx:4 = b; if (a %s b) goto <ok>; mn = b; mx = a; <ok> '
            '%s = mx; if (!%s) goto <e>; %s = mn; <e>') % (o[1], o[2], lt, o[0], o[3], o[0])

def r_popc(info, kinds, mods):
    return _dst_src(info, kinds, mods)

def p_popc(info, o, R):
    if len(o) < 2 or not all(o[:2]): return None
    return '%s = popcount(%s);' % (o[0], o[1])

def r_fp(info, kinds, mods, w=4):
    n = len(kinds)
    R = _dst_src(info, kinds, mods, w, f=True)
    return R

def p_fadd(info, o, R, op='f+'):
    if len(o) < 3 or not all(o[:3]): return None
    return '%s = %s %s %s;' % (o[0], o[1], op, o[2])

def p_ffma(info, o, R):
    if len(o) < 4 or not all(o[:4]): return None
    return '%s = (%s f* %s) f+ %s;' % (o[0], o[1], o[2], o[3])

def r_load(info, kinds, mods):
    n = len(kinds); R = [None] * n
    # [Pd,] Rd, [addr] ...
    i = 0
    if kinds[0] == 'pred':
        i = 1
    if i + 1 >= n or kinds[i] != 'reg' or kinds[i + 1] != 'mem':
        return R
    w = width(mods)
    R[i] = 'd%d' % max(w, 4)
    R[i + 1] = 'a'
    info['ld'] = (i, w)
    return R

def p_load(info, o, R):
    i, w = info['ld']
    if not o[i] or not o[i + 1]:
        return None
    sp = LOADS.get(info['mn'], 'ram')
    m = mods_of(info)
    ext = None
    for k, (sz, e) in SIZE.items():
        if k in m: ext = e
    a, pre = o[i + 1], ''
    if sp != 'ram':
        pre = 'local sa:4 = %s:4; ' % a; a = 'sa'
    if ext:
        return pre + '%s = %s(*[%s]:%d %s);' % (o[i], ext, sp, w, a)
    return pre + '%s = *[%s]:%d %s;' % (o[i], sp, w, a)

def r_store(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n < 2 or kinds[0] != 'mem' or kinds[1] != 'reg':
        return R
    w = width(mods)
    R[0] = 'a'; R[1] = 's%d' % max(w, 4)
    info['st'] = w
    return R

def p_store(info, o, R):
    if not o[0] or not o[1]: return None
    w = info['st']
    sp = STORES.get(info['mn'], 'ram')
    v = o[1] if w >= 4 else '%s:%d' % (o[1], w)
    a, pre = o[0], ''
    if sp != 'ram':
        pre = 'local sa:4 = %s:4; ' % a; a = 'sa'
    return pre + '*[%s]:%d %s = %s;' % (sp, w, a, v)

def r_ldc(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n < 2 or kinds[0] != 'reg' or kinds[1] != 'cbank':
        return R
    w = width(mods)
    R[0] = 'd%d' % max(w, 4); R[1] = 'cb%d' % w
    return R

def p_ldc(info, o, R):
    if not o[0] or not o[1]: return None
    m = mods_of(info)
    for k, (sz, e) in SIZE.items():
        if k in m and e:
            return '%s = %s(%s);' % (o[0], e, o[1])
    return '%s = %s;' % (o[0], o[1])

def r_s2r(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n >= 2 and kinds[0] == 'reg':
        R[0] = 'd8' if info['mn'] == 'CS2R' and '.32' not in mods else 'd4'
        R[1] = 'sr'
    return R

def p_s2r(info, o, R):
    if not o[0] or not o[1]: return None
    if R[0] == 'd8':
        return '%s = zext(%s);' % (o[0], o[1])
    return '%s = %s;' % (o[0], o[1])

def r_flow(info, kinds, mods):
    n = len(kinds); R = [None] * n
    for i, k in enumerate(kinds):
        if k == 'tgt': R[i] = 't'
        elif k == 'reg' and info['mn'] in ('BRX', 'JMX', 'RET', 'CALL'): R[i] = 's8'
    return R

def p_bra(info, o, R):
    t = [o[i] for i, r in enumerate(R) if r == 't' and o[i]]
    if t:
        return 'goto %s;' % t[0]
    return None

def p_brx(info, o, R):
    r = [o[i] for i, x in enumerate(R) if x == 's8' and o[i]]
    t = [o[i] for i, x in enumerate(R) if x == 't' and o[i]]
    if r and t:
        return 'local d:8 = %s + %s; goto [d];' % (t[0], r[0])
    if r:
        return 'goto [%s];' % r[0]
    return None

def p_call(info, o, R):
    t = [o[i] for i, r in enumerate(R) if r == 't' and o[i]]
    if t:
        return 'RETPC = inst_next; call %s;' % t[0]
    r = [o[i] for i, x in enumerate(R) if x == 's8' and o[i]]
    if r:
        return 'RETPC = inst_next; call [%s];' % r[0]
    return None

def p_ret(info, o, R):
    return 'return [RETPC];'

def p_exit(info, o, R):
    return 'sass_exit(); return [RETPC];'

def r_hfma2(info, kinds, mods):
    n = len(kinds); R = [None] * n
    o = info['ops']
    if n >= 5 and kinds[0] == 'reg' and o[1]['shape'] in ('RZ', '-RZ') and o[2]['shape'] in ('RZ', '-RZ') \
            and kinds[3] == 'fimm' and kinds[4] == 'fimm':
        R[0] = 'd4'; R[3] = R[4] = 'h'
        info['hmov'] = True
    elif n >= 5 and kinds[0] == 'reg' and kinds[1] == 'reg' and kinds[2] == 'reg' and kinds[3] == 'fimm' and kinds[4] == 'fimm':
        R[0] = 'd4'; R[1] = R[2] = 's4'; R[3] = R[4] = 'h'
        info['hfix'] = True
    else:
        R = _dst_src(info, kinds, mods)
    return R

def p_hfma2(info, o, R):
    if info.get('hmov') and o[0] and o[3] and o[4]:
        # RZ*RZ + {hi, lo}: the compiler's idiom for loading a 32-bit constant
        return '%s = (zext(%s) << 16) | zext(%s);' % (o[0], o[3], o[4])
    if info.get('hfix') and all(o[i] for i in (0, 1, 2, 3, 4)):
        # with a zero multiplicand the result is the packed immediate pair
        return ('local hv:4 = (zext(%s) << 16) | zext(%s); if (%s != 0 && %s != 0) goto <g>; %s = hv; goto <e>; '
                '<g> %s = sass_HFMA2(%s, %s, hv); <e>') % (o[3], o[4], o[1], o[2], o[0], o[0], o[1], o[2])
    return None

def r_prmt(info, kinds, mods):
    n = len(kinds); R = [None] * n
    if n >= 4 and kinds[0] == 'reg' and all(kinds[i] in ('reg', 'imm', 'cbank') for i in (1, 2, 3)):
        R[0] = 'd4'; R[1] = R[2] = R[3] = 's4'
    return R

def p_prmt(info, o, R):
    if len(info['mods']) > 0 and any(m in info['mods'] for m in ('.F4E', '.B4E', '.RC8', '.ECL', '.ECR', '.RC16')):
        return None
    if not all(o[:4]):
        return None
    d, a, sel, b = o[:4]
    parts = []
    for i in range(4):
        parts.append('(((c >> zext(((%s >> %d) & 7) * 8)) & 0xff) << %d)' % (sel, 4 * i, 8 * i))
    return 'local c:8 = (zext(%s) << 32) | zext(%s); local r:8 = %s; %s = r:4;' % (b, a, ' | '.join(parts), d)

def r_bin(info, kinds, mods):
    n = len(kinds); R = [None] * n
    # OP Rd[.CC], Ra, Rb/imm  (Maxwell/Pascal style two-source ALU)
    if n >= 3 and kinds[0] == 'reg' and all(kinds[i] in ('reg', 'imm', 'cbank') for i in (1, 2)):
        R[0] = 'd4'; R[1] = R[2] = 's4'
        for i in range(3, n):
            if kinds[i] in ('reg', 'imm', 'cbank'): R[i] = 's4'
    return R

def p_iadd(info, o, R):
    if not all(o[:3]): return None
    m = mods_of(info)
    if '.X' in m or '.CC' in info.get('text', ''):
        return None
    return '%s = %s + %s;' % (o[0], o[1], o[2])

def p_shl(info, o, R):
    if not all(o[:3]): return None
    return '%s = %s << (%s & 31);' % (o[0], o[1], o[2])

def p_shr(info, o, R):
    if not all(o[:3]): return None
    op = '>>' if '.U32' in mods_of(info) else 's>>'
    return '%s = %s %s (%s & 31);' % (o[0], o[1], op, o[2])

def p_lop(info, o, R):
    if not all(o[:3]): return None
    m = mods_of(info)
    for k, op in (('.AND', '&'), ('.OR', '|'), ('.XOR', '^')):
        if k in m:
            return '%s = %s %s %s;' % (o[0], o[1], op, o[2])
    if '.PASS_B' in m:
        return '%s = %s;' % (o[0], o[2])
    return None

def p_iscadd(info, o, R):
    if len(o) < 4 or not all(o[:4]): return None
    if '.CC' in info.get('text', ''):
        return None
    return '%s = (%s << (%s & 31)) + %s;' % (o[0], o[1], o[3], o[2])

TEMPL = {
    'IADD': (r_bin, p_iadd), 'IADD32I': (r_bin, p_iadd),
    'SHL': (r_bin, p_shl), 'SHR': (r_bin, p_shr),
    'LOP': (r_bin, p_lop), 'LOP32I': (r_bin, p_lop),
    'ISCADD': (r_bin, p_iscadd), 'ISCADD32I': (r_bin, p_iscadd),
    'MOV32I': (r_mov, p_mov),
    'CAL': (r_flow, p_call), 'JCAL': (r_flow, p_call),
    'PRMT': (r_prmt, p_prmt),
    'HFMA2': (r_hfma2, p_hfma2),
    'MOV': (r_mov, p_mov),
    'IADD3': (r_iadd3, p_iadd3),
    'IMAD': (r_imad, p_imad),
    'LOP3': (r_lop3, p_lop3),
    'SHF': (r_shf, p_shf),
    'ISETP': (r_isetp, p_isetp),
    'FSETP': (r_fsetp, lambda i, o, R: p_isetp(i, o, R, flt=True)),
    'DSETP': (r_dsetp, lambda i, o, R: p_isetp(i, o, R, flt=True)),
    'SEL': (r_sel, p_sel), 'FSEL': (r_sel, p_sel),
    'LEA': (r_lea, p_lea),
    'IABS': (r_iabs, p_iabs),
    'IMNMX': (r_imnmx, p_imnmx),
    'POPC': (r_popc, p_popc),
    'FADD': (r_fp, p_fadd), 'FMUL': (r_fp, lambda i, o, R: p_fadd(i, o, R, 'f*')),
    'FFMA': (r_fp, p_ffma),
    'DADD': (lambda i, k, m: r_fp(i, k, m, 8), p_fadd),
    'DMUL': (lambda i, k, m: r_fp(i, k, m, 8), lambda i, o, R: p_fadd(i, o, R, 'f*')),
    'DFMA': (lambda i, k, m: r_fp(i, k, m, 8), p_ffma),
    'LDG': (r_load, p_load), 'LD': (r_load, p_load), 'LDS': (r_load, p_load), 'LDL': (r_load, p_load),
    'STG': (r_store, p_store), 'ST': (r_store, p_store), 'STS': (r_store, p_store), 'STL': (r_store, p_store),
    'LDC': (r_ldc, p_ldc), 'LDC': (r_ldc, p_ldc),
    'S2R': (r_s2r, p_s2r), 'CS2R': (r_s2r, p_s2r), 'S2UR': (r_s2r, p_s2r),
    'BRA': (r_flow, p_bra), 'BRX': (r_flow, p_brx), 'JMP': (r_flow, p_bra), 'JMX': (r_flow, p_brx),
    'CALL': (r_flow, p_call), 'RET': (r_flow, p_ret), 'EXIT': (r_flow, p_exit),
}
TEMPL['ULDC'] = TEMPL['LDC']

def pcode(info, o, R):
    mn = info['mn']
    base = mn
    if mn == 'UMOV':
        base = 'MOV'
    elif mn.startswith('U') and mn[1:] in TEMPL and mn not in TEMPL:
        base = mn[1:]
    t = TEMPL.get(base)
    if t is not None:
        try:
            r = t[1](info, o, R)
        except (KeyError, IndexError, TypeError):
            r = None
        if r is not None:
            return r, None
    # generic pcodeop
    if mn in NOOPS:
        return '', None
    dst = [i for i, r in enumerate(R) if r in ('d4', 'pd') and o[i]]
    src = [o[i] for i, r in enumerate(R) if r in ('s4', 'p', 'f4', 's8', 'f8') and o[i]]
    op = 'sass_' + re.sub(r'\W', '_', mn)
    args = ', '.join(src)
    if dst:
        i = dst[0]
        if R[i] == 'pd':
            return '%s = %s(%s);' % (o[i], op, args), op
        return '%s = %s(%s);' % (o[i], op, args), op
    return '%s(%s);' % (op, args), op
