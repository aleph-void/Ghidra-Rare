#!/usr/bin/env python3
"""Compare Ghidra's Alpha disassembly with GNU objdump's, word by word.

  compare.py <ghidra.txt> <objdump.txt> [examples-per-class] [--regs unix|nt|vms]

ghidra.txt: DumpDisasm.java output ("<off> <word> <text>").
objdump.txt: `objdump -D -b binary -m alpha[:evN]` output.
Prints exact/semantic agreement and every difference class with examples.
"""
import os, re, sys
from collections import Counter, defaultdict

UNIX = "v0 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 fp a0 a1 a2 a3 a4 a5 t8 t9 t10 t11 ra pv at gp sp zero".split()
NT = "v0 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 fp a0 a1 a2 a3 a4 a5 t8 t9 t10 t11 ra t12 at gp sp zero".split()
VMS = "r0 r1 r2 r3 r4 r5 r6 r7 r8 r9 r10 r11 r12 r13 r14 r15 r16 r17 r18 r19 r20 r21 r22 r23 r24 ai ra pv r28 fp sp rz".split()
args = [a for a in sys.argv[1:] if not a.startswith("--")] if __name__ == "__main__" else []
regs = "unix"
entries = None
for i, a in enumerate(sys.argv if __name__ == "__main__" else []):
    if a == "--regs":
        regs = sys.argv[i + 1]
        args.remove(regs)
    if a == "--entries":   # --entries <alpha-opc.txt> <ev4|ev5|ev6>: per-table-entry check
        entries = (sys.argv[i + 1], sys.argv[i + 2])
        args.remove(entries[0]); args.remove(entries[1])
GREG = {"unix": UNIX, "nt": NT, "vms": VMS}[regs]
GMAP = {n: f"r{i}" for i, n in enumerate(GREG)}
GMAP.update({"fzero": "f31", "fz": "f31"})
OBJDUMP = UNIX[:27] + ["t12"] + UNIX[28:]  # objdump calls $27 t12, not pv
OMAP = {n: f"r{i}" for i, n in enumerate(OBJDUMP)}
nex = int(args[2]) if len(args) > 2 else 5

def num(t):
    try:
        v = int(t, 0)
    except ValueError:
        return None
    return str(v & 0xffffffffffffffff)

def norm_tok(t, rmap):
    t = t.strip().lower()
    if t.startswith("$f"):
        return "f" + t[2:]
    if t.startswith("$") and t[1:].isdigit():
        return "r" + t[1:]
    if t in rmap:
        return rmap[t]
    n = num(t)
    return n if n is not None else t

def norm(text, rmap):
    text = text.strip()
    parts = text.split(None, 1)
    mn = parts[0].lower()
    ops = parts[1] if len(parts) > 1 else ""
    toks = [x for x in re.split(r"([,()+])", ops) if x.strip()]
    return " ".join([mn] + [norm_tok(t, rmap) for t in toks])

# 21064 internal processor registers: Ghidra prints names, objdump the 5-bit index
EV4IPR = {}
for lst in ("tb_tag itb_pte iccsr itb_pte_temp exc_addr sl_rcv itbzap itbasm itbis ps exc_sum pal_base hirr sirr astrr ibox15 hier sier aster sl_clr ibox20 ibox21 sl_xmit ibox23 ibox24 ibox25 ibox26 ibox27 ibox28 ibox29 ibox30 ibox31",
            "tb_ctl abox1 wdtb_pte dtb_pte_temp mm_csr va dtbzap dtbasm dtbis biu_addr biu_stat abox11 dc_stat fill_addr abox_ctl alt_mode cc cc_ctl biu_ctl fill_syndrome bc_tag flush_ic abox22 flush_ic_asm abox24 abox25 abox26 abox27 abox28 abox29 abox30 abox31",
            " ".join(f"paltemp{i}" for i in range(32))):
    for i, n in enumerate(lst.split()):
        EV4IPR[n] = str(i)

# CALL_PAL names: objdump's OSF/1 names plus the names the module prints for --regs <os>
PALNAMES = {"halt": 0, "draina": 2, "imb": 0x86, "bpt": 0x80, "bugchk": 0x81, "callsys": 0x83,
            "rduniq": 0x9e, "wruniq": 0x9f, "gentrap": 0xaa}
GPALNAMES = dict(PALNAMES)
_sinc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "languages", f"alpha_pal_{regs}.sinc")
for line in open(_sinc):
    m = re.match(r':(\S+)\s+is opcode=0x00 & pcode=(0x[0-9a-f]+)', line)
    if m:
        GPALNAMES[m.group(1).replace('^"', "").replace('"', "").lower()] = int(m.group(2), 16)

