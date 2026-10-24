"""Instruction-form model shared by the learner, the SLEIGH generator and the tests.

A *form* describes a set of instruction words that share some fixed bits and
print with the same token skeleton.  Its display is the token list of a
"generic" seed word in which

  * slots   - value tokens (register, hex number, float) computed linearly
              from word bits,
  * groups  - small sets of bits whose combined value selects a replacement
              for a token region (modifiers, decorations, optional operands),
  * specials- replacements of a region around slots when a slot holds a
              special value (zero / all-ones / negative)

are substituted.  render() reproduces nvdisasm's text for a word, which lets the
learner validate itself without Ghidra; gen_sleigh.py turns the same data into
SLEIGH constructors.
"""
import re, struct, math

# ------------------------------------------------------------------ tokens
TOKRE = re.compile(r"""
   (?P<cs>,\ )
 | (?P<sp>\ )
 | (?P<hex>-?0x[0-9a-fA-F]+)
 | (?P<flt>[-+]?(?:\d+\.\d+(?:e[-+]\d+)?|\d+e[-+]\d+|\d+|INF|QNAN|SNAN|NAN)(?![A-Za-z0-9_]))
 | (?P<nid>\d+[A-Za-z_][A-Za-z0-9_]*)
 | (?P<dot>\.[A-Za-z0-9_?]+)
 | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
 | (?P<q>\?\?\?)
 | (?P<p>.)
""", re.X)

def tokenize(t):
    return [m.group(0) for m in TOKRE.finditer(t)]

REGRE = re.compile(r'^(R|UR|P|UP|B)(\d+)$')
REGZ = {'R': (255, 'RZ'), 'UR': (63, 'URZ'), 'P': (7, 'PT'), 'UP': (7, 'UPT')}
ZNAME = {v[1]: (k, v[0]) for k, v in REGZ.items()}
HEXRE = re.compile(r'^-?0x[0-9a-fA-F]+$')
FLTRE = re.compile(r'^[-+]?(?:\d+\.\d+(?:e[-+]\d+)?|\d+e[-+]\d+|\d+|INF|QNAN|SNAN|NAN)$')

def classify(tok):
    """-> (cls, value) for value tokens, else None.  cls in R UR P UP B hex flt."""
    m = REGRE.match(tok)
    if m:
        return m.group(1), int(m.group(2))
    if tok in ZNAME:
        return ZNAME[tok]
    if HEXRE.match(tok):
        return 'hex', int(tok, 16)
    if FLTRE.match(tok):
        return 'flt', tok
    return None

def is_value_tok(tok):
    return classify(tok) is not None

def mnem_of(toks):
    """Base mnemonic: first identifier token after an optional guard."""
    i = 0
    if toks and toks[0] == '@':
        i = 1
        while i < len(toks) and toks[i] != ' ':
            i += 1
    for t in toks[i:]:
        if re.match(r'^[A-Za-z_]', t):
            return t
    return None

# ------------------------------------------------------------------ floats
def f16(r):
    return struct.unpack('<e', struct.pack('<H', r & 0xffff))[0]
def f32(r):
    return struct.unpack('<f', struct.pack('<I', r & 0xffffffff))[0]
def f64hi(r):
    return struct.unpack('<d', struct.pack('<Q', (r & 0xffffffff) << 32))[0]
def f64(r):
    return struct.unpack('<d', struct.pack('<Q', r & 0xffffffffffffffff))[0]
FLTFMT = {'f16': (16, f16), 'f32': (32, f32), 'f64hi': (32, f64hi), 'f64': (64, f64)}

def parse_flt(tok):
    t = tok.strip()
    s = -1.0 if t.startswith('-') else 1.0
    u = t.lstrip('+-')
    if u == 'INF': return s * math.inf
    if u in ('QNAN', 'SNAN', 'NAN'): return ('nan', s, u)
    return float(t)

def flt_full(fmt, raw):
    """(width, IEEE bit pattern) of a float slot value.  Formats: f16, f32, f64hi (32-bit
    field = upper half of a double), f64, and f32tN / f64tN: an N-bit field holding the
    top N bits of an f32 / f64 (Maxwell/Pascal 20-bit float immediates)."""
    if fmt in ('f16', 'f32', 'f64'):
        return FLTFMT[fmt][0], raw
    if fmt == 'f64hi':
        return 64, (raw & 0xffffffff) << 32
    m = re.match(r'f(32|64)t(\d+)$', fmt)
    if m:
        wd, n = int(m.group(1)), int(m.group(2))
        return wd, (raw & ((1 << n) - 1)) << (wd - n)
    raise KeyError(fmt)

