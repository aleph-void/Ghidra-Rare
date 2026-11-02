#!/usr/bin/env python3
"""Assemble the module's own disassembly of every halfword with tc32-elf-as and compare the bytes.

  gas_roundtrip.py <all16.gh> <all16.bin> <workdir> <tc32 bin dir>

all16.gh is Ghidra's linear-sweep listing of the every-halfword corpus (4-byte slots, run-decode.sh).
Each slot's text is placed at its address with .org, assembled, and the resulting halfword compared
with the original. Lines gas rejects are bucketed by mnemonic (exit 1 if any are unexplained).
"""
import collections, os, re, struct, subprocess, sys
gh, binf, w, tb = sys.argv[1:5]
os.makedirs(w, exist_ok=True)
data = open(binf, 'rb').read()
ALU2 = {'tands', 'txors', 'tshftls', 'tshftrs', 'tasrs', 'taddcs', 'tsubcs', 'trotrs', 'tors', 'tmuls', 'tbclrs'}
KEEP2 = {'tnegs': 'tneg', 'tmovns': 'tmovn'}

def to_gas(t):
    """objdump-style text (what the module prints) -> the syntax tc32-elf-as accepts: gas writes the
    flag-setting forms without the trailing s, and the two-operand ALU forms as Rd, Rd, Rm."""
    m = re.match(r'(\S+)\s*(.*)$', t)
    mn, ops = m.group(1), m.group(2)
    o = [x.strip() for x in re.split(r',(?![^\[{]*[\]}])', ops)] if ops else []
    if mn in ALU2 and len(o) == 2:
        return f'{mn[:-1]} {o[0]}, {o[0]}, {o[1]}'
    if mn in KEEP2:
        return f'{KEEP2[mn]} {", ".join(o)}'
    if mn in ('tadds', 'tsubs') and len(o) == 2:
        return f'{mn[:-1]} {o[0]}, {o[0]}, {o[1]}'
    if mn in ('tadds', 'tsubs', 'tshftls', 'tshftrs', 'tasrs', 'tmovs'):
        return f'{mn[:-1]} {", ".join(o)}'
    return t

items = []
for l in open(gh):
    a, b, t = l.rstrip('\n').split(' ', 2)
    a = int(a, 16)
    if a % 4 or t.startswith('BAD'):
        continue
    items.append((a, to_gas(t), t))
src = ['\t.text', '\t.code 16'] if False else ['\t.text']
lineno = {}
for a, t, _ in items:
    src.append(f'\t.org 0x{a:x}')
    lineno[len(src) + 1] = (a, t)
    src.append('\t' + t)
open(f'{w}/rt.s', 'w').write('\n'.join(src) + '\n')
r = subprocess.run([f'{tb}/tc32-elf-as', '-o', f'{w}/rt.o', f'{w}/rt.s'], capture_output=True, text=True)
rej = collections.Counter(); rex = {}
bad_lines = set()
for l in r.stderr.splitlines():
    m = re.match(r'.*rt\.s:(\d+): Error: (.*)', l)
    if m and int(m.group(1)) in lineno:
        n = int(m.group(1)); bad_lines.add(n)
        a, t = lineno[n]; k = t.split()[0] + ': ' + re.sub(r'`.*', '', m.group(2))[:50]
        rej[k] += 1; rex.setdefault(k, t)
if bad_lines:   # gas stops producing output on errors: reassemble without the rejected lines
    keep = [s for i, s in enumerate(open(f'{w}/rt.s').read().split('\n'), 1) if i not in bad_lines]
    open(f'{w}/rt2.s', 'w').write('\n'.join(keep))
    subprocess.run([f'{tb}/tc32-elf-as', '-o', f'{w}/rt.o', f'{w}/rt2.s'], check=True, capture_output=True)
subprocess.run([f'{tb}/tc32-elf-objcopy', '-O', 'binary', '-j', '.text', f'{w}/rt.o', f'{w}/rt.bin'], check=True)
out = open(f'{w}/rt.bin', 'rb').read()
rejected = {lineno[n][0] for n in bad_lines}
same = diff = 0; dex = []; dk = collections.Counter()
bytext = {}
for l in open(gh):
    a_, b_, t_ = l.rstrip('\n').split(' ', 2)
    if int(a_, 16) % 4 == 0 and not t_.startswith('BAD'):
        bytext[int(a_, 16) // 4] = t_

def explain(orig, want, got):
    w = int.from_bytes(want, 'little'); mn = orig.split()[0]
    g = bytext.get(int.from_bytes(got, 'little'))
    if g and to_gas(g) == to_gas(orig):
        return 'alias: gas picks another encoding that the module decodes to the same instruction'
    if mn == 'tmovs' and (w >> 11) == 0x1e:
        return 'tmovs Rd,Rm (shift-by-0 encoding, C kept): gas assembles tmov Rd,Rm as tadds Rd,Rm,#0 (C and V cleared)'
    if mn == 'tserv':
        return 'toolchain inconsistency: gas encodes tserv n as 0xDFnn, objdump decodes 0xCFnn as tserv (0xDFnn is tloadm)'
    if mn == 'tjex':
        return 'tjex with non-zero reserved bits (bit 7 / bits 2:0): gas writes them as zero'
    if (w >> 8) in (0x04, 0x05, 0x06) and not re.search(r'\b(r(8|9|1[0-5])|sl|fp|ip|sp|lr|pc)\b', orig):
        return 'high-register-format tadd/tcmp/tmov with two low registers: gas picks the low-register encoding'
    if mn in ('tsubs', 'tadds') and (w >> 11) == 0x17:
        return ''
    return ''

for a, t, orig in items:
    if a in rejected: continue
    want = data[a:a + 2]; got = out[a:a + 2]
    if want == got: same += 1
    else:
        diff += 1
        e = explain(orig, want, got)
        dk[e or 'UNEXPLAINED ' + orig.split()[0]] += 1
        if not e and len(dex) < 10: dex.append(f'{a:08x} {orig!r} -> gas {t!r}: {want.hex()} -> {got.hex()}')
print(f'gas round trip: {len(items)} module decodes, {same} reassemble to the same halfword, {diff} differ, {sum(rej.values())} rejected by gas')
for k, v in rej.most_common(): print(f'  rejected {v:6d} {k}   e.g. {rex[k]}  (empty register list: gas has no syntax for it)')
for k, v in dk.most_common(): print(f'  differs {v:6d} {k}')
for d in dex: print('  e.g.', d)

sys.exit(1 if any(k.startswith('UNEXPLAINED') for k in dk) or any('{}' not in rex[k] for k in rej) else 0)
