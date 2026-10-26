#!/usr/bin/env python3
"""Compare MAME unidasm (tms320c2x / tms320c5x) with Ghidra on a gen_corpus.py corpus.

    compare.py <family c2x|c5x> <corpus dir> [--show N]

<corpus dir> holds records.txt, m/cNN.txt (unidasm output per chunk) and g/cNN.bin.txt (Ghidra
TmsDump output per chunk, stride 4). Both listings are normalised (numbers to integers, case,
spacing, operand syntax) and compared record by record, including the instruction length. Known
differences are classified by explain(): each class is a confirmed MAME display or decode error,
or an encoding the manual marks reserved; anything else is unexplained. Exit status 1 if any
difference is unexplained.
"""
import collections
import os
import re
import sys

REC = 4
CHUNK = 16384


def parse_mame(path):
    lines = []
    for line in open(path):
        m = re.match(r"^\s*([0-9a-f]+): (\S+)(?: (\S{4}))?\s+(.*)$", line.rstrip("\n"))
        lines.append((int(m.group(1), 16), m.group(4).strip()))
    res = {}
    for i, (a, t) in enumerate(lines):
        if a % REC == 0:
            n = (lines[i + 1][0] if i + 1 < len(lines) else a + 1) - a
            res[a // REC] = (n, t)
    return res


def parse_ghidra(path):
    res = {}
    for line in open(path):
        a, n, t = line.rstrip("\n").split(" ", 2)
        a = int(a, 16)
        if a % REC == 0:
            res[a // REC] = (int(n), t.strip())
    return res


def tonum(s):
    s = s.strip()
    m = re.fullmatch(r"#?(-?)0x([0-9a-f]+)", s)
    if m:
        return int(m.group(2), 16) * (-1 if m.group(1) else 1)
    m = re.fullmatch(r"#?([0-9a-f]+)h", s)
    if m:
        return int(m.group(1), 16)
    m = re.fullmatch(r"(?:pa)?\$([0-9a-f]+)", s)
    if m:
        return int(m.group(1), 16)
    m = re.fullmatch(r"#?(-?\d+)", s)
    if m:
        return int(m.group(1))
    return None


BRANCH5 = {"b", "bd", "call", "calld", "banz", "banzd"}


def norm_c2x(text, ghidra):
    t = text.lower().strip()
    t = re.sub(r"\s*\(.*\)$", "", t)                 # MAME "cmpr 0 (ARx = AR0)"
    mn, _, rest = t.partition(" ")
    rest = rest.strip()
    if not ghidra:
        rest = re.sub(r"(?<!\*)br0-", "*br0-", rest)   # MAME prints the *BR0- mode without '*'
        rest = re.sub(r"(ar\d)\*", r"\1,*", rest)     # MAME "lar AR0*,AR0" = "lar AR0,*,AR0"
        rest = re.sub(r"^\$([0-9a-f]+)h$", r"$\1", rest)  # MAME "mar $10h"
        rest = re.sub(r"^([0-9a-f]+h) ", r"\1,", rest)  # MAME "b 1234h *,AR0"
    ops = [o.strip() for o in rest.split(",")] if rest else []
    return mn, ops


TARGET5 = {"b", "bd", "call", "calld", "banz", "banzd", "bcnd", "bcndd", "cc", "ccd"}
SWAP5 = {"splk", "mac", "macd", "apl", "opl", "xpl", "cpl"}   # MAME prints dma before #lk / pma


MMR5 = {n: i + 4 for i, n in enumerate(
    "imr greg ifr pmst rptc brcr pasr paer treg0 treg1 treg2 dbmr ar0 ar1 ar2 ar3 ar4 ar5 ar6 ar7 "
    "indx arcr cbsr1 cber1 cbsr2 cber2 cbcr bmar".split())}
SHIFT5 = {"lacc", "add", "sub", "sacl", "sach", "and", "or", "xor"}


def norm_c5x(text, ghidra, hi=0):
    t = text.lower().strip()
    mn, _, rest = t.partition(" ")
    rest = re.sub(r"\s+", " ", rest.strip())
    if not ghidra:
        rest = re.sub(r"\s*<<\s*16$", ",16", rest)    # MAME "add * << 16"
        rest = {"hold": "hm", "carry": "c"}.get(rest, rest)
        m = re.fullmatch(r"ar (=|<|>|!=) arcr", rest)  # MAME "cmpr ar < arcr"
        if m:
            rest = str(["=", "<", ">", "!="].index(m.group(1)))
        if mn in ("bcnd", "bcndd", "cc", "ccd", "retc", "retcd", "xc"):
            rest = rest.replace(" ", ",")             # MAME "c ov"
    ops = [o.strip() for o in rest.split(",") if o.strip() != ""] if rest else []
    if not ghidra:
        conv = []
        for i, o in enumerate(ops):
            if re.fullmatch(r"#[0-9a-f]+", o):
                conv.append(int(o[1:], 16))
            elif re.fullmatch(r"[0-9a-f]+", o) and i == 0 and mn in TARGET5:
                conv.append(int(o, 16))
            elif re.fullmatch(r"\d+", o):
                conv.append(int(o))
            else:
                conv.append(o)
        ops = conv
        if (mn in ("splk", "mac", "macd") or (mn, hi) in (("bldd", 0xA8), ("blpd", 0xA5)) or
                (mn in ("apl", "opl", "xpl", "cpl") and 0x5C <= hi <= 0x5F)) and len(ops) >= 2:
            # MAME prints dma (or ind[,arN]) before the #lk / pma word
            ops = [ops[-1]] + ops[:-1]
        if mn == "bit" and len(ops) >= 2:
            ops = ops[1:2] + [ops[0]] + ops[2:]       # MAME "bit code, dma"
        if mn in SHIFT5 and len(ops) == 3 and isinstance(ops[2], int) and str(ops[1]).startswith("ar"):
            ops = [ops[0], ops[2], ops[1]]            # MAME "add *-, ar2 , 10"
    else:
        # long immediates with a shift: MAME prints the shifted value
        if mn in SHIFT5 and len(ops) == 2 and ops[0].startswith("#") and tonum(ops[1]) is not None:
            ops = ["#0x%x" % ((tonum(ops[0]) << tonum(ops[1])) & 0xffffffff)]
        conv = []
        for o in ops:
            v = tonum(o)
            conv.append(v if v is not None else o)
        ops = conv
    ops = [o for o in ops if o != "unc"]
    # the next-ARP operand goes last (TI syntax); MAME puts it right after the indirect operand
    for i in range(1, len(ops)):
        if isinstance(ops[i], str) and re.fullmatch(r"ar[0-7]", ops[i]) and str(ops[i - 1]).startswith("*"):
            ops = ops[:i] + ops[i + 1:] + [ops[i]]
            break
    if ghidra:
        if hi in (0xA4, 0xAC, 0xAD):
            ops = [o for o in ops if o != "bmar"]     # MAME omits the BMAR operand
        # direct operands that hit a memory-mapped register print as its name
        conv = []
        for i, o in enumerate(ops):
            isar = isinstance(o, str) and re.fullmatch(r"ar[0-7]", o)
            if isinstance(o, str) and o in MMR5 and not (isar and (
                    (i == 0 and mn in ("lar", "sar")) or (i > 0 and str(ops[i - 1]).startswith("*")) or
                    (i == len(ops) - 1 and any(str(x).startswith("*") for x in ops)))):
                conv.append(MMR5[o])
            else:
                conv.append(o)
        ops = conv
    if mn in ("bcnd", "bcndd", "cc", "ccd", "retc", "retcd", "xc"):
        k = 1 if mn not in ("retc", "retcd") else 0
        ops = ops[:k] + sorted(str(o) for o in ops[k:])   # condition order differs
    if mn in SHIFT5 and len(ops) >= 2 and ops[1] == 0:
        ops = ops[:1] + ops[2:]                       # shift 0 (MAME omits it)
    return mn, ops


def canon(fam, text, ghidra, word, w2):
    mn, ops = norm_c2x(text, ghidra) if fam == "c2x" else norm_c5x(text, ghidra, word >> 8)
    out = []
    for o in ops:
        v = tonum(o) if isinstance(o, str) else o
        out.append(v if v is not None else o)
    # 13-bit multiply constants: the module shows them signed, MAME unsigned
    if mn == "mpyk" or (mn == "mpy" and fam == "c5x" and (word >> 13) == 6):
        out = [o & 0x1fff if isinstance(o, int) else o for o in out]
    # branches: a lone trailing '*' means "no AR modification"
    if out and out[-1] == "*" and fam == "c2x" and mn.startswith("b") or \
            out and out[-1] == "*" and mn in ("call",) or \
            (fam == "c5x" and mn in BRANCH5 and len(out) == 2 and out[-1] == "*"):
        out = out[:-1]
    return mn, out


def explain(fam, word, w2, g, m):
    """Classify a difference: returns a class name for a known/confirmed case, else None."""
    gn, gt = g
    mn_, mt = m
    hi = word >> 8
    ind = (word & 0x80) != 0
    aru = (word >> 4) & 7
    if fam == "c2x":
        if gt.startswith("BAD") and ind and aru == 3 and "??" in mt:
            return "reserved ARU 011 (indirect): MAME prints '??', module rejects"
        if hi == 0xCF and mt.startswith("mpys"):
            return "MAME decodes CFxx (MPYU) as MPYS"
        if hi in (0x7E, 0x7F) and ind and re.match(r"(adrk|sbrk)\s+(\*|\?\?|br0)", mt.lower()):
            return "MAME decodes ADRK/SBRK constants >= 80h as indirect operands"
        if hi == 0x43 and mt.startswith("addc"):
            return "MAME prints a spurious shift operand on ADDC"
        return None
    # c5x
    if gt.startswith("BAD") and ind and aru == 3 and "???" in mt:
        return "reserved ARU 011 (indirect): MAME prints '???', module rejects"
    if hi in (0x79, 0x7A, 0x7B, 0x7D, 0x7E, 0x7F) and not ind and gt.startswith("BAD"):
        return "branch/call with bit 7 = 0: the manual's opcode is 1AAA AAAA; MAME ignores bit 7"
    if hi == 0xBF and 0x40 <= (word & 0xff) <= 0x4F and not (0x44 <= (word & 0xff) <= 0x47) and gt == "BAD":
        return "CMPR with bits 3-2 != 01 (manual: 0100 01CM); MAME ignores them"
    if hi == 0xBF and 0x04 <= (word & 0xff) <= 0x07 and gt == "BAD":
        return "SPM with bit 2 set (manual: 0000 00PM); MAME ignores it"
    if word in (0xBE31, 0xBE90, 0xBE91, 0xBE92, 0xBE93, 0xBEB0, 0xBEB1, 0xBEB3) and mt.startswith("???"):
        return "undocumented emulation instruction (TI assembler, via c5xtools); MAME does not decode it"
    if (word >> 13) == 6 and mt.startswith("???") and gt.startswith("MPY"):
        return "MAME does not decode MPY #k (13-bit short immediate, C000h-DFFFh)"
    if hi == 0xA0 and mt.startswith("norm") and mn_ == 2 and gn == 1:
        return "MAME decodes NORM (A0xx) as a 2-word instruction"
    if hi == 0xA3 and mt.startswith("macd") and mn_ == 1 and gn == 2:
        return "MAME decodes MACD (A3xx) as a 1-word instruction"
    return None


def main():
    fam, d = sys.argv[1], sys.argv[2]
    show = 5
    if "--show" in sys.argv:
        show = int(sys.argv[sys.argv.index("--show") + 1])
    recs = [tuple(int(x, 16) for x in l.split()) for l in open(os.path.join(d, "records.txt"))]
    total = exact = 0
    classes = collections.Counter()
    unexpl = collections.defaultdict(list)
    for c in range((len(recs) + CHUNK - 1) // CHUNK):
        m = parse_mame(os.path.join(d, "m", "c%02d.txt" % c))
        g = parse_ghidra(os.path.join(d, "g", "c%02d.bin.txt" % c))
        for i in range(min(CHUNK, len(recs) - c * CHUNK)):
            word, w2 = recs[c * CHUNK + i]
            total += 1
            gg = g.get(i, (1, "BAD"))
            mm = m.get(i, (1, "?"))
            gbad = gg[1].startswith("BAD")
            mbad = "??" in mm[1] or mm[1].startswith("dw") or "dw " in mm[1]
            if gbad and mbad and "??" not in mm[1].split(" ", 1)[-1][:0]:
                if mm[1].split()[0] in ("????", "???"):
                    exact += 1
                    continue
            same = (not gbad and not mbad and gg[0] == mm[0] and
                    canon(fam, gg[1], True, word, w2) == canon(fam, mm[1], False, word, w2))
            if same:
                exact += 1
                continue
            cls = explain(fam, word, w2, gg, mm)
            if cls:
                classes[cls] += 1
            else:
                key = (word >> 8, gg[1].split(" ")[0], mm[1].split(" ")[0])
                unexpl[key].append((word, w2, gg, mm))
    nun = sum(len(v) for v in unexpl.values())
    print(f"{fam}: {total} records, {exact} identical after normalisation, "
          f"{sum(classes.values())} explained, {nun} unexplained")
    for k, v in classes.most_common():
        print(f"  explained {v:6d}  {k}")
    for k, v in sorted(unexpl.items(), key=lambda kv: -len(kv[1])):
        print(f"  UNEXPLAINED {len(v):6d}  op {k[0]:02x}  ghidra {k[1]}  mame {k[2]}")
        for word, w2, gg, mm in v[:show]:
            print(f"      {word:04x} {w2:04x}  ghidra[{gg[0]}] {gg[1]!r}  mame[{mm[0]}] {mm[1]!r}")
    sys.exit(1 if nun else 0)


if __name__ == "__main__":
    main()
