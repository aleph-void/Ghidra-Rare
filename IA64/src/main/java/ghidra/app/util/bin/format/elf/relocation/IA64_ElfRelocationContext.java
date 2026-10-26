/* ###
 * Ghidra-Rare IA-64 module (MIT).
 */
package ghidra.app.util.bin.format.elf.relocation;

import java.util.*;

import ghidra.app.util.MemoryBlockUtils;
import ghidra.app.util.bin.format.elf.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.data.QWordDataType;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.MemoryAccessException;
import ghidra.program.model.mem.MemoryBlock;

/**
 * Relocation context for IA-64: the global pointer and an artificial linkage block holding the
 * official function descriptors ({entry, gp}) and linkage-table entries that relocations need
 * but the loaded image does not provide. The block is shared by every relocation table of a
 * program.
 */
public class IA64_ElfRelocationContext extends ElfRelocationContext<IA64_ElfRelocationHandler> {

	private static final int LINKAGE_SIZE = 0x20000;

	private static final class Linkage {
		Address base;
		long next;
		long end;
		final Map<Long, Long> descriptors = new HashMap<>();
		final Map<Long, Long> entries = new HashMap<>();
		Long gp;
	}

	private static final Map<Program, Linkage> LINKAGE = new WeakHashMap<>();

	IA64_ElfRelocationContext(IA64_ElfRelocationHandler handler, ElfLoadHelper loadHelper,
			Map<ElfSymbol, Address> symbolMap) {
		super(handler, loadHelper, symbolMap);
	}

	private Linkage linkage() {
		synchronized (LINKAGE) {
			return LINKAGE.computeIfAbsent(program, p -> new Linkage());
		}
	}

	private boolean isRelocatable() {
		return getElfHeader().isRelocatable();
	}

	/** Global pointer of this module (DT_PLTGOT, else __gp, else the GOT; relocatable objects use
	 *  the start of the artificial linkage block). */
	public long getGp() {
		Linkage l = linkage();
		if (l.gp != null) {
			return l.gp;
		}
		long gp = 0;
		if (isRelocatable()) {
			allocate(l);
			gp = l.base != null ? l.base.getOffset() : 0;
		}
		else {
			Long v = IA64GpUtil.findGp(loadHelper);
			if (v != null) {
				gp = v;
			}
		}
		l.gp = gp;
		return gp;
	}

	private void allocate(Linkage l) {
		if (l.base != null || l.end < 0) {
			return;
		}
		AddressRange range = loadHelper.allocateLinkageBlock(16, LINKAGE_SIZE, "%ia64.linkage");
		if (range == null) {
			l.end = -1;
			loadHelper.log("Failed to allocate the IA-64 linkage block for descriptors");
			return;
		}
		try {
			MemoryBlock block = MemoryBlockUtils.createInitializedBlock(program, false,
				"%ia64.linkage", range.getMinAddress(), LINKAGE_SIZE,
				"NOTE: artificial block: function descriptors and linkage-table entries created " +
					"by the IA-64 relocation handler",
				"Elf Loader", true, false, false, loadHelper.getLog());
			block.setArtificial(true);
			l.base = range.getMinAddress();
			l.next = 0;
			l.end = LINKAGE_SIZE;
		}
		catch (Exception e) {
			l.end = -1;
			loadHelper.log("Failed to create the IA-64 linkage block: " + e.getMessage());
		}
	}

	private long alloc(Linkage l, int size) {
		allocate(l);
		if (l.base == null || l.next + size > l.end) {
			return -1;
		}
		long off = l.next;
		l.next += size;
		return off;
	}

	private void put64(Address a, long v) throws MemoryAccessException {
		byte[] b = new byte[8];
		boolean be = program.getMemory().isBigEndian();
		for (int i = 0; i < 8; i++) {
			b[be ? 7 - i : i] = (byte) (v >>> (8 * i));
		}
		program.getMemory().setBytes(a, b);
	}

	/**
	 * Address of the official function descriptor {entry, gp} for a function entry; external
	 * functions get gp 0.
	 */
	public long functionDescriptor(long entry, boolean external) throws MemoryAccessException {
		Linkage l = linkage();
		Long d = l.descriptors.get(entry);
		if (d != null) {
			return d;
		}
		long gp = external ? 0 : getGp();
		long off = alloc(l, 16);
		if (off < 0) {
			return entry;
		}
		Address a = l.base.add(off);
		put64(a, entry);
		put64(a.add(8), gp);
		loadHelper.createData(a, PointerDataType.dataType);
		loadHelper.createData(a.add(8), QWordDataType.dataType);
		l.descriptors.put(entry, a.getOffset());
		if (!external && (entry & 0xf) == 0) {
			// an @fptr target is a function entry
			Address e = a.getNewAddress(entry);
			MemoryBlock b = program.getMemory().getBlock(e);
			if (b != null && b.isExecute() && b.isInitialized()) {
				loadHelper.createOneByteFunction(null, e, false);
			}
		}
		return a.getOffset();
	}

	/** Address of a linkage-table entry (an 8-byte word in the linkage block) holding value. */
	public long linkageEntry(long value) throws MemoryAccessException {
		Linkage l = linkage();
		Long d = l.entries.get(value);
		if (d != null) {
			return d;
		}
		getGp();
		long off = alloc(l, 8);
		if (off < 0) {
			return 0;
		}
		Address a = l.base.add(off);
		put64(a, value);
		loadHelper.createData(a, PointerDataType.dataType);
		l.entries.put(value, a.getOffset());
		return a.getOffset();
	}

	/** Base for SEGREL relocations: the lowest executable block. */
	public long segmentBase() {
		long base = Long.MAX_VALUE;
		for (MemoryBlock b : program.getMemory().getBlocks()) {
			if (b.isExecute() && b.isInitialized() && b.getStart().isMemoryAddress()) {
				base = Math.min(base, b.getStart().getOffset());
			}
		}
		return base == Long.MAX_VALUE ? 0 : base;
	}

	/** Load address of the section that defines the symbol (SECREL relocations). */
	public long sectionBase(ElfSymbol sym) {
		int idx = sym.getSectionHeaderIndex();
		ElfSectionHeader[] sections = getElfHeader().getSections();
		if (idx <= 0 || idx >= sections.length) {
			return 0;
		}
		Address a = loadHelper.findLoadAddress(sections[idx], 0);
		return a != null ? a.getOffset() : 0;
	}
}
