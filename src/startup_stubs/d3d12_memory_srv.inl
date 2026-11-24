// Included after the resource creation and descriptor handlers.
struct MemoryShaderResourceView {
    D3D12_SHADER_RESOURCE_VIEW_DESC view;
    u64 address;
};
static_assert(offsetof(MemoryShaderResourceView, address) == 0x28);

bool same_texture_description(const D3D12_RESOURCE_DESC& a, const D3D12_RESOURCE_DESC& b)
{
    return a.Dimension == b.Dimension && a.Alignment == b.Alignment && a.Width == b.Width &&
           a.Height == b.Height && a.DepthOrArraySize == b.DepthOrArraySize && a.MipLevels == b.MipLevels &&
           a.Format == b.Format && a.SampleDesc.Count == b.SampleDesc.Count &&
           a.SampleDesc.Quality == b.SampleDesc.Quality && a.Layout == b.Layout && a.Flags == b.Flags;
}

bool supports_memory_srv(const D3D12_RESOURCE_DESC& r, const D3D12_SHADER_RESOURCE_VIEW_DESC& v)
{
    return r.Dimension == D3D12_RESOURCE_DIMENSION_TEXTURE2D && r.Width && r.Height &&
           r.DepthOrArraySize == 1 && r.MipLevels == 1 && r.SampleDesc.Count == 1 && r.SampleDesc.Quality == 0 &&
           r.Format == DXGI_FORMAT_R8_UNORM && v.Format == r.Format && !(r.Flags & D3D12_RESOURCE_FLAG_DENY_SHADER_RESOURCE) &&
           v.ViewDimension == D3D12_SRV_DIMENSION_TEXTURE2D &&
           v.Shader4ComponentMapping == D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING &&
           v.Texture2D.MostDetailedMip == 0 && v.Texture2D.MipLevels == 1 && v.Texture2D.PlaneSlice == 0 &&
           v.Texture2D.ResourceMinLODClamp == 0.0f;
}

bool memory_srv_destination(u64 handle)
{
    bool valid = false;
    AcquireSRWLockShared(&note_lock);
    for (const auto& heap : heap_infos()) {
        if (heap.type != D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV || !heap.increment) continue;
        const u64 base = heap.title_cpu ? heap.title_cpu : heap.desktop_cpu;
        if (handle >= base && (handle - base) % heap.increment == 0 &&
            (handle - base) / heap.increment < heap.count) {
            valid = true;
            break;
        }
    }
    ReleaseSRWLockShared(&note_lock);
    return valid;
}

Wrapper* existing_memory_texture(u64 address, const D3D12_RESOURCE_DESC& desc)
{
    Wrapper* match = nullptr;
    AcquireSRWLockShared(&note_lock);
    for (const auto& [wrapper, info] : resource_infos()) {
        if (reinterpret_cast<u64>(wrapper->own().title_memory) != address ||
            InterlockedCompareExchange(&wrapper->own().refs, 0, 0) <= 0 ||
            !same_texture_description(desc, info.console)) continue;
        if (match) {
            match = nullptr;
            break;
        }
        match = const_cast<Wrapper*>(wrapper);
    }
    ReleaseSRWLockShared(&note_lock);
    return match;
}

void __stdcall device_memory_srv(Wrapper* self, const D3D12_RESOURCE_DESC* resource,
                                 const MemoryShaderResourceView* input, u64 destination)
{
    static LONG refused;
    if (!destination || !x2w_local::readable(resource, sizeof(*resource)) ||
        !x2w_local::readable(input, sizeof(*input)) || !input->address ||
        !supports_memory_srv(*resource, input->view) || !memory_srv_destination(destination)) {
        if (first_calls(refused, 8)) log("x2w-d3d12 Device::slot70 unsupported memory SRV arguments");
        return;
    }
    Wrapper* texture = existing_memory_texture(input->address, *resource);
    if (!texture) {
        if (first_calls(refused, 8)) log("x2w-d3d12 Device::slot70 no unique registered texture at the supplied base and layout");
        return;
    }
    view_slot<18, 2>(self, reinterpret_cast<u64>(texture), reinterpret_cast<u64>(&input->view), destination, 0);
}
