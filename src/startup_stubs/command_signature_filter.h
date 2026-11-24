// Device slot 41, CreateCommandSignature: which argument descriptions desktop D3D12 cannot create.
//
// The console executable names an indirect argument type outside the desktop enumeration (0x69 is
// seen, with stride 12). Desktop D3D12 defines the types from DRAW up to DISPATCH_MESH; any larger value
// is refused, and with the debug layer on the call is also reported as an error ("unexpected parameter
// type"). The description is therefore recognised before the desktop call, which is then not made.
//
// The header has no Windows dependency: it works on any description type that has a `Type` member.
#pragma once

#include <cstddef>

namespace x2w_startup {
// True when any of the `count` argument descriptions has a type above `last_desktop_type`.
template <class Description, class Type>
inline bool has_console_indirect_arg_type(const Description* arguments, std::size_t count, Type last_desktop_type)
{
    if (!arguments) return false;
    for (std::size_t i = 0; i < count; ++i)
        if (static_cast<unsigned>(arguments[i].Type) > static_cast<unsigned>(last_desktop_type)) return true;
    return false;
}
}  // namespace x2w_startup
