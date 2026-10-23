"""Split keys whose atoms are inconsistent (atoms share selector bits) into sub-keys.
Usage: refine.py SIL in.json out.json"""
import sys, json, itertools
import infer
infer.SIL = sys.argv[1]
res = json.load(open(sys.argv[2]))
out = {}
todo = {}
for k, r in res.items():
    bad = [j for j, a in r['atom'].items() if (not a.get('manual') and a['consistent'] is False) or
           (a.get('manual') and r['unitbase'] != '.B1')]
    used = set(b for a in r['atom'].values() for b in a['bits']) | set(r['infl'].get('0', []))
    dc = [i for i in range(1, 32) if r['var'] >> i & 1 and i not in used]
    if len(dc) > 3:
        dc = [b for b in range(5, 14) if r['var'] >> b & 1]   # union of several opcodes
        if len(dc) > 8: dc = []
    if not bad and not dc:
        out[k] = r; continue
    cnt = {}
    for j, a in r['atom'].items():
        for b in set(a['bits']): cnt[b] = cnt.get(b, 0) + 1
    sets = [tuple(a['bits']) for a in r['atom'].values()]
    shared = sorted(b for b, c in cnt.items() if c >= 2 and
                    len(set(s for s in sets if b in s)) >= 2) if bad else []
    shared = sorted(set(shared) | set(dc))
    if len(shared) > 8 or not shared:
        print('cannot split', k, shared, file=sys.stderr); out[k] = r; continue
    todo[k] = (r, shared)
# build sub-keys
sub = {}
for k, (r, shared) in todo.items():
    for vals in itertools.product((0, 1), repeat=len(shared)):
        ws = []
        for w in r['samples']:
            w2 = w
            for b, v in zip(shared, vals):
                w2 = (w2 & ~(1 << b)) | (v << b)
            ws.append(w2)
        ps = infer.dec(ws)
        good = [w for w, p in zip(ws, ps) if p and p['key'] == k]
        if not good: continue
        r2 = dict(r)
        m = sum(1 << b for b in shared); v = sum(vv << b for b, vv in zip(shared, vals))
        r2['fixed_mask'] = r['fixed_mask'] | m
        r2['fixed_val'] = r['fixed_val'] | v
        r2['var'] = r['var'] & ~m
        r2['samples'] = sorted(set(good))
        r2['infl'] = {int(j): [b for b in bl if b not in shared] for j, bl in r['infl'].items()}
        r2['infl'] = {j: bl for j, bl in r2['infl'].items() if bl}
        r2['parent'] = k
        sub['%s#%s' % (k, ''.join('%d=%d' % (b, vv) for b, vv in zip(shared, vals)))] = r2
infer.dec([w for r in sub.values() for w in r['samples']])
infer.round2(sub)
for k, r in sub.items():
    bad = [j for j, a in r['atom'].items() if a.get('manual') or a['consistent'] is False]
    print('sub', k, 'still bad' if bad else 'ok', file=sys.stderr)
    out[k] = r
json.dump(out, open(sys.argv[3], 'w'))
