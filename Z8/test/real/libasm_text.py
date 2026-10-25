#!/usr/bin/env python3
"""Second decode oracle for the assembler's reference sources (test_z8/test_z86c): compare the
Ghidra instruction text at each assembled address with the source statement libasm assembled
there. Source spellings are normalised first: condition aliases (EQ=Z, NE=NZ, ULT=C, UGE=NC),
"$+n" relative targets, signed index offsets (-1(r8) = 0FFh(r8)), and, inside "setrp" sections,
register addresses in the working-register group (setrp 20h: 21H = R1, as the encoding uses
the 4-bit form).

    libasm_text.py <ghidra.dis> <assembler.lst>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compare  # noqa: E402
import real_compare  # noqa: E402

ALIAS = {"EQ": "Z", "NE": "NZ", "ULT": "C", "UGE": "NC"}


def norm(src, addr, rp):
    t = src.upper()
    t = re.sub(r"\$([+-]\d+)?", lambda m: "%XH" % (addr + int(m.group(1) or 0)), t)
    t = re.sub(r"([+-]\d+)\(", lambda m: "%XH(" % (int(m.group(1)) & 0xff), t)
    t = re.sub(r"(?<![A-Z0-9])([0-9A-F]+)H(?![A-Z0-9])", lambda m: "0X%X" % int(m.group(1), 16), t)
    mn, _, ops = t.strip().partition(" ")
    ops = [o.strip() for o in ops.split(",")] if ops.strip() else []
    if ops and ops[0] in ALIAS:
        ops[0] = ALIAS[ops[0]]
    if rp is not None:
        def wr(m):
            v = int(m.group(2), 16)
            # register pairs: @rr of LDC/LDE(I), @RR of JP/CALL, RR of DECW/INCW
            pair = (m.group(1) == "@" and mn in ("LDC", "LDE", "LDCI", "LDEI", "JP", "CALL")) \
                or mn in ("DECW", "INCW")
            r = "RR" if pair else "R"
            return f"{m.group(1)}{r}{v & 15}" if v >> 4 == rp >> 4 else m.group(0)
        ops = [re.sub(r"^(@?)0X([0-9A-F]+)$", wr, o) for o in ops]
    return compare.norm_ghidra(mn + " " + ",".join(ops))


def main():
    ghid = compare.load_ghidra(sys.argv[1])
    rp = None
    n = ok = 0
    bad = []
    for line in open(sys.argv[2], errors="replace"):
        m = re.search(r"\bsetrp\s+(\S+)", line, re.I)
        if m and not line.lstrip().startswith(";"):
            v = m.group(1).rstrip("hH")
            rp = None if v.startswith("-") else int(v, 16)
            continue
        m = real_compare.LST_RE.match(line.rstrip("\n"))
        if not m or not m.group(3):
            continue
        a = int(m.group(1), 16)
        src = re.sub(r";.*", "", m.group(3)).strip()
        if not src or src.split()[0].lower() in real_compare.DIRECTIVES:
            continue
        n += 1
        want = norm(src, a, rp)
        got = compare.norm_ghidra(ghid[a][1]) if a in ghid else "-"
        if want == got:
            ok += 1
        else:
            bad.append(f"{a:04x} source '{src}' ghidra '{ghid.get(a, ('', '-'))[1]}'")
    print(f"{os.path.basename(sys.argv[2])}: {ok}/{n} source statements match the Ghidra text")
    for s in bad[:20]:
        print("   ", s)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
