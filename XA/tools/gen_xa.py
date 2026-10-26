#!/usr/bin/env python3
"""Generate data/languages/xa_gen.sinc: XA direct-address operand tables and the regular
instruction groups (ALU, MOV, immediates, ADDS/MOVS, XCH, shifts and rotates, multiply and
divide, CJNE/DJNZ, PUSH/POP).

Source: Philips "XA User Guide" (1998), chapter 6 (addressing modes, instruction encodings and
operations) and chapter 3 (SFR and bit address spaces). Nothing here is taken from another
disassembler's source.

    python3 tools/gen_xa.py > data/languages/xa_gen.sinc
"""

import re

out = []
w = out.append

ALU = ["ADD", "ADDC", "SUB", "SUBB", "CMP", "AND", "OR", "XOR", "MOV"]
SFX = {1: "b", 2: "w"}
MASK = {1: 0xff, 2: 0xffff}

# core SFRs that are registers in this module: byte address -> register
SFR_REG = {0x400: "PSWL", 0x401: "PSWH", 0x402: "PSW51", 0x403: "SSEL",
           0x440: "SCR", 0x441: "DS", 0x442: "ES", 0x443: "CS"}
# word accesses use the even address (user guide 3.3.1)
SFR_REG2 = {0x400: "PSW", 0x402: "PSW51_SSEL", 0x440: "SCR_DS", 0x442: "ES_CS"}

# direct operand positions: (name, high-bits field, pattern before the low byte, low field)
DIRPOS = {
    "L": ("lo3", "lo3 ; xa8", "xa8"),       # byte 2 bits 2-0, byte 3
    "H": ("hi3", "hi3 ; xa8", "xa8"),       # byte 2 bits 6-4, byte 3
    "S": ("lo3", "lo3 ; xa8 ; xb8", "xb8"),  # byte 2 bits 2-0, byte 4 (MOV direct,direct source)
}


def dir_tables():
    w("# ---------------------------------------------------------------- direct operands")
    w("# 11-bit direct address: 000h-3FFh data memory in the DS segment, 400h-7FFh SFRs")
    for pos, (hf, pre, lf) in DIRPOS.items():
        for size in (1, 2):
            n = f"dir{size}_{pos}"
            pat_hi = pre.replace(hf, f"{hf}<4 & {hf}", 1)
            w(f"{n}: a is {pat_hi} & dsk=1 & dsv [ a = ({hf} << 8) | {lf}; ] "
              f"{{ local ea:3 = (dsv << 16) | a; export *[data]:{size} ea; }}")
            w(f"{n}: a is {pat_hi} & dsk=0 [ a = ({hf} << 8) | {lf}; ] "
              f"{{ local ea:3 = segment(DS, a:2); export *[data]:{size} ea; }}")
            pat_sfr = pre.replace(hf, f"{hf}>=4 & {hf}", 1)
            w(f"{n}: a is {pat_sfr} [ a = ({hf} << 8) | {lf}; ] {{ export *[sfr]:{size} a; }}")
            regs = SFR_REG if size == 1 else {a: SFR_REG2[a & ~1] for a in SFR_REG}
            for a, r in sorted(regs.items()):
                pat = pre.replace(hf, f"{hf}={a >> 8}", 1).replace(lf, f"{lf}=0x{a & 0xff:02x}")
                pk = "packflags(); " if a in (0x400, 0x401) and (size == 2 or a == 0x400) else ""
                w(f'{n}: "{SFR_REG[a]}" is {pat} {{ {pk}export {r}; }}')
            if pos == "S":
                continue
            # after a write: reload the flags from PSWL, forget a tracked DS
            p = f"dpost{size}_{pos}"
            w(f"{p}: is {pre} {{ }}")
            for a in (0x400, 0x401) if size == 2 else (0x400,):
                pat = pre.replace(hf, f"{hf}={a >> 8}", 1).replace(lf, f"{lf}=0x{a & 0xff:02x}")
                w(f"{p}: is {pat} {{ unpackflags(); }}")
            for a in (0x440, 0x441) if size == 2 else (0x441,):
                pat = pre.replace(hf, f"{hf}={a >> 8}", 1).replace(lf, f"{lf}=0x{a & 0xff:02x}")
                w(f"{p}: is {pat} [ dsk = 0; globalset(inst_next, dsk); ] {{ }}")
    w("")


