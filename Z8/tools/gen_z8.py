#!/usr/bin/env python3
"""Generate data/languages/z8_gen.sinc: Z8 operand subtables and instruction constructors.

Source: Zilog UM0016 "Z8 CPU User Manual" (UM001604-0108): op code map (figure 134), address
modes (tables 39/40), instruction descriptions (flags), register file (tables 2-8), condition
codes (table 36). Nothing here is taken from another disassembler's source.

    python3 tools/gen_z8.py > data/languages/z8_gen.sinc
"""

out = []
w = out.append

CTRL_NAMES = {
    0xF0: "SIO", 0xF1: "TMR", 0xF2: "T1", 0xF3: "PRE1", 0xF4: "T0", 0xF5: "PRE0",
    0xF6: "P2M", 0xF7: "P3M", 0xF8: "P01M", 0xF9: "IPR", 0xFA: "IRQ", 0xFB: "IMR",
    0xFC: "FLAGS", 0xFD: "RP", 0xFE: "SPH", 0xFF: "SPL",
}
PORT_NAMES = {0: "P0", 1: "P1", 2: "P2", 3: "P3"}

# nibble fields that name a working register: (constraint field, display field)
NIB = {"ophi": "ophid", "b1hi": "b1hid", "b1lo": "b1lod", "b2lo": "b2lod"}
PAIR_FIELDS = {"b1lo"}
NIBR = {"ophi": "ophir", "b1hi": "b1hir", "b1lo": "b1lor", "b2lo": "b2lor"}
# 8-bit register fields: (field, hi nibble, lo nibble, lo nibble display)
BYTE = {"b1": ("b1hi", "b1lo", "b1lod"), "b2": ("b2hi", "b2lo", "b2lod")}

DYN = "(*[rf]:1 0xfd:1 & 0xf0)"


def working_tables():
    for f, d in NIB.items():
        # helpers: the static address of a working register / ERF register as an operand
        # register pairs are only ever named by the low nibble of the first operand byte
        sizes = (1, 2) if f in PAIR_FIELDS else (1,)
        for size in sizes:
            w(f"Wrf{size}_{f}: wa is {f} [ wa = (rpg << 4) | {f}; ] {{ export *[rf]:{size} wa; }}")
            w(f"Erf{size}_{f}: ea is {f} [ ea = (rpb << 4) | {f}; ] {{ export *[erf]:{size} ea; }}")
        for size, pref in ((1, "Rw"), (2, "RRw"))[:len(sizes)]:
            name = f"{pref}_{f}"
            if size == 2:
                d = NIBR[f]
            w(f"# working register{' pair' if size == 2 else ''} named by {f}")
            w(f'{name}: {d} is rpv=0 & {f} & {d} '
              f'{{ local a:1 = {DYN} | {f}; export *[rf]:{size} a; }}')
            w(f'{name}: {d} is rpv=1 & rpg=0 & {d} & Erf{size}_{f} '
              f'{{ export Erf{size}_{f}; }}')
            w(f'{name}: {d} is rpv=1 & rpg=0 & rpb=0 & {f} & {d} '
              f'{{ export *[rf]:{size} {f}; }}')
            w(f'{name}: {d} is rpv=1 & {d} & Wrf{size}_{f} '
              f'{{ export Wrf{size}_{f}; }}')
            if size == 1:
                w(f'{name}: {d} is rpv=1 & rpg=15 & {f}=12 & {d} '
                  f'{{ packflags(); export FLAGS; }}')
                w(f'{name}: {d} is rpv=1 & rpg=15 & {f}=14 & {d} {{ export SPH; }}')
                w(f'{name}: {d} is rpv=1 & rpg=15 & {f}=15 & {d} {{ export SPL; }}')
            else:
                w(f'{name}: {d} is rpv=1 & rpg=15 & {f}=14 & {d} {{ export SP; }}')
            w("")
        # post-write hook: a write to FLAGS through a working register updates C..H
        w(f"Rwp_{f}: is rpv=1 & rpg=15 & {f}=12 {{ unpackflags(); }}")
        # a write to RP (FDh) other than SRP / LD RP,#imm: the RP value is no longer known
        w(f"Rwp_{f}: is rpv=1 & rpg=15 & {f}=13 [ rpv = 0; globalset(inst_next, rpv); ] {{ }}")
        w(f"Rwp_{f}: is {f} {{ }}")
        w("")


