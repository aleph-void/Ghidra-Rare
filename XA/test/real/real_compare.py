#!/usr/bin/env python3
"""Compare an analysed Ghidra listing of an XA image with
  1. MAME unidasm -arch xa at the same addresses (text, via ../compare.py normalisation and
     its classes of explained differences), and
  2. the asxa assembler listing: every assembled instruction must start a Ghidra instruction of
     the same length, and no Ghidra instruction may cover a data directive.

    real_compare.py <image.bin> <ghidra.dis> <assembler.lst> [label] [image base, hex]
"""
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import compare  # noqa: E402

DIRECTIVES = {"db", "dw", "ds", "dd", "resb", "resw", "org", "equ", "bit", "segment", "end",
              "align", "even", "byte", "word"}
LST_RE = re.compile(r"^([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})*)\s*\t+\s*(\d+)>?\t?(.*)$")


def mame_ranges(img, ghid, base=0):
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
        r = subprocess.run(["unidasm", img, "-arch", "xa", "-basepc", hex(start), "-skip",
                            str(start - base), "-count", str(end - start)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            m = compare.MAME_RE.match(line)
            if m:
                out[int(m.group(1), 16)] = (m.group(2).replace(" ", ""), m.group(3).strip())
    return out


def lst_entries(path):
    insns, data, srcs = {}, set(), {}
    for line in open(path, errors="replace"):
        m = LST_RE.match(line.rstrip("\n"))
        if not m or not m.group(2).strip():
            continue
        a = int(m.group(1), 16)
        nb = len(m.group(2).split())
        src = re.sub(r";.*", "", m.group(4) or "").strip()
        src = re.sub(r"^[A-Za-z_.$][\w.$]*:\s*", "", src)
        words = src.lower().split()
        word = words[0] if words else ""
        if len(words) > 1 and words[1] in DIRECTIVES:
            word = words[1]                # label without a colon ("msghour db ...")
        if not word or word in DIRECTIVES or word.startswith("$"):
            data.update(range(a, a + nb))
        else:
            insns[a] = nb
            srcs[a] = src
    return insns, data, srcs


# asxa 1.12 encodes XCH Rd,[Rs] with the pointer in the wrong bits (its test bench line
# "XCH R4L,[R1]" assembles to 50 88; the user guide and MAME give 50 81); these statements
# are counted separately
ASXA_BUG = re.compile(r"^xch\s+\w+\s*,\s*\[", re.I)


def main():
    if sys.argv[1] == "--addresses":
        insns, _, _ = lst_entries(sys.argv[2])
        print("\n".join(f"{a:x}" for a in sorted(insns)))
        return 0
    img, dis, lst = sys.argv[1:4]
    label = sys.argv[4] if len(sys.argv) > 4 else os.path.basename(dis)
    base = int(sys.argv[5], 16) if len(sys.argv) > 5 else 0
    ghid = compare.load_ghidra(dis)
    mame = mame_ranges(img, ghid, base)
    agree = 0
    expl = Counter()
    bad = []
    for a, (gb, gt) in sorted(ghid.items()):
        if a not in mame:
            bad.append(f"{a:06x} {gb} {gt}: no MAME line")
            continue
        mb, mt = mame[a]
        nm, ng = compare.norm_mame(mt), compare.norm_ghidra(gt)
        mm = mt.split()[0] if mt else ""
        if nm == ng and mb == gb:
            agree += 1
            continue
        if "." not in mm and re.sub(r"^([A-Z]+)\.[BWD]", r"\1", ng) == nm and mb == gb:
            agree += 1
            continue
        c = compare.classify(mb, nm, gb, ng, mt)
        if c:
            expl[c] += 1
        else:
            bad.append(f"{a:06x} {gb}: mame '{mt}' ghidra '{gt}'")
    insns, data, srcs = lst_entries(lst)
    covered = mism = multi = asxabug = 0
    gcover = {}
    for a, (gb, _) in ghid.items():
        for k in range(len(gb) // 2):
            gcover[a + k] = a
    lbad = []
    indata = sorted({gcover[a] for a in data if a in gcover})
    # inline arguments: a call followed by data the callee skips (asxa's "call prmsg" followed
    # by "db 13,10,'text',0"); flow analysis cannot know the callee does not return there
    calls = {a + len(gb) // 2 for a, (gb, gt) in ghid.items() if re.match(r"F?CALL ", gt)}
    inline = set()
    for a in sorted(indata):
        b = a
        while b in ghid and b not in calls:
            b = max((k for k in ghid if k < b and k + len(ghid[k][0]) // 2 == b), default=None)
            if b is None or b not in gcover or b in data and b not in ghid:
                break
        if b in calls:
            inline.add(a)
    indata = [a for a in indata if a not in inline]
    bugaddrs = {a + k for a in insns if ASXA_BUG.match(srcs[a]) for k in range(insns[a])}
    bad = [x for x in bad if int(x[:6], 16) not in bugaddrs]
    # the garbage run: instructions decoded on from an inline argument until a real one
    garbage = set()
    for a in inline:
        k = a
        while k in ghid and k not in insns:
            garbage.add(k)
            k += len(ghid[k][0]) // 2
    inlconf = 0
    for a, n in sorted(insns.items()):
        if a in gcover and gcover[a] in garbage:
            inlconf += 1
            continue
        if ASXA_BUG.match(srcs[a]):
            asxabug += 1
            continue
        if a in ghid:
            k, b = a, 0
            while k in ghid and b < n:
                b += len(ghid[k][0]) // 2
                k = a + b
            if len(ghid[a][0]) // 2 == n:
                covered += 1
            elif b == n:
                multi += 1                 # the assembler expanded one statement (PUSH lists)
            else:
                mism += 1
                lbad.append(f"{a:06x}: listing length {n}, ghidra {ghid[a]}")
        elif a in gcover:
            mism += 1
            lbad.append(f"{a:06x}: inside ghidra instruction at {gcover[a]:06x}")
    for a in indata:
        lbad.append(f"{a:06x}: ghidra instruction over data directive: {ghid[a]}")
    ex = ", ".join(f"{k} {v}" for k, v in sorted(expl.items()))
    print(f"{label}: {len(ghid)} ghidra instructions; vs MAME {agree} agree, "
          f"{sum(expl.values())} explained ({ex or '-'}), {len(bad)} differ; vs listing "
          f"{covered + multi}/{len(insns) - asxabug} assembled statements disassembled"
          f"{f' ({multi} expanded to two instructions)' if multi else ''}, {mism} boundary "
          f"conflicts, {len(indata)} instructions in data"
          f"{f' ({len(inline)} more in inline call arguments' if inline else ''}"
          f"{f', which overlap {inlconf} statements after them' if inlconf else ''}"
          f"{')' if inline else ''}"
          f"{f'; {asxabug} statements hit an asxa XCH encoding bug' if asxabug else ''}")
    missed = [a for a in sorted(insns) if a not in ghid and a not in gcover]
    if missed and os.environ.get("VERBOSE"):
        print("    not disassembled:", " ".join(f"{a:06x}" for a in missed))
    for s in (bad + lbad)[:20]:
        print("   ", s)
    return 1 if bad or mism or indata else 0


if __name__ == "__main__":
    sys.exit(main())
