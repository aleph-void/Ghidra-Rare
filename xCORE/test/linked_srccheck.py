#!/usr/bin/env python3
"""Compare Ghidra's analysed listing of a LINKED xCORE image with the assembly sources it was
built from (e.g. lib_xud's dual-issue USB PHY loop in the sw_usb_audio release).

    linked_srccheck.py <elf> <listing.txt from RealCheck.java> <srcdir> [XS2|XS3]

Every source label that is also an ELF symbol starts a block; the block's instructions and
"{ a ; b }" dual-issue bundles are compared with Ghidra's instructions from that address on
(mnemonic, registers, literal immediates; operands built from unknown macros are wildcards).
Because the image is linked, branch / call / ldap operands that name a label are compared with
the absolute target Ghidra computed - an independent check of the single- and dual-issue
pc-relative scaling.
"""
import collections, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xs3_srccheck import norm_src, norm_gh, match as _match
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection

PCREL = {'bt', 'bf', 'bu', 'bl', 'ldap', 'brft', 'brff', 'brbt', 'brbf', 'brfu', 'brbu', 'blrf', 'blrb'}
STOP = re.compile(r'\.(word|byte|short|long|int|ascii|asciiz|space|skip|cc_bottom|size|section|data)\b')


def src_items(path, incdirs, arch):
    stub = tempfile.mkdtemp()
    for h in ('xs1.h', 'platform.h', 'xs1_user.h', 'xs1_kernel.h', 'xs1_registers.h'):
        open(os.path.join(stub, h), 'w').close()
    cmd = ['cpp', '-P', '-x', 'assembler-with-cpp', '-D__XS%sA__' % arch[-1], '-D__XS%s__' % arch[-1],
           '-I', stub] + sum([['-I', d] for d in incdirs], []) + [path]
    pp = subprocess.run(cmd, capture_output=True, text=True).stdout
    items = []
    lines, acc = [], ''
    for raw in pp.split('\n'):          # join "{ a\n b }" bundles written over several lines
        s = re.sub(r'//.*|#.*', '', raw).strip()
        acc = (acc + ' ; ' + s) if acc else s
        if acc.count('{') <= acc.count('}'):
            lines.append(acc)
            acc = ''
    for s in lines:
        while True:
            m = re.match(r'^([A-Za-z_.$][\w.$]*):\s*(.*)$', s)
            if not m:
                break
            items.append(('label', m.group(1)))
            s = m.group(2).strip()
        if not s:
            continue
        if s.startswith('.'):
            items.append(('dir', s))
            continue
        while s:
            s = s.strip().lstrip(';').strip()
            if not s:
                break
            if s.startswith('{'):
                j = s.index('}') if '}' in s else len(s)
                parts = [p.strip() for p in s[1:j].split(';') if p.strip()]
                items.append(('bundle', parts) if len(parts) > 1 else ('insn', parts[0]) if parts else ('dir', ''))
                s = s[j + 1:]
            else:
                j = min([k for k in (s.find(';'), s.find('{')) if k >= 0] or [len(s)])
                items.append(('insn', s[:j].strip()))
                s = s[j:]
    return items


ALIAS = {'brft': 'bt', 'brbt': 'bt', 'brff': 'bf', 'brbf': 'bf', 'brfu': 'bu', 'brbu': 'bu',
         'blrf': 'bl', 'blrb': 'bl', 'ldapf': 'ldap', 'ldapb': 'ldap', 'ldwsp': 'ldw', 'stwsp': 'stw',
         'ldawsp': 'ldaw', 'ldwdp': 'ldw', 'stwdp': 'stw', 'ldawdp': 'ldaw', 'ldwcp': 'ldw'}


def match(src, gh):
    # linked image: no relocation placeholders, so a nop never stands in for bl/bu/ldap
    if gh[0] == 'nop' and src[0] != 'nop':
        return False
    return _match(src, gh)


def want(ins, syms):
    mn, ops = norm_src(ins)
    mn = ALIAS.get(mn, mn)
    raw = [o.strip() for o in (ins.split(None, 1) + [''])[1].split(',')]
    if mn in PCREL and ops:
        ops[-1] = '?'           # numeric operand = raw encoded offset; labels resolved below
        if raw[-1] in syms and len(syms[raw[-1]]) == 1:
            ops[-1] = str(next(iter(syms[raw[-1]])))
    return mn, ops


