// Checks src/startup_stubs/command_signature_filter.h without a device (builds on any platform): which
// indirect argument descriptions desktop D3D12 cannot create, so that device slot 41 does not hand
// them to the desktop device. usage: startup_command_signature_filter_check [--mutate off-by-one|first-only]
#include "startup_stubs/command_signature_filter.h"

#include <cstdio>
#include <cstring>

namespace {
// The shape of D3D12_INDIRECT_ARGUMENT_DESC the helper relies on: a Type member first.
struct Argument {
    unsigned Type;
    unsigned Payload[3];
};
constexpr unsigned last_desktop_type = 9;  // D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH_MESH

enum class Mutation { none, off_by_one, first_only };
Mutation mutation = Mutation::none;
int failures;

// The two wrong versions the check must catch: a bound that refuses the last desktop type, and a
// scan that only reads the first argument.
bool under_test(const Argument* arguments, std::size_t count)
{
    switch (mutation) {
    case Mutation::off_by_one: return x2w_startup::has_console_indirect_arg_type(arguments, count, last_desktop_type - 1);
    case Mutation::first_only: return x2w_startup::has_console_indirect_arg_type(arguments, count ? 1 : 0, last_desktop_type);
    default: return x2w_startup::has_console_indirect_arg_type(arguments, count, last_desktop_type);
    }
}

void expect(const char* name, const Argument* arguments, std::size_t count, bool expected)
{
    if (under_test(arguments, count) != expected) {
        std::printf("FAIL %s: expected %s\n", name, expected ? "a console type" : "desktop types only");
        ++failures;
    }
}
}  // namespace

int main(int argc, char** argv)
{
    if (argc == 3 && std::strcmp(argv[1], "--mutate") == 0) {
        if (std::strcmp(argv[2], "off-by-one") == 0) mutation = Mutation::off_by_one;
        else if (std::strcmp(argv[2], "first-only") == 0) mutation = Mutation::first_only;
        else return 2;
    } else if (argc != 1) {
        return 2;
    }

    const Argument draw_indexed[] = {{2, {}}};
    expect("one desktop argument", draw_indexed, 1, false);
    const Argument largest_desktop[] = {{last_desktop_type, {}}};
    expect("the largest desktop type", largest_desktop, 1, false);
    const Argument first_after[] = {{last_desktop_type + 1, {}}};
    expect("the first type above the desktop range", first_after, 1, true);
    const Argument seen[] = {{0x69, {12, 0, 0}}};
    expect("the type seen in a title (0x69)", seen, 1, true);
    const Argument mixed[] = {{1, {}}, {0x69, {}}};
    expect("a console type after a desktop one", mixed, 2, true);
    const Argument all_desktop[] = {{0, {}}, {4, {}}, {9, {}}};
    expect("several desktop types", all_desktop, 3, false);
    const Argument wide[] = {{0xffffffffu, {}}};
    expect("a type with the high bit set", wide, 1, true);
    expect("no arguments", draw_indexed, 0, false);
    expect("a null list", nullptr, 3, false);

    if (failures) return 1;
    std::printf("startup_command_signature_filter: PASS\n");
    return 0;
}
