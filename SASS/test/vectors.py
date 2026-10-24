#!/usr/bin/env python3
"""Test-vector helpers.
  vectors.py tobin <vectors.txt> <out.bin>          hex words (one per line) -> raw file
  vectors.py fuzz <VARIANT> <out.bin> <seed> <n>    random instruction words (opcode-uniform)
  vectors.py make <VARIANT> <out.txt> <n_real> <n_fuzz> <cubin>...   (redistributable cubins only)
"""
import sys, os, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CTRL_STD = (0x000fe4 << 104) & sum(1 << b for b in list(range(105, 122)) + [126, 127])

def fuzz_words(n, seed, isz=16):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        if isz == 16:
            dens = rng.choice([0.03, 0.08, 0.15, 0.3, 0.5])
            w = rng.randrange(4096) | (rng.randrange(16) << 12)
            for b in range(16, 105):
                if rng.random() < dens:
                    w |= 1 << b
            w |= CTRL_STD
            # reuse flags occasionally
            if rng.random() < 0.2:
                w |= rng.randrange(16) << 122
        else:
            w = rng.getrandbits(64)
        out.append(w)
    return out

def tobin(words, path, isz=16, arch=None):
    """Raw image; 64-bit encodings get a scheduling control word before every
    3 (Kepler: 7) instructions, as in real code."""
    with open(path, 'wb') as f:
        if isz == 8:
            import nvd
            nb, ctrl, fill = nvd.bundle_of(arch)
            words = list(words)
            while len(words) % (nb - 1):
                words.append(fill)
            for i in range(0, len(words), nb - 1):
                f.write(ctrl.to_bytes(8, 'little'))
                for w in words[i:i + nb - 1]:
                    f.write(w.to_bytes(8, 'little'))
            return
        for w in words:
            f.write(w.to_bytes(isz, 'little'))

def main():
    cmd = sys.argv[1]
    if cmd == 'tobin':
        # tobin <words.txt> <out.bin> [VARIANT]
        import nvd
        arch = sys.argv[4] if len(sys.argv) > 4 else 'SM80'
        ws = [int(l.split()[0], 16) for l in open(sys.argv[2]) if l.strip() and not l.startswith('#')]
        tobin(ws, sys.argv[3], nvd.isz_of(arch), arch)
    elif cmd == 'fuzz':
        import nvd
        arch = sys.argv[2]
        isz = nvd.isz_of(arch)
        ws = fuzz_words(int(sys.argv[5]), int(sys.argv[4]), isz)
        if isz == 8:
            g = 18 if arch in nvd.KEPLER else 16
            ws = [(w & ~(0xf << g)) | (random.Random(w).randrange(16) << g) for w in ws]
        tobin(ws, sys.argv[3], isz, arch)
    elif cmd == 'make':
        # make <VARIANT> <out.txt> <n_real> <n_fuzz> <cubin>...
        import nvd, cubin_words
        v, out, nr, nf = sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        cubs = sys.argv[6:]
        isz = nvd.isz_of(v)
        rng = random.Random(1)
        real = []
        srcs = []
        for p in cubs:
            nb = nvd.bundle_of(v)[0] if isz == 8 else 0
            ws = sorted({w for _, l in cubin_words.text_words(p, isz) for i, w in enumerate(l) if not (nb and i % nb == 0)})
            real += ws
            srcs.append(os.path.basename(p))
        real = sorted(set(real))
        rt = nvd.disasm(v, real, use_cache=False)
        real = [w for w, t in zip(real, rt) if t]
        real = rng.sample(real, min(nr, len(real)))
        fw = fuzz_words(nf * 12, 99, isz)
        ft = nvd.disasm(v, fw, use_cache=False)
        fw = [w for w, t in zip(fw, ft) if t][:nf]
        with open(out, 'w') as f:
            f.write('# %s test vectors: %d instruction words from %s, %d random words nvdisasm accepts\n' % (
                v, len(real), ', '.join(srcs), len(fw)))
            f.write('# bitsandbytes (https://github.com/bitsandbytes-foundation/bitsandbytes) is MIT licensed;\n')
            f.write('# k*.cubin are built from test/ptx/kernels.ptx (ptxas) and test/cuda/kernels.cu (test/build-cu-cubins.sh).\n')
            for w in real + fw:
                f.write('%0*x\n' % (2 * isz, w))
    else:
        raise SystemExit(__doc__)

if __name__ == '__main__':
    main()
