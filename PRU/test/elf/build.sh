#!/usr/bin/env bash
# Rebuild demo_v3.elf with TI PRU CGT:  TI_CGT=/path/to/ti-cgt-pru_2.3.3 ./build.sh
set -euo pipefail
cd "$(dirname "$0")"
if [[ -n ${TI_CGT:-} ]]; then
"$TI_CGT/bin/clpru" -v3 -O2 --hardware_mac=on -i"$TI_CGT/include" demo.c demo_asm.asm -z demo.cmd \
	-i"$TI_CGT/lib" -l"$TI_CGT/lib/rtspruv3_le.lib" -o demo_v3.elf >/dev/null
rm -f demo.obj demo_asm.obj
fi
# GNU pru-elf variant (binutils 2.45 gas/ld):  PRU_AS=... PRU_LD=... ./build.sh
if [[ -n ${PRU_AS:-} && -n ${PRU_LD:-} ]]; then
	"$PRU_AS" -o gnu_demo.o gnu_demo.s && "$PRU_LD" -o gnu_demo.elf gnu_demo.o && rm -f gnu_demo.o
fi