def byte_tables():
    for f, (hi, lo, lod) in BYTE.items():
        # 8-bit register operand R
        w(f"# register operand R in {f} (Ex = working register)")
        for size in ((1, 2) if f == "b1" else (1,)):
            w(f"Rf{size}_{f}: {f} is {f} {{ export *[rf]:{size} {f}; }}")
        w(f"R8_{f}: Rw_{lo} is {hi}=0xe & Rw_{lo} {{ export Rw_{lo}; }}")
        for v in range(16):
            disp = f'"{PORT_NAMES[v]}"' if v in PORT_NAMES else f"Rf1_{f}"
            w(f"R8_{f}: {disp} is rpv=0 & {f}={v} & Rf1_{f} {{ export Rf1_{f}; }}")
            w(f"R8_{f}: {disp} is rpv=1 & rpb=0 & {f}={v} & Rf1_{f} {{ export Rf1_{f}; }}")
            w(f"R8_{f}: {disp} is rpv=1 & {f}={v} & Rf1_{f} & Erf1_{lo} {{ export Erf1_{lo}; }}")
        for v, n in CTRL_NAMES.items():
            if n == "FLAGS":
                w(f'R8_{f}: "{n}" is {f}={v:#x} {{ packflags(); export FLAGS; }}')
            elif n in ("SPH", "SPL"):
                w(f'R8_{f}: "{n}" is {f}={v:#x} {{ export {n}; }}')
            else:
                w(f'R8_{f}: "{n}" is {f}={v:#x} & Rf1_{f} {{ export Rf1_{f}; }}')
        w(f"R8_{f}: {f} is {f} {{ export *[rf]:1 {f}; }}")
        w("")
        w(f"R8p_{f}: is {hi}=0xe & Rwp_{lo} {{ }}")
        w(f"R8p_{f}: is {f}=0xfc {{ unpackflags(); }}")
        w(f"R8p_{f}: is {f}=0xfd [ rpv = 0; globalset(inst_next, rpv); ] {{ }}")
        w(f"R8p_{f}: is {f} {{ }}")
        w("")
        w(f'IR_{f}: "@"^{lod} is {hi}=0xe & {lod} & R8_{f} '
          f'{{ local p:1 = R8_{f}; export *[rf]:1 p; }}')
        w(f'IR_{f}: "@"^{f} is {f} & R8_{f} '
          f'{{ local p:1 = R8_{f}; export *[rf]:1 p; }}')
        if f != "b1":
            w("")
            continue
        # register pair operands (DECW/INCW, JP/CALL @RR) only occur in the first byte
        # register pair operand RR (DECW/INCW, JP/CALL @RR)
        w(f"# register pair operand RR in {f}")
        w(f"RR8_{f}: RRw_{lo} is {hi}=0xe & RRw_{lo} {{ export RRw_{lo}; }}")
        for v in range(16):
            w(f"RR8_{f}: Rf2_{f} is rpv=0 & {f}={v} & Rf2_{f} {{ export Rf2_{f}; }}")
            w(f"RR8_{f}: Rf2_{f} is rpv=1 & rpb=0 & {f}={v} & Rf2_{f} {{ export Rf2_{f}; }}")
            w(f"RR8_{f}: Rf2_{f} is rpv=1 & {f}={v} & Rf2_{f} & Erf2_{lo} {{ export Erf2_{lo}; }}")
        w(f"RR8_{f}: Rf2_{f} is {f}=0xfe & Rf2_{f} {{ export SP; }}")
        w(f"RR8_{f}: {f} is {f} {{ export *[rf]:2 {f}; }}")
        w("")
        # indirect register operand IR: the register holds a register-file address
        w(f'IRW_{f}: "@"^{lod} is {hi}=0xe & {lod} & R8_{f} '
          f'{{ local p:1 = R8_{f}; export *[rf]:2 p; }}')
        w(f'IRW_{f}: "@"^{f} is {f} & R8_{f} '
          f'{{ local p:1 = R8_{f}; export *[rf]:2 p; }}')
        # indirect register pair (JP/CALL @RR): exports the pair, whose value is the target
        w(f'IRR_{f}: "@"^{lo}r is {hi}=0xe & {lo}r & RR8_{f} {{ export RR8_{f}; }}')
        w(f'IRR_{f}: "@"^{f} is {f} & RR8_{f} {{ export RR8_{f}; }}')
        w("")
    # @r (working register indirect)
    for f, d in (("b1hi", "b1hid"), ("b1lo", "b1lod")):
        w(f'Iw_{f}: "@"^{d} is Rw_{f} & {d} {{ local p:1 = Rw_{f}; export *[rf]:1 p; }}')
    w("")


