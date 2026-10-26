/* MIT License (see the repository LICENSE). Ghidra-Rare DSP56000 module. */
package dsp56000;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;

import ghidra.app.util.MemoryBlockUtils;
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
 * Loader for Motorola DSP "LOD" absolute load files, the ASCII output of the Motorola DSP
 * linker/assembler (asm56000, asm56100, dsplnk, cldlod): records
 * <pre>
 *   _START name ver rev ...      header
 *   _DATA P|X|Y|L addr           data words (hex) from addr on, P/X/Y spaces; L = X:Y pairs
 *   _BLOCKDATA space addr count value
 *   _SYMBOL P|X|Y|L|N            "name I|F value" lines
 *   _COMMENT ...                 ignored
 *   _END addr                    entry point
 * </pre>
 * Words of six hex digits select the DSP56000 language, four digits the DSP56156 one.
 * Contiguous words become initialized blocks; the rest of X and Y stays uninitialized.
 */
public class DspLodLoader extends AbstractProgramWrapperLoader {

	public static final String NAME = "Motorola DSP LOD";
	private static final String LANG_56000 = "DSP56000:BE:16:default";
	private static final String LANG_56156 = "DSP56000:BE:16:DSP56156";

	private static class Lod {
		int digits = 0;
		final Map<String, TreeMap<Long, Long>> data = new LinkedHashMap<>();
		final List<String[]> symbols = new ArrayList<>();
		Long entry;
		String name;
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

	private static Lod parse(ByteProvider provider, boolean full) throws IOException {
		Lod lod = new Lod();
		try (BufferedReader r = new BufferedReader(
			new InputStreamReader(provider.getInputStream(0), StandardCharsets.ISO_8859_1))) {
			String line = r.readLine();
			if (line == null || !line.startsWith("_START")) {
				return null;
			}
			String[] h = line.trim().split("\\s+");
			lod.name = h.length > 1 ? h[1] : "lod";
			String section = null;
			String space = null;
			long addr = 0;
			String symSpace = null;
			boolean lY = false;
			int lines = 0;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				String[] f = line.split("\\s+");
				if (f[0].startsWith("_")) {
					section = f[0];
					if (section.equals("_DATA") && f.length >= 3) {
						space = f[1].toUpperCase();
						addr = Long.parseLong(f[2], 16);
						lY = false;
					}
					else if (section.equals("_BLOCKDATA") && f.length >= 5) {
						String sp = f[1].toUpperCase();
						long a = Long.parseLong(f[2], 16);
						long n = Long.parseLong(f[3], 16);
						long v = Long.parseLong(f[4], 16);
						noteDigits(lod, f[4]);
						for (long i = 0; i < n; i++) {
							put(lod, sp, a + i, v);
						}
					}
					else if (section.equals("_SYMBOL")) {
						symSpace = f.length > 1 ? f[1].toUpperCase() : "N";
					}
					else if (section.equals("_END")) {
						// normally the last record; some hand-made files have more after it
						if (f.length > 1) {
							lod.entry = Long.parseLong(f[1].replace("$", ""), 16);
						}
					}
					continue;
				}
				if ("_DATA".equals(section)) {
					for (String w : f) {
						noteDigits(lod, w);
						long v = Long.parseLong(w, 16);
						if (space.equals("L")) {
							// L memory: the X word, then the Y word, of each address
							put(lod, lY ? "Y" : "X", addr, v);
							if (lY) {
								addr++;
							}
							lY = !lY;
						}
						else {
							put(lod, space, addr++, v);
						}
					}
				}
				else if ("_SYMBOL".equals(section) && f.length >= 3) {
					lod.symbols.add(new String[] { symSpace, f[0], f[1], f[2] });
				}
				if (!full && ++lines > 64 && lod.digits != 0) {
					break;
				}
			}
		}
		catch (NumberFormatException e) {
			return null;
		}
		return lod.digits == 0 && lod.data.isEmpty() ? null : lod;
	}

	private static void noteDigits(Lod lod, String w) {
		if (lod.digits == 0 && (w.length() == 6 || w.length() == 4)) {
			lod.digits = w.length();
		}
	}

	private static void put(Lod lod, String space, long a, long v) {
		lod.data.computeIfAbsent(space, k -> new TreeMap<>()).put(a & 0xffff, v);
	}

	@Override
	public Collection<LoadSpec> findSupportedLoadSpecs(ByteProvider provider) throws IOException {
		List<LoadSpec> specs = new ArrayList<>();
		byte[] head = provider.readBytes(0, Math.min(6, provider.length()));
		if (!new String(head, StandardCharsets.ISO_8859_1).equals("_START")) {
			return specs;
		}
		Lod lod = parse(provider, false);
		if (lod == null) {
			return specs;
		}
		String lang = lod.digits == 4 ? LANG_56156 : LANG_56000;
		specs.add(new LoadSpec(this, 0, new LanguageCompilerSpecPair(lang, "default"), true));
		return specs;
	}

