; Source-owned single-provider reference. The table values differ from the local package.
.const
PUBLIC fixture_name
fixture_name BYTE "fixture-7",0
.code
fixture_query PROC FRAME
    .endprolog
    test rcx,rcx
    jz invalid
    cmp qword ptr [rcx],4
    jne invalid
    mov edx,[rcx+16]
    and edx,0ff0000h
    cmp edx,10000h
    je enumerate
    mov eax,2
    cmp edx,20000h
    jne missing
    mov eax,4
missing:
    mov qword ptr [rcx+32],0
    ret
enumerate:
    mov r8,[rcx+32]
    test r8,r8
    jz success
    mov rdx,[r8]
    mov qword ptr [r8],1
    test rdx,rdx
    jz success
    mov rdx,[rcx+40]
    test rdx,rdx
    jz names
    mov rax,0abcd000000001234h
    mov [rdx],rax
names:
    mov rdx,[rcx+48]
    test rdx,rdx
    jz success
    lea rax,fixture_name
    mov [rdx],rax
success:
    xor eax,eax
    ret
invalid:
    mov eax,6
    ret
fixture_query ENDP
END
