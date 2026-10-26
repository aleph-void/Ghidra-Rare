#!/bin/bash
# Runs inside the i386 build container (see build-programs.sh): /w = workdir, /m = test/real.
set -e
T=i860-stardent-sysv4
TC=/w/tc/inst32
CC="$TC/gcc-4.0.4/bin/$T-gcc"
export PATH=$TC/bin:$PATH
RT=/m/rt
O=/w/real/obj
BIN=/w/real/bin
ZL=/w/real/src/zlib-1.3.1
EB=/w/real/src/embench-iot-embench-1.0
LIBGCC=$($CC -print-libgcc-file-name)
# -fno-guess-branch-probability works around an ICE in the GCC 4.0 i860 port (loop-iv.c).
for opt in O2 O1; do
	CF="-$opt -g -std=gnu99 -fno-guess-branch-probability -I$RT/include -I$RT"
	mkdir -p $O/$opt
	$T-as $RT/crt0.s -o $O/$opt/crt0.o
	$T-as $RT/divide.s -o $O/$opt/divide_s.o
	for f in libc libm divide boardsupport; do $CC $CF -c $RT/$f.c -o $O/$opt/$f.o; done
	RTO="$O/$opt/crt0.o"
	RTL="$O/$opt/libc.o $O/$opt/libm.o $O/$opt/divide.o $O/$opt/divide_s.o $LIBGCC"
	# zlib 1.3.1: the deflate/inflate core (no gz* file I/O) and a round-trip driver
	ZO=""
	for f in adler32 crc32 deflate inflate inffast inftrees trees zutil compress uncompr; do
		$CC $CF -DZ_SOLO -I$ZL -c $ZL/$f.c -o $O/$opt/z_$f.o
		ZO="$ZO $O/$opt/z_$f.o"
	done
	$CC $CF -DZ_SOLO -I$ZL -c $RT/zmain.c -o $O/$opt/zmain.o
	$T-ld -T $RT/link.ld $RTO $O/$opt/zmain.o $ZO $RTL -o $BIN/zlib-$opt.elf
	# Embench-IoT 1.0
	for b in $EB/src/*; do
		n=$(basename $b)
		BO=""
		ok=1
		for f in $b/*.c $EB/support/main.c $EB/support/beebsc.c; do
			o=$O/$opt/eb_${n}_$(basename $f .c).o
			if ! $CC $CF -I$EB/support -DCPU_MHZ=1 -DWARMUP_HEAT=1 -c $f -o $o 2>$O/$opt/eb_$n.err; then
				# the obsolete GCC i860 port aborts on a few files; record and skip them
				echo "SKIP $n-$opt: $(grep -m1 -E 'error|internal' $O/$opt/eb_$n.err)"
				ok=0
				break
			fi
			BO="$BO $o"
		done
		[ $ok = 1 ] && $T-ld -T $RT/link.ld $RTO $BO $O/$opt/boardsupport.o $RTL -o $BIN/$n-$opt.elf
	done
done
