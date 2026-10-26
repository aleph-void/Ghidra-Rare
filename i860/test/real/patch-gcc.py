#!/usr/bin/env python3
"""Fixes applied to the GCC 4.0.4 i860 port before building it (test/real/build-toolchain.sh).
The port was obsolete in 4.0 and does not build or compile ordinary C without these:
  1. i860.c: build_int_cst() lost its third argument in 4.0 (three calls in va_start).
  2. i860.h/i860.md: the special REG+REG load patterns use the "m" constraint, which this GCC
     no longer accepts for REG+REG addresses (they are not legitimate because st has no index
     form), so reload_cse_simplify_operands aborts ("insn does not satisfy its constraints").
     A machine constraint 'Q' (an indexed memory reference) replaces "m" on those patterns.
  3. i860.h: MOVE_MAX 16 makes move_by_pieces_ninsns abort on structure copies; use 8.
  4. t-i860: build libgcc and crtstuff with -fno-guess-branch-probability (the branch predictor
     runs the RTL loop analysis, which aborts on the port's compare patterns), and leave the
     DWARF unwinder out of libgcc (C only; it does not compile with this port).
Usage: patch-gcc.py <gcc-4.0.4 source dir>"""
import re
import sys

g = sys.argv[1] + "/gcc/config/i860/"


def edit(name, fn):
    p = g + name
    s = open(p).read()
    t = fn(s)
    if t != s:
        open(p, "w").write(t)


edit("i860.c", lambda s: s.replace("build_int_cst (NULL_TREE, off, 0)", "build_int_cst (NULL_TREE, off)")
     .replace("UNITS_PER_WORD, 0)", "UNITS_PER_WORD)"))


def h(s):
    s = s.replace("#define MOVE_MAX 16\n", "#define MOVE_MAX 8\n")
    if "EXTRA_CONSTRAINT" not in s:
        s += ("\n/* Ghidra-Rare test toolchain: 'Q' is an indexed (REG+REG) memory reference. */\n"
              "#define EXTRA_CONSTRAINT(OP, C) ((C) == 'Q' && indexed_operand (OP, GET_MODE (OP)))\n"
              "#define EXTRA_MEMORY_CONSTRAINT(C, STR) ((C) == 'Q')\n")
    return s


edit("i860.h", h)
edit("i860.md", lambda s: re.sub(r'"indexed_operand" "(=?)m"', r'"indexed_operand" "\1Q"', s))


def t(s):
    if "fno-guess-branch-probability" not in s:
        s += ("\nTARGET_LIBGCC2_CFLAGS = -fno-guess-branch-probability\n"
              "CRTSTUFF_T_CFLAGS = -fno-guess-branch-probability\n"
              "LIB2ADDEH =\nLIB2ADDEHSTATIC =\nLIB2ADDEHSHARED =\n")
    return s


edit("t-i860", t)
