// Experimental (docs/startup-runtime.md#input-script): fills the presented-picture signature
// (present_signature.h) from the console present of the D3D12 stand-in.
//
// Every `every` presents it copies the 18 sampled rows of the presented surface (one texel high
// each, never the whole surface) into a small readback buffer on the presenting queue and signals
// a fence. It never waits: a later call publishes the rows once the fence has passed, and no new
// copy starts while one is in flight. The surface rests in COMMON before and after.
#pragma once

#include "startup_stubs/present_signature.h"
#include "startup_stubs/present_view_format.h"

#include <d3d12.h>

#include <initializer_list>

namespace x2w_present_signature {

// Layout of the 4-byte colour formats the signature reads; false for any other format.
inline bool layout_of(DXGI_FORMAT format, Layout& layout)
{
    switch (x2w_startup::present_view_format(format)) {
    case DXGI_FORMAT_R8G8B8A8_UNORM:
    case DXGI_FORMAT_R8G8B8A8_UNORM_SRGB: layout = Layout::rgba8; return true;
    case DXGI_FORMAT_B8G8R8A8_UNORM:
    case DXGI_FORMAT_B8G8R8A8_UNORM_SRGB:
    case DXGI_FORMAT_B8G8R8X8_UNORM:
    case DXGI_FORMAT_B8G8R8X8_UNORM_SRGB: layout = Layout::bgra8; return true;
    case DXGI_FORMAT_R10G10B10A2_UNORM: layout = Layout::rgb10a2; return true;
    default: return false;
    }
}

class Sampler {
public:
    explicit Sampler(int every) : every_(every) {}

    // Called once per present with the presented surface. Returns true when this call published a sample.
    bool present(ID3D12Device* device, ID3D12CommandQueue* queue, ID3D12Resource* surface, LONG64 present_number, Block* block)
    {
        bool published = false;
        if (in_flight_ && fence_->GetCompletedValue() >= fence_value_) {
            in_flight_ = false;
            void* mapped = nullptr;
            const D3D12_RANGE range{0, static_cast<SIZE_T>(row_stride_ * cells_y)};
            if (SUCCEEDED(readback_->Map(0, &range, &mapped))) {
                std::uint8_t luma[cells];
                for (int band = 0; band < cells_y; ++band)
                    reduce_row(static_cast<const unsigned char*>(mapped) + row_stride_ * band, width_, layout_, luma + band * cells_x);
                const D3D12_RANGE none{0, 0};
                readback_->Unmap(0, &none);
                if (block) publish(block, luma, copied_present_);
                published = true;
            }
        }
        if (block) note_present(block, present_number);
        if (every_ <= 0 || failed_ || !device || !queue || !surface) return published;
        if ((counter_++ % every_) != 0 || in_flight_) return published;
        const D3D12_RESOURCE_DESC desc = surface->GetDesc();
        Layout layout;
        if (!x2w_startup::present_surface_supported(desc) || !layout_of(desc.Format, layout) || desc.Width > 16384) {
            unsupported_ = desc.Format;
            return published;
        }
        const auto width = static_cast<UINT>(desc.Width);
        const UINT64 pitch = (UINT64{width} * 4 + D3D12_TEXTURE_DATA_PITCH_ALIGNMENT - 1) & ~UINT64{D3D12_TEXTURE_DATA_PITCH_ALIGNMENT - 1};
        const UINT64 stride = (pitch + D3D12_TEXTURE_DATA_PLACEMENT_ALIGNMENT - 1) & ~UINT64{D3D12_TEXTURE_DATA_PLACEMENT_ALIGNMENT - 1};
        if (!setup(device, stride * cells_y)) return published;
        if (FAILED(allocator_->Reset()) || FAILED(list_->Reset(allocator_, nullptr))) {
            failed_ = true;
            return published;
        }
        barrier(surface, D3D12_RESOURCE_STATE_COMMON, D3D12_RESOURCE_STATE_COPY_SOURCE);
        D3D12_TEXTURE_COPY_LOCATION from{};
        from.pResource = surface;
        from.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        for (int band = 0; band < cells_y; ++band) {
            const UINT y = sampled_row(band, desc.Height);
            D3D12_TEXTURE_COPY_LOCATION to{};
            to.pResource = readback_;
            to.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
            to.PlacedFootprint.Offset = stride * band;
            to.PlacedFootprint.Footprint = {desc.Format, width, 1, 1, static_cast<UINT>(pitch)};
            const D3D12_BOX box{0, y, 0, width, y + 1, 1};
            list_->CopyTextureRegion(&to, 0, 0, 0, &from, &box);
        }
        barrier(surface, D3D12_RESOURCE_STATE_COPY_SOURCE, D3D12_RESOURCE_STATE_COMMON);
        if (FAILED(list_->Close())) {
            failed_ = true;
            return published;
        }
        ID3D12CommandList* lists[] = {list_};
        queue->ExecuteCommandLists(1, lists);
        if (FAILED(queue->Signal(fence_, ++fence_value_))) {
            failed_ = true;
            return published;
        }
        in_flight_ = true;
        layout_ = layout;
        width_ = width;
        row_stride_ = stride;
        copied_present_ = present_number;
        return published;
    }

