#!/usr/bin/env python3
"""Annotate every form of a spec with how it renders the known valid words.

  evidence.py <ARCH> <spec.json> <corpus.txt>... [--probes N]

For each word nvdisasm accepts (corpus words plus the opcode probe set) every
form whose fixed bits match is asked to render it; form['evidence'] = [right,
wrong].  gen_sleigh.py uses this to order overlapping forms, so the form that
reproduces real code wins in SLEIGH.
"""
import sys, os, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'test'))
import nvd, build_spec
from sassmodel import from_json, to_json, render, same_text, word_key, form_keys

def main():
    arch, path = sys.argv[1], sys.argv[2]
    corp = [p for p in sys.argv[3:] if not p.startswith('--')]
    d = json.load(open(path))
    forms = [from_json(f) for f in d['forms']]
    byop = collections.defaultdict(list)
    for i, f in enumerate(forms):
        for k in form_keys(arch, f):
            byop[k].append(i)
    words = []
    for p in corp:
        for ln in open(p):
            x = ln.split()
            if x:
                words.append((int(x[0], 16), int(x[1]) if len(x) > 1 else 1))
    pw = build_spec.probe_words(arch)
    words += [(w, 1) for w in pw]
    texts = nvd.disasm(arch, [w for w, _ in words])
    ev = collections.defaultdict(lambda: [0, 0])
    for (w, c), t in zip(words, texts):
        if not t:
            continue
        res = {}
        for i in byop.get(word_key(arch, w), []) + byop.get(None, []):
            f = forms[i]
            if (w & f['mask']) != f['val']:
                continue
            try:
                res[i] = same_text(render(f, w), t)
            except Exception:
                res[i] = False
        for i, ok in res.items():
            if not ok:
                # a wrong rendering only counts against a form that SLEIGH would pick for
                # this word, i.e. when no strictly more specific form also matches it
                m = forms[i]['mask']
                if any((forms[j]['mask'] & m) == m and forms[j]['mask'] != m for j in res):
                    continue
            ev[i][0 if ok else 1] += c
    for i, f in enumerate(d['forms']):
        f['evidence'] = ev[i] if i in ev else [0, 0]
    json.dump(d, open(path, 'w'))
    bad = sum(1 for i in ev if ev[i][1] > ev[i][0])
    print('forms', len(forms), 'with evidence', len(ev), 'mostly wrong', bad)

if __name__ == '__main__':
    main()
