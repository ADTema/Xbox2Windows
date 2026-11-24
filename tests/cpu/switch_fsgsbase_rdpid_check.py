"""Differential checks, mutated-C++ controls, and unit/PE rejection controls
for RDFSBASE, RDGSBASE, WRFSBASE, WRGSBASE, and RDPID in tools/cpu_switch_aot.py.
"""

import ctypes
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

import pefile
from iced_x86 import Code, Decoder, Encoder, Formatter, FormatterSyntax, Instruction, Register as R

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_leaf_aot import bounded_code, export_rva
from cpu_switch_aot import Lifter, translate

U64 = ctypes.c_uint64
MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF

TRANSLATED_EXPORTS = (
    "rdfsbase_32",
    "rdfsbase_64",
    "rdgsbase_32",
    "rdgsbase_64",
    "wrfsbase_32_roundtrip",
    "wrfsbase_64_roundtrip",
    "wrgsbase_32_roundtrip",
    "wrgsbase_64_roundtrip",
    "wrfsgsbase_nonvolatile",
    "rdpid_64",
    "rdpid_twice",
    "flag_preserve_fsgsbase_rdpid",
    "unused_host_reads",
)

CANONICAL_64_VALUES = (
    0x0000000000000000,
    0x0000000012345678,
    0x0000000080000001,
    0x0000123456789ABC,
    0x00007FFFFFFFFFF0,
    0xFFFF800012345678,
    0xFFFFFFFF80000001,
)

WR32_VALUES = (
    0x0000000000000000,
    0x0000000012345678,
    0x0000000080000001,
    0x00007FFF80000001,
    0xDEAD0000BEEF1234,
    0xFFFFFFFFFFFFFFFF,
)

FLAG_PAIRS = (
    (0, 0),
    (1, 0),
    (0xFFFFFFFFFFFFFFFF, 1),
    (0x7FFFFFFFFFFFFFFF, 1),
    (0x8000000000000000, 0x8000000000000000),
    (0x5555555555555555, 0xAAAAAAAAAAAAAAAA),
    (0x123456789ABCDEF0, 0x0FEDCBA987654321),
)


def even_parity_byte(v):
    return (bin(v & 0xFF).count("1") % 2) == 0


def expected_add_flags(a, b):
    total = (a + b) & MASK64
    cf = int((a + b) > MASK64)
    zf = int(total == 0)
    sf = int((total >> 63) & 1)
    of = int((((~(a ^ b)) & (a ^ total)) >> 63) & 1)
    pf = int(even_parity_byte(total))
    return total, bytes((cf, zf, sf, of, pf))


def bind_lib(dll_path, prefix=""):
    lib = ctypes.CDLL(str(Path(dll_path).resolve()))
    funcs = {}
    for name in TRANSLATED_EXPORTS:
        fn = getattr(lib, prefix + name)
        fn.argtypes = [U64, U64, U64]
        fn.restype = U64
        funcs[name] = fn
    if not prefix:
        for helper in ("native_host_features", "native_rdtscp_aux"):
            fn = getattr(lib, helper)
            fn.argtypes = [U64, U64, U64]
            fn.restype = U64
            funcs[helper] = fn
    return lib, funcs


def logical_cpus():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetCurrentThread.restype = ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.SetThreadAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel32.SetThreadAffinityMask.restype = ctypes.c_size_t
    kernel32.GetCurrentProcessorNumber.restype = ctypes.c_uint32
    process, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel32.GetProcessAffinityMask(
        kernel32.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(system)
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessAffinityMask")
    cpus = [k for k in range(process.value.bit_length()) if (process.value >> k) & 1]
    return kernel32, process.value, cpus


def pin_to_cpu(kernel32, cpu):
    prev = kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(), 1 << cpu)
    if not prev:
        raise OSError(ctypes.get_last_error(), "SetThreadAffinityMask")
    for _ in range(200):
        running = kernel32.GetCurrentProcessorNumber()
        if running == cpu:
            return prev
        kernel32.Sleep(1)
    raise AssertionError(f"pinned to logical processor {cpu}, still running on {running}")