def fdec(fmt, raw):
    wd, b = flt_full(fmt, raw)
    return {16: f16, 32: f32, 64: f64}[wd](b)

def flt_match(tok, fmt, raw):
    """Does raw (encoded per fmt) print as tok?"""
    try:
        x = fdec(fmt, raw)
        wd, full = flt_full(fmt, raw)
    except Exception:
        return False
    y = parse_flt(tok)
    if isinstance(y, tuple):
        if not math.isnan(x): return False
        neg = math.copysign(1.0, x) < 0
        if (y[1] < 0) != neg: return False
        quiet = (full >> {16: 9, 32: 22, 64: 51}[wd]) & 1
        return (y[2] == 'QNAN') == bool(quiet) or y[2] == 'NAN'
    if math.isnan(x): return False
    if x == y:
        return True
    if y == 0 or x == 0: return False
    return abs(x - y) <= abs(y) * 1e-15

# ------------------------------------------------------------------ slot values
def bit(w, b):
    return (w >> b) & 1

def slot_raw(slot, w):
    """Field value (unsigned, bits in significance order)."""
    v = 0
    for i, b in enumerate(slot['bits']):
        v |= bit(w, b) << i
    return v

def slot_value(slot, w):
    raw = slot_raw(slot, w)
    n = len(slot['bits'])
    if slot.get('signed') and n and (raw >> (n - 1)) & 1:
        raw -= 1 << n
    return slot.get('add', 0) + raw * slot.get('scale', 1)

def fmt_value(slot, w):
    cls = slot['cls']
    if cls == 'flt':
        return '%%%s:0x%x' % (slot['fmt'], slot_raw(slot, w))
    v = slot_value(slot, w)
    if cls == 'hex':
        return ('-0x%x' % -v) if v < 0 else ('0x%x' % v)
    if cls == 'dec':
        return '%d' % v
    z = REGZ.get(cls)
    if z and v == z[0]:
        return z[1]
    return '%s%d' % (cls, v)

def slot_state(slot, w):
    """Special state of a slot: 'max' (all ones), 'zero', or None."""
    raw = slot_raw(slot, w)
    n = len(slot['bits'])
    if 'max' in slot.get('spec', ()) and raw == (1 << n) - 1:
        return 'max'
    if 'zero' in slot.get('spec', ()) and raw == 0:
        return 'zero'
    if 'neg' in slot.get('spec', ()) and (raw >> (n - 1)) & 1:
        return 'neg'
    return None

# ------------------------------------------------------------------ rendering
def group_value(g, w):
    v = 0
    for i, b in enumerate(g['bits']):
        v |= bit(w, b) << i
    return v

def _expand(out, form, w):
    res = []
    for t in out:
        if isinstance(t, int):
            res.append(fmt_value(form['slots'][t], w))
        else:
            res.append(t)
    return res

class RenderConflict(Exception):
    pass

def render_items(form, w):
    """Item list (strings and ('s', k) slot markers) for word w, or None if invalid."""
    if (w & form['mask']) != form['val']:
        return None
    toks = form['toks']
    reps = []   # (lo, hi, out)
    suppressed = set()
    for sp in form.get('specials', []):
        if 'gis' not in sp:
            continue
        st = tuple(slot_state(form['slots'][k], w) for k in sp['slots'])
        if all(s is None for s in st):
            continue
        key = ','.join(s or '-' for s in st) + '|' + ','.join(str(group_value(form['groups'][gi], w)) for gi in sp['gis'])
        if key not in sp['cases']:
            continue
        out = sp['cases'][key]
        if out is None:
            return None
        reps.append((sp['lo'], sp['hi'], out))
        suppressed |= set(sp['gis'])
    for gi, g in enumerate(form['groups']):
        if gi in suppressed:
            continue
        out = g['table'].get(group_value(g, w))
        if out is None:
            return None
        reps.append((g['lo'], g['hi'], out))
    reps.sort(key=lambda r: (r[0], r[1]))
    slotpos = {s['pos']: k for k, s in enumerate(form['slots'])}
    items = []
    pos = 0
    def lit(i):
        return ('s', slotpos[i]) if i in slotpos else toks[i]
    for lo, hi, out in reps:
        if lo < pos:
            raise RenderConflict()
        items.extend(lit(i) for i in range(pos, lo))
        items.extend(('s', t) if isinstance(t, int) else t for t in out)
        pos = hi
    items.extend(lit(i) for i in range(pos, len(toks)))
    # specials: region relative to the anchor slot marker
    acts = []
    for sp in form.get('specials', []):
        if 'gis' in sp:
            continue
        st = tuple(slot_state(form['slots'][k], w) for k in sp['slots'])
        if all(s is None for s in st):
            continue
        key = ','.join(s or '-' for s in st)
        if key not in sp['cases']:
            continue
        try:
            idx = items.index(('s', sp['slots'][0]))
        except ValueError:
            continue
        acts.append((idx, sp, sp['cases'][key]))
    acts.sort(key=lambda a: -a[0])
    for idx, sp, out in acts:
        if out is None:
            return None
        lo, hi = idx + sp['rlo'], idx + sp['rhi']
        if lo < 0 or hi > len(items):
            raise RenderConflict()
        items[lo:hi] = [('s', t) if isinstance(t, int) else t for t in out]
    return items

