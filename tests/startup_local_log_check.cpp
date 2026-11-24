// Checks src/startup_stubs/local_log.h, the switches and log lines every permissive stand-in shares:
// which switch values count as on, the caller's last error kept by env_on and logf, and the exact
// bytes logf writes to stderr and appends to %X2W_TRAP_LOG%. The check points its own stderr handle
// and X2W_TRAP_LOG at files in a fresh folder under %TEMP% and removes them at the end.
#include "startup_stubs/local_log.h"

#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

namespace {
constexpr DWORD sentinel = 0x2A5A0BADu;  // an error value no call in the header sets
constexpr std::size_t longest = 1536 - 3;  // the line buffer, less CRLF and the terminator
int failures;

void check(bool condition, const char* what)
{
    if (condition) return;
    std::printf("FAIL: %s\n", what);
    ++failures;
}

std::string read_file(const std::wstring& path)
{
    std::ifstream in(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}

void write_file(const std::wstring& path, const std::string& text)
{
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

void same_bytes(const std::string& got, const std::string& expected, const char* what)
{
    if (got == expected) return;
    std::size_t at = 0;
    while (at < got.size() && at < expected.size() && got[at] == expected[at]) ++at;
    std::printf("FAIL: %s: %zu bytes, expected %zu; first difference at byte %zu\n", what, got.size(), expected.size(),
                at);
    ++failures;
}

// value nullptr: the variable is absent.
void switch_value(const char* value, bool on, const char* what)
{
    SetEnvironmentVariableA("X2W_LOCAL_LOG_SWITCH", value);
    SetLastError(sentinel);
    const bool got = x2w_local::env_on("X2W_LOCAL_LOG_SWITCH");
    const DWORD error = GetLastError();
    if (got != on || error != sentinel) {
        std::printf("FAIL: switch %s: %s with last error %lu, expected %s with %lu\n", what, got ? "on" : "off", error,
                    on ? "on" : "off", sentinel);
        ++failures;
    }
}

void logged(const char* text, const char* what)
{
    SetLastError(sentinel);
    x2w_local::logf("%s", text);
    if (GetLastError() != sentinel) {
        std::printf("FAIL: %s: last error %lu after logf, expected %lu\n", what, GetLastError(), sentinel);
        ++failures;
    }
}
}  // namespace

int main()
{
    wchar_t temp[MAX_PATH];
    const DWORD temp_length = GetTempPathW(MAX_PATH, temp);
    if (!temp_length || temp_length >= MAX_PATH) return std::printf("FAIL: no temporary folder\n"), 2;
    const std::wstring dir = std::wstring(temp) + L"x2w_local_log_" + std::to_wstring(GetCurrentProcessId());
    if (!CreateDirectoryW(dir.c_str(), nullptr)) return std::printf("FAIL: cannot create the work folder\n"), 2;
    const std::wstring err_path = dir + L"\\stderr.txt", log_path = dir + L"\\trap.log";
    // The longest path that fits MAX_PATH with its terminator (259 characters), and one character more.
    const std::size_t name_length = MAX_PATH - 1 - dir.size() - 1;
    if (name_length < 5 || name_length > 250) return std::printf("FAIL: unusable temporary folder length\n"), 2;
    const std::wstring fit_path = dir + L"\\" + std::wstring(name_length - 4, L'f') + L".log";
    const std::wstring long_path = dir + L"\\" + std::wstring(name_length - 3, L'g') + L".log";

    // Switches: a value that starts with '1' is on, anything else is off. env_on leaves the caller's last
    // error alone either way. Values of four or more characters are not checked: they do not fit the
    // reader's 4-byte buffer, and whether that is intended is not settled.
    switch_value(nullptr, false, "absent");
    switch_value("", false, "empty");
    for (const char* on : {"1", "10", "1x", "100"}) switch_value(on, true, on);
    for (const char* off : {"0", "2", "01", " 1", "on", "yes"}) switch_value(off, false, off);
    SetEnvironmentVariableA("X2W_LOCAL_LOG_SWITCH", nullptr);

    // logf writes to whatever the stderr handle is when it runs.
    HANDLE saved_err = GetStdHandle(STD_ERROR_HANDLE);
    HANDLE err = CreateFileW(err_path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS,
                             FILE_ATTRIBUTE_NORMAL, nullptr);
    if (err == INVALID_HANDLE_VALUE) return std::printf("FAIL: cannot create %ls\n", err_path.c_str()), 2;
    SetStdHandle(STD_ERROR_HANDLE, err);

    // Two lines append to a log that already holds a line; a missing variable leaves the log alone.
    std::string expected_err;
    write_file(log_path, "earlier line\r\n");
    SetEnvironmentVariableA("X2W_TRAP_LOG", nullptr);
    logged("not in the log", "no X2W_TRAP_LOG");
    expected_err += "not in the log\r\n";
    SetEnvironmentVariableW(L"X2W_TRAP_LOG", log_path.c_str());
    logged("first line", "existing log");
    SetLastError(sentinel);
    x2w_local::logf("second %s %d 0x%x", "line", -7, 0xBEEFu);
    check(GetLastError() == sentinel, "last error after a formatted logf");
    expected_err += "first line\r\nsecond line -7 0xbeef\r\n";
    std::string expected_log = "earlier line\r\nfirst line\r\nsecond line -7 0xbeef\r\n";
    same_bytes(read_file(log_path), expected_log, "log after two lines");

    // Truncation: the longest line fits whole, longer ones keep their first 1533 bytes and still end in CRLF.
    const std::string text(longest + 400, 'L');
    for (const std::size_t length : {longest - 1, longest, longest + 1, text.size()}) {
        logged(text.substr(0, length).c_str(), "long line");
        const std::string line = text.substr(0, length < longest ? length : longest) + "\r\n";
        expected_err += line;
        expected_log += line;
    }
    same_bytes(read_file(log_path), expected_log, "log after long lines");

    // A log path of exactly MAX_PATH - 1 characters is used; one character more is ignored, even right after
    // a line that went to another log (the buffer a too-long value leaves is undefined).
    SetEnvironmentVariableW(L"X2W_TRAP_LOG", fit_path.c_str());
    logged("longest log path", "longest log path");
    expected_err += "longest log path\r\n";
    same_bytes(read_file(fit_path), "longest log path\r\n", "log at the longest path");
    SetEnvironmentVariableW(L"X2W_TRAP_LOG", log_path.c_str());
    logged("before a long path", "short log path");
    expected_err += "before a long path\r\n";
    expected_log += "before a long path\r\n";
    SetEnvironmentVariableW(L"X2W_TRAP_LOG", long_path.c_str());
    logged("path too long", "log path too long");
    expected_err += "path too long\r\n";
    same_bytes(read_file(log_path), expected_log, "log after a path past MAX_PATH");
    check(GetFileAttributesW(long_path.substr(0, MAX_PATH - 1).c_str()) == INVALID_FILE_ATTRIBUTES,
          "no file at the truncated long path");

    // A log that cannot be opened (a folder) leaves the last error alone too.
    SetEnvironmentVariableW(L"X2W_TRAP_LOG", dir.c_str());
    logged("log is a folder", "log is a folder");
    expected_err += "log is a folder\r\n";
    SetEnvironmentVariableA("X2W_TRAP_LOG", nullptr);

    SetStdHandle(STD_ERROR_HANDLE, saved_err);
    CloseHandle(err);
    same_bytes(read_file(err_path), expected_err, "stderr");

    // first_calls: true for exactly the first limit calls.
    LONG counter = 0;
    int allowed = 0;
    for (int i = 0; i < 5; ++i) allowed += x2w_local::first_calls(counter, 3);
    check(allowed == 3, "first_calls allows 3 of 5 calls with limit 3");

    for (const std::wstring& path : {err_path, log_path, fit_path}) DeleteFileW(path.c_str());
    check(RemoveDirectoryW(dir.c_str()) != FALSE, "the work folder holds only the expected files");
    std::printf(failures ? "startup_local_log: %d failure(s)\n" : "startup_local_log: ok\n", failures);
    return failures ? 1 : 0;
}
