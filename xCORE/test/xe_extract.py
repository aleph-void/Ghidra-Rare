#!/usr/bin/env python3
"""Split an XMOS .xe executable into its embedded ELF images.

.xe layout (little endian): "XMOS", u16 version, u16 pad, then sectors:
    u16 type, u16 pad, u64 length            (length 0 -> no payload)
    payload[length]: u8 padbytes, u8[3] reserved, body, padbytes of padding
Sector types: 1 binary, 2 ELF, 3 config (XN), 4 goto, 5 call, 6 XN, 0x5555 last.
ELF body: u16 node, u16 core(tile), u64 load address, then the ELF image.

Usage: xe_extract.py file.xe outdir   -> outdir/<base>_n<node>_t<tile>_<k>.elf (+ listing)
The last ELF per (node, tile) is the application image; earlier ones are boot/loader stubs.
"""
import os, struct, sys


def sectors(data):
    if data[:4] != b"XMOS":
        raise SystemExit("not an .xe file")
    off = 8
    while off + 12 <= len(data):
        typ, _, length = struct.unpack_from("<HHQ", data, off)
        off += 12
        if typ == 0x5555:
            return
        payload = data[off:off + length]
        off += length
        if length:
            pad = payload[0]
            yield typ, payload[4:len(payload) - pad]
        else:
            yield typ, b""


def main():
    xe, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    data = open(xe, "rb").read()
    base = os.path.splitext(os.path.basename(xe))[0]
    seen = {}
    for typ, body in sectors(data):
        if typ != 2:
            continue
        node, tile, addr = struct.unpack_from("<HHQ", body)
        elf = body[12:]
        assert elf[:4] == b"\x7fELF", "bad ELF sector"
        k = seen.get((node, tile), 0)
        seen[(node, tile)] = k + 1
        entry, = struct.unpack_from("<I", elf, 24)
        mach, = struct.unpack_from("<H", elf, 18)
        name = "%s_n%d_t%d_%d.elf" % (base, node, tile, k)
        open(os.path.join(outdir, name), "wb").write(elf)
        print("%s  node=%d tile=%d load=0x%x size=%d e_machine=%d entry=0x%x"
              % (name, node, tile, addr, len(elf), mach, entry))


if __name__ == "__main__":
    main()
