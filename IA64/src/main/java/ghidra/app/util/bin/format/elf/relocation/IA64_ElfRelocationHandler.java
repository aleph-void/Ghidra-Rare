/* ###
 * Ghidra-Rare IA-64 module (MIT).
 *
 * ELF relocations for IA-64 (Intel Itanium Processor-specific ABI). Data relocations (DIR, REL,
 * FPTR, IPLT, GPREL, PCREL, SEGREL, SECREL, LTV) are applied for executables, shared objects and
 * relocatable objects; instruction-slot relocations (IMM14/22/64, GPREL22, LTOFF22(X), PLTOFF22,
 * FPTR64I, LTOFF_FPTR22, PCREL21B/M/F, PCREL60B, PCREL22/64I) patch the 41-bit slot that
 * r_offset names (bundle address + slot number 0-2) and are needed for relocatable objects.
 * Official function descriptors (@fptr) and linkage-table entries (@ltoff) that a loaded image
 * lacks are created in an artificial "%ia64.linkage" block (see IA64_ElfRelocationContext).
 * TLS relocations are reported, not applied.
 */
package ghidra.app.util.bin.format.elf.relocation;

import java.math.BigInteger;
import java.util.Map;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

public class IA64_ElfRelocationHandler
		extends AbstractElfRelocationHandler<IA64_ElfRelocationType, IA64_ElfRelocationContext> {

	public static final int EM_IA_64 = 50;

	private static final BigInteger SLOT_MASK = BigInteger.ONE.shiftLeft(41).subtract(BigInteger.ONE);

	public IA64_ElfRelocationHandler() {
		super(IA64_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_IA_64;
	}

	@Override
	public IA64_ElfRelocationContext createRelocationContext(ElfLoadHelper loadHelper,
			Map<ElfSymbol, Address> symbolMap) {
		return new IA64_ElfRelocationContext(this, loadHelper, symbolMap);
	}

	// ---------------------------------------------------------------------------------------
	// Instruction slots: a 16-byte bundle is always little-endian; slot k = bits 5+41k .. 45+41k

	private static BigInteger readBundle(Memory mem, Address bundle) throws MemoryAccessException {
		byte[] b = new byte[16];
		mem.getBytes(bundle, b);
		byte[] be = new byte[17];
		for (int i = 0; i < 16; i++) {
			be[16 - i] = b[i];
		}
		return new BigInteger(be);
	}

	private static void writeBundle(Memory mem, Address bundle, BigInteger v)
			throws MemoryAccessException {
		byte[] b = new byte[16];
		for (int i = 0; i < 16; i++) {
			b[i] = v.shiftRight(8 * i).byteValue();
		}
		mem.setBytes(bundle, b);
	}

	private static long getSlot(BigInteger bundle, int k) {
		return bundle.shiftRight(5 + 41 * k).and(SLOT_MASK).longValue();
	}

	private static BigInteger setSlot(BigInteger bundle, int k, long slot) {
		BigInteger mask = SLOT_MASK.shiftLeft(5 + 41 * k);
		return bundle.andNot(mask).or(BigInteger.valueOf(slot).and(SLOT_MASK).shiftLeft(5 + 41 * k));
	}

	/** insert value bits [vlo, vlo+len) at slot bit pos */
	private static long put(long slot, int pos, int len, long value, int vlo) {
		long m = ((1L << len) - 1) << pos;
		return (slot & ~m) | (((value >>> vlo) << pos) & m);
	}

	private static long imm22(long s, long v) {
		s = put(s, 13, 7, v, 0);
		s = put(s, 27, 9, v, 7);
		s = put(s, 22, 5, v, 16);
		return put(s, 36, 1, v, 21);
	}

	private static long imm14(long s, long v) {
		s = put(s, 13, 7, v, 0);
		s = put(s, 27, 6, v, 7);
		return put(s, 36, 1, v, 13);
	}

	private static boolean fits(long v, int bits) {
		long lim = 1L << (bits - 1);
		return v >= -lim && v < lim;
	}

	private enum Form {
		IMM14, IMM22, IMM64, PCREL21B, PCREL21M, PCREL21F, PCREL60B
	}

	/** patch one instruction field; returns false on overflow */
	private static boolean patch(Memory mem, Address relocAddr, Form form, long value)
			throws MemoryAccessException {
		int k = (int) (relocAddr.getOffset() & 0xf);
		Address bundleAddr = relocAddr.subtract(k);
		BigInteger bundle = readBundle(mem, bundleAddr);
		boolean ok = true;
		switch (form) {
			case IMM14: {
				ok = fits(value, 14);
				bundle = setSlot(bundle, k, imm14(getSlot(bundle, k), value));
				break;
			}
			case IMM22: {
				ok = fits(value, 22);
				bundle = setSlot(bundle, k, imm22(getSlot(bundle, k), value));
				break;
			}
			case IMM64: {   // movl: L slot 1 holds imm41, X slot 2 the rest
				long l = (value >>> 22) & ((1L << 41) - 1);
				long x = getSlot(bundle, 2);
				x = put(x, 13, 7, value, 0);
				x = put(x, 27, 9, value, 7);
				x = put(x, 22, 5, value, 16);
				x = put(x, 21, 1, value, 21);
				x = put(x, 36, 1, value, 63);
				bundle = setSlot(setSlot(bundle, 1, l), 2, x);
				break;
			}
			case PCREL21B: {
				long d = value >> 4;
				ok = fits(d, 21) && (value & 0xf) == 0;
				long s = getSlot(bundle, k);
				s = put(s, 13, 20, d, 0);
				s = put(s, 36, 1, d, 20);
				bundle = setSlot(bundle, k, s);
				break;
			}
			case PCREL21M: {
				long d = value >> 4;
				ok = fits(d, 21) && (value & 0xf) == 0;
				long s = getSlot(bundle, k);
				s = put(s, 6, 7, d, 0);
				s = put(s, 20, 13, d, 7);
				s = put(s, 36, 1, d, 20);
				bundle = setSlot(bundle, k, s);
				break;
			}
			case PCREL21F: {
				long d = value >> 4;
				ok = fits(d, 21) && (value & 0xf) == 0;
				long s = getSlot(bundle, k);
				s = put(s, 6, 20, d, 0);
				s = put(s, 36, 1, d, 20);
				bundle = setSlot(bundle, k, s);
				break;
			}
			case PCREL60B: {   // brl: X slot imm20b + i, L slot bits 40:2 imm39
				long d = value >> 4;
				long x = getSlot(bundle, 2);
				x = put(x, 13, 20, d, 0);
				x = put(x, 36, 1, d, 59);
				long l = getSlot(bundle, 1);
				l = put(l, 2, 39, d, 20);
				bundle = setSlot(setSlot(bundle, 1, l), 2, x);
				break;
			}
		}
		writeBundle(mem, bundleAddr, bundle);
		return ok;
	}

	private static void put32(Memory mem, Address a, long v, boolean msb) throws MemoryAccessException {
		byte[] b = new byte[4];
		for (int i = 0; i < 4; i++) {
			b[msb ? 3 - i : i] = (byte) (v >>> (8 * i));
		}
		mem.setBytes(a, b);
	}

	private static void put64(Memory mem, Address a, long v, boolean msb) throws MemoryAccessException {
		byte[] b = new byte[8];
		for (int i = 0; i < 8; i++) {
			b[msb ? 7 - i : i] = (byte) (v >>> (8 * i));
		}
		mem.setBytes(a, b);
	}

	private static boolean isExternal(Program program, Address addr) {
		if (addr == null) {
			return true;
		}
		MemoryBlock block = program.getMemory().getBlock(addr);
		return block == null || MemoryBlock.EXTERNAL_BLOCK_NAME.equals(block.getName()) ||
			addr.isExternalAddress();
	}

	@Override
	protected RelocationResult relocate(IA64_ElfRelocationContext ctx, ElfRelocation relocation,
			IA64_ElfRelocationType type, Address relocAddr, ElfSymbol sym, Address symbolAddr,
			long symbolValue, String symbolName) throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long addend = relocation.getAddend();
		long p = relocAddr.getOffset();
		long pBundle = p & ~0xfL;

		// relocations that need no symbol
		switch (type) {
			case R_IA64_REL64LSB:
			case R_IA64_REL64MSB:
				put64(mem, relocAddr, ctx.getImageBaseWordAdjustmentOffset() + addend,
					type == IA64_ElfRelocationType.R_IA64_REL64MSB);
				return new RelocationResult(Status.APPLIED, 8);
			case R_IA64_REL32LSB:
			case R_IA64_REL32MSB:
				put32(mem, relocAddr, ctx.getImageBaseWordAdjustmentOffset() + addend,
					type == IA64_ElfRelocationType.R_IA64_REL32MSB);
				return new RelocationResult(Status.APPLIED, 4);
			case R_IA64_LDXMOV:
				// ld8.mov marker for a relaxable LTOFF22X: nothing to patch
				return new RelocationResult(Status.APPLIED_OTHER, 0);
			case R_IA64_COPY:
				markAsUnsupportedCopy(program, relocAddr, type, symbolName,
					relocation.getSymbolIndex(), sym.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;
			case R_IA64_TPREL14:
			case R_IA64_TPREL22:
			case R_IA64_TPREL64I:
			case R_IA64_TPREL64MSB:
			case R_IA64_TPREL64LSB:
			case R_IA64_LTOFF_TPREL22:
			case R_IA64_DTPMOD64MSB:
			case R_IA64_DTPMOD64LSB:
			case R_IA64_LTOFF_DTPMOD22:
			case R_IA64_DTPREL14:
			case R_IA64_DTPREL22:
			case R_IA64_DTPREL64I:
			case R_IA64_DTPREL32MSB:
			case R_IA64_DTPREL32LSB:
			case R_IA64_DTPREL64MSB:
			case R_IA64_DTPREL64LSB:
			case R_IA64_LTOFF_DTPREL22:
				markAsWarning(program, relocAddr, type, symbolName, relocation.getSymbolIndex(),
					"thread-local storage relocation not applied", ctx.getLog());
				return RelocationResult.UNSUPPORTED;
			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocAddr)) {
			return RelocationResult.FAILURE;
		}
		boolean external = isExternal(program, symbolAddr);
		long s = symbolAddr != null ? symbolAddr.getOffset() : symbolValue;
		long sa = s + addend;
		boolean ok = true;
		int len = 8;

		switch (type) {
			case R_IA64_DIR64LSB:
			case R_IA64_DIR64MSB:
			case R_IA64_LTV64LSB:
			case R_IA64_LTV64MSB:
				put64(mem, relocAddr, sa, type.name().endsWith("MSB"));
				break;
			case R_IA64_DIR32LSB:
			case R_IA64_DIR32MSB:
			case R_IA64_LTV32LSB:
			case R_IA64_LTV32MSB:
				put32(mem, relocAddr, sa, type.name().endsWith("MSB"));
				len = 4;
				break;
			case R_IA64_FPTR64LSB:
			case R_IA64_FPTR64MSB:
				put64(mem, relocAddr, ctx.functionDescriptor(sa, external),
					type == IA64_ElfRelocationType.R_IA64_FPTR64MSB);
				break;
			case R_IA64_FPTR32LSB:
			case R_IA64_FPTR32MSB:
				put32(mem, relocAddr, ctx.functionDescriptor(sa, external),
					type == IA64_ElfRelocationType.R_IA64_FPTR32MSB);
				len = 4;
				break;
			case R_IA64_IPLTLSB:
			case R_IA64_IPLTMSB: {
				// 16-byte descriptor {entry, gp} in .IA_64.pltoff
				boolean msb = type == IA64_ElfRelocationType.R_IA64_IPLTMSB;
				put64(mem, relocAddr, sa, msb);
				put64(mem, relocAddr.add(8), external ? 0 : ctx.getGp(), msb);
				len = 16;
				break;
			}
			case R_IA64_GPREL64LSB:
			case R_IA64_GPREL64MSB:
				put64(mem, relocAddr, sa - ctx.getGp(), type.name().endsWith("MSB"));
				break;
			case R_IA64_GPREL32LSB:
			case R_IA64_GPREL32MSB:
				put32(mem, relocAddr, sa - ctx.getGp(), type.name().endsWith("MSB"));
				len = 4;
				break;
			case R_IA64_PLTOFF64LSB:
			case R_IA64_PLTOFF64MSB:
				put64(mem, relocAddr, ctx.functionDescriptor(sa, external) - ctx.getGp(),
					type.name().endsWith("MSB"));
				break;
			case R_IA64_LTOFF_FPTR64LSB:
			case R_IA64_LTOFF_FPTR64MSB:
				put64(mem, relocAddr, ctx.linkageEntry(ctx.functionDescriptor(sa, external)) -
					ctx.getGp(), type.name().endsWith("MSB"));
				break;
			case R_IA64_LTOFF_FPTR32LSB:
			case R_IA64_LTOFF_FPTR32MSB:
				put32(mem, relocAddr, ctx.linkageEntry(ctx.functionDescriptor(sa, external)) -
					ctx.getGp(), type.name().endsWith("MSB"));
				len = 4;
				break;
			case R_IA64_PCREL64LSB:
			case R_IA64_PCREL64MSB:
				put64(mem, relocAddr, sa - p, type.name().endsWith("MSB"));
				break;
			case R_IA64_PCREL32LSB:
			case R_IA64_PCREL32MSB:
				put32(mem, relocAddr, sa - p, type.name().endsWith("MSB"));
				len = 4;
				break;
			case R_IA64_SEGREL64LSB:
			case R_IA64_SEGREL64MSB:
				put64(mem, relocAddr, sa - ctx.segmentBase(), type.name().endsWith("MSB"));
				break;
			case R_IA64_SEGREL32LSB:
			case R_IA64_SEGREL32MSB:
				put32(mem, relocAddr, sa - ctx.segmentBase(), type.name().endsWith("MSB"));
				len = 4;
				break;
			case R_IA64_SECREL64LSB:
			case R_IA64_SECREL64MSB:
				put64(mem, relocAddr, sa - ctx.sectionBase(sym), type.name().endsWith("MSB"));
				break;
			case R_IA64_SECREL32LSB:
			case R_IA64_SECREL32MSB:
				put32(mem, relocAddr, sa - ctx.sectionBase(sym), type.name().endsWith("MSB"));
				len = 4;
				break;
			// instruction slots
			case R_IA64_IMM14:
				ok = patch(mem, relocAddr, Form.IMM14, sa);
				len = 16;
				break;
			case R_IA64_IMM22:
				ok = patch(mem, relocAddr, Form.IMM22, sa);
				len = 16;
				break;
			case R_IA64_IMM64:
				ok = patch(mem, relocAddr, Form.IMM64, sa);
				len = 16;
				break;
			case R_IA64_GPREL22:
				ok = patch(mem, relocAddr, Form.IMM22, sa - ctx.getGp());
				len = 16;
				break;
			case R_IA64_GPREL64I:
				ok = patch(mem, relocAddr, Form.IMM64, sa - ctx.getGp());
				len = 16;
				break;
			case R_IA64_LTOFF22:
			case R_IA64_LTOFF22X:
				ok = patch(mem, relocAddr, Form.IMM22, ctx.linkageEntry(sa) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_LTOFF64I:
				ok = patch(mem, relocAddr, Form.IMM64, ctx.linkageEntry(sa) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_PLTOFF22:
				ok = patch(mem, relocAddr, Form.IMM22, ctx.functionDescriptor(sa, external) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_PLTOFF64I:
				ok = patch(mem, relocAddr, Form.IMM64, ctx.functionDescriptor(sa, external) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_FPTR64I:
				ok = patch(mem, relocAddr, Form.IMM64, ctx.functionDescriptor(sa, external));
				len = 16;
				break;
			case R_IA64_LTOFF_FPTR22:
				ok = patch(mem, relocAddr, Form.IMM22,
					ctx.linkageEntry(ctx.functionDescriptor(sa, external)) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_LTOFF_FPTR64I:
				ok = patch(mem, relocAddr, Form.IMM64,
					ctx.linkageEntry(ctx.functionDescriptor(sa, external)) - ctx.getGp());
				len = 16;
				break;
			case R_IA64_PCREL21B:
			case R_IA64_PCREL21BI:
				ok = patch(mem, relocAddr, Form.PCREL21B, sa - pBundle);
				len = 16;
				break;
			case R_IA64_PCREL21M:
				ok = patch(mem, relocAddr, Form.PCREL21M, sa - pBundle);
				len = 16;
				break;
			case R_IA64_PCREL21F:
				ok = patch(mem, relocAddr, Form.PCREL21F, sa - pBundle);
				len = 16;
				break;
			case R_IA64_PCREL60B:
				ok = patch(mem, relocAddr, Form.PCREL60B, sa - pBundle);
				len = 16;
				break;
			case R_IA64_PCREL22:
				ok = patch(mem, relocAddr, Form.IMM22, sa - pBundle);
				len = 16;
				break;
			case R_IA64_PCREL64I:
				ok = patch(mem, relocAddr, Form.IMM64, sa - pBundle);
				len = 16;
				break;
			default:
				markAsUnhandled(program, relocAddr, type, relocation.getSymbolIndex(), symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
		if (!ok) {
			markAsError(program, relocAddr, type, symbolName, relocation.getSymbolIndex(),
				"relocation value does not fit the instruction field", ctx.getLog());
			return RelocationResult.FAILURE;
		}
		return new RelocationResult(Status.APPLIED, len);
	}
}
