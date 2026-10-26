"""Explanations for DSP56156 decode differences vs MAME unidasm -arch dsp56156 (used by
compare.py --arch dsp56156). Written from the DSP56100 Family Manual (Appendix A Opcode
sections) and the DSP56156 User's Manual instruction list, independently of
tools/gen_dsp56156.py:

- valid(word, ext) decides from the manual's encodings whether a word is a defined DSP56156
  instruction ('don't care' bits accepted). A record where Ghidra rejects a word that MAME
  decodes is explained only if valid() says the manual leaves it undefined; a word MAME
  rejects is explained only if valid() accepts it and the reason is one of MAME's known gaps.
- differences between two decodes are explained only by MAME behaviour confirmed against the
  manual and the Motorola ASM56100 assembler (see README).
"""
import re

D5_OK = set(range(32)) - {27}             # DDDDD: 11011 is the only unassigned code


def bf_second_ok(first, ext):
    if ext is None:
        return False
    bbb, opc = ext >> 13, (ext >> 8) & 0x1f
    if bbb not in (4, 2, 1):
        return False
    if first & 0x80:
        return opc in (0x12, 0x04, 0x18)     # BFCHG, BFCLR, BFSET
    return opc in (0x10, 0x00)               # BFTSTH, BFTSTL


def p15_ok(lo):
    hi4, low4 = lo >> 4, lo & 0xf
    if hi4 & 0x9 == 0 and lo & 0x4:          # 0xx0 F1DD: DIV (bits 6, 5 don't care)
        return True
    if hi4 == 0:
        return lo & 0x4 == 0                 # TFR(2) 0000F00J, ADC 0000F01J
    if hi4 == 1:
        return lo & 0x4 == 4                 # TST(2) 0001-1DD
    if hi4 == 2:
        return True                          # NORM 0010F0RR (F1DD is DIV)
    if hi4 == 3:
        return low4 & 0x6 == 0               # ASR4 / ASL4
    if hi4 == 5:
        return low4 & 0x7 in (0, 2)          # ZERO / EXT
    if hi4 == 6:
        return low4 & 0x7 == 0               # NEGC
    if hi4 == 7:
        return low4 & 0x6 == 0               # ASR16 / SWAP
    return hi4 in (8, 9, 10, 11, 12, 14)     # IMPY DMACss IMAC DMACsu/uu MPYsu/uu MACsu/uu


def valid(w, ext=None):
    if w & 0x8000:
        return True                                          # 1mRRHHHW + ALU
    if w >> 13 == 3:
        return (w >> 5) & 3 != 3                             # dual read: rr = 11 reserved
    t = w >> 12
    if t == 5:
        return True                                          # X:(F1)
    if t == 4:
        return (w >> 8) & 0xf != 11                          # IIII = 1011 undefined
    if t == 3:
        if not w & 0x800:
            return True                                      # address register update
        if (w >> 5) & 0x1f not in D5_OK:
            return False
        if w & 0x10 and w & 0x6 == 4 and w & 0x8 and not w & 0x400:
            return False                                     # immediate as a destination
        return True
    if t == 2:
        if (w >> 10) & 3 == 2:
            return (w >> 5) & 0x1f in D5_OK and w & 0x1f in D5_OK
        return True                                          # MOVE(I), TFR3, Bcc aa
    if t == 1:
        hb = w >> 8
        if hb & 0xf8 == 0x18:
            return True                                      # ANDI/ORI, MOVE(S)/(P)
        if hb in (0x16, 0x17):
            return True                                      # MPY/MAC + write + move
        if hb == 0x15:
            return p15_ok(w & 0xff)
        if hb == 0x14:
            if not bf_second_ok(w, ext):
                return False
            if w & 0x40 or w & 0x20:
                return True
            return w & 0x1f in D5_OK
        if hb & 0xfc == 0x10:
            return w & 0x2 == 0                              # Tcc: bit 1 = 0
        return False
    hb = w >> 8
    lo = w & 0xff
    if hb in (0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x06, 0x07):
        return True
    if hb == 0x05:
        if ext is None:
            return False
        if ext >> 11 == 7 and not ext & 0x10:
            return (ext >> 5) & 0x1f in D5_OK                # MOVE(C) X:(R2+xx)
        return True                                          # MOVE(M) P:(R2+xx) / parallel
    if hb == 0x04:
        return lo >> 6 == 0 and lo & 0x1f in D5_OK           # DO S / REP S
    if hb in (0x02, 0x03):
        return lo & 0x30 != 0x20                             # MOVE(M)
    if hb == 0x01:
        if lo & 0x80:
            return lo & 0x0c != 0                            # LEA: MM = 00 not an update mode
        return lo >> 4 in (1, 2, 3, 5)                       # BRKcc, Rn forms, xxxx forms, REPcc
    if hb == 0x00:
        if lo >> 4 == 0:
            return lo in (0, 1, 2, 4, 5, 6, 7, 8, 9, 0xa, 0xb, 0xf)
        if lo >> 4 == 5:
            return True                                      # DEBUGcc
        return lo >> 6 == 3 and lo & 0x20 == 0 or lo >> 5 in (6, 7)
    return False


