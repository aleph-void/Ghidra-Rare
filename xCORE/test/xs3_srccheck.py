#!/usr/bin/env python3
"""XS3 ground-truth check: compare Ghidra's decoding of XMOS-assembled objects (.S.obj from the
xmos-ai-tools wheel, built by XMOS xcc from lib_nn) against the assembly sources.

  xs3_srccheck.py extract <objdir> <srcdir> <work>     -> <work>/funcs.bin + <work>/funcs.json
  xs3_srccheck.py check   <work> <ghidra.txt>

The objects are relocatable, so pc-relative / symbolic immediates are zero and not compared;
everything else (mnemonic, registers, literal immediates) is.  Dual-issue bundles
"{ a ; b }" are compared as unordered pairs (the assembler places the lanes in a fixed order),
and the assembler's nop padding of lone 16-bit instructions in dual-issue mode is accepted.
"""
import json, os, re, subprocess, sys
from elftools.elf.elffile import ELFFile

PCREL = {'bt', 'bf', 'bu', 'bl', 'ldap', 'bla', 'blat'}


def src_items(path):
    txt = open(path).read()
    txt = txt.replace('#include <xs1.h>', '')
    pp = subprocess.run(['cpp', '-P', '-x', 'assembler-with-cpp', '-D__XS3A__', '-'], input=txt,
                        capture_output=True, text=True).stdout
    lines = []
    for raw in pp.split('\n'):
        s = re.sub(r'//.*', '', raw).strip()
        if not s:
            continue
        # labels (possibly followed by an instruction)
        while True:
            m = re.match(r'^([A-Za-z_.$][\w.$]*):\s*(.*)$', s)
            if not m:
                break
            lines.append(('label', m.group(1)))
            s = m.group(2).strip()
        if not s:
            continue
        if s.startswith('.'):
            lines.append(('dir', s))
            continue
        while s:
            s = s.strip().lstrip(';').strip()
            if not s:
                break
            if s.startswith('{'):
                j = s.index('}')
                parts = [p.strip() for p in s[1:j].split(';') if p.strip()]
                if len(parts) == 1:
                    lines.append(('insn', parts[0]))
                elif parts:
                    lines.append(('bundle', parts))
                s = s[j + 1:]
            else:
                j = min([k for k in (s.find(';'), s.find('{')) if k >= 0] or [len(s)])
                lines.append(('insn', s[:j].strip()))
                s = s[j:]
    return lines


def evalnum(tok):
    t = tok.strip()
    if re.fullmatch(r'[0-9xXa-fA-F()+\-*/ <>|&]+', t) and re.search(r'\d', t):
        try:
            return str(int(eval(t, {'__builtins__': {}})) & 0xffffffff)
        except Exception:
            return None
    return None


def norm_src(ins):
    ins = ins.strip().lower()
    m = re.match(r'(\S+)\s*(.*)', ins)
    mn, ops = m.group(1), m.group(2)
    mn = re.sub(r'_(lu6|lru6|lu10|u6|ru6|u10)$', '', mn)   # explicit encoding-form suffixes
    out = []
    for o in [x.strip() for x in ops.split(',')] if ops else []:
        mm = re.match(r'^(\w+)\[(.*)\]$', o)
        if mm:
            v = evalnum(mm.group(2))
            out.append('%s[%s]' % (mm.group(1), v if v is not None else '?'))
            continue
        if re.fullmatch(r'r\d+|sp|dp|cp|lr', o):
            out.append(o)
            continue
        v = evalnum(o)
        out.append(v if v is not None else '?')
    if mn == 'mov' and len(out) == 2:
        mn, out = 'add', out + ['0']
    if mn in PCREL:
        out = [o if not (i == len(out) - 1) else '?' for i, o in enumerate(out)]
    return mn, out


def norm_gh(txt):
    t = txt.strip().lower()
    m = re.match(r'(\S+)\s*(.*)', t)
    mn, ops = m.group(1), m.group(2)
    out = []
    for o in [x.strip() for x in ops.split(',')] if ops else []:
        o = re.sub(r'-?0x[0-9a-f]+', lambda x: str(int(x.group(0), 16) & 0xffffffff), o)
        out.append(o)
    return mn, out


def match(src, gh):
    smn, sops = src
    gmn, gops = gh
    if smn in ('ldap', 'bl', 'bu') and gmn == 'nop':
        return True   # relocation placeholder in the relocatable object
    if smn != gmn or len(sops) != len(gops):
        return False
    for a, b in zip(sops, gops):
        if a == '?':
            continue
        if a.endswith('[?]') and b.startswith(a[:-3]):
            continue
        if a != b:
            return False
    return True


