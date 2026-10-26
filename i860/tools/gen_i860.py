#!/usr/bin/env python3
"""Generate data/languages/i860_gen.sinc: the Intel i860 XR/XP instruction constructors.

Encodings and operations follow the i860 Programmer's Reference Manual (Intel 240875-001,
May 1991): appendix B (formats and opcodes), chapter 7 (core instructions) and chapter 8
(floating-point, graphics and dual-operation instructions). XP-only encodings (ldio, stio,
ldint, scyc, pfld.q and the control registers bear, ccr, p0-p3) are wrapped in @ifdef XP.

Output is deterministic: python3 tools/gen_i860.py > data/languages/i860_gen.sinc
"""

import sys

out = []


def emit(s=""):
    out.append(s)


# ---------------------------------------------------------------------------------------------
# helpers

CTX_SINGLE = "slot=0"            # single-instruction mode, or (undefined) core op in a low word
CTX_DUAL = "dual=1 & slot=1"     # core word of a dual pair: the delay slot is the next pair


def ctor(mnem, operands, pattern, body, ifdef=None):
    disp = ":" + mnem + ((" " + operands) if operands else "")
    if ifdef:
        emit("@ifdef " + ifdef)
    emit(f"{disp} is {pattern} & cx {{")
    for line in body.strip("\n").split("\n"):
        emit("\t" + line.strip())
    emit("}")
    if ifdef:
        emit("@endif")


# ---------------------------------------------------------------------------------------------
# integer arithmetic and logic (manual 7.7, 7.8, 7.10)

def alu():
    emit("# ---- integer add/subtract (7.7): CC and epsr.OF ----")
    # (name, op6 base): register form op6, immediate form op6 + 1
    for name, base in (("addu", 0x20), ("subu", 0x22), ("adds", 0x24), ("subs", 0x26)):
        for imm in (0, 1):
            op = base + imm
            a = "simm16" if imm else "rs1"
            pat = f"op6={op:#x} & {a} & rs2 & rd" if imm else f"op6={op:#x} & rs1 & rs2 & rd"
            if imm:
                pre = "local a:4 = simm16;"
            else:
                pre = "local a:4 = rs1;"
            pre += "\nlocal b:4 = rs2;"
            if name == "addu":
                calc = "local r:4 = a + b;\nlocal c:1 = carry(a, b);\nOF = c;"
                cc = "c"
            elif name == "adds":
                calc = "local r:4 = a + b;\nlocal v:1 = scarry(a, b);\nOF = v;"
                cc = "(r s< 0) != v"
            elif name == "subu":
                calc = "local r:4 = a - b;\nlocal c:1 = !(a < b);\nOF = !c;"
                cc = "c"
            else:
                calc = "local r:4 = a - b;\nOF = sborrow(a, b);"
                cc = "b s> a"
            for cmp in (0, 1):
                body = pre + "\n" + calc + "\n"
                if cmp == 0:
                    body += f"CC = {cc};\n"
                body += "rd = r;"
                ctor(name, f"{a},rs2,rd", pat + f" & cmpslot={cmp}", body)
    emit()
    emit("# ---- logical (7.10): CC set if the result is zero ----")
    for name, base, expr in (("and", 0x30, "a & b"), ("andnot", 0x34, "~a & b"),
                             ("or", 0x38, "a | b"), ("xor", 0x3c, "a ^ b")):
        for form in ("reg", "imm", "high"):
            if form == "reg":
                op, mn, a, pre = base, name, "rs1", "local a:4 = rs1;"
            elif form == "imm":
                op, mn, a, pre = base + 1, name, "imm16", "local a:4 = imm16;"
            else:
                op, mn, a, pre = base + 3, name + "h", "imm16", "local a:4 = imm16 << 16;"
            pat = f"op6={op:#x} & {a} & rs2 & rd"
            for cmp in (0, 1):
                body = f"{pre}\nlocal b:4 = rs2;\nlocal r:4 = {expr};\n"
                if cmp == 0:
                    body += "CC = (r == 0);\n"
                body += "rd = r;"
                ctor(mn, f"{a},rs2,rd", pat + f" & cmpslot={cmp}", body)
    emit()
    emit("# ---- shifts (7.8); counts are taken modulo 32 ----")
    for name, base in (("shl", 0x28), ("shr", 0x2a), ("shra", 0x2e)):
        for imm in (0, 1):
            op = base + imm
            a = "simm16" if imm else "rs1"
            pre = "local n:4 = simm16 & 31;" if imm else "local n:4 = rs1 & 31;"
            if name == "shl":
                body = f"{pre}\nrd = rs2 << n;"
            elif name == "shr":
                body = f"{pre}\nlocal b:4 = rs2;\nSC = n:1;\nrd = b >> n;"
            else:
                body = f"{pre}\nrd = rs2 s>> n;"
            ctor(name, f"{a},rs2,rd", f"op6={op:#x} & {a} & rs2 & rd", body)
    # shrd: bit 9 is interpreted as the dual-instruction-mode bit (8.6), so d.shrd is d.fnop
    for d in (0, 1):
        mn = "d.shrd" if d else "shrd"
        ctor(mn, "rs1,rs2,rd", f"op6=0x2c & fD={d} & rs1 & rs2 & rd",
             "local v:8 = (zext(rs1) << 32) | zext(rs2);\nv = v >> zext(SC & 0x1f);\nrd = v:4;")
    emit()


