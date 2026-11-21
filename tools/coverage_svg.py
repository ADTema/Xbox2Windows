"""Draw the result of tools/form_coverage.py as a static SVG (one square per reference form).

Usage:
    python tools/form_coverage.py out/test-results.xml --json out/coverage.json
    python tools/coverage_svg.py out/coverage.json docs/coverage/dashboard.svg --source "<commit, OS, adapter>"

Green squares are covered forms, amber squares are forms held back only by skipped tests, and grey
squares are forms no passing fixture translates. Counts only; the graphic never shows a percentage,
since instruction-form coverage is not a measure of port completion. Python standard library only.
"""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

AREAS = (("x64_zen2", "x64 (Zen 2 user-mode mnemonics)", 220), ("gfx1013", "gfx1013 forms", 300),
         ("gfx1030", "gfx1030 (RDNA2) forms", 300))
WIDTH, BG, PANEL, BORDER, TEXT, MUTED = 1000, "#0d1117", "#161b22", "#30363d", "#e6edf3", "#8b949e"
COVERED, HELD, OPEN = "#2ea043", "#d29922", "#484f58"
NOTE = "Instruction-form coverage of source-built fixtures; not a measure of port completion."


def text(x, y, s, size=12, fill=TEXT, bold=False):
    weight = ' font-weight="600"' if bold else ""
    return f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}"{weight}>{escape(s)}</text>'


def squarify(items, x, y, w, h):
    """Squarified treemap (Bruls et al.): [(key, size)] largest first -> {key: (x, y, w, h)}."""
    scale = w * h / sum(size for _, size in items)
    areas, out = [(key, size * scale) for key, size in items], {}

    def worst(row, side):
        s = sum(a for _, a in row)
        return max(max(side * side * a / (s * s), s * s / (side * side * a)) for _, a in row)

    while areas:
        side, n = min(w, h), 1
        while n < len(areas) and worst(areas[:n + 1], side) <= worst(areas[:n], side):
            n += 1
        row, areas = areas[:n], areas[n:]
        s = sum(a for _, a in row)
        if w >= h:
            cw, yy = s / h, y
            for key, a in row:
                out[key] = (x, yy, cw, a / cw)
                yy += a / cw
            x, w = x + cw, w - cw
        else:
            rh, xx = s / w, x
            for key, a in row:
                out[key] = (xx, y, a / rh, rh)
                xx += a / rh
            y, h = y + rh, h - rh
    return out


def group(name, counts, x, y, w, h):
    """A labelled box of squares: covered, then held back, then open."""
    covered, held, total = counts
    label = f"{name} {covered}/{total}"
    room = h - 18 if len(label) * 6.2 < w - 6 else h - 4
    for size in range(int(min(w, room)) - 4, 1, -1):  # largest square size that fits every form
        cols = int(w - 3) // (size + 1)
        if cols and -(-total // cols) * (size + 1) - 1 <= room - 4:
            break
    else:
        size, cols = 1, max(int(w - 4), 1)  # ponytail: overlapping 1px squares only in a degenerate box
    top = 2 + (h - room)
    parts = [f'<g transform="translate({x:.1f},{y:.1f})"><rect width="{w:.1f}" height="{h:.1f}" '
             f'fill="{PANEL}" stroke="{BG}" stroke-width="2"/>']
    if room < h:
        parts.append(text(4, 13, label, 11))
    for color, first, last in ((COVERED, 0, covered), (HELD, covered, covered + held), (OPEN, covered + held, total)):
        cells = "".join(f'<rect x="{2 + i % cols * (size + 1)}" y="{top + i // cols * (size + 1)}" '
                        f'width="{size}" height="{size}"/>' for i in range(first, last))
        parts.append(f'<g fill="{color}">{cells}</g>')
    return "".join(parts) + "</g>"


def render(m, source):
    rows = [text(20, 34, "Instruction-form coverage", 20, bold=True), text(20, 56, NOTE, 12, MUTED),
            text(20, 74, f"Measured on {source}. Green: covered. Amber: held back by skipped tests. "
                         "Grey: not covered.", 12, MUTED)]
    y = 92
    for key, label, height in AREAS:
        r = m[key]
        held = {}
        for form in r["blocked_by_skip"]:
            held[form.split()[0]] = held.get(form.split()[0], 0) + 1
        title = (f"{label}: {r['covered']} of {r['total']} covered, "
                 f"{len(r['blocked_by_skip'])} held back by skips")
        rows.append(f'<rect x="20" y="{y}" width="{WIDTH - 40}" height="{height + 40}" rx="6" '
                    f'fill="{PANEL}" stroke="{BORDER}"/>' + text(32, y + 21, title, 13, bold=True))
        items = sorted(((g, v["total"]) for g, v in r["groups"].items() if v["total"]), key=lambda kv: -kv[1])
        for name, (gx, gy, gw, gh) in squarify(items, 30, y + 30, WIDTH - 60, height).items():
            g = r["groups"][name]
            rows.append(group(name, (g["covered"], held.get(name, 0), g["total"]), gx, gy, gw, gh))
        y += height + 56
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{y - 6}" '
            f'viewBox="0 0 {WIDTH} {y - 6}" font-family="Segoe UI,Helvetica,Arial,sans-serif">'
            f'<rect width="{WIDTH}" height="{y - 6}" fill="{BG}"/>' + "".join(rows) + "</svg>\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("coverage", type=Path, help="JSON written by form_coverage.py --json")
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", required=True, help="commit, OS build and adapter of the measured run")
    args = parser.parse_args()
    svg = render(json.loads(args.coverage.read_text(encoding="utf-8")), args.source)
    args.output.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