def ind_tables():
    """Indirect data operands through a 3-bit pointer field (pd: bits 6-4, ps: bits 2-0)."""
    w("# ---------------------------------------------------------------- indirect operands")
    w('o8: "+"^xa8 is xa8hi=0 & xa8 { }')
    w('o8: "-"^n is xa8hi=1 & xa8s [ n = -xa8s; ] { }')
    w('o16: "+"^xa16 is xa16hi=0 & xa16 { }')
    w('o16: "-"^n is xa16hi=1 & xa16s [ n = -xa16s; ] { }')
    for f in ("pd", "ps"):
        for size in (1, 2):
            w(f'ind{size}_{f}: "["^{f}^"]" is {f} & dseg_{f} '
              f'{{ local a:3 = segment(dseg_{f}, {f}); export *[data]:{size} a; }}')
            w(f'inc{size}_{f}: "["^{f}^"+]" is {f} & dseg_{f} '
              f'{{ local a:3 = segment(dseg_{f}, {f}); export *[data]:{size} a; }}')
            w(f'off8_{size}_{f}: "["^{f}^o8^"]" is {f} & dseg_{f} ; o8 & xa8s '
              f'{{ local o:2 = {f} + xa8s; local a:3 = segment(dseg_{f}, o); export *[data]:{size} a; }}')
            w(f'off16_{size}_{f}: "["^{f}^o16^"]" is {f} & dseg_{f} ; o16 & xa16 '
              f'{{ local o:2 = {f} + xa16; local a:3 = segment(dseg_{f}, o); export *[data]:{size} a; }}')
    w("")


def op_body(op, size, d, s):
    """P-code for dest d (op) source s; returns the statements (no trailing write hook)."""
    t = size
    cin = "C" if size == 1 else "zext(C)"
    if op == "MOV":
        return f"local v:{t} = {s}; {d} = v; nz(v);"
    if op in ("AND", "OR", "XOR"):
        sym = {"AND": "&", "OR": "|", "XOR": "^"}[op]
        return f"local r:{t} = {d} {sym} {s}; {d} = r; nz(r);"
    pre = f"local a:{t} = {d}; local b:{t} = {s};"
    if op == "ADD":
        return f"{pre} local r:{t} = a + b; addflags(a, b, r); {d} = r;"
    if op == "ADDC":
        return f"{pre} local c:{t} = {cin}; local r:{t} = a + b + c; addcflags(a, b, c, r); {d} = r;"
    if op == "SUB":
        return f"{pre} local r:{t} = a - b; subflags(a, b, r); {d} = r;"
    if op == "SUBB":
        return f"{pre} local c:{t} = {cin}; local r:{t} = a - b - c; subbflags(a, b, c, r); {d} = r;"
    if op == "CMP":
        return f"{pre} local r:{t} = a - b; subflags(a, b, r);"
    raise ValueError(op)


MULTI = re.compile(r"^(off8_|off16_|dir\d_[LH]$|dpost|bitloc|bitnum)")
TRIPLE = re.compile(r"^dir\d_S$")


def fixpat(pat):
    """Patterns that AND byte-2 fields with operand tables spanning later bytes need the
    ellipsis operator: (fields) ... & table."""
    act = ""
    if "[" in pat:
        pat, act = pat[:pat.index("[")].rstrip(), " " + pat[pat.index("["):]
    segs = pat.split(" ; ")
    for i, seg in enumerate(segs):
        if "..." in seg:
            continue
        atoms = seg.split(" & ")
        two = [a for a in atoms if MULTI.match(a)]
        three = [a for a in atoms if TRIPLE.match(a)]
        if not two and not three:
            continue
        one = [a for a in atoms if a not in two and a not in three]
        e = " & ".join(one)
        if two:
            e = f"({e}) ... & " + " & ".join(two) if e else " & ".join(two)
        if three:
            e = f"({e}) ... & " + " & ".join(three)
        segs[i] = e
    return " ; ".join(segs) + act


def con(mnem, ops, pat, body):
    pat = fixpat(pat)
    w(f":{mnem} {ops} is {pat} {{ {body} }}" if ops else f":{mnem} is {pat} {{ {body} }}")


def alu_group():
    w("# ---------------------------------------------------------------- ALU and MOV, register forms")
    for n, op in enumerate(ALU):
        for size in (1, 2):
            szb = size - 1
            m = f"{op}.{SFX[size]}"
            rd = "rdb" if size == 1 else "rdw"
            rs = "rsb" if size == 1 else "rsw"
            base = f"opn={n} & sz={szb}"
            # Rd, Rs
            con(m, f"{rd}, {rs}", f"{base} & mode=1 ; {rd} & {rs}", op_body(op, size, rd, rs))
            # Rd, [Rs] / [Rd], Rs
            ind = f"ind{size}_ps"
            con(m, f"{rd}, {ind}", f"{base} & mode=2 ; {rd} & b3=0 & {ind}", op_body(op, size, rd, ind))
            con(m, f"{ind}, {rd}", f"{base} & mode=2 ; {rd} & b3=1 & {ind}", op_body(op, size, ind, rd))
            # Rd, [Rs+] / [Rd+], Rs
            inc = f"inc{size}_ps"
            con(m, f"{rd}, {inc}", f"{base} & mode=3 ; {rd} & b3=0 & ps & {inc}",
                op_body(op, size, rd, inc) + f" ps = ps + {size};")
            con(m, f"{inc}, {rd}", f"{base} & mode=3 ; {rd} & b3=1 & ps & {inc}",
                op_body(op, size, inc, rd) + f" ps = ps + {size};")
            # offsets
            for mode, tab in ((4, f"off8_{size}_ps"), (5, f"off16_{size}_ps")):
                con(m, f"{rd}, {tab}", f"{base} & mode={mode} ; {rd} & b3=0 & {tab}",
                    op_body(op, size, rd, tab))
                con(m, f"{tab}, {rd}", f"{base} & mode={mode} ; {rd} & b3=1 & {tab}",
                    op_body(op, size, tab, rd))
            # direct
            dr = f"dir{size}_L"
            dp = f"dpost{size}_L"
            con(m, f"{rd}, {dr}", f"{base} & mode=6 ; {rd} & b3=0 & {dr}", op_body(op, size, rd, dr))
            post = f" build {dp};" if op != "CMP" else ""
            con(m, f"{dr}, {rd}", f"{base} & mode=6 ; {rd} & b3=1 & {dr} & {dp}",
                op_body(op, size, dr, rd) + post)
    w("")


