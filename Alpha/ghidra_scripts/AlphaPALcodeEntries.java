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
// Marks the hardware entry points of an Alpha PALcode image: the exception/interrupt vectors
// and the CALL_PAL entries, which nothing in the code branches to. PALcode is entered at
// fixed offsets from PAL_BASE:
//   21264 (EV6):  vectors at PAL_BASE + 0x000..0x780 (every 0x80); CALL_PAL privileged
//                 functions 0x00-0x3f at 0x2000 + 0x40*f, unprivileged 0x80-0xbf at 0x3000 + 0x40*(f-0x80)
//   21164 (EV5) and 21064 (EV4): the same CALL_PAL layout; vectors every 0x100 / 0x20 from
//                 PAL_BASE (21164 HRM 5.2, 21064 HRM 6.4). Vector offsets that fall inside
//                 another vector's code are skipped automatically (not disassemblable there).
// Arguments (headless): [PAL_BASE hex]. Default: the start of the lowest executable block.
//@category Alpha
//@menupath Analysis.Alpha.Mark PALcode entry points

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

public class AlphaPALcodeEntries extends GhidraScript {

	@Override
	protected void run() throws Exception {
		Address base = null;
		String[] args = getScriptArgs();
		if (args.length > 0) {
			base = toAddr(Long.parseUnsignedLong(args[0].replaceFirst("^0x", ""), 16));
		}
		else {
			for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
				if (b.isExecute() && (base == null || b.getStart().compareTo(base) < 0)) {
					base = b.getStart();
				}
			}
		}
		String cpu = currentProgram.getLanguageID().getIdAsString();
		int vecStep = cpu.startsWith("21064") ? 0x20 : cpu.startsWith("21164") ? 0x100 : 0x80;
		int vecEnd = cpu.startsWith("21064") ? 0x2000 : cpu.startsWith("21164") ? 0x2000 : 0x800;
		int n = 0;
		for (int off = 0; off < vecEnd; off += vecStep) {
			n += mark(base.add(off), String.format("pal_vector_%04x", off));
		}
		for (int f = 0; f < 0x40; f++) {
			n += mark(base.add(0x2000 + 0x40 * f), String.format("call_pal_%02x", f));
			n += mark(base.add(0x3000 + 0x40 * f), String.format("call_pal_%02x", 0x80 + f));
		}
		println("PALcode entry points marked: " + n + " (PAL_BASE " + base + ")");
	}

	private int mark(Address a, String name) throws Exception {
		if (!currentProgram.getMemory().contains(a) ||
			currentProgram.getListing().getDefinedDataContaining(a) != null) {
			return 0;
		}
		if (currentProgram.getListing().getInstructionAt(a) == null) {
			if (currentProgram.getListing().getInstructionContaining(a) != null) {
				return 0;
			}
			DisassembleCommand cmd = new DisassembleCommand(a, null, true);
			if (!cmd.applyTo(currentProgram, monitor) ||
				currentProgram.getListing().getInstructionAt(a) == null) {
				return 0;
			}
		}
		createLabel(a, name, true, SourceType.ANALYSIS);
		if (getFunctionAt(a) == null) {
			new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
		}
		return 1;
	}
}
