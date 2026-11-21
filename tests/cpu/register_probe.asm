; probe(fn, x, y, trace, observed): save our caller's state, seed RBX/RSI,
; invoke fn(x, y, trace), and sample both physical registers before restoring.
.code
probe PROC FRAME
    push rbx
    .pushreg rbx
    push rsi
    .pushreg rsi
    sub rsp, 28h
    .allocstack 28h
    .endprolog
    mov rax, rcx
    mov rcx, rdx
    mov rdx, r8
    mov r8, r9
    mov rbx, 0123456789abcdefh
    mov rsi, 0fedcba9876543210h
    call rax
    ; Entry RSP + 28h is the incoming fifth argument, now at RSP + 60h.
    mov r10, [rsp+60h]
    mov [r10], rbx
    mov [r10+8], rsi
    add rsp, 28h
    pop rsi
    pop rbx
    ret
probe ENDP

; Called only by probe, which restores both registers for its own caller.
clobber_control PROC
    xor ebx, ebx
    xor esi, esi
    ret
clobber_control ENDP
END
