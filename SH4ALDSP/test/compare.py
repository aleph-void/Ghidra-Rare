#!/usr/bin/env python3
"""Compare Ghidra's linear-sweep dump (tools/DumpDisasm.java) with GNU objdump, slot by slot.

    compare.py <ghidra.txt> <objdump.txt> [explained.txt] [--slot N]

Only addresses that are multiples of the slot size (default 4) are compared: every corpus slot
starts an instruction; the filler word after a 16-bit instruction is not counted.

exact    same text after lower-casing and removing blanks
semantic same instruction after normalising spellings (see norm())
Every other slot is put in a class by classify(), which looks at the instruction bits; each class
must have a reason in the explained file (lines "class reason") or the run fails, and so does
every slot that no class covers.
Adapted from the compare.py of aleph-void/ghidra-sh (MIT).
"""
import re
import sys
from collections import defaultdict


def norm(text):
    t = text.lower().strip()
    t = re.sub(r"^_", "", t)  # Ghidra marks a delay-slot instruction with a leading underscore
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ",", t)
    t = re.sub(r"^(bt|bf)/s ", r"\1.s ", t)
    t = re.sub(r"@\((0x[0-9a-f]+),pc\)", r"\1", t)
    t = t.replace("nopx ", "").replace(" nopy", "")

    def sub(m):
        s = m.group(0)
        v = int(s, 16) if "0x" in s else int(s)
        return str(v)
    t = re.sub(r"(?<![a-z0-9_])-?(0x[0-9a-f]+|\d+)(?![a-z0-9_])", sub, t)
    return t.strip()


def exact_key(text):
    return re.sub(r"\s+", "", text.lower().lstrip("_"))


def load_ghidra(p):
    d = {}
    for line in open(p):
        f = line.rstrip("\n").split(" ", 2)
        off = int(f[0], 16)
        d[off] = None if f[2].startswith("BAD") else f[2].strip()
    return d


def load_objdump(p, little):
    d = {}
    words = {}
    for line in open(p):
        m = re.match(r"\s*([0-9a-f]+):\t([0-9a-f ]+)\t(.*)$", line)
        if not m:
            continue
        txt = m.group(3).split("\t! ")[0]
        txt = re.sub(r"\t+", " ", txt).strip()
        off = int(m.group(1), 16)
        # a 32-bit P-op whose B field objdump rejects is printed as ".word 0x...." (after the A field)
        d[off] = None if txt.startswith(".word") else txt
        b = bytes.fromhex(m.group(2).replace(" ", ""))
        for i in range(0, len(b) - 1, 2):
            words[off + i] = (b[i + 1] << 8 | b[i]) if little else (b[i] << 8 | b[i + 1])
    return d, words


RES_DZ = {0, 1, 2, 3, 4, 6, 13, 15}
DELAYED = {"bra", "bsr", "braf", "bsrf", "jmp", "jsr", "rts", "rte", "bt.s", "bf.s", "bt/s", "bf/s"}


def classify(w0, w1, gt, ot, onext):
    """class of a difference, from the instruction bits (see decode-explained.txt).  The classes
    for rejected encodings require Ghidra to have rejected the slot; the display classes check
    that the two values differ exactly as the class says."""
    c = _classify(w0, w1, gt, ot, onext)
    if c in ("reserved-afield", "reserved-ds", "reserved-dz", "ignored-field", "branch-in-delay-slot"):
        return c if gt is None else None
    if c == "ldrs-ldre-negative":
        a, b = re.findall(r"0x([0-9a-f]+)", gt.lower()), re.findall(r"0x([0-9a-f]+)", ot.lower())
        return c if a and b and int(b[0], 16) - int(a[0], 16) == 0x200 else None
    if c == "shift-imm-unsigned":
        fixed = re.sub(r"#(\d+)", lambda m: "#%d" % (int(m.group(1)) - 128), ot)
        return c if norm(fixed) == norm(gt) else None
    return c


