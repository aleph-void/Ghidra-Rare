#!/usr/bin/env python3
"""Minimal "linker" for XMOS xcc relocatable objects -> ELF32 EM_XCORE executable.

    xobj2elf.py <out.elf> <obj> [obj ...]

No XMOS linker (xmap) is available, and Ghidra has no relocation handler for the XMOS
relocation types, so the decompiler sanity check would otherwise see zero placeholders
for every branch and constant-pool reference.  This script lays out the alloc'd section
fragments (xcc emits SHT_LOOS fragments whose sh_info names the parent .text / .cp.* / .dp.*
section), resolves the relocation types that occur in compiler output, adds a "retsp 0"
stub for every undefined symbol, and writes a static ELF with a symbol table.

Relocation types handled (inferred from the instruction at each site, all long/prefixed
forms): 1 abs32 (data), 5 cp-relative word index (LDWCP/LDAWCP), 7 BLACP, 12 LDC absolute,
19 pc-relative branch (BRF*/BRB*), 21 LDAP; short (unprefixed) forms: 8 / 18 pc-relative
branch, 20 LDAP; 22 is an annotation (ignored).  Anything else
is reported and left as is.  A text fragment counts as dual-issue (pc-relative scale 4 from
the next bundle) when it contains DUALENTSP, or no ENTSP but bundle-padding NOPs.
"""
import struct
import sys

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

TEXT_BASE = 0x80000         # xcore.ai RAM base
NOP = 0x17ff                # XS2/XS3 "nop" (0r)
RETSP0 = 0x77c0             # retsp 0 (u6)


def align(x, a):
    return (x + a - 1) & ~(a - 1) if a > 1 else x


def region_of(name):
    if name.startswith('.text'):
        return 'text'
    if name.startswith('.cp.'):
        return 'cp'
    if name.startswith('.dp.') or name.startswith('.data') or name.startswith('.bss'):
        return 'dp'
    return None


