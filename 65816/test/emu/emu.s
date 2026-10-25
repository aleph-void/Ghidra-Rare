; P-code emulation cases for the 65816 module (assembled with ca65, linked at $8000).
; Every case starts at t_<name> and ends at the stp after it; emu_cases.txt gives the
; initial registers/memory and the hand-computed results.
        .p816
        .smart -
        .segment "CODE"
        .a8
        .i8
t_adc8v:    clc
            adc #$01            ; $7f + 1
            stp
t_adc8c:    clc
            adc #$01            ; $ff + 1
            stp
            .a16
t_adc16v:   clc
            adc #$0001          ; $7fff + 1
            stp
            .a8
t_adcbcd8:  sed
            clc
            adc #$28            ; BCD 19 + 28
            stp
t_adcbcd8c: sed
            clc
            adc #$01            ; BCD 99 + 01
            stp
            .a16
t_adcbcd16: sed
            clc
            adc #$0001          ; BCD 1999 + 1
            stp
            .a8
t_sbc8:     sec
            sbc #$20            ; $10 - $20
            stp
t_sbcbcd8:  sed
            sec
            sbc #$01            ; BCD 10 - 01
            stp
            .a16
t_cmp16:    cmp #$1234
            php                 ; status after equal compare -> stack
            cmp #$2000
            stp
            .i8
t_cpx8:     cpx #$20
            stp
            .a8
t_ldadp:    lda $10             ; D=$0100 -> $000110
            stp
t_ldaabs:   lda $2000           ; DBR=$7e -> $7e2000
            stp
            .a16
t_ldaabsx:  lda $fff8,x         ; DBR=$7e, X=$10 -> $7f0008 (crosses the bank)
            stp
            .a8
t_ldadiy:   lda ($20),y         ; ptr $3000, DBR=$7e, Y=2 -> $7e3002
            stp
t_ldadil:   lda [$30]           ; long ptr $7f1234
            stp
t_ldasr:    lda $03,s           ; SP=$1ff0 -> $001ff3
            stp
t_stalong:  sta f:$7e1000
            stp
            .a16
t_sta16:    sta $0200           ; DBR=0, writes $0200/$0201
            stp
t_jsr:      jsr sub_jsr
            stp
sub_jsr:    lda #$4242
            rts
t_jsl:      jsl sub_jsl
            stp
sub_jsl:    lda #$1111
            rtl
            .i16
            .a8
t_loop:     lda #$00
@l:         inc a
            dex
            bne @l
            stp
t_brl:      brl @far
            lda #$01
            stp
@far:       lda #$02
            stp
t_repsep:   sep #$c3            ; N V Z C set
            rep #$41            ; V C cleared
            stp
t_xba:      xba
            stp
            .a16
            .i16
t_mvn:      mvn #$7e,#$7e       ; copy C+1 = 3 bytes from X to Y
            stp
t_pha16:    pha
            lda #$0000
            pla
            stp
            .a8
            .i8
t_php:      php                 ; P = $e3 in emulation-free native M=X=1 state
            pla
            stp
t_tsb:      tsb $40
            stp
t_trb:      trb $41
            stp
t_asl:      asl a
            stp
t_ror:      sec
            ror a
            stp
            .a16
t_inc16:    inc a
            stp
            .a8
t_per:      per t_per
            stp
t_pea:      pea $beef
            stp
            .i16
t_txa8:     txa                 ; M=1, X=16-bit: A = low byte of X, B kept
            stp
            .a16
t_tcs:      tcs
            tsc
            stp
t_biti:     bit #$8000          ; immediate BIT: Z only
            stp
            .a8
            .i8
t_emupha:   pha                 ; emulation mode: SP wraps within page 1
            stp
t_jmpind:   jmp ($0300)
            stp
t_jmpind_t: lda #$77
            stp
t_jmpidx:   jmp ($0300,x)
            stp
t_beq:      lda #$00
            beq @t
            lda #$01
@t:         stp
            .a8
            .i8
t_dpwrap:   lda $ff,x           ; emulation mode, DP=0: wraps to $0001; native: $0101
            stp
t_plp:      plp
            stp
            .i16
t_sepx:     sep #$10            ; 16 -> 8-bit index: high bytes cleared
            stp