# ---------------------------------------------------------------- instructions

ALU = {0x0: "ADD", 0x1: "ADC", 0x2: "SUB", 0x3: "SBC", 0x4: "OR", 0x5: "AND",
       0x6: "TCM", 0x7: "TM", 0xA: "CP", 0xB: "XOR"}
NOSTORE = {"TCM", "TM", "CP"}


def alu_body(mn, dst, src, post):
    """p-code for dst <- dst op src (UM0016 flag tables)."""
    b = [f"local a:1 = {dst};", f"local b:1 = {src};"]
    if mn == "ADD":
        b += ["local r:1 = a + b;", "C = carry(a, b);", "V = scarry(a, b);",
              "H = ((a & 0xf) + (b & 0xf)) > 0xf;", "D = 0;"]
    elif mn == "ADC":
        b += ["local cin:1 = C;", "local r:1 = a + b + cin;",
              "local t:2 = zext(a) + zext(b) + zext(cin);", "C = t > 0xff;",
              "H = ((a & 0xf) + (b & 0xf) + cin) > 0xf;",
              "V = ((~(a ^ b)) & (a ^ r) & 0x80) != 0;", "D = 0;"]
    elif mn in ("SUB", "CP"):
        b += ["local r:1 = a - b;", "C = a < b;", "V = sborrow(a, b);"]
        if mn == "SUB":
            b += ["H = (a & 0xf) < (b & 0xf);", "D = 1;"]
    elif mn == "SBC":
        b += ["local cin:1 = C;", "local r:1 = a - b - cin;",
              "local za:2 = zext(a);", "local zb:2 = zext(b) + zext(cin);", "C = za < zb;",
              "H = (a & 0xf) < ((b & 0xf) + cin);",
              "V = ((a ^ b) & (a ^ r) & 0x80) != 0;", "D = 1;"]
    elif mn == "OR":
        b += ["local r:1 = a | b;", "V = 0;"]
    elif mn == "AND":
        b += ["local r:1 = a & b;", "V = 0;"]
    elif mn == "XOR":
        b += ["local r:1 = a ^ b;", "V = 0;"]
    elif mn == "TCM":
        b += ["local r:1 = (~a) & b;", "V = 0;"]
    elif mn == "TM":
        b += ["local r:1 = a & b;", "V = 0;"]
    b.append("zs8(r);")
    if mn not in NOSTORE:
        b.append(f"{dst} = r;")
        if post:
            b.append(f"build {post};")
    return " ".join(b)


def ctor(disp, pattern, body):
    w(f":{disp} is {pattern} {{ {body} }}")


