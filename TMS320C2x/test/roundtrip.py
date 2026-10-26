#!/usr/bin/env python3
"""Round trip: re-assemble Ghidra's disassembly with an independent assembler and compare words.

    roundtrip.py c5x <c5xasm> <records.txt> <ghidra dump dir g/> <workdir>
    roundtrip.py c2x <asl dir> <records.txt> <ghidra dump dir g/> <workdir>

c5x: c5xtools' c5xasm (MIT, conformance-checked against TI's assembler) assembles every decoded
record at its own address (.ps). c2x: the Macroassembler AS (asl, CPU 320C25). The re-assembled
words are compared with the original record. Differences are classified: bits the instruction
ignores (next-AR bits when N = 0), equivalent condition encodings, and assembler limitations; the
rest are reported. Exit status 1 on an unexplained difference.
"""
import collections
import os
import re
import subprocess
import sys

REC = 4
CHUNK = 16384
MMR = {n: i + 4 for i, n in enumerate(
    "IMR GREG IFR PMST RPTC BRCR PASR PAER TREG0 TREG1 TREG2 DBMR AR0 AR1 AR2 AR3 AR4 AR5 AR6 AR7 "
    "INDX ARCR CBSR1 CBER1 CBSR2 CBER2 CBCR BMAR".split())}