def canon(t, pal=PALNAMES):
    """Map a normalized line to a canonical form: pseudo-ops and aliases expanded."""
    f = t.split()
    mn, ops = f[0], [x for x in f[1:] if x not in (",",)]
    q = ""
    if "/" in mn:
        mn, q = mn.split("/", 1)
        q = "/" + q
    # 21064 IPR names -> index
    ops = [EV4IPR.get(o, o) for o in ops]
    if "+" in ops:  # hw_mtpr/ai ra, abox+ibox: objdump prints the shared index once
        ops = [o for o in ops if o != "+"]
        if len(set(ops[1:])) == 1:
            ops = ops[:2]
    alias = {"or": "bis", "andnot": "bic", "jcr": "jsr_coroutine", "hw_coroutine": "hw_jcr",
             "chmk": "callsys"}
    mn = alias.get(mn, mn)
    pf = {"prefetch": ("ldl", "r31"), "prefetch_en": ("ldq", "r31"), "prefetch_m": ("lds", "f31"),
          "prefetch_men": ("ldt", "f31")}
    if mn in pf:
        mn, r = pf[mn]
        ops = [r] + ops
    if mn == "bsr" and len(ops) == 1:
        ops = ["r31"] + ops
    if mn in ("negl", "negq", "sextl", "not") and len(ops) == 2:
        mn = {"negl": "subl", "negq": "subq", "sextl": "addl", "not": "ornot"}[mn]
        ops = ["r31"] + ops
    if mn in ("negf", "negg", "negs", "negt") and len(ops) == 2:
        mn = "sub" + mn[3]
        ops = ["f31"] + ops
    if mn == "mov" and len(ops) == 2:
        mn, ops = "bis", ["r31"] + ops
    if mn == "bis" and len(ops) == 3 and ops[0] == ops[1] and ops[0].startswith("r"):
        ops = ["r31"] + ops[1:]
    if mn == "nop" and not ops:
        mn, ops = "bis", ["r31", "r31", "r31"]
    if mn == "clr" and len(ops) == 1:
        mn, ops = "bis", ["r31", "r31"] + ops
    if mn == "fmov" and len(ops) == 2:
        mn, ops = "cpys", [ops[0], ops[0], ops[1]]
    if mn == "fneg" and len(ops) == 2:
        mn, ops = "cpysn", [ops[0], ops[0], ops[1]]
    if mn == "fabs" and len(ops) == 2:
        mn, ops = "cpys", ["f31"] + ops
    if mn == "fclr" and len(ops) == 1:
        mn, ops = "cpys", ["f31", "f31"] + ops
    if mn == "fnop" and not ops:
        mn, ops = "cpys", ["f31", "f31", "f31"]
    if mn == "unop" and not ops:
        mn, ops = "ldq_u", ["r31", "0", "(", "r30", ")"]
    if mn in ("lda", "ldah") and len(ops) == 2:
        ops = ops + ["(", "r31", ")"]
    if mn == "br" and len(ops) == 1:
        ops = ["r31"] + ops
    if mn == "ret" and not ops:
        ops = ["r31", "(", "r26", ")", "1"]
    if mn == "ret" and len(ops) == 3:   # ret (rb)
        ops = ["r31"] + ops + ["0"]
    if mn == "rpcc" and len(ops) == 2 and ops[1] == "r31":
        ops = ops[:1]
    if mn == "call_pal" and len(ops) == 1:
        return "call_pal " + ops[0]
    if mn + q in pal and not ops:
        return "call_pal " + str(pal[mn + q])
    return " ".join([mn + q] + ops)

def known_objdump_bug(word, gn, on):
    """Differences traced to GNU objdump 2.45 bugs (see README):
    - EV5 HW_LD/HW_ST: EV5HWMEM_MASK is 0xF800, so bit 10 (load LOCK / store COND) is never
      decoded although the table has the hw_ldl/l, hw_stl/c entries for it.
    - EV4 HW_ST: the 0xE entry is misspelled "hw_stq/par" (the longword form is hw_stl/par)."""
    op = word >> 26
    g, o = gn.split(), on.split()
    if op in (0x1b, 0x1f) and word & 0x400 and g[1:] == o[1:]:
        gm = g[0][:-1] if g[0].endswith(("l", "c")) and "/" in g[0] else g[0]
        if gm.endswith("/"):
            gm = gm[:-1]
        if gm == o[0]:
            return True
    if op == 0x1f and (word >> 12) & 0xf == 0xe and g[0] == "hw_stl/par" and o[0] == "hw_stq/par" and g[1:] == o[1:]:
        return True
    return False

