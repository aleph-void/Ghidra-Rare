#!/usr/bin/env python3
"""Learn a complete form specification for one 128-bit SASS architecture.

  build_spec.py SM80 [--corpus words.txt ...] [--out spec/SM80.json] [--rounds N]

Seeds come from (a) instruction words of real cubins (corpus files: one hex
word per line, optional count) and (b) a random probe of all 4096 opcode values.
Forms are learned in parallel until every seed is reproduced by some form (or
the round limit is reached).  The resulting JSON is consumed by gen_sleigh.py.
"""
import sys, os, json, random, argparse, collections, time, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import nvd
import learn as LN
from sassmodel import render, same_text, to_json, from_json, tokenize, mnem_of, word_key, form_keys, is64

def probe_words(arch, per_op=48, seed=7):
    rng = random.Random(seed)
    out = []
    if is64(arch):
        g = 18 if arch in ('SM35', 'SM37') else 16
        for op in range(4096):
            for k in range(per_op):
                dens = [0.05, 0.1, 0.25, 0.5, 0.75][k % 5]
                w = op << 52
                for b in range(0, 52):
                    if rng.random() < dens:
                        w |= 1 << b
                w = (w & ~(0xf << g)) | (7 << g)
                out.append(w)
        return out
    for op in range(4096):
        for k in range(per_op):
            dens = [0.02, 0.05, 0.1, 0.25, 0.5][k % 5]
            w = op | (7 << 12)
            for b in range(16, 105):
                if rng.random() < dens:
                    w |= 1 << b
            out.append(w | LN.CTRL_STD)
    return out

_L = None
def _init(arch):
    global _L
    _L = LN.Learner(arch, rng=random.Random(os.getpid()), jobs=1)

def _learn(seed):
    t0 = time.time()
    try:
        f = _L.learn(seed)
        if f is None:
            return seed, None, None, time.time() - t0
        return seed, LN_to_json(f), None, time.time() - t0
    except Exception as e:
        import traceback
        return seed, None, traceback.format_exc()[-800:], time.time() - t0

def _check(fj):
    """Re-validate a form learned on another architecture."""
    try:
        f = from_json(fj)
        f['arch'] = _L.arch
        st, bad = _L.validate(f, n=120)
        ok = st.get('ok', 0); nb = st.get('bad', 0) + st.get('under', 0)
        if ok >= 20 and nb <= max(1, (ok + nb) // 50):
            f['score'] = dict(st)
            return to_json(f)
    except Exception:
        pass
    return None

def LN_to_json(f):
    return to_json(f)

class Spec:
    def __init__(self, arch):
        self.arch = arch
        self.forms = []
        self.byop = collections.defaultdict(list)
    def add(self, f):
        self.forms.append(f)
        for k in form_keys(self.arch, f):
            self.byop[k].append(f)
    def match(self, w, text):
        """Return (form, ok) of the first form whose pattern matches w and renders text."""
        cands = [f for f in self.byop.get(word_key(self.arch, w), []) + self.byop.get(None, []) if (w & f['mask']) == f['val']]
        for f in cands:
            try:
                if same_text(render(f, w), text):
                    return f, True
            except Exception:
                pass
        return (cands[0] if cands else None), False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch')
    ap.add_argument('--corpus', nargs='*', default=[])
    ap.add_argument('--out')
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--jobs', type=int, default=18)
    ap.add_argument('--per-op', type=int, default=48)
    ap.add_argument('--max-new', type=int, default=4000)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--init', help='spec of a related architecture to transfer forms from')
    a = ap.parse_args()
    arch = a.arch
    out = a.out or os.path.join(HERE, '..', 'spec', arch + '.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)

    corpus = []
    for p in a.corpus:
        for ln in open(p):
            x = ln.split()
            if x:
                corpus.append(int(x[0], 16))
    t0 = time.time()
    ctext = nvd.disasm(arch, corpus) if corpus else []
    seeds = [(w, t) for w, t in zip(corpus, ctext) if t]
    print('corpus', len(corpus), 'valid', len(seeds), '%.0fs' % (time.time() - t0), flush=True)
    pw = probe_words(arch, a.per_op)
    ptext = nvd.disasm(arch, pw)
    probes = [(w, t) for w, t in zip(pw, ptext) if t]
    print('probes', len(pw), 'valid', len(probes), 'ops', len({word_key(arch, w) for w, _ in probes}), '%.0fs' % (time.time() - t0), flush=True)

    spec = Spec(arch)
    if a.resume and os.path.exists(out):
        for f in json.load(open(out))['forms']:
            spec.add(from_json(f))
    allseeds = seeds + probes
    tried = set()
    errors = []
    with mp.Pool(a.jobs, initializer=_init, initargs=(arch,)) as pool:
        if a.init:
            src = json.load(open(a.init))['forms']
            kept = 0
            for fj in pool.imap_unordered(_check, src, chunksize=4):
                if fj:
                    spec.add(from_json(fj)); kept += 1
            print('transferred', kept, 'of', len(src), 'forms from', a.init, '%.0fs' % (time.time() - t0), flush=True)
        for rnd in range(a.rounds):
            unc = []
            for w, t in allseeds:
                f, ok = spec.match(w, t)
                if not ok:
                    unc.append((w, t))
            print('round', rnd, 'uncovered', len(unc), 'forms', len(spec.forms), flush=True)
            if not unc:
                break
            # choose representatives: one per (opcode, mnemonic, token skeleton)
            reps = {}
            cnt = collections.Counter()
            for w, t in unc:
                sk = (word_key(arch, w), tuple('#' if LN.classify(x) else x for x in tokenize(t) if x not in ('.reuse',)))
                cnt[sk] += 1
                if sk not in reps and w not in tried:
                    reps[sk] = w
            # most frequent skeletons first (real code dominates the corpus seeds)
            todo = [reps[sk] for sk, _ in cnt.most_common() if sk in reps]
            todo = todo[:a.max_new]
            for w in todo:
                tried.add(w)
            print('  learning', len(todo), flush=True)
            n = 0
            newseeds = []
            for seed, fj, err, dt in pool.imap_unordered(_learn, todo, chunksize=1):
                n += 1
                if err:
                    errors.append((hex(seed), err))
                    continue
                if fj is None:
                    continue
                f = from_json(fj)
                spec.add(f)
                sw = int(f['seed'], 16)
                for b in f.get('struct', []):
                    newseeds.append(sw ^ (1 << b))
                for x in f.get('spawn', []):
                    newseeds.append(int(x, 16))
                if n % 200 == 0:
                    print('   ', n, len(spec.forms), flush=True)
            if newseeds:
                nt = nvd.disasm(arch, newseeds, use_cache=False)
                for w, t in zip(newseeds, nt):
                    if t:
                        allseeds.append((w, t))
            json.dump(dict(arch=arch, forms=[to_json(f) for f in spec.forms]), open(out, 'w'))
            print('  saved', len(spec.forms), 'errors', len(errors), '%.0fs' % (time.time() - t0), flush=True)
    # final coverage
    for name, ss in (('corpus', seeds), ('probes', probes)):
        ok = sum(1 for w, t in ss if spec.match(w, t)[1])
        print('%s coverage %d/%d = %.2f%%' % (name, ok, len(ss), 100.0 * ok / max(1, len(ss))))
    for e in errors[:10]:
        print('ERR', e[0], e[1])

if __name__ == '__main__':
    main()
