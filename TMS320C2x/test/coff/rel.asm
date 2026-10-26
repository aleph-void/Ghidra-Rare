* Relocation test object for the TI COFF relocation handler (original test input, MIT).
* R_PARTMS9 (LDP #sym), R_PARTLS7 (direct dma), R_RELWORD (branch, .word, long immediates)
* against .bss, .data, .text and an undefined external symbol.
        .global EXTF
        .bss    BUF,4
        .data
TAB     .word   1,2,3
        .text
START   LDP     #BUF
        LACC    BUF
        SACL    BUF+1
        B       NEXT
        .word   TAB
NEXT    CALL    EXTF
        ADD     #TAB
        MPY     #TAB
        LAR     AR1,#BUF
        RET
