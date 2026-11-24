#include <d3d12.h>
#include <d3d12sdklayers.h>
#include <d3dcompiler.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include "desktop_gpu.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

extern "C" __declspec(dllimport) HRESULT WINAPI D3D12XboxCreateDevice(IUnknown*, const void*, REFIID, void**);

namespace {
using Microsoft::WRL::ComPtr;
using Words = std::array<std::uint32_t, 6>;
constexpr Words initial{0xa5a5a5a5, 0, 3, 2, 0x31415926, 0x5a5a5a5a};
constexpr UINT argument_offset = sizeof(std::uint32_t);
constexpr UINT argument_bytes = 4 * sizeof(std::uint32_t);
constexpr UINT result_bytes = 2 * sizeof(std::uint32_t);

// The two entry points bind different buffers at u0. The consumer changes
// one word per group, so a missing or incorrectly shaped dispatch is visible.
constexpr char shader[] = R"(
RWByteAddressBuffer data : register(u0);
[numthreads(1, 1, 1)]
void write_args() { data.Store3(4, uint3(4, 3, 2)); }

[numthreads(1, 1, 1)]
void consume_args(uint3 group : SV_GroupID) {
    uint previous;
    data.InterlockedAdd(0, 1 + group.x + 10 * group.y + 100 * group.z, previous);
}
)";

ComPtr<ID3D12PipelineState> pipeline(ID3D12Device* device, ID3D12RootSignature* root, const char* entry)
{
    ComPtr<ID3DBlob> code, errors;
    const HRESULT hr = D3DCompile(shader, sizeof(shader) - 1, nullptr, nullptr, nullptr, entry, "cs_5_0",
                                  0, 0, &code, &errors);
    if (FAILED(hr) && errors) std::fprintf(stderr, "%s\n", static_cast<const char*>(errors->GetBufferPointer()));
    check(hr, entry);
    D3D12_COMPUTE_PIPELINE_STATE_DESC desc{};
    desc.pRootSignature = root;
    desc.CS = {code->GetBufferPointer(), code->GetBufferSize()};
    ComPtr<ID3D12PipelineState> result;
    check(device->CreateComputePipelineState(&desc, IID_PPV_ARGS(&result)), entry);
    return result;
}

