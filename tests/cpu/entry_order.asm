; Source-owned control for a translated function whose entry is not its lowest instruction.
; A leaf without unwind data may use any unowned bytes of its section, so a jump from the
; exported entry can continue in code assembled below it.
.code
; RAX = RCX * RCX + RDX, stored to the first trace word.
square_tail PROC
    imul rcx, rcx
    lea rax, [rcx+rdx]
    mov [r8], rax
    ret
square_tail ENDP

; Increments RCX, then continues in square_tail below the entry.
inc_square PROC
    inc rcx
    jmp square_tail
inc_square ENDP

; Below RDX: continues in square_tail. Otherwise RAX = RCX - RDX, stored to the second trace word.
pick_tail PROC
    cmp rcx, rdx
    jb square_tail
    mov rax, rcx
    sub rax, rdx
    mov [r8+8], rax
    ret
pick_tail ENDP
END
