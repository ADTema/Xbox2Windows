EXTERN __imp_XMemIsToolsMemAvailable:QWORD

.data
call1 dd 0
call2 dd 0

.code
native_entry PROC FRAME
    sub rsp, 28h
    .allocstack 28h
    .endprolog

    ; 1. First call to XMemIsToolsMemAvailable
    call qword ptr [__imp_XMemIsToolsMemAvailable]
    mov dword ptr [call1], eax

    ; 2. Second call to XMemIsToolsMemAvailable
    call qword ptr [__imp_XMemIsToolsMemAvailable]
    mov dword ptr [call2], eax

    ; 3. Verify consistency: both calls must return the same BOOL value
    mov edx, dword ptr [call1]
    cmp eax, edx
    jne fail_mismatch

    ; 4. Branch based on BOOL outcome:
    ; If 0 (FALSE): desktop without a tools partition fallback
    test eax, eax
    jz desktop_no_tools

    ; If 1 (TRUE): console devkit with a tools partition
    cmp eax, 1
    jne fail_invalid_bool

    ; Outcome: TRUE -> devkit mode, return 84
    mov eax, 84
    jmp done

desktop_no_tools:
    ; Outcome: FALSE -> desktop mode, return 42
    mov eax, 42
    jmp done

fail_mismatch:
    mov eax, 1
    jmp done

fail_invalid_bool:
    mov eax, 2
    jmp done

done:
    add rsp, 28h
    ret
native_entry ENDP
END
