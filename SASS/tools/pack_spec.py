#!/usr/bin/env python3
"""Prune a spec to the forms the generator emits, replace every seed word by a
synthesized canonical word, and gzip it.

  pack_spec.py spec/SM80.json [--no-verify]  ->  spec/SM80.json.gz

The learner's seeds come from the (non-redistributable) libcurand corpus.  The
generator only needs a word inside the form whose groups print the form's token
skeleton and whose slots hold non-special values, so the packed spec stores
  fixed bits | group values matching the skeleton | every slot = 1 (floats = 1.0)
and re-derives the skeleton text from it.  Unless --no-verify is given the
canonical word is checked against nvdisasm (the model must reproduce its text).
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import gen_sleigh as G
from sassmodel import (load_spec, save_spec, from_json, to_json, render, render_tokens, fmt_value,
                       same_text, is64, FLTFMT)

FONE = {'f32': 0x3f800000, 'f64hi': 0x3ff00000, 'f16': 0x3c00, 'f64': 0x3ff0000000000000}
CTRL128 = (0x000fe4 << 104) & sum(1 << b for b in list(range(105, 122)) + [126, 127])

def setbits(w, bits, v):
    for i, b in enumerate(bits):
        w = (w & ~(1 << b)) | (((v >> i) & 1) << b)
    return w

def canonical(f, arch, alt=1):
    w = f['val'] | (0 if is64(arch) else CTRL128)
    slotpos = {s['pos']: k for k, s in enumerate(f['slots'])}
    toks = f['toks']
    for g in f['groups']:
        want = [('s', slotpos[i]) if i in slotpos else toks[i] for i in range(g['lo'], g['hi'])]
        for v, out in sorted(g['table'].items()):
            if out is not None and [('s', x) if isinstance(x, int) else x for x in out] == want:
                w = setbits(w, g['bits'], v)
                break
        else:
            return None
    for s in f['slots']:
        n = len(s['bits'])
        if s['cls'] == 'flt':
            v = FONE[s['fmt']]
        else:
            v = alt if n >= 3 else 1
        w = setbits(w, s['bits'], v)
    return w

def flt_text(s, w):
    from sassmodel import slot_raw
    x = FLTFMT[s['fmt']][1](slot_raw(s, w))
    return repr(float(x)).rstrip('0').rstrip('.') if x == int(x) else repr(x)

def main():
    src = sys.argv[1]
    verify = '--no-verify' not in sys.argv
    d = load_spec(src)
    arch = d['arch']
    forms = [from_json(f) for f in d['forms']]
    g = G.Gen(arch, forms)
    g.generate()
    used = [f for f in forms if any(f is u for u in g.used_forms)]
    cands = []
    out = []
    bad = 0
    for f in used:
        ws = [x for x in (canonical(f, arch, a) for a in (1, 2, 4)) if x is not None]
        if not ws:
            bad += 1
            ws = [f['val']]
        cands.append(ws)
    texts = {}
    if verify:
        import nvd
        allw = sorted({w for ws in cands for w in ws})
        texts = dict(zip(allw, nvd.disasm(arch, allw, use_cache=False)))
    nver = 0
    for f, ws in zip(used, cands):
        w = ws[0]
        for x in ws:
            try:
                m = render(f, x)
            except Exception:
                m = None
            if m is not None and (not verify or same_text(m, texts.get(x))):
                w = x; nver += 1
                break
        f = dict(f)
        toks = list(f['toks'])
        for s in f['slots']:
            toks[s['pos']] = flt_text(s, w) if s['cls'] == 'flt' else fmt_value(s, w)
        f['toks'] = toks
        f['text'] = ''.join(toks)
        f['seed'] = '%x' % w
        for k in ('spawn',):
            f.pop(k, None)
        out.append(to_json(f))
    d['forms'] = out
    dst = src[:-3] if src.endswith('.gz') else src
    dst += '.gz'
    save_spec(d, dst)
    print('kept %d of %d forms, canonical words verified by nvdisasm: %d, unresolved: %d -> %s (%d bytes)' % (
        len(out), len(forms), nver, bad, dst, os.path.getsize(dst)))

if __name__ == '__main__':
    main()
