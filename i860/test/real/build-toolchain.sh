#!/usr/bin/env bash
# Build the i860 test toolchain: test/real/build-toolchain.sh <workdir>
#  - GNU binutils 2.30 (the last release with the i860 target, --enable-obsolete) for the host:
#    as, ld, objdump and readelf run as black boxes by the tests -> <workdir>/tc/inst/bin
#  - GCC 4.0.4 (the last release with the i860 port) with binutils 2.30, built inside an i386
#    Debian 5 container (docker image debian/eol:lenny, pinned by digest), because the port
#    needs a 2008-era host compiler -> <workdir>/tc/inst32. test/real/patch-gcc.py lists the
#    fixes the obsolete port needs.
# Target i860-stardent-sysv4: little-endian ELF.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(readlink -m "$1"); TC=$W/tc; mkdir -p "$TC/dl"
T=i860-stardent-sysv4
get() {
	[[ -f $TC/dl/$2 ]] || curl -sSL -o "$TC/dl/$2" "$1"
	echo "$3  $TC/dl/$2" | sha256sum -c --quiet || { echo "checksum mismatch: $2" >&2; exit 1; }
}
get https://ftp.gnu.org/gnu/binutils/binutils-2.30.tar.xz binutils-2.30.tar.xz \
	6e46b8aeae2f727a36f0bd9505e405768a72218f1796f0d09757d45209871ae6
get https://ftp.gnu.org/gnu/gcc/gcc-4.0.4/gcc-core-4.0.4.tar.bz2 gcc-core-4.0.4.tar.bz2 \
	e9bf58c761a4f988311aef6b41f12fd5c7e51d09477468fb73826aecc1be32e7
cd "$TC"
[[ -d binutils-2.30 ]] || tar xf dl/binutils-2.30.tar.xz
if [[ ! -d gcc-4.0.4 ]]; then
	tar xf dl/gcc-core-4.0.4.tar.bz2
	python3 "$HERE/patch-gcc.py" gcc-4.0.4
fi
# 1. host binutils
if [[ ! -x inst/bin/$T-objdump ]]; then
	rm -rf b-bu && mkdir b-bu && cd b-bu
	../binutils-2.30/configure --target=$T --prefix="$TC/inst" --enable-obsolete --disable-nls \
		--disable-werror --disable-gdb --disable-sim CFLAGS="-O2 -fcommon -std=gnu11 -w" > cfg.log 2>&1
	make -j"$(nproc)" > make.log 2>&1 && make install > inst.log 2>&1
	cd "$TC"
fi
# 2. build container
if ! docker image inspect i860-lenny-build >/dev/null 2>&1; then
	docker rm -f i860-lenny-setup >/dev/null 2>&1 || true
	docker run --name i860-lenny-setup --platform linux/386 \
		debian/eol:lenny@sha256:c3ccfeb011d015021c84da0a502d9328dc17bdc1ca16ee503bac98a537305691 \
		sh -c 'apt-get update && apt-get install -y --force-yes gcc make bzip2' > docker-setup.log 2>&1
	docker commit i860-lenny-setup i860-lenny-build >/dev/null
	docker rm i860-lenny-setup >/dev/null
fi
# 3. binutils and GCC inside the container
cat > "$TC/cbuild.sh" <<'IN'
#!/bin/bash
set -e
T=i860-stardent-sysv4
P=/w/inst32
export PATH=$P/bin:$PATH
cd /w
if [ ! -x $P/bin/$T-as ]; then
	rm -rf c-bu; mkdir c-bu; cd c-bu
	../binutils-2.30/configure --target=$T --prefix=$P --enable-obsolete --disable-nls \
		--disable-werror --disable-gdb --disable-sim > cfg.log 2>&1
	make -j16 > make.log 2>&1; make install > inst.log 2>&1; cd ..
fi
rm -rf c-gcc; mkdir c-gcc; cd c-gcc
../gcc-4.0.4/configure --target=$T --prefix=$P/gcc-4.0.4 --enable-obsolete --enable-languages=c \
	--disable-nls --disable-shared --disable-threads --without-headers --with-newlib \
	--with-gnu-as --with-gnu-ld --with-as=$P/bin/$T-as --with-ld=$P/bin/$T-ld > cfg.log 2>&1
make -j16 all-gcc MAKEINFO=true > make.log 2>&1
make install-gcc MAKEINFO=true > inst.log 2>&1
mkdir -p $P/gcc-4.0.4/$T/bin
for t in as ld ar ranlib nm; do ln -sf ../../../bin/$T-$t $P/gcc-4.0.4/$T/bin/$t; done
IN
chmod +x "$TC/cbuild.sh"
[[ -x $TC/inst32/gcc-4.0.4/bin/$T-gcc ]] || docker run --rm --platform linux/386 \
	-u "$(id -u):$(id -g)" -v "$TC:/w" i860-lenny-build /w/cbuild.sh
"$TC/inst/bin/$T-as" --version | head -1
ls "$TC/inst32/gcc-4.0.4/bin"
