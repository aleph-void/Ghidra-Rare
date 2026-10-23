import sys, random, collections, json
from nvd import disasm
arch = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
random.seed(1)
words = []
CTRL = 0x000fc00000000000 << 64
for op in range(4096):
    base = op | (7 << 12)
    words.append(base)
    words.append(base | CTRL)
    for k in range(n):
        dens = random.choice([0.02, 0.05, 0.1, 0.2])
        w = base
        for b in range(16, 105):
            if random.random() < dens: w |= 1 << b
        words.append(w | CTRL)
res = disasm(arch, words, batch=32)
ops = collections.defaultdict(list)
for w, t in zip(words, res):
    if t: ops[w & 0xfff].append((w, t))
out = {}
for op in sorted(ops):
    mn = collections.Counter(t.split()[0] if not t.startswith('@') else t.split()[1] for w, t in ops[op])
    out['%03x' % op] = {'n': len(ops[op]), 'mn': dict(mn), 'ex': ['%032x %s' % x for x in ops[op][:4]]}
json.dump(out, open('/tmp/claude-1000/-home-nick-Documents-git-Ghidra-Rare/738fc310-bd10-40da-87e5-b0a8be585382/scratchpad/work/sass/ops_%s.json' % arch, 'w'), indent=1)
print(len(out), 'opcodes valid')