	@Override
	protected void load(Program program, Loader.ImporterSettings settings)
			throws CancelledException, IOException {
		ByteProvider provider = settings.provider();
		MessageLog log = settings.log();
		TaskMonitor monitor = settings.monitor();
		Lod lod = parse(provider, true);
		if (lod == null) {
			throw new IOException("not a LOD file");
		}
		Memory mem = program.getMemory();
		Map<String, AddressSpace> spaces = new HashMap<>();
		for (String s : new String[] { "P", "X", "Y" }) {
			AddressSpace sp = program.getAddressFactory().getAddressSpace(s.toLowerCase());
			if (sp != null) {
				spaces.put(s, sp);
			}
		}
		// the language's default (uninitialized) data blocks are rebuilt around the file data
		for (MemoryBlock b : mem.getBlocks()) {
			String n = b.getStart().getAddressSpace().getName();
			if (n.equals("x") || n.equals("y")) {
				try {
					mem.removeBlock(b, monitor);
				}
				catch (Exception e) {
					log.appendMsg(NAME, "cannot remove block " + b.getName() + ": " + e);
				}
			}
		}
		for (Map.Entry<String, TreeMap<Long, Long>> e : lod.data.entrySet()) {
			AddressSpace sp = spaces.get(e.getKey());
			if (sp == null) {
				log.appendMsg(NAME, "no memory space " + e.getKey() + " in this language");
				continue;
			}
			int unit = sp.getAddressableUnitSize();
			Long runStart = null;
			long prev = -2;
			List<Long> run = new ArrayList<>();
			for (Map.Entry<Long, Long> w : e.getValue().entrySet()) {
				monitor.checkCancelled();
				if (w.getKey() != prev + 1 && !run.isEmpty()) {
					block(program, sp, runStart, run, unit, log, monitor);
					run.clear();
				}
				if (run.isEmpty()) {
					runStart = w.getKey();
				}
				run.add(w.getValue());
				prev = w.getKey();
			}
			if (!run.isEmpty()) {
				block(program, sp, runStart, run, unit, log, monitor);
			}
		}
		for (String s : new String[] { "X", "Y" }) {
			if (spaces.containsKey(s)) {
				fill(program, spaces.get(s), log);
			}
		}
		SymbolTable st = program.getSymbolTable();
		for (String[] sy : lod.symbols) {
			AddressSpace sp = spaces.get(sy[0]);
			if (sp == null) {
				continue;
			}
			try {
				long v = Long.parseLong(sy[3], 16);
				Address a = sp.getTruncatedAddress(v & 0xffff, true);
				st.createLabel(a, SymbolUtilities.replaceInvalidChars(sy[1], true),
					SourceType.IMPORTED);
			}
			catch (Exception ex) {
				log.appendMsg(NAME, "symbol " + sy[1] + ": " + ex.getMessage());
			}
		}
		if (lod.entry != null && spaces.containsKey("P")) {
			Address a = spaces.get("P").getTruncatedAddress(lod.entry, true);
			if (mem.contains(a)) {
				st.addExternalEntryPoint(a);
			}
		}
	}

	private static void block(Program program, AddressSpace sp, long start, List<Long> words,
			int unit, MessageLog log, TaskMonitor monitor) {
		byte[] b = new byte[words.size() * unit];
		for (int i = 0; i < words.size(); i++) {
			long v = words.get(i);
			for (int k = 0; k < unit; k++) {
				b[i * unit + k] = (byte) (v >> (8 * (unit - 1 - k)));
			}
		}
		String name = String.format("%s_%04X", sp.getName().toUpperCase(), start);
		try {
			MemoryBlockUtils.createInitializedBlock(program, false, name,
				sp.getTruncatedAddress(start, true), new java.io.ByteArrayInputStream(b), b.length,
				"LOD data", NAME, true, !sp.getName().equals("p"), sp.getName().equals("p"), log,
				monitor);
		}
		catch (Exception e) {
			log.appendMsg(NAME, name + ": " + e.getMessage());
		}
	}

	/** Uninitialized blocks over the rest of a 64K-word data space. */
	private static void fill(Program program, AddressSpace sp, MessageLog log) {
		Memory mem = program.getMemory();
		long w = 0;
		while (w <= 0xffff) {
			MemoryBlock b = mem.getBlock(sp.getTruncatedAddress(w, true));
			if (b != null) {
				w = b.getEnd().getAddressableWordOffset() + 1;
				continue;
			}
			long e = w;
			while (e < 0xffff && mem.getBlock(sp.getTruncatedAddress(e + 1, true)) == null) {
				e++;
			}
			try {
				MemoryBlockUtils.createUninitializedBlock(program, false,
					String.format("%s_%04X", sp.getName().toUpperCase(), w),
					sp.getTruncatedAddress(w, true), (e - w + 1) * sp.getAddressableUnitSize(),
					"data memory", NAME, true, true, false, log);
			}
			catch (Exception ex) {
				log.appendMsg(NAME, "fill: " + ex.getMessage());
			}
			w = e + 1;
		}
	}
}
