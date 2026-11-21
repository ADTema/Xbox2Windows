; Windows x64: ECX = unsigned input, RDX = address of one writable DWORD.
.code
branch_value PROC FRAME
    .endprolog
    mov eax, ecx
    cmp eax, 5
IFDEF INVERT_BRANCH
    jae short small_value
ELSE
    jb short small_value
ENDIF
    add eax, 3
    jmp short store_value
small_value:
    sub eax, 7
store_value:
    mov DWORD PTR [rdx], eax
    add eax, 1
    ret
branch_value ENDP
END