def load_ghidra(p):
    d = {}
    for line in open(p):
        off, w, text = line.rstrip("\n").split(" ", 2)
        d[int(off, 16)] = (w, None if text.startswith("BAD") else text)
    return d

def load_objdump(p):
    d = {}
    for line in open(p):
        m = re.match(r"\s*([0-9a-f]+):\t([0-9a-f ]+)\t(.*)$", line)
        if not m:
            continue
        text = m.group(3).replace("\t", " ").strip()
        # ".long" and the raw "palNN <function>" form are objdump's undecoded words
        d[int(m.group(1), 16)] = None if re.match(r"\.long|pal1[9bdef]\b", text) else text
    return d

def main():
    g, o = load_ghidra(args[0]), load_objdump(args[1])
    cnt = Counter()
    classes = defaultdict(list)
    status = {}
    for off in sorted(g):
        w, gt = g[off]
        ot = o.get(off)
        status[off] = "ok"
        if gt is None and ot is None:
            status[off] = "undef"
            cnt["both undefined"] += 1
            continue
        if gt is None:
            status[off] = "bad"
            cnt["objdump only"] += 1
            classes[("objdump-only", ot.split()[0])].append((w, "-", ot))
            continue
        if ot is None:
            status[off] = "bad"
            cnt["ghidra only"] += 1
            classes[("ghidra-only", gt.split()[0].lower())].append((w, gt, "-"))
            continue
        gn, on = norm(gt, GMAP), norm(ot, OMAP)
        if gn == on:
            cnt["exact"] += 1
        elif known_objdump_bug(int(w, 16), gn, on):
            cnt["objdump bug"] += 1
            classes[("objdump-bug", gt.split()[0].lower() + " / " + ot.split()[0])].append((w, gt, ot))
        elif canon(gn, GPALNAMES) == canon(on):
            cnt["semantic"] += 1
            classes[("semantic", gt.split()[0].lower() + " / " + ot.split()[0])].append((w, gt, ot))
        else:
            status[off] = "bad"
            cnt["differ"] += 1
            classes[("differ", gt.split()[0].lower() + " / " + ot.split()[0])].append((w, gt, ot))
    total = len(g)
    ref = cnt["exact"] + cnt["semantic"] + cnt["objdump bug"] + cnt["differ"] + cnt["objdump only"]
    print(f"compared {total} words: objdump decodes {ref}; exact {cnt['exact']} ({100*cnt['exact']/max(1,ref):.2f}%), "
          f"exact+semantic {cnt['exact']+cnt['semantic']} ({100*(cnt['exact']+cnt['semantic'])/max(1,ref):.2f}%), "
          f"objdump bug {cnt['objdump bug']}, "
          f"differ {cnt['differ']}, objdump-only {cnt['objdump only']}, ghidra-only {cnt['ghidra only']}, both undefined {cnt['both undefined']}")
    for k, v in sorted(classes.items(), key=lambda kv: (kv[0][0] in ("semantic", "objdump-bug"), -len(kv[1]))):
        print(f"  [{len(v):5d}] {k[0]}: {k[1]}")
        for w, gt, ot in v[:nex]:
            print(f"           {w}  ghidra: {gt:40s} objdump: {ot}")

    if entries:
        # Every opcode-table entry that applies to this processor: all 16 words generated for it
        # (table.bin layout, gen_corpus.py) must decode and agree with objdump.
        want = {"ev4": 0x2, "ev5": 0x4, "ev6": 0x8}[entries[1]]
        n = good = 0
        bad = []
        for i, line in enumerate(open(entries[0])):
            f = line.split()
            flags = int(f[3], 16)
            if f[0] in ("pal19", "pal1b", "pal1d", "pal1e", "pal1f", "call_pal", "pal"):
                continue   # raw catch-all forms
            if flags & 0xe and not flags & want:
                continue   # PALcode entry of another implementation
            n += 1
            st = [status.get(4 * (16 * i + k)) for k in range(16)]
            if all(x == "ok" for x in st):
                good += 1
            else:
                bad.append(f"{f[0]} ({st.count('ok')}/16 ok, {st.count('undef')} undefined)")
        print(f"table entries for {entries[1]}: {good}/{n} decode and agree on all 16 words")
        for b in bad:
            print("   entry not fully covered:", b)


if __name__ == "__main__":
    main()