# ---------------------------------------------------------------------------------------------
# loads and stores (7.1-7.6, 7.12, 7.13)

def addr_operands():
    """Address-mode subtables. Each exports the effective address; ++ forms update src2."""
    emit("# ---- address modes ----")
    # ld.b: register index or full 16-bit offset
    emit("eab: rs1^\"(\"^rs2^\")\" is opI=0 & rs1 & rs2 { local a:4 = rs1 + rs2; export a; }")
    emit("eab: simm16^\"(\"^rs2^\")\" is opI=1 & simm16 & rs2 { local a:4 = simm16 + rs2; export a; }")
    # ld.s/ld.l: bit 0 selects the size; an immediate offset has bit 0 forced to zero (and is
    # aligned to the operand size, as for fld below)
    emit("eah: rs1^\"(\"^rs2^\")\" is opI=0 & rs1 & rs2 { local a:4 = rs1 + rs2; export a; }")
    emit("eah: off^\"(\"^rs2^\")\" is opI=1 & bit0=0 & simm16 & rs2 [ off = simm16 & ~1; ] { local a:4 = off + rs2; export a; }")
    emit("eah: off^\"(\"^rs2^\")\" is opI=1 & bit0=1 & simm16 & rs2 [ off = simm16 & ~3; ] { local a:4 = off + rs2; export a; }")
    # st.x: offset split between the dest field (high 5 bits) and bits 10-0
    emit("esb: off^\"(\"^rs2^\")\" is dhi & low11 & rs2 [ off = (dhi << 11) | low11; ] { local a:4 = off + rs2; export a; }")
    emit("esh: off^\"(\"^rs2^\")\" is bit0=0 & dhi & low11 & rs2 [ off = ((dhi << 11) | low11) & ~1; ] { local a:4 = off + rs2; export a; }")
    emit("esh: off^\"(\"^rs2^\")\" is bit0=1 & dhi & low11 & rs2 [ off = ((dhi << 11) | low11) & ~3; ] { local a:4 = off + rs2; export a; }")
    # fld/fst/pfld: bit 0 = autoincrement. The manual forces bits 1-0 (.l) or 2-0 (.d, .q) of an
    # immediate offset to zero and requires the address to be aligned to the operand size;
    # offsets are shown and used aligned to the operand size (bits 3-0 for .q), as MAME and GNU
    # objdump show them. The autoincrement form writes the effective address back into src2.
    for nm, mask in (("eafl", 3), ("eafd", 7), ("eafq", 15)):
        for inc in (0, 1):
            suf = "^\"++\"" if inc else ""
            wb = " rs2f = a;" if inc else ""
            emit(f"{nm}: rs1^\"(\"^rs2^\")\"{suf} is opI=0 & bit0={inc} & rs1 & rs2 & rs2f "
                 f"{{ local a:4 = rs1 + rs2;{wb} export a; }}")
            emit(f"{nm}: off^\"(\"^rs2^\")\"{suf} is opI=1 & bit0={inc} & simm16 & rs2 & rs2f "
                 f"[ off = simm16 & ~{mask}; ] {{ local a:4 = off + rs2;{wb} export a; }}")
    # flush and pst.d: immediate only (bits 2-1 must be zero); flush addresses a 16-byte line
    for nm, mask in (("eaim", 7), ("eafl16", 15)):
        for inc in (0, 1):
            suf = "^\"++\"" if inc else ""
            wb = " rs2f = a;" if inc else ""
            emit(f"{nm}: off^\"(\"^rs2^\")\"{suf} is bit0={inc} & simm16 & rs2 & rs2f "
                 f"[ off = simm16 & ~{mask}; ] {{ local a:4 = off + rs2;{wb} export a; }}")
    emit()


