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
    if len(shared) > 8 and bad:
        # many shared bits: split first on the bits common to every inconsistent atom (typically a
        # direction/selector bit, e.g. MVCI bit 6)
        common = set.intersection(*[set(a['bits']) for a in r['atom'].values()])
        if 0 < len(common) <= 3:
            shared = sorted(common | set(dc)) if len(common | set(dc)) <= 8 else sorted(common)
        elif 0 < len(dc) <= 4:
            shared = sorted(dc)        # split on the opcode-like bits first (e.g. VPUT* bits 10/12)
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
        # bits that never vary among the sub-key's valid samples and belong to no operand are fixed
        # (e.g. VPUT* CUCR form: bits 30-31 must be 0)
        g0 = r2['samples'][0]
        gv = 0
        for w in r2['samples'][1:]: gv |= w ^ g0
        ib = sum(1 << b for bl in r2['infl'].values() for b in bl)
        nv = r2['var'] & (gv | ib) & ~1
        if nv != r2['var']:
            r2['var'] = nv
            r2['fixed_mask'] = 0xfffffffe & ~nv
            r2['fixed_val'] = g0 & r2['fixed_mask']
        sub['%s#%s' % (k, ''.join('%d=%d' % (b, vv) for b, vv in zip(shared, vals)))] = r2
infer.dec([w for r in sub.values() for w in r['samples']])
infer.round2(sub)
for k, r in sub.items():
    bad = [j for j, a in r['atom'].items() if a.get('manual') or a['consistent'] is False]
    print('sub', k, 'still bad' if bad else 'ok', file=sys.stderr)
    out[k] = r

# Orphan pass: bits that vary within a key but belong to no operand field are treated as
# don't-care by gen.py.  Flip each orphan bit on a few samples; if an operand's text changes, the
# bit belongs to that operand -> add it and re-enumerate the operand tables.
def orphan_pass(out):
    todo = {}
    probes = []
    for k in sorted(out):
        r = out[k]
        infl = {int(j): list(b) for j, b in r['infl'].items()}
        used = set(b for bl in infl.values() for b in bl)
        orph = [b for b in range(1, 32) if r['var'] >> b & 1 and b not in used]
        if not orph: continue
        bases = r['samples'][:8]
        todo[k] = (infl, orph, bases)
        probes += bases + [w ^ (1 << b) for w in bases for b in orph]
    infer.dec(probes)
    changed = {}
    for k, (infl, orph, bases) in todo.items():
        add = False
        for b in orph:
            for w in bases:
                p0 = infer.CACHE.get(w); q = infer.CACHE.get(w ^ (1 << b))
                if not p0 or not q or q['key'] != p0['key']: continue
                s0, s1 = infer.sig(p0), infer.sig(q)
                if len(s0) != len(s1): continue
                for j in range(2, len(s0)):
                    if s0[j] != s1[j] and b not in infl.setdefault(j, []):
                        infl[j].append(b); add = True
        if add:
            r = out[k]
            r['infl'] = {j: sorted(v) for j, v in infl.items()}
            changed[k] = r
    if changed:
        infer.dec([w for r in changed.values() for w in r['samples']])
        infer.round2(changed)
    print('orphan pass: keys updated', len(changed), file=sys.stderr)

# Overlap pass: operand fields that share bits usually come from a few unlucky base words (e.g. a
# source equal to SE0++ changes how another operand prints).  Re-derive each operand's bits by
# majority vote over up to 24 sample words and re-enumerate if that removes the overlap.
def overlap_pass(out):
    todo = {}
    probes = []
    for k in sorted(out):
        r = out[k]
        sets = [set(a['bits']) for a in r['atom'].values() if not a.get('manual')]
        cnt = {}
        for st in sets:
            for b in st: cnt[b] = cnt.get(b, 0) + 1
        if not any(c > 1 for c in cnt.values()): continue
        bases = r['samples'][::max(1, len(r['samples']) // 24)][:24]
        todo[k] = bases
        probes += bases + [w ^ (1 << b) for w in bases for b in range(1, 32)]
    infer.dec(probes)
    changed = {}
    for k, bases in todo.items():
        r = out[k]
        votes = {}; tot = {}
        for w in bases:
            p0 = infer.CACHE.get(w)
            if not p0: continue
            s0 = infer.sig(p0)
            for b in range(1, 32):
                if (r['fixed_mask'] >> b) & 1: continue      # selector bits of a refined sub-key
                q = infer.CACHE.get(w ^ (1 << b))
                if not q or q['key'] != p0['key']: continue
                s1 = infer.sig(q)
                if len(s1) != len(s0): continue
                tot[b] = tot.get(b, 0) + 1
                for j in range(len(s0)):
                    if s0[j] != s1[j]: votes[(j, b)] = votes.get((j, b), 0) + 1
        infl = {}
        for (j, b), v in votes.items():
            if v * 2 > tot[b]: infl.setdefault(j, []).append(b)
        sets = [set(v) for j, v in infl.items() if j >= 2]
        allb = [b for st in sets for b in st]
        if len(allb) != len(set(allb)):
            continue          # still overlapping: leave as is
        old = {int(j): sorted(v) for j, v in r['infl'].items()}
        if any(j >= 2 and j not in infl for j in old):
            continue
        r['infl'] = {j: sorted(v) for j, v in infl.items()}
        changed[k] = r
    if changed:
        infer.dec([w for r in changed.values() for w in r['samples']])
        infer.round2(changed)
    print('overlap pass: keys updated', len(changed), sorted(changed)[:20], file=sys.stderr)

overlap_pass(out)
orphan_pass(out)
json.dump(out, open(sys.argv[3], 'w'))