def imm_group():
    w("# ---------------------------------------------------------------- ALU and MOV, immediate source")
    for n, op in enumerate(ALU):
        for size in (1, 2):
            szb = size - 1
            m = f"{op}.{SFX[size]}"
            rd = "rdb" if size == 1 else "rdw"
            # immediate token for each destination form
            if size == 1:
                i_plain, i_off8, i_off16, i_dir = ("xa8", "xa8"), ("xb8", "xb8"), ("xb8", "xb8"), ("xb8", "xb8")
            else:
                i_plain, i_off8, i_off16, i_dir = ("xa16", "xa16"), ("xa16", "xa16"), ("xb16", "xb16"), ("xa16", "xa16")
            base = f"op={0x90 | (szb << 3)}"
            post = lambda dp: f" build {dp};" if op != "CMP" else ""

            def c(mode, dst, b2pat, tail, imm, extra=""):
                body = op_body(op, size, dst, imm[1]) + extra
                con(m, f"{dst}, \"#\"^{imm[0]}",
                    f"op={0x90 | (szb << 3) | mode} ; {b2pat} & lo4={n}{tail}", body)

            c(1, rd, f"{rd}", f" ; {i_plain[0]}", i_plain)
            c(2, f"ind{size}_pd", f"b7=0 & ind{size}_pd", f" ; {i_plain[0]}", i_plain)
            c(3, f"inc{size}_pd", f"b7=0 & pd & inc{size}_pd", f" ; {i_plain[0]}", i_plain,
              f" pd = pd + {size};")
            # offset forms: the offset token follows byte 2, then the immediate
            con(m, f"off8_{size}_pd, \"#\"^{i_off8[0]}",
                f"op={0x94 | (szb << 3)} ; b7=0 & lo4={n} & off8_{size}_pd ; {i_off8[0]}",
                op_body(op, size, f"off8_{size}_pd", i_off8[1]))
            con(m, f"off16_{size}_pd, \"#\"^{i_off16[0]}",
                f"op={0x95 | (szb << 3)} ; b7=0 & lo4={n} & off16_{size}_pd ; {i_off16[0]}",
                op_body(op, size, f"off16_{size}_pd", i_off16[1]))
            dr, dp = f"dir{size}_H", f"dpost{size}_H"
            con(m, f"{dr}, \"#\"^{i_dir[0]}",
                f"op={0x96 | (szb << 3)} ; b7=0 & lo4={n} & {dr} & {dp} ; {i_dir[0]}",
                op_body(op, size, dr, i_dir[1]) + post(dp))
    # MOV.b DS,#data8 sets the tracked DS value
    w(':MOV.b "DS", "#"^xb8 is op=0x96 ; b7=0 & hi3=4 & lo4=8 ; xa8=0x41 ; xb8 '
      '[ dsv = xb8; dsk = 1; globalset(inst_next, dsv); globalset(inst_next, dsk); ] '
      '{ DS = xb8; nz(DS); }')
    w("")


def short_group():
    w("# ---------------------------------------------------------------- ADDS / MOVS (4-bit signed immediate)")
    for name, hi in (("ADDS", 0xa0), ("MOVS", 0xb0)):
        for size in (1, 2):
            szb = size - 1
            m = f"{name}.{SFX[size]}"
            rd = "rdb" if size == 1 else "rdw"
            imm = f'"#"^v'
            act = f"[ v = simm4 & {MASK[size]:#x}; ]"
            t = size

            def body(d):
                if name == "ADDS":
                    return f"local r:{t} = {d} + {'simm4' if size == 1 else 'simm4'}; {d} = r; nz(r);"
                return f"local r:{t} = simm4; {d} = r; nz(r);"
            base = hi | (szb << 3)
            con(m, f"{rd}, {imm}", f"op={base | 1} ; {rd} & simm4 {act}", body(rd))
            con(m, f"ind{size}_pd, {imm}", f"op={base | 2} ; b7=0 & ind{size}_pd & simm4 {act}",
                body(f"ind{size}_pd"))
            con(m, f"inc{size}_pd, {imm}", f"op={base | 3} ; b7=0 & pd & inc{size}_pd & simm4 {act}",
                body(f"inc{size}_pd") + f" pd = pd + {size};")
            con(m, f"off8_{size}_pd, {imm}", f"op={base | 4} ; b7=0 & simm4 & off8_{size}_pd {act}",
                body(f"off8_{size}_pd"))
            con(m, f"off16_{size}_pd, {imm}", f"op={base | 5} ; b7=0 & simm4 & off16_{size}_pd {act}",
                body(f"off16_{size}_pd"))
            dr, dp = f"dir{size}_H", f"dpost{size}_H"
            con(m, f"{dr}, {imm}", f"op={base | 6} ; b7=0 & simm4 & {dr} & {dp} {act}",
                body(dr) + f" build {dp};")
    w(':MOVS.b "DS", "#"^v is op=0xb6 ; hi3=4 & b7=0 & simm4 ; xa8=0x41 '
      '[ v = simm4 & 0xff; dsv = simm4 & 0xff; dsk = 1; globalset(inst_next, dsv); globalset(inst_next, dsk); ] '
      '{ DS = simm4; nz(DS); }')
    w("")