def main():
    elf, lst, srcdir = sys.argv[1:4]
    arch = sys.argv[4] if len(sys.argv) > 4 else 'XS3'
    syms = collections.defaultdict(set)
    with open(elf, 'rb') as f:
        e = ELFFile(f)
        secs = list(e.iter_sections())
        for s in secs:
            if isinstance(s, SymbolTableSection):
                for sym in s.iter_symbols():
                    if sym.name and isinstance(sym['st_shndx'], int) and secs[sym['st_shndx']]['sh_flags'] & 4:
                        syms[sym.name].add(sym['st_value'])
    gh = []
    for line in open(lst):
        head = line.split('\t')[0]
        p = head.split(' ', 3)
        gh.append((int(p[0], 16), len(p[1]) // 2, int(p[2]), p[3]))
    byaddr = {g[0]: i for i, g in enumerate(gh)}
    incdirs = sorted({r for r, _, fs in os.walk(srcdir) for f in fs if f.endswith(('.h', '.S', '.inc'))})
    srcs = [os.path.join(r, f) for r, _, fs in os.walk(srcdir) for f in fs
            if f.endswith('.S') and 'included' not in r]
    tot = ok = blocks = pcrel = 0
    bad = []
    seen = set()
    for src in sorted(srcs):
        items = src_items(src, incdirs, arch)
        k = 0
        while k < len(items):
            t, v = items[k]
            k += 1
            if t != 'label' or v not in syms or len(syms[v]) != 1:
                continue
            addr = next(iter(syms[v]))
            if addr not in byaddr or (v, addr) in seen:
                continue
            seen.add((v, addr))
            blocks += 1
            gi = byaddr[addr]
            while k < len(items) and items[k][0] != 'label':
                t, v2 = items[k]
                k += 1
                if t == 'dir':
                    if STOP.match(v2):
                        break
                    continue
                grp = [v2] if t == 'insn' else v2
                w = [want(x, syms) for x in grp]
                n = len(w)
                if gi + n > len(gh):
                    break
                # the assembler pads lone 16-bit instructions in dual-issue code with nops (and some
                # sources have nops under #if XUD_CORE_CLOCK etc. that cpp here cannot see)
                skip = 0
                while skip < 8 and gi + skip < len(gh) and w[0][0] != 'nop' and \
                        norm_gh(gh[gi + skip][3])[0] == 'nop' and \
                        (gi + skip + 1 >= len(gh) or gh[gi + skip + 1][0] == gh[gi + skip][0] + 2):
                    if match(w[0], norm_gh(gh[gi + skip][3])):
                        break
                    skip += 1
                got = [norm_gh(gh[gi + skip + j][3]) for j in range(min(n, len(gh) - gi - skip))]
                good, used = False, n + skip
                if len(got) < n:
                    break
                if n == 1:
                    good = match(w[0], got[0])
                else:
                    good = (match(w[0], got[0]) and match(w[1], got[1])) or \
                           (match(w[0], got[1]) and match(w[1], got[0]))
                    if not good and skip:
                        used = n
                tot += 1
                pcrel += sum(1 for x in w if x[0] in PCREL and x[1] and x[1][-1].isdigit())
                if good:
                    ok += 1
                else:
                    bad.append('%s %s @%08x dual=%d: src %s | ghidra %s' % (
                        os.path.basename(src), v, gh[gi][0], gh[gi][2], grp,
                        [gh[gi + j][3] for j in range(min(n, len(gh) - gi))]))
                # next instruction must follow contiguously
                nxt = gi + used
                if nxt >= len(gh) or gh[nxt][0] != gh[nxt - 1][0] + gh[nxt - 1][1]:
                    break
                gi = nxt
    print('source blocks %d, instruction groups %d, matched %d (%.2f%%), label-resolved pc-relative operands %d'
          % (blocks, tot, ok, 100.0 * ok / max(tot, 1), pcrel))
    for b in bad[:60]:
        print('  ' + b)


if __name__ == '__main__':
    main()
