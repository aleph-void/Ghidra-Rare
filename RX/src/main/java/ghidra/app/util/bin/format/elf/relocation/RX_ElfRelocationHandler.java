/* SPDX-License-Identifier: MIT */
package ghidra.app.util.bin.format.elf.relocation;

import java.util.ArrayDeque;
import java.util.Deque;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for Renesas RX (EM_RX = 173), for relocatable objects (.o / .a members)
 * produced by the GNU toolchain. Linked executables need no relocation.
 * <p>
 * Fields are little-endian except the _REV types. PC-relative 8/16/24-bit fields follow the
 * one-byte opcode of BRA/BSR/BCnd, and the displacement counts from that opcode byte, so the
 * stored value is S + A - (P - 1) (checked by linking gas output with GNU ld). DIRn / ABSn store the low n bits of the value;
 * the UL/UW variants store the value divided by 4/2 (scaled displacements); DIR3U_PCREL patches
 * the 3-bit displacement of BRA.S/BEQ.S/BNE.S (distances 3..10, stored modulo 8). The SYM / OPxxx
 * / ABSn types are a stack machine for expressions gas cannot reduce (e.g. differences of
 * symbols): SYM pushes S + A, each OP pops its operands and pushes the result, ABSn pops and
 * stores. Section-relative operators (OPsctsize, OPscttop, OPromtop, OPramtop) and the
 * relaxation hints (RH_*) are reported but not applied.
 */
public class RX_ElfRelocationHandler
		extends AbstractElfRelocationHandler<RX_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_RX = 173;

	/** Expression stack of the complex relocations (relocations are applied in order). */
	private final Deque<Long> stack = new ArrayDeque<>();

	public RX_ElfRelocationHandler() {
		super(RX_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == EM_RX;
	}

	private static int store(Memory mem, Address a, long v, int bytes, boolean bigEndian)
			throws MemoryAccessException {
		for (int i = 0; i < bytes; i++) {
			int shift = bigEndian ? 8 * (bytes - 1 - i) : 8 * i;
			mem.setByte(a.add(i), (byte) (v >> shift));
		}
		return bytes;
	}

	/** Store a DIRn/ABSn style value; returns the number of bytes written, or -1. */
	private static int put(Memory mem, Address a, String kind, long v, long p)
			throws MemoryAccessException {
		switch (kind) {
			case "32":
				return store(mem, a, v, 4, false);
			case "24S":
				return store(mem, a, v, 3, false);
			case "16":
			case "16U":
			case "16S":
				return store(mem, a, v, 2, false);
			case "8":
			case "8U":
			case "8S":
				return store(mem, a, v, 1, false);
			// branch displacements count from the opcode byte that precedes the field
			case "24S_PCREL":
				return store(mem, a, v - (p - 1), 3, false);
			case "16S_PCREL":
				return store(mem, a, v - (p - 1), 2, false);
			case "8S_PCREL":
				return store(mem, a, v - (p - 1), 1, false);
			case "16UL":
				return store(mem, a, v >> 2, 2, false);
			case "16UW":
				return store(mem, a, v >> 1, 2, false);
			case "8UL":
				return store(mem, a, v >> 2, 1, false);
			case "8UW":
				return store(mem, a, v >> 1, 1, false);
			case "32_REV":
				return store(mem, a, v, 4, true);
			case "16_REV":
				return store(mem, a, v, 2, true);
			case "3U_PCREL": {
				byte b = mem.getByte(a);
				mem.setByte(a, (byte) ((b & ~7) | ((v - p) & 7)));
				return 1;
			}
			default:
				return -1;
		}
	}

	private long pop() {
		Long v = stack.poll();
		return v == null ? 0 : v;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			RX_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Memory mem = ctx.getProgram().getMemory();
		long A = relocation.getAddend();
		long P = relocationAddress.getOffset();
		String name = type.name();

		if (type == RX_ElfRelocationType.R_RX_NONE || type == RX_ElfRelocationType.R_RX_RH_RELAX) {
			return RelocationResult.SKIPPED;
		}
		if (name.startsWith("R_RX_RH_")) {
			markAsUnhandled(ctx.getProgram(), relocationAddress, type, relocation.getSymbolIndex(),
				symbolName, ctx.getLog());
			return RelocationResult.UNSUPPORTED;
		}
		if (name.startsWith("R_RX_DIR") || type == RX_ElfRelocationType.R_RX_SYM) {
			if (relocation.getSymbolIndex() != 0 &&
				handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
				return RelocationResult.FAILURE;
			}
		}
		long S = symbolValue;

		if (name.startsWith("R_RX_DIR")) {
			int n = put(mem, relocationAddress, name.substring(8), S + A, P);
			if (n < 0) {
				return RelocationResult.UNSUPPORTED;
			}
			return new RelocationResult(Status.APPLIED, n);
		}
		if (name.startsWith("R_RX_ABS")) {
			int n = put(mem, relocationAddress, name.substring(8), pop(), P);
			if (n < 0) {
				return RelocationResult.UNSUPPORTED;
			}
			return new RelocationResult(Status.APPLIED, n);
		}
		long a, b;
		switch (type) {
			case R_RX_SYM:
				stack.push(S + A);
				return new RelocationResult(Status.APPLIED_OTHER, 0);
			case R_RX_OPneg:
				stack.push(-pop());
				return new RelocationResult(Status.APPLIED_OTHER, 0);
			case R_RX_OPnot:
				stack.push(~pop());
				return new RelocationResult(Status.APPLIED_OTHER, 0);
			case R_RX_OPadd:
			case R_RX_OPsub:
			case R_RX_OPmul:
			case R_RX_OPdiv:
			case R_RX_OPmod:
			case R_RX_OPshla:
			case R_RX_OPshra:
			case R_RX_OPand:
			case R_RX_OPor:
			case R_RX_OPxor:
				b = pop();   // top of stack: second operand
				a = pop();
				long r;
				switch (type) {
					case R_RX_OPadd -> r = a + b;
					case R_RX_OPsub -> r = a - b;
					case R_RX_OPmul -> r = a * b;
					case R_RX_OPdiv -> r = b == 0 ? 0 : a / b;
					case R_RX_OPmod -> r = b == 0 ? 0 : a % b;
					case R_RX_OPshla -> r = a << b;
					case R_RX_OPshra -> r = a >> b;
					case R_RX_OPand -> r = a & b;
					case R_RX_OPor -> r = a | b;
					default -> r = a ^ b;
				}
				stack.push(r);
				return new RelocationResult(Status.APPLIED_OTHER, 0);
			default:
				markAsUnhandled(ctx.getProgram(), relocationAddress, type,
					relocation.getSymbolIndex(), symbolName, ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
