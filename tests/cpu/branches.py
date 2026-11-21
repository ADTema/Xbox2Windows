"""Check a PE function and its independently compiled translation through the Windows ABI."""

import ctypes
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from cpu_leaf_aot import translate

Word = ctypes.c_uint32
MASK = 0xffffffff


def invoke(function, value):
    words = (Word * 3)(0xaced0123, 0xdeadbeef, 0x9876cafe)
    output = ctypes.cast(ctypes.byref(words, ctypes.sizeof(Word)), ctypes.POINTER(Word))
    result = function(value, output)
    return result, tuple(words)


def expected(value, adjustment):
    stored = (value + adjustment) & MASK
    return (stored + 1) & MASK, (0xaced0123, stored, 0x9876cafe)


def check(original_path, lifted_path, inverted_path):
    original = ctypes.CDLL(original_path).branch_value
    lifted = ctypes.CDLL(lifted_path).lifted
    inverted = ctypes.CDLL(inverted_path).lifted
    for function in (original, lifted, inverted):
        function.argtypes = [Word, ctypes.POINTER(Word)]
        function.restype = Word

    values = [*range(256), 0x7fffffff, 0x80000000, *range(MASK - 4, MASK + 1)]
    for value in values:
        reference = invoke(original, value)
        if reference != expected(value, -7 if value < 5 else 3):
            raise AssertionError(f"source fixture mismatch for {value:#x}: {reference}")
        actual = invoke(lifted, value)
        if actual != reference:
            raise AssertionError(f"translation mismatch for {value:#x}: {actual} != {reference}")
        control = invoke(inverted, value)
        if control == reference or control != expected(value, 3 if value < 5 else -7):
            raise AssertionError(f"inverted branch control mismatch for {value:#x}: {control}")
    print(f"{len(values)} native/translated matches and {len(values)} inverted-branch differences; "
          f"{sum(v < 5 for v in values)} below threshold, {sum(v >= 5 for v in values)} at or above")


def check_rejections():
    for body, error in [
        ("90 c3", "unsupported or incomplete instruction at RVA 0x1002"),
        ("83 c0", "unsupported or incomplete instruction at RVA 0x1002"),
        ("eb 01 83 c0 05 c3", "branch into an instruction at RVA 0x1005"),
        ("eb 7f c3", "expected forward in-function branch at RVA 0x1002"),
        ("89 02", "missing terminal return at RVA 0x1004"),
    ]:
        try:
            translate(0x1000, bytes.fromhex("8b c1 " + body))
        except ValueError as exc:
            if str(exc) != error:
                raise AssertionError(str(exc)) from exc
        else:
            raise AssertionError(f"accepted invalid function: {body}")


if __name__ == "__main__":
    check(*sys.argv[1:])
    check_rejections()