def verify_exports(native_fns, target_fns, label, cpus):
    """Run all differential checks for target_fns against native_fns across pinned CPUs."""
    kernel32, full_mask, _ = logical_cpus()
    saved_affinity = None
    total_checks = 0
    try:
        for cpu in cpus:
            prev = pin_to_cpu(kernel32, cpu)
            if saved_affinity is None:
                saved_affinity = prev

            # 1) Direct FS/GS base reads + 32-bit zero-extension
            base_fs = native_fns["rdfsbase_64"](0, 0, 0)
            base_gs = native_fns["rdgsbase_64"](0, 0, 0)
            if base_gs == 0:
                raise AssertionError(f"{label}: expected non-zero TEB GS_BASE on Windows x64")
            for tag, fns in (("native", native_fns), (label, target_fns)):
                got_fs64 = fns["rdfsbase_64"](0, 0, 0)
                got_gs64 = fns["rdgsbase_64"](0, 0, 0)
                got_fs32 = fns["rdfsbase_32"](0, 0, 0)
                got_gs32 = fns["rdgsbase_32"](0, 0, 0)
                if got_fs64 != base_fs or got_gs64 != base_gs:
                    raise AssertionError(
                        f"{tag} read base mismatch on cpu {cpu}: "
                        f"fs={got_fs64:#x}!={base_fs:#x}, gs={got_gs64:#x}!={base_gs:#x}"
                    )
                if got_fs32 != (base_fs & MASK32) or got_gs32 != (base_gs & MASK32):
                    raise AssertionError(
                        f"{tag} 32-bit read did not zero-extend on cpu {cpu}: "
                        f"fs32={got_fs32:#x}, gs32={got_gs32:#x}"
                    )
                total_checks += 4

            # 2) Canonical FS/GS round-trips (preserving TEB GS_BASE & FS_BASE across every call)
            for tag, fns in (("native", native_fns), (label, target_fns)):
                for val in WR32_VALUES:
                    got_fs = fns["wrfsbase_32_roundtrip"](val, 0, 0)
                    got_gs = fns["wrgsbase_32_roundtrip"](val, 0, 0)
                    want = val & MASK32
                    if got_fs != want or got_gs != want:
                        raise AssertionError(
                            f"{tag} wr*base_32({val:#x}): got fs={got_fs:#x}, gs={got_gs:#x}, want={want:#x}"
                        )
                    if native_fns["rdfsbase_64"](0, 0, 0) != base_fs or native_fns["rdgsbase_64"](0, 0, 0) != base_gs:
                        raise AssertionError(f"{tag} wr*base_32 failed to restore FS_BASE/TEB GS_BASE")
                    total_checks += 2

                for val in CANONICAL_64_VALUES:
                    got_fs = fns["wrfsbase_64_roundtrip"](val, 0, 0)
                    got_gs = fns["wrgsbase_64_roundtrip"](val, 0, 0)
                    if got_fs != val or got_gs != val:
                        raise AssertionError(
                            f"{tag} wr*base_64({val:#x}): got fs={got_fs:#x}, gs={got_gs:#x}"
                        )
                    if native_fns["rdfsbase_64"](0, 0, 0) != base_fs or native_fns["rdgsbase_64"](0, 0, 0) != base_gs:
                        raise AssertionError(f"{tag} wr*base_64 failed to restore FS_BASE/TEB GS_BASE")
                    total_checks += 2

                out_nv = (U64 * 2)()
                for fs_v, gs_v in zip(CANONICAL_64_VALUES, reversed(CANONICAL_64_VALUES)):
                    got_xor = fns["wrfsgsbase_nonvolatile"](fs_v, gs_v, ctypes.addressof(out_nv))
                    if got_xor != (fs_v ^ gs_v) or out_nv[0] != fs_v or out_nv[1] != gs_v:
                        raise AssertionError(
                            f"{tag} wrfsgsbase_nonvolatile({fs_v:#x}, {gs_v:#x}): "
                            f"got ({got_xor:#x}, {out_nv[0]:#x}, {out_nv[1]:#x})"
                        )
                    if native_fns["rdfsbase_64"](0, 0, 0) != base_fs or native_fns["rdgsbase_64"](0, 0, 0) != base_gs:
                        raise AssertionError(f"{tag} wrfsgsbase_nonvolatile failed to restore FS_BASE/TEB GS_BASE")
                    total_checks += 1

            # 3) RDPID cross-checked against pinned RDTSCP IA32_TSC_AUX
            aux = native_fns["native_rdtscp_aux"](0, 0, 0)
            out_pid = (U64 * 2)()
            for tag, fns in (("native", native_fns), (label, target_fns)):
                pid1 = fns["rdpid_64"](0, 0, 0)
                pid2 = fns["rdpid_twice"](0, 0, ctypes.addressof(out_pid))
                if pid1 != aux or pid2 != aux or out_pid[0] != aux or out_pid[1] != aux:
                    raise AssertionError(
                        f"{tag} rdpid mismatch on cpu {cpu}: pid1={pid1:#x}, pid2={pid2:#x}, "
                        f"buf=({out_pid[0]:#x}, {out_pid[1]:#x}), rdtscp_aux={aux:#x}"
                    )
                total_checks += 2

            # 4) FLAG_NEUTRAL flag preservation across all five instructions
            flag_buf = ctypes.create_string_buffer(8)
            for tag, fns in (("native", native_fns), (label, target_fns)):
                for a, b in FLAG_PAIRS:
                    exp_sum, exp_flags = expected_add_flags(a, b)
                    got_sum = fns["flag_preserve_fsgsbase_rdpid"](a, b, ctypes.addressof(flag_buf))
                    got_flags = flag_buf.raw[:5]
                    if got_sum != exp_sum or got_flags != exp_flags:
                        raise AssertionError(
                            f"{tag} flag_preserve({a:#x}, {b:#x}): "
                            f"sum={got_sum:#x}!={exp_sum:#x}, flags={got_flags.hex()}!={exp_flags.hex()}"
                        )
                    total_checks += 1

            # 5) Unused host-CPU reads must still compile and return 42
            for tag, fns in (("native", native_fns), (label, target_fns)):
                got_unused = fns["unused_host_reads"](0, 0, 0)
                if got_unused != 42:
                    raise AssertionError(f"{tag} unused_host_reads returned {got_unused}, expected 42")
                total_checks += 1
    finally:
        if saved_affinity is not None:
            kernel32.SetThreadAffinityMask(kernel32.GetCurrentThread(), full_mask)
    return total_checks


