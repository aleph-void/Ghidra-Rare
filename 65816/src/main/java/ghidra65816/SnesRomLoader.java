/* MIT License: see LICENSE in this module. */
package ghidra65816;

import java.io.IOException;
import java.math.BigInteger;
import java.util.*;

import ghidra.app.util.MemoryBlockUtils;
import ghidra.app.util.bin.ByteProvider;
import ghidra.app.util.opinion.*;
import ghidra.program.database.mem.FileBytes;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.data.WordDataType;
import ghidra.program.model.lang.*;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.SymbolTable;
import ghidra.program.model.util.CodeUnitInsertionException;
import ghidra.util.exception.CancelledException;

/**
 * Loads a SNES cartridge image (.sfc/.smc, with or without a 512-byte copier header) into the
 * 24-bit 65816 address space.
 * <p>
 * The internal header is looked for at the LoROM ($7FC0) and HiROM ($FFC0) positions and scored
 * on the checksum/complement pair, the map-mode byte and the reset vector. ROM is mapped where
 * the CPU sees it (LoROM: bank n at $8000-$FFFF; HiROM: bank $C0+n) with byte-mapped mirrors for
 * the other views code commonly runs from ($80+n LoROM FastROM, $00+n/$40+n HiROM). Work RAM, the
 * low-RAM mirror and the I/O register pages are created uninitialised. The reset and interrupt
 * vectors become entry points; each target gets the decode context the CPU has there: emulation
 * mode (E=1, M=X=1) for the emulation vectors including RESET, native mode with 8-bit M and X
 * for the native vectors (the real widths there are those of the interrupted code).
 */
public class SnesRomLoader extends AbstractProgramWrapperLoader {

	public static final String NAME = "SNES ROM";
	private static final LanguageCompilerSpecPair LANG =
		new LanguageCompilerSpecPair("65816:LE:16:default", "default");

	private enum Mapping { LOROM, HIROM }

	private record Layout(long skip, Mapping map, int score) {}

	@Override
	public String getName() {
		return NAME;
	}

	private static int u8(byte[] b, int o) {
		return b[o] & 0xff;
	}

	private static int u16(byte[] b, int o) {
		return u8(b, o) | u8(b, o + 1) << 8;
	}

	private static int score(ByteProvider p, long skip, Mapping m) throws IOException {
		long hdr = skip + (m == Mapping.LOROM ? 0x7fc0 : 0xffc0);
		if (hdr + 0x40 > p.length()) {
			return -1;
		}
		byte[] h = p.readBytes(hdr, 0x40);
		int s = 0;
		if ((u16(h, 0x1c) ^ u16(h, 0x1e)) == 0xffff) {
			s += 4;
		}
		int mode = u8(h, 0x15) & 0xef;
		if (m == Mapping.LOROM && mode == 0x20 || m == Mapping.HIROM && mode == 0x21) {
			s += 2;
		}
		if (u16(h, 0x3c) >= 0x8000) {
			s += 1; // reset vector points into ROM
		}
		int printable = 0;
		for (int i = 0; i < 21; i++) {
			int c = u8(h, i);
			if (c >= 0x20 && c < 0x7f) {
				printable++;
			}
		}
		if (printable == 21) {
			s += 1;
		}
		return s;
	}

	private static Layout detect(ByteProvider p) throws IOException {
		long len = p.length();
		long skip = len % 0x8000 == 512 ? 512 : 0;
		if ((len - skip) % 0x8000 != 0 || len - skip < 0x8000) {
			return null;
		}
		Layout best = null;
		for (Mapping m : Mapping.values()) {
			int s = score(p, skip, m);
			if (best == null || s > best.score) {
				best = new Layout(skip, m, s);
			}
		}
		// Require a valid checksum pair or a matching map-mode byte plus a ROM reset vector.
		return best != null && best.score >= 3 ? best : null;
	}

	@Override
	public Collection<LoadSpec> findSupportedLoadSpecs(ByteProvider provider) throws IOException {
		List<LoadSpec> specs = new ArrayList<>();
		if (detect(provider) != null) {
			specs.add(new LoadSpec(this, 0, LANG, true));
		}
		return specs;
	}

