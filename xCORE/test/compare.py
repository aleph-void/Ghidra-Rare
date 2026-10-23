#!/usr/bin/env python3
"""Compare Ghidra linear-sweep output with libLLVM's XCore disassembler.
   compare.py <corpus.bin> <ghidra.txt> <itemsize: 2|4> [maxshow]
For itemsize 2 every halfword is an item; for 4 each 4-byte item is decoded independently."""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llvm_xcore

PCREL = {'bt', 'bf', 'bu', 'bl', 'ldap'}


def norm_num(tok):
    if re.fullmatch(r'-?0x[0-9a-f]+', tok):
        return str(int(tok, 16) & 0xffffffff)
    if re.fullmatch(r'-?\d+', tok):
        return str(int(tok) & 0xffffffff)
    return tok


def norm(text):
    t = text.strip().lower()
    t = re.sub(r'\s*,\s*', ',', t)
    t = re.sub(r'\s+', ' ', t)
    return re.sub(r'-?0x[0-9a-f]+|(?<![\w])-?\d+', lambda m: norm_num(m.group(0)), t)


def llvm_text(b, off):
    n, t = llvm_xcore.dis(b, off)
    if n == 0:
        return 0, 'BAD'
    parts = t.split(None, 1)
    if parts[0] in PCREL:
        ops = parts[1].split(',')
        imm = int(ops[-1].strip())
        ops[-1] = str((off + n + 2 * imm) & 0xffffffff)
        t = parts[0] + ' ' + ','.join(o.strip() for o in ops)
    return n, norm(t)


def main():
    data = open(sys.argv[1], 'rb').read()
    size = int(sys.argv[3])
    maxshow = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    gh = {}
    for line in open(sys.argv[2]):
        p = line.rstrip('\n').split(' ', 2)
        off = int(p[0], 16)
        txt = 'BAD' if p[2].startswith('BAD') else norm(p[2])
        gh[off] = (len(p[1]) // 2, txt)
    total = agree = 0
    mism = collections.Counter()
    examples = collections.defaultdict(list)
    for off in range(0, len(data), size):
        b = data[off:off + size]
        n, lt = llvm_text(b, off)
        gn, gt = gh.get(off, (0, 'MISSING'))
        if gt == 'BAD':
            gn = 0
        total += 1
        if lt == gt and (n == gn or lt == 'BAD'):
            agree += 1
            continue
        key = (lt.split(' ')[0], gt.split(' ')[0])
        mism[key] += 1
        if len(examples[key]) < 3:
            examples[key].append('%s  llvm[%d]: %s | ghidra[%d]: %s' % (b[:max(n, gn, 2)].hex(), n, lt, gn, gt))
    print('items %d  agree %d  (%.4f%%)  mismatches %d' % (total, agree, 100.0 * agree / total, total - agree))
    for k, c in mism.most_common(maxshow):
        print('%7d  llvm=%s ghidra=%s' % (c, k[0], k[1]))
        for e in examples[k]:
            print('           ' + e)


main()
