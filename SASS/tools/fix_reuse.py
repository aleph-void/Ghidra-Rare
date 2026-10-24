#!/usr/bin/env python3
"""Re-learn the operand-reuse flags (bits 122-125) of 128-bit forms.

nvdisasm only accepts / prints ".reuse" for some scheduling control values; forms
learned with a control word that rejects reuse have those bits fixed to 0.  This
pass re-probes them with a reuse-friendly control word and turns each into a
one-bit group that inserts ".reuse" after its operand.
  fix_reuse.py <ARCH> <spec.json>"""
import sys, os, json, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import nvd, learn as LN
from sassmodel import from_json, to_json, tokenize, load_spec, save_spec

REUSE = [122, 123, 124, 125]
CTRL = (0x000fe4 << 104) & LN.CTRL_MASK
ARCH = None
_L = None

def learner():
    global _L
    if _L is None:
        _L = LN.Learner(ARCH, jobs=1)
    return _L

def fix(fj):
    f = from_json(fj)
    fixed = [b for b in REUSE if (f['mask'] >> b) & 1 and not (f['val'] >> b) & 1]
    if not fixed:
        return fj, 0
    w = (int(f['seed'], 16) & ~LN.CTRL_MASK) | CTRL
    words = [w] + [w | (1 << b) for b in fixed]
    res = nvd.disasm(ARCH, words, use_cache=False, jobs=1)
    if res[0] is None:
        return fj, 0
    base = tokenize(res[0])
    if base != f['toks']:
        return fj, 0
    n = 0
    for b, t in zip(fixed, res[1:]):
        if t is None:
            continue
        tk = tokenize(t)
        if tk == base:
            # flag not shown for this instruction: a don't-care bit
            f['mask'] &= ~(1 << b)
            f['val'] &= ~(1 << b)
            n += 1
            continue
        lo, hi, out = LN.region(base, tk)
        if not (lo == hi and out == ['.reuse']):
            continue
        hit = [g for g in f['groups'] if LN.overlaps((g['lo'], g['hi']), (lo, hi)) or g['hi'] == lo or g['lo'] == lo]
        hit = [g for g in hit if not set(g['bits']) & set(LN.GUARD_BITS)]
        if hit:
            # the flag prints next to another modifier group (e.g. R2.reuse.H0_H0): merge them
            g = hit[0]
            gi = f['groups'].index(g)
            if len(g['bits']) >= 8 or any(gi in sp.get('gis', []) for sp in f.get('specials', [])):
                continue
            L = learner()
            L.O.rebase = False
            ng = L.enum_one(w, base, sorted(g['bits'] + [b]), min(g['lo'], lo), max(g['hi'], hi), dict(f, groups=[x for x in f['groups'] if x is not g]))
            if ng is None:
                continue
            f['groups'][gi] = ng     # in place: specials refer to groups by index
        else:
            f['groups'].append(dict(bits=[b], lo=lo, hi=hi, table={0: [], 1: ['.reuse']}))
        f['mask'] &= ~(1 << b)
        f['val'] &= ~(1 << b)
        n += 1
    return to_json(f), n

def init(a):
    global ARCH
    ARCH = a

def main():
    arch, path = sys.argv[1], sys.argv[2]
    d = load_spec(path)
    with mp.Pool(20, initializer=init, initargs=(arch,)) as p:
        res = p.map(fix, d['forms'], chunksize=16)
    d['forms'] = [r[0] for r in res]
    save_spec(d, path)
    print('reuse groups added:', sum(r[1] for r in res), 'forms touched:', sum(1 for r in res if r[1]))

if __name__ == '__main__':
    main()