	@Override
	protected void load(Program program, ImporterSettings settings)
			throws CancelledException, IOException {
		ByteProvider p = settings.provider();
		Layout lay = detect(p);
		if (lay == null) {
			throw new IOException("not a SNES ROM image");
		}
		AddressSpace bus = program.getAddressFactory().getDefaultAddressSpace();
		Memory mem = program.getMemory();
		FileBytes fb = MemoryBlockUtils.createFileBytes(program, p, settings.monitor());
		long romLen = p.length() - lay.skip;
		var log = settings.log();
		try {
			if (lay.map == Mapping.LOROM) {
				for (long n = 0; n * 0x8000 < romLen; n++) {
					long bank = n < 0x7e ? n : 0x80 + n;
					Address a = bus.getAddress(bank << 16 | 0x8000);
					MemoryBlockUtils.createInitializedBlock(program, false,
						String.format("rom_%02X", bank), a, fb, lay.skip + n * 0x8000, 0x8000,
						"LoROM", null, true, false, true, log);
					if (n < 0x7e) {
						mem.createByteMappedBlock(String.format("rom_%02X", 0x80 + n),
							bus.getAddress((0x80 + n) << 16 | 0x8000), a, 0x8000, false)
								.setPermissions(true, false, true);
					}
				}
			}
			else {
				for (long n = 0; n * 0x10000 < romLen; n++) {
					long size = Math.min(0x10000, romLen - n * 0x10000);
					Address a = bus.getAddress((0xc0 + n) << 16);
					MemoryBlockUtils.createInitializedBlock(program, false,
						String.format("rom_%02X", 0xc0 + n), a, fb, lay.skip + n * 0x10000, size,
						"HiROM", null, true, false, true, log);
					if (n < 0x3e) {
						mem.createByteMappedBlock(String.format("rom_%02X", 0x40 + n),
							bus.getAddress((0x40 + n) << 16), a, size, false)
								.setPermissions(true, false, true);
					}
					if (n < 0x40 && size > 0x8000) {
						for (long b : new long[] { n, 0x80 + n }) {
							mem.createByteMappedBlock(String.format("rom_%02X_hi", b),
								bus.getAddress(b << 16 | 0x8000), a.add(0x8000), size - 0x8000,
								false).setPermissions(true, false, true);
						}
					}
				}
			}
			MemoryBlock wram = mem.createUninitializedBlock("wram", bus.getAddress(0x7e0000),
				0x20000, false);
			wram.setPermissions(true, true, true);
			mem.createByteMappedBlock("lowram", bus.getAddress(0), wram.getStart(), 0x2000, false)
					.setPermissions(true, true, true);
			for (long[] io : new long[][] { { 0x2100, 0x100 }, { 0x4000, 0x400 } }) {
				MemoryBlock b = mem.createUninitializedBlock(String.format("io_%04X", io[0]),
					bus.getAddress(io[0]), io[1], false);
				b.setPermissions(true, true, false);
				b.setVolatile(true);
			}
			setUpVectors(program, bus);
		}
		catch (Exception e) {
			throw new IOException("SNES ROM load failed: " + e.getMessage(), e);
		}
	}

	private static final Object[][] VECTORS = {
		// address, name, emulation mode
		{ 0xffe4, "COP_NATIVE", false }, { 0xffe6, "BRK_NATIVE", false },
		{ 0xffe8, "ABORT_NATIVE", false }, { 0xffea, "NMI_NATIVE", false },
		{ 0xffee, "IRQ_NATIVE", false }, { 0xfff4, "COP_EMULATION", true },
		{ 0xfff8, "ABORT_EMULATION", true }, { 0xfffa, "NMI_EMULATION", true },
		{ 0xfffc, "RESET", true }, { 0xfffe, "IRQBRK_EMULATION", true } };

	private void setUpVectors(Program program, AddressSpace bus) throws Exception {
		Memory mem = program.getMemory();
		SymbolTable st = program.getSymbolTable();
		Language lang = program.getLanguage();
		Register ctx = lang.getContextBaseRegister();
		Register mf = lang.getRegister("ctx_MF");
		Register xf = lang.getRegister("ctx_XF");
		Register ef = lang.getRegister("ctx_EF");
		for (Object[] v : VECTORS) {
			Address va = bus.getAddress((Integer) v[0]);
			if (!mem.contains(va, va.add(1))) {
				continue;
			}
			try {
				program.getListing().createData(va, WordDataType.dataType);
			}
			catch (CodeUnitInsertionException e) {
				// already defined
			}
			st.createLabel(va, "VEC_" + v[1], SourceType.IMPORTED);
			int target = (mem.getByte(va) & 0xff) | (mem.getByte(va.add(1)) & 0xff) << 8;
			Address t = bus.getAddress(target);
			MemoryBlock tb = mem.getBlock(t);
			if (target < 0x8000 || tb == null || !tb.isInitialized() && !tb.isMapped()) {
				continue;
			}
			st.createLabel(t, (String) v[1], SourceType.IMPORTED);
			st.addExternalEntryPoint(t);
			RegisterValue rv = new RegisterValue(ctx);
			rv = rv.assign(mf, BigInteger.ONE);
			rv = rv.assign(xf, BigInteger.ONE);
			rv = rv.assign(ef, (Boolean) v[2] ? BigInteger.ONE : BigInteger.ZERO);
			program.getProgramContext().setRegisterValue(t, t, rv);
		}
	}
}
