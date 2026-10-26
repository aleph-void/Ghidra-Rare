#!/usr/bin/env python3
"""Decode-test corpora for IA-64: raw images of 16-byte bundles.

  gen_corpus.py random <out.bin> <count> [seed]   random bundles, every valid/reserved template
  gen_corpus.py opcodes <out.bin> [seed]           every value of slot bits 27-40 (major opcode and
      the extension fields above bit 26) for each unit in each slot position it can occupy, with
      random low bits (two samples each), plus the X-unit space of MLX bundles
The bundle layout follows Figure 4-1: template bits 4:0, slot k at bits 5+41k .. 45+41k.
"""
import random, sys

UNIT_POS = {  # unit -> list of (template, slot index)
    'M': [(0x08, 0), (0x09, 1)], 'I': [(0x00, 1), (0x01, 2)], 'F': [(0x0C, 1), (0x0F, 2)],
    'B': [(0x16, 0), (0x13, 1), (0x11, 2)]}
NOPS = {'M': 1 << 27, 'I': 1 << 27, 'F': 1 << 27, 'B': (2 << 37)}
TUNITS = {0x00: 'MII', 0x01: 'MII', 0x02: 'MII', 0x03: 'MII', 0x08: 'MMI', 0x09: 'MMI', 0x0A: 'MMI',
          0x0B: 'MMI', 0x0C: 'MFI', 0x0D: 'MFI', 0x0E: 'MMF', 0x0F: 'MMF', 0x10: 'MIB', 0x11: 'MIB',
          0x12: 'MBB', 0x13: 'MBB', 0x16: 'BBB', 0x17: 'BBB', 0x18: 'MMB', 0x19: 'MMB', 0x1C: 'MFB',
          0x1D: 'MFB'}

def bundle(t, s):
    v = t | (s[0] << 5) | (s[1] << 46) | (s[2] << 87)
    return v.to_bytes(16, 'little')

def random_corpus(n, rnd):
    out = bytearray()
    for _ in range(n):
        t = rnd.randrange(32)
        out += bundle(t, [rnd.getrandbits(41) for _ in range(3)])
    return out

def opcode_corpus(rnd, samples=2):
    out = bytearray()
    for unit, poss in UNIT_POS.items():
        for t, k in poss:
            units = TUNITS[t]
            for hi in range(1 << 14):
                for _ in range(samples):
                    s = [NOPS[u] for u in units]
                    s[k] = (hi << 27) | rnd.getrandbits(27)
                    out += bundle(t, s)
    # MLX: X slot opcode space, random L slot
    for t in (0x04, 0x05):
        for hi in range(1 << 14):
            for _ in range(samples):
                out += bundle(t, [NOPS['M'], rnd.getrandbits(41), (hi << 27) | rnd.getrandbits(27)])
    return out

def branch_corpus():
    """br.call / brl.call / br.ctop / br.cexit / br.wtop / br.wexit / br.cloop in every slot
    they can occupy, for the frame-context passes of the every-entry test"""
    out = bytearray()
    call = (5 << 37) | (1 << 13)                   # br.call b0=+16
    icall = (1 << 37) | (1 << 32) | (6 << 13)      # br.call b0=b6
    loops = [(4 << 37) | (bt << 6) | (1 << 13) for bt in (2, 3, 5, 6, 7)]
    for ins in [call, icall] + loops:
        for t, k in UNIT_POS['B']:
            s = [NOPS[u] for u in TUNITS[t]]
            s[k] = ins
            out += bundle(t, s)
    lcall = (0xD << 37) | (1 << 13)
    out += bundle(0x04, [NOPS['M'], 0, lcall])
    return out

def pseudo_corpus(rnd):
    """encodings of the assembler pseudo-ops (fmerge f2 = f3, extr/dep with pos + len = 64, ...)
    with random other fields, in every slot position of their unit"""
    slots = []   # (unit, slot value)
    def r(n):
        return rnd.getrandbits(n)
    for i in range(128):
        for op, x6 in ((0, 0x10), (0, 0x11), (1, 0x11)):    # mov / fneg / fpneg
            slots.append(('F', (op << 37) | (x6 << 27) | (i << 20) | (i << 13) | (r(7) << 6) | r(6)))
    for p_ in range(64):
        for y in (0, 1):                                     # shr.u / shr
            slots.append(('I', (5 << 37) | (1 << 34) | ((63 - p_) << 27) | (r(7) << 20) | (p_ << 14) | (y << 13)
                          | (r(7) << 6) | r(6)))
        slots.append(('I', (5 << 37) | (1 << 34) | (1 << 33) | ((63 - p_) << 27) | ((63 - p_) << 20)   # shl
                      | (r(7) << 13) | (r(7) << 6) | r(6)))
    for _ in range(4):
        slots.append(('M', (8 << 37) | (2 << 34) | (r(7) << 20) | (r(7) << 6) | r(6)))         # mov r1=r3
        slots.append(('I', (8 << 37) | (2 << 34) | (r(7) << 20) | (r(7) << 6) | r(6)))
        slots.append(('M', (8 << 37) | (r(7) << 20) | (r(7) << 6) | r(6)))                      # add r1=r0,r3
        for mb in (0, 8, 9, 10, 11):                                                            # mux1
            slots.append(('I', (7 << 37) | (3 << 34) | (2 << 30) | (2 << 28) | (mb << 20) | (r(7) << 13)
                          | (r(7) << 6) | r(6)))
        for op, x6 in ((0, 0x10), (0, 0x11), (1, 0x10), (1, 0x11)):                           # fabs ...
            slots.append(('F', (op << 37) | (x6 << 27) | (r(7) << 20) | (r(7) << 6) | r(6)))
        for op, x in ((8, 0), (8, 1), (9, 0)):                                                  # fnorm
            slots.append(('F', (op << 37) | (x << 36) | (r(2) << 34) | (1 << 27) | (r(7) << 20) | (r(7) << 6) | r(6)))
        slots.append(('B', (4 << 37) | (r(20) << 13) | (r(1) << 12)))                            # br
    out = bytearray()
    for unit, v in slots:
        for t, k in UNIT_POS[unit]:
            s = [NOPS[u] for u in TUNITS[t]]
            s[k] = v
            out += bundle(t, s)
    return out

if __name__ == '__main__':
    mode, path = sys.argv[1], sys.argv[2]
    if mode == 'pseudo':
        data = pseudo_corpus(random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1))
    elif mode == 'branches':
        data = branch_corpus()
    elif mode == 'random':
        n = int(sys.argv[3])
        rnd = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 1)
        data = random_corpus(n, rnd)
    else:
        rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
        data = opcode_corpus(rnd)
    open(path, 'wb').write(data)
    print('%d bundles' % (len(data) // 16))
