# LLVM C-API XCore disassembler oracle.  usage: llvmdis.py <in.bin> <out.txt> [mode]
# mode "words16": each 16-bit word at even offset decoded independently, bytes beyond given as next word
# mode "sweep": linear sweep like Ghidra harness
import ctypes, sys, struct
lib = ctypes.CDLL('/usr/lib/llvm-21/lib/libLLVM.so')
for f in ('LLVMInitializeXCoreTargetInfo','LLVMInitializeXCoreTargetMC','LLVMInitializeXCoreDisassembler'):
    getattr(lib, f)()
lib.LLVMCreateDisasm.restype = ctypes.c_void_p
lib.LLVMCreateDisasm.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
lib.LLVMDisasmInstruction.restype = ctypes.c_size_t
lib.LLVMDisasmInstruction.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_size_t]
dc = lib.LLVMCreateDisasm(b'xcore', None, 0, None, None)
assert dc
buf = ctypes.create_string_buffer(256)
def dis(b, pc=0):
    cb = (ctypes.c_ubyte * len(b)).from_buffer_copy(b)
    n = lib.LLVMDisasmInstruction(dc, cb, len(b), pc, buf, 256)
    return n, buf.value.decode().strip().replace('\t', ' ')
if __name__ == '__main__':
    data = open(sys.argv[1], 'rb').read()
    out = open(sys.argv[2], 'w')
    mode = sys.argv[3] if len(sys.argv) > 3 else 'sweep'
    off = 0
    while off < len(data):
        n, t = dis(data[off:off+4], off)
        if n == 0:
            out.write('%08x %s BAD\n' % (off, data[off:off+2].hex())); off += 2
        else:
            out.write('%08x %s %s\n' % (off, data[off:off+n].hex(), ' '.join(t.split())))
            off += n
