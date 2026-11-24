// Experimental (docs/startup-runtime.md): a cross-process lock on one small file, used by the
// game-save store so that readers and the publication of an update exclude each other. Windows:
// LockFileEx on byte 0 of the file; elsewhere flock. The system releases the lock when the holder's
// handle closes, so a process that died while holding it never blocks the others for good. A wait
// is always bounded: acquire gives up with LockResult::timeout.
#pragma once

#include <cerrno>
#include <chrono>
#include <filesystem>
#include <thread>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace x2w_save {

enum class LockResult { locked, timeout, error };

class FileLock {
public:
    FileLock() = default;
    FileLock(const FileLock&) = delete;
    FileLock& operator=(const FileLock&) = delete;
    ~FileLock() { release(); }

    // Opens (creating it when needed) and locks the file, shared or exclusive, trying again every
    // few milliseconds until the timeout ends. The directory of the file must exist.
    LockResult acquire(const std::filesystem::path& file, bool exclusive, std::chrono::milliseconds timeout)
    {
        release();
        if (!open(file)) return LockResult::error;
        const auto deadline = std::chrono::steady_clock::now() + timeout;
        for (int pause = 1;; pause = pause < 16 ? pause * 2 : pause) {
            const Attempt attempt = try_lock_once(exclusive);
            if (attempt == Attempt::locked) return LockResult::locked;
            if (attempt == Attempt::error) break;
            if (std::chrono::steady_clock::now() >= deadline) {
                release();
                return LockResult::timeout;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(pause));
        }
        release();
        return LockResult::error;
    }

    void release() noexcept
    {
#ifdef _WIN32
        if (handle_ != INVALID_HANDLE_VALUE) CloseHandle(handle_);  // closing the handle drops the lock
        handle_ = INVALID_HANDLE_VALUE;
#else
        if (fd_ >= 0) close(fd_);
        fd_ = -1;
#endif
    }

private:
    enum class Attempt { locked, busy, error };

    bool open(const std::filesystem::path& file)
    {
#ifdef _WIN32
        handle_ = CreateFileW(file.c_str(), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        return handle_ != INVALID_HANDLE_VALUE;
#else
        fd_ = ::open(file.c_str(), O_RDWR | O_CREAT | O_CLOEXEC, 0644);
        return fd_ >= 0;
#endif
    }

    Attempt try_lock_once(bool exclusive)
    {
        // x2w-seam: lock-attempt
#ifdef _WIN32
        OVERLAPPED where{};
        const DWORD flags = LOCKFILE_FAIL_IMMEDIATELY | (exclusive ? LOCKFILE_EXCLUSIVE_LOCK : 0);
        if (LockFileEx(handle_, flags, 0, 1, 0, &where)) return Attempt::locked;
        return GetLastError() == ERROR_LOCK_VIOLATION ? Attempt::busy : Attempt::error;
#else
        if (flock(fd_, (exclusive ? LOCK_EX : LOCK_SH) | LOCK_NB) == 0) return Attempt::locked;
        return errno == EWOULDBLOCK ? Attempt::busy : Attempt::error;
#endif
    }

#ifdef _WIN32
    HANDLE handle_ = INVALID_HANDLE_VALUE;
#else
    int fd_ = -1;
#endif
};

}  // namespace x2w_save
