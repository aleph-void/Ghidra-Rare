"""dis7x oracle: decode lists of 32-bit words with TI's C7000 disassembler (black box)."""
import os, subprocess, tempfile, re

S = os.environ.get('C7X_CGT') or '/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad/tools/ti/inst/ti-cgt-c7000_5.0.2.LTS'
BIN = os.path.join(S, 'bin')
LINE = re.compile(r'^0x([0-9a-f]+)\s+([0-9a-f]{8})\s(.*)$')

def decode(words, silicon='7100', keep_lines=False):
    """Return list of (addr, word, text) for words placed at address 0 in .text."""
    with tempfile.TemporaryDirectory(dir=os.environ.get('C7X_TMP')) as d:
        asm = os.path.join(d, 'a.asm'); obj = os.path.join(d, 'a.obj')
        with open(asm, 'w') as f:
            f.write('\t.text\n')
            for w in words:
                f.write('\t.word 0x%08x\n' % (w & 0xffffffff))
        subprocess.run([os.path.join(BIN, 'asm7x'), '-mv%s' % silicon if False else '--silicon_version=%s' % silicon, asm, obj],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = subprocess.run([os.path.join(BIN, 'dis7x'), '-qq', '-i', '-v=%s' % silicon, obj],
                             check=True, capture_output=True, text=True).stdout
    res = []
    for ln in out.splitlines():
        m = LINE.match(ln)
        if m:
            res.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3).strip()))
    return res

if __name__ == '__main__':
    import sys
    sil = os.environ.get('SIL', '7100')
    ws = [int(x, 16) for x in sys.argv[1:]]
    for a, w, t in decode(ws, sil):
        print('%04x %08x %s' % (a, w, t))

_POOL = None
def _dec(args):
    ws, sil, g = args
    try:
        r = decode(ws, sil)
    except subprocess.CalledProcessError:
        if len(ws) <= g:
            return ['.word CRASH'] * len(ws)
        h = (len(ws) // g // 2) * g
        return _dec((ws[:h], sil, g)) + _dec((ws[h:], sil, g))
    out = [None] * len(ws)
    for a, w, t in r:
        out[a // 4] = t
    return out

def decode_many(words, silicon='7100', chunk=39996, procs=12, group=1):
    """Decode many independent words (each should have p-bit clear); returns texts aligned to words."""
    global _POOL
    from multiprocessing import Pool
    if _POOL is None:
        _POOL = Pool(procs)
    words = list(words)
    chunks = [(words[i:i + chunk], silicon, group) for i in range(0, len(words), chunk)]
    out = []
    for r in _POOL.imap(_dec, chunks):
        out.extend(r)
    return out
