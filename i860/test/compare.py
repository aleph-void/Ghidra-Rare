#!/usr/bin/env python3
"""Compare Ghidra's i860 disassembly with MAME `unidasm -arch i860` (one instruction per word).

  compare.py <mame.txt> <ghidra.txt> [--show N] [--explain]

Both texts are normalized before comparison: '%' prefixes dropped, MAME's r2/r3 written as
sp/fp, Ghidra's register pairs fdN/fqN written as fN, numbers compared by value, MAME's
column padding and glued operands split. Remaining differences are grouped into buckets; with
--explain each bucket is classified against the reasons established from the Programmer's
Reference Manual (see the module README), and the run fails if any difference is unexplained.
"""
import re
import sys
from collections import Counter, defaultdict

MAME_RE = re.compile(r"^([0-9a-f]+): ([0-9a-f]{8})\s+(.*)$")
GH_RE = re.compile(r"^([0-9a-f]+) ([0-9a-f]+) (.*)$")


def num(tok):
    try:
        return str(int(tok, 0))
    except ValueError:
        return tok


def norm_ops(ops):
    ops = ops.replace("%", "").replace(" ", "")
    ops = re.sub(r"\bf[dq](\d+)\b", r"f\1", ops)
    ops = re.sub(r"\br2\b", "sp", ops)
    ops = re.sub(r"\br3\b", "fp", ops)
    ops = re.sub(r"-?0x[0-9a-fA-F]+|-?\b\d+\b", lambda m: num(m.group(0)), ops)
    return ops


def norm_mame(text):
    text = text.strip()
    if text.startswith(".long"):
        return None
    m = re.match(r"(\S+?)(%.*|\s+.*)?$", text)
    mn, ops = m.group(1), (m.group(2) or "")
    # MAME spellings normalized to the manual's (each one is a documented MAME quirk)
    mn = mn.replace("ppfld", "pfld").replace("ppfmul3", "pfmul3").replace("pstd.d", "pst.d")
    mn = re.sub(r"^(d\.)?(p?)fmul3\.dd(ss|sd|ds|dd)$", r"\1pfmul3.dd", mn)
    mn = re.sub(r"^(d\.)?(p?(?:faddp|faddz|form|fzchkl|fzchks))(ss|sd|ds|dd)$", r"\1\2", mn)
    return mn + " " + norm_ops(ops)


def norm_ghidra(text):
    text = text.strip()
    if text.startswith("BAD"):
        return None
    text = text.lstrip("_")          # Ghidra marks delay-slot instructions with "_"
    parts = text.split(" ", 1)
    return parts[0] + " " + norm_ops(parts[1] if len(parts) > 1 else "")


def load(path, rx, norm):
    res = {}
    with open(path) as f:
        for line in f:
            m = rx.match(line.rstrip("\n"))
            if not m:
                continue
            addr = int(m.group(1), 16)
            res[addr] = (m.group(2), norm(m.group(3)))
    return res


def mnem(s):
    return s.split(" ")[0] if s else "-"


def main():
    args = sys.argv[1:]
    show = 3
    explain = "--explain" in args
    global XP
    XP = "--xp" in args
    if "--show" in args:
        show = int(args[args.index("--show") + 1])
    mame = load(args[0], MAME_RE, norm_mame)
    gh = load(args[1], GH_RE, norm_ghidra)
    stats = Counter()
    buckets = defaultdict(list)
    for addr, (word, mt) in sorted(mame.items()):
        g = gh.get(addr)
        gt = g[1] if g else None
        if mt is None and gt is None:
            stats["both invalid"] += 1
            if not manual_problems(int(word, 16), XP):
                buckets[("both reject a valid encoding", "-", "-")].append((addr, word, gt, mt))
        elif mt == gt:
            stats["agree"] += 1
            probs = manual_problems(int(word, 16), XP)
            if probs:
                buckets[("both accept: " + probs[0], mnem(gt), mnem(mt))].append((addr, word, gt, mt))
        else:
            key = ("ghidra-only" if mt is None else "mame-only" if gt is None else "differ",
                   mnem(gt), mnem(mt))
            buckets[key].append((addr, word, gt, mt))
            stats["different"] += 1
    total = sum(stats.values())
    print(f"{total} words: " + ", ".join(f"{k} {v}" for k, v in sorted(stats.items())))
    unexplained = 0
    allreasons = Counter()
    for key, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        reasons = classify(key, items) if explain else None
        if explain and reasons is None:
            unexplained += len(items)
        if reasons:
            allreasons.update(reasons)
        print(f"  {len(items):7d}  {key[0]:11s} ghidra={key[1]:14s} mame={key[2]:14s}"
              + ("  [explained]" if reasons else "  [UNEXPLAINED]" if explain else ""))
        for addr, word, gt, mt in items[:show]:
            print(f"           {word}  ghidra: {gt}   mame: {mt}")
    if explain:
        agg = Counter()
        for r, n in allreasons.items():
            agg[re.sub(r"code \d+ undefined", "code undefined", r)] += n
        print("reasons:")
        for r, n in agg.most_common():
            print(f"  {n:7d}  {r}")
    if explain:
        print(f"unexplained: {unexplained}")
        sys.exit(1 if unexplained else 0)


