#!/usr/bin/env python3
"""Fetch real-world cubins for validation (not committed).

Source: bitsandbytes 0.50.2 (MIT licensed) manylinux wheel from PyPI.  Only the
needed members of the wheel are read (HTTP range requests); the .nv_fatbin
section of each libbitsandbytes_cuda*.so is split and the first cubin for each
wanted SM is written to <outdir> as libbitsandbytes_<cuda>_sm<NN>_1.cubin.
CUDA 13 fatbins store their cubins zstd-compressed; the zstd CLI is used.

  test/fetch-real-samples.py [outdir]     (default: test/samples)
"""
import sys, os, io, struct, zipfile, urllib.request, subprocess, tempfile

URL = ('https://files.pythonhosted.org/packages/a5/6e/e4e8b75716dbe5e50964f070266e06f4e6806ce051bfb97f52ee162b9310/'
       'bitsandbytes-0.50.2-py3-none-manylinux_2_24_x86_64.whl')
WANT = {'cuda118': [60], 'cuda124': [75, 86, 90], 'cuda130': [100, 120]}

class HttpFile(io.RawIOBase):
    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method='HEAD'))
        self.url = r.geturl(); self.n = int(r.headers['Content-Length']); self.p = 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.p
    def seek(self, o, w=0):
        self.p = o if w == 0 else (self.p + o if w == 1 else self.n + o); return self.p
    def readinto(self, b):
        if self.p >= self.n: return 0
        e = min(self.p + len(b), self.n) - 1
        d = urllib.request.urlopen(urllib.request.Request(self.url, headers={'Range': 'bytes=%d-%d' % (self.p, e)})).read()
        b[:len(d)] = d; self.p += len(d); return len(d)

def elf_section(data, name):
    shoff, = struct.unpack_from('<Q', data, 0x28)
    shentsz, shnum, shstrndx = struct.unpack_from('<HHH', data, 0x3a)
    hdr = lambda i: struct.unpack_from('<IIQQQQ', data, shoff + i * shentsz)
    so = hdr(shstrndx)[4]
    for i in range(shnum):
        nm, typ, fl, addr, off, size = hdr(i)
        if data[so + nm: data.index(b'\0', so + nm)].decode() == name:
            return data[off:off + size]
    return None

def cubins(fatbin, want):
    p = 0; got = {}
    while p + 16 <= len(fatbin):
        magic, ver, hs, fs = struct.unpack_from('<IHHQ', fatbin, p)
        if magic != 0xBA55ED50:
            p += 8; continue
        q = p + hs; end = q + fs
        while q < end:
            kind, _, ehs, sz, csz, _, mn, mj, arch = struct.unpack_from('<HHIQIIHHI', fatbin, q)
            flags, = struct.unpack_from('<Q', fatbin, q + 40)
            pl = fatbin[q + ehs:q + ehs + sz]
            if kind == 2 and arch in want and arch not in got:
                if pl[:4] != b'\x7fELF':
                    i = pl.find(b'\x28\xb5\x2f\xfd')   # zstd frame magic
                    if i >= 0:
                        pl = subprocess.run(['zstd', '-d', '-c'], input=pl[i:], capture_output=True).stdout
                if pl[:4] == b'\x7fELF':
                    got[arch] = pl
            q += ehs + sz
        p = end
    return got

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
    os.makedirs(out, exist_ok=True)
    z = zipfile.ZipFile(io.BufferedReader(HttpFile(URL), buffer_size=1 << 20))
    names = z.namelist()
    lic = [n for n in names if n.endswith('LICENSE')]
    if lic:
        open(os.path.join(out, 'LICENSE'), 'wb').write(z.read(lic[0]))
    for cu, sms in WANT.items():
        so = next(n for n in names if n.endswith('libbitsandbytes_%s.so' % cu))
        data = z.read(so)
        fb = elf_section(data, '.nv_fatbin')
        for arch, pl in sorted(cubins(fb, set(sms)).items()):
            fn = os.path.join(out, 'libbitsandbytes_%s_sm%d_1.cubin' % (cu, arch))
            open(fn, 'wb').write(pl)
            print('wrote', fn, len(pl))
        del data

if __name__ == '__main__':
    main()
