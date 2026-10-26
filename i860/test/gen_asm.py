#!/usr/bin/env python3
"""Assembler-enumerated corpus: every instruction form of the i860 XR/XP with a spread of
operands, in GNU as syntax (AT&T/SVR4, run with -mxp). Each test instruction sits at an 8-byte
aligned address and is followed by a nop, so it decodes on its own (test words at 8k).

  gen_asm.py <out.s> <out.lst>
out.lst gets one line per test instruction: its source text.
"""
import sys

R = ["%r0", "%r1", "%sp", "%fp", "%r4", "%r15", "%r16", "%r27", "%r31"]
lines = []


def t(s):
    lines.append(s)


def main():
    regs3 = [("%r1", "%r2", "%r3"), ("%r0", "%r31", "%r16"), ("%r17", "%r0", "%r0"), ("%r4", "%r5", "%r6")]
    for op in ("addu", "subu", "adds", "subs", "and", "andnot", "or", "xor", "shl", "shr", "shra"):
        for a, b, c in regs3:
            t(f"{op} {a},{b},{c}")
    for op in ("addu", "subu", "adds", "subs", "shl", "shr", "shra"):
        for imm in (-32768, -1, 0, 1, 31, 32767):
            t(f"{op} {imm},%r5,%r6")
    for op in ("and", "andnot", "or", "xor", "andh", "andnoth", "orh", "xorh"):
        for imm in (0, 1, 0x8000, 0xffff, 0x1234):
            t(f"{op} {imm},%r5,%r6")
    for a, b, c in regs3:
        t(f"shrd {a},{b},{c}")
        t(f"trap {a},{b},{c}")
    t("fnop")
    t("d.fnop")
    for r in R:
        t(f"bri {r}")
        if r != "%r1":
            t(f"calli {r}")
    for op in ("br", "call", "bc", "bc.t", "bnc", "bnc.t"):
        for tgt in ("L_back", "L_fwd", ".+8", ".-0x1000", ".+0x400000"):
            t(f"{op} {tgt}")
    for op in ("bte", "btne"):
        for a in ("%r0", "%r7", "%r31", "0", "5", "31"):
            for tgt in ("L_back", "L_fwd", ".+0x20000", ".-0x1fffc"):
                t(f"{op} {a},%r9,{tgt}")
    for tgt in ("L_back", "L_fwd", ".+0x20000", ".-0x1fffc"):
        t(f"bla %r4,%r5,{tgt}")
    # loads and stores
    for sz, offs in (("b", (-32768, -1, 0, 1, 32767)), ("s", (-32768, -2, 0, 2, 32766)),
                     ("l", (-32768, -4, 0, 4, 32764))):
        for o in offs:
            t(f"ld.{sz} {o}(%r4),%r5")
            t(f"st.{sz} %r5,{o}(%r4)")
        t(f"ld.{sz} %r6(%r4),%r5")
        t(f"ld.{sz} %r0(%r0),%r31")
    t("ixfr %r5,%f6")
    t("ixfr %r0,%f31")
    for sz, align, regs in (("l", 4, ("%f0", "%f1", "%f5", "%f31")), ("d", 8, ("%f0", "%f2", "%f30")),
                            ("q", 16, ("%f0", "%f4", "%f28"))):
        for o in (-32768, -align, 0, align, 32768 - align):
            for r in regs:
                t(f"fld.{sz} {o}(%r4),{r}")
                t(f"fst.{sz} {r},{o}(%r4)")
                t(f"fld.{sz} {o}(%r4)++,{r}")
                t(f"fst.{sz} {r},{o}(%r4)++")
                if sz != "q" or True:
                    t(f"pfld.{sz} {o}(%r4),{r}")
                    t(f"pfld.{sz} {o}(%r4)++,{r}")
        t(f"fld.{sz} %r6(%r4),{regs[-1]}")
        t(f"fld.{sz} %r6(%r4)++,{regs[-1]}")
        t(f"fst.{sz} {regs[-1]},%r6(%r4)")
        t(f"fst.{sz} {regs[-1]},%r6(%r4)++")
        t(f"pfld.{sz} %r6(%r4),{regs[-1]}")
        t(f"pfld.{sz} %r6(%r4)++,{regs[-1]}")
    for o in (-32768, -16, 0, 16, 32752):
        t(f"flush {o}(%r4)")
        t(f"flush {o}(%r4)++")
    for o in (-32768, -8, 0, 8, 32760):
        t(f"pst.d %f8,{o}(%r4)")
        t(f"pst.d %f0,{o}(%r4)++")
    for c in ("fir", "psr", "dirbase", "db", "fsr", "epsr", "bear", "ccr", "p0", "p1", "p2", "p3"):
        t(f"ld.c %{c},%r5")
        t(f"st.c %r5,%{c}")
    t("lock")
    t("unlock")
    t("intovr")
    for sz in "bsl":
        t(f"ldio.{sz} %r4,%r5")
        t(f"stio.{sz} %r5,%r4")
        t(f"ldint.{sz} %r4,%r5")
    t("scyc.b %r4")      # GNU as knows only scyc.b
    # floating point
    P3 = ("ss", "sd", "dd")

    def regsfor(p):
        s = {"s": ("%f5", "%f6", "%f7"), "d": ("%f4", "%f6", "%f8")}
        a, b = s[p[0]][0], s[p[0]][1]
        d = "%f9" if p[1] == "s" else "%f10"
        return a, b, d

    for d in ("", "d."):
        for op in ("fmul", "pfmul", "fadd", "pfadd", "fsub", "pfsub"):
            for p in P3:
                a, b, c = regsfor(p)
                t(f"{d}{op}.{p} {a},{b},{c}")
        t(f"{d}fmlow.dd %f4,%f6,%f8")
        t(f"{d}pfmul3.dd %f4,%f6,%f8")
        for op in ("frcp", "frsqr"):
            for p in P3:
                a, b, c = regsfor(p)
                t(f"{d}{op}.{p} {b},{c}")
        for op in ("fix", "pfix", "ftrunc", "pftrunc"):
            for p in ("sd", "dd"):
                a, b, c = regsfor(p)
                t(f"{d}{op}.{p} {a},{c}")
        for op in ("famov", "pfamov"):
            for p in ("ss", "sd", "ds", "dd"):
                a, b, c = regsfor(p)
                t(f"{d}{op}.{p} {a},{c}")
        for op in ("pfgt", "pfle"):
            for p in ("ss", "dd"):
                a, b, c = regsfor(p)
                t(f"{d}{op}.{p} {a},{b},%f0")
        for p in ("ss", "dd"):     # GNU as has no pfeq.sd
            a, b, c = regsfor(p)
            t(f"{d}pfeq.{p} {a},{b},%f0")
        t(f"{d}fxfr %f5,%r6")
        for op in ("fiadd", "pfiadd", "fisub", "pfisub"):
            t(f"{d}{op}.ss %f5,%f6,%f7")
            t(f"{d}{op}.dd %f4,%f6,%f8")
        for op in ("faddp", "pfaddp", "faddz", "pfaddz", "fzchkl", "pfzchkl", "fzchks", "pfzchks"):
            t(f"{d}{op} %f4,%f6,%f8")
        t(f"{d}form %f4,%f8")
        t(f"{d}pform %f4,%f8")
        for names in (["r2p1", "r2pt", "r2ap1", "r2apt", "i2p1", "i2pt", "i2ap1", "i2apt",
                       "rat1p2", "m12apm", "ra1p2", "m12ttpa", "iat1p2", "m12tpm", "ia1p2", "m12tpa"],
                      ["r2s1", "r2st", "r2as1", "r2ast", "i2s1", "i2st", "i2as1", "i2ast",
                       "rat1s2", "m12asm", "ra1s2", "m12ttsa", "iat1s2", "m12tsm", "ia1s2", "m12tsa"],
                      ["mr2p1", "mr2pt", "mr2mp1", "mr2mpt", "mi2p1", "mi2pt", "mi2mp1", "mi2mpt",
                       "mrmt1p2", "mm12mpm", "mrm1p2", "mm12ttpm", "mimt1p2", "mm12tpm", "mim1p2"],
                      ["mr2s1", "mr2st", "mr2ms1", "mr2mst", "mi2s1", "mi2st", "mi2ms1", "mi2mst",
                       "mrmt1s2", "mm12msm", "mrm1s2", "mm12ttsm", "mimt1s2", "mm12tsm", "mim1s2"]):
            for n in names:
                for p in P3:
                    reg = "%f4,%f6,%f8" if p == "dd" else "%f5,%f7,%f9" if p == "ss" else None
                    if p == "sd":
                        # src1 feeds the multiplier (single) or the adder (double)
                        k = names.index(n)
                        s1 = "%f5" if k in (1, 3, 5, 7, 9, 11, 13, 15) else "%f4"
                        s2 = "%f6" if k in (8, 10, 12, 14) else "%f7"
                        reg = f"{s1},{s2},%f8"
                    t(f"{d}{n}.{p} {reg}")
    with open(sys.argv[1], "w") as f:
        f.write("\t.text\n\t.align 8\nL_back:\n")
        for s in lines:
            f.write(f"\t.align 8\n\t{s}\n\tnop\n")
        f.write("L_fwd:\n\tnop\n")
    with open(sys.argv[2], "w") as f:
        f.write("\n".join(lines) + "\n")


main()