def misc_moves():
    w("# ---------------------------------------------------------------- other data moves")
    for size in (1, 2):
        szb = size - 1
        sx = SFX[size]
        rd = "rdb" if size == 1 else "rdw"
        rs = "rsb" if size == 1 else "rsw"
        t = size
        # XCH
        con(f"XCH.{sx}", f"{rd}, {rs}", f"op={0x60 | (szb << 3)} ; {rd} & {rs}",
            f"local v:{t} = {rd}; {rd} = {rs}; {rs} = v;")
        con(f"XCH.{sx}", f"{rd}, ind{size}_ps", f"op={0x50 | (szb << 3)} ; {rd} & b3=0 & ind{size}_ps",
            f"local v:{t} = {rd}; {rd} = ind{size}_ps; ind{size}_ps = v;")
        con(f"XCH.{sx}", f"{rd}, dir{size}_L",
            f"op={0xa0 | (szb << 3)} ; {rd} & b3=1 & dir{size}_L & dpost{size}_L",
            f"local v:{t} = {rd}; {rd} = dir{size}_L; dir{size}_L = v; build dpost{size}_L;")
        # MOV [Rd],direct and MOV direct,[Rs]: pointer in bits 6-4
        con(f"MOV.{sx}", f"ind{size}_pd, dir{size}_L",
            f"op={0xa0 | (szb << 3)} ; b7=0 & b3=0 & ind{size}_pd & dir{size}_L",
            f"local v:{t} = dir{size}_L; ind{size}_pd = v; nz(v);")
        con(f"MOV.{sx}", f"dir{size}_L, ind{size}_pd",
            f"op={0xa0 | (szb << 3)} ; b7=1 & b3=0 & ind{size}_pd & dir{size}_L & dpost{size}_L",
            f"local v:{t} = ind{size}_pd; dir{size}_L = v; nz(v); build dpost{size}_L;")
        # MOV direct,direct
        con(f"MOV.{sx}", f"dir{size}_H, dir{size}_S",
            f"op={0x97 | (szb << 3)} ; b7=0 & b3=0 & dir{size}_H & dir{size}_S & dpost{size}_H",
            f"local v:{t} = dir{size}_S; dir{size}_H = v; nz(v); build dpost{size}_H;")
        # MOV [Rd+],[Rs+]
        con(f"MOV.{sx}", f"inc{size}_pd, inc{size}_ps",
            f"op={0x90 | (szb << 3)} ; b7=0 & b3=0 & pd & ps & inc{size}_pd & inc{size}_ps",
            f"local v:{t} = inc{size}_ps; inc{size}_pd = v; nz(v); pd = pd + {size}; ps = ps + {size};")
        # MOVC Rd,[Rs+]: code memory, segment PC[23:16] or CS
        con(f"MOVC.{sx}", f"{rd}, \"[\"^ps^\"+]\"",
            f"op={0x80 | (szb << 3)} ; {rd} & b3=0 & ps & cseg_ps",
            f"local a:3 = (zext(cseg_ps) << 16) | zext(ps); local v:{t} = *[code]:{t} a; {rd} = v; nz(v); ps = ps + {size};")
        # MOVX: external data, segment 0
        con(f"MOVX.{sx}", f"{rd}, \"[\"^ps^\"]\"", f"op={0xa7 | (szb << 3)} ; {rd} & b3=0 & ps",
            f"local a:3 = segment(0:1, ps); local v:{t} = *[data]:{t} a; {rd} = v; nz(v);")
        con(f"MOVX.{sx}", f"\"[\"^ps^\"]\", {rd}", f"op={0xa7 | (szb << 3)} ; {rd} & b3=1 & ps",
            f"local a:3 = segment(0:1, ps); local v:{t} = {rd}; *[data]:{t} a = v; nz(v);")
    # LEA
    con("LEA", "pd, ps^o8", "op=0x40 ; b7=0 & b3=0 & pd & ps ; o8 & xa8s", "pd = ps + xa8s;")
    con("LEA", "pd, ps^o16", "op=0x48 ; b7=0 & b3=0 & pd & ps ; o16 & xa16", "pd = ps + xa16;")
    # USP
    w(':MOV rdw, "USP" is op=0x90 ; rdw & lo4=0xf { rdw = USP; nz(rdw); }')
    w(':MOV "USP", rdw is op=0x98 ; rdw & lo4=0xf { USP = rdw; nz(rdw); }')
    # 80C51-compatible MOVC (A = R4L, DPTR = R6)
    w(':MOVC "A", "[A+DPTR]" is op=0x90 ; b2=0x4e { local a:3 = (inst_next & 0xff0000) | zext(zext(R4L) + R6); R4L = *[code]:1 a; nz(R4L); }')
    w(':MOVC "A", "[A+PC]" is op=0x90 ; b2=0x4c { local pc:3 = inst_next; local a:3 = (inst_next & 0xff0000) | zext(zext(R4L) + pc:2); R4L = *[code]:1 a; nz(R4L); }')
    w("")


