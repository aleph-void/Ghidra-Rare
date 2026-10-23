#!/usr/bin/env python3
"""Compare Ghidra's analysed listing of a linked xCORE ELF with LLVM's XCore (XS1) disassembler
and check pc-relative targets against the ELF symbols.

    real_compare.py <elf> <listing.txt from RealCheck.java> [maxshow]

* Every instruction Ghidra decoded is re-decoded by libLLVM at the same address. LLVM only knows
  the XS1 ISA and single issue, so for instructions Ghidra decoded in dual-issue mode the
  pc-relative LLVM immediate is rescaled with the XS2 dual-issue rule
  (target = ((addr + 4) & ~3) + 4 * imm) before comparing. Mismatches are grouped by
  (llvm mnemonic, ghidra mnemonic).
* Independent check of the pc-relative rule, per issue mode: the target of every BL/BLRF/BLRB
  must be an ELF FUNC symbol or a Ghidra instruction start, and every branch target must be the
  start of an instruction Ghidra decoded.
* Issue mode vs the $s/$d mapping symbols (issue_map.py): pc-relative instructions decoded in a
  mode that differs from the mapping symbol are counted (other instructions are mode-independent).
"""
import bisect, collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llvm_xcore
from compare import norm, PCREL
from issue_map import regions
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

BRANCH = {'bt', 'bf', 'bu', 'brft', 'brbt', 'brff', 'brbf', 'brfu', 'brbu'}
CALL = {'bl', 'blrf', 'blrb'}
# XS2 re-encodes these XS1 instructions (LLVM prints the XS1 meaning: init/set for TINIT*/TSETR)
REENC = {'init', 'set', 'byterev', 'clz', 'bitrev', 'krestsp', 'kret', 'dret', 'dentsp', 'drestsp'}


def llvm_norm(b, addr, dual):
    n, t = llvm_xcore.dis(b, addr)
    if n == 0:
        return 0, 'BAD'
    parts = t.split(None, 1)
    if parts[0] in PCREL:
        ops = parts[1].split(',')
        imm = int(ops[-1].strip())
        if dual:
            tgt = ((addr + 4) & ~3) + 4 * imm
        else:
            tgt = addr + n + 2 * imm
        ops[-1] = str(tgt & 0xffffffff)
        t = parts[0] + ' ' + ','.join(o.strip() for o in ops)
    return n, norm(t)


def main():
    elf, lst = sys.argv[1], sys.argv[2]
    maxshow = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    funcs = set()
    with open(elf, 'rb') as f:
        for s in ELFFile(f).iter_sections():
            if isinstance(s, SymbolTableSection):
                for sym in s.iter_symbols():
                    if sym['st_info']['type'] == 'STT_FUNC':
                        funcs.add(sym['st_value'])
    regs = regions(elf)
    rst = [r[0] for r in regs]
    rows = []
    for line in open(lst):
        head, _, fn = line.rstrip('\n').partition('\t')
        p = head.split(' ', 3)
        rows.append((int(p[0], 16), bytes.fromhex(p[1]), int(p[2]), p[3]))
    starts = {r[0] for r in rows}

    tot = agree = explained = 0
    mism = collections.Counter()
    ex = collections.defaultdict(list)
    tchk = collections.Counter()
    tbad = []
    wrongmode = 0
    wm_ex = []
    for a, b, d, txt in rows:
        tot += 1
        g = norm(txt)
        n, l = llvm_norm(b, a, d)
        if l == g and n == len(b):
            agree += 1
        else:
            k = (l.split(' ')[0], g.split(' ')[0])
            # LLVM knows XS1 only: XS2/XS3-only opcodes are undefined there, and the XS2
            # re-encodings decode as a different XS1 instruction
            if l == 'BAD' or (k[0] in REENC and k[1] in REENC):
                explained += 1
            mism[k] += 1
            if len(ex[k]) < 3:
                ex[k].append('%08x %s dual=%d  llvm: %s | ghidra: %s' % (a, b.hex(), d, l, g))
        mn = txt.split(' ')[0].lower()
        if mn in BRANCH or mn in CALL:
            m = re.search(r'0x([0-9a-f]+)\s*$', txt)
            if m:
                t = int(m.group(1), 16)
                ok = t in starts or (mn in CALL and t in funcs)
                tchk[(mn in CALL, d, ok)] += 1
                if not ok and len(tbad) < 15:
                    tbad.append('%08x dual=%d %s' % (a, d, txt))
        if mn in BRANCH or mn in CALL or mn == 'ldap':
            i = bisect.bisect_right(rst, a) - 1
            if i >= 0 and regs[i][0] <= a < regs[i][1] and regs[i][2] != d:
                wrongmode += 1
                if len(wm_ex) < 10:
                    wm_ex.append('%08x dual=%d (map says %d) %s' % (a, d, regs[i][2], txt))

    print('instructions %d  agree with LLVM(XS1) %d (%.2f%%)  XS2/XS3-only or re-encoded %d  unexplained %d'
          % (tot, agree, 100.0 * agree / max(tot, 1), explained, tot - agree - explained))
    for k, c in mism.most_common(maxshow):
        print('%7d  llvm=%s ghidra=%s' % (c, k[0], k[1]))
        for e in ex[k]:
            print('           ' + e)
    for call in (True, False):
        for d in (0, 1):
            okc, bad = tchk[(call, d, True)], tchk[(call, d, False)]
            if okc + bad:
                print('%s targets, %s issue: %d on an instruction%s, %d not'
                      % ('call' if call else 'branch', 'dual' if d else 'single', okc,
                         '/FUNC symbol' if call else '', bad))
    for e in tbad:
        print('    ' + e)
    print('pc-relative instructions decoded in a different mode than the $s/$d mapping symbols: %d'
          % wrongmode)
    for e in wm_ex:
        print('    ' + e)


if __name__ == '__main__':
    main()