def main():
    out = sys.argv[1]
    objs = sys.argv[2:]
    frags = []          # (obj_idx, sec_idx, region, align, data)
    elfs = []
    for oi, path in enumerate(objs):
        e = ELFFile(open(path, 'rb'))
        elfs.append(e)
        secs = list(e.iter_sections())
        pend = {}
        for si, s in enumerate(secs):
            if not (s['sh_flags'] & 2):     # SHF_ALLOC
                continue
            parent = secs[s['sh_info']].name if s['sh_type'] == 'SHT_LOOS' else s.name
            reg = region_of(parent or '')
            if reg is None:
                continue
            a = max(1, s['sh_addralign'], pend.pop(reg, 1))
            if s['sh_size'] == 0:
                pend[reg] = a       # an empty fragment carries a pending .align
                continue
            data = bytes(s['sh_size']) if s['sh_type'] == 'SHT_NOBITS' else s.data()
            frags.append((oi, si, reg, a, data))

    # undefined symbols get a 'retsp 0' stub placed after the text
    defined, undef = set(), set()
    for oi, e in enumerate(elfs):
        for s in e.get_section_by_name('.symtab').iter_symbols():
            if not s.name:
                continue
            if s['st_shndx'] == 'SHN_UNDEF':
                undef.add(s.name)
            elif s['st_info']['bind'] != 'STB_LOCAL':
                defined.add(s.name)
    # "<fn>.nstackwords" / ".maxcores" / ... are XMOS resource-usage constants: resolve to 0
    stub_names = sorted(n for n in undef - defined if '.' not in n)

    # layout: text, stubs, cp, dp
    addr = {}
    dual = {}
    img = bytearray()
    bases = {}
    for reg in ('text', 'cp', 'dp'):
        if reg != 'text':
            img += bytes(align(len(img), 4) - len(img))
        bases[reg] = TEXT_BASE + len(img)
        for oi, si, r, a, data in frags:
            if r != reg:
                continue
            pad = align(len(img), a) - len(img)
            img += (struct.pack('<H', NOP) * (pad // 2) + bytes(pad % 2)) if reg == 'text' else bytes(pad)
            addr[(oi, si)] = TEXT_BASE + len(img)
            if reg == 'text':
                hw = struct.unpack('<%dH' % (len(data) // 2), data[:len(data) & ~1])
                # dual-issue code: has DUALENTSP or bundle-padding NOPs (never emitted in single issue)
                if any(0x7f80 <= h <= 0x7fbf for h in hw):
                    dual[(oi, si)] = True
                elif any(0x7740 <= h <= 0x777f for h in hw):     # ENTSP: single issue
                    dual[(oi, si)] = False
                else:
                    dual[(oi, si)] = NOP in hw
            img += data
        if reg == 'text':
            img += bytes(align(len(img), 4) - len(img))
            stub_addr = {}
            for n in stub_names:
                stub_addr[n] = TEXT_BASE + len(img)
                img += struct.pack('<HH', RETSP0, NOP)
            bases['text_end'] = TEXT_BASE + len(img)
    cp_base, dp_base = bases['cp'], bases['dp']

    # symbols
    syms = {}           # (oi, symidx) -> address
    names = {}          # global name -> address
    out_syms = []       # (name, value, size, type, bind, region)
    for oi, e in enumerate(elfs):
        st = e.get_section_by_name('.symtab')
        for i, s in enumerate(st.iter_symbols()):
            shn = s['st_shndx']
            if shn == 'SHN_ABS':
                syms[(oi, i)] = s['st_value']
            elif isinstance(shn, int) and (oi, shn) in addr:
                v = addr[(oi, shn)] + s['st_value']
                syms[(oi, i)] = v
                if s.name and not s.name.startswith(('.L', '$')):
                    if s['st_info']['bind'] != 'STB_LOCAL':
                        names[s.name] = v
                    out_syms.append((s.name, v, s['st_size'], s['st_info']['type'], s['st_info']['bind']))
    for n, v in stub_addr.items():
        out_syms.append((n, v, 4, 'STT_FUNC', 'STB_GLOBAL'))
    for oi, e in enumerate(elfs):
        st = e.get_section_by_name('.symtab')
        for i, s in enumerate(st.iter_symbols()):
            if s['st_shndx'] == 'SHN_UNDEF' and s.name:
                syms[(oi, i)] = names.get(s.name, stub_addr.get(s.name, 0))

    def rd(a):
        return struct.unpack_from('<H', img, a - TEXT_BASE)[0]

    def wr(a, v):
        struct.pack_into('<H', img, a - TEXT_BASE, v & 0xffff)

    def put_long(a, imm, bits):
        pre, w = rd(a), rd(a + 2)
        if pre >> 10 != 0x3c:
            raise ValueError('no prefix at %x' % a)
        lo = (1 << bits) - 1
        if imm < 0 or imm >= (1 << (bits + 10)):
            raise ValueError('immediate out of range at %x: %d' % (a, imm))
        wr(a, 0xf000 | (imm >> bits))
        wr(a + 2, (w & ~lo) | (imm & lo))

    def pcrel(a, target, bits, scale):
        w = rd(a + 2)
        d = target - (((a + 4) & ~3) if scale == 4 else (a + 4))
        if d % scale:
            raise ValueError('odd branch target at %x' % a)
        if d < 0:
            w |= 1 << 10     # forward -> backward opcode (BRFx/BRBx, LDAPF/LDAPB, BLRF/BLRB)
            d = -d
        else:
            w &= ~(1 << 10)
        wr(a + 2, w)
        put_long(a, d // scale, bits)

    def pcrel_short(a, target, bits, scale):
        w = rd(a)
        d = target - (((a + 4) & ~3) if scale == 4 else (a + 2))
        if d % scale:
            raise ValueError('odd branch target at %x' % a)
        w = (w | (1 << 10)) if d < 0 else (w & ~(1 << 10))
        d = abs(d) // scale
        if d >= (1 << bits):
            raise ValueError('short branch out of range at %x' % a)
        wr(a, (w & ~((1 << bits) - 1)) | d)

    unhandled = {}
    for oi, e in enumerate(elfs):
        secs = list(e.iter_sections())
        st = e.get_section_by_name('.symtab')
        for rs in secs:
            if not isinstance(rs, RelocationSection) or (oi, rs['sh_info']) not in addr:
                continue
            base = addr[(oi, rs['sh_info'])]
            for r in rs.iter_relocations():
                t = r['r_info_type']
                a = base + r['r_offset']
                S = syms.get((oi, r['r_info_sym']))
                A = r['r_addend'] if r.is_RELA() else 0
                if t == 22:
                    continue
                if S is None:
                    unhandled[('nosym', t)] = unhandled.get(('nosym', t), 0) + 1
                    continue
                v = S + A
                top6 = rd(a + (0 if t in (8, 18, 20) else 2)) >> 10 if t != 1 else 0
                bits = 10 if top6 in (0x34, 0x35, 0x36, 0x37, 0x38) else 6
                if t == 1:
                    struct.pack_into('<I', img, a - TEXT_BASE, v & 0xffffffff)
                elif t in (5, 7):
                    put_long(a, (v - cp_base) // 4, bits)
                elif t == 12:
                    put_long(a, v, bits)
                elif t in (19, 21):
                    pcrel(a, v, bits, 4 if dual.get((oi, rs['sh_info'])) else 2)
                elif t in (8, 18, 20):
                    pcrel_short(a, v, bits, 4 if dual.get((oi, rs['sh_info'])) else 2)
                else:
                    unhandled[t] = unhandled.get(t, 0) + 1
    if unhandled:
        print('unhandled relocations:', unhandled, file=sys.stderr)

    write_elf(out, img, bases, cp_base, dp_base, out_syms)
    print('%s: %d bytes, text %#x-%#x, cp %#x, dp %#x, %d symbols, %d stubs'
          % (out, len(img), TEXT_BASE, bases['text_end'], cp_base, dp_base, len(out_syms), len(stub_addr)))


def write_elf(out, img, bases, cp_base, dp_base, out_syms):
    shstr = b'\0.text\0.cp\0.dp\0.symtab\0.strtab\0.shstrtab\0'

    def sname(n):
        return shstr.index(b'\0' + n.encode() + b'\0') + 1
    strtab = bytearray(b'\0')
    symtab = bytearray(bytes(16))
    secs_for = lambda v: 1 if v < cp_base else (2 if v < dp_base else 3)
    locs = [s for s in out_syms if s[4] == 'STB_LOCAL']
    globs = [s for s in out_syms if s[4] != 'STB_LOCAL']
    for n, v, sz, ty, bind in locs + globs:
        off = len(strtab)
        strtab += n.encode() + b'\0'
        st_type = {'STT_FUNC': 2, 'STT_OBJECT': 1}.get(ty, 0)
        st_bind = 0 if bind == 'STB_LOCAL' else 1
        symtab += struct.pack('<IIIBBH', off, v, sz, (st_bind << 4) | st_type, 0, secs_for(v))
    ehsz, phsz = 52, 32
    data_off = ehsz + phsz
    text_end = cp_base - 0x80000
    parts = [(data_off, img)]
    o = data_off + len(img)
    o = align(o, 4)
    sym_off = o
    o += len(symtab)
    str_off = o
    o += len(strtab)
    shs_off = o
    o += len(shstr)
    sh_off = align(o, 4)
    f = bytearray(sh_off + 7 * 40)
    f[0:16] = b'\x7fELF\x01\x01\x01' + bytes(9)
    struct.pack_into('<HHIIIIIHHHHHH', f, 16, 2, 0xcb, 1, 0x80000, ehsz, sh_off, 0, ehsz, phsz, 1, 40, 7, 6)
    struct.pack_into('<IIIIIIII', f, ehsz, 1, data_off, 0x80000, 0x80000, len(img), len(img), 7, 4)
    f[data_off:data_off + len(img)] = img
    f[sym_off:sym_off + len(symtab)] = symtab
    f[str_off:str_off + len(strtab)] = strtab
    f[shs_off:shs_off + len(shstr)] = shstr
    sh = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (sname('.text'), 1, 6, 0x80000, data_off, text_end, 0, 0, 4, 0),
        (sname('.cp'), 1, 2, cp_base, data_off + cp_base - 0x80000, dp_base - cp_base, 0, 0, 4, 0),
        (sname('.dp'), 1, 3, dp_base, data_off + dp_base - 0x80000, 0x80000 + len(img) - dp_base, 0, 0, 4, 0),
        (sname('.symtab'), 2, 0, 0, sym_off, len(symtab), 5, len(locs) + 1, 4, 16),
        (sname('.strtab'), 3, 0, 0, str_off, len(strtab), 0, 0, 1, 0),
        (sname('.shstrtab'), 3, 0, 0, shs_off, len(shstr), 0, 0, 1, 0),
    ]
    for i, s in enumerate(sh):
        struct.pack_into('<IIIIIIIIII', f, sh_off + 40 * i, *s)
    open(out, 'wb').write(f)


main()
