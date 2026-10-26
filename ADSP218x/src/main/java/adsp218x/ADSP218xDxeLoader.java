/* MIT License (see the repository LICENSE). Ghidra-Rare ADSP-218x module. */
package adsp218x;

import java.io.IOException;
import java.util.*;

import ghidra.app.util.MemoryBlockUtils;
import ghidra.app.util.bin.BinaryReader;
import ghidra.app.util.bin.ByteProvider;
import ghidra.app.util.importer.MessageLog;
import ghidra.app.util.opinion.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.LanguageCompilerSpecPair;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.symbol.SymbolUtilities;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Loader for ADSP-218x executables ("DXE") written by the VisualDSP++ 3.x linker: 32-bit
 * little-endian ELF with e_machine 30 (0x1E) and 44-byte section headers.  Allocated
 * PROGBITS sections whose flags have bit 0x2000 set are program memory (24-bit words stored
 * as 3 big-endian bytes, sh_addr a word address); the others are data memory (16-bit words,
 * 2 big-endian bytes); the rest of dm:0000-3FFF is filled with uninitialized blocks and the
 * processor's labels (memory-mapped registers, interrupt vectors) are applied.  This layout was read from linked files; the format has no public
 * specification.  The symbol table names functions (type 2) in pm and objects in dm.
 */
public class ADSP218xDxeLoader extends AbstractProgramWrapperLoader {

	public static final String NAME = "ADSP-218x VisualDSP++ DXE";
	private static final int EM_ADSP218X = 30;
	private static final int SHT_PROGBITS = 1;
	private static final int SHF_PM = 0x2000;
	private static final String LANG = "ADSP218x:BE:16:default";

	private static class Section {
		String name;
		int type, flags, info, link, entsize;
		long addr, off, size;
		boolean pm;
	}

	@Override
	public String getName() {
		return NAME;
	}

	@Override
	public LoaderTier getTier() {
		return LoaderTier.SPECIALIZED_TARGET_LOADER;
	}

	@Override
	public int getTierPriority() {
		return 40;
	}

	@Override
	public Collection<LoadSpec> findSupportedLoadSpecs(ByteProvider provider) throws IOException {
		List<LoadSpec> specs = new ArrayList<>();
		if (provider.length() < 52) {
			return specs;
		}
		BinaryReader r = new BinaryReader(provider, true);
		if (r.readInt(0) != 0x464c457f || r.readByte(4) != 1 || r.readByte(5) != 1 ||
			r.readUnsignedShort(18) != EM_ADSP218X) {
			return specs;
		}
		int shentsize = r.readUnsignedShort(46);
		if (shentsize < 40) {
			return specs;
		}
		specs.add(new LoadSpec(this, 0, new LanguageCompilerSpecPair(LANG, "default"), true));
		return specs;
	}

