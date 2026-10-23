--entry_point=start
MEMORY
{
    PAGE 0: PRU_IMEM : org = 0x00000000 len = 0x00002000
    PAGE 1: PRU_DMEM : org = 0x00000000 len = 0x00002000
}
SECTIONS
{
    .text > PRU_IMEM, PAGE 0
}
