import json, sys, collections, os
import c7parse
W=os.path.dirname(os.path.abspath(sys.argv[1]))
E = json.load(open(sys.argv[1])); X = E['X']
res = json.load(open(sys.argv[2]))
summ = {}
forms = collections.Counter()
for k, lst in E['data'].items():
    r = res[k]
    nat = [int(j) - 2 for j in r['atom'] if r['kinds'][int(j)] == 'N']
    info = {}
    for w, n, ea, pa in lst:
        if ea is None:
            info.setdefault('invalid', set()).add(n); continue
        for j in nat:
            pv = c7parse.numval(pa[j]); ev = c7parse.numval(ea[j])
            if pv == ev: continue
            f = None
            for sh in range(0, 40):
                lowm = (1 << sh) - 1
                raw = (X << sh) | (pv & lowm)
                if ev == raw: f = (sh, 'u'); break
                if ev == (raw | (0xffffffffffffffff << (27 + sh))) & 0xffffffffffffffff: f = (sh, 's'); break
                if ev == raw & 0xffffffff: f = (sh, 'u32'); break
            info.setdefault(j, set()).add((n, f))
    summ[k] = {str(a): sorted(map(str, b)) for a, b in info.items()}
    for a, b in info.items():
        if a != 'invalid': forms[tuple(sorted(map(str, b)))] += 1
for f, c in forms.most_common(): print(c, f)
json.dump(summ, open(os.path.join(W, os.path.basename(sys.argv[1]).replace('ext', 'extsumm', 1)), 'w'), indent=0)

# condition analysis
cond = collections.Counter(); odd = []
EXT = {}
for k, lst in E['data'].items():
    r = res[k]
    nat = [int(j) - 2 for j in r['atom'] if r['kinds'][int(j)] == 'N']
    for j in nat:
        for n in (0, 1):
            A = []; B = []
            for w, nn, ea, pa in lst:
                if nn != n or ea is None: continue
                (A if ea[j] != pa[j] else B).append(w)
            if not A: continue
            det = []
            for i in range(1, 32):
                av = set(w >> i & 1 for w in A); bv = set(w >> i & 1 for w in B)
                if B and len(av) == 1 and av.isdisjoint(bv): det.append((i, av.pop()))
            fm = [f for f in summ[k].get(str(j), []) if f.startswith('(%d' % n)]
            EXT.setdefault(k, []).append(dict(atom=j, n=n, det=det, nB=len(B), form=fm))
            if not B: cond['always'] += 1
            elif det: cond[str([d for d in det if d[0] not in r['atom'].get(str(j+2), {}).get('bits', [])][:3])] += 1
            else: odd.append((k, j, n))
print(cond.most_common(20)); print(len(odd), odd[:20])
json.dump(EXT, open(os.path.join(W, os.path.basename(sys.argv[1]).replace('ext', 'ext_rules', 1)), 'w'))