def loadstore():
    emit("# ---- integer loads and stores (7.1, 7.2) ----")
    for I in (0, 1):
        ctor("ld.b", "eab,rd", f"op6={0x00 + I:#x} & eab & rd", "rd = sext(*:1 eab);")
        ctor("ld.s", "eah,rd", f"op6={0x04 + I:#x} & bit0=0 & eah & rd", "rd = sext(*:2 eah);")
        ctor("ld.l", "eah,rd", f"op6={0x04 + I:#x} & bit0=1 & eah & rd", "rd = *:4 eah;")
    ctor("st.b", "rs1,esb", "op6=0x03 & rs1 & esb", "*:1 esb = rs1:1;")
    ctor("st.s", "rs1,esh", "op6=0x07 & bit0=0 & rs1 & esh", "*:2 esh = rs1:2;")
    ctor("st.l", "rs1,esh", "op6=0x07 & bit0=1 & rs1 & esh", "*:4 esh = rs1;")
    ctor("ixfr", "rs1,fds", "op6=0x02 & rs1 & fds", "fds = rs1;")
    emit()
    emit("# ---- floating-point loads and stores (7.4, 7.5); bits 2-1 select the size ----")
    for I in (0, 1):
        ctor("fld.l", "eafl,fds", f"op6={0x08 + I:#x} & bit1=1 & eafl & fds", "fds = *:4 eafl;")
        ctor("fld.d", "eafd,fdd", f"op6={0x08 + I:#x} & b21=0 & eafd & fdd", "fdd = *:8 eafd;")
        ctor("fld.q", "eafq,fdq", f"op6={0x08 + I:#x} & b21=2 & eafq & fdq", "fdq = *:16 eafq;")
        ctor("fst.l", "fdrs,eafl", f"op6={0x0a + I:#x} & bit1=1 & eafl & fdrs", "*:4 eafl = fdrs;")
        ctor("fst.d", "fdrd,eafd", f"op6={0x0a + I:#x} & b21=0 & eafd & fdrd", "*:8 eafd = fdrd;")
        ctor("fst.q", "fdrq,eafq", f"op6={0x0a + I:#x} & b21=2 & eafq & fdrq", "*:16 eafq = fdrq;")
    emit()
    emit("# ---- pipelined floating-point load (7.4): fdest gets the data of the third previous pfld ----")
    for I in (0, 1):
        ctor("pfld.l", "eafl,fds", f"op6={0x18 + I:#x} & bit1=1 & eafl & fds",
             "local v:4 = *:4 eafl;\nfds = L3:4;\nL3 = L2; L2 = L1; L1 = zext(v);")
        ctor("pfld.d", "eafd,fdd", f"op6={0x18 + I:#x} & b21=0 & eafd & fdd",
             "local v:8 = *:8 eafd;\nfdd = L3:8;\nL3 = L2; L2 = L1; L1 = zext(v);")
        ctor("pfld.q", "eafq,fdq", f"op6={0x18 + I:#x} & b21=2 & eafq & fdq",
             "local v:16 = *:16 eafq;\nfdq = L3;\nL3 = L2; L2 = L1; L1 = v;", ifdef="XP")
    emit()
    emit("# ---- pixel store (7.6): stores the pixels enabled by psr.PM, then shifts PM ----")
    # Byte j of the 64-bit operand belongs to pixel j >> PS (PS 0: 8-bit, 1: 16-bit, 2: 32-bit).
    lines = ["local v:8 = fdrd;", "local old:8 = *:8 eaim;", "local m:8 = 0;",
             "local pm:8 = zext(PM);", "local ps:8 = zext(PS & 3);"]
    for j in range(8):
        lines.append(f"m = m | ((((pm >> ({j} >> ps)) & 1) * 0xff) << {8 * j});")
    lines += ["*:8 eaim = (old & ~m) | (v & m);", "PM = PM >> (8 >> (PS & 3));"]
    ctor("pst.d", "fdrd,eaim", "op6=0x0f & b21=0 & eaim & fdrd", "\n".join(lines))
    emit()
    emit("# ---- cache flush (7.13). The manual requires bits 2-1 to be zero, but GNU as sets bit 2,")
    emit("# ---- so they are ignored here.")
    ctor("flush", "eafl16", "op6=0x0d & eafl16", "flush(eafl16);")
    emit()
    emit("# ---- control registers (7.12) ----")
    cregs = [(0, "fir", None), (1, "psr", None), (2, "dirbase", None), (3, "db", None),
             (4, "fsr", None), (5, "epsr", None), (6, "bear", "XP"), (7, "ccr", "XP"),
             (8, "p0", "XP"), (9, "p1", "XP"), (10, "p2", "XP"), (11, "p3", "XP")]
    for n, name, ifd in cregs:
        if name == "psr":
            ld, st = "psr_read(rd);", "psr_write(rs1);"
        elif name == "epsr":
            ld, st = "epsr_read(rd);", "epsr_write(rs1);"
        elif name in ("fir", "bear"):
            ld, st = f"rd = {name};", None      # not writable by st.c
        else:
            ld, st = f"rd = {name};", f"{name} = rs1;"
        ctor("ld.c", f"\"{name}\",rd", f"op6=0x0c & creg={n} & rd", ld, ifdef=ifd)
        ctor("st.c", f"rs1,\"{name}\"", f"op6=0x0e & creg={n} & rs1", st or "", ifdef=ifd)
    emit()


# ---------------------------------------------------------------------------------------------
# control transfer (7.11)

