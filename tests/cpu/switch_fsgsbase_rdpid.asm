; coverage: record cpu_aot_switch_fsgsbase_rdpid
; Source-built MASM fixture for RDFSBASE, RDGSBASE, WRFSBASE, WRGSBASE, and RDPID
; in tools/cpu_switch_aot.py (--host-cpu opt-in), plus native CPUID/RDTSCP helpers
; and negative controls.
; Every translated export uses the Windows x64 ABI: RCX, RDX, R8 -> RAX.
.code

; --- Translated positive exports ---

rdfsbase_32 PROC FRAME
    .endprolog
    mov rax, -1
    rdfsbase eax
    ret
rdfsbase_32 ENDP

rdfsbase_64 PROC FRAME
    .endprolog
    rdfsbase rax
    ret
rdfsbase_64 ENDP

rdgsbase_32 PROC FRAME
    .endprolog
    mov rax, -1
    rdgsbase eax
    ret
rdgsbase_32 ENDP

rdgsbase_64 PROC FRAME
    .endprolog
    rdgsbase rax
    ret
rdgsbase_64 ENDP

wrfsbase_32_roundtrip PROC FRAME
    .endprolog
    rdfsbase r9
    wrfsbase ecx
    mov rax, -1
    rdfsbase rax
    wrfsbase r9
    ret
wrfsbase_32_roundtrip ENDP

wrfsbase_64_roundtrip PROC FRAME
    .endprolog
    rdfsbase r9
    wrfsbase rcx
    rdfsbase rax
    wrfsbase r9
    ret
wrfsbase_64_roundtrip ENDP

wrgsbase_32_roundtrip PROC FRAME
    .endprolog
    rdgsbase r9
    wrgsbase ecx
    mov rax, -1
    rdgsbase rax
    wrgsbase r9
    ret
wrgsbase_32_roundtrip ENDP

wrgsbase_64_roundtrip PROC FRAME
    .endprolog
    rdgsbase r9
    wrgsbase rcx
    rdgsbase rax
    wrgsbase r9
    ret
wrgsbase_64_roundtrip ENDP

wrfsgsbase_nonvolatile PROC FRAME
    push rbx
    .pushreg rbx
    push r12
    .pushreg r12
    .endprolog
    rdfsbase rbx
    rdgsbase r12
    wrfsbase rcx
    rdfsbase r10
    wrfsbase rbx
    wrgsbase rdx
    rdgsbase r11
    wrgsbase r12
    mov QWORD PTR [r8], r10
    mov QWORD PTR [r8+8], r11
    mov rax, r10
    xor rax, r11
    pop r12
    pop rbx
    ret
wrfsgsbase_nonvolatile ENDP

rdpid_64 PROC FRAME
    .endprolog
    mov rax, -1
    rdpid rax
    ret
rdpid_64 ENDP

rdpid_twice PROC FRAME
    .endprolog
    rdpid r9
    rdpid r10
    mov QWORD PTR [r8], r9
    mov QWORD PTR [r8+8], r10
    mov rax, r9
    ret
rdpid_twice ENDP

flag_preserve_fsgsbase_rdpid PROC FRAME
    .endprolog
    rdfsbase r9
    rdgsbase r10
    add rcx, rdx
    rdfsbase rax
    rdgsbase r11
    wrfsbase r9
    wrgsbase r10
    rdpid r11
    setb BYTE PTR [r8]
    sete BYTE PTR [r8+1]
    sets BYTE PTR [r8+2]
    seto BYTE PTR [r8+3]
    setp BYTE PTR [r8+4]
    mov rax, rcx
    ret
flag_preserve_fsgsbase_rdpid ENDP

unused_host_reads PROC FRAME
    .endprolog
    rdfsbase r10
    rdgsbase r10
    rdpid r10
    mov eax, 42
    ret
unused_host_reads ENDP

; --- Native-only host CPUID / RDTSCP helpers (never translated) ---

native_host_features PROC FRAME
    push rbx
    .pushreg rbx
    .endprolog
    xor eax, eax
    cpuid
    xor r8d, r8d
    cmp eax, 7
    jb done_features
    mov eax, 7
    xor ecx, ecx
    cpuid
    test ebx, 1
    jz check_rdpid
    or r8d, 1
check_rdpid:
    bt ecx, 22
    jnc done_features
    or r8d, 2
done_features:
    mov eax, r8d
    pop rbx
    ret
native_host_features ENDP

native_rdtscp_aux PROC FRAME
    .endprolog
    rdtscp
    mov eax, ecx
    ret
native_rdtscp_aux ENDP

; --- Negative controls (refused by translator; never translated in build) ---

neg_undef_wrfsbase PROC FRAME
    .endprolog
    wrfsbase r10
    xor eax, eax
    ret
neg_undef_wrfsbase ENDP

neg_undef_wrgsbase PROC FRAME
    .endprolog
    wrgsbase r11d
    xor eax, eax
    ret
neg_undef_wrgsbase ENDP

neg_rsp_rdfsbase PROC FRAME
    .endprolog
    rdfsbase rsp
    xor eax, eax
    ret
neg_rsp_rdfsbase ENDP

neg_rsp_rdpid PROC FRAME
    .endprolog
    rdpid rsp
    xor eax, eax
    ret
neg_rsp_rdpid ENDP

END
