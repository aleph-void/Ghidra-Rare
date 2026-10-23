#!/usr/bin/env python3
"""Disassemble raw 32-bit PRU words with TI dispru for a given silicon version.

Usage: ti_dis.py <TI_CGT_DIR> <version 0-4> <raw.bin> <out.txt> [workdir]

Assembles a .text section of NOPs with `clpru -v<N>` (so the object carries the
right build attributes / silicon version), patches the raw words over the NOPs,
then runs `dispru` and writes "<byteoffset> <word> <text>" lines.
"""
import os, struct, subprocess, sys, tempfile

def main():
    cgt, ver, raw, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    work = sys.argv[5] if len(sys.argv) > 5 else tempfile.mkdtemp()
    os.makedirs(work, exist_ok=True)
    data = open(raw, 'rb').read()
    n = len(data) // 4
    asm = os.path.join(work, 'pad%s.asm' % ver)
    obj = os.path.join(work, 'pad%s.obj' % ver)
    with open(asm, 'w') as f:
        f.write('\t.text\n')
        f.write('\tadd r0, r0, r0\n' * n)
    subprocess.check_call([os.path.join(cgt, 'bin', 'clpru'), '-v' + ver, '-c', asm,
                           '--output_file=' + obj], cwd=work,
                          stdout=subprocess.DEVNULL)
    blob = bytearray(open(obj, 'rb').read())
    # locate .text via section headers
    shoff, = struct.unpack_from('<I', blob, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', blob, 0x2e)
    def sh(i):
        return struct.unpack_from('<IIIIIIIIII', blob, shoff + i * shentsize)
    stro = sh(shstrndx)[4]
    for i in range(shnum):
        s = sh(i)
        name = blob[stro + s[0]:blob.index(b'\0', stro + s[0])].decode()
        if name == '.text':
            assert s[5] == n * 4, (s[5], n)
            blob[s[4]:s[4] + n * 4] = data[:n * 4]
            break
    else:
        raise SystemExit('no .text')
    open(obj, 'wb').write(blob)
    txt = subprocess.run([os.path.join(cgt, 'bin', 'dispru'), '-qq', obj],
                         stdout=subprocess.PIPE, universal_newlines=True).stdout
    with open(out, 'w') as f:
        for line in txt.splitlines():
            p = line.split(None, 2)
            if len(p) >= 2 and len(p[0]) == 8 and len(p[1]) == 8:
                try:
                    int(p[0], 16); int(p[1], 16)
                except ValueError:
                    continue
                f.write('%s %s %s\n' % (p[0], p[1], p[2].strip() if len(p) > 2 else ''))

if __name__ == '__main__':
    main()
