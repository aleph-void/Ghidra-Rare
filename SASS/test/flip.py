import sys
from nvd import disasm
arch = sys.argv[1]; w = int(sys.argv[2], 16)
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 12
ws = [w] + [w ^ (1 << b) for b in range(lo, 128)]
r = disasm(arch, ws)
print('base', r[0])
for b, t in zip(range(lo, 128), r[1:]):
    if t != r[0]: print('%3d' % b, t)
