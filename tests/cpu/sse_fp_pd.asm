; coverage: source cpu_aot_sse_fp_pd
; Source-built MASM fixture for the seven legacy SSE2 packed double arithmetic forms from
; docs/coverage/x64_zen2.tsv group SSE2: addpd, subpd, mulpd, divpd, minpd, maxpd and sqrtpd, each
; with an xmm source and an aligned m128 source. Operands are loaded and stored with movaps.
; Every export uses the Windows x64 leaf ABI:
;   RCX = const void* input_a (32 bytes, 16-byte aligned)
;   RDX = const void* input_b (32 bytes, 16-byte aligned; second vector at +16)
;   R8  = void*       output  (32 bytes, 16-byte aligned)
; Each operation has four exports: register source, m128 at [rdx], m128 at [rdx+16] and the same
; register as both operands. ALTER_IMM swaps each register-form operation (add/sub, mul/div,
; min/max; sqrt becomes add), each memory form with the other displacement, each self form with a
; second register and the chain with a division in place of the multiplication.
.code

op_addpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    subpd xmm0, xmm1
ELSE
    addpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_addpd ENDP

op_addpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    addpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    addpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_addpd_mem ENDP

op_addpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    addpd xmm0, XMMWORD PTR [rdx]
ELSE
    addpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_addpd_mem_disp ENDP

op_addpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    addpd xmm0, xmm1
ELSE
    addpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_addpd_self ENDP

op_subpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    addpd xmm0, xmm1
ELSE
    subpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_subpd ENDP

op_subpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    subpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    subpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_subpd_mem ENDP

op_subpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    subpd xmm0, XMMWORD PTR [rdx]
ELSE
    subpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_subpd_mem_disp ENDP

op_subpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    subpd xmm0, xmm1
ELSE
    subpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_subpd_self ENDP

op_mulpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    divpd xmm0, xmm1
ELSE
    mulpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_mulpd ENDP

op_mulpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    mulpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    mulpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_mulpd_mem ENDP

op_mulpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    mulpd xmm0, XMMWORD PTR [rdx]
ELSE
    mulpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_mulpd_mem_disp ENDP

op_mulpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    mulpd xmm0, xmm1
ELSE
    mulpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_mulpd_self ENDP

op_divpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    mulpd xmm0, xmm1
ELSE
    divpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_divpd ENDP

op_divpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    divpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    divpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_divpd_mem ENDP

op_divpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    divpd xmm0, XMMWORD PTR [rdx]
ELSE
    divpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_divpd_mem_disp ENDP

op_divpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    divpd xmm0, xmm1
ELSE
    divpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_divpd_self ENDP

op_minpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    maxpd xmm0, xmm1
ELSE
    minpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_minpd ENDP

op_minpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    minpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    minpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_minpd_mem ENDP

op_minpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    minpd xmm0, XMMWORD PTR [rdx]
ELSE
    minpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_minpd_mem_disp ENDP

op_minpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    minpd xmm0, xmm1
ELSE
    minpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_minpd_self ENDP

op_maxpd PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    minpd xmm0, xmm1
ELSE
    maxpd xmm0, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_maxpd ENDP

op_maxpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    maxpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    maxpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_maxpd_mem ENDP

op_maxpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    maxpd xmm0, XMMWORD PTR [rdx]
ELSE
    maxpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_maxpd_mem_disp ENDP

op_maxpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    maxpd xmm0, xmm1
ELSE
    maxpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_maxpd_self ENDP

op_sqrtpd PROC FRAME
    .endprolog
    movaps xmm1, XMMWORD PTR [rdx]
    movaps xmm2, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    addpd xmm2, xmm1
ELSE
    sqrtpd xmm2, xmm1
ENDIF
    movaps XMMWORD PTR [r8], xmm2
    ret
op_sqrtpd ENDP

op_sqrtpd_mem PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    sqrtpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    sqrtpd xmm0, XMMWORD PTR [rdx]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_sqrtpd_mem ENDP

op_sqrtpd_mem_disp PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
IFDEF ALTER_IMM
    sqrtpd xmm0, XMMWORD PTR [rdx]
ELSE
    sqrtpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_sqrtpd_mem_disp ENDP

op_sqrtpd_self PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
IFDEF ALTER_IMM
    addpd xmm0, xmm1
ELSE
    sqrtpd xmm0, xmm0
ENDIF
    movaps XMMWORD PTR [r8], xmm0
    ret
op_sqrtpd_self ENDP

; Chained arithmetic: every operation feeds the next through registers, with a memory
; source at +16 and a destination reused across instructions.
op_pd_pipeline PROC FRAME
    .endprolog
    movaps xmm0, XMMWORD PTR [rcx]
    movaps xmm1, XMMWORD PTR [rdx]
    addpd xmm0, xmm1
IFDEF ALTER_IMM
    divpd xmm0, XMMWORD PTR [rdx+16]
ELSE
    mulpd xmm0, XMMWORD PTR [rdx+16]
ENDIF
    subpd xmm0, xmm1
    movaps xmm2, XMMWORD PTR [rcx+16]
    divpd xmm2, xmm0
    minpd xmm2, xmm1
    maxpd xmm0, xmm2
    sqrtpd xmm3, xmm0
    movaps XMMWORD PTR [r8], xmm3
    movaps XMMWORD PTR [r8+16], xmm2
    ret
op_pd_pipeline ENDP

END
