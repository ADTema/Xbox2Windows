#!/usr/bin/env python3
"""Render a static dark-theme SVG progress dashboard (stdlib only, no scripts/fonts/images).

render(data) -> str; see the self-test at the bottom for the expected `data` shape.
"""
import re
import sys
from xml.sax.saxutils import escape

W, PAD, GAP = 1000, 20, 16
BG, PANEL, BORDER, TEXT, MUTED = "#0d1117", "#161b22", "#30363d", "#e6edf3", "#8b949e"
DONE, TODO, TRACK = "#2ea043", "#484f58", "#30363d"
FONT, MONO = "Segoe UI,Helvetica,Arial,sans-serif", "Consolas,monospace"
CW = 6.2  # estimated px per char at 11px (scaled for other sizes below)


def esc(s):
    return escape(str(s), {'"': "&quot;"})


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def trunc(s, px, cw):
    n = int(px // cw)
    return s if len(s) <= n else (s[:n - 1] + "…" if n > 1 else "")


def text(x, y, s, size=12, fill=TEXT, anchor="start", extra=""):
    return (f'<text x="{fmt(x)}" y="{fmt(y)}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{extra}>{esc(s)}</text>')


def panel(x, y, w, h, title="", tx=12):
    r = (f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6" '
         f'fill="{PANEL}" stroke="{BORDER}"/>')
    return r + (text(x + tx, y + 21, title, 13, TEXT, extra=' font-weight="600"') if title else "")


def badge(x, y, b):
    lw, vw = len(b["label"]) * 6.3 + 14, len(b["value"]) * 6.3 + 14
    svg = (f'<rect x="{fmt(x)}" y="{y}" width="{fmt(lw)}" height="20" rx="3" fill="{TODO}"/>'
           f'<rect x="{fmt(x + lw - 3)}" y="{y}" width="{fmt(vw + 3)}" height="20" rx="3" fill="{esc(b["color"])}"/>'
           + text(x + lw / 2, y + 14, b["label"], 11, "#fff", "middle")
           + text(x + lw + vw / 2, y + 14, b["value"], 11, "#fff", "middle", ' font-weight="600"'))
    return svg, lw + vw + 8


def squarify(items, x, y, w, h):
    """Bruls et al. squarified treemap. items: [(key, value>0)] sorted desc -> {key: (x, y, w, h)}."""
    k = w * h / sum(v for _, v in items)
    areas, out = [(n, v * k) for n, v in items], {}

    def worst(row, side):
        s = sum(a for _, a in row)
        return max(max(side * side * a / (s * s), s * s / (side * side * a)) for _, a in row)

    while areas:
        side, n = min(w, h), 1
        while n < len(areas) and worst(areas[:n + 1], side) <= worst(areas[:n], side):
            n += 1
        row, areas = areas[:n], areas[n:]
        s = sum(a for _, a in row)
        if w >= h:  # lay the row out as a column on the left
            cw, yy = s / h, y
            for key, a in row:
                out[key] = (x, yy, cw, a / cw)
                yy += a / cw
            x, w = x + cw, w - cw
        else:  # ... or as a strip on top
            rh, xx = s / w, x
            for key, a in row:
                out[key] = (xx, y, a / rh, rh)
                xx += a / rh
            y, h = y + rh, h - rh
    return out


def group(name, done, total, gx, gy, gw, gh):
    """One treemap group: border rect, optional label strip, `total` square cells (first `done` green)."""
    def fit(wd, hd):  # largest integer cell size >= 2 (1px gap) holding `total` cells in wd x hd
        wd = int(wd)
        for s in range(int(min(wd, hd)), 1, -1):
            cols = (wd + 1) // (s + 1)
            if cols and -(-total // cols) * (s + 1) - 1 <= hd:
                return s, cols
    lab = f"{name} {done}/{total}"
    if len(lab) * CW > gw - 6:
        lab = trunc(name, gw - 6, CW)
    if len(lab) < 3 or not fit(gw - 4, gh - 18):
        lab = ""
    f = fit(gw - 4, gh - (18 if lab else 4))
    gap = 1 if f else 0
    s, cols = f or (1, max(int(gw - 4), 1))  # ponytail: s=1/no-gap fallback only if the rect is absurdly small
    step, oy = s + gap, 2 + (14 if lab else 0)

    def cells(lo, hi, color):
        r = "".join(f'<rect x="{2 + i % cols * step}" y="{oy + i // cols * step}" width="{s}" height="{s}"/>'
                    for i in range(lo, hi))
        return f'<g fill="{color}">{r}</g>' if r else ""
    return (f'<g class="grp" transform="translate({fmt(gx)},{fmt(gy)})">'
            f'<rect width="{fmt(gw)}" height="{fmt(gh)}" fill="{PANEL}" stroke="{BG}" stroke-width="2"/>'
            + (text(4, 13, lab, 11) if lab else "") + cells(0, done, DONE) + cells(done, total, TODO) + "</g>")


def treemap(tm, x, y, w, maph):
    h = 30 + maph + 10
    out = [f'<g class="tm">{panel(x, y, w, h, trunc(tm["title"], w - 24, 7.2))}']
    items = sorted(((k, v["total"]) for k, v in tm["groups"].items() if v["total"] > 0), key=lambda kv: -kv[1])
    for name, (rx, ry, rw, rh) in (squarify(items, x + 10, y + 30, w - 20, maph) if items else {}).items():
        x0, y0, x1, y1 = round(rx, 1), round(ry, 1), round(rx + rw, 1), round(ry + rh, 1)
        g = tm["groups"][name]
        out.append(group(name, min(g["done"], g["total"]), g["total"], x0, y0, round(x1 - x0, 1), round(y1 - y0, 1)))
    return "".join(out) + "</g>", h


def bars_height(b):
    return 34 + 20 * len(b["rows"]) + 8


def bars(b, x, y, w, h):
    legend = b.get("legend", [])
    lw = sum(len(i["text"]) * CW + 23 for i in legend)
    out, lx = [panel(x, y, w, h, trunc(b["title"], w - 24 - lw, 7.2))], x + w - 12
    for i in reversed(legend):
        tw = len(i["text"]) * CW
        out.append(f'<rect x="{fmt(lx - tw - 13)}" y="{y + 12}" width="9" height="9" rx="2" fill="{esc(i["color"])}"/>'
                   + text(lx - tw - 2, y + 21, i["text"], 11, MUTED))
        lx -= tw + 23
    rows = b["rows"]
    mx = max([sum(s["value"] for s in r["segments"]) for r in rows] + [1])
    tx = x + 12 + 158
    trw = max(w - 12 - 158 - 12 - 8 - max([len(r["text"]) for r in rows] + [0]) * 6.4, 10)
    for n, r in enumerate(rows):
        yy, sx = y + 34 + 20 * n, tx
        out.append(text(x + 12, yy + 14, trunc(r["label"], 150, 6.4), 12)
                   + f'<rect x="{fmt(tx)}" y="{yy + 5}" width="{fmt(trw)}" height="10" rx="2" fill="{TRACK}"/>')
        for sg in r["segments"]:
            sw = trw * sg["value"] / mx
            if sw > 0:
                out.append(f'<rect x="{fmt(sx)}" y="{yy + 5}" width="{fmt(sw)}" height="10" fill="{esc(sg["color"])}"/>')
                sx += sw
        out.append(text(x + w - 12, yy + 14, r["text"], 12, MUTED, "end"))
    return "".join(out)


def list_lines(lst, w):
    maxc = max(int((w - 24 - 12) / 6.6), 8)
    lines = []
    for k, items in lst["items"].items():
        lines.append((0, f"{k} ({len(items)})"))
        cur = ""
        for it in items:
            tok = it + ","
            if cur and len(cur) + 1 + len(tok) > maxc:
                lines.append((1, cur))
                cur = tok
            else:
                cur = f"{cur} {tok}".strip()
        if cur:
            lines.append((1, cur.rstrip(",")))
    return lines


def lists(lst, lines, x, y, w, h):
    out = [panel(x, y, w, h, lst["title"])]
    for n, (ind, s) in enumerate(lines):
        out.append(text(x + 12 + 12 * ind, y + 44 + 14 * n, s, 11, MUTED if ind else TEXT,
                        extra=f' font-family="{MONO}"' + ("" if ind else ' font-weight="bold"')))
    return "".join(out)


def render(data):
    inner, parts = W - 2 * PAD, []
    y = PAD + 20
    parts.append(text(PAD, y, data["title"], 22, extra=' font-weight="600"'))
    parts.append(text(PAD, y + 22, trunc(data.get("subtitle", ""), inner, 6.4), 12, MUTED))
    x, y = PAD, y + 36
    for b in data.get("badges", []):
        svg, bw = badge(x, y, b)
        parts.append(svg)
        x += bw
    y += 36
    tms = data.get("treemaps", [])
    for row in ([tms[:1]] + [tms[i:i + 2] for i in range(1, len(tms), 2)]) if tms else []:
        w = (inner - GAP * (len(row) - 1)) / len(row)
        for n, tm in enumerate(row):
            svg, h = treemap(tm, PAD + n * (w + GAP), y, w, 260 if len(row) == 1 else 300)
            parts.append(svg)
        y += h + GAP
    bs = data.get("bars", [])
    if bs:
        w, h = (inner - GAP * (len(bs) - 1)) / len(bs), max(bars_height(b) for b in bs)
        parts += [bars(b, PAD + n * (w + GAP), y, w, h) for n, b in enumerate(bs)]
        y += h + GAP
    ls = data.get("lists", [])
    if ls:
        w = (inner - GAP * (len(ls) - 1)) / len(ls)
        lines = [list_lines(l, w) for l in ls]
        h = 34 + 14 * max(len(x) for x in lines) + 10
        parts += [lists(l, lines[n], PAD + n * (w + GAP), y, w, h) for n, l in enumerate(ls)]
        y += h + GAP
    parts.append(text(PAD, y + 4, data.get("footer", ""), 11, MUTED))
    H = y + 20
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}" role="img"><title>{esc(data["title"])}</title>'
            f'<rect width="{W}" height="{H}" fill="{BG}"/>' + "".join(parts) + "</svg>\n")


