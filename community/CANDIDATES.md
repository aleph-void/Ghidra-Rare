# Community SLEIGH implementations: candidates

Survey date 2026-10-25. Sources: all 2,160 pull requests to NationalSecurityAgency/ghidra (changed files checked for new processors or `.slaspec` files), GitHub code search for `.slaspec` files (sharded by size), and repository search by name, description and topic. Copies of Ghidra's own specs are excluded by comparing against the 152 `.slaspec` names in Ghidra master.

126 CPUs not supported by Ghidra 12.2. Where several implementations exist, the most complete one that compiles and is licensed for redistribution is picked; metrics are constructors in the SLEIGH, `unimpl` p-code bodies, spec files, Java, tests and whether every `.slaspec` compiles with Ghidra 12.1.4's `sleigh`. These are first-pass selections; verification can change them.

License status: **90 permissive**, **7 copyleft** (GPL/LGPL), **29 blocked** (no license, non-commercial or unclear: cannot be redistributed without the author's permission).

Pull requests are covered by Ghidra's contribution terms (Apache-2.0).

| CPU | Selected source | License | Compiles | Constructors | Original authors (credit) | Alternatives / notes |
|---|---|---|---|---|---|---|
| 65816 (SNES) | [kaayzouee/ghidra-65816](https://github.com/kaayzouee/ghidra-65816) | MIT (ok) | 1/1 | 277 | @achan1989, @kaayzouee, @greg-kennedy; also @achan1989, @greg-kennedy (achan1989/ghidra-65816) | achan1989's history (original, credit) plus Kay's semantic fixes (145 lines of the SLEIGH differ); saffronisa/ghidra-saffron is an unmodified copy of achan1989 Alternatives: achan1989/ghidra-65816, saffronisa/ghidra-saffron. |
| ADI SHARC | [roblg/ghidra-sharc](https://github.com/roblg/ghidra-sharc) | Apache-2.0 (ok) | 1/1 | 2774 | @roblg | Only implementation found |
| Adreno SQE (QRISC) | [locus-x64/ida-adreno-qrisc](https://github.com/locus-x64/ida-adreno-qrisc) | MIT (ok) | 3/3 | 118 | @locus-x64 | Only implementation found |
| Aeon R2 | [eb4x/ghidra-plugin-aeon](https://github.com/eb4x/ghidra-plugin-aeon) | Apache-2.0 (ok) | 3/3 | 816 | @eb4x | Only implementation found |
| AMD Am29000 | [mumbel/ghidra_a29k](https://github.com/mumbel/ghidra_a29k) | Apache-2.0 (ok) | 2/2 | 160 | @mumbel | Only implementation found |
| AMD Radeon F32 | [cyrozap/ghidra-radeon-f32](https://github.com/cyrozap/ghidra-radeon-f32) | Apache-2.0 (ok) | 2/2 | 112 | @cyrozap | Only implementation found |
| ARC 32-bit (legacy ARCtangent) | [PR#3233](https://github.com/NationalSecurityAgency/ghidra/pull/3233) | Apache-2.0 (Ghidra contribution) (ok) | 2/2 | 225 | @cyrozap (commits: cyrozap) | Only implementation found |
| ARCompact (ARC600/700) | [PR#3006](https://github.com/NationalSecurityAgency/ghidra/pull/3006) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 540 | @niooss-ledger (commits: Nicolas Iooss) | ARCompact (ARC600/700); BonusPlay repo carries the same SLEIGH unlicensed. ARC 32-bit legacy (PR#3233) and ARCv2 (PR#6344, does not compile) listed separately Alternatives: BonusPlay/ghidra-arcompact, JacksonDonaldson/arcompact_be_ghidra, PR#3233, PR#6344. |
| ARCv2 (ARC EM/HS) | [sony/ARCv2_Ghidra](https://github.com/sony/ARCv2_Ghidra) | Apache-2.0 (ok) | ? | ? | Sony | Not yet surveyed. PR#6344 (@dgenin, 121 constructors, does not compile) turned out to be ARCtangent-A4, the same ISA as PR#3233 (published as ARC32). Alternatives: korkikian/ARCv2 (no license) |
| Blackfin | [geepot/ghidra-blackfin](https://github.com/geepot/ghidra-blackfin) | GPL-3.0-or-later (copyleft) | 1/1 | 766 | @geepot | 766 constructors, 0 unimpl vs sualk 594 with 294 unimpl; GPL-3.0-or-later Alternatives: hekar-lab/Ghidra-BlackFinPlus, sualk/ghidra-blackfin. |
| BQ 8-bit (TI gauge) | [solar-pwr/bq8bit](https://github.com/solar-pwr/bq8bit) | Apache-2.0 (ok) | 1/1 | 213 | @solar-pwr | Only implementation found |
| Broadcom VideoCore IV | [PR#1147](https://github.com/NationalSecurityAgency/ghidra/pull/1147) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 441 | @paolovagnero (commits: Paolo Vagnero) | Only implementation found |
| C-SKY v1 (CK610) | [nnonickreal/ghidra-csky-ISAv1](https://github.com/nnonickreal/ghidra-csky-ISAv1) | none (blocked) | 1/1 | 157 | @nnonickreal | Only one that compiles; NO LICENSE Alternatives: selar2025/Ghidra_CK610_Processor. |
| Casio HCD62121 | [qufb/HCD62121](https://github.com/qufb/HCD62121) | none (blocked) | 0/1 | 210 | @qufb | Only implementation found |
| Cell SPU | [aerosoul94/GhidraSPU](https://github.com/aerosoul94/GhidraSPU) | Apache-2.0 (ok) | 1/1 | 208 | @balika011, @aerosoul94, @elad335, @VelocityRa | Only implementation found |
| MediaTek GCPU control CPU (CCPU; listed as Chip Command CCPU) | [cyrozap/ghidra-ccpu](https://github.com/cyrozap/ghidra-ccpu) | Apache-2.0 (ok) | 1/1 | 40 | @cyrozap | Only implementation found |
| cr816 | [pelrun/ghidra-cr816](https://github.com/pelrun/ghidra-cr816) | Apache-2.0 (ok) | 1/1 | 88 | @pelrun | Only implementation found |
| CSR XAP | [Thaelz/ghidra-xap](https://github.com/Thaelz/ghidra-xap) | LGPL-3.0 (copyleft) | 1/1 | 89 | @Thaelz | XAP (LGPL-3); XAP2 (SamL98, Apache) is a different ISA Alternatives: SamL98/xap2. |
| CSR XAP2 | [SamL98/xap2](https://github.com/SamL98/xap2) | Apache-2.0 (ok) | 1/1 | 68 | @SamL98, @unusual-thoughts | Only implementation found |
| DEC Alpha | [kkaempf/ghidra-alpha](https://github.com/kkaempf/ghidra-alpha) | Apache-2.0 (ok) | 15/15 | 367 | @mattst88, @kkaempf | 367 constructors and OS-specific variants vs 242 (and claesmnyberg has no license) Alternatives: claesmnyberg/ghidra-cpu-alpha. |
| Broadcom D11 (listed as DEC D-11) | [CUB3D/ghidra-d11](https://github.com/CUB3D/ghidra-d11) | Apache-2.0 (ok) | 1/1 | 65 | @CUB3D | Only implementation found |
| DEC PDP-11 | [kaunomedis/PDP11](https://github.com/kaunomedis/PDP11) | GPL-3.0 (copyleft) | 1/1 | 250 | @kaunomedis | Only implementation found |
| DEC VAX | [kkaempf/ghidra-vax](https://github.com/kkaempf/ghidra-vax) | Apache-2.0 (ok) | 0/1 | 439 | @kkaempf | Only implementation found |
| Epson E0C6S46 | [Veryyes/E0C6S46-Ghidra-Processor](https://github.com/Veryyes/E0C6S46-Ghidra-Processor) | none (blocked) | 1/1 | 385 | @Veryyes, @atribecalledqst | Only implementation found |
| Epson S1C33 | [GMMan/s1c33_sleigh](https://github.com/GMMan/s1c33_sleigh) | none (blocked) | 1/1 | 366 | @GMMan | 366 constructors; NO LICENSE (both repos) Alternatives: dogtopus/slac33. |
| Epson S1C88 | [xtla/s1c88](https://github.com/xtla/s1c88) | none (blocked) | 1/1 | 143 | @cxiao, @xamroot, @mftoor | Only implementation found |
| Fairchild F8 | [PR#9087](https://github.com/NationalSecurityAgency/ghidra/pull/9087) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 228 | @polartape (commits: Sami Saari) | Only implementation found |
| Femtium | [RobertLarsen/GhidraFemtiumProcessor](https://github.com/RobertLarsen/GhidraFemtiumProcessor) | none (blocked) | 1/1 | 80 | @RobertLarsen | Only implementation found |
| Freescale FMan RISC | [mihakralj/vyos-ls1046a-build](https://github.com/mihakralj/vyos-ls1046a-build) | Apache-2.0 (ok) | 1/1 | 204 | @mihakralj, @github-actions[bot], @renovate[bot], @huihuimoe, @Daegara, @Sprinterfreak | Only implementation found |
| Fujitsu F2MC-16LX | [mehmooda/F2MC-16LX](https://github.com/mehmooda/F2MC-16LX) | none (blocked) | 1/1 | 313 | @mehmooda, @qufb | Only implementation found |
| Fujitsu FR (FR/FR60/FR81/MB91) | [desrdev/ghidra-fr60](https://github.com/desrdev/ghidra-fr60) | Apache-2.0 (ok) | 2/2 | 412 | @DiscoStarslayer, @esaulenka, @mumbel, @dracc, @antoniovazquezblanco, @KostyaSha | FR60+FR81, 412 constructors, Apache; simeonpilgrim (Apache) earlier FR Alternatives: simeonpilgrim/ghidra_fujitsu_fr, ammaraskar/ghidra-fujitsu-risc, mumbel/ghidra_mb91f. |
| GameCube DSP | [Pokechu22/ghidra-gcdsp-lang](https://github.com/Pokechu22/ghidra-gcdsp-lang) | Apache-2.0 (ok) | 1/1 | 450 | @Pokechu22, @Tilka | Only implementation found |
| Hitachi (RotorRE) | [phaseseeker/RotorRE](https://github.com/phaseseeker/RotorRE) | none (blocked) | 1/1 | 101 | @phaseseeker | Only implementation found |
| Hitachi H8/300, H8/300H, H8S | [shizmob/ghidra-h8-300](https://github.com/shizmob/ghidra-h8-300) | WTFPL (ok) | 1/3 | 314 | @shizmob | WTFPL, three variants (2 fail to compile: fix); ThomHPL H8S (GPL-3) for H8S if needed Alternatives: carllom/sleigh-h8, Thodoris1999/H8-38602R, ThomHPL/ghidra-h8s. |
| Hitachi H8/500 | [OZVR4/Ghidra-H8-Processor](https://github.com/OZVR4/Ghidra-H8-Processor) | none (blocked) | 3/3 | 1972 | @professor-jonny, @foxbcx | 1,972 constructors; NO LICENSE (all three H8/500 repos unlicensed) Alternatives: c4ashley/ghidra-h8-500, BigRaj/H8_539F. |
| HP NMOS-II | [kkaempf/ghidra-nmos-ii](https://github.com/kkaempf/ghidra-nmos-ii) | Apache-2.0 (ok) | 2/2 | 116 | @kkaempf | Only implementation found |
| Hudson HuC6280 | [TiCoKH/Ghidra_HuC6280](https://github.com/TiCoKH/Ghidra_HuC6280) | none (blocked) | 1/1 | 135 | @TiCoKH | Only implementation found |
| IBM s390x | [paulovitorjp/ghidra-s390x](https://github.com/paulovitorjp/ghidra-s390x) | Apache-2.0 (ok) | 1/1 | 4345 | @paulovitorjp | Only implementation found |
| Infineon C166 / ST10 | [keyhana/c166-ghidra-module](https://github.com/keyhana/c166-ghidra-module) | MIT (ok) | 1/1 | 318 | @keyhana, @cocktailyogi, @rnd-ash, @jnzenlab, @Arinerron, @esaulenka; also @esaulenka, @rnd-ash, @mumbel (esaulenka/Ghidra_C166) | MIT, Java and tests; TheFlashBold/haldex has more constructors (601) but no license; esaulenka (Apache) also credited if merged Alternatives: esaulenka/Ghidra_C166, TheFlashBold/ghidra-c166-haldex, robbederks/C166SV2_Ghidra. |
| Intel 8008 | [PR#8007](https://github.com/NationalSecurityAgency/ghidra/pull/8007) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 61 | @spirosekulovski (commits: Spiro Sekulovski) | Only implementation found |
| Intel Atom microcode | [pietroborrello/CustomProcessingUnit](https://github.com/pietroborrello/CustomProcessingUnit) | Apache-2.0 (ok) | 1/1 | 364 | @pietroborrello | Same spec in both (MIT/Apache); Apache copy Alternatives: pietroborrello/ghidra-atom-microcode. |
| Intel i960 | [PR#1452](https://github.com/NationalSecurityAgency/ghidra/pull/1452) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 265 | @mumbel (commits: mumbel) | Same author as mumbel/ghidra_i960; PR adds Java and tests Alternatives: mumbel/ghidra_i960. |
| JieLi pi32 / q32s | [quarkslab/ghidra-jieli](https://github.com/quarkslab/ghidra-jieli) | Apache-2.0 (ok) | 3/3 | 1028 | @virtualabs; also @kagaimiq (kagaimiq/ghidra-jieli) | 1,028 constructors vs 653; extends kagaimiq (credit) Alternatives: kagaimiq/ghidra-jieli, 6uan/kc02-fw-mod. |
| Kirk (PSP crypto) | [LemonHaze420/ghidra_kirk](https://github.com/LemonHaze420/ghidra_kirk) | none (blocked) | 1/1 | 66 | @LemonHaze420 | Only implementation found |
| Lattice LM32 | [jevinskie/ghidra-lm32](https://github.com/jevinskie/ghidra-lm32) | MIT (ok) | 2/2 | 98 | @jevinskie, @cyrozap | Only implementation found |
| MD32 (MediaTek) | [cyrozap/ghidra-md32](https://github.com/cyrozap/ghidra-md32) | Apache-2.0 (ok) | 1/1 | 207 | @cyrozap | Only implementation found |
| Microchip PIC16F153xx | [PR#667](https://github.com/NationalSecurityAgency/ghidra/pull/667) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 128 | @mh- (commits: Michael Huebler) | Only implementation found |
| Micronova | [pkooiman/micronova_ghidra](https://github.com/pkooiman/micronova_ghidra) | MIT (ok) | 1/1 | 106 | @pkooiman | Only implementation found |
| Toshiba TMP76C75T/TMP76C55T (listed as Mitsubishi 7700; 6801-family) | [Data-ptr/7675-processor](https://github.com/Data-ptr/7675-processor) | Unlicense (ok) | 1/1 | 202 | @Data-ptr | Same author; 7655 and 7675 differ by one constructor; merge into one module. Verified 2026-10-27: a 6801-core MCU with Toshiba extensions, not M7700; the extension opcodes have no datasheet or oracle, so it is held Alternatives: Data-ptr/7655-processor. |
| Mitsubishi MELPS-740 | [PR#5012](https://github.com/NationalSecurityAgency/ghidra/pull/5012) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 104 | @philpem (commits: Phil, Philip Pemberton, philpem) | Only implementation found |
| MOS 6510 (C64) | [anarkiwi/deity-informant](https://github.com/anarkiwi/deity-informant) | Apache-2.0 (ok) | 0/1 | 43 | @anarkiwi, @CBongo | Only implementation found |
| Motorola 146805E2 | [PR#856](https://github.com/NationalSecurityAgency/ghidra/pull/856) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 99 | @gareth8118 (commits: Gareth Edwards) | Only implementation found |
| Motorola 68HC11 / 6801 / HD6301/6303 | [sigurasg/GhidraMC6800](https://github.com/sigurasg/GhidraMC6800) | Apache-2.0 (ok) | 4/4 | 220 | @sigurasg, @antoniovazquezblanco | Covers 6801, HD6301 and 68HC11 with tests; compare HC11 depth against GaryOderNichts (PR#5068) during verification Alternatives: GaryOderNichts/ghidra-hc11-lang, PR#5068, PR#6314, PR#1904. |
| Motorola 68HC16 | [HausRummel/Ghidra-Processor-MC68HC16Z](https://github.com/HausRummel/Ghidra-Processor-MC68HC16Z) | Apache-2.0 (ok) | 1/1 | 1372 | @HausRummel, @claude, @laszlodaniel | 1,372 constructors vs 916/365; Java loader and tests Alternatives: chirpy8/ghidra_68HC16, rimwall/Ghidra-HC16-Processor. |
| Motorola DSP56300 | [roblg/ghidra-dsp56300](https://github.com/roblg/ghidra-dsp56300) | Apache-2.0 (ok) | 2/2 | 1019 | @roblg | DSP56300, 1,019 constructors, Apache (sambanks/octabam vendors the same); 56000 (yatli) doesn't compile, unlicensed Alternatives: sambanks/octabam, cessna85/Icarus, yatli/ghidra_dsp56k. |
| Motorola M-CORE | [PR#9270](https://github.com/NationalSecurityAgency/ghidra/pull/9270) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 103 | @CUB3D (commits: CUB3D) | Same author (CUB3D); PR is newer Alternatives: CUB3D/ghidra-mcore. |
| N64 RSP | [Random06457/Ghidra-RSP](https://github.com/Random06457/Ghidra-RSP) | MIT (ok) | 1/1 | 464 | @Random06457, @antoniovazquezblanco | Only implementation found |
| nanoMIPS | [nccgroup/ghidra-nanomips](https://github.com/nccgroup/ghidra-nanomips) | GPL-3.0 (copyleft) | 1/1 | 966 | @jamchamb, @jchambers-ncc | 966 constructors vs 257; GPL-3.0 (marcushall42 is Apache if GPL is unwanted) Alternatives: marcushall42/ghidra-nanomips. |
| National SC/MP | [sigurasg/GhidraSCMP](https://github.com/sigurasg/GhidraSCMP) | none (blocked) | 1/1 | 57 | @sigurasg | Only implementation found |
| NEC 78K0 | [psxjt5/Ghidra-78K0-Processor-Module](https://github.com/psxjt5/Ghidra-78K0-Processor-Module) | GPL-3.0 (copyleft) | 1/1 | 294 | @psxjt5 | Only implementation found |
| NEC uPD77016 | [Pokechu22/ghidra-upd77016-lang](https://github.com/Pokechu22/ghidra-upd77016-lang) | Apache-2.0 (ok) | 1/1 | 203 | @Pokechu22, @pcbbc | Only implementation found |
| NEC uPD78xx (78C10) | [PR#7930](https://github.com/NationalSecurityAgency/ghidra/pull/7930) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 311 | @ajxs (commits: Anthony, Vesa-Pekka Palmu); also @depili (commits: Vesa-Pekka Palmu) (PR#1509) | Only version that compiles; same SLEIGH as PR#1509 (depili, credit) Alternatives: PR#1509. |
| NEC V30MZ | [JidouGhost-TL/ghidra-wonderswan](https://github.com/JidouGhost-TL/ghidra-wonderswan) | Apache-2.0 (ok) | 1/1 | 484 | @JidouGhost-TL | Only implementation found |
| NEC V60 / Fujitsu MB86233 | [frangarcj/model1-ghidra](https://github.com/frangarcj/model1-ghidra) | none (blocked) | 2/2 | 688 | @frangarcj | Only implementation found |
| NEC V810/V830 | [PR#6412](https://github.com/NationalSecurityAgency/ghidra/pull/6412) | Apache-2.0 (Ghidra contribution) (ok) | 2/2 | 0 | @20Enderdude20 (commits: 20Enderdude20) | Same author as 20Enderdude20 repo; Apache Alternatives: 20Enderdude20/Ghidra_v810_v830. |
| Norsk Data ND-100 | [RetroCoreLabs/ghidra-nd100](https://github.com/RetroCoreLabs/ghidra-nd100) | MIT (ok) | 2/3 | 431 | @RonnyA | Only implementation found |
| NS32016 | [raybellis/ghidra-NS32016](https://github.com/raybellis/ghidra-NS32016) | Apache-2.0 (ok) | 1/1 | 146 | @raybellis | Only implementation found |
| NVIDIA Falcon | [marysaka/ghidra_falcon](https://github.com/marysaka/ghidra_falcon) | ISC (ok) | 3/3 | 284 | @marysaka, @antoniovazquezblanco, @vbe0201 | Only implementation found |
| NY8A054E | [jamesw343/Ghidra_NY8A054E](https://github.com/jamesw343/Ghidra_NY8A054E) | MIT (ok) | 1/1 | 73 | @jamesw343 | Only implementation found |
| OKI MSM66 (nX-8/200: 66201/66207/66301; listed as nX-8/500) | [VIRUXE/ghidra-oki66207](https://github.com/VIRUXE/ghidra-oki66207) | Unlicense (ok) | 2/2 | 2609 | @VIRUXE | Unlicense, 2,609 constructors; a1k0n (3,152) unlicensed Alternatives: a1k0n/ghidra-msm66q59x. |
| OKI nX-U8 | [EwTE-H/nX-U8_for_Ghidra](https://github.com/EwTE-H/nX-U8_for_Ghidra) | none (blocked) | 1/1 | 159 | @EwTE-H | Original; NO LICENSE (Physics365 GPL copy has unclear provenance) Alternatives: Physics365/991CN-X-CW-Decompilation. |
| OpenRISC 1000 | [Spritetm/ghidra-or1k-le-hack](https://github.com/Spritetm/ghidra-or1k-le-hack) | Apache-2.0 (ok) | 2/2 | 107 | @smaeul, @Spritetm; also @smaeul (smaeul/ghidra-or1k) | OpenRISC 1000 BE+LE; derived from smaeul/ghidra-or1k (credit). Aeon R2 (eb4x) is a separate ISA, listed separately Alternatives: smaeul/ghidra-or1k, CUB3D/Ghidra-Aeon, eb4x/ghidra-plugin-aeon. |
| Padauk PDK | [CUB3D/ghidra-pdk](https://github.com/CUB3D/ghidra-pdk) | Apache-2.0 (ok) | 0/5 | 429 | @CUB3D | Only implementation found |
| Panasonic MN10200 | [Pokechu22/ghidra-mn102-lang](https://github.com/Pokechu22/ghidra-mn102-lang) | Apache-2.0 (ok) | 1/1 | 214 | @Pokechu22 | Only implementation found |
| Panasonic MN10300 | [michaelbrandi/ghidra-mn103-extension](https://github.com/michaelbrandi/ghidra-mn103-extension) | Apache-2.0 (ok) | 1/2 | 1766 | @michaelbrandi | 1,766 constructors, Apache, tests (1 of 2 specs compiles) Alternatives: txt231/GhidraMn10300. |
| PS2 Emotion Engine (R5900) | [chaoticgd/ghidra-emotionengine-reloaded](https://github.com/chaoticgd/ghidra-emotionengine-reloaded) | Apache-2.0 (ok) | 1/1 | 378 | @chaoticgd, @beardypig, @VelocityRa, @WI-Lee, @Tupelov, @abelbriggs1; also @beardypig, @chaoticgd, @WI-Lee, @Tupelov, @PFedak, @GregoryMorse (beardypig/ghidra-emotionengine) | Maintained successor of beardypig (credit); VU and COP2 semantics Alternatives: beardypig/ghidra-emotionengine, bigianb/ghidra-emotionengine, astrelsky/ghidra_MIPSR5900. |
| PSP Allegrex | [kotcrab/ghidra-allegrex](https://github.com/kotcrab/ghidra-allegrex) | Apache-2.0 (ok) | 1/1 | 996 | @kotcrab, @KieronJ, @antoniovazquezblanco, @CB9001, @Sakimotor, @artart78 | Only implementation found |
| RCA CDP1802/1806 | [inbarraz/payphone](https://github.com/inbarraz/payphone) | GPL-3.0 (copyleft) | 1/1 | 122 | @inbarraz | Only implementation found |
| MediaTek SPM PCM (listed as Realtek PCM) | [cyrozap/ghidra-pcm](https://github.com/cyrozap/ghidra-pcm) | Apache-2.0 (ok) | 1/1 | 143 | @cyrozap | Only implementation found |
| Realtek r8169 | [cyrozap/realtek-nic-re](https://github.com/cyrozap/realtek-nic-re) | 0BSD (ok) | 1/1 | 17 | @cyrozap | Only implementation found |
| Renesas M32R | [ripnet/ghidra-m32r](https://github.com/ripnet/ghidra-m32r) | none (blocked) | 1/1 | 112 | @ripnet, @verasativa | All three are copies of one spec; NO LICENSE Alternatives: GhidrAuto/ghidra_m32r_working, TheFlashBold/ghidra-m32r. |
| Renesas RL78 | [CUB3D/ghidra-rl78](https://github.com/CUB3D/ghidra-rl78) | Apache-2.0 (ok) | 1/1 | 577 | @CUB3D | Apache, compiles, 577 constructors; zecoxao 1,601 unlicensed, half compiles Alternatives: hedgeberg/RL78_sleigh, zecoxao/yarl78s. Also found later: xyzz/ghidra-rl78 (MIT), 97.6% vs objdump. |
| Renesas RX | [redballoonsecurity/rx-proc-ghidra](https://github.com/redballoonsecurity/rx-proc-ghidra) | none (blocked) | 1/1 | 359 | @jamchamb | Only implementation found |
| Renesas V850E2/E3 / RH850 | [esaulenka/ghidra_v850](https://github.com/esaulenka/ghidra_v850) | MIT (ok) | 2/2 | 479 | @esaulenka, @pd0wm, @EgorKin, @jbmokuz, @HexRoman | MIT; kaikozlov/ghidra_rh850 more complete (805, no unimpl) but NO LICENSE Alternatives: kaikozlov/ghidra_rh850, ZEEKRZERO/Ghidra-RH850. |
| Rockwell L39 | [honx/rockwell_l39_ghidra](https://github.com/honx/rockwell_l39_ghidra) | Apache-2.0 (ok) | 1/1 | 128 | @honx | Only implementation found |
| S5L8702 FMISS | [lemonjesus/S5L8702-FMISS-Tools](https://github.com/lemonjesus/S5L8702-FMISS-Tools) | CC-BY-NC-SA-4.0 (blocked) | 1/1 | 21 | @lemonjesus, @q3k | Only implementation found |
| Sanyo LC87 | [Konsl/ghidra-lc87-processor](https://github.com/Konsl/ghidra-lc87-processor) | none (blocked) | 1/1 | 110 | @Konsl | Only implementation found |
| Sanyo xstormy16 | [xerootg/ghidra-xstormy16](https://github.com/xerootg/ghidra-xstormy16) | GPL-3.0 (copyleft) | 1/1 | 233 | @xerootg | Only implementation found |
| SCN3 | [LemonHaze420/GhidraSCN3](https://github.com/LemonHaze420/GhidraSCN3) | none (blocked) | 1/1 | 100 | @LemonHaze420 | Only implementation found |
| SCORE7 | [PR#9671](https://github.com/NationalSecurityAgency/ghidra/pull/9671) | Apache-2.0 (Ghidra contribution) (ok) | 2/2 | 447 | @ArthurKoba (commits: Arthur Koba) | Only implementation found |
| Sega VMU (LC86K) | [RossMeikleham/Ghidra-VMU-Processor](https://github.com/RossMeikleham/Ghidra-VMU-Processor) | MIT (ok) | 1/1 | 89 | @RossMeikleham | Only implementation found |
| Sharp SM83 (Game Boy) | [minorum/ghidra-sm83](https://github.com/minorum/ghidra-sm83) | Apache-2.0 (ok) | 1/1 | 121 | @Gekkio, @minorum, @antoniovazquezblanco, @ariscop, @SuperPupperDoggo, @TellowKrinkle | Apache, tests; CTurt has more constructors (242) but no license Alternatives: CTurt/GameBoy_GhidraSleigh, resonancellc/SleighGB. |
| Signetics 2650 | [iromero91/ghidra-signetics2650](https://github.com/iromero91/ghidra-signetics2650) | none (blocked) | 1/1 | 214 | @iromero91 | Only implementation found |
| Silicon Labs Si4440 | [astuder/Inside-EZRadioPRO](https://github.com/astuder/Inside-EZRadioPRO) | MIT (ok) | 1/1 | 235 | @astuder | Only implementation found |
| Sony SA-DSP | [ma1co/SA-DSP](https://github.com/ma1co/SA-DSP) | none (blocked) | 1/1 | 84 | @ma1co | Only implementation found |
| Sony SPC700 | [qwertymodo/SPCdra](https://github.com/qwertymodo/SPCdra) | Apache-2.0 (ok) | 2/2 | 429 | @qwertymodo | Only implementation found |
| ST200 (Lx) | [mumbel/ST200](https://github.com/mumbel/ST200) | Apache-2.0 (ok) | 2/2 | 136 | @mumbel | Only implementation found |
| STM8 | [esaulenka/ghidra_STM8](https://github.com/esaulenka/ghidra_STM8) | Apache-2.0 (ok) | 2/2 | 230 | @esaulenka, @abliss, @Megatokio | Only implementation found |
| STMicro ST7 | [PR#3631](https://github.com/NationalSecurityAgency/ghidra/pull/3631) | Apache-2.0 (Ghidra contribution) (ok) | 2/2 | 161 | @agatti (commits: Alessandro Gatti) | Only implementation found |
| Sunplus SPC970 | [DiscoStarslayer/ghidra-spc970](https://github.com/DiscoStarslayer/ghidra-spc970) | none (blocked) | 1/1 | 771 | @DiscoStarslayer, @Myriachan | Only implementation found |
| Sunplus unSP | [SamuelWAnderson45/ghidra-unSP](https://github.com/SamuelWAnderson45/ghidra-unSP) | Apache-2.0 (ok) | 1/1 | 249 | @GMMan, @SamuelWAnderson45 | Only implementation found |
| SuperFX (GSU) | [ChekeEdd/ghidra-superfx](https://github.com/ChekeEdd/ghidra-superfx) | BSD-3-Clause (ok) | 1/1 | 105 | @toxicUnicorn | Only implementation found |
| XpertTeak | [Pokechu22/ghidra-xpertteak-lang](https://github.com/Pokechu22/ghidra-xpertteak-lang) | Apache-2.0 (ok) | 1/1 | 981 | @Pokechu22 | XpertTeak 981 constructors (Apache); TeakLite (SachinVin, MIT) is a different core, 363 unimpl Alternatives: SachinVin/TeakLite-SLEIGH. |
| TeakLite | [SachinVin/TeakLite-SLEIGH](https://github.com/SachinVin/TeakLite-SLEIGH) | MIT (ok) | 1/1 | 646 | @SachinVin | Only implementation found |
| Telink TC32 | [rgov/Ghidra_TELink_TC32](https://github.com/rgov/Ghidra_TELink_TC32) | none (blocked) | 1/1 | 72 | @rgov | NO LICENSE (both repos) Alternatives: leommxj/ghidra_tc32. |
| TI TMS320C24x | [banksy-git/ghidra-tms320c24x](https://github.com/banksy-git/ghidra-tms320c24x) | Apache-2.0 (ok) | 1/1 | 41 | @banksy-git | Licensed; ArapKBett copy unlicensed Alternatives: ArapKBett/zoommulti. |
| TI TMS320C28x | [outlandnish/ghidra-tms320c28x](https://github.com/outlandnish/ghidra-tms320c28x) | Apache-2.0 (ok) | 2/2 | 795 | @outlandnish, @abedegno, @dieseld23 | Includes the CLA coprocessor and tests; mwdmwd (854 constructors) close; decide by verification Alternatives: mwdmwd/ghidra-c28x. |
| TI TMS320C3x | [gm-stack/tms320-ghidra](https://github.com/gm-stack/tms320-ghidra) | none (blocked) | 2/2 | 811 | @gm-stack | Only implementation found |
| TI TMS320C6000 | [geepot/ghidra-c6000](https://github.com/geepot/ghidra-c6000) | Apache-2.0 (ok) | 4/4 | 2278 | @geepot, @roblg | 2,278 constructors, tests, Apache; zisonzishen's 43k-constructor generated spec has an unclear license Alternatives: zisonzishen0415-stack/ghidra-c6000, ArapKBett/zoommulti. |
| TI TMS34010 | [ZPaul2Fresh8/Ghidra_TMS34010](https://github.com/ZPaul2Fresh8/Ghidra_TMS34010) | Apache-2.0 (ok) | 1/1 | 156 | @ZPaul2Fresh8 | Only implementation found |
| TI TMS9900 | [gnulnulf/Ghidra-TMS9900](https://github.com/gnulnulf/Ghidra-TMS9900) | Apache-2.0 (ok) | 1/1 | 82 | @gnulnulf, @cvpeck | Only implementation found |
| TI TopSM (BLE) | [antoniovazquezblanco/GhidraTopSM](https://github.com/antoniovazquezblanco/GhidraTopSM) | MIT (ok) | 1/1 | 52 | @antoniovazquezblanco, @dependabot[bot]; also @rjp5th (rjp5th/beyond-ble-tools) | Same as rjp5th; newer, MIT Alternatives: rjp5th/beyond-ble-tools. |
| TILE-Gx | [PR#9426](https://github.com/NationalSecurityAgency/ghidra/pull/9426) | Apache-2.0 (Ghidra contribution) (ok) | 1/1 | 631 | @speidy (commits: Idan Freiberg) | 631 constructors, compiles; PR#9281 doesn't Alternatives: PR#9281. |
| Toshiba MeP | [CreepNT/VitaLoaderRedux](https://github.com/CreepNT/VitaLoaderRedux) | BSD-3-Clause-Clear (ok) | 1/1 | 247 | @CreepNT, @scribam, @antoniovazquezblanco, @DCNick3 | 247 constructors (Vita CMeP) vs xyzz 115; BSD-3-Clause; extract processor only Alternatives: xyzz/ghidra-mep, guedou/ghidra-processor-mep. |
| Toshiba T8x | [DrWhax/SLEIGH-Toshiba-T8x](https://github.com/DrWhax/SLEIGH-Toshiba-T8x) | none (blocked) | 1/1 | 228 | @DrWhax | Only implementation found |
| Toshiba TLCS-900/H | [nevesnunes/ghidra-tlcs900h](https://github.com/nevesnunes/ghidra-tlcs900h) | none (blocked) | 1/1 | 1495 | @nevesnunes | Only implementation found |
| WCH (CH32 variants) | [smhgzll/dmt-99-multimeter-custom-firmware](https://github.com/smhgzll/dmt-99-multimeter-custom-firmware) | unclear (blocked) | 1/1 | 1449 | @smhgzll | Only implementation found |
| WE32100 | [fletto2/ghidra-we32100](https://github.com/fletto2/ghidra-we32100) | MIT (ok) | 1/1 | 272 | @fletto2; also @mumbel, @sethm (mumbel/ghidra_we) | Compiles, MIT; mumbel (Apache) doesn't compile Alternatives: mumbel/ghidra_we. |
| Wii Starlet | [eigenform/gcwii-toolbox](https://github.com/eigenform/gcwii-toolbox) | none (blocked) | 0/1 | 123 | @eigenform | Only implementation found |
| XaviX | [widberg/rad_sbw](https://github.com/widberg/rad_sbw) | MIT (ok) | 1/1 | 156 | @widberg | MIT; tahg unlicensed copy Alternatives: tahg/x2ghidra. |
| Xilinx PicoBlaze | [PR#7511](https://github.com/NationalSecurityAgency/ghidra/pull/7511) | Apache-2.0 (Ghidra contribution) (ok) | 2/2 | 117 | @CUB3D (commits: CUB3D) | Same author (CUB3D); PR is newer Alternatives: CUB3D/ghidra-picoblaze. |
| Zilog Z8000 | [jpelletier/Z8000](https://github.com/jpelletier/Z8000) | none (blocked) | 2/2 | 937 | @jpelletier | Only implementation found |
| TI TMS320C54x | [gabtremblay/ghidra-tms320c54x](https://github.com/gabtremblay/ghidra-tms320c54x) | Apache-2.0 (ok) | ? | - | Gabriel Tremblay (@gabtremblay) | Only implementation found; released 2026-10-25 for Ghidra 12.2; found after the survey (IDA gap check). |
| Hitachi SH-3 / SH-2E | [will07c5/ghidra-sh](https://github.com/will07c5/ghidra-sh) | MIT (ok) | ? | - | @will07c5 | Ghidra has SH-1/SH-2/SH-2A and SH-4 but no SH-3 or SH-2E; this repo has SH-3 (SH-2E to be added). Originally set aside as a near-duplicate of Ghidra's SuperH. |
| WebAssembly | [PR#4103](https://github.com/NationalSecurityAgency/ghidra/pull/4103) | Apache-2.0 (Ghidra contribution) (ok) | ? | - | @nneonneo | Bytecode VM, added because IDA supports it out of the box; PR is Apache-2.0 and maintained; compare with the GPL plugins during verification. Alternatives: garrettgu10/ghidra-wasm-plugin (GPL-3.0), Ryxm-a/Ghidra-WebAssembly-WASM-Plugin (GPL-3.0), andr3colonel/ghidra_wasm (no license). |
| EFI Byte Code (EBC) | [meromwolff/Ghidra-EFI-Byte-Code-Processor](https://github.com/meromwolff/Ghidra-EFI-Byte-Code-Processor) | MIT (ok) | 1/1 | - | @meromwolff | Bytecode VM, added because IDA supports it out of the box. |

## Not selected (variants of processors Ghidra already has)

Unmerged pull requests and repositories that extend an official Ghidra processor rather than add a CPU. Candidates for a later round: 8051 vendor variants (TI CC, ZBS243, 8051x, PR#3439 buddha, PR#8130 CIP-51), 6805 MC146805E2 (PR#856), PIC16F153xx (PR#667), 68000 CPU32 (PR#9084 and earlier), 68000 A-line traps (PR#7126, hippietrail), OS-9 68000 (Stovent), PowerPC e200 (PR#4952), Gekko/Broadway (aldelaro5, Cuyler36), Xenon/VMX128 (freeqaz, EveryoneEverybody), PowerPC AS (PR#9484, silentsignal), Apple AArch64 (PR#9059), ARMv8-M coprocessor (PR#8582), RISC-V T-Head/QingKe (PR#5778, PR#6390, isaacthorn), Xtensa FLIX/MediaTek (flto, germiBest), Solana sBPF (NWMonster, neodyme-labs), Z80 e-Reader (PR#8257), SH-2A-NoFPU (PR#9237), AVR8 small-flash (PR#8845, PR#10021).

## Not selected (bytecode and script VMs)

WebAssembly and EFI Byte Code moved to the main table (IDA Pro supports them out of the box). Still not selected: EVM (adelapie, syjcnss), V8 bytecode (Llamaware, drylikov, aynakeya), Hermes, NSIS, AGS, CHIP-8, Garmin VM, Wasmtime Pulley, QVM, game script VMs (BGI, YSC, Clock Tower, KH2 AI, fscript), DXBC, toy and test specs.

## Overlaps with this repository

XMOS (PR#9112) overlaps `xCORE/`; MicroBlaze (KodaSec, embogit) overlaps `MicroBlaze/`; CUDA (Danil6969) overlaps `SASS/`. Compare during verification; keep ours unless theirs is better.

## License requests

Opened 2026-10-25 for every blocked pick. A module moves into the verification queue once its author adds a license; a decline removes it from this list.

| CPU | Request | Status |
|---|---|---|
| C-SKY v1 (CK610) | https://github.com/nnonickreal/ghidra-csky-ISAv1/issues/1 | open |
| Casio HCD62121 | https://github.com/qufb/HCD62121/issues/1 | open |
| CoolRISC 816 (cr816) | https://github.com/pelrun/ghidra-cr816/issues/2 | open; only Ghidra's template LICENSE.txt; verified, held until confirmed (asked 2026-10-27) |
| Epson E0C6S46 | https://github.com/Veryyes/E0C6S46-Ghidra-Processor/issues/2 | open |
| Epson S1C33 | https://github.com/GMMan/s1c33_sleigh/issues/1 | open |
| Epson S1C88 | https://github.com/xtla/s1c88/issues/1 | open |
| Femtium | https://github.com/RobertLarsen/GhidraFemtiumProcessor/issues/1 | open |
| Fujitsu F2MC-16LX | https://github.com/mehmooda/F2MC-16LX/issues/6 | author agrees; waiting for co-contributors @qufb and @mkrasselt1 |
| GameCube DSP | https://github.com/Pokechu22/ghidra-gcdsp-lang/issues/2 | open; published while Ghidra's template LICENSE.txt was the only license file; confirmation asked 2026-10-27 |
| Hitachi (RotorRE) | https://github.com/phaseseeker/RotorRE/issues/1 | open |
| Hitachi H8/500 | https://github.com/OZVR4/Ghidra-H8-Processor/issues/5 | open |
| Hudson HuC6280 | https://github.com/TiCoKH/Ghidra_HuC6280/issues/2 | open |
| Kirk (PSP crypto) | https://github.com/LemonHaze420/ghidra_kirk/issues/1 | open |
| Micronova | https://github.com/pkooiman/micronova_ghidra/issues/1 | license added by the author 2026-10-25 |
| National SC/MP | https://github.com/sigurasg/GhidraSCMP/issues/45 | open |
| NEC V60 / Fujitsu MB86233 | https://github.com/frangarcj/model1-ghidra/issues/1 | open |
| NS32016 | https://github.com/raybellis/ghidra-NS32016/issues/1 | open; published while Ghidra's template LICENSE.txt was the only license file; confirmation asked 2026-10-27 |
| OKI nX-U8 | https://github.com/EwTE-H/nX-U8_for_Ghidra/issues/1 | open |
| Panasonic MN10200 | https://github.com/Pokechu22/ghidra-mn102-lang/issues/2 | open; published while Ghidra's template LICENSE.txt was the only license file; confirmation asked 2026-10-27 |
| Renesas M32R | https://github.com/ripnet/ghidra-m32r/issues/7 | open |
| Renesas RX | https://github.com/redballoonsecurity/rx-proc-ghidra/pull/2#issuecomment-6401502742 | comment on an existing license PR |
| S5L8702 FMISS | https://github.com/lemonjesus/S5L8702-FMISS-Tools/issues/6 | open |
| Sanyo LC87 | https://github.com/Konsl/ghidra-lc87-processor/issues/1 | open |
| SCN3 | https://github.com/LemonHaze420/GhidraSCN3/issues/1 | open |
| Signetics 2650 | https://github.com/iromero91/ghidra-signetics2650/issues/1 | open |
| Sony SA-DSP | https://github.com/ma1co/SA-DSP/issues/1 | open |
| Sunplus SPC970 | https://github.com/DiscoStarslayer/ghidra-spc970/issues/5 | open |
| Telink TC32 | https://github.com/rgov/Ghidra_TELink_TC32/issues/5 | open |
| TI TMS320C3x | https://github.com/gm-stack/tms320-ghidra/issues/1 | open |
| TI TMS34010 | https://github.com/ZPaul2Fresh8/Ghidra_TMS34010/issues/1 | license added by the author 2026-10-25 |
| TI TMS9900 | https://github.com/gnulnulf/Ghidra-TMS9900/issues/7 | open; published while Ghidra's template LICENSE.txt was the only license file; confirmation asked 2026-10-27 |
| Toshiba T8x | https://github.com/DrWhax/SLEIGH-Toshiba-T8x/issues/1 | open |
| Toshiba TLCS-900/H | https://github.com/nevesnunes/ghidra-tlcs900h/issues/1 | open |
| WCH (CH32 variants) | not requested | Repository says files keep their original rights; the original author is unknown |
| Wii Starlet | https://github.com/eigenform/gcwii-toolbox/issues/1 | open |
| XpertTeak | https://github.com/Pokechu22/ghidra-xpertteak-lang/issues/1 | open; only Ghidra's template LICENSE.txt; not imported until confirmed (asked 2026-10-27) |
| Zilog Z8000 | https://github.com/jpelletier/Z8000/issues/1 | open |
