.code
group_init PROC
    lea rax, [rcx+64]
    mov [rcx+8], rax
    mov [rcx], rax
    mov r8d, edx
    lea rax, [rax+r8*8]
    mov [rcx+24], rax
    mov [rcx+16], rax
    mov [rcx+44], edx
    mov dword ptr [rcx+40], 0
    mov qword ptr [rcx+32], 0
    ret
group_init ENDP

group_append PROC
    mov eax, [rcx+40]
    cmp eax, [rcx+44]
    jne available
    int 3
available:
    ; Work in bytes. Pick the first rounded stride with the required low ten bits.
    add r8, 31
    and r8, -32
    mov r9, [rcx+32]
    add r9, 32
    and r9, 1023
    mov r10, r8
    and r10, -1024
    or r10, r9
    cmp r10, r8
    jae have_stride
    add r10, 1024
have_stride:
    mov eax, [rcx+40]
    mov r11, [rcx+8]
    mov [r11+rax*8], rdx
    mov r11, [rcx+24]
    mov [r11+rax*8], r10
    add [rcx+32], r10
    inc dword ptr [rcx+40]
    mov eax, 1
    ret
group_append ENDP
END
