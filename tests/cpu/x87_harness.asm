; Native-only harness for tests/cpu/x87_add.py; it is never translated. x87_call(fn, input, output)
; saves the caller's x87 environment, establishes the profile's entry state (FNINIT, then control word
; 0x027F: 53-bit precision, round to nearest-even, all exceptions masked; TOP 0, empty stack, clear
; status), calls fn(input, output), and records the state fn left. It restores the caller's environment
; before returning the control word in bits 0 to 15, the status word in bits 16 to 31 and the tag word in
; bits 32 to 47, as they were when fn returned. The native and translated functions both run through it.
.code

x87_call PROC FRAME
    sub rsp, 104
    .allocstack 104
    .endprolog
    fnstenv [rsp+72]
    fninit
    mov word ptr [rsp+32], 027Fh
    fldcw word ptr [rsp+32]
    mov rax, rcx
    mov rcx, rdx
    mov rdx, r8
    call rax
    fnstenv [rsp+40]
    movzx eax, word ptr [rsp+40]
    movzx edx, word ptr [rsp+44]
    shl edx, 16
    or eax, edx
    movzx edx, word ptr [rsp+48]
    shl rdx, 32
    or rax, rdx
    fldenv [rsp+72]
    add rsp, 104
    ret
x87_call ENDP

END
