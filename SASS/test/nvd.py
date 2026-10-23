"""Batch driver for NVIDIA nvdisasm on raw instruction words.

nvdisasm refuses to print anything for a raw file that contains an illegal
instruction, but it reports most illegal words on stderr together with their
address.  We therefore run a batch, replace every reported word by a NOP and
re-run; words that still fail without an address are isolated by bisection.

disasm() returns, for every word, the text nvdisasm prints when the word sits
at address 0 (PC-relative targets are rebased by running each batch at two base
addresses).  Results are cached on disk per architecture (JSONL).

Environment:
  SASS_NV      directory holding the nvdisasm builds (see TOOLS below)
  SASS_WORK    cache / temp directory
"""
import os, re, subprocess, tempfile, json, sys
from concurrent.futures import ThreadPoolExecutor

S = '/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad'
NV = os.environ.get('SASS_NV', S + '/tools/nv')
WORK = os.environ.get('SASS_WORK', S + '/work/sass')
TOOLS = {
    '13': NV + '/x/nvidia/cu13/bin/nvdisasm',     # CUDA 13.4: SM75 .. SM121
    '12': NV + '/nvdis-12.4.127/bin/nvdisasm',    # CUDA 12.4: SM50 .. SM90a
    '11': NV + '/nvdis-11.8.86/bin/nvdisasm',     # CUDA 11.8: SM35 .. SM90
}
WIDE8 = {'SM35', 'SM37', 'SM50', 'SM52', 'SM53', 'SM60', 'SM61', 'SM62'}
NOP128 = 0x000fc00000000000_0000000000007918

def isz_of(arch):
    return 8 if arch in WIDE8 else 16

def smnum(arch):
    return int(re.match(r'SM(\d+)', arch).group(1))

def tool_for(arch):
    a = smnum(arch)
    if a >= 75: return os.environ.get('NVDISASM', TOOLS['13'])
    if a >= 50: return TOOLS['12']
    return TOOLS['11']

LINE = re.compile(r'^\s*/\*([0-9a-f]+)\*/\s*(.*?)\s*$')
ERRADDR = re.compile(r'at address (0x[0-9a-f]+)')
NUMTOK = re.compile(r'(-?)(0x[0-9a-f]+)')
REL_SHIFT = 0x1000000

def _norm(t):
    t = t.strip()
    if t.endswith(';'): t = t[:-1]
    t = re.sub(r'\s+', ' ', t).strip()
    return re.sub(r' +,', ',', t)

CTRL64 = 0x001ffc00fd8007f1          # Maxwell/Pascal control word (no reuse, no barriers)
NOP64 = 0x50b0000000070f00           # Maxwell/Pascal NOP
CTRL_K = 0x0880b8b0a0a08cc0          # Kepler control word
FILL_K = 0x86400000109c0002          # Kepler filler (S2R R0, SR_TID.X)
KEPLER = {'SM35', 'SM37'}

def bundle_of(arch):
    """(words per bundle, control word, filler) for 64-bit encodings."""
    if arch in KEPLER:
        return 8, CTRL_K, FILL_K
    return 4, CTRL64, NOP64

def _exec(arch, words, base, isz, tmpdir, asis=False):
    if isz == 8 and BUNDLE and not asis:
        return _exec64(arch, words, base, tmpdir)
    fd, path = tempfile.mkstemp(dir=tmpdir, suffix='.bin')
    with os.fdopen(fd, 'wb') as f:
        for w in words:
            f.write(w.to_bytes(isz, 'little'))
    try:
        p = subprocess.run([tool_for(arch), '-b', arch, '-base', hex(base), path],
                           capture_output=True, text=True)
    finally:
        os.unlink(path)
    if p.returncode != 0:
        bad = {int(m.group(1), 16) for m in ERRADDR.finditer(p.stderr)}
        return None, bad
    out = {}
    for ln in p.stdout.splitlines():
        m = LINE.match(ln)
        if m:
            out[int(m.group(1), 16)] = _norm(m.group(2))
    return [out.get(base + i * isz) for i in range(len(words))], None