def branches():
    emit("# ---- control transfer (7.11). Delayed forms execute one more instruction, or one more")
    emit("# ---- pair in dual-instruction mode; call/calli link the address after it in r1.")
    for ctx, ds in ((CTX_SINGLE, 4), (CTX_DUAL, 8)):
        ctor("br", "lbr", f"op6=0x1a & lbr & {ctx}", f"delayslot({ds});\ngoto lbr;")
        ctor("call", "lbr", f"op6=0x1b & lbr & {ctx}", f"r1 = inst_next;\ndelayslot({ds});\ncall lbr;")
        ctor("bc.t", "lbr", f"op6=0x1d & lbr & {ctx}",
             f"if (CC == 0) goto inst_next;\ndelayslot({ds});\ngoto lbr;")
        ctor("bnc.t", "lbr", f"op6=0x1f & lbr & {ctx}",
             f"if (CC != 0) goto inst_next;\ndelayslot({ds});\ngoto lbr;")
        ctor("bri", "rs1", f"op6=0x10 & rs1 & src1=1 & {ctx}",
             f"local t:4 = rs1;\ndelayslot({ds});\nreturn [t];")
        ctor("bri", "rs1", f"op6=0x10 & rs1 & {ctx}",
             f"local t:4 = rs1;\ndelayslot({ds});\ngoto [t];")
        ctor("calli", "rs1", f"op6=0x13 & escop=2 & escrsv=0 & escsz=0 & src2=0 & dest=0 & rs1 & {ctx}",
             f"local t:4 = rs1;\nr1 = inst_next;\ndelayslot({ds});\ncall [t];")
        # bla (7.11): LCC_temp is set when isrc2 + isrc1 >= 0 (signed, exact sum)
        ctor("bla", "rs1,rs2,sbr", f"op6=0x2d & rs1 & rs2 & rs2f & sbr & {ctx}",
             "local a:4 = rs1;\nlocal b:4 = rs2;\nlocal s:4 = a + b;\n"
             "local lt:1 = !((s s< 0) != scarry(a, b));\nrs2f = s;\nlocal go:1 = LCC;\n"
             f"delayslot({ds});\nLCC = lt;\nif (go) goto sbr;")
    for cmp in (0, 1):
        cc = "CCold" if cmp else "CC"
        ctor("bc", "lbr", f"op6=0x1c & lbr & cmpslot={cmp}", f"if ({cc} != 0) goto lbr;")
        ctor("bnc", "lbr", f"op6=0x1e & lbr & cmpslot={cmp}", f"if ({cc} == 0) goto lbr;")
    ctor("btne", "rs1,rs2,sbr", "op6=0x14 & rs1 & rs2 & sbr", "if (rs1 != rs2) goto sbr;")
    ctor("btne", "src1,rs2,sbr", "op6=0x15 & src1 & rs2 & sbr", "if (src1 != rs2) goto sbr;")
    ctor("bte", "rs1,rs2,sbr", "op6=0x16 & rs1 & rs2 & sbr", "if (rs1 == rs2) goto sbr;")
    ctor("bte", "src1,rs2,sbr", "op6=0x17 & src1 & rs2 & sbr", "if (src1 == rs2) goto sbr;")
    emit()
    emit("# ---- traps, bus lock, I/O (7.9, 7.14-7.17). Unused core-escape fields must be zero. ----")
    ctor("trap", "rs1,rs2,rd", "op6=0x11 & rs1 & rs2 & rd", "trap(rs1, rs2);")
    esc = "op6=0x13 & escrsv=0"
    ctor("lock", "", f"{esc} & escop=1 & escsz=0 & src1=0 & src2=0 & dest=0", "lock();")
    ctor("intovr", "", f"{esc} & escop=4 & escsz=0 & src1=0 & src2=0 & dest=0",
         "if (OF == 0) goto inst_next;\noverflow_trap();")
    ctor("unlock", "", f"{esc} & escop=7 & escsz=0 & src1=0 & src2=0 & dest=0", "unlock();")
    for sz, suf, n in ((0, "b", 1), (1, "s", 2), (2, "l", 4)):
        ld = f"rd = sext(*[io]:{n} rs2);" if n < 4 else "rd = *[io]:4 rs2;"
        ctor(f"ldio.{suf}", "rs2,rd", f"{esc} & escop=8 & escsz={sz} & src1=0 & rs2 & rd", ld, ifdef="XP")
        st = f"*[io]:{n} rs2 = rs1:{n};" if n < 4 else "*[io]:4 rs2 = rs1;"
        ctor(f"stio.{suf}", "rs1,rs2", f"{esc} & escop=9 & escsz={sz} & dest=0 & rs1 & rs2", st, ifdef="XP")
        v = "local v:4 = load_interrupt_vector(rs2, {}:1);".format(n)
        ext = f"rd = sext(v:{n});" if n < 4 else "rd = v;"
        ctor(f"ldint.{suf}", "rs2,rd", f"{esc} & escop=10 & escsz={sz} & src1=0 & rs2 & rd",
             v + "\n" + ext, ifdef="XP")
        ctor(f"scyc.{suf}", "rs2", f"{esc} & escop=11 & escsz={sz} & src1=0 & dest=0 & rs2",
             f"special_cycle(rs2, {n}:1);", ifdef="XP")
    emit()


