"""Random-sample dis7x over p=0 words; collect per-key sample words. Usage: sample.py SIL NWORDS OUT.json"""
import sys, os, json, random
from multiprocessing import Pool
import oracle, c7parse

SIL = sys.argv[1]; N = int(sys.argv[2]); OUT = sys.argv[3]
CH = 50000

def job(seed):
    rnd = random.Random(seed * 7919 + int(SIL))
    ws = [rnd.getrandbits(32) & ~1 for _ in range(CH)]
    res = {}
    for a, w, t in oracle.decode(ws, SIL):
        if t.startswith('.word'):
            continue
        p = c7parse.parse(t)
        if not p: continue
        k = c7parse.key(p)
        lst = res.setdefault(k, [0, []])
        lst[0] += 1
        if len(lst[1]) < 40: lst[1].append(w)
    return res

if __name__ == '__main__':
    tot = {}
    with Pool(12) as pool:
        for r in pool.imap(job, range(N // CH)):
            for k, (c, ws) in r.items():
                e = tot.setdefault(k, [0, []]); e[0] += c
                if len(e[1]) < 40: e[1].extend(ws[:40 - len(e[1])])
    json.dump(tot, open(OUT, 'w'))
    print(len(tot), 'keys', len(set(k.split('|')[0] for k in tot)), 'mnemonics')