# ---- reference rules from the Programmer's Reference Manual (240875-001) ----------------------
# Used only to explain differences: for every word on which Ghidra and MAME disagree, list the
# manual rules the encoding breaks. A difference is explained when Ghidra rejects a word that
# breaks a rule (MAME accepts it) and no word that follows every rule is decoded differently.

XP = False
PREC = {0: "ss", 1: "sd", 2: "ds", 3: "dd"}       # (S << 1) | R


def fpregs_ok(word, roles):
    """roles: {field: width in registers}; misaligned pairs/groups are undefined (3.2)."""
    f = {"s1": (word >> 11) & 31, "s2": (word >> 21) & 31, "d": (word >> 16) & 31}
    return all(f[r] % w == 0 for r, w in roles.items())


def fp_rules(word):
    fop, P, S, R = word & 0x7f, (word >> 10) & 1, (word >> 8) & 1, (word >> 7) & 1
    sr = PREC[(S << 1) | R]
    w = {"s": 1, "d": 2}
    bad = []
    if fop < 0x20:                                   # dual operation (8.4, table 8-1)
        if P == 0 and (fop & 0xf) == 0xf:
            return ["reserved PFMAM/PFMSM data-path code 1111 (table 8-1)"]
        if sr == "ds":
            bad.append(".ds not allowed for .p (preface)")
        dpc = fop & 0xf
        # Table 8-1: src1 feeds the multiplier (or KR/KI) for DPC 1,3,5,7,9,b,d,f, else the
        # adder; src2 feeds the multiplier except for DPC 8,a,c,e. Multiplier sources have the
        # source precision, adder sources and all results the result precision.
        roles = {"d": w[sr[1]],
                 "s1": w[sr[0]] if dpc in (1, 3, 5, 7, 9, 0xb, 0xd, 0xf) else w[sr[1]],
                 "s2": w[sr[1]] if dpc in (8, 0xa, 0xc, 0xe) else w[sr[0]]}
        if not fpregs_ok(word, roles):
            bad.append("misaligned register pair (3.2)")
        return bad
    table = {  # fop: (allowed P values, allowed precisions, operand roles by precision)
        0x20: ({0, 1}, {"ss", "sd", "dd"}, "s1s s2s dr"),            # (p)fmul.p
        0x21: ({0}, {"dd"}, "s1s s2s dr"),                           # fmlow.dd
        0x22: ({0}, {"ss", "sd", "dd"}, "s2s dr"),                   # frcp.p
        0x23: ({0}, {"ss", "sd", "dd"}, "s2s dr"),                   # frsqr.p
        0x24: ({1}, {"dd"}, "s1s s2s dr"),                           # pfmul3.dd
        0x30: ({0, 1}, {"ss", "sd", "dd"}, "s1s s2s dr"),            # (p)fadd.p
        0x31: ({0, 1}, {"ss", "sd", "dd"}, "s1s s2s dr"),            # (p)fsub.p
        0x32: ({0, 1}, {"sd", "dd"}, "s1s dr"),                      # (p)fix.v
        0x33: ({0, 1}, {"ss", "sd", "ds", "dd"}, "s1s dr"),          # (p)famov.r
        0x34: ({1}, {"ss", "sd", "ds", "dd"}, "s1s s2s ds"),         # pfgt/pfle (R = gt/le)
        0x35: ({1}, {"ss", "sd", "ds", "dd"}, "s1s s2s ds"),         # pfeq.p (R unused, as pfgt)
        0x3a: ({0, 1}, {"sd", "dd"}, "s1s dr"),                      # (p)ftrunc.v
        0x40: ({0}, {"ss", "sd", "ds", "dd"}, ""),                   # fxfr (scalar)
        0x49: ({0, 1}, {"ss", "dd"}, "s1s s2s dr"),                  # (p)fiadd.w
        0x4d: ({0, 1}, {"ss", "dd"}, "s1s s2s dr"),                  # (p)fisub.w
        0x50: ({0, 1}, None, "s1D s2D dD"),                          # (p)faddp (64-bit)
        0x51: ({0, 1}, None, "s1D s2D dD"),                          # (p)faddz
        0x57: ({0, 1}, None, "s1D s2D dD"),                          # (p)fzchkl
        0x5f: ({0, 1}, None, "s1D s2D dD"),                          # (p)fzchks
        0x5a: ({0, 1}, None, "s1D dD"),                              # (p)form
    }
    if fop not in table:
        return ["reserved floating-point opcode (B-8)"]
    Ps, precs, roles = table[fop]
    if P not in Ps:
        bad.append("P bit not allowed: scalar-only or pipelined-only (B-8)")
    if precs is not None and sr not in precs:
        bad.append(f".{sr} not allowed for this instruction")
    rr = {}
    for r in roles.split():
        fld, kind = r[:-1], r[-1]
        width = {"s": w[sr[0]], "r": w[sr[1]], "D": 2}[kind]
        rr[fld] = width
    if not fpregs_ok(word, rr):
        bad.append("misaligned register pair (3.2)")
    return bad


