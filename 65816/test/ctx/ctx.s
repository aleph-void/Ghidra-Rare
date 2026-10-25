; Context-tracking test for the 65816 module: M/X/E widths after REP/SEP/XCE and across calls.
; Entry at $8000 in the reset state (E=1, M=1, X=1). Each "; expect" comment gives the operand
; Ghidra must decode (lda8 = 8-bit immediate, ...); test/ctx-test.sh checks them.
        .p816
        .smart -
        .segment "CODE"
reset:  .a8
        .i8
        sei
        clc
        xce                     ; native mode, M/X unchanged (still 8-bit)
        lda #$12                ; expect lda8
        ldx #$34                ; expect ldx8
        rep #$30
        .a16
        .i16
        lda #$1234              ; expect lda16
        ldx #$5678              ; expect ldx16
        sep #$20
        .a8
        lda #$56                ; expect lda8
        ldy #$9abc              ; expect ldy16
        jsr sub16               ; callee entered with M=1 X=0
        lda #$78                ; expect lda8 (caller context after return)
        rep #$10                ; X already 16: no change
        ldx #$def0              ; expect ldx16
        sep #$10
        .i8
        ldx #$11                ; expect ldx8
        php
        rep #$30
        .a16
        .i16
        jsl farsub
        plp                     ; restores M=X=1 saved by the php above
        .a8
        .i8
        lda #$44                ; expect lda8
        ldx #$55                ; expect ldx8
        rep #$30
        .a16
        .i16
        pea $7e20               ; P image $20: M=1, X=0
        plp
        .a8
        lda #$66                ; expect lda8
        ldx #$7788              ; expect ldx16
        plb
        sec
        xce                     ; back to emulation: M=X=1
        .i8
        lda #$22                ; expect lda8
        ldx #$33                ; expect ldx8
        bra done
sub16:  .a8
        .i16
        lda #$aa                ; expect lda8
        ldx #$bbcc              ; expect ldx16
        rep #$20
        .a16
        lda #$ddee              ; expect lda16
        rts
farsub: .a16
        .i16
        lda #$1357              ; expect lda16
        ldy #$2468              ; expect ldy16
        rtl
done:   stp
