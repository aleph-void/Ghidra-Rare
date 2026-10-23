#!/usr/bin/env python3
"""Compare Ghidra's *analysed* listing of a real PRU ELF with reference
disassemblers run linearly over the same executable sections.

Usage: real_compare.py --ghidra x.dis --ranges x.ranges [--gnu gnu.txt] [--ti ti.txt]
                       [--label name] [--show N]

Reports, per reference:
  * agreement on every word that both Ghidra (analysis) and the reference
    disassemble (exact and semantic, see compare.py for the normalisation);
  * words the reference decodes but auto-analysis left undisassembled
    (grouped into ranges: unreached code, or data/padding in .text);
  * words Ghidra disassembled that the reference cannot decode
    (= analysis ran into data).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import canon, expand, load, load_gnu  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghidra", required=True)
    ap.add_argument("--ranges", required=True)
    ap.add_argument("--gnu")
    ap.add_argument("--ti")
    ap.add_argument("--label", default="")
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()
    g = load(a.ghidra)
    ranges = []
    for line in open(a.ranges):
        s, e, n = line.split()
        ranges.append((int(s, 16), int(e, 16)))

    def inside(off):
        return any(s <= off < e for s, e in ranges)

    total_words = sum((e - s) // 4 for s, e in ranges)
    out = []
    for refname, path, loader, src in (("gnu", a.gnu, load_gnu, "gnu"), ("ti", a.ti, load, "ti")):
        if not path:
            continue
        ref = {o: v for o, v in loader(path).items() if inside(o)}
        both = exact = sem = 0
        diffs, extra, unreached = [], [], []
        for off in sorted(ref):
            word, rt = ref[off]
            rc = canon(src, rt, off)
            if off not in g:
                if rc != "UNDEF":
                    unreached.append(off)
                continue
            gw, gt = g[off]
            if gw != word:
                diffs.append("%x: word %08x vs %08x" % (off, gw, word))
                continue
            gc = canon("ghidra", gt, off)
            if rc == "UNDEF":
                extra.append("%x: %08x ghidra=%s" % (off, word, gt))
                continue
            both += 1
            if rc == gc:
                exact += 1
                sem += 1
            elif expand(rc, off) == expand(gc, off):
                sem += 1
            else:
                diffs.append("%x: %08x %s=%s | ghidra=%s" % (off, word, refname, rt, gt))
        # group unreached words into ranges
        runs = []
        for off in unreached:
            if runs and runs[-1][1] == off:
                runs[-1][1] = off + 4
            else:
                runs.append([off, off + 4])
        out.append("== %s vs %s: %d code words, Ghidra analysed %d, both decode %d" % (
            a.label, refname, total_words, len(g), both))
        if both:
            out.append("   exact %d (%.2f%%), semantic %d (%.2f%%), mismatches %d" % (
                exact, 100.0 * exact / both, sem, 100.0 * sem / both, len(diffs)))
        out.append("   %s decodes but not disassembled by analysis: %d words in %d ranges %s" % (
            refname, len(unreached), len(runs),
            " ".join("%x-%x" % (s, e) for s, e in runs[:a.show]) + (" ..." if len(runs) > a.show else "")))
        out.append("   analysis disassembled, %s cannot decode: %d" % (refname, len(extra)))
        for x in extra[:a.show]:
            out.append("      " + x)
        for d in diffs[:a.show]:
            out.append("   diff " + d)
    print("\n".join(out))


if __name__ == "__main__":
    main()
