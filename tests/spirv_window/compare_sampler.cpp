// D3D12 readback for the #670 comparison-sampler fixture (tests/spirv_window/shared_sampler.spvasm).
// t0 holds depth texels, t1 ordinary texels. s2 is a point-clamp LESS_EQUAL comparison sampler and
// the ordinary point-clamp sampler goes to the register the lowering pass was given. Outputs land
// in a raw UAV at u4; every word of it, including the 13 guards, is compared with the reference.
#include "../desktop_gpu.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;

namespace {
constexpr UINT comparison_register = 2;
constexpr UINT output_words = 16;
constexpr UINT guard = 0xc5c5c5c5u;

std::vector<char> read_file(const char* path, const char* what)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error(std::string("Cannot open ") + what + ": " + path);
    return {std::istreambuf_iterator<char>(file), {}};
}
}

void check_spirv_compare_sampler(ID3D12Device* device, const char* shader_path, const char* ordinary_register,
                                 const char* reference_path)
{
    char* end = nullptr;
    const unsigned long ordinary = std::strtoul(ordinary_register, &end, 10);
    if (!*ordinary_register || *end || ordinary == comparison_register || ordinary > 15)
        throw std::runtime_error("Ordinary sampler register must be 0-15 and differ from s2");
    const auto shader = read_file(shader_path, "comparison-sampler shader");
    const auto reference_bytes = read_file(reference_path, "comparison-sampler reference");
    if (reference_bytes.size() != output_words * sizeof(UINT))
        throw std::runtime_error("Comparison-sampler reference must hold 16 words");
    std::array<UINT, output_words> expected;
    std::memcpy(expected.data(), reference_bytes.data(), sizeof(expected));

    D3D12_DESCRIPTOR_RANGE textures{D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 2, 0, 0, 0};
    D3D12_ROOT_PARAMETER parameters[2]{};
    parameters[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    parameters[0].DescriptorTable = {1, &textures};
    parameters[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_UAV;
    parameters[1].Descriptor = {4, 0};
    D3D12_STATIC_SAMPLER_DESC samplers[2]{};
    for (UINT i = 0; i < 2; ++i) {
        auto& s = samplers[i];
        const bool comparison = i == 0;
        s.Filter = comparison ? D3D12_FILTER_COMPARISON_MIN_MAG_MIP_POINT : D3D12_FILTER_MIN_MAG_MIP_POINT;
        s.AddressU = s.AddressV = s.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
        s.MaxAnisotropy = 1;
        s.ComparisonFunc = comparison ? D3D12_COMPARISON_FUNC_LESS_EQUAL : D3D12_COMPARISON_FUNC_ALWAYS;
        s.MaxLOD = D3D12_FLOAT32_MAX;
        s.ShaderRegister = comparison ? comparison_register : static_cast<UINT>(ordinary);
    }
    D3D12_ROOT_SIGNATURE_DESC root_desc{2, parameters, 2, samplers, D3D12_ROOT_SIGNATURE_FLAG_NONE};
    ComPtr<ID3DBlob> root_bytes, error;
    check(D3D12SerializeRootSignature(&root_desc, D3D_ROOT_SIGNATURE_VERSION_1, &root_bytes, &error),
          "Serialize comparison-sampler root signature");
    ComPtr<ID3D12RootSignature> root;
    check(device->CreateRootSignature(0, root_bytes->GetBufferPointer(), root_bytes->GetBufferSize(),
                                      IID_PPV_ARGS(&root)), "Create comparison-sampler root signature");
    D3D12_COMPUTE_PIPELINE_STATE_DESC pso{};
    pso.pRootSignature = root.Get();
    pso.CS = {shader.data(), shader.size()};
    ComPtr<ID3D12PipelineState> pipeline;
    check(device->CreateComputePipelineState(&pso, IID_PPV_ARGS(&pipeline)), "Create comparison-sampler pipeline");

    // 2x2 R32_FLOAT textures. UV (0.25, 0.25) with point sampling selects the top-left texel:
    // depth 0.5 (compared with 0.25 and 0.75) and ordinary value 0.375.
    constexpr UINT row_pitch = D3D12_TEXTURE_DATA_PITCH_ALIGNMENT;
    constexpr UINT texture_bytes = 2 * row_pitch;
    const float texels[2][2][2] = {{{0.5f, 0.75f}, {0.25f, 1.0f}}, {{0.375f, 0.875f}, {0.625f, 0.125f}}};
    std::array<UINT, output_words> initial;
    initial.fill(guard);
    auto upload = make_buffer(device, 2 * texture_bytes + sizeof(initial), D3D12_HEAP_TYPE_UPLOAD,
                              D3D12_RESOURCE_STATE_GENERIC_READ);
    auto output = make_buffer(device, sizeof(initial), D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON,
                              D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    auto readback = make_buffer(device, sizeof(initial), D3D12_HEAP_TYPE_READBACK, D3D12_RESOURCE_STATE_COPY_DEST);
    D3D12_RANGE empty{};
    BYTE* mapped = nullptr;
    check(upload->Map(0, &empty, reinterpret_cast<void**>(&mapped)), "Map comparison-sampler upload");
    for (UINT i = 0; i < 2; ++i)
        for (UINT row = 0; row < 2; ++row)
            std::memcpy(mapped + i * texture_bytes + row * row_pitch, texels[i][row], sizeof(texels[i][row]));
    std::memcpy(mapped + 2 * texture_bytes, initial.data(), sizeof(initial));
    upload->Unmap(0, nullptr);

    D3D12_DESCRIPTOR_HEAP_DESC heap_desc{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, 2,
                                         D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE};
    ComPtr<ID3D12DescriptorHeap> heap;
    check(device->CreateDescriptorHeap(&heap_desc, IID_PPV_ARGS(&heap)), "Create comparison-sampler descriptors");
    auto cpu = heap->GetCPUDescriptorHandleForHeapStart();
    const UINT stride = device->GetDescriptorHandleIncrementSize(heap_desc.Type);

    ComputeCommands commands(device, pipeline.Get());
    auto& list = commands.list;
    D3D12_RESOURCE_DESC texture_desc{};
    texture_desc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    texture_desc.Width = texture_desc.Height = 2;
    texture_desc.DepthOrArraySize = texture_desc.MipLevels = 1;
    texture_desc.Format = DXGI_FORMAT_R32_FLOAT;
    texture_desc.SampleDesc.Count = 1;
    std::array<ComPtr<ID3D12Resource>, 2> inputs;
    for (UINT i = 0; i < 2; ++i) {
        inputs[i] = resource(device, texture_desc, D3D12_HEAP_TYPE_DEFAULT, D3D12_RESOURCE_STATE_COMMON);
        transition(list.Get(), inputs[i].Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
        D3D12_TEXTURE_COPY_LOCATION to{};
        to.pResource = inputs[i].Get();
        to.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        D3D12_TEXTURE_COPY_LOCATION from{};
        from.pResource = upload.Get();
        from.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        from.PlacedFootprint = {i * texture_bytes, {DXGI_FORMAT_R32_FLOAT, 2, 2, 1, row_pitch}};
        list->CopyTextureRegion(&to, 0, 0, 0, &from, nullptr);
        transition(list.Get(), inputs[i].Get(), D3D12_RESOURCE_STATE_COPY_DEST,
                   D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE);
        device->CreateShaderResourceView(inputs[i].Get(), nullptr, cpu);
        cpu.ptr += stride;
    }
    transition(list.Get(), output.Get(), D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_DEST);
    list->CopyBufferRegion(output.Get(), 0, upload.Get(), 2 * texture_bytes, sizeof(initial));
    transition(list.Get(), output.Get(), D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_STATE_UNORDERED_ACCESS);
    ID3D12DescriptorHeap* heaps[] = {heap.Get()};
    list->SetDescriptorHeaps(1, heaps);
    list->SetComputeRootSignature(root.Get());
    list->SetComputeRootDescriptorTable(0, heap->GetGPUDescriptorHandleForHeapStart());
    list->SetComputeRootUnorderedAccessView(1, output->GetGPUVirtualAddress());
    list->Dispatch(1, 1, 1);
    transition(list.Get(), output.Get(), D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_STATE_COPY_SOURCE);
    list->CopyBufferRegion(readback.Get(), 0, output.Get(), 0, sizeof(initial));
    commands.submit_and_wait(device);

    D3D12_RANGE read{0, sizeof(initial)};
    check(readback->Map(0, &read, reinterpret_cast<void**>(&mapped)), "Map comparison-sampler readback");
    std::array<UINT, output_words> actual;
    std::memcpy(actual.data(), mapped, sizeof(actual));
    readback->Unmap(0, &empty);
    UINT mismatches = 0;
    for (UINT i = 0; i < output_words; ++i) {
        if (actual[i] == expected[i]) continue;
        std::fprintf(stderr, "word=%u expected=%08x actual=%08x\n", i, expected[i], actual[i]);
        ++mismatches;
    }
    std::printf("outputs=%08x,%08x,%08x sampler_registers=s%u,s%lu compared_words=%u mismatches=%u\n",
                actual[0], actual[1], actual[2], comparison_register, ordinary, output_words, mismatches);
    if (mismatches) throw std::runtime_error("Comparison-sampler readback differs from CPU reference");
}
