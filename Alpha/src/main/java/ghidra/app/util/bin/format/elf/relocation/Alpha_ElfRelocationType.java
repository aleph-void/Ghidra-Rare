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

/** DEC Alpha ELF relocation types (binutils include/elf/alpha.h). */
public enum Alpha_ElfRelocationType implements ElfRelocationType {

	R_ALPHA_NONE(0),
	R_ALPHA_REFLONG(1),
	R_ALPHA_REFQUAD(2),
	R_ALPHA_GPREL32(3),
	R_ALPHA_LITERAL(4),
	R_ALPHA_LITUSE(5),
	R_ALPHA_GPDISP(6),
	R_ALPHA_BRADDR(7),
	R_ALPHA_HINT(8),
	R_ALPHA_SREL16(9),
	R_ALPHA_SREL32(10),
	R_ALPHA_SREL64(11),
	R_ALPHA_GPRELHIGH(17),
	R_ALPHA_GPRELLOW(18),
	R_ALPHA_GPREL16(19),
	R_ALPHA_COPY(24),
	R_ALPHA_GLOB_DAT(25),
	R_ALPHA_JMP_SLOT(26),
	R_ALPHA_RELATIVE(27),
	R_ALPHA_BRSGP(28),
	R_ALPHA_TLSGD(29),
	R_ALPHA_TLSLDM(30),
	R_ALPHA_DTPMOD64(31),
	R_ALPHA_GOTDTPREL(32),
	R_ALPHA_DTPREL64(33),
	R_ALPHA_DTPRELHI(34),
	R_ALPHA_DTPRELLO(35),
	R_ALPHA_DTPREL16(36),
	R_ALPHA_GOTTPREL(37),
	R_ALPHA_TPREL64(38),
	R_ALPHA_TPRELHI(39),
	R_ALPHA_TPRELLO(40),
	R_ALPHA_TPREL16(41);

	public final int typeId;

	private Alpha_ElfRelocationType(int typeId) {
		this.typeId = typeId;
	}

	@Override
	public int typeId() {
		return typeId;
	}
}
