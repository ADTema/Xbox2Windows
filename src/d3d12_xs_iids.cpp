// Standard D3D12 and DXGI interface identifiers exported by the console
// d3d12_xs.dll.  Games resolve these by name for QueryInterface and device
// creation.  All values are defined in the public Windows SDK headers
// (d3d12.h, dxgi.h, dxgi1_2.h).  initguid.h emits the GUID definitions
// so each symbol has storage in this translation unit.
#include <initguid.h>
#include <d3d12.h>
#include <dxgi1_6.h>