def unary_group():
    w("# ---------------------------------------------------------------- DA, SEXT, CPL, NEG")
    w(":DA rdb is op=0x90 ; rdb & lo4=8 {\n"
      "\tlocal v:1 = rdb;\n"
      "\tlocal lo:1 = ((v & 0xf) > 9) || (AC != 0);\n"
      "\tlocal t:2 = zext(v) + zext(lo * 6);\n"
      "\tlocal c:1 = (C != 0) || (t > 0xff);\n"
      "\tv = t:1;\n"
      "\tlocal hi:1 = ((v >> 4) > 9) || c;\n"
      "\tt = zext(v) + zext(hi * 0x60);\n"
      "\tC = c || (t > 0xff);\n"
      "\tv = t:1;\n"
      "\trdb = v;\n"
      "\tnz(v);\n}")
    for size in (1, 2):
        szb = size - 1
        sx = SFX[size]
        rd = "rdb" if size == 1 else "rdw"
        t = size
        o = 0x90 | (szb << 3)
        w(f":SEXT.{sx} {rd} is op={o} ; {rd} & lo4=9 {{ {rd} = 0 - zext(N); }}" if size == 2 else
          f":SEXT.{sx} {rd} is op={o} ; {rd} & lo4=9 {{ {rd} = 0 - N; }}")
        w(f":CPL.{sx} {rd} is op={o} ; {rd} & lo4=0xa {{ {rd} = ~{rd}; nz({rd}); }}")
        w(f":NEG.{sx} {rd} is op={o} ; {rd} & lo4=0xb {{ local a:{t} = {rd}; V = a == {1 << (8 * t - 1):#x}; {rd} = -a; nz({rd}); }}")
    w("")


