#!/usr/bin/env python3
"""Compare an analysed Ghidra listing of a Z8 image with
  1. MAME unidasm -arch z8 at the same addresses (text, via ../compare.py normalisation), and
  2. the assembler listing (libasm .lst): every assembled instruction must start a Ghidra
     instruction of the same length, and no Ghidra instruction may cover a data directive.

    real_compare.py <image.bin> <ghidra.dis> <assembler.lst> [label]
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compare  # noqa: E402

DIRECTIVES = {"db", "dw", "dl", "ds", "org", "equ", "align", "cpu", "include", "end", "setrp",
              "assume", "dc", "dz", "byte", "word", "fcb", "fdb", "string"}
LST_RE = re.compile(r"^(?:\(\d+\))?\s*([0-9A-Fa-f]+) :((?: [0-9A-Fa-f]{2})+)(?:\s{2,}(.*))?$")


def mame_ranges(img, ghid):
    """unidasm over each contiguous run of Ghidra instructions."""
    addrs = sorted(ghid)
    out = {}
    i = 0
    while i < len(addrs):
        start = addrs[i]
        end = start
        while i < len(addrs) and addrs[i] == end:
            end += len(ghid[addrs[i]][0]) // 2
            i += 1
        r = subprocess.run(["unidasm", img, "-arch", "z8", "-basepc", hex(start), "-skip",
                            str(start), "-count", str(end - start)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            m = compare.MAME_RE.match(line)
            if m:
                out[int(m.group(1), 16)] = (m.group(2).replace(" ", ""), m.group(3).strip())
    return out


def lst_entries(path):
    insns, data, dstmts = {}, set(), {}
    cont = None
    for line in open(path, errors="replace"):
        m = LST_RE.match(line.rstrip("\n"))
        if not m:
            continue
        a = int(m.group(1), 16)
        nb = len(m.group(2).split())
        src = re.sub(r";.*", "", m.group(3) or "").strip()
        src = re.sub(r"^[A-Za-z_.$][\w.$]*:\s*", "", src)
        word = src.split()[0].lower() if src.split() else ""
        if not word:
            # continuation line of the previous statement's bytes
            if cont == "data":
                data.update(range(a, a + nb))
            elif cont in insns:
                insns[cont] += nb
            continue
        if word in DIRECTIVES or word.startswith("."):
            data.update(range(a, a + nb))
            dstmts[a] = nb
            cont = "data"
        else:
            insns[a] = nb
            cont = a
    return insns, data, dstmts


def main():
    img, dis, lst = sys.argv[1:4]
    label = sys.argv[4] if len(sys.argv) > 4 else os.path.basename(dis)
    ghid = compare.load_ghidra(dis)
    mame = mame_ranges(img, ghid)
    agree = expl = 0
    bad = []
    for a, (gb, gt) in sorted(ghid.items()):
        if a not in mame:
            if a < 0xc:
                expl += 1  # MAME decodes 0000h-000Bh as 2-byte vectors (linear sweep)
            else:
                bad.append(f"{a:04x} {gb} {gt}: no MAME line")
            continue
        mb, mt = mame[a]
        nm, ng = compare.norm_mame(mt), compare.norm_ghidra(gt)
        if nm == ng and mb == gb:
            agree += 1
        elif compare.classify(mb, nm, ng) or (a < 0xc and "VECTOR" in nm):
            # MAME prints 0000h-000Bh as the IRQ0-IRQ5 vector table whatever the flow; Ghidra
            # only decodes there when an unused vector (0000h) points at address 0
            expl += 1
        else:
            bad.append(f"{a:04x} {gb}: mame '{mt}' ghidra '{gt}'")
    insns, data, dstmts = lst_entries(lst)
    # sources that hand-code an instruction with db (divmul.asm "db 0xDF ; scf"): a Ghidra
    # instruction exactly covering one db statement is that instruction, not a decode error
    dbcoded = {a for a, n in dstmts.items()
               if a >= 0xc and a in ghid and len(ghid[a][0]) // 2 == n}
    data -= {a + k for a in dbcoded for k in range(dstmts[a])}
    covered = mism = 0
    gcover = {}
    for a, (gb, _) in ghid.items():
        for k in range(len(gb) // 2):
            gcover[a + k] = a
    lbad = []
    for a, n in sorted(insns.items()):
        if a in ghid:
            if len(ghid[a][0]) // 2 == n:
                covered += 1
            else:
                mism += 1
                lbad.append(f"{a:04x}: listing length {n}, ghidra {ghid[a]}")
        elif a in gcover:
            mism += 1
            lbad.append(f"{a:04x}: inside ghidra instruction at {gcover[a]:04x}")
    # an unused interrupt vector holding 0000h is a code pointer to address 0 (pspec vectors),
    # so Ghidra decodes the vector table there; counted separately
    vec = sorted({gcover[a] for a in data if a in gcover and gcover[a] < 0xc})
    indata = sorted({gcover[a] for a in data if a in gcover and gcover[a] >= 0xc})
    for a in indata:
        lbad.append(f"{a:04x}: ghidra instruction over data directive: {ghid[a]}")
    print(f"{label}: {len(ghid)} ghidra instructions; vs MAME {agree} agree, {expl} explained, "
          f"{len(bad)} differ; vs listing {covered}/{len(insns)} assembled instructions "
          f"disassembled, {mism} boundary conflicts, {len(indata)} instructions in data ({len(vec)} more in the vector table, {len(dbcoded)} db-coded instructions)")
    missed = [a for a in sorted(insns) if a not in ghid and a not in gcover]
    if missed and os.environ.get("VERBOSE"):
        print("    not disassembled:", " ".join(f"{a:04x}" for a in missed))
    for s in (bad + lbad)[:20]:
        print("   ", s)
    return 1 if bad or mism or indata else 0


if __name__ == "__main__":
    sys.exit(main())
