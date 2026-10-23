#!/usr/bin/env python3
"""XMOS issue-mode mapping symbols: "$s.N" starts single-issue code, "$d.N" dual-issue code
(cf. ARM $a/$t). Library helper + CLI:
    issue_map.py <elf>                      print the regions
    issue_map.py <elf> <ghidra-listing>     compare the dual bit Ghidra used per instruction
                                            (RealCheck.java listing format) with the regions
"""
import bisect, sys
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection


def regions(path):
    """Return sorted [(addr, end, dual)] for executable sections."""
    with open(path, 'rb') as f:
        e = ELFFile(f)
        secs = list(e.iter_sections())
        marks = {}
        for s in secs:
            if not isinstance(s, SymbolTableSection):
                continue
            for sym in s.iter_symbols():
                n = sym.name
                if len(n) > 2 and n[0] == '$' and n[1] in 'sd' and n[2] == '.':
                    sh = sym['st_shndx']
                    if isinstance(sh, int) and secs[sh]['sh_flags'] & 4:   # SHF_EXECINSTR
                        marks[(sym['st_value'], sh)] = 1 if n[1] == 'd' else 0
        out = []
        bysec = {}
        for (a, sh), d in marks.items():
            bysec.setdefault(sh, []).append((a, d))
        for sh, lst in bysec.items():
            lst.sort()
            end = secs[sh]['sh_addr'] + secs[sh]['sh_size']
            for i, (a, d) in enumerate(lst):
                nxt = lst[i + 1][0] if i + 1 < len(lst) else end
                if nxt > a:
                    out.append((a, nxt, d))
        out.sort()
        return out


def lookup(regs, addr):
    i = bisect.bisect_right([r[0] for r in regs], addr) - 1
    if i >= 0 and regs[i][0] <= addr < regs[i][1]:
        return regs[i][2]
    return None


def main():
    regs = regions(sys.argv[1])
    if len(sys.argv) == 2:
        for a, e, d in regs:
            print('%08x-%08x %s' % (a, e, 'dual' if d else 'single'))
        return
    starts = [r[0] for r in regs]
    tot = unk = bad = 0
    ex = []
    for line in open(sys.argv[2]):
        p = line.split(' ', 3)
        a, d = int(p[0], 16), int(p[2])
        i = bisect.bisect_right(starts, a) - 1
        m = regs[i][2] if i >= 0 and regs[i][0] <= a < regs[i][1] else None
        tot += 1
        if m is None:
            unk += 1
        elif m != d:
            bad += 1
            if len(ex) < 15:
                ex.append(line.rstrip())
    print('instructions %d  outside mapped regions %d  wrong issue mode %d' % (tot, unk, bad))
    for x in ex:
        print('   ' + x)


if __name__ == '__main__':
    main()
