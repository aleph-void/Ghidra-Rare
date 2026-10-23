#!/usr/bin/env python3
"""Generate MicroBlaze test corpora.

  gen_corpus.py <opc.h> <bits:32|64> <outdir> [seed]

Produces in <outdir>:
  fuzz<bits>.words    one hex word per line: table-directed + uniformly random instruction
                      words, with imm (and for 64-bit, imml) prefixes sprinkled in
  fuzz<bits>_be.bin / fuzz<bits>_le.bin   the same words as big / little endian bytes
  asm<bits>.s         gas source with one line per opcode-table mnemonic (random operands)

The binutils opcode table (opcodes/microblaze-opc.h) is only used to direct test-vector
generation at interesting encodings; the SLEIGH spec does not depend on it.
"""
import random
import re
import struct
import sys

opc_h, bits, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
rng = random.Random(seed)

src = open(opc_h).read()
masks = {m.group(1): int(m.group(2), 16)
         for m in re.finditer(r'#define\s+OPCODE_MASK_(\w+)\s+0x([0-9A-Fa-f]+)', src)}
entries = []
for m in re.finditer(r'\{\s*"([^"]+)",\s*INST_TYPE_(\w+),[^,]+,[^,]+,[^,]+,\s*(0x[0-9A-Fa-f]+),\s*OPCODE_MASK_(\w+)', src):
    entries.append((m.group(1), m.group(2), int(m.group(3), 16), masks[m.group(4)]))

words = []
# 1. table directed: fixed bits from the table, random elsewhere; some near misses
for name, typ, val, mask in entries:
    for _ in range(48):
        w = val | (rng.getrandbits(32) & ~mask & 0xffffffff)
        if rng.random() < 0.25:
            # bias free fields towards small/zero values
            w &= ~(rng.choice([0x7ff, 0xffff, 0x001f0000, 0x03e00000, 0xf800, 0x3f]))
            w |= val
        if rng.random() < 0.15:
            w ^= 1 << rng.choice([b for b in range(32) if mask >> b & 1])
        words.append(w & 0xffffffff)
# 2. every primary opcode with small low bits
for op in range(64):
    for low in list(range(0, 0x800, 0x20)) + list(range(0x10)):
        words.append((op << 26) | (rng.getrandbits(15) << 11) | low)
# 3. uniformly random
words += [rng.getrandbits(32) for _ in range(20000)]
# objdump's MicroBlaze printer treats a zero word as a read error and stops, so avoid it
words = [w if w else 0x00000001 for w in words]
rng.shuffle(words)

# 4. sprinkle imm / imml prefixes (in front of whatever follows)
out = []
for w in words:
    r = rng.random()
    if r < 0.06:
        out.append(0xb0000000 | rng.getrandbits(16))
    elif bits == 64 and r < 0.10:
        out.append(0xb2000000 | rng.getrandbits(24))
        if rng.random() < 0.3:
            out.append(0xb2000000 | rng.getrandbits(24))
    out.append(w)

with open("%s/fuzz%d.words" % (outdir, bits), "w") as f:
    f.write("\n".join("%08x" % w for w in out) + "\n")
for e, fmt in (("be", ">I"), ("le", "<I")):
    with open("%s/fuzz%d_%s.bin" % (outdir, bits, e), "wb") as f:
        f.write(b"".join(struct.pack(fmt, w) for w in out))

# 5. assembler source: one line per mnemonic, random operands
def r():
    return "r%d" % rng.randrange(32)

def imm16():
    return str(rng.randrange(-32768, 32768))

ops = {
    "RD_R1_R2": lambda: "%s, %s, %s" % (r(), r(), r()),
    "RD_R1_IMM": lambda: "%s, %s, %s" % (r(), r(), imm16()),
    "RD_R1_IMML": lambda: "%s, %s, %s" % (r(), r(), imm16()),
    "RD_R1_UNSIGNED_IMM": lambda: "%s, %s, %d" % (r(), r(), rng.randrange(65536)),
    "RD_R1": lambda: "%s, %s" % (r(), r()),
    "RD_R2": lambda: "%s, %s" % (r(), r()),
    "RD_IMM": lambda: "%s, %s" % (r(), imm16()),
    "RD_IMML": lambda: "%s, %s" % (r(), imm16()),
    "R2": lambda: r(),
    "R1_R2": lambda: "%s, %s" % (r(), r()),
    "R1_IMM": lambda: "%s, %s" % (r(), imm16()),
    "R1_IMML": lambda: "%s, %s" % (r(), imm16()),
    "IMM": lambda: imm16(),
    "IMML": lambda: str(rng.randrange(1 << 24)),
    "SPECIAL_R1": lambda: "%s, %s" % (rng.choice(["rmsr", "rfsr", "rslr", "rshr", "rpid", "rzpr", "rtlbx", "rtlblo", "rtlbhi", "rtlbsx"]), r()),
    "RD_SPECIAL": lambda: "%s, %s" % (r(), rng.choice(["rpc", "rmsr", "rear", "resr", "rfsr", "rbtr", "redr", "rslr", "rshr", "rpid", "rzpr", "rtlbx", "rtlblo", "rtlbhi", "rpvr%d" % rng.randrange(13)])),
    "R1": lambda: r(),
    "RD_R1_IMM5": lambda: "%s, %s, %d" % (r(), r(), rng.randrange(32)),
    "RD_R1_IMMS": lambda: "%s, %s, %d" % (r(), r(), rng.randrange(32 if bits == 32 else 64)),
    "RD_RFSL": lambda: "%s, rfsl%d" % (r(), rng.randrange(16)),
    "R1_RFSL": lambda: "%s, rfsl%d" % (r(), rng.randrange(16)),
    "R1_R2_SPECIAL": lambda: "%s, %s" % (r(), r()),
    "RD_IMM15": lambda: "%s, %d" % (r(), rng.randrange(32768)),
    "RD": lambda: r(),
    "RFSL": lambda: "rfsl%d" % rng.randrange(16),
    "IMM5": lambda: str(rng.randrange(32)),
    "NONE": lambda: "",
}
skip = {"imm", "imml", "la", "lla", "tuqula", "lmi", "smi", "rtb"}
lines = []
for name, typ, val, mask in entries:
    if name in skip:
        continue
    if typ == "RD_R1_IMMW_IMMS":
        for _ in range(3):
            width = 32 if not (name.startswith("bsl") and len(name) == 6) else 64
            s = rng.randrange(width - 1)
            w = rng.randrange(1, width - s + 1)
            lines.append("\t%s\t%s, %s, %d, %d" % (name, r(), r(), w, s))
        continue
    if typ not in ops:
        continue
    for _ in range(3):
        o = ops[typ]()
        if name.startswith("b") and typ in ("IMM", "R1_IMM", "RD_IMM", "R1_IMML") and name not in ("brai", "braid", "bralid", "brki"):
            # PC-relative branches: use a label so gas computes the offset
            o = re.sub(r'-?\d+$', "L%d" % rng.randrange(8), o)
        lines.append("\t%s\t%s" % (name, o))
labels = ["L%d:\tor\tr0, r0, r0" % i for i in range(8)]
body = []
step = max(1, len(lines) // 8)
for i, l in enumerate(lines):
    if i % step == 0 and labels:
        body.append(labels.pop(0))
    body.append(l)
body += labels
with open("%s/asm%d.s" % (outdir, bits), "w") as f:
    f.write("\t.text\n" + "\n".join(body) + "\n")
print("fuzz words: %d, asm lines: %d" % (len(out), len(body)))
