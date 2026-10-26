#!/usr/bin/env python3
"""Compare Ghidra's XA disassembly with MAME unidasm (-arch xa).

    compare.py [--stride N] <mame.txt> <ghidra.txt> [label]

Both texts are normalised (case, spacing, MAME "$3C" / Ghidra "0x3c" numbers, MAME's unsigned
offsets as signed, MAME SFR names as addresses). Differences with a known cause are counted
separately (see CLASSES); everything else is reported as unexplained.
"""
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

MAME_RE = re.compile(r"^([0-9a-f]+): ((?:[0-9a-f]{2} )+)\s*(.*)$")
FLAGBITS = {"7": "C", "6": "AC", "2": "V", "1": "N", "0": "Z"}


def mame_sfr_names():
    """MAME's SFR names (black-box: the names unidasm prints for MOV.b R0L,direct 400h-7FFh)."""
    with tempfile.NamedTemporaryFile(suffix=".bin") as f:
        f.write(b"".join(bytes([0x86, (a >> 8) & 7, a & 0xff]) for a in range(0x400, 0x800)))
        f.flush()
        txt = subprocess.run(["unidasm", f.name, "-arch", "xa"], capture_output=True,
                             text=True).stdout
    names = {}
    for i, line in enumerate(txt.splitlines()):
        name = line.split("R0L, ")[-1].strip()
        if not name.startswith("$") and not name.startswith("unk_"):
            names[name.upper()] = 0x400 + i
    return names


SFR = mame_sfr_names()


def hexnum(v):
    return "0X%X" % v


def norm_mame(t):
    t = t.upper()
    # mnemonic fixes: .dw = .d, RTI = RETI, "NEG.b R0Lx"
    t = re.sub(r"^(\S+)\.DW\b", r"\1.D", t)
    t = re.sub(r"^RTI\b", "RETI", t)
    t = re.sub(r"^TRAP (\d+)$", lambda m: "TRAP #" + hexnum(int(m.group(1))), t)
    t = re.sub(r"^(NEG\.[BW] R\d+[LH]?)X$", r"\1", t)
    # offsets: [Rn+#$xx] / [Rn+$xx], unsigned in MAME
    def off(m):
        h = m.group(2)
        v = int(h, 16)
        bits = 8 if len(h) <= 2 else 16
        if v >= 1 << (bits - 1):
            return f"[{m.group(1)}-{hexnum((1 << bits) - v)}]"
        return f"[{m.group(1)}+{hexnum(v)}]"
    t = re.sub(r"\[(R\d+)\+#?\$([0-9A-F]+)\]", off, t)
    def leaoff(m):
        h = m.group(2)
        v = int(h, 16)
        bits = 8 if len(h) <= 2 else 16
        if v >= 1 << (bits - 1):
            return f"{m.group(1)}-{hexnum((1 << bits) - v)}"
        return f"{m.group(1)}+{hexnum(v)}"
    t = re.sub(r"(R\d+)\+#\$([0-9A-F]+)", leaoff, t)
    # SFR names and their bits
    def sfr(m):
        n = m.group(1)
        if n.startswith("UNK_SFR_"):
            a = int(n[8:], 16)
        elif n in SFR:
            a = SFR[n]
        else:
            return m.group(0)
        if a == 0x400 and m.group(2) and m.group(2)[1:] in FLAGBITS:
            return FLAGBITS[m.group(2)[1:]]
        core = {0x400: "PSWL", 0x401: "PSWH", 0x402: "PSW51", 0x403: "SSEL", 0x440: "SCR",
                0x441: "DS", 0x442: "ES", 0x443: "CS"}
        return (core.get(a) or hexnum(a)) + (m.group(2) or "")
    t = re.sub(r"\b(UNK_SFR_[0-9A-F]+|[A-Z][A-Z0-9_]*)(\.\d)?\b", sfr, t)
    # code addresses: MAME prints targets below 0 as 32-bit values; the code space is 24-bit
    t = re.sub(r"\$([0-9A-F]+)", lambda m: hexnum(int(m.group(1), 16) & 0xffffff), t)
    t = re.sub(r"^((?:LSR|ASL|ASR|RL|RLC|RR|RRC)\S*\s+\S+,\s*)(\d+)$",
               lambda m: m.group(1) + "#" + hexnum(int(m.group(2))), t)
    return re.sub(r"\s+", "", t)


def norm_ghidra(t):
    t = t.upper()
    t = re.sub(r"0X([0-9A-F]+)", lambda m: hexnum(int(m.group(1), 16)), t)
    return re.sub(r"\s+", "", t)