def manual_problems(word, xp=False):
    op6 = word >> 26
    src1, src2, dest = (word >> 11) & 31, (word >> 21) & 31, (word >> 16) & 31
    if op6 == 0x12:
        return fp_rules(word)
    if op6 == 0x13:                                  # core escape (B-5)
        op, sz = word & 31, (word >> 9) & 3
        bad = []
        if (word >> 5) & 0xf:
            bad.append("core escape reserved bits 8-5 set (B-5)")
        use = {1: "", 2: "s1", 4: "", 7: "", 8: "s2 d sz", 9: "s1 s2 sz", 10: "s2 d sz", 11: "s2 sz"}
        if op not in use or (op >= 8 and not xp):
            return ["reserved core escape opcode (B-5)" if op not in use else "XP-only instruction"]
        u = use[op].split()
        if (src1 and "s1" not in u) or (src2 and "s2" not in u) or (dest and "d" not in u):
            bad.append("unused core escape field not zero (B-5)")
        if (sz and "sz" not in u) or sz == 3:
            bad.append("core escape size bits reserved (B-5)")
        return bad
    if op6 in (0x0c, 0x0e):                          # ld.c / st.c (table 7-1)
        if src2 > (11 if xp else 5):
            return [f"control register code {src2} undefined on the {'XP' if xp else 'XR'}"
                    + (f" (MAME shows code & 7)" if src2 > 7 else " (MAME shows '!')" if src2 > 5 else "")]
        return []
    size = (word >> 1) & 3
    if op6 in (0x08, 0x09, 0x0a, 0x0b, 0x18, 0x19):  # fld, fst, pfld (7.4, 7.5)
        width = 1 if size & 1 else 2 if size == 0 else 4
        if op6 >= 0x18 and width == 4 and not xp:
            return ["pfld.q is XP-only (7.4)"]
        return [] if dest % width == 0 else ["misaligned register pair/group (3.2)"]
    if op6 == 0x0d:                                  # flush: bits 2-1 "must be zero" (B-3), but
        return []                                    # GNU as sets bit 2; they are ignored
    if op6 == 0x0f:                                  # pst.d (7.6)
        bad = ["pst.d size bits not .d"] if size else []
        if dest % 2:
            bad.append("misaligned register pair (3.2)")
        return bad
    if op6 in (0x06, 0x32, 0x36, 0x3a, 0x3e):
        return ["reserved opcode (B-4)"]
    return []


def mame_quirk(word, gt, mt):
    """Known MAME i860 disassembler limitations, each checked against the manual."""
    op6 = word >> 26
    if op6 == 0x13:
        op = word & 31
        if op in (4, 7) and gt and mt is None:
            return "MAME does not decode intovr/unlock (core escape 00100/00111, B-5)"
        if op in (5, 6, 9, 10, 13, 14) or op > 15:
            if mt and mt.split(" ")[0] in ("lock", "calli"):
                return "MAME decodes core escape opcodes by bits 1-0 only (lock/calli)"
        if 8 <= op <= 11 and XP and mt is None:
            return "XP instruction (ldio/stio/ldint/scyc) unknown to MAME"
    if op6 in (0x0c, 0x0e) and XP and 6 <= (word >> 21) & 31 <= 11:
        return "XP control register (bear, ccr, p0-p3) unknown to MAME"
    if op6 in (0x18, 0x19) and XP and (word >> 1) & 3 == 2 and mt is None:
        return "XP pfld.q unknown to MAME"
    if op6 == 0x12 and word & 0x7f == 0x35 and gt and mt and gt.split(" ")[1:] == mt.split(" ")[1:]:
        return "MAME names pfeq's precision from S and R; R is not a precision bit for compares (8.3.2)"
    return None


def classify(key, items):
    """Counter of reasons for a bucket of differences, or None if any item is unexplained."""
    kind = key[0]
    reasons = Counter()
    for addr, word, gt, mt in items:
        w = int(word, 16)
        probs = manual_problems(w, XP)
        q = mame_quirk(w, gt, mt)
        if q:
            reasons[q] += 1
        elif kind == "mame-only" and probs:
            reasons["MAME accepts: " + probs[0]] += 1
        else:
            return None
    return reasons


if __name__ == "__main__":
    main()