def alu():
    for row, mn in sorted(ALU.items()):
        st = mn not in NOSTORE
        o = row << 4
        p = " & Rwp_b1hi" if st else ""
        ctor(f"{mn} Rw_b1hi, Rw_b1lo", f"op={o | 2:#04x}; Rw_b1hi & Rw_b1lo{p}",
             alu_body(mn, "Rw_b1hi", "Rw_b1lo", "Rwp_b1hi" if st else None))
        ctor(f"{mn} Rw_b1hi, Iw_b1lo", f"op={o | 3:#04x}; Rw_b1hi & Iw_b1lo{p}",
             alu_body(mn, "Rw_b1hi", "Iw_b1lo", "Rwp_b1hi" if st else None))
        p = " & R8p_b2" if st else ""
        ctor(f"{mn} R8_b2, R8_b1", f"op={o | 4:#04x}; R8_b1; R8_b2{p}",
             alu_body(mn, "R8_b2", "R8_b1", "R8p_b2" if st else None))
        ctor(f"{mn} R8_b2, IR_b1", f"op={o | 5:#04x}; IR_b1; R8_b2{p}",
             alu_body(mn, "R8_b2", "IR_b1", "R8p_b2" if st else None))
        p = " & R8p_b1" if st else ""
        ctor(f'{mn} R8_b1, "#"^b2', f"op={o | 6:#04x}; R8_b1{p}; b2",
             alu_body(mn, "R8_b1", "b2", "R8p_b1" if st else None))
        ctor(f'{mn} IR_b1, "#"^b2', f"op={o | 7:#04x}; IR_b1; b2",
             alu_body(mn, "IR_b1", "b2", None))


UNARY = {
    0x0: ("DEC", "local r:1 = a - 1; zs8(r); V = (a == 0x80);"),
    0x1: ("RLC", "local c0:1 = C; C = a >> 7; local r:1 = (a << 1) | c0; zs8(r); "
                 "V = ((r ^ a) & 0x80) != 0;"),
    0x2: ("INC", "local r:1 = a + 1; zs8(r); V = (a == 0x7f);"),
    0x4: ("DA", "local lo:1 = zext((H != 0) || ((a & 0xf) > 9)); "
                "local hi:1 = zext((C != 0) || (a > 0x99)); "
                "local sub:1 = zext(D != 0); "
                "local addv:1 = (lo * 6) + (hi * 0x60); "
                "local subv:1 = (H * 6) + (C * 0x60); "
                "local r:1 = a + (addv * (1 - sub)) - (subv * sub); "
                "C = ((sub == 0) && (hi != 0)) || ((sub != 0) && (C != 0)); zs8(r);"),
    0x5: ("POP", "local r:1 = 0; pop8(r);"),
    0x6: ("COM", "local r:1 = ~a; zs8(r); V = 0;"),
    0x7: ("PUSH", "push8(a);"),
    0x9: ("RL", "C = a >> 7; local r:1 = (a << 1) | (a >> 7); zs8(r); "
                "V = ((r ^ a) & 0x80) != 0;"),
    0xB: ("CLR", "local r:1 = 0;"),
    0xC: ("RRC", "local c0:1 = C; C = a & 1; local r:1 = (a >> 1) | (c0 << 7); zs8(r); "
                 "V = ((r ^ a) & 0x80) != 0;"),
    0xD: ("SRA", "C = a & 1; local r:1 = a s>> 1; zs8(r); V = 0;"),
    0xE: ("RR", "C = a & 1; local r:1 = (a >> 1) | (a << 7); zs8(r); "
                "V = ((r ^ a) & 0x80) != 0;"),
    0xF: ("SWAP", "local r:1 = (a << 4) | (a >> 4); zs8(r);"),
}


def unary():
    for row, (mn, body) in sorted(UNARY.items()):
        o = row << 4
        rd = "" if mn == "POP" else None
        store = mn != "PUSH"
        for col, opnd, post in ((0, "R8_b1", "R8p_b1"), (1, "IR_b1", None)):
            pre = "" if mn == "POP" else f"local a:1 = {opnd}; "
            b = pre + body
            if store:
                b += f" {opnd} = r;"
                if post:
                    b += f" build {post};"
            pat = f"op={o | col:#04x}; {opnd}" + (f" & {post}" if post and store else "")
            ctor(f"{mn} {opnd}", pat, b)
    # word increment / decrement
    for o, mn, op in ((0x80, "DECW", "-"), (0xA0, "INCW", "+")):
        lim = "0x8000" if mn == "DECW" else "0x7fff"
        for col, opnd in ((0, "RR8_b1"), (1, "IRW_b1")):
            ctor(f"{mn} {opnd}", f"op={o | col:#04x}; {opnd}",
                 f"local a:2 = {opnd}; local r:2 = a {op} 1; zs16(r); V = (a == {lim}); "
                 f"{opnd} = r;")