def mame_raw(t, addr, words):
    """MAME prints PC-relative targets as *+$n / *-$n (from the instruction address) and short
    immediates as #<+$n: rewrite to absolute addresses and plain numbers"""
    def rel(m):
        n = int(m.group(2), 16)
        v = addr + n if m.group(1) == "+" else addr - n
        return "$%x" % (v & 0xffff)
    t = re.sub(r"\*([+-])\$([0-9a-fA-F]+)", rel, t)
    t = t.replace("#<+$", "#<$")
    return t


ACC_PARTS = {"a": {"a", "a0", "a1", "a2", "a10"}, "b": {"b", "b0", "b1", "b2", "b10"}}


def move_dests(ops):
    """destination registers of the parallel-move text (after the ALU operands)"""
    d = []
    for part in ops:
        if "," in part:
            dst = part.rsplit(",", 1)[1]
            if not dst.startswith("x:"):
                d.append(dst)
    return d


def explain(w, nm, ng, mi, gi, mn, gn, ext=None):
    v = valid(w, ext)
    if gi and not mi:
        return "MAME decodes an encoding the manual leaves undefined" if not v else None
    if mi and not gi:
        if not v:
            return None
        hb = w >> 8
        if hb == 0x14:
            return "BFCHG/BFCLR/BFSET/BFTSTH/BFTSTL: MAME lacks the bit-field instructions"
        if hb == 0x05:
            return "X:(R2+xx) / P:(R2+xx) forms: MAME lacks them"
        if hb == 0x15 and (w & 0x90) == 0 and w & 4 and w & 0x60:
            return "MAME requires the DIV don't-care bits 6..5 = 0"
        if hb == 0x15 and w & 0xf0 == 0x10 and w & 8:
            return "MAME requires the TST(2) don't-care bit 3 = 0"
        if hb == 0x15 and w & 0xf0 == 0x90 and w & 4:
            return "MAME requires the DMACss don't-care bit 2 = 0"
        if w & 0xfc00 == 0x1000 and (w >> 4) & 3 == 0 and w & 5 == 1:
            return "MAME rejects Tcc R0,R0 without a data ALU transfer"
        if hb == 0x04 and w & 0x1f == 24:
            return "MAME rejects SSH as the DO/REP count source"
        if w & 0xfc00 == 0x2800 and (w >> 5) & 0x1f == 24 and w & 0x1f == 24:
            return "MAME rejects MOVE(C) SSH,SSH"
        # destination conflicts: MAME rejects a parallel move whose destination is (part of)
        # the data ALU accumulator, or two moves into one register; the manual states this as an
        # assembler restriction ("duplicate destinations are not allowed"), not an encoding one
        toks = ng.split(" ")
        if toks[0] == "move" and w >> 12 == 4:
            toks = ["move", "b" if w & 8 else "a"] + toks[1:]   # MOVE: bit 3 still names F
        if len(toks) >= 2:
            alu = toks[1].split(",")[-1]
            rest = toks[2:]
            dests = move_dests(rest)
            if alu in ACC_PARTS and any(x in ACC_PARTS[alu] for x in dests):
                return "MAME rejects a parallel move into the data ALU accumulator (assembler restriction)"
            if toks[0] == "tfr3" and len(rest) >= 1:
                d1 = toks[1].split(",")[-1]
                if d1 in dests:
                    return "MAME rejects TFR(3) with D1 = D2 (assembler restriction)"
            if len(dests) == 2 and dests[0] == dests[1]:
                return "MAME rejects two parallel moves into one register (assembler restriction)"
        return None
    # both decode, texts differ
    if w >> 13 == 3 and w & 0x80:
        # dual-read multiply: MAME prints S2,S1 (Y before X); the manual lists X0,Y0 ...
        m = re.match(r"^(\S+) (\w+),(\w+),(\w+)(.*)$", nm)
        if m:
            t = "%s %s,%s,%s%s" % (m.group(1), m.group(3), m.group(2), m.group(4), m.group(5))
            if t == ng and mn == gn:
                return "MAME prints the dual-read multiply sources in S2,S1 order"
    if nm == "nop" and ng == "move":
        return "MAME prints a MOVE with no move fields as NOP"
    return None
