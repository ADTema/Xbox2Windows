#pragma once

#include <cstdint>

struct IDXGIAdapter;

struct StartupBc7Input {
    const char* blocks;
    std::uint32_t width, height;
    bool tiled;
};

int check_stream_draw(IDXGIAdapter* adapter, void* guest, void* pso, const char* pixels,
                      const StartupBc7Input* bc7 = nullptr, std::uint32_t format = 0,
                      std::uint32_t export_word = 0);
