#!/usr/bin/env python3
"""Diff Ghidra's disassembly of all .text sections of a cubin against nvdisasm.
  cubin_compare.py <file.cubin> [--show N]
The SM version comes from e_flags; the sections are concatenated into one raw
file (both tools see identical bytes/addresses), then compare.py does the rest."""
import sys, os, struct, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import compare, cubin_words
from gen_ldefs import VARIANTS

def sm_of(data):
    abiv = data[8]
    fl = cubin_words.eflags(data)
    return (fl >> 8) & 0xff if abiv >= 8 else fl & 0xff

def main():
    path = sys.argv[1]
    show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 5
    data = open(path, 'rb').read()
    sm = sm_of(data)
    var = next((v for v, _, sms in VARIANTS if sm in sms), None)
    if '--variant' in sys.argv:
        print(var or 'none'); return
    if var is None:
        print('%s: sm_%d not supported' % (os.path.basename(path), sm)); return
    blob = b''.join(b for n, t, b in cubin_words.sections(data) if n.startswith('.text.') and t == 1)
    if not blob:
        print('%s: no code' % os.path.basename(path)); return
    fd, raw = tempfile.mkstemp(suffix='.bin'); os.close(fd)
    open(raw, 'wb').write(blob)
    try:
        rows = compare.compare(var, raw)
    finally:
        for p in (raw, raw + '.ghidra.txt'):
            if os.path.exists(p): os.unlink(p)
    st, valid = compare.summarize(rows)
    exact = st['match'] + st['match_mod_reuse']
    print('%s (sm_%d -> %s): %d instructions, exact %d (%.2f%%), ghidra BAD %d, mismatch %d' % (
        os.path.basename(path), sm, var, valid, exact, 100.0 * exact / max(1, valid), st['ghidra_bad'], st['mismatch']))
    n = 0
    for a, w, nv, g in rows:
        if nv is not None and not compare.same(g, nv, True):
            if n < show:
                print('  %06x %032x\n     nv: %s\n     gh: %s' % (a, w, nv, g))
            n += 1

if __name__ == '__main__':
    main()
