"""Extract instruction words from .text.* sections of CUDA cubin ELF files."""
import struct, sys, os, re, collections

def sections(data):
    if data[:4] != b'\x7fELF': return
    is64 = data[4] == 2
    if is64:
        shoff, = struct.unpack_from('<Q', data, 0x28); shentsz, shnum, shstrndx = struct.unpack_from('<HHH', data, 0x3a)
    else:
        shoff, = struct.unpack_from('<I', data, 0x20); shentsz, shnum, shstrndx = struct.unpack_from('<HHH', data, 0x2e)
    sh = []
    for i in range(shnum):
        o = shoff + i * shentsz
        if is64:
            name, typ, flags, addr, off, size = struct.unpack_from('<IIQQQQ', data, o)
        else:
            name, typ, flags, addr, off, size = struct.unpack_from('<IIIIII', data, o)
        sh.append((name, typ, off, size))
    so = sh[shstrndx][2]
    for name, typ, off, size in sh:
        n = data[so + name: data.index(b'\0', so + name)].decode()
        yield n, typ, data[off:off + size]

def eflags(data):
    return struct.unpack_from('<I', data, 0x30 if data[4] == 2 else 0x24)[0]

def text_words(path, isz):
    yield from text_words_bytes(open(path, 'rb').read(), isz)

def text_words_bytes(data, isz):
    for n, typ, b in sections(data):
        if n.startswith('.text.') and typ == 1:
            yield n, [int.from_bytes(b[i:i + isz], 'little') for i in range(0, len(b) - isz + 1, isz)]

if __name__ == '__main__':
    # usage: cubin_words.py <isz> files...  -> prints unique hex words with counts
    isz = int(sys.argv[1]); c = collections.Counter()
    for p in sys.argv[2:]:
        for n, ws in text_words(p, isz):
            c.update(ws)
    for w, k in c.most_common():
        print('%x %d' % (w, k))