def compile_cpp_dll(cxx_path, cpp_path, dll_path, opt_flag="/O2"):
    obj_path = dll_path.with_suffix(".obj")
    cmd = [
        str(cxx_path),
        "/nologo",
        opt_flag,
        "/W4",
        "/LD",
        str(cpp_path),
        f"/Fo{obj_path}",
        f"/Fe{dll_path}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        raise AssertionError(f"failed to compile {cpp_path.name}:\n{res.stdout}\n{res.stderr}")


def build_mutated_sources(base_source):
    """Create four C++ mutants that each break one required semantic invariant."""
    mutants = {}

    # 1) Keep high 32 bits instead of zero-extending on RDFSBASE/RDGSBASE 32-bit and RDPID.
    src_keep, n1a = re.subn(
        r"(\w+) = static_cast<std::uint32_t>\(base\);",
        r"\1 = (\1 & ~0xffffffffull) | static_cast<std::uint32_t>(base);",
        base_source,
    )
    src_keep, n1b = re.subn(
        r"(\w+) = static_cast<std::uint64_t>\(pid\);",
        r"\1 = (\1 & ~0xffffffffull) | static_cast<std::uint32_t>(pid);",
        src_keep,
    )
    if n1a != 2 or n1b < 3:
        raise AssertionError(f"keep_high32 mutant expected 2 base + >=3 pid replacements, got {n1a}, {n1b}")
    mutants["keep_high32"] = src_keep

    # 2) Drop WRFSBASE/WRGSBASE writes (no-op).
    src_drop, n2 = re.subn(
        r"_write(fs|gs)base_u(32|64)\(([^;]+)\);",
        r"static_cast<void>(\3);",
        base_source,
    )
    if n2 < 4:
        raise AssertionError(f"drop_wrfsgsbase mutant expected >= 4 replacements, got {n2}")
    mutants["drop_wrfsgsbase"] = src_drop

    # 3) Constant RDPID instead of reading IA32_TSC_AUX.
    src_pid, n3 = re.subn(r"_rdpid_u32\(\)", "0x13572468u", base_source)
    if n3 < 2:
        raise AssertionError(f"constant_rdpid mutant expected >= 2 replacements, got {n3}")
    mutants["constant_rdpid"] = src_pid

    # 4) Clobber arithmetic flags inside lifted_flag_preserve_fsgsbase_rdpid.
    marker = "lifted_flag_preserve_fsgsbase_rdpid("
    head, rest = base_source.split(marker, 1)
    body, tail = rest.split("\n}", 1)
    body_mut, n4 = re.subn(
        r"(const volatile std::uint32_t pid = _rdpid_u32\(\);[^\n]+\n)",
        r"\1    fa = 0; fb = 1;\n",
        body,
        count=1,
    )
    if n4 != 1:
        raise AssertionError("clobber_flags mutant failed to anchor on _rdpid_u32 in flag_preserve")
    mutants["clobber_flags"] = head + marker + body_mut + "\n}" + tail

    return mutants


def encode_seq(*instructions):
    enc = Encoder(64)
    ip = 0x1000
    for ins in instructions:
        ip += enc.encode(ins, ip)
    return enc.take_buffer()


def check_rejections(native_path):
    # 1) Default profile (host_cpu omitted) must refuse all five instructions.
    for name in ("rdfsbase_64", "rdgsbase_64", "wrfsbase_64_roundtrip", "wrgsbase_64_roundtrip", "rdpid_64"):
        try:
            translate(native_path, [name])
        except ValueError as exc:
            if "requires host_cpu=True" not in str(exc):
                raise AssertionError(f"default profile {name}: unexpected {exc!r}") from exc
        else:
            raise AssertionError(f"default profile unexpectedly accepted {name}")

    # 2) MASM negative exports (undefined source on WRFSBASE/WRGSBASE, RSP operand).
    masm_refusals = (
        ("neg_undef_wrfsbase", "undefined register r10"),
        ("neg_undef_wrgsbase", "undefined register r11"),
        ("neg_rsp_rdfsbase", "rsp"),
        ("neg_rsp_rdpid", "rsp"),
    )
    for name, expected_reason in masm_refusals:
        try:
            translate(native_path, [name], host_cpu=True)
        except ValueError as exc:
            if expected_reason not in str(exc).lower():
                raise AssertionError(f"{name}: expected {expected_reason!r}, got {exc!r}") from exc
        else:
            raise AssertionError(f"{name}: translator unexpectedly accepted negative export")

    # 3) Unit Lifter.lower rejections: host_cpu omitted, RSP/ESP, prefixes, RDPID_R32.
    unit_insns = [
        ("lower_default_rdfsbase", Instruction.create_reg(Code.RDFSBASE_R64, R.RAX), False, "requires host_cpu=True"),
        ("lower_default_rdgsbase", Instruction.create_reg(Code.RDGSBASE_R32, R.EAX), False, "requires host_cpu=True"),
        ("lower_default_wrfsbase", Instruction.create_reg(Code.WRFSBASE_R64, R.RCX), False, "requires host_cpu=True"),
        ("lower_default_wrgsbase", Instruction.create_reg(Code.WRGSBASE_R32, R.ECX), False, "requires host_cpu=True"),
        ("lower_default_rdpid", Instruction.create_reg(Code.RDPID_R64, R.RAX), False, "requires host_cpu=True"),
        ("lower_rsp_rdfsbase", Instruction.create_reg(Code.RDFSBASE_R64, R.RSP), True, "unsupported use of rsp"),
        ("lower_esp_rdgsbase", Instruction.create_reg(Code.RDGSBASE_R32, R.ESP), True, "unsupported use of rsp"),
        ("lower_rsp_wrfsbase", Instruction.create_reg(Code.WRFSBASE_R64, R.RSP), True, "unsupported use of rsp"),
        ("lower_esp_wrgsbase", Instruction.create_reg(Code.WRGSBASE_R32, R.ESP), True, "unsupported use of rsp"),
        ("lower_rsp_rdpid", Instruction.create_reg(Code.RDPID_R64, R.RSP), True, "unsupported use of rsp"),
        ("lower_rdpid_r32", Instruction.create_reg(Code.RDPID_R32, R.EAX), True, "unsupported RDPID encoding"),
    ]
    for label, ins, opt_in, reason in unit_insns:
        try:
            Lifter(host_cpu=opt_in).lower(ins)
        except ValueError as exc:
            if reason not in str(exc):
                raise AssertionError(f"{label}: expected {reason!r}, got {exc!r}") from exc
        else:
            raise AssertionError(f"{label}: Lifter.lower unexpectedly accepted {ins}")

    # Segment / REP / LOCK prefixes on FSGSBASE and RDPID.
    gs_rdfsbase = Instruction.create_reg(Code.RDFSBASE_R32, R.EAX)
    gs_rdfsbase.segment_prefix = R.GS
    gs_rdpid = Instruction.create_reg(Code.RDPID_R64, R.RAX)
    gs_rdpid.segment_prefix = R.GS
    rep_wrfsbase = Instruction.create_reg(Code.WRFSBASE_R64, R.RCX)
    rep_wrfsbase.has_rep_prefix = True
    repne_rdgsbase = Instruction.create_reg(Code.RDGSBASE_R64, R.RAX)
    repne_rdgsbase.has_repne_prefix = True
    for label, ins in (
        ("seg_rdfsbase", gs_rdfsbase),
        ("seg_rdpid", gs_rdpid),
        ("rep_wrfsbase", rep_wrfsbase),
        ("repne_rdgsbase", repne_rdgsbase),
    ):
        try:
            Lifter(host_cpu=True).lower(ins)
        except ValueError as exc:
            if "unsupported instruction prefix" not in str(exc):
                raise AssertionError(f"{label}: expected prefix rejection, got {exc!r}") from exc
        else:
            raise AssertionError(f"{label}: Lifter.lower unexpectedly accepted prefixed {ins}")

    # 4) End-to-end PE-patched DLL rejections (patching wrfsgsbase_nonvolatile).
    pe_bytes = Path(native_path).read_bytes()
    with pefile.PE(data=pe_bytes, fast_load=True) as pe:
        entry = export_rva(pe, "wrfsgsbase_nonvolatile")
        file_off = pe.get_offset_from_rva(entry)
        pdata = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
        records = pe.get_data(pdata.VirtualAddress, pdata.Size)
        rec_idx = next(i for i in range(0, len(records), 12)
                       if int.from_bytes(records[i:i + 4], "little") == entry)
        pdata_end_off = pe.get_offset_from_rva(pdata.VirtualAddress + rec_idx + 4)
        orig_end = int.from_bytes(records[rec_idx + 4:rec_idx + 8], "little")
        max_len = orig_end - entry

    ret_bytes = encode_seq(Instruction.create(Code.RETNQ))
    pe_patches = [
        ("pe_seg_rdfsbase", bytes.fromhex("65f30faec0") + ret_bytes, "unsupported instruction prefix"),
        ("pe_seg_rdpid", bytes.fromhex("65f30fc7f8") + ret_bytes, "unsupported instruction prefix"),
        ("pe_lock_rdfsbase", bytes.fromhex("f0f30faec0") + ret_bytes, "invalid"),
        ("pe_rsp_rdfsbase", bytes.fromhex("f3480faec4") + ret_bytes, "frame"),
        ("pe_rsp_rdpid", bytes.fromhex("f30fc7fc") + ret_bytes, "frame"),
        ("pe_undef_wrfsbase", bytes.fromhex("f3490faed2") + ret_bytes, "undefined register"),
    ]
    with TemporaryDirectory() as folder:
        patched_path = Path(folder) / "patched.dll"
        for label, patch, reason in pe_patches:
            if len(patch) > max_len:
                raise AssertionError(f"{label}: patch ({len(patch)} bytes) exceeds max_len ({max_len})")
            damaged = bytearray(pe_bytes)
            damaged[file_off:file_off + len(patch)] = patch
            damaged[pdata_end_off:pdata_end_off + 4] = (entry + len(patch)).to_bytes(4, "little")
            patched_path.write_bytes(damaged)
            try:
                translate(patched_path, ["wrfsgsbase_nonvolatile"], host_cpu=True)
            except ValueError as exc:
                if reason not in str(exc).lower():
                    raise AssertionError(f"{label}: expected {reason!r}, got {exc!r}") from exc
            else:
                raise AssertionError(f"{label}: PE translate unexpectedly accepted patched bytes")

    print(f"20 unit rejections (5 default-profile, 4 MASM negative, 11 Lifter.lower/prefix) "
          f"and {len(pe_patches)} PE-patched rejections passed")


def record_covered_forms(native_path):
    record = os.environ.get("FORM_COVERAGE_RECORD")
    if not record:
        return
    formatter = Formatter(FormatterSyntax.INTEL)
    forms = set()
    with pefile.PE(str(native_path), fast_load=True) as pe:
        for name in TRANSLATED_EXPORTS:
            entry = export_rva(pe, name)
            raw = bounded_code(pe, entry)
            for ins in Decoder(64, raw, ip=entry):
                forms.add(formatter.format_mnemonic(ins).lower())
    out_path = Path(record)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(word + "\n" for word in sorted(forms)), encoding="utf-8")


