/* ###
 * Ghidra-Rare IA-64 module (MIT).
 */
package ghidra.app.util.bin.format.elf.relocation;

import java.math.BigInteger;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;

/** Global pointer (gp, r1) of an IA-64 ELF module. */
public final class IA64GpUtil {

	private IA64GpUtil() {
	}

	/**
	 * DT_PLTGOT holds the module's gp on IA-64 Linux; otherwise the __gp symbol; otherwise the
	 * gp that the entry code of a static executable computes (GNU crt1: movl r1 = K; mov rN = ip;
	 * sub r1 = rN, r1, or an absolute movl r1 = K). Adjusted for the image base Ghidra loaded the
	 * module at. Null if none is found.
	 */
	public static Long findGp(ElfLoadHelper helper) {
		ElfHeader elf = helper.getElfHeader();
		long adjust = helper.getImageBaseWordAdjustmentOffset();
		try {
			ElfDynamicTable dyn = elf.getDynamicTable();
			if (dyn != null && dyn.containsDynamicValue(ElfDynamicType.DT_PLTGOT)) {
				return dyn.getDynamicValue(ElfDynamicType.DT_PLTGOT) + adjust;
			}
		}
		catch (Exception e) {
			// fall through
		}
		for (ElfSymbolTable st : elf.getSymbolTables()) {
			for (ElfSymbol s : st.getSymbols()) {
				if ("__gp".equals(s.getNameAsString())) {
					return s.getValue() + adjust;
				}
			}
		}
		if (!elf.isRelocatable() && elf.e_entry() != 0) {
			return gpFromEntry(helper, elf.e_entry() + adjust);
		}
		return null;
	}

	private static long slot(BigInteger b, int k) {
		return b.shiftRight(5 + 41 * k).and(BigInteger.ONE.shiftLeft(41).subtract(BigInteger.ONE))
				.longValue();
	}

	private static long bits(long v, int lo, int hi) {
		return (v >>> lo) & ((1L << (hi - lo + 1)) - 1);
	}

	private static Long gpFromEntry(ElfLoadHelper helper, long entry) {
		Memory mem = helper.getProgram().getMemory();
		Address start = helper.getDefaultAddress(entry & ~0xfL);
		int n = 12;
		BigInteger[] bundle = new BigInteger[n];
		try {
			for (int i = 0; i < n; i++) {
				byte[] b = new byte[16];
				mem.getBytes(start.add(16 * i), b);
				BigInteger v = BigInteger.ZERO;
				for (int j = 15; j >= 0; j--) {
					v = v.shiftLeft(8).or(BigInteger.valueOf(b[j] & 0xff));
				}
				bundle[i] = v;
			}
		}
		catch (Exception e) {
			return null;
		}
		for (int i = 0; i < n; i++) {
			int tmpl = bundle[i].intValue() & 0x1f;
			if (tmpl != 4 && tmpl != 5) {
				continue;
			}
			long l = slot(bundle[i], 1), x = slot(bundle[i], 2);
			if (bits(x, 37, 40) != 6 || bits(x, 20, 20) != 0 || bits(x, 6, 12) != 1) {
				continue;
			}
			long k = (bits(x, 36, 36) << 63) | (l << 22) | (bits(x, 21, 21) << 21) |
				(bits(x, 22, 26) << 16) | (bits(x, 27, 35) << 7) | bits(x, 13, 19);
			// mov rN = ip ; sub r1 = rN, r1 within the next bundles
			Long ip = null;
			long reg = -1;
			for (int j = i; j < Math.min(n, i + 5); j++) {
				for (int s = 0; s < 3; s++) {
					long v = slot(bundle[j], s);
					if (ip == null && bits(v, 37, 40) == 0 && bits(v, 33, 35) == 0 &&
						bits(v, 27, 32) == 0x30) {
						ip = start.getOffset() + 16L * j;
						reg = bits(v, 6, 12);
					}
					else if (ip != null && bits(v, 37, 40) == 8 && bits(v, 34, 35) == 0 &&
						bits(v, 33, 33) == 0 && bits(v, 29, 32) == 1 && bits(v, 27, 28) == 1 &&
						bits(v, 6, 12) == 1 && bits(v, 13, 19) == reg && bits(v, 20, 26) == 1) {
						return ip - k;
					}
				}
			}
			return k;
		}
		return null;
	}
}