bool run(ID3D12Device* device, ID3D12RootSignature* root, ID3D12PipelineState* writer,
         ID3D12PipelineState* consumer, ID3D12CommandSignature* signature, bool write_args)
{
    auto upload = make_buffer(device, sizeof(initial), D3D12_HEAP_TYPE_UPLOAD, D3D12_RESOURCE_STATE_GENERIC_READ);
    auto readback = make_buffer(device, sizeof(initial), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    auto arguments = make_buffer(device, argument_bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST,
                                 D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto result = make_buffer(device, result_bytes, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COPY_DEST,
                              D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    void* memory = nullptr;
    const D3D12_RANGE untouched{0, 0};
    check(upload->Map(0, &untouched, &memory), "map upload");
    std::memcpy(memory, initial.data(), sizeof(initial));
    upload->Unmap(0, nullptr);

    ComputeCommands commands(device, nullptr);
    auto* list = commands.list.Get();
    list->CopyBufferRegion(arguments.Get(), 0, upload.Get(), 0, argument_bytes);
    list->CopyBufferRegion(result.Get(), 0, upload.Get(), argument_bytes, result_bytes);
    transition(list, result.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    list->SetComputeRootSignature(root);
    auto argument_state = D3D12_RESOURCE_STATE_COPY_DEST;
    if (write_args) {
        transition(list, arguments.Get(), argument_state, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
        argument_state = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        list->SetPipelineState(writer);
        list->SetComputeRootUnorderedAccessView(0, arguments->GetGPUVirtualAddress());
        list->Dispatch(1, 1, 1);
    }
    // The transition orders the UAV writes before the command processor reads the record.
    transition(list, arguments.Get(), argument_state, D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT);
    list->SetPipelineState(consumer);
    list->SetComputeRootUnorderedAccessView(0, result->GetGPUVirtualAddress());
    list->ExecuteIndirect(signature, 1, arguments.Get(), argument_offset, nullptr, 0);
    transition(list, arguments.Get(), D3D12_RESOURCE_STATE_INDIRECT_ARGUMENT, D3D12_RESOURCE_STATE_COPY_SOURCE);
    transition(list, result.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(readback.Get(), 0, arguments.Get(), 0, argument_bytes);
    list->CopyBufferRegion(readback.Get(), argument_bytes, result.Get(), 0, result_bytes);
    commands.submit_and_wait(device);

    const D3D12_RANGE read{0, sizeof(initial)};
    check(readback->Map(0, &read, &memory), "map readback");
    Words observed{};
    std::memcpy(observed.data(), memory, sizeof(observed));
    readback->Unmap(0, &untouched);
    Words expected = initial;
    if (write_args) {
        expected[1] = 4;
        for (std::uint32_t z = 0; z < expected[3]; ++z)
            for (std::uint32_t y = 0; y < expected[2]; ++y)
                for (std::uint32_t x = 0; x < expected[1]; ++x)
                    expected[4] += 1 + x + 10 * y + 100 * z;
    }
    std::printf("%s: args=(%u,%u,%u), result=0x%08x (expected 0x%08x)\n",
                write_args ? "GPU writer" : "omitted writer", observed[1], observed[2], observed[3],
                observed[4], expected[4]);
    for (std::size_t i = 0; i < expected.size(); ++i) {
        if (observed[i] == expected[i]) continue;
        std::fprintf(stderr, "word %zu: got 0x%08x, expected 0x%08x\n", i, observed[i], expected[i]);
        return false;
    }
    return true;
}
}  // namespace

int main(int argc, char** argv) try
{
    const bool warp = argc == 2 && std::strcmp(argv[1], "warp") == 0;
    if (!warp && (argc != 2 || std::strcmp(argv[1], "hardware") != 0)) return 2;
    ComPtr<ID3D12Debug> debug;
    const HRESULT debug_hr = D3D12GetDebugInterface(IID_PPV_ARGS(&debug));
    if (debug_hr != DXGI_ERROR_SDK_COMPONENT_MISSING) check(debug_hr, "get debug layer");
    if (debug) debug->EnableDebugLayer();
    ComPtr<IDXGIFactory6> factory;
    check(CreateDXGIFactory1(IID_PPV_ARGS(&factory)), "create DXGI factory");
    ComPtr<IDXGIAdapter1> adapter;
    ComPtr<ID3D12Device> device;
    if (warp) {
        check(factory->EnumWarpAdapter(IID_PPV_ARGS(&adapter)), "find WARP");
    } else {
        for (UINT index = 0; factory->EnumAdapters1(index, adapter.ReleaseAndGetAddressOf()) == S_OK; ++index) {
            DXGI_ADAPTER_DESC1 desc{};
            if (SUCCEEDED(adapter->GetDesc1(&desc)) && !(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) &&
                SUCCEEDED(D3D12CreateDevice(adapter.Get(), D3D_FEATURE_LEVEL_12_0, __uuidof(ID3D12Device), nullptr))) break;
        }
        if (!adapter) return 77;
    }
    check(D3D12XboxCreateDevice(adapter.Get(), nullptr, IID_PPV_ARGS(&device)), "create desktop device through d3d12_xs");
    DXGI_ADAPTER_DESC1 adapter_desc{};
    check(adapter->GetDesc1(&adapter_desc), "get adapter description");
    std::printf("adapter: %ls, debug layer %s\n", adapter_desc.Description, debug ? "enabled" : "unavailable");
    LARGE_INTEGER driver{};
    if (SUCCEEDED(adapter->CheckInterfaceSupport(__uuidof(IDXGIDevice), &driver)))
        std::printf("driver: %u.%u.%u.%u\n", HIWORD(driver.HighPart), LOWORD(driver.HighPart),
                    HIWORD(driver.LowPart), LOWORD(driver.LowPart));

    D3D12_ROOT_PARAMETER uav{};
    uav.ParameterType = D3D12_ROOT_PARAMETER_TYPE_UAV;
    uav.ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    const D3D12_ROOT_SIGNATURE_DESC desc{1, &uav, 0, nullptr, D3D12_ROOT_SIGNATURE_FLAG_NONE};
    ComPtr<ID3DBlob> serialized;
    ComPtr<ID3D12RootSignature> root;
    D3D12_INDIRECT_ARGUMENT_DESC argument{D3D12_INDIRECT_ARGUMENT_TYPE_DISPATCH};
    const D3D12_COMMAND_SIGNATURE_DESC signature_desc{sizeof(D3D12_DISPATCH_ARGUMENTS), 1, &argument, 0};
    ComPtr<ID3D12CommandSignature> signature;
    ComPtr<ID3D12InfoQueue> info;
    if (debug) check(device.As(&info), "get debug message queue");
    check(D3D12SerializeRootSignature(&desc, D3D_ROOT_SIGNATURE_VERSION_1, &serialized, nullptr), "serialize root");
    check(device->CreateRootSignature(0, serialized->GetBufferPointer(), serialized->GetBufferSize(), IID_PPV_ARGS(&root)), "create root");
    check(device->CreateCommandSignature(&signature_desc, nullptr, IID_PPV_ARGS(&signature)), "create command signature");
    const auto writer = pipeline(device.Get(), root.Get(), "write_args");
    const auto consumer = pipeline(device.Get(), root.Get(), "consume_args");
    if (!run(device.Get(), root.Get(), writer.Get(), consumer.Get(), signature.Get(), true) ||
        !run(device.Get(), root.Get(), writer.Get(), consumer.Get(), signature.Get(), false)) return 1;
    if (info) {
        for (UINT64 i = 0; i < info->GetNumStoredMessages(); ++i) {
            SIZE_T bytes = 0;
            check(info->GetMessage(i, nullptr, &bytes), "get debug message size");
            std::vector<char> storage(bytes);
            auto* message = reinterpret_cast<D3D12_MESSAGE*>(storage.data());
            check(info->GetMessage(i, message, &bytes), "get debug message");
            if (message->Severity <= D3D12_MESSAGE_SEVERITY_ERROR) {
                std::fprintf(stderr, "D3D12 debug message %u: %s\n", static_cast<unsigned>(message->ID), message->pDescription);
                return 1;
            }
        }
    }
    return 0;
}
catch (const std::exception&) {
    return 3;
}
