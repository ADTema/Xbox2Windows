; Source-owned arithmetic control for the device-init lowerer.
.code
heap_layout PROC FRAME
    .endprolog
    mov r8d,ecx
    shl r8d,9
    mov [rdx],r8d
    imul eax,ecx,19000h
    add eax,10000h
    mov [rdx+4],eax
    imul eax,ecx,0be000h
    or rax,1100h
    ret
heap_layout ENDP

; Compact public fixture: scan one flag byte per record and sum four sizes
; into the return value when the index output is written.
slot_probe PROC FRAME
    .endprolog
    xor eax,eax
    test ecx,ecx
    je exhausted
scan:
    movzx r10d,byte ptr [rdx+rax]
    test r10d,1
    je available
    inc eax
    cmp eax,ecx
    jb scan
exhausted:
    xor eax,eax
    ret
available:
    mov [r9],eax
    vmovdqu xmm2,xmmword ptr [r8]
    vpsrldq xmm1,xmm2,4
    vpaddd xmm2,xmm1,xmm2
    vpsrldq xmm0,xmm2,8
    vpaddd xmm0,xmm2,xmm0
    vmovd eax,xmm0
    ret
slot_probe ENDP
END
