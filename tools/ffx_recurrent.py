"""Bounded translation for the default upscaler provider's first resource."""
from uuid import UUID

from ffx_version_query import lower, region


def generate_recurrent(pe):
    def blocks(*ranges):
        return [ins for start, end in ranges for ins in region(pe, start, end)]

    name = "FSR4UPSCALER_Recurrent"
    raw_name = (name + "\0").encode("utf-16le")
    iid = pe.get_data(0x48310, 16)
    if pe.get_data(0x4d928, len(raw_name)) != raw_name or UUID(bytes_le=iid) != UUID("696442be-a72e-4059-bc79-5b5c98040fad"):
        raise ValueError("unexpected recurrent resource identity")
    builder = lower(blocks((0xcfcb, 0xcfd2), (0xcfe0, 0xd001), (0xbf95, 0xc038)),
                    ["rdi = reinterpret_cast<word>(&provider); rdx = reinterpret_cast<word>(&config);",
                     "uint8_t local[192]{}; rbp = reinterpret_cast<word>(local + 112);"],
                    {0x4d928: 'reinterpret_cast<word>(L"FSR4UPSCALER_Recurrent")', 0x4d958: "0"}, {},
                    {0xcfd2: "goto block_cfe0;",
                     0xd001: "r14 = r8; rdi = reinterpret_cast<word>(descriptor); goto block_bf95;",
                     0xc038: "return;"})

    # Resolve the two enum-switch edges from the file's own jump tables.
    format_code, state_code = 10, 2
    fmt = pe.get_dword_at_rva(0x226c + 4 * format_code)
    format_leaf = lower(region(pe, fmt, fmt + 6), [], {}, {}, {})
    selector = pe.get_data(0x3a20 + state_code - 1, 1)[0]
    state = pe.get_dword_at_rva(0x39f4 + 4 * selector)
    path = blocks((0xd1e4, 0xd1ff), (0x2e5d, 0x2f7f), (0x2fca, 0x3002),
                  (0x301f, 0x303d), (0x31fa, 0x321c), (0x3228, 0x322b),
                  (state, state + 7), (0x329d, 0x32a8), (0x32f6, 0x3302),
                  (0x3333, 0x33f2), (0x33f9, 0x340b))
    unsupported = 'throw std::runtime_error("Outside default recurrent resource path");'
    edges = dict.fromkeys((0x2f7f, 0x301b, 0x3002, 0x303d, 0x321c, 0x32a8, 0x3302, 0x33f2), unsupported)
    edges.update({0xd1ff: "goto block_2e5d;",
                  0x322b: f"if (rbx != {state_code}) {unsupported} goto block_{state:x};",
                  0x340b: "return;"})
    calls = {0x2ea1: "rax = 0; /* No Xbox working-set statistics on this host. */",
             0x2fd0: f"if (rcx != {format_code}) {unsupported} rax = recurrent_format();",
             0x33cc: "rax = binding.create(rcx, rdx, r8, r9, frame);",
             0x33d4: 'check(static_cast<HRESULT>(rcx), "Recurrent resource creation");',
             0x33f9: 'check(binding.resource->SetName(reinterpret_cast<const wchar_t*>(rdx)), "Name recurrent resource");'}
    backend = lower(path, ["rdi = reinterpret_cast<word>(&provider); rdx = reinterpret_cast<word>(descriptor);",
                           "uint8_t local[384]{}; rbp = reinterpret_cast<word>(local + 128);"],
                    {0: "0", 0xbeb50: "reinterpret_cast<word>(&no_callback)",
                     0x48310: "reinterpret_cast<word>(resource_iid)"}, calls, edges)
    return ('\n#include "ffx_recurrent.h"\n#include <stdexcept>\n'
            'static const word no_callback = 0;\n'
            'static const uint8_t resource_iid[] = {' + ','.join(map(str, iid)) + '};\n'
            'static word recurrent_format() {\n' + format_leaf + '\n}\n'
            'static void first_descriptor(RecurrentProvider& provider, const RecurrentConfig& config, uint8_t* descriptor) {\n'
            + builder + '\n}\n'
            'void run_recurrent(RecurrentBinding& binding, RecurrentProvider& provider, const RecurrentConfig& config) {\n'
            '    uint8_t descriptor[0x68]{}; first_descriptor(provider, config, descriptor);\n' + backend + '\n}\n')