def load_mame(path, stride):
    d = {}
    for line in open(path):
        m = MAME_RE.match(line.rstrip("\n"))
        if m:
            a = int(m.group(1), 16)
            if stride and a % stride:
                continue
            d[a] = (m.group(2).replace(" ", ""), m.group(3).strip())
    return d


def load_ghidra(path):
    d = {}
    for line in open(path):
        a, b, t = (line.rstrip("\n").split(" ", 2) + ["", ""])[:3]
        d[int(a, 16)] = (b, t)
    return d


def reserved(b1, b2):
    """Encodings MAME decodes that have a bit the user guide fixes set differently (chapter 6
    encodings), or that name registers the instruction cannot use. Returns a class or None."""
    lo4, hi4, b7, b3, b4 = b2 & 15, b2 >> 4, b2 >> 7, (b2 >> 3) & 1, (b2 >> 4) & 1
    if b1 & 0x87 == 0x07 and b1 < 0x80:
        if b1 & 0x48 == 0x48:
            return "rsv-word-list-hl"      # word register list with H/L = 1
        if b2 == 0:
            return "rsv-empty-list"
    if b1 == 0xc6 and b2 & 0xf8:
        return "rsv-bits"
    if b1 in (0xe3, 0xeb) and (lo4 not in (0, 8) or (lo4 == 8 and b7)):
        return "rsv-bits"
    if b1 in (0x40, 0x48) and b2 & 0x88:
        return "rsv-bits"
    if b1 in (0x50, 0x58, 0x80, 0x88) and b3:
        return "rsv-bits"
    if (0x92 <= b1 <= 0x96 or 0x9a <= b1 <= 0x9e or 0xa2 <= b1 <= 0xa6 or 0xaa <= b1 <= 0xae
            or 0xb2 <= b1 <= 0xb6 or 0xba <= b1 <= 0xbe) and b7:
        return "rsv-bits"
    if b1 in (0xe2, 0xea) and b3 and hi4:
        return "rsv-bits"
    if b1 in (0x87, 0x8f) and b3 and b2 & 7:
        return "rsv-bits"
    if b1 in (0x97, 0x9f) and not b7 and b3:
        return "rsv-bits"
    if b1 in (0x90, 0x98):
        if lo4 < 8 and (b7 or b3):
            return "rsv-bits"
        if lo4 == 8 and b1 == 0x98:
            return "rsv-bits"              # DA is byte-only
        if lo4 in (0xc, 0xe) and (b1 == 0x98 or hi4 != 4):
            return "rsv-bits"
    if b1 == 0xd6:
        if hi4 in (1, 8, 9) and lo4:
            return "rsv-bits"
        if hi4 == 4 and b2 != 0x46:
            return "rsv-bits"
        if hi4 in (6, 7) and b3:
            return "rsv-bits"
    if b1 in (0xed, 0xef) and b4:
        return "rsv-bits"
    if b1 == 0xe9 and lo4 in (1, 9) and b4:
        return "rsv-bits"
    if b1 == 0x08 and b2 & 0x0c:
        return "rsv-bits"
    if b1 == 0x97 and b7 and b2 & 0x1c:
        return "rsv-bits"
    if b1 == 0x9f and b7:
        return "rsv-bits"                  # JB/JNB/JBC exist only as 97h
    if hi4 >= 8 and (b1 in (0xb8, 0xbf, 0xc8, 0xc9, 0xca, 0xcb, 0xd8, 0xd9, 0xda, 0xdb, 0xdf, 0xeb)
                     or b1 == 0xe8 and lo4 in (3, 0xb)):
        return "r8-r15"                    # word registers R8-R15 are not implemented
    if b1 in (0xdc, 0xdd, 0xde) and b2 >> 5 >= 4:
        return "r8-r15"
    if b1 in (0xcc, 0xcd, 0xce, 0xcf) and b4:
        return "odd-dword"                 # 32-bit operand must be an even register pair
    if (b1 in (0xe0, 0xe1) or b1 == 0xe8 and lo4 in (0, 1)) and hi4 == 15:
        return "pair-overflow"             # byte result pair R7H:R8L
    if (b1 in (0xe4, 0xe6) or b1 == 0xe9 and lo4 in (0, 8)) and hi4 == 7:
        return "pair-overflow"             # word result pair R7:R8
    return None


