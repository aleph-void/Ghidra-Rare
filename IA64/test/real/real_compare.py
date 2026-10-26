#!/usr/bin/env python3
"""Compare Ghidra's disassembly of an analysed ELF (IA64RealCheck .dis) with GNU objdump -d.

  real_compare.py <elf> <prefix.dis> <image-base-adjust hex> [--objdump OBJDUMP] [--out DIR]

Every Ghidra instruction in an objdump-disassembled section is matched with objdump's line at the
same slot (Ghidra's slot 2 is bundle+11, objdump's bundle+12) and compared after the same
normalisation as the decode test (test/compare.py). Prints: instructions compared, identical,
different (with buckets), objdump slots Ghidra did not disassemble (coverage)."""
import collections, os, re, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from compare import norm

def main():
    elf, dis, adj = sys.argv[1], sys.argv[2], int(sys.argv[3], 16)
    objdump = sys.argv[sys.argv.index('--objdump') + 1] if '--objdump' in sys.argv else \
        os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump')
    out = subprocess.run([objdump, '-d', elf], capture_output=True, text=True, check=True).stdout
    od = {}
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\t([0-9a-f ]+)\t?(.*)$', line)
        if m:
            txt = re.sub(r'^\[[^\]]*\]', '', m.group(3)).strip()
            txt = re.sub(r'\s*<[^>]*>', '', txt)
            od[int(m.group(1), 16)] = txt
    gh = {}
    for line in open(dis):
        a, txt = line.rstrip('\n').split(' ', 1)
        a = int(a, 16) - adj
        slot = a & 0xf
        if slot == 11:
            a += 1
        gh[a] = txt
    same, diff = 0, collections.Counter()
    examples = collections.defaultdict(list)
    for a, g in gh.items():
        if a not in od:
            continue
        o = od[a]
        # objdump prints IP-relative targets and tags as bare hex link addresses
        mn = o.split()[1] if o.startswith('(') and len(o.split()) > 1 else (o.split() or [''])[0]
        if mn.startswith(('br', 'chk', 'fchkf')) or (mn.startswith('mov') and '=r' in o and
                                                     re.search(r'=r\d+,', o)):
            def fix(m):
                t = m.group(2)
                last = m.end() == len(o) or o[m.end():] == ';;'
                if re.fullmatch(r'b[0-7]', t) or (not last and re.fullmatch(
                        r'[rf](\d|[1-9]\d|1[01]\d|12[0-7])|p(\d|[1-5]\d|6[0-3])', t)):
                    return m.group(0)
                return '%s0x%x' % (m.group(1), int(t, 16) + adj)
            o = re.sub(r'([ =,])([0-9a-f]+)(?=(,|;;|$))', fix, o)
        ng, no = norm(g, 'g'), norm(o, 'o')
        if ng == no:
            same += 1
        else:
            key = (ng[1] if ng else 'BAD', no[1] if no else o.split(' ')[0])
            diff[key] += 1
            if len(examples[key]) < 3:
                examples[key].append('%x  G: %s  O: %s' % (a, g, o))
    # coverage: objdump slots (non-empty text) without a Ghidra instruction
    missing = sorted(a for a, t in od.items() if t and a not in gh)
    # bundles whose slots are all nop / break 0 / data8 are alignment padding
    bundles = collections.defaultdict(list)
    for a in missing:
        bundles[a & ~0xf].append(od[a])
    pad = 0
    for b, ts in bundles.items():
        if all(re.match(r'(nop\.\w|break\.\w 0x0|data8)', t.lstrip('(p0123456789) ')) for t in ts):
            pad += len(ts)
    if '--missing' in sys.argv:
        start = prev = None
        for a in missing + [None]:
            if a is not None and prev is not None and a - prev <= 16:
                prev = a
                continue
            if start is not None:
                print('missing %x-%x' % (start, prev))
            start = prev = a
    print('compared %d, identical %d, different %d, objdump slots not disassembled by Ghidra %d '
          '(%d of them in nop-only padding bundles)' %
          (same + sum(diff.values()), same, sum(diff.values()), len(missing), pad))
    for k, n in diff.most_common():
        print('  %5d %s <-> %s' % (n, k[0], k[1]))
        for e in examples[k]:
            print('        ' + e)
    return 0

if __name__ == '__main__':
    sys.exit(main())