	@Override
	protected void load(Program program, Loader.ImporterSettings settings)
			throws CancelledException, IOException {
		ByteProvider provider = settings.provider();
		MessageLog log = settings.log();
		TaskMonitor monitor = settings.monitor();
		BinaryReader r = new BinaryReader(provider, true);
		long shoff = r.readUnsignedInt(32);
		int shentsize = r.readUnsignedShort(46);
		int shnum = r.readUnsignedShort(48);
		int shstrndx = r.readUnsignedShort(50);

		List<Section> secs = new ArrayList<>();
		for (int i = 0; i < shnum; i++) {
			long o = shoff + (long) i * shentsize;
			Section s = new Section();
			s.name = Integer.toString(r.readInt(o));
			s.type = r.readInt(o + 4);
			s.flags = r.readInt(o + 8);
			s.addr = r.readUnsignedInt(o + 12);
			s.off = r.readUnsignedInt(o + 16);
			s.size = r.readUnsignedInt(o + 20);
			s.link = r.readInt(o + 24);
			s.info = r.readInt(o + 28);
			s.entsize = r.readInt(o + 36);
			s.pm = (s.flags & SHF_PM) != 0;
			secs.add(s);
		}
		long strOff = secs.get(shstrndx).off;
		for (Section s : secs) {
			s.name = r.readAsciiString(strOff + Long.parseLong(s.name));
		}

		AddressSpace pm = program.getAddressFactory().getAddressSpace("pm");
		AddressSpace dm = program.getAddressFactory().getAddressSpace("dm");
		Memory mem = program.getMemory();
		Map<Integer, Section> byIndex = new HashMap<>();
		for (int i = 0; i < secs.size(); i++) {
			Section s = secs.get(i);
			byIndex.put(i, s);
			monitor.checkCancelled();
			if (s.type != SHT_PROGBITS || s.size == 0) {
				continue;
			}
			AddressSpace sp = s.pm ? pm : dm;
			int unit = s.pm ? 3 : 2;
			Address start = sp.getTruncatedAddress(s.addr, true);
			try {
				MemoryBlockUtils.createInitializedBlock(program, false, s.name, start,
					provider.getInputStream(s.off), s.size - s.size % unit,
					(s.pm ? "pm" : "dm") + " section", NAME, true, !s.pm, s.pm, log, monitor);
			}
			catch (Exception e) {
				log.appendMsg(NAME, "section " + s.name + ": " + e.getMessage());
			}
		}

		fillDm(program, dm, log);

		// symbols: the processor's (memory-mapped registers, vectors), then the file's
		SymbolTable st = program.getSymbolTable();
		for (ghidra.program.model.lang.AddressLabelInfo info : program.getLanguage()
				.getDefaultSymbols()) {
			try {
				st.createLabel(info.getAddress(), info.getLabel(), SourceType.IMPORTED);
			}
			catch (Exception e) {
				// processor label outside loaded memory
			}
		}
		for (Section sy : secs) {
			if (sy.type != 2) {
				continue;
			}
			long strtab = secs.get(sy.link).off;
			int esz = sy.entsize > 0 ? sy.entsize : 16;
			for (long o = sy.off; o + 16 <= sy.off + sy.size; o += esz) {
				long nameOff = r.readUnsignedInt(o);
				long value = r.readUnsignedInt(o + 4);
				int info = r.readUnsignedByte(o + 12);
				int shndx = r.readUnsignedShort(o + 14);
				Section target = byIndex.get(shndx);
				if (target == null || target.type != SHT_PROGBITS || nameOff == 0) {
					continue;
				}
				String name = r.readAsciiString(strtab + nameOff);
				if (name.isEmpty() || name.startsWith(".")) {
					continue;
				}
				Address a = (target.pm ? pm : dm).getTruncatedAddress(value, true);
				try {
					st.createLabel(a, SymbolUtilities.replaceInvalidChars(name, true),
						SourceType.IMPORTED);
					if (target.pm && (info & 0xf) == 2) {
						program.getFunctionManager().createFunction(null, a,
							new ghidra.program.model.address.AddressSet(a), SourceType.IMPORTED);
					}
				}
				catch (Exception e) {
					log.appendMsg(NAME, "symbol " + name + ": " + e.getMessage());
				}
			}
		}
		// interrupt vectors (four instructions each, pm:0000-002F, ADSP-2181 Table 3.6)
		String[] vec = { "RESET", "IRQ2", "IRQL1", "IRQL0", "SPORT0_TX", "SPORT0_RX", "IRQE",
			"BDMA", "SPORT1_TX_IRQ1", "SPORT1_RX_IRQ0", "TIMER", "POWERDOWN" };
		for (int i = 0; i < vec.length; i++) {
			Address a = pm.getTruncatedAddress(4L * i, true);
			if (mem.getBlock(a) == null || !mem.getBlock(a).isInitialized()) {
				continue;
			}
			try {
				st.createLabel(a, vec[i] + "_VECTOR", SourceType.IMPORTED);
				st.addExternalEntryPoint(a);
			}
			catch (Exception e) {
				log.appendMsg(NAME, "vector " + vec[i] + ": " + e.getMessage());
			}
		}
	}


	/** Uninitialized DM blocks around the file's DM sections (dm:0000-3FFF). */
	private void fillDm(Program program, AddressSpace dm, MessageLog log) {
		Memory mem = program.getMemory();
		long w = 0;
		while (w < 0x4000) {
			MemoryBlock b = mem.getBlock(dm.getTruncatedAddress(w, true));
			if (b != null) {
				w = b.getEnd().getAddressableWordOffset() + 1;
				continue;
			}
			long end = w;
			while (end < 0x4000 && mem.getBlock(dm.getTruncatedAddress(end, true)) == null) {
				end++;
			}
			try {
				MemoryBlockUtils.createUninitializedBlock(program, false,
					String.format("DM_%04x", w), dm.getTruncatedAddress(w, true), (end - w) * 2,
					"", NAME, true, true, false, log);
			}
			catch (Exception e) {
				log.appendMsg(NAME, "dm fill: " + e.getMessage());
			}
			w = end;
		}
	}
}
