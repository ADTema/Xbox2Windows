; coverage: source cpu_aot_integer_flags
; Source-built MASM fixture exercising 5 uncovered Integer forms from
; docs/coverage/x64_zen2.tsv: lahf, pushf, popf, pushfq, popfq.
; Every export uses the Windows x64 leaf ABI:
;   RCX = const uint64_t* input_a (32 bytes)
;   RDX = const uint64_t* input_b (32 bytes)
;   R8  = uint64_t*       output  (32 bytes)
.code

op_lahf_preserve PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9, QWORD PTR [rdx]
IFDEF ALTER_IMM
    add r9d, 1
ELSE
    add r9d, 17
ENDIF
    lahf
    mov QWORD PTR [r8], rax
    ret
op_lahf_preserve ENDP

op_lahf_add PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9, QWORD PTR [rdx]
IFDEF ALTER_IMM
    add al, 5
ELSE
    add al, r9b
ENDIF
    lahf
    mov QWORD PTR [r8], rax
    ret
op_lahf_add ENDP

op_lahf_sub PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9, QWORD PTR [rdx]
IFDEF ALTER_IMM
    sub r9d, 1
ELSE
    sub r9d, 15
ENDIF
    lahf
    mov QWORD PTR [r8], rax
    ret
op_lahf_sub ENDP

op_lahf_adc_sbb PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9d, DWORD PTR [rdx]
    stc
    adc r9d, 0
    lahf
    mov QWORD PTR [r8], rax
    mov r10d, DWORD PTR [rdx]
    stc
    sbb r10d, 0
    lahf
    mov QWORD PTR [r8+8], rax
    clc
    mov r11d, DWORD PTR [rdx+8]
    adc r11d, DWORD PTR [rdx+16]
    lahf
    mov QWORD PTR [r8+16], rax
    ret
op_lahf_adc_sbb ENDP

op_lahf_inc_dec_neg PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9d, DWORD PTR [rdx]
    clc
    inc r9d
    lahf
    mov QWORD PTR [r8], rax
    mov r10d, DWORD PTR [rdx]
    stc
    dec r10d
    lahf
    mov QWORD PTR [r8+8], rax
    mov r11d, DWORD PTR [rdx]
    neg r11d
    lahf
    mov QWORD PTR [r8+16], rax
    ret
op_lahf_inc_dec_neg ENDP

op_lahf_cmp_clc_cmc PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9d, DWORD PTR [rdx]
    cmp r9d, DWORD PTR [rdx+8]
    lahf
    mov QWORD PTR [r8], rax
    cmc
    lahf
    mov QWORD PTR [r8+8], rax
    clc
    lahf
    mov QWORD PTR [r8+16], rax
    ret
op_lahf_cmp_clc_cmc ENDP

op_pushf_flags PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov r9, QWORD PTR [rdx]
    mov r10d, 0
    cmp rax, r9
IFDEF ALTER_IMM
    std
ELSE
    cld
ENDIF
    pushf
    pop r10w
    cld
    mov QWORD PTR [r8], r10
    ret
op_pushf_flags ENDP

op_pushf_stride PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    push rax
    mov r9d, DWORD PTR [rdx]
    add r9d, DWORD PTR [rdx+8]
    pushf
    mov r10, QWORD PTR [rsp]
    popf
    pop r11
    cld
    mov QWORD PTR [r8], r10
    mov QWORD PTR [r8+8], r11
    ret
op_pushf_stride ENDP

op_popf_stride PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    push rax
    mov r9, QWORD PTR [rdx]
    push r9w
    popf
    mov r10, QWORD PTR [rsp]
    mov r11d, 0
    pushf
    pop r11w
    cld
    pop rax
    mov QWORD PTR [r8], r11
    mov QWORD PTR [r8+8], r10
    mov QWORD PTR [r8+16], rax
    ret
op_popf_stride ENDP

op_popfq_pushfq_roundtrip PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rdx]
    push rax
    mov r9, QWORD PTR [rcx]
IFDEF ALTER_IMM
    xor r9d, 1
ENDIF
    push r9
    popfq
    mov r10, QWORD PTR [rsp]
    pushfq
    pop r11
    pop rax
    cld
    mov QWORD PTR [r8], r11
    mov QWORD PTR [r8+8], r10
    mov QWORD PTR [r8+16], rax
    ret
op_popfq_pushfq_roundtrip ENDP

op_pipeline PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    push rax
    popfq
    mov rax, QWORD PTR [rdx]
    sahf
    mov r9, QWORD PTR [rdx+8]
    add r9, QWORD PTR [rdx+16]
    lahf
    pushf
    popf
    pushfq
    pop r10
    cld
    mov QWORD PTR [r8], rax
    mov QWORD PTR [r8+8], r10
    ret
op_pipeline ENDP

; The discarded read must still fault after the first store and before the second.
op_discarded_read PROC FRAME
    .endprolog
    mov rax, QWORD PTR [rcx]
    mov QWORD PTR [r8], rax
    mov r9, QWORD PTR [rdx]
    mov QWORD PTR [r8+8], rax
    ret
op_discarded_read ENDP

END
