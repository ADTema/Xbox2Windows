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
END