# ---------------------------------------------------------------------------------------------
# floating-point unit (chapter 8)

def fsrc(field, prec):
    """Operand subtable name for a floating-point source field of the given precision."""
    return {("1", "s"): "fs1s", ("1", "d"): "fs1d", ("2", "s"): "fs2s", ("2", "d"): "fs2d"}[(field, prec)]


def fdst(prec):
    return "fds" if prec == "s" else "fdd"


def size(prec):
    return 4 if prec == "s" else 8


def conv(expr, frm, to):
    return expr if frm == to else f"float2float({expr})"


def stage_out(reg, prec):
    """Value of a 64-bit pipeline stage seen as a result of the given precision."""
    return f"{reg}:4" if prec == "s" else reg


def stage_in(var, prec):
    return f"zext({var})" if prec == "s" else var


PSUF = {"ss": (0, 0), "sd": (0, 1), "ds": (1, 0), "dd": (1, 1)}


def fp_ctor(mnem, D, P, S, R, fop, operands, extra, body):
    pre = "d." if D else ""
    pat = f"op6=0x12 & fop={fop:#x} & fP={P} & fD={D}"
    if S is not None:
        pat += f" & fS={S}"
    if R is not None:
        pat += f" & fR={R}"
    if extra:
        pat += " & " + extra
    ctor(pre + mnem, operands, pat, body)


def unit_ops(unit, prec_src, prec_res, P, dest, res):
    """Body tail for a result 'r' entering unit A, M (mul) or G, scalar (P=0) or pipelined."""
    lines = []
    if unit == "A":
        last, shift = "A3", "A3 = A2; A2 = A1; A1 = {};"
    elif unit == "M":
        if prec_src == "s":
            last, shift = "M3", "M3 = M2; M2 = M1; M1 = {};"
        else:
            last, shift = "M2", "M2 = M1; M1 = {};"
    elif unit == "M3":                           # pfmul3.dd: three-stage double multiply
        last, shift = "M3", "M3 = M2; M2 = M1; M1 = {};"
    else:
        last, shift = "G1", "G1 = {};"
    if P:
        # 8.1.3: the result leaving the pipeline is stored first; if fdest is also a source,
        # the stored value is the input operand.
        lines.append(f"local out:{size(prec_res)} = {stage_out(last, prec_res)};")
        lines.append(f"{dest} = out;")
        lines += res
        lines.append(shift.format(stage_in("r", prec_res)))
    else:
        lines += res
        lines.append(f"{dest} = r;")
        lines.append(f"{last} = {stage_in('r', prec_res)};")
    return "\n".join(lines)