def extract(objdir, srcdir, work):
    os.makedirs(work, exist_ok=True)
    blob = bytearray()
    funcs = []
    srcs = {}
    for root, _, files in os.walk(srcdir, followlinks=True):
        for f in files:
            if f.endswith('.S'):
                srcs.setdefault(f, os.path.join(root, f))
    for obj in sorted(os.listdir(objdir)):
        if not obj.endswith('.S.obj') or obj[:-4] not in srcs:
            continue
        src = srcs[obj[:-4]]
        items = src_items(src)
        labels = {v for k, v in items if k == 'label'}
        with open(os.path.join(objdir, obj), 'rb') as fh:
            elf = ELFFile(fh)
            symtab = elf.get_section_by_name('.symtab') or next(
                s for s in elf.iter_sections() if s.header.sh_type == 'SHT_SYMTAB')
            for sym in symtab.iter_symbols():
                if sym.name not in labels or not isinstance(sym['st_shndx'], int):
                    continue
                if sym['st_info']['bind'] != 'STB_GLOBAL':
                    continue
                sec = elf.get_section(sym['st_shndx'])
                if not sec.header.sh_flags & 4:
                    continue
                data = sec.data()
                start = sym['st_value']
                code = data[start:]
                while len(blob) % 4:
                    blob += b'\0'
                funcs.append({'obj': obj, 'src': src, 'sym': sym.name, 'off': len(blob), 'len': len(code)})
                blob += code
    open(os.path.join(work, 'funcs.bin'), 'wb').write(bytes(blob))
    json.dump(funcs, open(os.path.join(work, 'funcs.json'), 'w'), indent=1)
    print('%d functions, %d bytes' % (len(funcs), len(blob)))


def check(work, ghtxt):
    funcs = json.load(open(os.path.join(work, 'funcs.json')))
    gh = []
    for line in open(ghtxt):
        p = line.rstrip('\n').split(' ', 2)
        gh.append((int(p[0], 16), p[1], p[2]))
    byoff = {o: i for i, (o, _, _) in enumerate(gh)}
    tot = ok = 0
    bad = []
    for f in funcs:
        items = src_items(f['src'])
        # instructions following the function label until the next data directive / end
        i = [k for k, (t, v) in enumerate(items) if t == 'label' and v == f['sym']][0] + 1
        seq = []
        for t, v in items[i:]:
            if t == 'dir' and re.match(r'\.(word|byte|short|long|ascii|cc_bottom|cc_top|size|align|p2align|globl)\b', v):
                break
            if t == 'insn':
                seq.append([v])
            elif t == 'bundle':
                seq.append(v)
        gi = byoff.get(f['off'])
        if gi is None:
            bad.append('%s: start offset not decoded' % f['sym'])
            continue
        for grp in seq:
            want = [norm_src(x) for x in grp]
            n = len(want)
            got = [norm_gh(gh[gi + k][2]) for k in range(n)]
            good = False
            if n == 1:
                if match(want[0], got[0]):
                    good, used = True, 1
                elif got[0][0] == 'nop' and match(want[0], norm_gh(gh[gi + 1][2])):
                    good, used = True, 2
                elif match(want[0], got[0]) is False and norm_gh(gh[gi + 1][2])[0] == 'nop' and False:
                    pass
            else:
                if (match(want[0], got[0]) and match(want[1], got[1])) or \
                   (match(want[0], got[1]) and match(want[1], got[0])):
                    good, used = True, 2
            tot += 1
            if good:
                ok += 1
                gi += used
                # lone 16-bit instruction padded with a trailing nop
                if n == 1 and used == 1 and gi < len(gh) and norm_gh(gh[gi][2])[0] == 'nop' \
                        and (gh[gi][0] % 4) == 2 and want[0][0] != 'nop':
                    gi += 1
            else:
                bad.append('%s/%s @%x: src %s | ghidra %s' % (
                    os.path.basename(f['src']), f['sym'], gh[gi][0] - f['off'], grp,
                    [gh[gi + k][1] + ' ' + gh[gi + k][2] for k in range(max(n, 2))]))
                # resync: skip as many ghidra items as source items
                gi += n
    print('source instruction groups %d, matched %d (%.2f%%)' % (tot, ok, 100.0 * ok / max(tot, 1)))
    for b in bad[:80]:
        print('  ' + b)


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        check(sys.argv[2], sys.argv[3])
