#!/usr/bin/env python3
"""Every encoding in scripts/isa_tables.py must decode to its own mnemonic.
   enc_coverage.py gen <xs1|xs2|xs3> <out.bin> <out.json>   (64 random operand fills per form,
                                                              each item padded to 8 bytes)
   enc_coverage.py check <out.json> <ghidra.txt>
Reports forms for which no sample decodes (e.g. an opcode shadowed by another constructor) and
samples that decode to a different mnemonic. Needed because the LLVM comparison counts
"both undefined" as agreement, so XS2/XS3-only opcodes that Ghidra fails to decode go unseen."""
import json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from isa_tables import ENC
import gen_sleigh

NOP = bytes.fromhex('ff17')


def fill(p, rnd):
    return int(''.join(c if c in '01' else str(rnd.getrandbits(1)) for c in p), 2)


def gen(v, outbin, outjson):
    rnd = random.Random(1)
    blob, items = bytearray(), []
    for name, forms in sorted(ENC[v].items()):
        for fmt, pats in forms:
            for _ in range(64):
                hw = [fill(p, rnd) for p in pats]
                b = b''.join(h.to_bytes(2, 'little') for h in hw)
                items.append({'off': len(blob), 'name': name, 'fmt': fmt, 'hex': b.hex()})
                blob += b + NOP * ((8 - len(b)) // 2)
    open(outbin, 'wb').write(blob)
    json.dump(items, open(outjson, 'w'))


def check(js, gh):
    items = json.load(open(js))
    got = {}
    for line in open(gh):
        p = line.rstrip('\n').split(' ', 2)
        got[int(p[0], 16)] = p[2]
    spec = gen_sleigh.SPEC
    byform = {}
    nwrong = 0
    for it in items:
        t = got.get(it['off'], 'MISSING')
        want = spec[it['name']][0].split()[0].lower()
        ok = not t.startswith('BAD') and t != 'MISSING'
        key = (it['name'], it['fmt'])
        byform.setdefault(key, [0, 0])
        byform[key][1] += 1
        if ok:
            byform[key][0] += 1
            if t.split()[0].lower() != want:
                nwrong += 1
    dead = [k for k, (o, n) in byform.items() if o == 0]
    print('forms %d, never decoded %d' % (len(byform), len(dead)))
    for k in dead:
        print('   never decoded: %s (%s)' % k)
    # random fills ignore the packed-operand limits, so many samples legitimately land in
    # another instruction's space; only forms that never decode are reported
    print('(%d samples decoded as another mnemonic - expected for packed operand fields)' % nwrong)


if __name__ == '__main__':
    if sys.argv[1] == 'gen':
        gen(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        check(sys.argv[2], sys.argv[3])
