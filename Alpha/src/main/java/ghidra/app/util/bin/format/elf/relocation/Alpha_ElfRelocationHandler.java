/* ###
 * IP: Apache License 2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ghidra.app.util.bin.format.elf.relocation;

import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.reloc.Relocation.Status;
import ghidra.program.model.reloc.RelocationResult;

/**
 * ELF relocation handler for DEC Alpha (EM_ALPHA: 0x9026 as used by every GNU toolchain, and
 * the official 41).
 * <p>
 * Semantics follow binutils bfd/elf64-alpha.c and glibc sysdeps/alpha/dl-machine.h:
 * <ul>
 * <li>Dynamic: RELATIVE = B + A; REFQUAD, GLOB_DAT and JMP_SLOT = S + A (one quadword). With
 * the secure PLT (DT_ALPHA_PLTRO) JMP_SLOT addresses a .got entry; old-style PLTs are patched
 * by the dynamic linker at run time and are left alone here.</li>
 * <li>Static data and branch fields of relocatable objects: REFLONG, SREL16/32/64, BRADDR,
 * HINT.</li>
 * </ul>
 * GP-relative (LITERAL, GPDISP, GPREL*, BRSGP) relocations need the linker-built GOT and gp and
 * are reported, as are TLS module/offset relocations that only the dynamic linker can resolve.
 */
public class Alpha_ElfRelocationHandler
		extends AbstractElfRelocationHandler<Alpha_ElfRelocationType, ElfRelocationContext<?>> {

	public static final int EM_ALPHA = 0x9026;
	public static final int EM_ALPHA_OFFICIAL = 41;

	public Alpha_ElfRelocationHandler() {
		super(Alpha_ElfRelocationType.class);
	}

	@Override
	public boolean canRelocate(ElfHeader elf) {
		return elf.e_machine() == (short) EM_ALPHA || elf.e_machine() == EM_ALPHA_OFFICIAL;
	}

	@Override
	public int getRelrRelocationType() {
		return Alpha_ElfRelocationType.R_ALPHA_RELATIVE.typeId;
	}

	@Override
	protected RelocationResult relocate(ElfRelocationContext<?> ctx, ElfRelocation relocation,
			Alpha_ElfRelocationType type, Address relocationAddress, ElfSymbol elfSymbol,
			Address symbolAddr, long symbolValue, String symbolName)
			throws MemoryAccessException {

		Program program = ctx.getProgram();
		Memory mem = program.getMemory();
		long addend = relocation.getAddend();
		long P = relocationAddress.getOffset();
		int symIndex = relocation.getSymbolIndex();

		switch (type) {
			case R_ALPHA_NONE:
			case R_ALPHA_LITUSE: // marks uses of a LITERAL load for linker relaxation
				return RelocationResult.SKIPPED;

			case R_ALPHA_RELATIVE:
				mem.setLong(relocationAddress, ctx.getImageBaseWordAdjustmentOffset() + addend);
				return new RelocationResult(Status.APPLIED, 8);

			case R_ALPHA_DTPMOD64: // module ID: assigned by the dynamic linker
				return RelocationResult.SKIPPED;

			default:
				break;
		}

		if (handleUnresolvedSymbol(ctx, relocation, relocationAddress)) {
			return RelocationResult.FAILURE;
		}

		long S = symbolValue;
		switch (type) {
			case R_ALPHA_REFQUAD:
			case R_ALPHA_GLOB_DAT:
			case R_ALPHA_JMP_SLOT:
				mem.setLong(relocationAddress, S + addend);
				return new RelocationResult(Status.APPLIED, 8);

			case R_ALPHA_REFLONG:
				mem.setInt(relocationAddress, (int) (S + addend));
				return new RelocationResult(Status.APPLIED, 4);

			case R_ALPHA_SREL16:
				mem.setShort(relocationAddress, (short) (S + addend - P));
				return new RelocationResult(Status.APPLIED, 2);

			case R_ALPHA_SREL32:
				mem.setInt(relocationAddress, (int) (S + addend - P));
				return new RelocationResult(Status.APPLIED, 4);

			case R_ALPHA_SREL64:
				mem.setLong(relocationAddress, S + addend - P);
				return new RelocationResult(Status.APPLIED, 8);

			case R_ALPHA_BRADDR: { // 21-bit branch displacement in instructions
				int insn = mem.getInt(relocationAddress);
				long disp = (S + addend - (P + 4)) >> 2;
				mem.setInt(relocationAddress, (insn & 0xffe00000) | (int) (disp & 0x1fffff));
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_ALPHA_HINT: { // 14-bit JMP/JSR branch-prediction hint
				int insn = mem.getInt(relocationAddress);
				long disp = (S + addend - (P + 4)) >> 2;
				mem.setInt(relocationAddress, (insn & 0xffffc000) | (int) (disp & 0x3fff));
				return new RelocationResult(Status.APPLIED, 4);
			}

			case R_ALPHA_COPY:
				markAsUnsupportedCopy(program, relocationAddress, type, symbolName, symIndex,
					elfSymbol.getSize(), ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			case R_ALPHA_TLSGD:
			case R_ALPHA_TLSLDM:
			case R_ALPHA_GOTDTPREL:
			case R_ALPHA_DTPREL64:
			case R_ALPHA_DTPRELHI:
			case R_ALPHA_DTPRELLO:
			case R_ALPHA_DTPREL16:
			case R_ALPHA_GOTTPREL:
			case R_ALPHA_TPREL64:
			case R_ALPHA_TPRELHI:
			case R_ALPHA_TPRELLO:
			case R_ALPHA_TPREL16:
				markAsWarning(program, relocationAddress, type, symbolName, symIndex,
					"Thread Local Symbol relocation not supported", ctx.getLog());
				return RelocationResult.UNSUPPORTED;

			default:
				// LITERAL, GPDISP, GPREL16/32, GPRELHIGH/LOW, BRSGP: need the linker's GOT and gp
				markAsUnhandled(program, relocationAddress, type, symIndex, symbolName,
					ctx.getLog());
				return RelocationResult.UNSUPPORTED;
		}
	}
}
