"""Syntax-check every Python file under tools/startup (Refs #1149).

Compiles each source without importing or running it, so a file that cannot be parsed is reported with its path
and line number. Nothing in this check executes the tools; a syntax error is the only thing it can see.

The self-test is what keeps a "0 problems" line meaningful: a deliberately broken snippet must be rejected and
a valid one accepted, so the harness is shown to observe parse errors at all rather than reporting that it
looked at nothing.
"""

import pathlib
import sys

DEFAULT_DIRECTORY = "tools/startup"


def compile_sources(directory):
    """Returns (files, problems) for every .py file under directory."""
    files = sorted(pathlib.Path(directory).rglob("*.py"))
    problems = []
    for path in files:
        try:
            # utf-8-sig, not utf-8: Python accepts a UTF-8 BOM in source, so treating one as a syntax error
            # would fail a file that the interpreter runs.
            source = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            problems.append("{}: unreadable or not UTF-8: {}".format(path, error))
            continue
        try:
            compile(source, str(path), "exec", dont_inherit=True)
        except SyntaxError as error:
            problems.append("{}:{}: {}".format(path, error.lineno, error.msg))
    return files, problems


def self_test():
    """Proves this harness rejects a broken snippet and accepts a valid one."""
    failures = []
    try:
        compile("def broken(:\n", "<control>", "exec", dont_inherit=True)
    except SyntaxError:
        pass
    else:
        failures.append("control: a snippet that cannot be parsed was accepted")
    try:
        compile("def fine():\n    return 1\n", "<control>", "exec", dont_inherit=True)
    except SyntaxError as error:
        failures.append("control: a valid snippet was rejected ({})".format(error))
    return failures


def main(argv):
    directory = argv[1] if len(argv) > 1 else DEFAULT_DIRECTORY
    files, problems = compile_sources(directory)
    controls = self_test()
    if not files:
        print("FAIL: no Python files found under {}".format(directory))
        return 1
    for problem in problems:
        print("syntax error: {}".format(problem))
    for failure in controls:
        print(failure)
    if problems or controls:
        print("FAIL: {} of {} files under {} cannot be parsed".format(len(problems), len(files), directory))
        return 1
    print("PASS: {} files under {} parse; control snippet rejected and valid snippet accepted".format(
        len(files), directory))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))