def unload_lib(lib):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
    kernel32.FreeLibrary.restype = ctypes.c_int
    handle = getattr(lib, "_handle", None)
    if handle:
        kernel32.FreeLibrary(handle)


def main():
    native_path, lifted_path, cxx_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if os.environ.get("FORM_COVERAGE_RECORD"):
        Path(os.environ["FORM_COVERAGE_RECORD"]).unlink(missing_ok=True)

    _, native_fns = bind_lib(native_path)
    features = native_fns["native_host_features"](0, 0, 0)
    if (features & 3) != 3:
        print(f"host lacks CPUID.07H FSGSBASE/RDPID (mask={features:#x}); skipping")
        raise SystemExit(77)

    _, lifted_fns = bind_lib(lifted_path, "lifted_")
    _, _, all_cpus = logical_cpus()
    cpus = all_cpus[:4] if len(all_cpus) > 4 else all_cpus

    checked_cmake = verify_exports(native_fns, lifted_fns, "lifted_cmake", cpus)

    # Also build /O2 and the 4 mutated C++ negative control DLLs directly from cpu_switch_aot.
    source_text, _ = translate(native_path, list(TRANSLATED_EXPORTS), host_cpu=True)
    mutants = build_mutated_sources(source_text)
    with TemporaryDirectory() as folder:
        tmp = Path(folder)
        o2_cpp = tmp / "lifted_o2.cpp"
        o2_dll = tmp / "lifted_o2.dll"
        o2_cpp.write_text(source_text, encoding="utf-8")
        compile_cpp_dll(cxx_path, o2_cpp, o2_dll, "/O2")
        o2_lib, o2_fns = bind_lib(o2_dll, "lifted_")
        try:
            checked_o2 = verify_exports(native_fns, o2_fns, "lifted_o2", cpus)
        finally:
            o2_fns.clear()
            unload_lib(o2_lib)

        for mut_name, mut_src in mutants.items():
            mut_cpp = tmp / f"{mut_name}.cpp"
            mut_dll = tmp / f"{mut_name}.dll"
            mut_cpp.write_text(mut_src, encoding="utf-8")
            compile_cpp_dll(cxx_path, mut_cpp, mut_dll, "/O2")
            mut_lib, mut_fns = bind_lib(mut_dll, "lifted_")
            try:
                try:
                    verify_exports(native_fns, mut_fns, f"mutant_{mut_name}", cpus[:1])
                except AssertionError as exc:
                    print(f"mutant {mut_name} caught: {exc}")
                else:
                    raise AssertionError(f"mutant {mut_name} unexpectedly passed all checks")
            finally:
                mut_fns.clear()
                unload_lib(mut_lib)

    check_rejections(native_path)
    record_covered_forms(native_path)
    print(f"verified {checked_cmake} CMake-lifted + {checked_o2} /O2-lifted checks across "
          f"{len(cpus)} pinned CPU(s), 4 mutated-C++ controls, and all rejections")


if __name__ == "__main__":
    main()