def fpu():
    emit("# ---- floating-point multiplier and adder (8.2, 8.3) ----")
    two = [("fmul", 0x20, "f*", "M", ("ss", "sd", "dd")),
           ("fadd", 0x30, "f+", "A", ("ss", "sd", "dd")),
           ("fsub", 0x31, "f-", "A", ("ss", "sd", "dd"))]
    for name, fop, op, unit, precs in two:
        for p in precs:
            S, R = PSUF[p]
            ps, pr = p[0], p[1]
            for P in (0, 1):
                for D in (0, 1):
                    a, b, d = fsrc("1", ps), fsrc("2", ps), fdst(pr)
                    res = [f"local r:{size(pr)} = {conv(a, ps, pr)} {op} {conv(b, ps, pr)};"]
                    body = unit_ops(unit, ps, pr, P, d, res)
                    fp_ctor(("p" if P else "") + f"{name}.{p}", D, P, S, R, fop,
                            f"{a},{b},{d}", f"{a} & {b} & {d}", body)
    # fmlow.dd: low 53 bits of the 106-bit mantissa product, bit 53 = its most significant bit
    for D in (0, 1):
        body = ("local x:8 = fs1d;\nlocal y:8 = fs2d;\n"
                "local hx:8 = zext((x & 0x7ff0000000000000) != 0) << 52;\n"
                "local hy:8 = zext((y & 0x7ff0000000000000) != 0) << 52;\n"
                "local mx:16 = zext((x & 0x000fffffffffffff) | hx);\n"
                "local my:16 = zext((y & 0x000fffffffffffff) | hy);\n"
                "local p:16 = mx * my;\nlocal hi:16 = (p >> 105) & 1;\n"
                "local r:16 = (p & 0x1fffffffffffff) | (hi << 53);\nfdd = r:8;")
        fp_ctor("fmlow.dd", D, 0, 1, 1, 0x21, "fs1d,fs2d,fdd", "fs1d & fs2d & fdd", body)
    # frcp / frsqr: the hardware result is an approximation (mantissa error < 2^-7); the
    # p-code computes the exact reciprocal (or reciprocal square root).
    for name, fop in (("frcp", 0x22), ("frsqr", 0x23)):
        for p in ("ss", "sd", "dd"):
            S, R = PSUF[p]
            ps, pr = p[0], p[1]
            for D in (0, 1):
                b, d = fsrc("2", ps), fdst(pr)
                x = conv(b, ps, pr)
                if name == "frsqr":
                    x = f"sqrt({x})"
                body = f"local one:{size(pr)} = int2float(1:4);\n{d} = one f/ {x};\nM3 = {stage_in(d, pr)};"
                fp_ctor(f"{name}.{p}", D, 0, S, R, fop, f"{b},{d}", f"{b} & {d}", body)
    # pfmul3.dd: three-stage double-precision multiply (pipeline restore in trap handlers)
    for D in (0, 1):
        res = ["local r:8 = fs1d f* fs2d;"]
        body = unit_ops("M3", "d", "d", 1, "fdd", res)
        fp_ctor("pfmul3.dd", D, 1, 1, 1, 0x24, "fs1d,fs2d,fdd", "fs1d & fs2d & fdd", body)
    # fix / ftrunc: double result whose low 32 bits are the integer part
    for name, fop in (("fix", 0x32), ("ftrunc", 0x3a)):
        for p in ("sd", "dd"):
            S, R = PSUF[p]
            ps = p[0]
            for P in (0, 1):
                for D in (0, 1):
                    a = fsrc("1", ps)
                    rnd = f"round({a})" if name == "fix" else a
                    res = [f"local i:4 = trunc({rnd});", "local r:8 = zext(i);"]
                    body = unit_ops("A", ps, "d", P, "fdd", res)
                    fp_ctor(("p" if P else "") + f"{name}.{p}", D, P, S, R, fop,
                            f"{a},fdd", f"{a} & fdd", body)
    # famov: adder move, also the precision conversions fmov.sd / fmov.ds
    for p in ("ss", "sd", "ds", "dd"):
        S, R = PSUF[p]
        ps, pr = p[0], p[1]
        for P in (0, 1):
            for D in (0, 1):
                a, d = fsrc("1", ps), fdst(pr)
                res = [f"local r:{size(pr)} = {conv(a, ps, pr) if ps != pr else a};"]
                body = unit_ops("A", ps, pr, P, d, res)
                fp_ctor(("p" if P else "") + f"famov.{p}", D, P, S, R, 0x33,
                        f"{a},{d}", f"{a} & {d}", body)
    # compares (8.3.2): pipelined only; the first adder stage becomes undefined (zero here).
    # The old CC is kept in CCold for a bc/bnc in the same dual-mode pair.
    cmps = [("pfgt", 0x34, 0, "CC = {a} f> {b};"), ("pfle", 0x34, 1, "CC = !({a} f<= {b});")]
    for name, fop, Rbit, cc in cmps:
        for S, ps in ((0, "s"), (1, "d")):
            for D in (0, 1):
                a, b, d = fsrc("1", ps), fsrc("2", ps), fdst(ps)
                body = (f"local out:{size(ps)} = {stage_out('A3', ps)};\n{d} = out;\nCCold = CC;\n"
                        + cc.format(a=a, b=b) + "\nA3 = A2; A2 = A1; A1 = 0;")
                fp_ctor(f"{name}.{ps}{ps}", D, 1, S, Rbit, fop, f"{a},{b},{d}", f"{a} & {b} & {d}", body)
    # pfeq: like pfgt/pfle the R bit is not a precision bit (GNU as encodes pfeq.dd with R = 0);
    # the source precision S names the instruction.
    for S, ps in ((0, "s"), (1, "d")):
        for D in (0, 1):
            a, b, d = fsrc("1", ps), fsrc("2", ps), fdst(ps)
            body = (f"local out:{size(ps)} = {stage_out('A3', ps)};\n{d} = out;\nCCold = CC;\n"
                    f"CC = {a} f== {b};\nA3 = A2; A2 = A1; A1 = 0;")
            fp_ctor(f"pfeq.{ps}{ps}", D, 1, S, None, 0x35, f"{a},{b},{d}", f"{a} & {b} & {d}", body)
    emit()
    emit("# ---- graphics unit (8.5) ----")
    for D in (0, 1):
        fp_ctor("fxfr", D, 0, None, None, 0x40, "fs1s,rd", "fs1s & rd", "rd = fs1s;\nG1 = zext(fs1s);")
    for name, fop, op in (("fiadd", 0x49, "+"), ("fisub", 0x4d, "-")):
        for p in ("ss", "dd"):
            S, R = PSUF[p]
            pr = p[0]
            for P in (0, 1):
                for D in (0, 1):
                    a, b, d = fsrc("1", pr), fsrc("2", pr), fdst(pr)
                    res = [f"local r:{size(pr)} = {a} {op} {b};"]
                    body = unit_ops("G", pr, pr, P, d, res)
                    fp_ctor(("p" if P else "") + f"{name}.{p}", D, P, S, R, fop,
                            f"{a},{b},{d}", f"{a} & {b} & {d}", body)
    # 64-bit pixel operations. Their S/R bits are not interpreted (the assembler sets both).
    # faddp (table 8-2): MERGE shifts right by 8 (PS 0, 2) or 6 (PS 1), then takes the fields
    # 63..56,47..40,31..24,15..8 (8-bit), 63..58,47..42,31..26,15..10 (16-bit) or 63..56,31..24
    # (32-bit) from the sum.
    faddp = ["local r:8 = fs1d + fs2d;",
             "local q0:8 = zext(PS == 0); local q1:8 = zext(PS == 1); local q2:8 = zext(PS == 2);",
             "local fm:8 = q0 * 0xff00ff00ff00ff00 + q1 * 0xfc00fc00fc00fc00 + q2 * 0xff000000ff000000;",
             "local sh:8 = 8 - 2 * q1;",
             "MERGE = ((MERGE >> sh) & ~fm) | (r & fm);"]
    faddz = ["local r:8 = fs1d + fs2d;",
             "MERGE = ((MERGE >> 16) & 0x0000ffff0000ffff) | (r & 0xffff0000ffff0000);"]
    form = ["local r:8 = fs1d | MERGE;", "MERGE = 0;"]

    def zchk(n):
        w = 64 // n
        mask = (1 << w) - 1
        lines = ["local x:8 = fs1d;", "local y:8 = fs2d;", "local r:8 = 0;",
                 f"local pm:1 = PM >> {n};"]
        for i in range(n):
            lines += [f"local a{i}:8 = (x >> {w * i}) & {mask:#x};",
                      f"local b{i}:8 = (y >> {w * i}) & {mask:#x};",
                      f"local c{i}:1 = b{i} <= a{i};",
                      f"r = r | ((b{i} * zext(c{i}) + a{i} * zext(!c{i})) << {w * i});",
                      f"pm = pm | (c{i} << {i + 8 - n});"]
        lines += ["PM = pm;", "MERGE = 0;"]
        return lines

    for name, fop, res, ops in (("faddp", 0x50, faddp, "fs1d,fs2d,fdd"),
                                ("faddz", 0x51, faddz, "fs1d,fs2d,fdd"),
                                ("fzchkl", 0x57, zchk(2), "fs1d,fs2d,fdd"),
                                ("fzchks", 0x5f, zchk(4), "fs1d,fs2d,fdd"),
                                ("form", 0x5a, form, "fs1d,fdd")):
        for P in (0, 1):
            for D in (0, 1):
                body = unit_ops("G", "d", "d", P, "fdd", list(res))
                pat = " & ".join(ops.split(","))
                fp_ctor(("p" if P else "") + name, D, P, None, None, fop, ops, pat, body)
    emit()
    dual_ops()


