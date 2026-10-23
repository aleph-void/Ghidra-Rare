// Checks which C7x core an imported TI C7000 ELF was built for and warns if the program's language
// does not match.  The core is not recorded in the ELF header (e_flags is 0); TI's linker writes it
// to the ".c7xabi.attributes" section (vendor "c7xabi", file attribute tag 4):
//   1 = C7100, 2 = C7120, 4 = C7504, 7 = C7524
// The section is read from the program's memory blocks (Ghidra keeps non-allocated ELF sections as
// "other" blocks by default) or, failing that, from the original file on disk.
// Headless: -postScript C7xCoreCheck.java   (prints the language ID to use with -processor)
//@category C7x

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class C7xCoreCheck extends GhidraScript {

	private static String coreName(int isa) {
		switch (isa) {
			case 1: return "C7100";
			case 2: return "C7120";
			case 4: return "C7504";
			case 7: return "C7524";
			default: return null;
		}
	}

	@Override
	protected void run() throws Exception {
		byte[] attrs = fromMemory();
		String where = "memory block";
		if (attrs == null) {
			attrs = fromFile();
			where = "file " + currentProgram.getExecutablePath();
		}
		if (attrs == null) {
			println("C7xCoreCheck: no .c7xabi.attributes section found; cannot tell the core. " +
				"Current language: " + currentProgram.getLanguageID());
			return;
		}
		int isa = parseIsa(attrs);
		String core = coreName(isa);
		if (core == null) {
			println("C7xCoreCheck: .c7xabi.attributes (" + where + ") has no known ISA tag (tag 4 = " +
				isa + ")");
			return;
		}
		String want = "C7x:LE:64:" + core;
		String have = currentProgram.getLanguageID().getIdAsString();
		if (want.equals(have)) {
			println("C7xCoreCheck: built for " + core + "; language " + have + " is correct.");
		}
		else {
			String msg = "C7xCoreCheck: this program was built for " + core + " (.c7xabi.attributes tag 4 = " +
				isa + ") but is loaded as " + have + ".\nRe-import it with language " + want +
				" (GUI: Language field of the import dialog; headless: -processor " + want + ").";
			println(msg);
			if (!isRunningHeadless()) {
				popup(msg);
			}
		}
	}

	private byte[] fromMemory() {
		for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
			if (b.getName().equals(".c7xabi.attributes") && b.isInitialized()) {
				byte[] data = new byte[(int) b.getSize()];
				try {
					b.getBytes(b.getStart(), data);
					return data;
				}
				catch (Exception e) {
					return null;
				}
			}
		}
		return null;
	}

	/** Minimal ELF64 little-endian section-header walk. */
	private byte[] fromFile() {
		String path = currentProgram.getExecutablePath();
		if (path == null || !new File(path).isFile()) {
			return null;
		}
		try (RandomAccessFile f = new RandomAccessFile(path, "r")) {
			byte[] eh = new byte[64];
			f.readFully(eh);
			if (eh[0] != 0x7f || eh[1] != 'E' || eh[4] != 2 || eh[5] != 1) {
				return null;
			}
			ByteBuffer h = ByteBuffer.wrap(eh).order(ByteOrder.LITTLE_ENDIAN);
			long shoff = h.getLong(0x28);
			int shentsize = h.getShort(0x3a) & 0xffff;
			int shnum = h.getShort(0x3c) & 0xffff;
			int shstrndx = h.getShort(0x3e) & 0xffff;
			long[][] sh = new long[shnum][];
			for (int i = 0; i < shnum; i++) {
				byte[] e = new byte[shentsize];
				f.seek(shoff + (long) i * shentsize);
				f.readFully(e);
				ByteBuffer s = ByteBuffer.wrap(e).order(ByteOrder.LITTLE_ENDIAN);
				sh[i] = new long[] { s.getInt(0) & 0xffffffffL, s.getLong(0x18), s.getLong(0x20) };
			}
			byte[] names = new byte[(int) sh[shstrndx][2]];
			f.seek(sh[shstrndx][1]);
			f.readFully(names);
			for (int i = 0; i < shnum; i++) {
				int n = (int) sh[i][0];
				int end = n;
				while (end < names.length && names[end] != 0) {
					end++;
				}
				String name = new String(names, n, end - n, StandardCharsets.US_ASCII);
				if (name.equals(".c7xabi.attributes")) {
					byte[] data = new byte[(int) sh[i][2]];
					f.seek(sh[i][1]);
					f.readFully(data);
					return data;
				}
			}
		}
		catch (Exception e) {
			return null;
		}
		return null;
	}

	private static long[] uleb(byte[] d, int p) {
		long v = 0;
		int shift = 0;
		while (p < d.length) {
			int b = d[p++] & 0xff;
			v |= (long) (b & 0x7f) << shift;
			shift += 7;
			if ((b & 0x80) == 0) {
				break;
			}
		}
		return new long[] { v, p };
	}

	/** ARM-style build attributes: 'A' { u32 len, vendor\0, { tag, u32 len, attrs } }. */
	private static int parseIsa(byte[] d) {
		if (d.length < 1 || d[0] != 'A') {
			return -1;
		}
		ByteBuffer b = ByteBuffer.wrap(d).order(ByteOrder.LITTLE_ENDIAN);
		int p = 1;
		while (p + 4 <= d.length) {
			int len = b.getInt(p);
			if (len <= 0 || p + len > d.length) {
				break;
			}
			int end = p + len;
			int q = p + 4;
			int v0 = q;
			while (q < end && d[q] != 0) {
				q++;
			}
			String vendor = new String(d, v0, q - v0, StandardCharsets.US_ASCII);
			q++;
			while (vendor.equals("c7xabi") && q + 5 <= end) {
				int tag = d[q] & 0xff;
				int slen = b.getInt(q + 1);
				int send = Math.min(q + slen, end);
				int r = q + 5;
				if (tag == 1) {   // file attributes: uleb tag, uleb value (all integer-valued here)
					while (r < send) {
						long[] t = uleb(d, r);
						long[] v = uleb(d, (int) t[1]);
						if (t[0] == 4) {
							return (int) v[0];
						}
						r = (int) v[1];
					}
				}
				if (slen <= 0) {
					break;
				}
				q += slen;
			}
			p = end;
		}
		return -1;
	}
}
