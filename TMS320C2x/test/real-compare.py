#!/usr/bin/env python3
"""Compare the instructions Ghidra's analysis created in a real image with MAME unidasm.

    real-compare.py <c2x|c5x> <image.bin> <ghidra .dis from TmsRealCheck> [be|le] [base-word-addr]

unidasm disassembles the whole image linearly; every Ghidra instruction whose address also starts
an unidasm line is compared after the normalisation and difference classes of compare.py.
Prints counts and every difference; exit status 1 on an unexplained difference.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare  # noqa: E402


def main():
    fam, image, dis = sys.argv[1], sys.argv[2], sys.argv[3]
    end = sys.argv[4] if len(sys.argv) > 4 else ("be" if fam == "c2x" else "le")
    base = int(sys.argv[5], 16) if len(sys.argv) > 5 else 0
    data = open(image, "rb").read()
    want = "be" if fam == "c2x" else "le"          # unidasm byte order per architecture
    if end != want:
        data = bytes(x for i in range(0, len(data) - 1, 2) for x in (data[i + 1], data[i]))
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as t:
        t.write(data)
    arch = "tms320c2x" if fam == "c2x" else "tms320c5x"
    out = subprocess.run(["unidasm", t.name, "-arch", arch], capture_output=True, text=True).stdout
    os.unlink(t.name)
    mame = {}
    lines = []
    for line in out.splitlines():
        m = re.match(r"^\s*([0-9a-f]+): (\S+)(?: (\S{4}))?\s+(.*)$", line)
        if m:
            lines.append((int(m.group(1), 16), m.group(4).strip()))
    for i, (a, t) in enumerate(lines):
        n = (lines[i + 1][0] - a) if i + 1 < len(lines) else None   # last line: length unknown
        mame[a] = (n, t)
    same = diff = explained = missing = 0
    bad = []
    for line in open(dis):
        a, words, text = line.rstrip("\n").split(" ", 2)
        a = int(a, 16) - base
        w = [int(words[k:k + 4], 16) for k in range(0, len(words), 4)]
        if a not in mame:
            missing += 1
            continue
        g = (len(w), text)
        mm = mame[a]
        w2 = w[1] if len(w) > 1 else 0
        if mm[0] is None:
            mm = (g[0], mm[1])
        cg = compare.canon(fam, g[1], True, w[0], w2)
        cm = compare.canon(fam, mm[1], False, w[0], w2)
        if not (w[0] & 0x80) and cg[0] == cm[0] and len(cg[1]) == len(cm[1]):
            # with a known data page Ghidra shows the absolute direct address; MAME the offset
            cg = (cg[0], [m if (isinstance(x, int) and isinstance(m, int) and x > 0x7F and (x & 0x7F) == m)
                          else x for x, m in zip(cg[1], cm[1])])
        if g[0] == mm[0] and cg == cm:
            same += 1
            continue
        cls = compare.explain(fam, w[0], w2, g, mm)
        if cls:
            explained += 1
            print(f"  explained {a + base:04x} {words}: ghidra {text!r} mame {mm[1]!r} ({cls})")
        else:
            diff += 1
            bad.append(f"  DIFF {a + base:04x} {words}: ghidra {text!r} mame {mm[1]!r}")
    print(f"{os.path.basename(image)}: {same} identical, {explained} explained, {diff} unexplained, "
          f"{missing} not at an unidasm line boundary")
    for b in bad:
        print(b)
    sys.exit(1 if diff else 0)


if __name__ == "__main__":
    main()