def _selftest(data, svg):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(svg)
    q = lambda t: "{http://www.w3.org/2000/svg}" + t
    tms = [g for g in root.iter(q("g")) if g.get("class") == "tm"]
    assert len(tms) == len(data["treemaps"])
    for g, tm in zip(tms, data["treemaps"]):
        px, py, pw, ph = (float(g[0].get(k)) for k in ("x", "y", "width", "height"))
        boxes, done, todo = [], 0, 0
        for grp in g.findall(q("g")):
            tx, ty = map(float, re.match(r"translate\(([\d.]+),([\d.]+)\)", grp.get("transform")).groups())
            gw, gh = float(grp[0].get("width")), float(grp[0].get("height"))
            assert px - .05 <= tx and tx + gw <= px + pw + .05 and py - .05 <= ty and ty + gh <= py + ph + .05
            boxes.append((tx, ty, tx + gw, ty + gh))
            for cg in grp.findall(q("g")):
                for r in cg:
                    assert float(r.get("x")) + float(r.get("width")) <= gw and float(r.get("y")) + float(r.get("height")) <= gh
                    done, todo = (done + 1, todo) if cg.get("fill") == DONE else (done, todo + 1)
        gs = [v for v in tm["groups"].values() if v["total"] > 0]
        assert done == sum(min(v["done"], v["total"]) for v in gs), (done, tm["title"])
        assert done + todo == sum(v["total"] for v in gs), (done + todo, tm["title"])
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                assert a[2] <= b[0] + .05 or b[2] <= a[0] + .05 or a[3] <= b[1] + .05 or b[3] <= a[1] + .05, (a, b)


