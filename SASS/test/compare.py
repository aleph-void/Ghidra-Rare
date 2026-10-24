#!/usr/bin/env python3
"""Compare Ghidra's SASS disassembly of a raw instruction file with nvdisasm.

  compare.py <ARCH> <raw.bin> [--ghidra-out file] [--show N] [--json report.json]

Runs tools/ghidra-dis.sh (linear sweep, language SASS:LE:64:<ARCH>) and nvdisasm
on the same file (base address 0), normalizes both and reports the agreement.
Normalization: whitespace collapsed, hex numbers compared by value (Ghidra pads
addresses), float immediates (which Ghidra prints as raw hex bits) compared by
value against f32 / f64-high-word / f16 interpretations.
"""
import sys, os, re, subprocess, argparse, json, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import nvd
from sassmodel import tokenize, classify, flt_match

REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

def ghidra_dis(arch, path, out=None):
    out = out or path + '.ghidra.txt'
    lang = 'SASS:LE:64:' + arch
    step = str(nvd.isz_of(arch))
    subprocess.run([os.path.join(HERE, 'ghidra-dis.sh'), lang, path, '8' if nvd.isz_of(arch) == 8 else step, out], check=True)
    res = {}
    for ln in open(out):
        p = ln.rstrip('\n').split(' ', 2)
        if len(p) < 3:
            continue
        res[int(p[0], 16)] = p[2]
    return res

def norm_tokens(t):
    t = re.sub(r'\s+', ' ', t.strip().rstrip(';').strip())
    t = re.sub(r' ?, ?', ',', t)
    # Maxwell/Pascal dual-issue braces (nvdisasm only)
    t = t.replace('{', '').replace('}', '').strip()
    return tokenize(t)

def tok_eq(g, n):
    if g == n:
        return True
    cg, cn = classify(g), classify(n)
    if cg and cn and cg[0] == 'hex' and cn[0] == 'hex':
        # Ghidra shows addresses below 0 (backward branches near address 0) modulo 2^64
        return (cg[1] - cn[1]) % (1 << 64) == 0
    if cg and cn and cg[0] == 'hex' and cn[0] == 'flt':
        raw = cg[1] & 0xffffffffffffffff
        return any(flt_match(n, f, raw) for f in ('f32', 'f64hi', 'f16', 'f64'))
    return False

def same(g, n, ignore_reuse=False):
    if g is None or n is None:
        return False
    if ignore_reuse:
        g = g.replace('.reuse', ''); n = n.replace('.reuse', '')
    a, b = norm_tokens(g), norm_tokens(n)
    a = [x for x in a if x != ' ']; b = [x for x in b if x != ' ']
    if len(a) != len(b):
        return False
    return all(tok_eq(x, y) for x, y in zip(a, b))

def compare(arch, path, gout=None):
    words, nv = nvd.disasm_file(arch, path)
    gh = ghidra_dis(arch, path, gout)
    isz = nvd.isz_of(arch)
    rows = []
    nb = nvd.bundle_of(arch)[0] if isz == 8 else 0
    for i, (w, n) in enumerate(zip(words, nv)):
        a = i * isz
        if nb and i % nb == 0:
            continue    # scheduling control word (not printed by nvdisasm)
        g = gh.get(a)
        if g is not None and g.startswith('BAD'):
            g = None
        rows.append((a, w, n, g))
    return rows

def summarize(rows):
    st = collections.Counter()
    for a, w, n, g in rows:
        if n is None and g is None:
            st['both_invalid'] += 1
        elif n is None:
            st['ghidra_only'] += 1
        elif g is None:
            st['ghidra_bad'] += 1
        elif same(g, n):
            st['match'] += 1
        elif same(g, n, ignore_reuse=True):
            st['match_mod_reuse'] += 1
        else:
            st['mismatch'] += 1
    valid = sum(1 for r in rows if r[2] is not None)
    return st, valid

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch'); ap.add_argument('bin')
    ap.add_argument('--ghidra-out'); ap.add_argument('--show', type=int, default=20)
    ap.add_argument('--json')
    a = ap.parse_args()
    rows = compare(a.arch, a.bin, a.ghidra_out)
    st, valid = summarize(rows)
    exact = st['match'] + st['match_mod_reuse']
    print('%s: %d words, %d valid for nvdisasm; exact %d (%.2f%%), ghidra BAD %d, mismatch %d, ghidra-only %d' % (
        a.arch, len(rows), valid, exact, 100.0 * exact / max(1, valid), st['ghidra_bad'], st['mismatch'], st['ghidra_only']))
    n = 0
    for addr, w, nv_, g in rows:
        if nv_ is not None and not same(g, nv_, True):
            if n < a.show:
                print('  %05x %032x\n     nv: %s\n     gh: %s' % (addr, w, nv_, g))
            n += 1
    if a.json:
        json.dump(dict(arch=a.arch, stats=st, valid=valid), open(a.json, 'w'))

if __name__ == '__main__':
    main()
