#!/usr/bin/env python3
"""Compare Ghidra's slot disassembly (IA64DumpSlots.java) with GNU objdump on the same image.

  compare.py <image.bin> <ghidra.txt> <report-dir> [--objdump OBJDUMP]

Both sides are normalised to (predicate, mnemonic, operand tokens, stop): numbers compare as
64-bit values (objdump prints decimal immediates and hex addresses, Ghidra hex), Ghidra's slot 2
address bundle+11 is matched with objdump's bundle+12, and "data8"/"BAD" mean undecodable.
Writes summary.txt, diff.txt (all differences) and buckets.txt (differences grouped by mnemonic
pair) and prints the summary. Differences are then classified (EXPLAINED below); the exit status
is 1 only if an unexplained difference remains.
"""
import collections, os, re, subprocess, sys

OBJDUMP = os.path.expanduser('~/.cache/ghidra-rare-scratch/tools/binutils-all/bin/objdump')

def run_objdump(path, objdump):
    out = subprocess.run([objdump, '-D', '-b', 'binary', '-m', 'ia64-elf64', path],
                         capture_output=True, text=True, check=True).stdout
    res = {}
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\t([0-9a-f ]+)\t?(.*)$', line)
        if not m:
            continue
        a = int(m.group(1), 16)
        txt = re.sub(r'^\[[^\]]*\]', '', m.group(3)).strip()
        res[a] = txt
    return res

def num(tok):
    try:
        v = int(tok, 0)
    except ValueError:
        return None
    return v & 0xffffffffffffffff

def norm(text, side):
    """-> (qp, mnemonic, tokens, stop) or None for undecodable"""
    t = text.strip()
    if side == 'o':
        if not t or t.startswith('data8') or t.startswith('(bad)'):
            return None
        stop = t.endswith(';;')
        if stop:
            t = t[:-2].rstrip()
        qp = 0
        m = re.match(r'\(p(\d+)\)\s*(.*)$', t)
        if m:
            qp, t = int(m.group(1)), m.group(2)
    else:
        if t == 'BAD':
            return None
        stop = t.endswith(';;')
        if stop:
            t = t[:-2].rstrip()
        qp = 0
        m = re.match(r'(.*?)\s*\(p(\d+)\)$', t)
        if m:
            t, qp = m.group(1), int(m.group(2))
    parts = t.split(None, 1)
    mn = parts[0]
    ops = parts[1].replace(' ', '') if len(parts) > 1 else ''
    toks = [x for x in re.split(r'([=,\[\]])', ops) if x != '']
    toks = [num(x) if num(x) is not None else x for x in toks]
    return (qp, mn, tuple(toks), stop)

# Differences that are understood (see README "Decode differences"):
EXPLAINED = [
    ('post-2.3 Itanium 9500 extension: objdump reads hint.m as mov dahr / a shifted immediate',
     lambda g, o, gt, ot: g == 'hint.m' and o in ('hint.m', 'mov', 'objdump invalid')),
    ('post-2.3 Itanium 9500 extension: objdump decodes lfetch with bit 19 set as lfetch.count',
     lambda g, o, gt, ot: g.startswith('lfetch') and o.startswith('lfetch.count')),
    ('reserved mux1 permutation (Table 4-74 reservedQPa); objdump prints the raw mbtype',
     lambda g, o, gt, ot: g == 'ghidra BAD' and o == 'mux1'),
]

ADDR32 = False

def mask32(n):
    """32-bit address space (IA64:BE:32): branch targets and tags wrap at 32 bits"""
    if n is None or not ADDR32:
        return n
    mn = n[1]
    if mn.startswith(('br', 'chk', 'fchkf')) or (mn.startswith('mov') and any(
            isinstance(t, str) and re.fullmatch(r'b[0-7]', t) for t in n[2][:1])):
        return (n[0], mn, tuple(t & 0xffffffff if isinstance(t, int) else t for t in n[2]), n[3])
    return n

def main():
    global ADDR32
    ADDR32 = '--addr32' in sys.argv
    img, gh, rep = sys.argv[1], sys.argv[2], sys.argv[3]
    objdump = sys.argv[sys.argv.index('--objdump') + 1] if '--objdump' in sys.argv else OBJDUMP
    os.makedirs(rep, exist_ok=True)
    od = run_objdump(img, objdump)
    rows = []
    for line in open(gh):
        a, s, txt = line.rstrip('\n').split(' ', 2)
        rows.append((int(a, 16), int(s), txt))
    stats = collections.Counter()
    buckets = collections.defaultdict(list)
    diffs = []
    for a, s, gtxt in rows:
        oa = a + 1 if s == 2 else a
        otxt = od.get(oa, '')
        g, o = mask32(norm(gtxt, 'g')), mask32(norm(otxt, 'o'))
        if g is None and o is None:
            stats['both invalid'] += 1
        elif g == o:
            stats['exact'] += 1
        else:
            if g is None:
                key = ('ghidra BAD', o[1])
            elif o is None:
                key = (g[1], 'objdump invalid')
            else:
                key = (g[1], o[1])
            stats['different'] += 1
            buckets[key].append((a, s, gtxt, otxt))
            diffs.append('%x %d | %s | %s' % (a, s, gtxt, otxt))
    explained = collections.Counter()
    unexplained = 0
    for key, items in buckets.items():
        for why, rule in EXPLAINED:
            if rule(key[0], key[1], items[0][2], items[0][3]):
                explained[why] += len(items)
                break
        else:
            unexplained += len(items)
    total = sum(stats.values())
    summ = ['slots: %d' % total] + ['%s: %d' % kv for kv in sorted(stats.items())]
    summ.append('buckets: %d' % len(buckets))
    for why, n in explained.most_common():
        summ.append('  explained %d: %s' % (n, why))
    summ.append('unexplained: %d' % unexplained)
    open(os.path.join(rep, 'summary.txt'), 'w').write('\n'.join(summ) + '\n')
    open(os.path.join(rep, 'diff.txt'), 'w').write('\n'.join(diffs) + '\n')
    with open(os.path.join(rep, 'buckets.txt'), 'w') as f:
        for key, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            f.write('%6d  %s  <->  %s\n' % (len(items), key[0], key[1]))
            for a, s, g, o in items[:3]:
                f.write('        %x/%d  G: %s   O: %s\n' % (a, s, g, o))
    print('\n'.join(summ))
    return 0 if unexplained == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