# Table 8-1 (data-path control): M-unit op1, M-unit op2, A-unit op1, A-unit op2, T load, K load
DPC = {
    0x0: ("KR", "s2", "s1", "M", 0, 0), 0x1: ("KR", "s2", "T", "M", 0, 1),
    0x2: ("KR", "s2", "s1", "A", 1, 0), 0x3: ("KR", "s2", "T", "A", 1, 1),
    0x4: ("KI", "s2", "s1", "M", 0, 0), 0x5: ("KI", "s2", "T", "M", 0, 1),
    0x6: ("KI", "s2", "s1", "A", 1, 0), 0x7: ("KI", "s2", "T", "A", 1, 1),
    0x8: ("KR", "A", "s1", "s2", 1, 0), 0x9: ("s1", "s2", "A", "M", 0, 0),
    0xa: ("KR", "A", "s1", "s2", 0, 0), 0xb: ("s1", "s2", "T", "A", 1, 0),
    0xc: ("KI", "A", "s1", "s2", 1, 0), 0xd: ("s1", "s2", "T", "M", 0, 0),
    0xe: ("KI", "A", "s1", "s2", 0, 0), 0xf: ("s1", "s2", "T", "A", 0, 0),
}
DPCM = {  # PFMAM/PFMSM: "A result" inputs become "M result"; 0xf is reserved
    0x0: ("KR", "s2", "s1", "M", 0, 0), 0x1: ("KR", "s2", "T", "M", 0, 1),
    0x2: ("KR", "s2", "s1", "M", 1, 0), 0x3: ("KR", "s2", "T", "M", 1, 1),
    0x4: ("KI", "s2", "s1", "M", 0, 0), 0x5: ("KI", "s2", "T", "M", 0, 1),
    0x6: ("KI", "s2", "s1", "M", 1, 0), 0x7: ("KI", "s2", "T", "M", 1, 1),
    0x8: ("KR", "M", "s1", "s2", 1, 0), 0x9: ("s1", "s2", "M", "M", 0, 0),
    0xa: ("KR", "M", "s1", "s2", 0, 0), 0xb: ("s1", "s2", "T", "M", 1, 0),
    0xc: ("KI", "M", "s1", "s2", 1, 0), 0xd: ("s1", "s2", "T", "M", 0, 0),
    0xe: ("KI", "M", "s1", "s2", 0, 0),
}
NAMES_AM = ["r2p1", "r2pt", "r2ap1", "r2apt", "i2p1", "i2pt", "i2ap1", "i2apt",
            "rat1p2", "m12apm", "ra1p2", "m12ttpa", "iat1p2", "m12tpm", "ia1p2", "m12tpa"]
