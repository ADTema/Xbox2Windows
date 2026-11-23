#pragma once

#include <cstdint>
#include <string>
#include <vector>

struct _LUID;

// Windows can list one device under several DXGI LUIDs, and vendor/device IDs do not tell them
// apart from separate adapters of the same model; the PnP device keys do.
namespace adapter_identity {
struct Identity {
    std::uint32_t nodes = 0;            // physical adapters behind the LUID (DXGI nodes); 0 if unknown
    std::vector<std::wstring> devices;  // their sorted PnP hardware keys; empty if any cannot be read
};

Identity query(const _LUID& luid) noexcept;
}
