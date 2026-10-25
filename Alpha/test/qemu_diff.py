#!/usr/bin/env python3
"""Differential p-code check against QEMU: random operate-format instructions with random
inputs, executed by qemu-alpha (user mode) and by Ghidra's p-code emulator.

  qemu_diff.py gen <alpha-opc.txt> <outdir> [count] [seed]
      writes qd.elf (static Linux/Alpha executable), qd.txt (one line per test: index, word)
  qemu_diff.py cmp <outdir> <qemu.bin> <ghidra.bin> [examples]
      compares the two output dumps per test and buckets differences by mnemonic

Each test block loads t0..t3 and f1..f3 from an input record, executes the instruction under
test (sources t0/t1/zero or f1/f2/f31, destination t2/t3 or f3), and stores t0..t3, f1..f3 to
an output record. At the end the program writes the output area to stdout (callsys write) and
exits. QemuDiff.java runs the same image in Ghidra's emulator up to the write and dumps the
same area. Floating-point inputs are normal doubles of moderate magnitude so that unqualified
IEEE instructions do not trap; rounding-mode and trap qualifiers are not exercised.
"""
import os, random, struct, sys

BASE = 0x10000000
REC = 56                      # 4 integer + 3 FP quadwords
T0, T1, T2, T3, S0, S1, V0, A0, A1, A2, ZERO = 1, 2, 3, 4, 9, 10, 0, 16, 17, 18, 31

def mem(op, ra, disp, rb):
    return op << 26 | ra << 21 | rb << 16 | (disp & 0xffff)

def opl(op, fn, ra, lit, rc):
    return op << 26 | ra << 21 | (lit & 0xff) << 13 | 1 << 12 | fn << 5 | rc

LDQ, STQ, LDT, STT, LDA, LDAH = 0x29, 0x2d, 0x23, 0x27, 0x08, 0x09

def load_addr(reg, addr):
    lo = addr & 0xffff
    lo = lo - 0x10000 if lo >= 0x8000 else lo
    hi = (addr - lo) >> 16
    return [mem(LDAH, reg, hi, ZERO), mem(LDA, reg, lo, reg)]

# operate-format opcodes whose results are architecturally defined and modelled in p-code
# (MVI byte/word min/max/PERR are pcodeops; AMASK/IMPLVER are implementation specific)
INT_OPS = {0x10, 0x11, 0x12, 0x13, 0x1c}
SKIP = {"amask", "implver", "perr", "minsb8", "minsw4", "minub8", "minuw4", "maxub8", "maxuw4",
        "maxsb8", "maxsw4", "itoff"}
FP_OK = {"addt", "subt", "mult", "divt", "adds", "subs", "muls", "divs", "cmpteq", "cmptlt",
         "cmptle", "cmptun", "cvtqt", "cvtqs", "cvttq/c", "cvtts", "cpys", "cpysn", "cpyse",
         "cvtlq", "cvtql", "fcmoveq", "fcmovne", "fcmovlt", "fcmovge", "fcmovle", "fcmovgt",
         "itoft", "itofs", "sqrtt", "sqrts", "ftoit", "fmov", "fneg", "fabs", "fclr",
         "negt", "negs", "fnop", "unpkbw", "pkwb"}

ZA, ZB, ZC, RBA, RCA = 7, 8, 9, 12, 13    # binutils alpha_operands[] indices (see gen_corpus.py)

