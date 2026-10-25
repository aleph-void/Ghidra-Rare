// Runs the qemu_diff.py image in Ghidra's p-code emulator and dumps its output area.
// Script args: <qd.txt> <out.bin>   (qd.txt's first line: "# stop <addr> out <addr> len <n> ...")
//@category Testing

import java.io.FileOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.EmulateExecutionState;
import ghidra.program.model.address.Address;

public class QemuDiff extends GhidraScript {

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		String[] h = Files.readAllLines(Path.of(args[0])).get(0).split("\\s+");
		Address stop = toAddr(Long.decode(h[2]));
		Address out = toAddr(Long.decode(h[4]));
		int len = Integer.parseInt(h[6]);
		Address entry = toAddr(currentProgram.getSymbolTable().getExternalEntryPointIterator()
				.next().getOffset());
		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			emu.writeRegister(emu.getPCRegister(), entry.getOffset());
			emu.setBreakpoint(stop);
			emu.run(entry, null, monitor);
			if (emu.getEmulateExecutionState() != EmulateExecutionState.BREAKPOINT ||
				!emu.getExecutionAddress().equals(stop)) {
				throw new RuntimeException("did not reach " + stop + ": " +
					emu.getEmulateExecutionState() + " at " + emu.getExecutionAddress() + " " +
					emu.getLastError());
			}
			try (FileOutputStream f = new FileOutputStream(args[1])) {
				f.write(emu.readMemory(out, len));
			}
		}
		finally {
			emu.dispose();
		}
	}
}
