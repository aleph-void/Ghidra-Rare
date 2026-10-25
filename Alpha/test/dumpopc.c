/* Dump GNU binutils opcode tables (alpha_opcodes[], s390_opcodes[]) as text for the test
   corpora: name opcode mask flags operand-indices...
   Build: gcc -I<binutils-src>/include dumpopc.c <binutils-build>/opcodes/.libs/libopcodes.a
          <build>/bfd/.libs/libbfd.a <build>/libiberty/libiberty.a <build>/libsframe/.libs/libsframe.a -lz -lzstd */
#include <stdio.h>
#include "opcode/alpha.h"
#include "opcode/s390.h"
int main(int argc,char**argv){
  if(argv[1][0]=='a'){
    for(unsigned i=0;i<alpha_num_opcodes;i++){const struct alpha_opcode*o=&alpha_opcodes[i];
      printf("%s %08x %08x %x",o->name,o->opcode,o->mask,o->flags);
      for(int j=0;o->operands[j];j++)printf(" %d",o->operands[j]); printf("\n");}
  } else {
    for(int i=0;i<s390_num_opcodes;i++){const struct s390_opcode*o=&s390_opcodes[i];
      printf("%s ",o->name); for(int j=0;j<6;j++)printf("%02x",o->opcode[j]); printf(" ");
      for(int j=0;j<6;j++)printf("%02x",o->mask[j]);
      printf(" %d %x %x %x",o->oplen,o->modes,o->min_cpu,o->flags);
      for(int j=0;o->operands[j];j++)printf(" %d",o->operands[j]); printf("\n");}
  }
}
