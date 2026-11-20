"""Conditional routes must not overrule an ordinary import path or apply to unknown binaries."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from dependency_paths import FFX_EXPORTS, FFX_LOADER, trace


def main():
    loader = "amd_fidelityfx_loader_xbox.dll"
    upscaler = "amd_fidelityfx_upscaler_xbox.dll"
    framegen = "amd_fidelityfx_framegeneration_xbox.dll"
    data = dict(images={n: {"sha256": "fixture", "exports": [{"name": s} for s in FFX_EXPORTS]}
                        for n in ("entry.exe", "bridge.dll", loader, upscaler)}, imports=[])
    data["images"][loader]["sha256"] = FFX_LOADER

    def edge(caller, target, kind="normal"):
        data["imports"].append(dict(image=caller, kind=kind, dll=target, symbol="ffxQuery",
                                    bundle_exports_in=[target], desktop_export="provider_not_found"))

    edge("entry.exe", loader)
    edge("entry.exe", upscaler, "delay")
    edge(loader, "bridge.dll")
    edge("bridge.dll", upscaler)
    edge(upscaler, "bridge.dll")
    report = trace(data, "entry.exe")
    assert report["reachable"][upscaler]["reasons"] == ("normal", "normal", "normal")
    finding, = report["findings"]
    assert finding["dll"] == framegen and finding["conditional"]
    data["images"][loader]["sha256"] = "other build"
    assert not trace(data, "entry.exe")["findings"]


if __name__ == "__main__":
    main()
