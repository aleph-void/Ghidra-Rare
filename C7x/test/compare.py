#!/usr/bin/env python3
"""Compare Ghidra disassembly against TI dis7x for a raw word stream.

  compare.py fuzz  SIL N SEED OUTDIR     random words (p-bit clear => one-word packets)
  compare.py words SIL FILE OUTDIR       words (hex, one per line, packets allowed)

Writes OUTDIR/{in.bin, dis7x.txt, ghidra.txt, mismatches.txt} and prints the match rate over
the words dis7x decodes (plus how many dis7x-invalid words Ghidra wrongly decodes).
"""
import sys, os, re, random, subprocess, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'gen'))
import oracle, c7parse

M64 = (1 << 64) - 1
NUM = re.compile(r'-?0x[0-9a-fA-F]+|-?\b\d+\b')

def canon_nums(s):
    def rep(m):
        t = m.group(0)
        neg = t.startswith('-')
        v = int(t.lstrip('-'), 0)
        if neg: v = -v
        return '#%x' % (v & M64)
    return NUM.sub(rep, s)

def norm_dis(addr, text):
    t = text.strip()
    if t.startswith('||'): t = t[2:]
    # fetch-packet relative branch targets
    def lab(m):
        v = int(m.group(2), 0)
        if m.group(1) == '-': v = -v
        return '0x%x' % (((addr & ~0x3f) + v) & M64)
    t = re.sub(r'\$([+-])(0x[0-9a-f]+|\d+)', lab, t)
    m = re.match(r'^(\[!?A\d\])?\s*(B|CALL|BNL|CALLE|BE) \.B1$', t)
    if m:   # dis7x prints a branch to a symbol-less address 0 without operand
        t = t + ' 0x0'
    return re.sub(r'\s+', '', canon_nums(t))

def norm_ghidra(text):
    t = text.strip()
    if t.startswith('||'): t = t[2:]
    return re.sub(r'\s+', '', canon_nums(t))

def run_ghidra(sil, binpath, out):
    lang = 'C7x:LE:64:C%s' % sil
    subprocess.run([os.path.join(HERE, 'ghidra_dis.sh'), lang, binpath, out], check=True)
    res = {}
    for ln in open(out):
        p = ln.rstrip('\n').split(' ', 2)
        if len(p) < 3: continue
        res[int(p[0], 16)] = p[2]
    return res

def main():
    mode, sil = sys.argv[1], sys.argv[2]
    if mode == 'fuzz':
        n, seed, od = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
        rnd = random.Random(seed)
        words = [rnd.getrandbits(32) & ~1 for _ in range(n)]
    else:
        od = sys.argv[4]
        words = [int(l.split()[0], 16) for l in open(sys.argv[3]) if l.strip() and not l.startswith('#')]
    os.makedirs(od, exist_ok=True)
    binp = os.path.join(od, 'in.bin')
    with open(binp, 'wb') as f:
        for w in words: f.write(struct.pack('<I', w))
    texts = oracle.decode_many(words, sil, group=len(words) if mode != 'fuzz' else 1) if mode == 'fuzz' \
        else [t for a, w, t in oracle.decode(words, sil)]
    with open(os.path.join(od, 'dis7x.txt'), 'w') as f:
        for i, (w, t) in enumerate(zip(words, texts)):
            f.write('%08x %08x %s\n' % (i * 4, w, t))
    g = run_ghidra(sil, binp, os.path.join(od, 'ghidra.txt'))
    tot = ok = 0; inv = inv_bad = 0
    bymn = collections.Counter(); badmn = collections.Counter()
    mism = []
    for i, (w, t) in enumerate(zip(words, texts)):
        a = i * 4
        gt = g.get(a, 'BAD')
        if t is None or t.startswith('.word'):
            inv += 1
            if gt != 'BAD':
                inv_bad += 1
                mism.append('%08x %08x INVALID-in-dis7x  ghidra: %s' % (a, w, gt))
            continue
        tot += 1
        mn = c7parse.parse(t)['mn']
        bymn[mn] += 1
        if gt != 'BAD' and norm_dis(a, t) == norm_ghidra(gt):
            ok += 1
        else:
            badmn[mn] += 1
            mism.append('%08x %08x dis7x: %-50s ghidra: %s' % (a, w, t, gt))
    with open(os.path.join(od, 'mismatches.txt'), 'w') as f:
        f.write('\n'.join(mism) + '\n')
    print('dis7x-decodable words: %d  ghidra matches: %d (%.2f%%)' % (tot, ok, 100.0 * ok / max(tot, 1)))
    print('dis7x-invalid words: %d  ghidra decodes anyway: %d' % (inv, inv_bad))
    print('worst mnemonics:', badmn.most_common(15))

if __name__ == '__main__':
    main()
