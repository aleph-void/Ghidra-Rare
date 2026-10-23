#!/usr/bin/env python3
"""Recompute the slot specials of the forms in a spec with the current learner.
  refresh_specials.py <ARCH> <spec.json> [--all]
By default only forms with a special whose region reaches into the mnemonic."""
import sys, os, json, random, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import learn as LN
from sassmodel import from_json, to_json
_L = None
def _init(arch):
    global _L
    _L = LN.Learner(arch, rng=random.Random(os.getpid()), jobs=1)
def _do(fj):
    try:
        f = from_json(fj)
        _L.respecial(f)
        st, _ = _L.validate(f, n=120)
        f['score'] = dict(st)
        return to_json(f)
    except Exception:
        return fj
def crosses(fj):
    U = LN.units(fj['toks'])
    pos = {k: s['pos'] for k, s in enumerate(fj['slots'])}
    for sp in fj.get('specials', []):
        if 'gis' in sp:
            lo, hi = sp['lo'], sp['hi']
        else:
            a = pos[sp['slots'][0]]; lo, hi = a + sp['rlo'], a + sp['rhi']
        us = {u for u in U[max(0, lo):hi] if u is not None}
        if (-1 in us and len(us) > 1) or LN.crosses_sep(U, lo, hi):
            return True
    return False
def main():
    arch, path = sys.argv[1], sys.argv[2]
    d = json.load(open(path))
    idx = [i for i, f in enumerate(d['forms']) if '--all' in sys.argv or crosses(f) or any(s.get('xspec') for s in f['slots'])]
    print('refreshing', len(idx), 'forms', flush=True)
    with mp.Pool(20, initializer=_init, initargs=(arch,)) as pool:
        for i, fj in zip(idx, pool.imap(_do, [d['forms'][i] for i in idx], chunksize=2)):
            d['forms'][i] = fj
    json.dump(d, open(path, 'w'))
if __name__ == '__main__':
    main()
