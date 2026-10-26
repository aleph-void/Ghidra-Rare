"""Explanations for decode differences between Ghidra and GNU objdump (see compare.py).

explain(raw, oo, go, olen, glen, lang) returns a bucket name for a difference traced to the RX
manuals (R01US0032 RXv1, R01US0071 RXv2, R01US0316 RXv3, section 4 "Instruction Code"), or None.
raw is the instruction's bytes, oo/go the normalised objdump/Ghidra texts, lang v1/v2/v3.

Bucket prefixes:
  reserved:  objdump decodes an encoding the manual does not define (Ghidra: invalid)
  version:   the instruction exists only in a later ISA version than the language
  objdump:   objdump prints a wrong operand (confirmed against the manual and, where possible,
             gas-assembled code)
"""

V3_MNEM = {"bfmov", "bfmovz", "save", "rstr", "dabs", "dadd", "ddiv", "dmul", "dneg", "dround",
           "dsqrt", "dsub", "dtof", "dtoi", "dtou", "ftod", "itod", "utod", "mvfdc", "mvtdc", "mvfdr",
           "dpushm.d", "dpushm.l", "dpopm.d", "dpopm.l", "dmov.d", "dmov.l", "dcmpun", "dcmpeq",
           "dcmplt", "dcmple"}
V2_MNEM = {"fsqrt", "ftou", "utof", "movco", "movli", "emaca", "emsba", "emula", "maclh", "msbhi",
           "msblh", "msblo", "mullh", "mvfacgu", "mvfaclo", "mvtacgu", "racl", "rdacl", "rdacw"}

CR_RESERVED_W = {1, 4, 5, 6, 7, 14, 15}     # MVTC / POPC destinations (1 = PC)
CR_RESERVED_R = {4, 5, 6, 7, 14, 15}        # MVFC / PUSHC sources


def b(raw, i):
    return raw[i] if i < len(raw) else 0


def version_needed(raw, oo):
    """Lowest RX ISA version (1-3) that defines the instruction objdump printed, per the
    instruction lists in section 3 of the manuals ("Supported by the RXv2/RXv3 and later",
    "Extended for the RXv2/RXv3")."""
    m = oo.split(" ")[0]
    ops = oo[len(m):]
    if m in V3_MNEM:
        return 3
    if m == "xor" and ops.count(",") == 2:
        return 3
    if m in V2_MNEM:
        return 2
    b0, b1 = b(raw, 0), b(raw, 1)
    if m in ("mulhi", "mullo", "machi", "maclo", "mvtachi", "mvtaclo") and ",a1" in ops:
        return 2
    if m in ("mvfachi", "mvfacmi"):
        if ",a1," in ops or not ops.startswith(" #0,"):
            return 2
    if m in ("racw",) and (",a1" in ops or ops.startswith(" #2")):
        return 2
    if m in ("fadd", "fsub", "fmul") and ops.count(",") == 2:
        return 2
    if m in ("stz", "stnz") and b0 == 0xFC:
        return 2
    if m in ("mvtc", "mvfc", "pushc", "popc") and "extb" in ops:
        return 2
    return 1