def shift_group():
    w("# ---------------------------------------------------------------- shifts, rotates, NORM")
    # (size bytes, dest field, display) per SZ1/SZ0
    sizes = {0: (1, "rdb", "b"), 2: (2, "rdw", "w"), 3: (4, "rdd", "d")}

    def shbody(kind, t, d, cnt, const=False):
        bits = 8 * t
        if const or t == 1:
            n = f"local n:{t} = {cnt};"
        else:
            n = f"local n:{t} = zext({cnt});"
        if kind == "LSR":
            return (f"local x:{t} = {d}; {n} "
                    f"if (n == 0) goto <z>; local cb:{t} = x >> (n - 1); C = cb:1 & 1; x = x >> n; {d} = x; <z> nz(x);")
        if kind == "ASR":
            return (f"local x:{t} = {d}; {n} "
                    f"if (n == 0) goto <z>; local cb:{t} = x s>> (n - 1); C = cb:1 & 1; x = x s>> n; {d} = x; <z> nz(x);")
        if kind == "ASL":
            return (f"local x:{t} = {d}; {n} V = 0; "
                    f"if (n == 0) goto <z>; local cb:{t} = (x << (n - 1)) >> {bits - 1}; C = cb:1; "
                    f"V = ((x << n) s>> n) != x; x = x << n; {d} = x; <z> nz(x);")
        raise ValueError(kind)

    for code, (t, rd, sx) in sizes.items():
        disp = "rddn" if t == 4 else rd
        pat_d = "rdd & rddn" if t == 4 else rd
        for sopv, kind in ((0, "LSR"), (1, "ASL"), (2, "ASR")):
            # count in a byte register (5 bits used)
            con(f"{kind}.{sx}", f"{disp}, rsb", f"op={0xc0 | (code << 2) | sopv} ; {pat_d} & rsb",
                shbody(kind, t, rd, "(rsb & 31)"))
            # immediate count: 4 bits (byte, word), 5 bits (double word)
            if t == 4:
                con(f"{kind}.{sx}", f"pddn, \"#\"^imm5", f"op={0xd0 | (code << 2) | sopv} ; pdd & pddn & imm5",
                    shbody(kind, t, "pdd", "imm5", True))
            else:
                con(f"{kind}.{sx}", f"{rd}, \"#\"^imm4", f"op={0xd0 | (code << 2) | sopv} ; {rd} & imm4",
                    shbody(kind, t, rd, "imm4", True))
        # NORM: shift left until the MSB is set, count to the byte register
        con(f"NORM.{sx}", f"{disp}, rsb", f"op={0xc3 | (code << 2)} ; {pat_d} & rsb",
            f"local x:{t} = {rd}; local n:{t} = 0; if (x == 0) goto <z>; n = lzcount(x); x = x << n; "
            f"<z> {rd} = x; rsb = n:1; nz(x);")
    # rotates by #data4 (0-15), byte and word
    for size in (1, 2):
        szb = size - 1
        sx = SFX[size]
        rd = "rdb" if size == 1 else "rdw"
        bits = 8 * size
        t = size
        con(f"RR.{sx}", f"{rd}, \"#\"^imm4", f"op={0xb0 | (szb << 3)} ; {rd} & imm4",
            f"local x:{t} = {rd}; local n:{t} = imm4 % {bits}; x = (x >> n) | (x << ({bits} - n)); {rd} = x; nz(x);")
        con(f"RL.{sx}", f"{rd}, \"#\"^imm4", f"op={0xd3 | (szb << 3)} ; {rd} & imm4",
            f"local x:{t} = {rd}; local n:{t} = imm4 % {bits}; x = (x << n) | (x >> ({bits} - n)); {rd} = x; nz(x);")
        # through carry: rotate the (bits+1)-bit value C:x
        con(f"RRC.{sx}", f"{rd}, \"#\"^imm4", f"op={0xb7 | (szb << 3)} ; {rd} & imm4",
            f"local v:4 = (zext(C) << {bits}) | zext({rd}); local n:4 = imm4 % {bits + 1}; "
            f"v = ((v >> n) | (v << ({bits + 1} - n))) & {(1 << (bits + 1)) - 1:#x}; "
            f"{rd} = v:{t}; local cy:4 = v >> {bits}; C = cy:1; nz({rd});")
        con(f"RLC.{sx}", f"{rd}, \"#\"^imm4", f"op={0xd7 | (szb << 3)} ; {rd} & imm4",
            f"local v:4 = (zext(C) << {bits}) | zext({rd}); local n:4 = imm4 % {bits + 1}; "
            f"v = ((v << n) | (v >> ({bits + 1} - n))) & {(1 << (bits + 1)) - 1:#x}; "
            f"{rd} = v:{t}; local cy:4 = v >> {bits}; C = cy:1; nz({rd});")
    w("")


def muldiv_group():
    w("# ---------------------------------------------------------------- multiply and divide")

    def mulu_b(src):
        return (f"local s:1 = {src}; local p:2 = zext(rdb) * zext(s); rdb = p:1; rdb1 = p(1); "
                f"C = 0; V = p > 0xff; nz(p);")

    def mulu_w(src):
        return (f"local s:2 = {src}; local p:4 = zext(rdw) * zext(s); rdw = p:2; rdw1 = p(2); "
                f"C = 0; V = p > 0xffff; nz(p);")

    def mul_w(src):
        return (f"local s:2 = {src}; local p:4 = sext(rdw) * sext(s); rdw = p:2; rdw1 = p(2); "
                f"C = 0; V = sext(p:2) != p; nz(p);")

    def divguard(src, size, body):
        return (f"local dv:{size} = {src}; if (dv != 0) goto <ok>; C = 0; V = 1; divide_by_zero(); goto inst_next; "
                f"<ok> {body}")

    def divu_b(src):
        return divguard(src, 1, "local q:1 = rdb / dv; local r:1 = rdb % dv; rdb = q; rdb1 = r; C = 0; V = 0; nz(q);")

    def divu_w(src):
        return divguard(src, 1, "local x:2 = rdw; local d2:2 = zext(dv); local q:2 = x / d2; local r:2 = x % d2; "
                                "rdw = (r << 8) | (q & 0xff); C = 0; V = q > 0xff; local q1:1 = q:1; nz(q1);")

    def div_w(src):
        return divguard(src, 1, "local x:2 = rdw; local d2:2 = sext(dv); local q:2 = x s/ d2; local r:2 = x s% d2; "
                                "rdw = (r << 8) | (q & 0xff); C = 0; local q1:1 = q:1; V = sext(q1) != q; nz(q1);")

    def divu_d(src):
        return divguard(src, 2, "local x:4 = pdd; local d4:4 = zext(dv); local q:4 = x / d4; local r:4 = x % d4; "
                                "pdd = (r << 16) | (q & 0xffff); C = 0; V = q > 0xffff; local q2:2 = q:2; nz(q2);")

    def div_d(src):
        return divguard(src, 2, "local x:4 = pdd; local d4:4 = sext(dv); local q:4 = x s/ d4; local r:4 = x s% d4; "
                                "pdd = (r << 16) | (q & 0xffff); C = 0; local q2:2 = q:2; V = sext(q2) != q; nz(q2);")

    con("MULU.b", "rdb, rsb", "op=0xe0 ; rdb & rdb1 & rsb", mulu_b("rsb"))
    con("MULU.w", "rdw, rsw", "op=0xe4 ; rdw & rdw1 & rsw", mulu_w("rsw"))
    con("MUL.w", "rdw, rsw", "op=0xe6 ; rdw & rdw1 & rsw", mul_w("rsw"))
    con("DIVU.b", "rdb, rsb", "op=0xe1 ; rdb & rdb1 & rsb", divu_b("rsb"))
    con("DIVU.w", "rdw, rsb", "op=0xe5 ; rdw & rsb", divu_w("rsb"))
    con("DIV.w", "rdw, rsb", "op=0xe7 ; rdw & rsb", div_w("rsb"))
    con("DIVU.d", "pddn, rsw", "op=0xed ; pdd & pddn & b4=0 & rsw", divu_d("rsw"))
    con("DIV.d", "pddn, rsw", "op=0xef ; pdd & pddn & b4=0 & rsw", div_d("rsw"))
    # immediate forms (E8: #data8, E9: #data16; byte 2 low nibble selects the operation)
    con("MULU.b", 'rdb, "#"^xa8', "op=0xe8 ; rdb & rdb1 & lo4=0 ; xa8", mulu_b("xa8"))
    con("DIVU.b", 'rdb, "#"^xa8', "op=0xe8 ; rdb & rdb1 & lo4=1 ; xa8", divu_b("xa8"))
    con("DIVU.w", 'rdw, "#"^xa8', "op=0xe8 ; rdw & lo4=3 ; xa8", divu_w("xa8"))
    con("DIV.w", 'rdw, "#"^xa8', "op=0xe8 ; rdw & lo4=0xb ; xa8", div_w("xa8"))
    con("MULU.w", 'rdw, "#"^xa16', "op=0xe9 ; rdw & rdw1 & lo4=0 ; xa16", mulu_w("xa16"))
    con("MUL.w", 'rdw, "#"^xa16', "op=0xe9 ; rdw & rdw1 & lo4=8 ; xa16", mul_w("xa16"))
    con("DIVU.d", 'pddn, "#"^xa16', "op=0xe9 ; pdd & pddn & b4=0 & lo4=1 ; xa16", divu_d("xa16"))
    con("DIV.d", 'pddn, "#"^xa16', "op=0xe9 ; pdd & pddn & b4=0 & lo4=9 ; xa16", div_d("xa16"))
    w("")