def render_tokens(form, w):
    items = render_items(form, w)
    if items is None:
        return None
    return [fmt_value(form['slots'][x[1]], w) if isinstance(x, tuple) else x for x in items]

def render(form, w):
    try:
        r = render_tokens(form, w)
    except RenderConflict:
        return '<conflict>'
    return None if r is None else ''.join(r)

# ------------------------------------------------------------------ comparison
FLTTOK = re.compile(r'%(f16|f32|f64hi|f64|f32t\d+|f64t\d+):(0x[0-9a-f]+)')

def same_text(model_text, nv_text):
    """Compare a model rendering (floats as %fmt:raw) with nvdisasm text."""
    if model_text is None or nv_text is None:
        return model_text == nv_text
    if '%' not in model_text:
        return model_text == nv_text
    a = FLTTOK.split(model_text)
    # a = [lit, fmt, raw, lit, fmt, raw, lit ...]
    pat = ''
    for i, x in enumerate(a):
        if i % 3 == 0:
            pat += re.escape(x)
        elif i % 3 == 1:
            pat += r'([-+]?(?:\d+\.\d+(?:e[-+]\d+)?|\d+e[-+]\d+|\d+|INF|QNAN|SNAN|NAN))'
    m = re.fullmatch(pat, nv_text)
    if not m:
        return False
    for j, g in enumerate(m.groups()):
        fmt, raw = a[3 * j + 1], int(a[3 * j + 2], 16)
        if not flt_match(g, fmt, raw):
            return False
    return True

def to_json(form):
    f = dict(form)
    f['mask'] = '%x' % form['mask']; f['val'] = '%x' % form['val']
    f['groups'] = [dict(g, table={str(k): v for k, v in g['table'].items()}) for g in form['groups']]
    return f

def from_json(f):
    form = dict(f)
    form['mask'] = int(f['mask'], 16); form['val'] = int(f['val'], 16)
    form['groups'] = [dict(g, table={int(k): v for k, v in g['table'].items()}) for g in f['groups']]
    return form

def load_spec(path):
    import json, gzip
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'rt') as f:
        return json.load(f)

def save_spec(d, path):
    import json, gzip
    op = gzip.open if path.endswith('.gz') else open
    with op(path, 'wt') as f:
        json.dump(d, f, separators=(',', ':'))

# ------------------------------------------------------------------ opcode keys
def is64(arch):
    return arch in ('SM35', 'SM37', 'SM50', 'SM52', 'SM53', 'SM60', 'SM61', 'SM62')

def word_key(arch, w):
    """Index key of an instruction word (opcode field)."""
    return (w >> 52) & 0xfff if is64(arch) else w & 0xfff

def form_keys(arch, f):
    """All keys a form can match (forms of 64-bit encodings may not fix every key bit)."""
    if not is64(arch):
        return [f['val'] & 0xfff]
    km = (f['mask'] >> 52) & 0xfff
    kv = (f['val'] >> 52) & 0xfff
    free = [b for b in range(12) if not (km >> b) & 1]
    if len(free) > 8:
        return [None]
    out = []
    for x in range(1 << len(free)):
        k = kv
        for i, b in enumerate(free):
            k |= ((x >> i) & 1) << b
        out.append(k)
    return out