NAMES_SM = ["r2s1", "r2st", "r2as1", "r2ast", "i2s1", "i2st", "i2as1", "i2ast",
            "rat1s2", "m12asm", "ra1s2", "m12ttsa", "iat1s2", "m12tsm", "ia1s2", "m12tsa"]
NAMES_MAM = ["mr2p1", "mr2pt", "mr2mp1", "mr2mpt", "mi2p1", "mi2pt", "mi2mp1", "mi2mpt",
             "mrmt1p2", "mm12mpm", "mrm1p2", "mm12ttpm", "mimt1p2", "mm12tpm", "mim1p2", None]
NAMES_MSM = ["mr2s1", "mr2st", "mr2ms1", "mr2mst", "mi2s1", "mi2st", "mi2ms1", "mi2mst",
             "mrmt1s2", "mm12msm", "mrm1s2", "mm12ttsm", "mimt1s2", "mm12tsm", "mim1s2", None]


def dual_ops():
    emit("# ---- dual-operation instructions (8.4): pfam/pfsm (P=1, fdest gets the adder result)")
    emit("# ---- and pfmam/pfmsm (P=0, fdest gets the multiplier result). .p's source precision")
    emit("# ---- applies to the multiplication; its result precision to the addition and all results.")
    for P, sub, names, table in ((1, 0, NAMES_AM, DPC), (1, 1, NAMES_SM, DPC),
                                 (0, 0, NAMES_MAM, DPCM), (0, 1, NAMES_MSM, DPCM)):
        for dpc in range(16):
            name = names[dpc]
            if name is None:
                continue
            mop1, mop2, aop1, aop2, tload, kload = table[dpc]
            for p in ("ss", "sd", "dd"):
                S, R = PSUF[p]
                ps, pr = p[0], p[1]
                mlast = "M3" if ps == "s" else "M2"
                # display: src1 and src2 in the precision of the unit that uses them
                s1p = ps if (mop1 == "s1" or kload) else pr
                s2p = ps if mop2 == "s2" else pr
                s1, s2, d = fsrc("1", s1p), fsrc("2", s2p), fdst(pr)
                lines = [f"local alast:{size(pr)} = {stage_out('A3', pr)};",
                         f"local mlast:{size(pr)} = {stage_out(mlast, pr)};",
                         f"{d} = {'alast' if P else 'mlast'};"]
                # M-unit operand 1
                if kload:
                    lines.append(f"{mop1} = {stage_in(s1, ps)};")
                    m1 = s1
                elif mop1 in ("KR", "KI"):
                    m1 = stage_out(mop1, ps)
                else:
                    m1 = s1
                # M-unit operand 2
                if mop2 == "s2":
                    m2 = s2
                else:
                    src = "alast" if mop2 == "A" else "mlast"
                    if ps == pr:
                        m2 = src
                    else:
                        lines.append(f"local m2v:{size(ps)} = float2float({src});")
                        m2 = "m2v"
                # A-unit operands
                aval = {"s1": s1, "s2": s2, "T": stage_out("T", pr), "A": "alast", "M": "mlast"}
                a1, a2 = aval[aop1], aval[aop2]
                lines.append(f"local mr:{size(pr)} = {conv(m1, ps, pr)} f* {conv(m2, ps, pr)};")
                lines.append(f"local ar:{size(pr)} = {a1} {'f-' if sub else 'f+'} {a2};")
                if tload:
                    lines.append(f"T = {stage_in('mlast', pr)};")
                lines.append("A3 = A2; A2 = A1; A1 = " + stage_in("ar", pr) + ";")
                if ps == "s":
                    lines.append("M3 = M2; M2 = M1; M1 = " + stage_in("mr", pr) + ";")
                else:
                    lines.append("M2 = M1; M1 = " + stage_in("mr", pr) + ";")
                for D in (0, 1):
                    fop = (sub << 4) | dpc
                    fp_ctor(f"{name}.{p}", D, P, S, R, fop, f"{s1},{s2},{d}",
                            f"{s1} & {s2} & {d}", "\n".join(lines))
    emit()


def main():
    emit("# Generated by tools/gen_i860.py -- do not edit.")
    emit()
    addr_operands()
    alu()
    loadstore()
    branches()
    fpu()
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
