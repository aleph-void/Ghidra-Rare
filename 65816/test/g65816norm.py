"""Text normalisation shared by the 65816 comparison scripts (Ghidra vs MAME g65816)."""
import re


def num(s):
    return int(s, 16)


def norm_ghidra(t):
    t = t.strip().lower()
    t = re.sub(r"\$?0x([0-9a-f]+)", lambda m: "$%x" % num(m.group(1)), t)
    t = re.sub(r"[<>!]", "", t)          # WDC address-size hints
    t = re.sub(r"#\$", "#$", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r",\s+", ",", t)
    return t


def norm_mame(t, rec_bytes):
    t = t.strip().lower()
    t = re.sub(r"^(\w+ [0-9a-f]{6}) \((-?\$[0-9a-f]+)\)$", r"\1", t)  # "(+-disp)" after targets
    m = re.fullmatch(r"(bpl|bmi|bvc|bvs|bcc|bcs|bne|beq|bra|brl|per) ([0-9a-f]{6})", t)
    if m:
        t = "%s $%x" % (m.group(1), num(m.group(2)))
    t = re.sub(r"\$([0-9a-f]+)", lambda m: "$%x" % num(m.group(1)), t)
    # stack-relative offsets: MAME prints them signed, and prints 0x80 as "-$0" (bug)
    def sr(m):
        v = num(m.group(1))
        return "$%x,s" % ((0x80 if v == 0 else (0x100 - v)) & 0xff)
    t = re.sub(r"-\$([0-9a-f]+),s", sr, t)
    t = re.sub(r",\s+", ",", t)
    t = re.sub(r"^(asl|lsr|rol|ror)a$", r"\1 a", t)
    return t




def semantic(g, m, op, addr):
    """Fold spelling differences that do not change meaning."""
    m2 = {"ina": "inc a", "dea": "dec a"}.get(m, m)
    if op in (0x4c, 0x20):               # JMP/JSR abs: Ghidra shows the bank of the instruction
        m2 = re.sub(r"\$([0-9a-f]+)$", lambda x: "$%x" % (addr & 0xff0000 | int(x.group(1), 16)), m2)
    if op == 0x5c:                       # JMP long: MAME "jmp", WDC "jml"
        m2 = m2.replace("jmp ", "jml ", 1)
    if op == 0xdc:                       # JML [abs]: MAME prints "(...)"
        m2 = re.sub(r"^jml \((.*)\)$", r"jml [\1]", m2)
    if op in (0x00, 0x02, 0x42):         # BRK/COP/WDM signature byte: MAME "#$nn"
        m2 = m2.replace("#$", "$")
    return g == m2