def explain(raw, oo, go, olen, glen, lang):
    v = int(lang[1])
    b0, b1, b2, b3 = (b(raw, i) for i in range(4))
    m = oo.split(" ")[0]

    if go == "bad" and oo != "bad":
        need = version_needed(raw, oo)
        if need > v:
            return f"version: RXv{need} instruction, not in RXv{v}"
        if b0 == 0x01:
            return "reserved: 01h (objdump: undocumented 'dbt')"
        if b0 == 0x06 and (b1 & 3) == 3:
            return "reserved: memex prefix 06h with ld=11b (register operand)"
        if b0 == 0x06 and (b1 & 0x3C) == 0x20 and b2 in (0x00, 0x02) and (b1 >> 6) != 2:
            return "reserved: ADC/SBB memory operand other than .L"
        if 0xF8 <= b0 <= 0xFA:
            sz, li = b1 & 3, (b1 >> 2) & 3
            if sz == 3:
                return "reserved: MOV #imm,dst with sz=11b"
            if (sz == 0 and li != 1) or (sz == 1 and li not in (1, 2)):
                return "reserved: MOV.B/.W #imm,dst with an immediate size the manual does not list"
        if b0 == 0xFB and (b1 & 3) != 2:
            return "reserved: MOV #imm,Rd (FBh) with a size other than .L"
        if b0 in (0x6E, 0x6F):
            return "reserved: PUSHM/POPM register range (manual: R1-R14 to R2-R15, first < last)"
        if b0 == 0x3F:
            return "reserved: RTSD register range (manual: R1-R15, first <= last)"
        if b0 in (0xF3, 0xF7):
            return "reserved: BSET/BCLR/BTST #imm3 / PUSH with ld=11b"
        if b0 == 0xFC and (b1 & 0xF0) == 0xD0 and ((b1 & 3) == 3 and ((b1 >> 2) & 3) != 2 or
                                                    ((b1 >> 2) & 3) == 3):
            return "reserved: SCCnd.B/.W with a register / sz=11b"
        if b0 == 0xFC and (b1 & 0xF0) == 0xD0 and (b2 & 15) in (14, 15):
            return "reserved: SCCnd condition 1110b/1111b"
        if b0 == 0xFC and (b1 & 0xE0) == 0xE0 and (b1 & 3) == 3:
            return "reserved: BMCnd/BNOT #imm3 with ld=11b"
        if b0 == 0xFC and (b1 & 0xE0) == 0xE0 and (b2 & 15) == 14:
            return "reserved: BMCnd condition 1110b"
        if b0 == 0xFD and (b1 & 0xE0) == 0xE0 and (b2 >> 4) == 14:
            return "reserved: BMCnd condition 1110b"
        if b0 == 0xFD and b1 == 0x68 and (b2 & 15) in CR_RESERVED_W | ({13} if v == 1 else set()):
            return "reserved: MVTC to a reserved control register / PC"
        if b0 == 0xFD and (b1 & 0xF3) == 0x73 and (b2 & 15) in CR_RESERVED_W | ({13} if v == 1 else set()):
            return "reserved: MVTC to a reserved control register / PC"
        if b0 == 0xFD and (b1 & 0xF3) == 0x73 and (b2 >> 4) != 0:
            return "reserved: MVTC #imm with nonzero bits 7-4 of the third byte"
        if b0 == 0xFD and b1 == 0x6A and (b2 >> 4) in CR_RESERVED_R | ({13} if v == 1 else set()):
            return "reserved: MVFC from a reserved control register"
        if b0 == 0xFD and b1 in (0x69, 0x6B):
            return "reserved: FD 69h/6Bh (objdump: MVTC/MVFC variants)"
        if b0 == 0x7E and (b1 >> 4) == 0xE and (b1 & 15) in CR_RESERVED_W | ({13} if v == 1 else set()):
            return "reserved: POPC to a reserved control register / PC"
        if b0 == 0x7E and (b1 >> 4) == 0xC and (b1 & 15) in CR_RESERVED_R | ({13} if v == 1 else set()):
            return "reserved: PUSHC from a reserved control register"
        if b0 == 0x7E and (b1 >> 4) in (0xD, 0xF):
            return "reserved: 7E Dxh/Fxh (objdump: PUSHC/POPC variants)"
        if b0 == 0x7F and (b1 >> 4) in (0xA, 0xB) and (b1 & 15) not in (0, 1, 2, 3, 8, 9):
            return "reserved: SETPSW/CLRPSW reserved flag number"
        if b0 == 0xFD and b1 in (0x1E, 0x1F) and (b1 & 1) == 0 and (b2 & 0x40):
            return "reserved: MVFACxx shift field 01b"
        if m in ("emul", "emulu") and oo.endswith(",r15"):
            return "reserved: EMUL/EMULU with Rd = R15 (manual: R0-R14)"
        if m.startswith("dcmp"):
            return "reserved: DCMPcm condition other than UN/EQ/LT/LE"
        if m in ("mvtdc", "mvfdc", "dpushm.l", "dpopm.l") and go == "bad":
            return "reserved: double-precision control register number > 3"
        if m in ("dpushm.d", "dpopm.d"):
            return "reserved: DPUSHM/DPOPM range past DR15"

    if m in ("bfmov", "bfmovz") and go != "bad":
        imm = b3 | (b(raw, 4) << 8)
        dlsb = (imm >> 5) & 31
        slsb = (dlsb - (imm & 31)) & 31
        width = (((imm >> 10) & 31) - dlsb) & 31
        if go == f"{m} #{slsb},#{dlsb},#{width},{oo.split(',')[-2]},{oo.split(',')[-1]}":
            return "objdump: BFMOV/BFMOVZ slsb/width decoded without the modulo-32 rule (gas encodes per the manual)"
    if go.startswith("mvtdc") and (m == "mvtdc" or oo == "bad"):
        return "objdump: MVTDC register fields swapped relative to the manual (byte 3 = 1000 rs, byte 4 = rd 0100)"
    return None