def loads():
    # LD r,R / LD R,r / LD r,#IM / INC r / DJNZ / JR / JP cc
    ctor("LD Rw_ophi, R8_b1", "oplo=8 & Rw_ophi & Rwp_ophi; R8_b1",
         "Rw_ophi = R8_b1; build Rwp_ophi;")
    ctor("LD R8_b1, Rw_ophi", "oplo=9 & Rw_ophi; R8_b1 & R8p_b1",
         "R8_b1 = Rw_ophi; build R8p_b1;")
    ctor('LD Rw_ophi, "#"^b1', "oplo=0xc & Rw_ophi & Rwp_ophi; b1",
         "Rw_ophi = b1; build Rwp_ophi;")
    ctor("INC Rw_ophi", "oplo=0xe & Rw_ophi & Rwp_ophi",
         "local a:1 = Rw_ophi; local r:1 = a + 1; zs8(r); V = (a == 0x7f); "
         "Rw_ophi = r; build Rwp_ophi;")
    ctor("DJNZ Rw_ophi, rel", "oplo=0xa & Rw_ophi; rel",
         "Rw_ophi = Rw_ophi - 1; if (Rw_ophi != 0) goto rel;")
    ctor("JR cc, rel", "oplo=0xb & cc; rel", "if (cc) goto rel;")
    ctor("JR rel", "op=0x8b; rel", "goto rel;")
    ctor('JR "F", rel', "op=0x0b; rel", "")
    ctor("JP cc, dabs", "oplo=0xd & cc; dabs", "if (cc) goto dabs;")
    ctor("JP dabs", "op=0x8d; dabs", "goto dabs;")
    ctor('JP "F", dabs', "op=0x0d; dabs", "")
    # register-file moves
    ctor("LD Rw_b1hi, Iw_b1lo", "op=0xe3; Rw_b1hi & Iw_b1lo & Rwp_b1hi",
         "Rw_b1hi = Iw_b1lo; build Rwp_b1hi;")
    ctor("LD Iw_b1hi, Rw_b1lo", "op=0xf3; Iw_b1hi & Rw_b1lo", "Iw_b1hi = Rw_b1lo;")
    ctor("LD R8_b2, R8_b1", "op=0xe4; R8_b1; R8_b2 & R8p_b2", "R8_b2 = R8_b1; build R8p_b2;")
    ctor("LD R8_b2, IR_b1", "op=0xe5; IR_b1; R8_b2 & R8p_b2", "R8_b2 = IR_b1; build R8p_b2;")
    ctor('LD R8_b1, "#"^b2', "op=0xe6; R8_b1 & R8p_b1; b2", "R8_b1 = b2; build R8p_b1;")
    ctor('LD IR_b1, "#"^b2', "op=0xe7; IR_b1; b2", "IR_b1 = b2;")
    ctor("LD IR_b2, R8_b1", "op=0xf5; R8_b1; IR_b2", "IR_b2 = R8_b1;")
    ctor('LD Rw_b1hi, b2^"("^Rw_b1lo^")"', "op=0xc7; Rw_b1hi & Rw_b1lo & Rwp_b1hi; b2",
         "local p:1 = b2 + Rw_b1lo; Rw_b1hi = *[rf]:1 p; build Rwp_b1hi;")
    ctor('LD b2^"("^Rw_b1lo^")", Rw_b1hi', "op=0xd7; Rw_b1hi & Rw_b1lo; b2",
         "local p:1 = b2 + Rw_b1lo; *[rf]:1 p = Rw_b1hi;")
    # LD RP,#imm: also a register-pointer change the context can follow
    w(':LD "RP", "#"^b2 is op=0xe6; b1=0xfd; b2 & b2hi & b2lo '
      '[ rpv = 1; rpg = b2hi; rpb = b2lo; globalset(inst_next, rpv); '
      'globalset(inst_next, rpg); globalset(inst_next, rpb); ] { *[rf]:1 0xfd:1 = b2; }')
    w(':SRP "#"^b1 is op=0x31; b1 & b1hi & b1lo '
      '[ rpv = 1; rpg = b1hi; rpb = b1lo; globalset(inst_next, rpv); '
      'globalset(inst_next, rpg); globalset(inst_next, rpb); ] { *[rf]:1 0xfd:1 = b1; }')
    # program / external data memory
    for o, mn, sp in ((0x82, "LDE", "data"), (0xC2, "LDC", "code")):
        ctor(f'{mn} Rw_b1hi, "@"^RRw_b1lo', f"op={o:#04x}; Rw_b1hi & RRw_b1lo & Rwp_b1hi",
             f"Rw_b1hi = *[{sp}]:1 RRw_b1lo; build Rwp_b1hi;")
        ctor(f'{mn} "@"^RRw_b1lo, Rw_b1hi', f"op={o + 0x10:#04x}; Rw_b1hi & RRw_b1lo",
             f"*[{sp}]:1 RRw_b1lo = Rw_b1hi;")
        ctor(f'{mn}I "@"^Rw_b1hi, "@"^RRw_b1lo', f"op={o + 1:#04x}; Rw_b1hi & RRw_b1lo",
             f"local p:1 = Rw_b1hi; *[rf]:1 p = *[{sp}]:1 RRw_b1lo; "
             f"Rw_b1hi = p + 1; RRw_b1lo = RRw_b1lo + 1;")
        ctor(f'{mn}I "@"^RRw_b1lo, "@"^Rw_b1hi', f"op={o + 0x11:#04x}; Rw_b1hi & RRw_b1lo",
             f"local p:1 = Rw_b1hi; *[{sp}]:1 RRw_b1lo = *[rf]:1 p; "
             f"Rw_b1hi = p + 1; RRw_b1lo = RRw_b1lo + 1;")


