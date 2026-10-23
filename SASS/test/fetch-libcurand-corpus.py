#!/usr/bin/env python3
"""LOCAL-ONLY test corpus: instruction words of NVIDIA libcurand (proprietary EULA -
never commit the output).

Downloads the pinned nvidia-curand wheels from PyPI (verified by SHA-256), splits
the .nv_fatbin of libcurand.so into cubins and writes the unique instruction
words of every architecture to <outdir>/sm<NN>.txt ("<hex word> <count>"), the
format build_spec.py / evidence.py / run-tests.sh read.  This corpus is what the
module was learned from; run-tests.sh reports it as a local check when present.

  test/fetch-libcurand-corpus.py [outdir]     (default: test/corpus, git-ignored)
"""
import sys, os, io, hashlib, zipfile, urllib.request, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util
spec = importlib.util.spec_from_file_location('frs', os.path.join(HERE, 'fetch-real-samples.py'))
frs = importlib.util.module_from_spec(spec); spec.loader.exec_module(frs)
import cubin_words

WHEELS = [
    # CUDA 13 build: sm_75 .. sm_121
    ('https://files.pythonhosted.org/packages/07/73/3ee8e5b4cb891401e603ffd3a59b35c6afe785fd2de123afe7c7029603dc/'
     'nvidia_curand-10.4.4.72-py3-none-manylinux_2_27_x86_64.whl',
     '25c3457ae7a224fdd484dab90b0fc5dc0e842fab5db3012afa4a5bd2af4eb7e5', 'libcurand.so'),
    # CUDA 12 build: sm_50 .. sm_121 (used for sm_50, sm_60, sm_70)
    ('https://files.pythonhosted.org/packages/31/44/193a0e171750ca9f8320626e8a1f2381e4077a65e69e2fb9708bd479e34a/'
     'nvidia_curand_cu12-10.3.10.19-py3-none-manylinux_2_27_x86_64.whl',
     '49b274db4780d421bd2ccd362e1415c13887c53c214f0d4b761752b8f9f6aa1e', 'libcurand.so'),
]
WIDE8 = {50, 52, 53, 60, 61, 62, 35, 37}

def all_cubins(fatbin):
    import struct, subprocess
    p = 0
    while p + 16 <= len(fatbin):
        magic, ver, hs, fs = struct.unpack_from('<IHHQ', fatbin, p)
        if magic != 0xBA55ED50:
            p += 8; continue
        q = p + hs; end = q + fs
        while q < end:
            kind, _, ehs, sz, csz, _, mn, mj, arch = struct.unpack_from('<HHIQIIHHI', fatbin, q)
            pl = fatbin[q + ehs:q + ehs + sz]
            if kind == 2:
                if pl[:4] != b'\x7fELF':
                    i = pl.find(b'\x28\xb5\x2f\xfd')
                    if i >= 0:
                        pl = subprocess.run(['zstd', '-d', '-c'], input=pl[i:], capture_output=True).stdout
                if pl[:4] == b'\x7fELF':
                    yield arch, pl
            q += ehs + sz
        p = end

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'corpus')
    os.makedirs(out, exist_ok=True)
    words = collections.defaultdict(collections.Counter)
    done = set()
    for url, sha, member in WHEELS:
        data = urllib.request.urlopen(url).read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit('checksum mismatch for ' + url)
        z = zipfile.ZipFile(io.BytesIO(data))
        so = next(n for n in z.namelist() if os.path.basename(n).startswith(member))
        lib = z.read(so)
        del data, z
        fb = frs.elf_section(lib, '.nv_fatbin')
        seen = set()
        for arch, cub in all_cubins(fb):
            if arch in done:
                continue
            seen.add(arch)
            isz = 8 if arch in WIDE8 else 16
            for name, ws in cubin_words.text_words_bytes(cub, isz):
                for i, w in enumerate(ws):
                    if isz == 8 and i % 4 == 0:
                        continue        # Maxwell/Pascal control word
                    words[arch][w] += 1
        done |= seen
    for arch, c in sorted(words.items()):
        with open(os.path.join(out, 'sm%d.txt' % arch), 'w') as f:
            for w, k in c.most_common():
                f.write('%x %d\n' % (w, k))
        print('sm_%d: %d unique words' % (arch, len(c)))

if __name__ == '__main__':
    main()
