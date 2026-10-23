"""Black-box inference of C7x encodings from dis7x (no TI binaries are inspected; only
input words -> output text).   Usage: infer.py SIL samples.json out.json"""
import sys, json, random
import oracle, c7parse

SIL = sys.argv[1] if len(sys.argv) > 1 else '7100'
CACHE = {}
EXTRA = set()

def dec(words):
    need = sorted(set(w for w in words if w not in CACHE))
    if need:
        for w, t in zip(need, oracle.decode_many(need, SIL)):
            p = None
            if t is not None and not t.startswith('.word'):
                p = c7parse.parse(t)
                if p is not None:
                    p['key'] = c7parse.key(p); p['text'] = t
            CACHE[w] = p
    return [CACHE[w] for w in words]

def sig(p):
    return [p['unit'], p['pred'] or ''] + [a[1] for a in p['atoms']]

def setbits(base, bl, v):
    w = base & ~sum(1 << i for i in bl)
    for n, i in enumerate(bl):
        if v >> n & 1: w |= 1 << i
    return w

def round1(groups, keys):
    rnd = random.Random(1)
    bases = {}
    probes = []
    for k in keys:
        b = groups[k][:]; rnd.shuffle(b)
        pri = [w for w in b if w in EXTRA]
        b = (pri[:20] + [w for w in b if w not in EXTRA])[:max(20, min(len(pri), 40))]
        bases[k] = b
        probes += [w ^ (1 << i) for w in b for i in range(1, 32)]
    dec(probes)
    res = {}; newkeys = {}
    for k in keys:
        ws = groups[k]
        var = 0
        for w in ws[1:]: var |= w ^ ws[0]
        infl = {}
        same = set(ws)
        for w in bases[k]:
            p0 = CACHE[w]; s0 = sig(p0)
            for i in range(1, 32):
                q = CACHE[w ^ (1 << i)]
                if q is None: continue
                if q['key'] != k:
                    newkeys.setdefault(q['key'], w ^ (1 << i)); continue
                var |= 1 << i; same.add(w ^ (1 << i))
                s1 = sig(q)
                for j in range(len(s0)):
                    if s1[j] != s0[j]: infl.setdefault(j, set()).add(i)
        var &= ~1
        p0 = CACHE[ws[0]]
        res[k] = dict(key=k, fixed_mask=0xfffffffe & ~var, fixed_val=ws[0] & 0xfffffffe & ~var, var=var,
                      infl={j: sorted(v) for j, v in infl.items()}, samples=sorted(same),
                      skel=p0['skel'], mn=p0['mn'], unitbase=c7parse.unit_base(p0['unit']),
                      haspred=bool(p0['pred']), kinds=['U', 'P'] + [a[0] for a in p0['atoms']],
                      example=p0['text'], example_word=ws[0])
    return res, newkeys

def round2(res):
    req = []
    for k, r in res.items():
        smp = r['samples']
        # prefer bases without crosspath X
        nox = [w for w in smp if not CACHE[w]['unit'].endswith('X')] or smp
        r['bases'] = [nox[0], nox[len(nox) // 2]] if len(nox) > 1 else [nox[0]]
        for j, bl in r['infl'].items():
            if j == 0: continue
            if len(bl) <= 12:
                for base in r['bases']:
                    req += [setbits(base, bl, v) for v in range(1 << len(bl))]
    dec(req)
    for k0, r in res.items():
        k = r.get('parent', k0)
        r['atom'] = {}
        for j, bl in r['infl'].items():
            if j == 0: continue
            if len(bl) > 12:
                r['atom'][j] = dict(bits=bl, manual=True); continue
            tabs = []
            for base in r['bases']:
                tab = {}
                for v in range(1 << len(bl)):
                    q = CACHE[setbits(base, bl, v)]
                    if q is None or q['key'] != k: tab[v] = None
                    else: tab[v] = [sig(q)[j], q['unit'].endswith('X')]
                tabs.append(tab)
            cons = all(t == tabs[0] for t in tabs)
            if not cons:
                # names consistent but X differs?  keep names, mark X unknown
                names_same = all({v: (e[0] if e else None) for v, e in t.items()} ==
                                 {v: (e[0] if e else None) for v, e in tabs[0].items()} for t in tabs)
                cons = 'names' if names_same else False
            r['atom'][j] = dict(bits=bl, table=tabs[0], consistent=cons)

def main():
    samp = json.load(open(sys.argv[2]))
    allw = set(w for k, (c, ws) in samp.items() for w in ws)
    if len(sys.argv) > 4 and sys.argv[4]:
        EXTRA.update(json.load(open(sys.argv[4])))
        allw |= EXTRA
    allw = sorted(allw)
    groups = {}
    for w, p in zip(allw, dec(allw)):
        if p: groups.setdefault(p['key'], []).append(w)
    res = {}
    todo = list(groups)
    for it in range(4):
        print('round', it, 'keys', len(todo), file=sys.stderr)
        r, nk = round1(groups, todo)
        res.update(r)
        todo = []
        for k, w in nk.items():
            if k not in res and k not in groups:
                groups[k] = [w]; todo.append(k)
        if not todo: break
    round2(res)
    json.dump(res, open(sys.argv[3], 'w'))
    print('keys', len(res), file=sys.stderr)

if __name__ == '__main__':
    main()