def flow():
    ctor("JP IRR_b1", "op=0x30; IRR_b1", "goto [IRR_b1];")
    ctor("CALL IRR_b1", "op=0xd4; IRR_b1",
         "local t:2 = IRR_b1; local ret:2 = inst_next; push16(ret); call [t];")
    ctor("CALL dabs", "op=0xd6; dabs", "local ret:2 = inst_next; push16(ret); call dabs;")
    ctor("RET", "op=0xaf", "local t:2 = 0; pop16(t); return [t];")
    ctor("IRET", "op=0xbf",
         "pop8(FLAGS); unpackflags(); local t:2 = 0; pop16(t); "
         "*[rf]:1 0xfb:1 = *[rf]:1 0xfb:1 | 0x80; return [t];")
    ctor("DI", "op=0x8f", "*[rf]:1 0xfb:1 = *[rf]:1 0xfb:1 & 0x7f;")
    ctor("EI", "op=0x9f", "*[rf]:1 0xfb:1 = *[rf]:1 0xfb:1 | 0x80;")
    ctor("RCF", "op=0xcf", "C = 0;")
    ctor("SCF", "op=0xdf", "C = 1;")
    ctor("CCF", "op=0xef", "C = C ^ 1;")
    ctor("NOP", "op=0xff", "")
    # Z86C0x/Z86E0x CMOS additions (UM0016); NMOS Z8601-era parts treat these as illegal
    ctor("WDh", "op=0x4f", "watchdog_halt_enable();")
    ctor("WDT", "op=0x5f", "watchdog_refresh();")
    ctor("STOP", "op=0x6f", "stop();")
    ctor("HALT", "op=0x7f", "halt();")


w("# Generated by tools/gen_z8.py from Zilog UM0016. Do not edit.")
w("")
working_tables()
byte_tables()
alu()
unary()
loads()
flow()
print("\n".join(out))
