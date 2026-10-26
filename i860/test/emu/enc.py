"""Minimal i860 instruction encoder for the emulator cases, written from the Programmer's
Reference Manual's appendix B (not from the module). Registers are numbers; branch targets are
absolute addresses, encoded relative to the instruction's address."""

NOP = 0xa0000000                       # shl r0,r0,r0
FNOP = 0xb0000000                      # shrd r0,r0,r0
DFNOP = 0xb0000200                     # d.fnop


def reg(op6, s1, s2, d, low=0):
    return (op6 << 26) | (s2 << 21) | (d << 16) | (s1 << 11) | low


def imm(op6, v, s2, d):
    return (op6 << 26) | (s2 << 21) | (d << 16) | (v & 0xffff)


def split(op6, s1, off, s2, low=0):
    """st.x / bte / btne / bla: offset bits 15-11 in the dest field, 10-0 in bits 10-0."""
    off &= 0xffff
    return (op6 << 26) | (s2 << 21) | ((off >> 11) << 16) | (s1 << 11) | (off & 0x7ff) | low


ALU = {"addu": 0x20, "subu": 0x22, "adds": 0x24, "subs": 0x26, "shl": 0x28, "shr": 0x2a,
       "shra": 0x2e, "and": 0x30, "andnot": 0x34, "or": 0x38, "xor": 0x3c}
HIGH = {"andh": 0x33, "andnoth": 0x37, "orh": 0x3b, "xorh": 0x3f}


def alu(name, a, s2, d, immediate=False):
    if name in HIGH:
        return imm(HIGH[name], a, s2, d)
    return imm(ALU[name] + 1, a, s2, d) if immediate else reg(ALU[name], a, s2, d)


def shrd(s1, s2, d, D=0):
    return reg(0x2c, s1, s2, d, D << 9)


def ld(size, off, s2, d, index=False):
    op = 0x00 if size == "b" else 0x04
    bit0 = 1 if size == "l" else 0
    if index:
        return reg(op, off, s2, d, bit0)
    return imm(op + 1, (off & ~1) | bit0 if size != "b" else off, s2, d)


def st(size, s1, off, s2):
    op = 0x03 if size == "b" else 0x07
    bit0 = 1 if size == "l" else 0
    return split(op, s1, (off & ~1) | bit0 if size != "b" else off, s2)


FSZ = {"l": 0b010, "d": 0b000, "q": 0b100}


def fls(op6, size, off, s2, fd, inc=False, index=False):
    low = FSZ[size] | (1 if inc else 0)
    if index:
        return reg(op6, off, s2, fd, low)
    mask = 3 if size == "l" else 7
    return imm(op6 + 1, (off & ~mask) | low, s2, fd)


def fld(size, off, s2, fd, inc=False, index=False):
    return fls(0x08, size, off, s2, fd, inc, index)


def fst(size, fd, off, s2, inc=False, index=False):
    return fls(0x0a, size, off, s2, fd, inc, index)


def pfld(size, off, s2, fd, inc=False, index=False):
    return fls(0x18, size, off, s2, fd, inc, index)


def pst(fd, off, s2, inc=False):
    return imm(0x0f, (off & ~7) | (1 if inc else 0), s2, fd)


def ixfr(s1, fd):
    return reg(0x02, s1, 0, fd)


def ldc(creg, d):
    return reg(0x0c, 0, creg, d)


def stc(s1, creg):
    return reg(0x0e, s1, creg, 0)


def lbr(op6, pc, target):
    return (op6 << 26) | (((target - pc - 4) >> 2) & 0x3ffffff)


def br(pc, t): return lbr(0x1a, pc, t)
def call(pc, t): return lbr(0x1b, pc, t)
def bc(pc, t): return lbr(0x1c, pc, t)
def bct(pc, t): return lbr(0x1d, pc, t)
def bnc(pc, t): return lbr(0x1e, pc, t)
def bnct(pc, t): return lbr(0x1f, pc, t)


def sbr(op6, s1, s2, pc, target):
    return split(op6, s1, (target - pc - 4) >> 2, s2)


def bte(s1, s2, pc, t, immediate=False): return sbr(0x17 if immediate else 0x16, s1, s2, pc, t)
def btne(s1, s2, pc, t, immediate=False): return sbr(0x15 if immediate else 0x14, s1, s2, pc, t)
def bla(s1, s2, pc, t): return sbr(0x2d, s1, s2, pc, t)
def bri(s1): return reg(0x10, s1, 0, 0)


def esc(op, s1=0, s2=0, d=0, sz=0):
    return reg(0x13, s1, s2, d, (sz << 9) | op)


def calli(s1): return esc(2, s1=s1)


FPOP = {"fmul": 0x20, "fmlow": 0x21, "frcp": 0x22, "frsqr": 0x23, "pfmul3": 0x24, "fadd": 0x30,
        "fsub": 0x31, "fix": 0x32, "famov": 0x33, "pfgt": 0x34, "pfle": 0x34, "pfeq": 0x35,
        "ftrunc": 0x3a, "fxfr": 0x40, "fiadd": 0x49, "fisub": 0x4d, "faddp": 0x50, "faddz": 0x51,
        "fzchkl": 0x57, "form": 0x5a, "fzchks": 0x5f}


def fp(name, s1, s2, d, prec="ss", P=0, D=0):
    """Floating-point escape; prec gives S and R (for pfle R = 1, for pfgt/pfeq R = 0)."""
    S, R = int(prec[0] == "d"), int(prec[1] == "d")
    if name in ("pfgt", "pfeq"):
        R = 0
    if name == "pfle":
        R = 1
    fop = FPOP[name] if isinstance(name, str) else name
    return (0x12 << 26) | (s2 << 21) | (d << 16) | (s1 << 11) | (P << 10) | (D << 9) | (S << 8) | (R << 7) | fop


def dual(dpc, sub, s1, s2, d, prec="ss", P=1, D=0):
    """pfam/pfsm (P = 1) or pfmam/pfmsm (P = 0) with data-path code dpc (table 8-1)."""
    return fp((sub << 4) | dpc, s1, s2, d, prec, P, D)