def load_ghidra(gdir, nrec):
    res = {}
    for f in sorted(os.listdir(gdir)):
        m = re.match(r"c(\d+)\.bin\.txt$", f)
        if not m:
            continue
        base = int(m.group(1)) * CHUNK
        for line in open(os.path.join(gdir, f)):
            a, n, t = line.rstrip("\n").split(" ", 2)
            a = int(a, 16)
            if a % REC == 0 and not t.startswith("BAD"):
                res[base + a // REC] = (int(n), t.strip())
    return res


def to_c5xasm(text):
    mn, _, rest = text.partition(" ")
    ops = rest.split(",") if rest else []
    out = []
    for i, o in enumerate(ops):
        # memory-mapped register names Ghidra shows for page-0 direct operands
        if o in MMR and not (o == "BMAR" and mn in ("BLDD", "BLPD")) and not (i == 0 and mn in ("LAR", "SAR")) and not (
                i > 0 and ops[i - 1].startswith("*")) and not (o.startswith("AR") and i == len(ops) - 1 and
                                                              any(x.startswith("*") for x in ops)):
            o = hex(MMR[o])
        out.append(o)
    return mn + (" " + ",".join(out) if out else "")


def to_asl(text):
    mn, _, rest = text.partition(" ")
    rest = re.sub(r"0x([0-9a-f]+)", lambda m: "0" + m.group(1) + "h", rest)
    rest = rest.replace("#", "")
    if mn == "LDPK":
        k = int(rest.replace("h", ""), 16)
        if k > 0xFF and k & 0x7F:
            # AS reads such LDPK operands as data addresses and shifts them right by 7
            rest = "0%Xh" % ((k << 7) & 0xFFFF)
    if mn == "CONF":
        # TMS320C26-only instruction
        return "cpu 320C26\n\tCONF " + rest + "\n\tcpu 320C25"
    if mn == "MPYK":
        v = int(rest.replace("h", ""), 16) if not rest.startswith("-") else -int(rest[1:].replace("h", ""), 16)
        rest = str(v)
    return mn + (" " + rest if rest else "")


COND_BITS = 0x3FF


def cond_sets(low10):
    tp, b = low10 >> 8, low10 & 0xFF
    zs, ls, vs, cs = (b >> 7) & 1, (b >> 6) & 1, (b >> 5) & 1, (b >> 4) & 1
    zm, lm, vm, cm = (b >> 3) & 1, (b >> 2) & 1, (b >> 1) & 1, b & 1
    if lm:
        zl = {"neg"} if ls else {"pos"}
        if zm and zs:
            zl.add("zero")
    elif zm:
        zl = {"zero"} if zs else {"neg", "pos"}
    else:
        zl = {"neg", "pos", "zero"}
    return (tp, frozenset(zl), (vm, vs if vm else 0), (cm, cs if cm else 0))


def classify(fam, orig, new):
    w, n = orig[0], new[0]
    if fam == "c5x" and (w >> 13) == 7 and (w >> 10) & 3 != 1 or fam == "c5x" and (w >> 12) in (0xE, 0xF) and \
            ((w >> 10) & 3) == 1:
        if (w & ~COND_BITS) == (n & ~COND_BITS) and cond_sets(w & COND_BITS) == cond_sets(n & COND_BITS) and \
                orig[1:] == new[1:]:
            return "equivalent condition encoding (unmasked state bits / alternative Z,L form)"
    if fam == "c5x" and w in (0xBE81, 0xBE82, 0xBE83) and n == 0xBFB0 + 0x10 * (w - 0xBE81) and orig[1:] == new[1:]:
        return "c5xasm encodes AND/OR/XOR #lk,16 as shift 0 (BFx0); SPRU056D Table 6-4 gives BE81h-BE83h"
    if (w & 0x80) and not (w & 0x08) and (w ^ n) == (w & 7) and orig[1:] == new[1:]:
        return "next-AR bits 2-0 ignored when N = 0"
    return None


def main():
    fam, tool, recs_path, gdir, work = sys.argv[1:6]
    recs = [tuple(int(x, 16) for x in l.split()) for l in open(recs_path)]
    g = load_ghidra(gdir, len(recs))
    os.makedirs(work, exist_ok=True)
    order = sorted(g)
    words = {}
    errs = []
    chunks = sorted(set(r // CHUNK for r in order))
    for c in chunks:
        rs = [r for r in order if r // CHUNK == c]
        src = os.path.join(work, "rt%02d.asm" % c)
        with open(src, "w") as f:
            if fam == "c2x":
                f.write("\tcpu 320C25\n")
            for r in rs:
                n, t = g[r]
                a = (r % CHUNK) * REC
                if fam == "c5x":
                    f.write(f"\t.ps {a:#x}\n\t{to_c5xasm(t)}\n")
                else:
                    f.write(f"\torg 0{a:X}h\n\t{to_asl(t)}\n")
        base = c * CHUNK * REC
        if fam == "c5x":
            p = subprocess.run([tool, src, "-v50", "-q"], capture_output=True, text=True)
            for line in p.stdout.splitlines():
                m = re.match(r"P ([0-9A-F]+) ([0-9A-F]{4})", line)
                if m:
                    words[base + int(m.group(1), 16)] = int(m.group(2), 16)
            errs += [l for l in p.stderr.splitlines() if l.strip() and not l.startswith("c5xasm ")]
        else:
            asl = os.path.join(tool, "asl")
            lst = os.path.join(work, "rt%02d.lst" % c)
            subprocess.run([asl, "-q", "-L", "-olist", lst, src, "-o", os.path.join(work, "rt.p")],
                           capture_output=True, text=True)
            for line in open(lst, errors="replace"):
                m = re.match(r"\s*\d+/\s*([0-9A-F]+) :((?: [0-9A-F]{4})+)", line)
                if m:
                    a = int(m.group(1), 16)
                    for k, x in enumerate(m.group(2).split()):
                        words[base + a + k] = int(x, 16)
            errs += [l for l in open(lst, errors="replace") if "error" in l.lower()]
    same = 0
    cls = collections.Counter()
    bad = collections.defaultdict(list)
    for r in order:
        n, t = g[r]
        a = r * REC
        orig = recs[r][:n]
        new = tuple(words.get(a + k, -1) for k in range(n))
        if orig == new:
            same += 1
            continue
        c = classify(fam, orig, new) if -1 not in new else None
        if c:
            cls[c] += 1
        else:
            bad[t.split(" ")[0]].append((orig, new, t))
    nb = sum(len(v) for v in bad.values())
    print(f"{fam} round trip: {len(order)} decoded records, {same} re-assemble identically, "
          f"{sum(cls.values())} explained, {nb} unexplained; assembler messages: {len(errs)}")
    for k, v in cls.most_common():
        print(f"  explained {v:6d}  {k}")
    for k, v in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print(f"  UNEXPLAINED {len(v):6d}  {k}")
        for orig, new, t in v[:4]:
            print("      " + " ".join("%04x" % x for x in orig) + "  ->  " +
                  " ".join("%04x" % x if x >= 0 else "----" for x in new) + f"   {t!r}")
    for e in errs[:10]:
        print("  asm: " + e.strip())
    sys.exit(1 if nb else 0)


if __name__ == "__main__":
    main()
