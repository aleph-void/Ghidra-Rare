#!/usr/bin/env python3
"""Extract the DSP56100 family benchmark programs (DSP56100 Family Manual, Appendix B) from the
manual's text (pdftotext -layout) into one assembler source per benchmark.

    extract156.py <fm100.txt> <outdir>

The programs are Motorola's published benchmark code (also distributed on the Dr. BuB
bulletin board). They are used only as local test inputs: nothing extracted is committed.
Each file gets the appendix's equates and an ORG P:$40, as the appendix's prologue does.
"""
import os
import re
import sys

NOISE = re.compile(r"Freescale Semiconductor|For More Information|Go to: www|^\s*MOTOROLA\s|"
                   r"^\s*B\s*-\s*\d+\s|FIRST SET OF BENCHMARKS|SECOND SET OF BENCHMARKS|"
                   r"^\s*(B-\d+|MOTOROLA)\s*$|Table B-|USA/Europe|Hong Kong|Literature Distribution|"
                   r"Motorola Ltd|Mfax|INTERNET|Tokyo|Phoenix|Tai Po|Japan|Denver|Colorado|Arizona")


def main():
    lines = open(sys.argv[1], errors="replace").read().split("\n")
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    start = next(i for i, l in enumerate(lines) if re.match(r"^\s+APPENDIX B\s*$", l))
    body = lines[start:]
    # equates of the appendix prologue (two columns)
    equ = {}
    for l in body[:200]:
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s+(?:EQU|equ)\s+(\S+)", l):
            equ.setdefault(m.group(1), m.group(2))
    # benchmark sections
    sec = []
    for i, l in enumerate(body):
        m = re.match(r"^\s{30,40}(B\.[23]\.\d+)\s{3,}(\S.*)$", l)
        if m and i > 150:
            sec.append((i, m.group(1), m.group(2).strip()))
    sec.append((len(body), None, None))
    files = []
    for k in range(len(sec) - 1):
        i0, num, title = sec[k]
        i1 = sec[k + 1][0]
        src = []
        for l in body[i0 + 1:i1]:
            if NOISE.search(l) or not l.strip():
                continue
            if re.match(r"^\s*Freescale Semiconductor, Inc\.\.\.", l):
                continue
            code = l[34:] if len(l) > 34 else l.strip()
            code = code.rstrip()
            if not code.strip():
                continue
            # drop the cycle columns written as ";1   1" comments
            src.append(code.replace("…", "...").replace("’", "'"))
        name = "b" + num[2:].replace(".", "_")
        path = os.path.join(out, name + ".asm")
        with open(path, "w") as f:
            f.write(";%s %s\n" % (num, title))
            for k2, v in equ.items():
                f.write("%-12s equ %s\n" % (k2, v))
            f.write("\torg p:$40\n")
            for s in src:
                if s[0] in " \t":
                    f.write("\t%s\n" % s.strip())
                else:
                    f.write("%s\n" % s)
            f.write("\tend\n")
        files.append(path)
    print("\n".join(files))


if __name__ == "__main__":
    main()
