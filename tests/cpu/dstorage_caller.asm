EXTERN __imp_DStorageGetFactory:QWORD
PUBLIC native_entry

.data
; Test-provider policy console IIDs exercising the Xbox DirectStorage factory pattern
; IDStorageFactoryX: {62959d11-d45f-4884-a0a3-f7862ea243ae}
IID_IDStorageFactoryX db 11h, 9dh, 95h, 62h, 5fh, 0d4h, 84h, 48h, 0a0h, 0a3h, 0f7h, 86h, 2eh, 0a2h, 43h, 0aeh

; IDStorageQueueX: {3c02cb0c-c050-4195-99a1-a1ce94ba33c5}
IID_IDStorageQueueX   db 0ch, 0cbh, 02h, 3ch, 50h, 0c0h, 95h, 41h, 99h, 0a1h, 0a1h, 0ceh, 94h, 0bah, 33h, 0c5h

; Public MIT DirectStorage PC IDStorageFactory: {6924ea0c-c3cd-4826-b10a-f64f4ed927c1}
IID_IDStorageFactory_PC db 0ch, 0eah, 24h, 69h, 0cdh, 0c3h, 26h, 48h, 0b1h, 0ah, 0f6h, 4fh, 4eh, 0d9h, 27h, 0c1h

pFactory dq 0
pQueue   dq 0

queue_name db "TestQueue", 0
ALIGN 8
queue_desc:
dd 0                ; SourceType = DSTORAGE_REQUEST_SOURCE_FILE (0)
dd 0                ; padding
dw 16               ; Capacity = 16
db 0                ; Priority = NORMAL (0)
db 5 dup(0)         ; padding
dq queue_name       ; Name

dummy_request db 64 dup(0)
dest_buffer   db 64 dup(0AAh)

.code
native_entry PROC FRAME
    sub rsp, 38h
    .allocstack 38h
    .endprolog

    ; Step 0: Refusal control - request PC IDStorageFactory IID {6924ea0c-c3cd-4826-b10a-f64f4ed927c1}
    ; Must return E_NOINTERFACE (0x80004002) and leave *ppv untouched.
    mov qword ptr [pFactory], 0DEADBEEFh
    lea rcx, IID_IDStorageFactory_PC
    lea rdx, pFactory
    call qword ptr [__imp_DStorageGetFactory]
    cmp eax, 80004002h ; E_NOINTERFACE
    jne fail_pc_refusal
    cmp qword ptr [pFactory], 0DEADBEEFh
    jne fail_pc_clobber

    ; Step 1: DStorageGetFactory(&IID_IDStorageFactoryX, &pFactory)
    mov qword ptr [pFactory], 0
    lea rcx, IID_IDStorageFactoryX
    lea rdx, pFactory
    call qword ptr [__imp_DStorageGetFactory]
    test eax, eax
    jnz fail_factory
    mov rcx, qword ptr [pFactory]
    test rcx, rcx
    jz fail_factory

    ; Step 2: factory->SetStagingBufferSize(0x2000000) (slot 8 = +0x40)
    mov rax, qword ptr [rcx]
    mov edx, 2000000h
    call qword ptr [rax + 40h]
    test eax, eax
    js fail_staging_buffer

    ; Step 3: factory->CreateQueue(&queue_desc, &IID_IDStorageQueueX, &pQueue) (slot 10 = +0x50)
    mov rcx, qword ptr [pFactory]
    mov rax, qword ptr [rcx]
    lea rdx, queue_desc
    lea r8, IID_IDStorageQueueX
    lea r9, pQueue
    call qword ptr [rax + 50h]
    test eax, eax
    js fail_create_queue
    mov rcx, qword ptr [pQueue]
    test rcx, rcx
    jz fail_create_queue

    ; Step 4: queue->EnqueueRequest(&dummy_request) (slot 3 = +0x18)
    mov rcx, qword ptr [pQueue]
    mov rax, qword ptr [rcx]
    lea rdx, dummy_request
    call qword ptr [rax + 18h]

    ; Step 5: Delayed-submit negative control:
    ; Staged request (< half capacity) must remain pending before Submit
    mov rcx, qword ptr [pQueue]
    cmp dword ptr [rcx + 14h], 0
    jne fail_delayed_submit

    ; Check destination buffer remains unmodified (0xAA) before Submit
    cmp byte ptr [dest_buffer], 0AAh
    jne fail_delayed_submit

    ; Step 6: queue->Submit() (slot 6 = +0x30)
    mov rcx, qword ptr [pQueue]
    mov rax, qword ptr [rcx]
    call qword ptr [rax + 30h]

    ; Step 7: Verification: completion flag must now be set
    mov rcx, qword ptr [pQueue]
    cmp dword ptr [rcx + 14h], 1
    jne fail_submit

    ; Step 8: Cleanup and release objects
    mov rcx, qword ptr [pQueue]
    mov rax, qword ptr [rcx]
    call qword ptr [rax + 10h] ; queue->Release()

    mov rcx, qword ptr [pFactory]
    mov rax, qword ptr [rcx]
    call qword ptr [rax + 10h] ; factory->Release()

    ; Success exit milestone
    mov eax, 0870h
    jmp done

fail_factory:
    mov eax, 0301h
    jmp done

fail_staging_buffer:
    mov eax, 0302h
    jmp done

fail_create_queue:
    mov eax, 0303h
    jmp done

fail_delayed_submit:
    mov eax, 0304h
    jmp done

fail_submit:
    mov eax, 0305h
    jmp done

fail_pc_refusal:
    mov eax, 0306h
    jmp done

fail_pc_clobber:
    mov eax, 0307h
    jmp done

done:
    add rsp, 38h
    ret
native_entry ENDP
END