def loop_group():
    w("# ---------------------------------------------------------------- CJNE, DJNZ")
    for size in (1, 2):
        szb = size - 1
        sx = SFX[size]
        rd = "rdb" if size == 1 else "rdw"
        t = size
        imm = ("xb8", "xb8") if size == 1 else ("xa16", "xa16")

        def cj(a, b):
            return (f"local x:{t} = {a}; local y:{t} = {b}; local r:{t} = x - y; "
                    f"C = x < y; nz(r); if (r != 0) goto rel8a;")

        # CJNE Rd,direct,rel8: byte 2 = dddd 0hhh, byte 3 = direct, byte 4 = rel8
        w(f":CJNE.{sx} {rd}, dir{size}_L, rel8b is op={0xe2 | (szb << 3)} ; {rd} & b3=0 & dir{size}_L ; rel8b "
          f"{{ local x:{t} = {rd}; local y:{t} = dir{size}_L; local r:{t} = x - y; C = x < y; nz(r); "
          f"if (r != 0) goto rel8b; }}")
        # DJNZ direct,rel8: byte 2 = 0000 1hhh
        w(f":DJNZ.{sx} dir{size}_L, rel8b is op={0xe2 | (szb << 3)} ; hi4=0 & b3=1 & dir{size}_L & dpost{size}_L ; rel8b "
          f"{{ local r:{t} = dir{size}_L - 1; dir{size}_L = r; nz(r); build dpost{size}_L; if (r != 0) goto rel8b; }}")
        # CJNE Rd,#data,rel8 and CJNE [Rd],#data,rel8: rel8 in byte 3, data after it
        if size == 1:
            w(f":CJNE.{sx} {rd}, \"#\"^xb8, rel8a is op=0xe3 ; {rd} & lo4=0 ; rel8a & xa8 ; xb8 {{ {cj(rd, 'xb8')} }}")
            w(f":CJNE.{sx} ind1_pd, \"#\"^xb8, rel8a is op=0xe3 ; b7=0 & ind1_pd & lo4=8 ; rel8a & xa8 ; xb8 {{ {cj('ind1_pd', 'xb8')} }}")
        else:
            w(f":CJNE.{sx} {rd}, \"#\"^xa16, rel8a is op=0xeb ; {rd} & lo4=0 ; rel8a & xa8 ; xa16 {{ {cj(rd, 'xa16')} }}")
            w(f":CJNE.{sx} ind2_pd, \"#\"^xa16, rel8a is op=0xeb ; b7=0 & ind2_pd & lo4=8 ; rel8a & xa8 ; xa16 {{ {cj('ind2_pd', 'xa16')} }}")
        # DJNZ Rd,rel8: 87/8F, byte 2 = dddd 1000
        w(f":DJNZ.{sx} {rd}, rel8a is op={0x87 | (szb << 3)} ; {rd} & lo4=8 ; rel8a & xa8 "
          f"{{ local r:{t} = {rd} - 1; {rd} = r; nz(r); if (r != 0) goto rel8a; }}")
    w("")