BUNDLE = True   # 64-bit encodings: each word is disassembled in its own bundle

def _exec64(arch, words, base, tmpdir):
    """64-bit (Kepler/Maxwell/Pascal) words: one bundle per word, [ctrl, word, filler...].
    Word i is reported at logical address base + 8*i (physical: base*N + 8*N*i + 8)."""
    nb, ctrl, fill = bundle_of(arch)
    fd, path = tempfile.mkstemp(dir=tmpdir, suffix='.bin')
    with os.fdopen(fd, 'wb') as f:
        for w in words:
            for x in [ctrl, w] + [fill] * (nb - 2):
                f.write(x.to_bytes(8, 'little'))
    try:
        p = subprocess.run([tool_for(arch), '-b', arch, '-base', hex(base * nb), path],
                           capture_output=True, text=True)
    finally:
        os.unlink(path)
    if p.returncode != 0:
        bad = set()
        for m in ERRADDR.finditer(p.stderr):
            a = int(m.group(1), 16) - base * nb
            bad.add(base + (a // (8 * nb)) * 8)
        return None, bad
    out = {}
    for ln in p.stdout.splitlines():
        m = LINE.match(ln)
        if m:
            out[int(m.group(1), 16)] = _norm(m.group(2))
    return [out.get(base * nb + 8 * nb * i + 8) for i in range(len(words))], None

def _raw(arch, words, base, isz, tmpdir, filler):
    """Disassemble words at base; illegal ones -> None."""
    words = list(words)
    illegal = [False] * len(words)
    for _ in range(6):
        r, bad = _exec(arch, words, base, isz, tmpdir)
        if r is not None:
            return [None if il else t for il, t in zip(illegal, r)]
        idx = [(a - base) // isz for a in bad if base <= a < base + isz * len(words)]
        idx = [i for i in idx if not illegal[i]]
        if not idx:
            break
        for i in idx:
            illegal[i] = True; words[i] = filler
    if len(words) == 1:
        return [None]
    h = len(words) // 2
    a = _raw(arch, words[:h], base, isz, tmpdir, filler)
    b = _raw(arch, words[h:], base + h * isz, isz, tmpdir, filler)
    return [None if il else t for il, t in zip(illegal, a + b)]

def _rebase(t0, t1, addr, shift=REL_SHIFT):
    """t0 printed at addr, t1 at addr+shift.  Return text as if at address 0."""
    if t0 == t1 or t0 is None or t1 is None:
        return t0
    a = NUMTOK.split(t0); b = NUMTOK.split(t1)
    if len(a) != len(b):
        return t0
    out = []
    i = 0
    while i < len(a):
        if i % 3 == 0:
            out.append(a[i]); i += 1; continue
        sa, na, sb, nb = a[i], a[i + 1], b[i], b[i + 1]
        va = int(na, 16) * (-1 if sa else 1); vb = int(nb, 16) * (-1 if sb else 1)
        if vb - va == shift:
            v = va - addr
            out.append(('-0x%x' % -v) if v < 0 else ('0x%x' % v))
        else:
            out.append(sa + na)
        i += 2
    return ''.join(out)

def filler_for(arch):
    return NOP128 if isz_of(arch) == 16 else 0x50b0000000070f00

def _batch(arch, words, isz, tmpdir, rebase=True):
    f = filler_for(arch)
    r0 = _raw(arch, words, 0, isz, tmpdir, f)
    if not rebase:
        return r0
    good = [i for i, t in enumerate(r0) if t is not None]
    if not good:
        return r0
    # second run (only legal words) shifted by REL_SHIFT to detect pc-relative numbers
    ws = [words[i] if r0[i] is not None else f for i in range(len(words))]
    r1, _ = _exec(arch, ws, REL_SHIFT, isz, tmpdir)
    if r1 is None:
        return r0
    if isz == 8 and BUNDLE:
        # 64-bit: word i sits at physical 8*N*i+8; "address 0" means its bundle starts at 0
        nb = bundle_of(arch)[0]
        return [_rebase(t0, t1, 8 * nb * i, nb * REL_SHIFT) if t0 is not None else None for i, (t0, t1) in enumerate(zip(r0, r1))]
    return [_rebase(t0, t1, i * isz) if t0 is not None else None for i, (t0, t1) in enumerate(zip(r0, r1))]

class Cache:
    def __init__(self, arch, path=None):
        self.arch = arch
        self.path = path or os.path.join(WORK, 'cache3', arch + '.jsonl')
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.d = {}
        if os.path.exists(self.path):
            with open(self.path) as f:
                for ln in f:
                    try:
                        k, v = json.loads(ln)
                        self.d[k] = v
                    except Exception:
                        pass
        self.f = open(self.path, 'a')
    def put(self, k, v):
        self.d[k] = v
        self.f.write(json.dumps([k, v]) + '\n')
    def flush(self): self.f.flush()

_caches = {}
def cache(arch):
    if arch not in _caches: _caches[arch] = Cache(arch)
    return _caches[arch]

JOBS = int(os.environ.get('NVD_JOBS', '16'))

def disasm(arch, words, batch=512, jobs=None, use_cache=True, rebase=True):
    """Disassemble each word as if it were located at address 0.
    Returns list of normalized text, or None where nvdisasm rejects the word."""
    jobs = jobs or JOBS
    isz = isz_of(arch)
    c = cache(arch) if use_cache else None
    todo = []
    seen = set()
    for w in words:
        k = '%x' % w
        if (c is None or k not in c.d) and k not in seen:
            seen.add(k); todo.append(w)
    tmpdir = os.path.join(WORK, 'tmp'); os.makedirs(tmpdir, exist_ok=True)
    res = {}
    if todo:
        chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
        def work(ch):
            return ch, _batch(arch, ch, isz, tmpdir, rebase)
        with ThreadPoolExecutor(jobs) as ex:
            for ch, r in ex.map(work, chunks):
                for w, t in zip(ch, r):
                    res['%x' % w] = t
                    if c is not None: c.put('%x' % w, t)
        if c is not None: c.flush()
    if c is not None:
        return [c.d['%x' % w] for w in words]
    return [res['%x' % w] for w in words]

def _raw_asis(arch, words, base, isz, tmpdir):
    """64-bit image disassembled as laid out (control words included); bisect on failure."""
    r, bad = _exec(arch, words, base, isz, tmpdir, asis=True)
    if r is not None:
        return r
    nb = bundle_of(arch)[0]
    if len(words) <= nb:
        return [None] * len(words)
    h = (len(words) // nb // 2) * nb or nb
    return _raw_asis(arch, words[:h], base, isz, tmpdir) + _raw_asis(arch, words[h:], base + h * isz, isz, tmpdir)

def disasm_file(arch, path, base=0):
    """Disassemble a raw file in place (absolute addresses); illegal words -> None."""
    isz = isz_of(arch)
    data = open(path, 'rb').read()
    words = [int.from_bytes(data[i:i + isz], 'little') for i in range(0, len(data) - isz + 1, isz)]
    tmpdir = os.path.join(WORK, 'tmp'); os.makedirs(tmpdir, exist_ok=True)
    if isz == 8:
        nb = bundle_of(arch)[0]
        chunks = [(i, words[i:i + 64 * nb]) for i in range(0, len(words), 64 * nb)]
        out = []
        with ThreadPoolExecutor(JOBS) as ex:
            for r in ex.map(lambda a: _raw_asis(arch, a[1], base + a[0] * isz, isz, tmpdir), chunks):
                out.extend(r)
        return words, out
    f = filler_for(arch)
    chunks = [(i, words[i:i + 1024]) for i in range(0, len(words), 1024)]
    def work(a):
        i, ch = a
        return _raw(arch, ch, base + i * isz, isz, tmpdir, f)
    out = []
    with ThreadPoolExecutor(JOBS) as ex:
        for r in ex.map(work, chunks):
            out.extend(r)
    return words, out

if __name__ == '__main__':
    arch = sys.argv[1]
    ws = [int(x, 16) for x in sys.argv[2:]]
    for w, t in zip(ws, disasm(arch, ws, use_cache=False)):
        print('%032x' % w, t)