if __name__ == "__main__":
    def g(d):
        return {k: {"done": v[0], "total": v[1]} for k, v in d.items()}
    gfx = g({"VOP3": (40, 424), "DPP8": (0, 254), "SDWA": (0, 220), "VOPC": (30, 190), "FLAT": (10, 130),
             "MIMG": (0, 111), "DPP16": (0, 101), "SMEM": (20, 81), "VOP1": (25, 78), "MUBUF": (12, 70),
             "SOP1": (30, 65), "SOP2": (35, 51), "VOP2": (30, 50), "VOP3P": (0, 29), "SOPP": (20, 28),
             "SOPK": (5, 27), "SOPC": (10, 18), "MTBUF": (0, 16), "VINTRP": (0, 3), "EXP": (1, 1), "Empty": (0, 0)})
    x64 = g({"AVX": (2, 256), "Integer": (30, 191), "x87": (0, 100), "SSE3-4": (3, 86), "SSE": (0, 69),
             "SSE2": (0, 64), "FMA": (0, 60), "MMX": (0, 48), "AVX2": (0, 28), "Crypto": (0, 21),
             "BMI/ADX": (0, 16), "XSAVE": (0, 9)})
    sys_ = g({"File": (30, 60), "Memory": (20, 45), "Thread": (10, 38), "Sync": (30, 30), "Time": (0, 12), "Misc": (1, 9)})
    tdone = lambda d: sum(v["done"] for v in d.values())
    ttot = lambda d: sum(v["total"] for v in d.values())
    pct = lambda d: f"{100 * tdone(d) / ttot(d):.1f}% ({tdone(d)}/{ttot(d)})"
    data = {
        "title": "Xbox2Windows progress",
        "subtitle": "Counted from code and test results, not estimated. Percentages are of the cases we know about.",
        "badges": [{"label": "tests", "value": "70/75 pass", "color": "#2ea043"},
                   {"label": "x64 lifted", "value": pct(x64), "color": "#d29922"},
                   {"label": "gfx1013", "value": pct(gfx), "color": "#d29922"},
                   {"label": "throw sites", "value": "18", "color": "#f85149"}],
        "treemaps": [{"title": f"gfx1013 instruction forms translated: {pct(gfx)}", "groups": gfx},
                     {"title": f"x64 (Zen 2) instruction kinds lifted: {pct(x64)}", "groups": x64},
                     {"title": f"Kernel services implemented: {pct(sys_)}", "groups": sys_}],
        "bars": [{"title": "Tests by area",
                  "rows": [{"label": a, "segments": [{"value": p, "color": "#2ea043"}, {"value": s, "color": "#d29922"},
                                                     {"value": f, "color": "#f85149"}], "text": f"{p}/{p + s + f}"}
                           for a, p, s, f in (("CPU", 13, 0, 0), ("GPU shader", 20, 2, 3), ("Kernel", 25, 1, 1), ("A very long area label here", 6, 0, 1))],
                  "legend": [{"text": "pass", "color": "#2ea043"}, {"text": "skip", "color": "#d29922"},
                             {"text": "fail", "color": "#f85149"}]},
                 {"title": "Unsupported-instruction throw sites (18)",
                  "rows": [{"label": n, "segments": [{"value": v, "color": "#d29922"}], "text": str(v)}
                           for n, v in (("pixel_aot.py", 6), ("cpu_leaf_aot.py", 5), ("ffx_dispatch_aot.py", 4), ("bink_heap_aot.py", 3))]}],
        "lists": [{"title": "Forms in our fixtures not yet translated",
                   "items": {"x64": ["jne", "ud2", "vpermilps", "vfmadd231ps", "cmpxchg16b", "rdtscp", "xgetbv", "pdep", "pext", "aesenc", "pclmulqdq"],
                             "gfx1013": ["buffer_load_dwordx4", "image_sample_c_lz", "ds_swizzle_b32", "v_pk_fma_f16", "s_waitcnt_vscnt", "global_atomic_add_f32", "v_dot2_f32_f16", "image_gather4_lz", "flat_atomic_swap"]}},
                  {"title": "Sample second list", "items": {"misc": ["one", "two"]}}],
        "footer": "Generated by tools/progress.py at commit abc1234 on 2026-11-21",
    }
    out = render(data)
    _selftest(data, out)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(out)
    print("progress_svg self-test passed", len(out.encode("utf-8")), "bytes")
