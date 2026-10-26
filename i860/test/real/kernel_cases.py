#!/usr/bin/env python3
"""Emulator cases for test/real/kernels.s (calls into the assembled program). Expected values
are the mathematical results of each kernel, chosen to be exact in single precision.
    kernel_cases.py > kernel_cases.txt"""
import struct

A, BV, Z, ZN, P, PN = 0x30000, 0x30400, 0x30800, 0x30820, 0x30840, 0x30860
out = []


def f32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def f64(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def dot_case(func, n):
    a = [float((i * 3) % 7 - 2) for i in range(n)]
    b = [float((i * 5) % 11 - 4) for i in range(n)]
    out.append(f"case {func}_{n}")
    out.append(f"func {func}")
    for i in range(n + 1):           # dot_dual loads one element past the end
        out.append(f"set ram:{A + 4 * i:x}/4 {f32(a[i] if i < n else 0.0):#x}")
        out.append(f"set ram:{BV + 4 * i:x}/4 {f32(b[i] if i < n else 0.0):#x}")
    out.extend([f"set r16 {A:#x}", f"set r17 {BV:#x}", f"set r18 {n:#x}"])
    out.append(f"expect f8 {f32(sum(x * y for x, y in zip(a, b))):#x}")
    out.append("end")


for n in (1, 2, 3, 4, 7, 16, 33):
    dot_case("dot_pipe", n)
    dot_case("dot_dual", n)

# zbuf8: 8 pixels; a pixel is replaced when its new z is not farther (new <= old)
zold = [100, 5, 300, 7, 0xffff, 1, 50, 50]
znew = [99, 6, 300, 9, 0x8000, 0, 51, 49]
pix = [0x1111 * (i + 1) & 0xffff for i in range(8)]
pnew = [0xa000 + i for i in range(8)]
out += ["case zbuf8", "func zbuf8"]
for k, (base, vals) in enumerate(((Z, zold), (ZN, znew), (P, pix), (PN, pnew))):
    for half in range(2):
        v = 0
        for i in range(4):
            v |= vals[4 * half + i] << (16 * i)
        out.append(f"set ram:{base + 8 * half:x}/8 {v:#x}")
out += [f"set r16 {Z:#x}", f"set r17 {ZN:#x}", f"set r18 {P:#x}", f"set r19 {PN:#x}"]
zmin = [min(o, n) for o, n in zip(zold, znew)]
pres = [pn if n <= o else p for o, n, p, pn in zip(zold, znew, pix, pnew)]
for base, vals in ((Z, zmin), (P, pres)):
    for half in range(2):
        v = 0
        for i in range(4):
            v |= vals[4 * half + i] << (16 * i)
        out.append(f"expect ram:{base + 8 * half:x}/8 {v:#x}")
out += ["expect PS 0x1", "end"]

# poly_dual(x) = 3x^3 + 2x^2 + x + 5
for x in (0.0, 1.0, 2.0, -1.5):
    out += [f"case poly_dual_{x}", "func poly_dual", f"set fd8 {f64(x):#x}",
            f"expect fd8 {f64(3 * x ** 3 + 2 * x ** 2 + x + 5):#x}", "end"]
print("\n".join(out))