def stack_group():
    w("# ---------------------------------------------------------------- PUSH / POP")
    # direct: 87/8F, byte 2 = 00pp 0hhh: 00 POPU, 01 POP, 10 PUSHU, 11 PUSH
    for size in (1, 2):
        szb = size - 1
        sx = SFX[size]
        o = 0x87 | (szb << 3)
        dr, dp = f"dir{size}_L", f"dpost{size}_L"
        if size == 1:
            push = "R7 = R7 - 2; local sa:3 = segment(0:1, R7); *[data]:1 sa = {v};"
            pop = "local sa:3 = segment(0:1, R7); {v} = *[data]:1 sa; R7 = R7 + 2;"
            upush = "USP = USP - 2; local ua:3 = segment(DS, USP); *[data]:1 ua = {v};"
            upop = "local ua:3 = segment(DS, USP); {v} = *[data]:1 ua; USP = USP + 2;"
        else:
            push = "push16({v});"
            pop = "pop16({v});"
            upush = "upush16({v});"
            upop = "upop16({v});"
        w(f":POPU.{sx} {dr} is op={o} ; hi4=0 & b3=0 & {dr} & {dp} {{ {upop.format(v=dr)} build {dp}; }}")
        w(f":POP.{sx} {dr} is op={o} ; hi4=1 & b3=0 & {dr} & {dp} {{ {pop.format(v=dr)} build {dp}; }}")
        w(f":PUSHU.{sx} {dr} is op={o} ; hi4=2 & b3=0 & {dr} {{ {upush.format(v=dr)} }}")
        w(f":PUSH.{sx} {dr} is op={o} ; hi4=3 & b3=0 & {dr} {{ {push.format(v=dr)} }}")
    # register lists: op = 0 H/L kk SZ 111 (kk: 00 PUSH, 01 PUSHU, 10 POP, 11 POPU)
    WREG = [f"R{i}" for i in range(8)]
    LREG = ["R0L", "R0H", "R1L", "R1H", "R2L", "R2H", "R3L", "R3H"]
    HREG = ["R4L", "R4H", "R5L", "R5H", "R6L", "R6H", "R7L", "R7H"]
    for kk, name in enumerate(("PUSH", "PUSHU", "POP", "POPU")):
        for hl, szb, regs in ((0, 1, WREG), (0, 0, LREG), (1, 0, HREG)):
            o = (hl << 6) | (kk << 4) | (szb << 3) | 7
            sx = "w" if szb else "b"
            for mask in range(1, 256):
                sel = [i for i in range(8) if mask >> i & 1]
                disp = ", ".join(regs[i] for i in sel)
                stmts = []
                order = sorted(sel, reverse=True) if name.startswith("PUSH") else sel
                for i in order:
                    r = regs[i]
                    if szb:
                        stmts.append({"PUSH": f"push16({r});", "PUSHU": f"upush16({r});",
                                      "POP": f"pop16({r});", "POPU": f"upop16({r});"}[name])
                    else:
                        if name == "PUSH":
                            stmts.append(f"R7 = R7 - 2; sa = segment(0:1, R7); *[data]:1 sa = {r};")
                        elif name == "POP":
                            stmts.append(f"sa = segment(0:1, R7); {r} = *[data]:1 sa; R7 = R7 + 2;")
                        elif name == "PUSHU":
                            stmts.append(f"USP = USP - 2; ua = segment(DS, USP); *[data]:1 ua = {r};")
                        else:
                            stmts.append(f"ua = segment(DS, USP); {r} = *[data]:1 ua; USP = USP + 2;")
                if not szb:
                    stmts.insert(0, "local ua:3 = 0;" if name.endswith("U") else "local sa:3 = 0;")
                w(f':{name}.{sx} "{disp}" is op={o:#04x} ; rlist={mask:#04x} {{ {" ".join(stmts)} }}')
    w("")


def fixlines():
    for i, line in enumerate(out):
        if line.startswith(":") and " is " in line:
            head, rest = line.split(" is ", 1)
            j = rest.index(" {") if " {" in rest else len(rest)
            out[i] = f"{head} is {fixpat(rest[:j])}{rest[j:]}"


def main():
    w("# Generated by tools/gen_xa.py from the Philips XA User Guide; do not edit.")
    w("")
    dir_tables()
    ind_tables()
    alu_group()
    imm_group()
    short_group()
    misc_moves()
    unary_group()
    shift_group()
    muldiv_group()
    loop_group()
    stack_group()
    fixlines()
    print("\n".join(out))


if __name__ == "__main__":
    main()