def oracle_bug(b1, b2, mt, gt):
    """Differences traced to MAME's XA disassembler (checked against the user guide encodings
    and the asxa assembler)."""
    mm = mt.split(",")[0]
    gm = gt.split(",")[0]
    if b1 in (0xb0, 0xb7, 0xb8, 0xbf) and mm == gm:
        return "oracle-rotate-count"       # MAME prints the wrong field as the count
    if b1 in (0xd2, 0xda, 0xde) and mt.split("R")[0] == gt.split("R")[0]:
        return "oracle-asr-imm"            # MAME decodes ASR #imm with shifted fields
    if b1 in (0xd7, 0xdf) and "RD," in mt:
        return "oracle-rlc"                # MAME prints "RLC Rd, Rn"
    if b1 in (0xa0, 0xa8) and not b2 & 8 and mt.split(",")[0][:5] == gt.split(",")[0][:5]:
        return "oracle-mov-ind-dir"        # MAME takes the pointer from bits 2-0
    if b1 in (0xc4, 0xd4):
        mv, gv = int(mt.split("0X")[-1], 16), int(gt.split("0X")[-1], 16)
        if mv == gv + 1:
            return "odd-target"            # FCALL/FJMP clear bit 0 of the target (PC.0 = 0)
        if mv & 0xfffe == gv and mv != gv:
            return "page0-target"          # page 0 mode uses 16 bits of addr24
    if b1 in (0xa0, 0xa8) and b2 & 8 and mt.split(",")[1:] == gt.split(",")[1:]:
        return "oracle-xch-dir"            # MAME takes the register from bits 3-0
    if b1 in (0xe5, 0xe7) and mm == gm:
        return "oracle-div-src"            # 16/8 divide: the source is a byte register
    if b1 == 0xe8 and b2 & 15 in (3, 0xb) and mt.split(",")[1:] == gt.split(",")[1:]:
        return "oracle-div-dst"            # 16/8 divide: the destination is a word register
    if b1 == 0xeb and mt.split(",")[1:] == gt.split(",")[1:]:
        return "oracle-cjne-w"             # MAME names a byte register for CJNE.w
    if b1 == 0x95 and mt.split(",")[0] == gt.split(",")[0]:
        return "oracle-off16-imm8"         # MAME reads the wrong byte as #data8
    if re.search(r"0X[0-9A-F]+\.\d", mt) and b1 in (0x08, 0x97):
        return "oracle-databit"            # MAME adds 20h twice for data-memory bits
    return None


def classify(mb, mt, gb, gt, mraw):
    """Return the class name of an explained difference, or None."""
    if gt == "BAD" and ("ILLEGAL" in mt or "ILL_REG" in mt):
        return "both-illegal"
    b1 = int(mb[:2], 16)
    b2 = int(mb[2:4], 16) if len(mb) >= 4 else 0
    if gt == "BAD":
        return reserved(b1, b2)
    if mb == gb:
        return oracle_bug(b1, b2, mt, gt)
    return None


def main():
    args = sys.argv[1:]
    stride = 0
    if args[0] == "--stride":
        stride = int(args[1])
        args = args[2:]
    mame = load_mame(args[0], stride)
    ghid = load_ghidra(args[1])
    label = args[2] if len(args) > 2 else args[1]
    stats = Counter()
    bad = defaultdict(list)
    for a in sorted(mame):
        mb, mraw = mame[a]
        if a not in ghid:
            stats["missing"] += 1
            continue
        gb, graw = ghid[a]
        mt, gt = norm_mame(mraw), norm_ghidra(graw)
        mm = mraw.split()[0] if mraw else ""
        if "." not in mm and "." in gt.split(",")[0][:8] and gt != "BAD":
            # MAME omits the size suffix on some mnemonics (LSR reg, CJNE #imm, LEA ...)
            g2 = re.sub(r"^([A-Z]+)\.[BWD]", r"\1", gt)
            if mt == g2 and mb == gb:
                stats["exact-nosize"] += 1
                continue
        if mt == gt and mb == gb:
            stats["exact"] += 1
            continue
        c = classify(mb, mt, gb, gt, mraw)
        if c:
            stats[c] += 1
            if len(bad[c]) < 3:
                bad[c].append(f"{a:06x} {mb}/{gb}: mame '{mraw}' ghidra '{graw}'")
            continue
        stats["unexplained"] += 1
        bad["x " + mb[:2]].append(f"{a:06x} {mb}/{gb}: mame '{mraw}' ghidra '{graw}'")
    n = sum(stats.values())
    print(f"{label}: {n} instructions, {stats['exact']} exact, "
          + ", ".join(f"{k} {v}" for k, v in sorted(stats.items()) if k not in ("exact",)))
    import os
    for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        if not k.startswith("x ") and not os.environ.get("VERBOSE"):
            continue
        print(f"  [{k}] {len(v)}")
        for x in v[:3]:
            print("     ", x)
    return 1 if stats["unexplained"] or stats["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
