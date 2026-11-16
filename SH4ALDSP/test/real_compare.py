#!/usr/bin/env python3
"""(From aleph-void/ghidra-sh, MIT.)  Compare Ghidra's analysed instructions (RealCheck.java listing) with `objdump -d` of the same
ELF at the same addresses.   real_compare.py <objdump.txt> <ghidra.dis> [label] [delta]
delta: Ghidra address minus objdump address (a shared object linked at 0 is loaded higher).
Instructions are compared after compare.py's normalisation.  Prints totals, the difference
classes and examples; exit 1 if any difference is unexplained."""
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare as C  # noqa: E402  (compare.py runs main() only as a script)


def read_od(path, delta):
    out = {}
    for line in open(path, errors="replace"):
        m = re.match(r"^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} )+)\s*(?:\t(.*))?$", line)
        if not m or m.group(3) is None:
            continue
        txt = re.sub(r"\s*<[^>]*>", "", m.group(3).split("\t! ")[0]).strip()
        txt = re.sub(r"\s+", " ", txt)
        if txt.startswith(".word"):
            txt = None
        elif " " in txt:
            mn, ops = txt.split(" ", 1)
            parts = ops.split(",")
            # branch and PC-relative operands are bare hex addresses (shift by the load delta)
            if mn in ("bra", "bsr", "bt", "bf", "bt.s", "bf.s", "mova", "mov.w", "mov.l", "ldrs", "ldre") and \
                    re.fullmatch(r"[0-9a-f]+", parts[0]):
                parts[0] = "0x%x" % (int(parts[0], 16) + delta)
            txt = mn + " " + ",".join(parts)
        out[int(m.group(1), 16) + delta] = (txt, len(m.group(2).split()))
    return out


def refetch(a, n, delta):
    import subprocess
    cmd = os.environ["RC_OBJDUMP"].split() + ["--start-address=%#x" % a, "--stop-address=%#x" % (a + n)]
    path = os.environ["RC_OBJDUMP_FILE"]
    txt = subprocess.run(cmd + [path], capture_output=True, text=True).stdout
    tmp = path + ".one.txt"
    open(tmp, "w").write(txt)
    return read_od(tmp, delta).get(a + delta)


def read_ghidra(path):
    out = {}
    for line in open(path):
        a, hx, txt = line.rstrip("\n").split(" ", 2)
        out[int(a, 16)] = (txt, len(hx) // 2)
    return out


def main():
    delta = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
    od = read_od(sys.argv[1], delta)
    gh = read_ghidra(sys.argv[2])
    label = sys.argv[3] if len(sys.argv) > 3 else ""
    same = 0
    classes = defaultdict(list)
    for a in sorted(gh):
        g_txt, g_len = gh[a]
        o = od.get(a)
        if o is None and os.environ.get("RC_OBJDUMP"):
            # objdump's linear sweep went out of step here (a 32-bit DSP prefix word in a literal
            # pool takes the next word): disassemble the instruction on its own
            o = refetch(a - delta, g_len, delta)
        if o is None:
            classes["UNEXPLAINED: no objdump instruction at this address"].append((a, "-", g_txt))
            continue
        o_txt, o_len = o
        if o_txt is None:
            classes["UNEXPLAINED: objdump has no instruction here (.word)"].append((a, ".word", g_txt))
            continue
        if o_len == g_len and (C.exact_key(g_txt) == C.exact_key(o_txt) or C.norm(g_txt) == C.norm(o_txt)):
            same += 1
            continue
        classes["UNEXPLAINED: differs"].append((a, o_txt, g_txt))
    total = len(gh)
    unexpl = sum(len(v) for k, v in classes.items() if k.startswith("UNEXPLAINED"))
    for k in sorted(classes, key=lambda k: -len(classes[k])):
        print(f"{len(classes[k]):6d}  {k}")
        for a, o, g in classes[k][:8]:
            print(f"        {a:08x} objdump: {o:<40} ghidra: {g}")
    print(f"== {label}: {total} Ghidra instructions: {same} same as objdump, "
          f"{total - same - unexpl} explained, {unexpl} unexplained")
    sys.exit(1 if unexpl else 0)


if __name__ == "__main__":
    main()
