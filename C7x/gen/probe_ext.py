"""Probe how CSTX0/CSTX1 extend N atoms.
For each key with N atoms: bases (<=4 samples) and all single-bit flips staying in key;
each placed after CSTX0=X or CSTX1=X in a packet.  Output per key: list of
[word, n, ext_atoms(list of str), plain_atoms]"""
import sys, json
import oracle, c7parse
SIL = sys.argv[1]
res = json.load(open(sys.argv[2]))
X = 0x5d2c2b5   # bit 26 set
def cstx(n, v): return ((v & 0x7ffffff) << 5) | (0x17 if n == 0 else 0x1f)
cand = {}
for k, r in res.items():
    if not any(r['kinds'][int(j)] == 'N' for j in r['atom']): continue
    smp = r['samples']
    bases = [smp[i * len(smp) // 4] for i in range(min(4, len(smp)))]
    ws = set(bases)
    for b in bases:
        for i in range(1, 32): ws.add(b ^ (1 << i))
    cand[k] = sorted(ws)
allw = sorted(set(w for ws in cand.values() for w in ws))
plain = dict(zip(allw, oracle.decode_many(allw, SIL)))
words = []; idx = []
for k, ws in cand.items():
    for w in ws:
        t = plain[w]
        if not t or t.startswith('.word'): continue
        p = c7parse.parse(t)
        if c7parse.key(p) != k.split('#')[0]: continue
        for n in (0, 1):
            idx.append((k, w, n, len(words), [a[1] for a in p['atoms']]))
            words += [cstx(n, X), w, 0x0000084e]
texts = oracle.decode_many(words, SIL, group=3)
out = {}
for k, w, n, pos, pa in idx:
    t = texts[pos + 1]
    ea = None
    if t and not t.startswith('.word'):
        p = c7parse.parse(t)
        if c7parse.key(p) == k.split('#')[0]: ea = [a[1] for a in p['atoms']]
    out.setdefault(k, []).append([w, n, ea, pa])
json.dump(dict(X=X, data=out), open(sys.argv[3], 'w'))
print(len(out), 'keys', len(idx), 'packets')