    bool failed() const { return failed_; }
    DXGI_FORMAT unsupported_format() const { return unsupported_; }
    bool in_flight() const { return in_flight_; }

    ~Sampler()
    {
        for (IUnknown* object : {static_cast<IUnknown*>(readback_), static_cast<IUnknown*>(fence_),
                                 static_cast<IUnknown*>(list_), static_cast<IUnknown*>(allocator_)})
            if (object) object->Release();
    }

private:
    bool setup(ID3D12Device* device, UINT64 bytes)
    {
        HRESULT hr = S_OK;
        if (!allocator_) {
            hr = device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&allocator_));
            if (SUCCEEDED(hr)) hr = device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, allocator_, nullptr, IID_PPV_ARGS(&list_));
            if (SUCCEEDED(hr)) hr = list_->Close();
            if (SUCCEEDED(hr)) hr = device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence_));
        }
        if (SUCCEEDED(hr) && readback_bytes_ < bytes) {
            if (readback_) readback_->Release();
            readback_ = nullptr;
            readback_bytes_ = 0;
            D3D12_HEAP_PROPERTIES heap{};
            heap.Type = D3D12_HEAP_TYPE_READBACK;
            D3D12_RESOURCE_DESC buffer{};
            buffer.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
            buffer.Width = bytes;
            buffer.Height = 1;
            buffer.DepthOrArraySize = 1;
            buffer.MipLevels = 1;
            buffer.SampleDesc.Count = 1;
            buffer.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
            hr = device->CreateCommittedResource(&heap, D3D12_HEAP_FLAG_NONE, &buffer, D3D12_RESOURCE_STATE_COPY_DEST, nullptr,
                                                 IID_PPV_ARGS(&readback_));
            if (SUCCEEDED(hr)) readback_bytes_ = bytes;
        }
        if (FAILED(hr)) failed_ = true;
        return SUCCEEDED(hr);
    }
    void barrier(ID3D12Resource* resource, D3D12_RESOURCE_STATES from, D3D12_RESOURCE_STATES to)
    {
        D3D12_RESOURCE_BARRIER b{};
        b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        b.Transition.pResource = resource;
        b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        b.Transition.StateBefore = from;
        b.Transition.StateAfter = to;
        list_->ResourceBarrier(1, &b);
    }

    int every_;
    LONG64 counter_ = 0, copied_present_ = 0;
    ID3D12CommandAllocator* allocator_ = nullptr;
    ID3D12GraphicsCommandList* list_ = nullptr;
    ID3D12Fence* fence_ = nullptr;
    ID3D12Resource* readback_ = nullptr;
    UINT64 readback_bytes_ = 0, fence_value_ = 0, row_stride_ = 0;
    UINT width_ = 0;
    Layout layout_ = Layout::rgba8;
    DXGI_FORMAT unsupported_ = DXGI_FORMAT_UNKNOWN;
    bool in_flight_ = false, failed_ = false;
};

}  // namespace x2w_present_signature