def gen(opc, out, count, seed):
    rng = random.Random(seed)
    entries = []
    for line in open(opc):
        f = line.split()
        name, op, mask, flags = f[0], int(f[1], 16), int(f[2], 16), int(f[3], 16)
        operands = [int(x) for x in f[4:]]
        major = op >> 26
        if flags & 0xe or name.endswith("/v") or "/sv" in name:
            continue           # PALcode; integer-overflow traps would kill the run
        if major in INT_OPS and name not in SKIP or major in (0x14, 0x16, 0x17) and name in FP_OK \
                or name in ("ftoit", "ftois"):
            entries.append((name, op, mask, operands))
    code = []
    tests = []
    data = bytearray()
    specials = [0, 1, 2, 0xff, 0x7fffffff, 0x80000000, 0xffffffff, 0x8000000000000000,
                0xffffffffffffffff, 0x7fffffffffffffff]
    code += load_addr(S0, 0)          # patched below
    code += load_addr(S1, 0)
    for i in range(count):
        name, op, mask, operands = entries[i % len(entries)]
        w = op
        fpop = (op >> 26) in (0x14, 0x16, 0x17) or name in ("ftoit", "ftois")
        for lo, choices in ((21, [T0, T1, ZERO]), (16, [T0, T1, ZERO]), (0, [T2, T3])):
            if (mask >> lo) & 31 == 0:
                c = choices
                if fpop:
                    c = {21: [1, 2, 31], 16: [1, 2, 31], 0: [3]}[lo]
                    if name in ("itoft", "itofs") and lo == 21:
                        c = [T0, T1]
                    if name in ("ftoit", "ftois") and lo == 0:
                        c = [T2, T3]
                    if name.startswith("div") and lo == 16:
                        c = [1, 2]          # never divide by f31 (zero)
                w |= rng.choice(c) << lo
        if not fpop and not (mask >> 12) & 1 and rng.random() < 0.4 and ZB not in operands:
            w = (w & ~(0xff << 13) & ~(31 << 16)) | 1 << 12 | rng.getrandbits(8) << 13
        ra = (w >> 21) & 31
        for o in operands:
            if o == ZA:
                w |= 31 << 21
            elif o == ZB:
                w |= 31 << 16
            elif o == ZC:
                w |= 31
            elif o == RBA:
                w = (w & ~(31 << 16)) | ra << 16
            elif o == RCA:
                w = (w & ~31) | ra
        tests.append((i, name, w))
        for k in range(4):
            code.append(mem(LDQ, T0 + k, 8 * k, S0))
        for k in range(3):
            code.append(mem(LDT, 1 + k, 32 + 8 * k, S0))
        code.append(w)
        for k in range(4):
            code.append(mem(STQ, T0 + k, 8 * k, S1))
        for k in range(3):
            code.append(mem(STT, 1 + k, 32 + 8 * k, S1))
        code.append(mem(LDA, S0, REC, S0))
        code.append(mem(LDA, S1, REC, S1))
        # inputs: integers mixing small, boundary and random values; non-zero doubles of
        # moderate magnitude (no traps for unqualified IEEE ops); single-representable values
        # for S-precision ops; positive radicands for SQRT
        for k in range(4):
            v = rng.choice(specials) if rng.random() < 0.25 else rng.getrandbits(64)
            if rng.random() < 0.25:
                v = rng.getrandbits(8)
            if name == "itofs":   # the module converts by value: use normal single-precision bits
                v = struct.unpack("<I", struct.pack("<f", rng.uniform(-1e6, 1e6)))[0]
            data += struct.pack("<Q", v)
        for k in range(3):
            x = rng.choice([1.0, -2.5, 3.0, 0.5]) if rng.random() < 0.2 else rng.uniform(-1e6, 1e6)
            if name.startswith("sqrt"):
                x = abs(x)
            if name.split("/")[0] in ("adds", "subs", "muls", "divs", "sqrts", "negs", "ftois"):
                x = struct.unpack("<f", struct.pack("<f", x))[0]
            data += struct.pack("<d", x)
    stop_index = len(code)
    code += [mem(LDA, V0, 4, ZERO), mem(LDA, A0, 1, ZERO)]
    code += load_addr(A1, 0)           # patched below
    code += load_addr(A2, 0)
    code += [0x00000083, mem(LDA, V0, 1, ZERO), mem(LDA, A0, 0, ZERO), 0x00000083]
    code_size = 4 * len(code)
    hdr = 0x1000
    inp = BASE + hdr + ((code_size + 0xfff) & ~0xfff)
    outp = inp + count * REC
    code[0:2] = load_addr(S0, inp)
    code[2:4] = load_addr(S1, outp)
    code[stop_index + 2:stop_index + 4] = load_addr(A1, outp)
    code[stop_index + 4:stop_index + 6] = load_addr(A2, count * REC)
    image = bytearray(hdr) + b"".join(struct.pack("<I", w) for w in code)
    image += bytes(inp - BASE - len(image)) + data + bytes(count * REC)
    # ELF64 header + one RWX PT_LOAD covering everything, entry at the first instruction
    eh = struct.pack("<4sBBBBB7xHHIQQQIHHHHHH", b"\x7fELF", 2, 1, 1, 0, 0, 2, 0x9026, 1,
                     BASE + hdr, 64, 0, 0, 64, 56, 1, 64, 0, 0)
    ph = struct.pack("<IIQQQQQQ", 1, 7, 0, BASE, BASE, len(image), len(image), 0x10000)
    image[0:len(eh)] = eh
    image[64:64 + len(ph)] = ph
    open(f"{out}/qd.elf", "wb").write(image)
    os.chmod(f"{out}/qd.elf", 0o755)
    with open(f"{out}/qd.txt", "w") as fh:
        fh.write(f"# stop 0x{BASE + hdr + 4 * stop_index:x} out 0x{outp:x} len {count * REC} "
                 f"in 0x{inp:x}\n")
        for i, name, w in tests:
            fh.write(f"{i} {name} {w:08x}\n")
    print(f"{count} tests over {len(entries)} table entries; stop 0x{BASE + hdr + 4 * stop_index:x}")

def cmp(out, qfile, gfile, nex):
    from collections import Counter, defaultdict
    tests = [l.split() for l in open(f"{out}/qd.txt") if not l.startswith("#")]
    q, g = open(qfile, "rb").read(), open(gfile, "rb").read()
    names = ["t0", "t1", "t2", "t3", "f1", "f2", "f3"]
    ok = 0
    bad = defaultdict(list)
    per = Counter()
    for i, name, w in tests:
        i = int(i)
        qv = struct.unpack_from("<7Q", q, i * REC)
        gv = struct.unpack_from("<7Q", g, i * REC)
        per[name] += 1
        if qv == gv:
            ok += 1
        else:
            d = [f"{names[k]}: qemu {qv[k]:x} ghidra {gv[k]:x}" for k in range(7) if qv[k] != gv[k]]
            bad[name].append((w, d))
    total = len(tests)
    print(f"qemu vs ghidra: {ok}/{total} tests agree ({100 * ok / total:.2f}%), "
          f"{len(per)} mnemonics, {len(bad)} with differences")
    for name, v in sorted(bad.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{len(v):4d}/{per[name]}] {name}")
        for w, d in v[:nex]:
            print(f"         {w}: {'; '.join(d)}")

if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 20000,
            int(sys.argv[5]) if len(sys.argv) > 5 else 1)
    else:
        cmp(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 3)