def _classify(w0, w1, gt, ot, onext):
    top = w0 >> 10
    if top in (0x3c, 0x3e) and (w0 & 0xf) == 0 and (w0 & 0x3f0):
        return "reserved-afield"
    if top == 0x3d and ((w0 >> 4) & 0xf) in (0, 1, 2, 3, 4, 6):
        return "reserved-ds"
    if (w0 & 0xfd00) == 0x8c00 and (w0 & 0x80) and gt and ot:
        return "ldrs-ldre-negative"
    if gt is None and ot and ot.split()[0] in DELAYED and onext and onext.split()[0] in DELAYED:
        return "branch-in-delay-slot"
    if top != 0x3e or w1 is None:
        return None
    b = w1
    op6, cc, sx, sy, dz = b >> 10, (b >> 8) & 3, (b >> 6) & 3, (b >> 4) & 3, b & 15
    if (b >> 11) in (0, 2):                       # PSHL/PSHA #imm
        if dz in RES_DZ:
            return "reserved-dz"
        if (b >> 4) & 0x40 and gt and ot:
            return "shift-imm-unsigned"
        return None
    if op6 < 0x20:
        return None
    if op6 == 0b100001 and cc == 0:               # PCMP: Dz must be 0
        return "ignored-field" if dz else None
    if dz in RES_DZ:
        return "reserved-dz"
    sxform = {0b100010, 0b100110, 0b100111, 0b110010, 0b110110}
    syform = {0b101010, 0b101110, 0b101111, 0b111010, 0b111110}
    if op6 in sxform | syform:
        f = sy if op6 in sxform else sx
        two = op6 in (0b100010, 0b100110, 0b100111, 0b101010, 0b101110, 0b101111)
        if op6 in (0b100111, 0b101111):           # PDMSB/PSWAP: field 0 or 1, cc 01-11
            ok = cc != 0 and f in (0, 1)
        elif two:                                 # PDEC/PINC (f 0, cc 01-11), PABS/PRND (f 0/1 cc 00, f 1 cc 10-11)
            ok = (cc == 0 and f in (0, 1)) or (cc != 0 and f == 0) or (cc in (2, 3) and f == 1)
        else:                                     # PNEG/PCOPY: f 0, cc 01-11
            ok = cc != 0 and f == 0
        return "ignored-field" if not ok else None
    if op6 in (0b100011, 0b110011, 0b110111, 0b111011, 0b111111):   # PCLR, PSTS, PLDS
        return "ignored-field" if (sx or sy) else None
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    slot = 4
    if "--slot" in sys.argv:
        slot = int(sys.argv[sys.argv.index("--slot") + 1])
        args = [a for a in args if a != str(slot)]
    g = load_ghidra(args[0])
    o, words = load_objdump(args[1], "--le" in sys.argv)
    explained = {}
    if len(args) > 2:
        for line in open(args[2]):
            line = line.strip()
            if line and not line.startswith("#"):
                a, why = line.split(None, 1)
                explained[a] = why
    n = exact = sem = both_inv = 0
    buckets = defaultdict(list)
    for off in sorted(o):
        if off % slot:
            continue
        n += 1
        gt, ot = g.get(off), o[off]
        if gt is None and ot is None:
            both_inv += 1
            continue
        if gt is not None and ot is not None:
            if exact_key(gt) == exact_key(ot):
                exact += 1
                continue
            if norm(gt) == norm(ot):
                sem += 1
                continue
        cls = classify(words.get(off, 0), words.get(off + 2), gt, ot, o.get(off + 2))
        if cls is None:
            gm = gt.lstrip("_").split()[0].lower() if gt else "INVALID"
            om = ot.split()[0].lower() if ot else "INVALID"
            cls = "UNCLASSIFIED:%s/%s" % (gm, om)
        buckets[cls].append((off, gt, ot))
    unexpl = expl = 0
    for k, v in buckets.items():
        if k in explained:
            expl += len(v)
        else:
            unexpl += len(v)
    print(f"slots {n}: exact {exact}, semantic {sem}, both-invalid {both_inv}, "
          f"explained {expl}, unexplained {unexpl}")
    for k, v in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        why = explained.get(k, "UNEXPLAINED")
        print(f"  {k}: {len(v)}  [{why}]")
        for e in v[:3]:
            print(f"      {e[0]:#08x}: ghidra={e[1]!r} objdump={e[2]!r}")
    return 1 if unexpl else 0


if __name__ == "__main__":
    sys.exit(main())
