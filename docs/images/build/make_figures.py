"""IKEA-style line drawings for the PRATICO 3 build guide.

All geometry comes from hardware/pratico3/cad/pratico3_enclosure.py (mm, X = left->right seen
from the user, Y = front->back, Z = up). Parts are simplified to boxes and cylinders and drawn as
white shapes with black outlines (orthographic view, painter's order).

    python make_figures.py      -> build_*.svg next to this file (no dependencies)
"""
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INK = "#1d1d1d"
FONT = "Helvetica, Arial, sans-serif"
# fills per tone: (z face, y face, x face)
SH = {0: ("#ffffff", "#f1f1f1", "#e1e1e1"),
      1: ("#e2e2e2", "#d3d3d3", "#c4c4c4"),
      2: ("#7d7d7d", "#6c6c6c", "#5e5e5e"),
      3: ("#b9c4c4", "#aab5b5", "#9ca6a6")}       # glass
HOLE = "#4a4a4a"
_ids = [0]


def uid(p="c"):
    _ids[0] += 1
    return f"{p}{_ids[0]}"


# ----------------------------------------------------------------------------- geometry (CAD)
W = F = 1.6
OUT_X, OUT_Y, Z_TOP, Z_LIDB = 84.8, 59.7, 44.0, 42.4
Z_BLK, SEAT_Z, BEAM_Z = 2.8, 14.0, 24.0
WCX, WCY, WH = 37.6, 11.6, 6.5
LED_FACE, SEN_FACE, COLLAR_H, Z_COLLAR = 29.5, 47.1, 8.1, 50.0
BLK_X0 = 17.9
LTR_FRONT, LTR_BACK = 50.6, 52.2
BLOCK_SCREWS = [(37.6, 7.1), (37.6, 16.1), (23.7, 11.6)]
LCD_CX, LCD_CY, LCD_BACK, LCD_FRONT = 42.4, 39.85, 37.7, 39.4
LCD_HOLES = [(4.6, 24.05), (80.2, 24.05), (4.6, 55.65), (80.2, 55.65)]
RPI_CX = RPI_CY = 42.1
RPI_HOLES = [(13.1, 30.6), (71.1, 30.6), (13.1, 53.6), (71.1, 53.6)]
RPI_Z = 4.1
FRONT_POSTS = [(5.1, 5.1), (79.7, 5.1)]
BTN = [(12.6, 11.6), (23.6, 11.6)]          # OK (left), MODE (right)
CARRIER = (9.1, 1.9, 38.9, 27.6, 21.3, 40.5)
CARRIER_SCREWS = [(18.1, 4.1), (18.1, 19.1)]
LTR_BOSSES = [(17.95, 34.16), (5.25, 13.84)]  # (y, z)
PWR_X = 20.6


# ----------------------------------------------------------------------------- camera
class Cam:
    def __init__(s, az=35, el=30):
        a, e = math.radians(az), math.radians(el)
        s.e = (-math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))
        s.r = (math.cos(a), -math.sin(a), 0.0)
        s.u = (math.sin(e) * math.sin(a), math.sin(e) * math.cos(a), math.cos(e))

    def p(s, q):
        x, y, z = q
        return (x * s.r[0] + y * s.r[1] + z * s.r[2], -(x * s.u[0] + y * s.u[1] + z * s.u[2]))

    def d(s, q):
        return q[0] * s.e[0] + q[1] * s.e[1] + q[2] * s.e[2]


def hull(pts):
    pts = sorted(set((round(a, 4), round(b, 4)) for a, b in pts))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def ring(axis, c, r, n=44):
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        a, b = r * math.cos(t), r * math.sin(t)
        if axis == 2:
            out.append((c[0] + a, c[1] + b, c[2]))
        elif axis == 1:
            out.append((c[0] + a, c[1], c[2] + b))
        else:
            out.append((c[0], c[1] + a, c[2] + b))
    return out


def on_plane(axis, coord, u, v):
    if axis == 2:
        return (u, v, coord)
    if axis == 1:
        return (u, coord, v)
    return (coord, u, v)


class Item:
    def __init__(s, aabb, prims):
        s.aabb, s.prims = aabb, prims


# ----------------------------------------------------------------------------- scene
class Scene:
    def __init__(s, az=35, el=30):
        s.cam = Cam(az, el)
        s.items, s.over = [], []

    # ---- primitives ---------------------------------------------------------
    def box(s, x0, y0, z0, x1, y1, z1, tone=0, holes=(), decals=(), clip_holes=True):
        """holes: rect openings in the visible z face [(hx0, hy0, hx1, hy1, depth, tone)].
        decals: [('circle', axis, coord, u, v, r, fill) | ('rect', axis, coord, u0, v0, u1, v1, fill)
                 | ('poly', axis, coord, [(u, v)...], fill) | ('text', axis, coord, u, v, txt, size)]"""
        e = s.cam.e
        sz, sy, sx = SH[tone]
        pr = []
        if abs(e[0]) > 1e-6:
            xf = x0 if e[0] < 0 else x1
            pr.append(("poly3", [(xf, y0, z0), (xf, y1, z0), (xf, y1, z1), (xf, y0, z1)], sx))
        if abs(e[1]) > 1e-6:
            yf = y0 if e[1] < 0 else y1
            pr.append(("poly3", [(x0, yf, z0), (x1, yf, z0), (x1, yf, z1), (x0, yf, z1)], sy))
        zf = z1 if e[2] > 0 else z0
        outer = [(x0, y0, zf), (x1, y0, zf), (x1, y1, zf), (x0, y1, zf)]
        rings = [outer] + [[(a, b, zf), (c, b, zf), (c, d, zf), (a, d, zf)] for a, b, c, d, *_ in holes]
        pr.append(("path3", rings, sz))
        for a, b, c, d, depth, ht in holes:
            hz, hy, hx = SH[ht]
            zb = zf - depth if e[2] > 0 else zf + depth
            walls = []
            wx = c if e[0] < 0 else a
            walls.append(("poly3", [(wx, b, zf), (wx, d, zf), (wx, d, zb), (wx, b, zb)], hx))
            wy = d if e[1] < 0 else b
            walls.append(("poly3", [(a, wy, zf), (c, wy, zf), (c, wy, zb), (a, wy, zb)], hy))
            pr.append(("clip3", [(a, b, zf), (c, b, zf), (c, d, zf), (a, d, zf)], walls))
        pr += [s._decal(dc) for dc in decals]
        s.items.append(Item((x0, y0, z0, x1, y1, z1), pr))

    def _decal(s, dc):
        kind = dc[0]
        if kind == "circle":
            _, ax, co, u, v, r, fill = dc
            return ("poly3", [on_plane(ax, co, u + r * math.cos(t), v + r * math.sin(t))
                              for t in [2 * math.pi * i / 36 for i in range(36)]], fill, 0.8)
        if kind == "rect":
            _, ax, co, u0, v0, u1, v1, fill = dc
            return ("poly3", [on_plane(ax, co, u0, v0), on_plane(ax, co, u1, v0),
                              on_plane(ax, co, u1, v1), on_plane(ax, co, u0, v1)], fill, 0.8)
        if kind == "poly":
            _, ax, co, pts, fill = dc
            return ("poly3", [on_plane(ax, co, u, v) for u, v in pts], fill, 0.8)
        if kind == "line":
            _, ax, co, pts = dc
            return ("line3", [on_plane(ax, co, u, v) for u, v in pts], None, 1.0)
        raise ValueError(kind)

    def cyl_prims(s, axis, c, L, r0, r1=None, tone=0, cap_decals=(), rings_at=()):
        r1 = r0 if r1 is None else r1
        e = s.cam.e
        sz, sy, sx = SH[tone]
        end = list(c)
        end[axis] += L
        a = ring(axis, c, r0) if r0 > 0 else [tuple(c)]
        b = ring(axis, end, r1) if r1 > 0 else [tuple(end)]
        cam = s.cam
        pr = [("poly2", hull([cam.p(q) for q in a + b]), sy if axis == 2 else sx)]
        for t in rings_at:                      # knurl / decoration rings (front half)
            cc = list(c)
            cc[axis] += t * L
            rr = r0 + (r1 - r0) * t
            pts = [q for q in ring(axis, cc, rr, 60) if cam.d(q) >= cam.d(tuple(cc)) - 1e-9]
            pts.sort(key=lambda q: cam.p(q)[0])
            pr.append(("line3", pts, None, 0.8))
        sgn = 1 if L > 0 else -1
        if sgn * e[axis] > 0:
            cap, rc, cc = b, r1, end
        else:
            cap, rc, cc = a, r0, c
        if rc > 0:
            pr.append(("poly3", cap, sz))
            for dc in cap_decals:
                pr.append(dc(cc))
        pts = a + b
        bb = tuple(min(q[i] for q in pts) for i in range(3)) + tuple(max(q[i] for q in pts) for i in range(3))
        return pr, bb

    def cyl(s, axis, c, L, r0, r1=None, tone=0, cap_decals=(), rings_at=()):
        pr, bb = s.cyl_prims(axis, c, L, r0, r1, tone, cap_decals, rings_at)
        s.items.append(Item(bb, pr))

    def screw(s, tip, axis=2, head_dir=1, d=3.0, L=8.0, head="csk", tone=0):
        """Screw from its tip; the head is at tip + head_dir*L along axis."""
        dh = {"csk": 2.0 * d, "pan": 1.75 * d}[head]
        hh = (dh - d) / 2 if head == "csk" else 0.65 * d
        segs = []
        shaft = L - hh if head == "csk" else L
        c0 = list(tip)
        segs.append((tuple(c0), head_dir * shaft, d / 2 * 0.75, d / 2))      # pointed shaft
        c1 = list(tip)
        c1[axis] += head_dir * shaft
        if head == "csk":
            segs.append((tuple(c1), head_dir * hh, d / 2, dh / 2))
        else:
            segs.append((tuple(c1), head_dir * hh, dh / 2, dh / 2 * 0.92))
        cam = s.cam
        allpr, boxes = [], []
        order = sorted(segs, key=lambda sg: cam.d(tuple(sg[0][i] + (sg[1] / 2 if i == axis else 0)
                                                        for i in range(3))))
        for c, Ls, ra, rb in order:
            is_head = (c == segs[-1][0])

            def cross(cc, rr=rb * 0.55, ax=axis):
                u = [0, 0, 0]
                v = [0, 0, 0]
                o = [i for i in range(3) if i != ax]
                u[o[0]], v[o[1]] = rr, rr
                p = [tuple(cc[i] + k * u[i] for i in range(3)) for k in (-1, 1)]
                q = [tuple(cc[i] + k * v[i] for i in range(3)) for k in (-1, 1)]
                return ("multiline3", [p, q], None, 1.0)
            pr, bb = s.cyl_prims(axis, c, Ls, ra, rb, tone, cap_decals=(cross,) if is_head else ())
            allpr += pr
            boxes.append(bb)
        bb = tuple(min(b[i] for b in boxes) for i in range(3)) + tuple(max(b[i + 3] for b in boxes) for i in range(3))
        s.items.append(Item(bb, allpr))

    def insert(s, base_c, L=6.0, d=4.2):
        hole = lambda cc: ("poly3", ring(2, cc, 1.5, 24), HOLE, 0.6)
        s.cyl(2, base_c, L, d / 2, tone=1, cap_decals=(hole,), rings_at=(0.25, 0.5, 0.75))

    # ---- overlays -----------------------------------------------------------
    def arrow(s, a, b):
        s.over.append(("arrow3", a, b))

    def dash(s, a, b):
        s.over.append(("dash3", a, b))

    def label(s, p, txt, dx=0, dy=0, size=15, weight="bold", anchor="middle"):
        s.over.append(("text3", p, txt, dx, dy, size, weight, anchor))

    # ---- painter's order ----------------------------------------------------
    def _order(s):
        cam, items = s.cam, s.items
        sb = []
        for it in items:
            x0, y0, z0, x1, y1, z1 = it.aabb
            pts = [cam.p((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
            sb.append((min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)))
        dep = [cam.d(((it.aabb[0] + it.aabb[3]) / 2, (it.aabb[1] + it.aabb[4]) / 2, (it.aabb[2] + it.aabb[5]) / 2))
               for it in items]
        n = len(items)
        after = [set() for _ in range(n)]
        indeg = [0] * n

        def behind(A, B):   # True if A must be drawn before B
            for k in range(3):
                ek = cam.e[k]
                if abs(ek) < 1e-6:
                    continue
                a0, a1, b0, b1 = A[k], A[k + 3], B[k], B[k + 3]
                if a1 <= b0 + 1e-6:
                    return ek > 0           # A on the low side: behind if the viewer is high
                if b1 <= a0 + 1e-6:
                    return ek < 0
            return None
        for i in range(n):
            for j in range(i + 1, n):
                a, b = sb[i], sb[j]
                if a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
                    continue
                r = behind(items[i].aabb, items[j].aabb)
                if r is None:
                    r = dep[i] < dep[j]
                if r:
                    after[i].add(j)
                else:
                    after[j].add(i)
        for i in range(n):
            for j in after[i]:
                indeg[j] += 1
        done, out = [False] * n, []
        while len(out) < n:
            ready = [i for i in range(n) if not done[i] and indeg[i] == 0]
            if not ready:
                ready = [min((i for i in range(n) if not done[i]), key=lambda i: dep[i])]
            i = min(ready, key=lambda i: dep[i])
            done[i] = True
            out.append(items[i])
            for j in after[i]:
                indeg[j] -= 1
        return out

    # ---- render -------------------------------------------------------------
    def bounds(s):
        cam = s.cam
        pts = []
        for it in s.items:
            for pr in it.prims:
                if pr[0] == "poly2":
                    pts += pr[1]
                elif pr[0] == "path3":
                    pts += [cam.p(q) for q in pr[1][0]]
                elif pr[0] in ("poly3", "line3"):
                    pts += [cam.p(q) for q in pr[1]]
        for o in s.over:
            if o[0] in ("arrow3", "dash3"):
                pts += [cam.p(o[1]), cam.p(o[2])]
            elif o[0] == "text3":
                pts.append(cam.p(o[1]))
        return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))

    def render(s, x, y, w, h, scale=None, pad=10, center=None):
        bx0, by0, bx1, by1 = s.bounds()
        k = scale or min((w - 2 * pad) / (bx1 - bx0), (h - 2 * pad) / (by1 - by0))
        if center is not None:
            cx, cy = s.cam.p(center)
            bx0 = bx1 = cx
            by0 = by1 = cy
        ox = x + w / 2 - k * (bx0 + bx1) / 2
        oy = y + h / 2 - k * (by0 + by1) / 2
        cam = s.cam

        def T(q2):
            return (ox + k * q2[0], oy + k * q2[1])

        def P(q3):
            return T(cam.p(q3))
        s.P = P

        def pts(lst):
            return " ".join(f"{a:.1f},{b:.1f}" for a, b in lst)
        lw = 1.3
        out = []

        def emit(pr):
            t = pr[0]
            if t == "poly3":
                wdt = pr[3] if len(pr) > 3 else lw
                out.append(f'<polygon points="{pts([P(q) for q in pr[1]])}" fill="{pr[2]}" stroke="{INK}" '
                           f'stroke-width="{wdt}" stroke-linejoin="round"/>')
            elif t == "poly2":
                out.append(f'<polygon points="{pts([T(q) for q in pr[1]])}" fill="{pr[2]}" stroke="{INK}" '
                           f'stroke-width="{lw}" stroke-linejoin="round"/>')
            elif t == "path3":
                d = " ".join("M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in [P(q) for q in rg]) + " Z"
                             for rg in pr[1])
                out.append(f'<path d="{d}" fill="{pr[2]}" fill-rule="evenodd" stroke="{INK}" '
                           f'stroke-width="{lw}" stroke-linejoin="round"/>')
            elif t == "clip3":
                cid = uid()
                out.append(f'<clipPath id="{cid}"><polygon points="{pts([P(q) for q in pr[1]])}"/></clipPath>'
                           f'<g clip-path="url(#{cid})">')
                for sub in pr[2]:
                    emit(sub)
                out.append("</g>")
            elif t == "line3":
                out.append(f'<polyline points="{pts([P(q) for q in pr[1]])}" fill="none" stroke="{INK}" '
                           f'stroke-width="{pr[3]}" stroke-linecap="round"/>')
            elif t == "multiline3":
                for seg in pr[1]:
                    out.append(f'<polyline points="{pts([P(q) for q in seg])}" fill="none" stroke="{INK}" '
                               f'stroke-width="{pr[3]}" stroke-linecap="round"/>')
        for it in s._order():
            for pr in it.prims:
                emit(pr)
        for o in s.over:
            if o[0] == "dash3":
                (a, b), (c, d) = P(o[1]), P(o[2])
                out.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}" stroke="{INK}" '
                           f'stroke-width="1" stroke-dasharray="5 4"/>')
            elif o[0] == "arrow3":
                (a, b), (c, d) = P(o[1]), P(o[2])
                out.append(arrow2d(a, b, c, d))
            elif o[0] == "text3":
                _, p, txt, dx, dy, size, weight, anchor = o
                a, b = P(p)
                out.append(text(a + dx, b + dy, txt, size, weight, anchor))
        return "\n".join(out)


def arrow2d(x0, y0, x1, y1, w=2.2):
    ang = math.atan2(y1 - y0, x1 - x0)
    hl, hw = 13, 6.5
    bx, by = x1 - hl * math.cos(ang), y1 - hl * math.sin(ang)
    px, py = -math.sin(ang) * hw, math.cos(ang) * hw
    return (f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{INK}" stroke-width="{w}"/>'
            f'<polygon points="{x1:.1f},{y1:.1f} {bx + px:.1f},{by + py:.1f} {bx - px:.1f},{by - py:.1f}" '
            f'fill="{INK}"/>')


def text(x, y, txt, size=15, weight="normal", anchor="middle", fill=INK):
    txt = txt.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}">{txt}</text>')


# ----------------------------------------------------------------------------- 2D icons
def icon_ok(x, y, r=16):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{INK}" stroke-width="2"/>'
            f'<polyline points="{x - r * .45:.1f},{y + r * .02:.1f} {x - r * .1:.1f},{y + r * .38:.1f} '
            f'{x + r * .5:.1f},{y - r * .38:.1f}" fill="none" stroke="{INK}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def icon_no(x, y, r=16):
    k = r * 0.38
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke="{INK}" stroke-width="2"/>'
            f'<path d="M{x - k:.1f},{y - k:.1f} L{x + k:.1f},{y + k:.1f} M{x + k:.1f},{y - k:.1f} '
            f'L{x - k:.1f},{y + k:.1f}" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>')


def icon_warn(x, y, s=34):
    h = s * 0.87
    return (f'<polygon points="{x},{y - h / 2:.1f} {x + s / 2:.1f},{y + h / 2:.1f} {x - s / 2:.1f},{y + h / 2:.1f}" '
            f'fill="#fff" stroke="{INK}" stroke-width="2.2" stroke-linejoin="round"/>'
            + text(x, y + h / 2 - 6, "!", 20, "bold"))


def tool_screwdriver(x, y, s=1.0):
    return (f'<g transform="translate({x},{y}) scale({s}) rotate(-35)">'
            f'<rect x="0" y="-8" width="34" height="16" rx="7" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
            f'<line x1="6" y1="-3" x2="28" y2="-3" stroke="{INK}" stroke-width="1"/>'
            f'<line x1="6" y1="3" x2="28" y2="3" stroke="{INK}" stroke-width="1"/>'
            f'<rect x="34" y="-2.2" width="34" height="4.4" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
            f'<polygon points="68,-2.2 75,0 68,2.2" fill="{INK}"/></g>')


def tool_iron(x, y, s=1.0):
    return (f'<g transform="translate({x},{y}) scale({s}) rotate(-35)">'
            f'<path d="M-14,0 C-24,0 -26,14 -36,14" fill="none" stroke="{INK}" stroke-width="1.6"/>'
            f'<rect x="-14" y="-7" width="38" height="14" rx="6" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
            f'<rect x="24" y="-4.5" width="10" height="9" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
            f'<rect x="34" y="-2.5" width="26" height="5" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
            f'<polygon points="60,-2.5 72,0 60,2.5" fill="#fff" stroke="{INK}" stroke-width="1.4"/></g>')


def tool_knife(x, y, s=1.0):
    return (f'<g transform="translate({x},{y}) scale({s}) rotate(-35)">'
            f'<rect x="0" y="-5.5" width="40" height="11" rx="3" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
            f'<polygon points="40,-4 58,-4 70,4 40,4" fill="#fff" stroke="{INK}" stroke-width="1.4" '
            f'stroke-linejoin="round"/></g>')


# ----------------------------------------------------------------------------- parts
def base(S, o=(0, 0, 0), posts=True):
    X, Y, Z = o
    S.box(X, Y, Z, X + OUT_X, Y + OUT_Y, Z + F)                                     # floor
    S.box(X, Y, Z + F, X + OUT_X, Y + W, Z + Z_LIDB)                                # front
    S.box(X, Y + OUT_Y - W, Z + F, X + OUT_X, Y + OUT_Y, Z + Z_LIDB,
          decals=[("rect", 1, Y + OUT_Y - W, X + PWR_X - 6, Z + 3.5, X + PWR_X + 6, Z + 11.5, HOLE)])
    S.box(X, Y + W, Z + F, X + W, Y + OUT_Y - W, Z + Z_LIDB)                        # left
    S.box(X + OUT_X - W, Y + W, Z + F, X + OUT_X, Y + OUT_Y - W, Z + Z_LIDB)        # right
    if not posts:
        return
    hole = lambda cc: ("poly3", ring(2, cc, 2.0, 24), HOLE, 0.6)
    pil = lambda cc: ("poly3", ring(2, cc, 0.9, 16), HOLE, 0.6)
    for x, y in FRONT_POSTS:
        S.cyl(2, (X + x, Y + y, Z + F), Z_LIDB - F, 3.5, cap_decals=(hole,))
    for x, y in LCD_HOLES:
        S.cyl(2, (X + x, Y + y, Z + F), LCD_BACK - F, 3.0, cap_decals=(pil,))
    for x, y in RPI_HOLES:
        S.cyl(2, (X + x, Y + y, Z + F), RPI_Z - F, 2.5, cap_decals=(pil,))
    for x, y in BLOCK_SCREWS:
        S.cyl(2, (X + x, Y + y, Z + F), Z_BLK - F, 4.0)


def base_bottom_holes(S, o=(0, 0, 0)):
    """Floor seen from below, with the three countersunk holes."""
    X, Y, Z = o
    dec = [("circle", 2, Z, X + x, Y + y, 3.15, HOLE) for x, y in BLOCK_SCREWS]
    S.box(X, Y, Z, X + OUT_X, Y + OUT_Y, Z + Z_LIDB, decals=dec)


def lid(S, o=(0, 0, 0)):
    X, Y, Z = o
    ch = COLLAR_H + 0.4
    holes = [(X + WCX - ch, Y + WCY - ch, X + WCX + ch, Y + WCY + ch, 1.6, 2),
             (X + 6.45, Y + 24.75, X + 78.35, Y + 52.15, 1.6, 1)]
    holes += [(X + x - 3.3, Y + y - 3.3, X + x + 3.3, Y + y + 3.3, 1.6, 2) for x, y in BTN]
    top = S.cam.e[2] > 0
    zf = Z + (Z_TOP if top else Z_LIDB)
    dec = [("circle", 2, zf, X + x, Y + y, 3.1 if top else 1.7, HOLE) for x, y in FRONT_POSTS]
    dec += [("circle", 2, zf, X + x, Y + y, 1.9 if top else 1.2, HOLE) for x, y in LCD_HOLES]
    if not top:
        dec += [("circle", 2, zf, X + x, Y + y, 0.9, HOLE) for x, y in CARRIER_SCREWS]
    for sgn in (-1, 1) if top else ():
        x = WCX + sgn * (ch + 2.5)
        dec.append(("poly", 2, zf, [(X + x + sgn * 1.6, Y + WCY), (X + x - sgn * 1.0, Y + WCY + 1.6),
                                     (X + x - sgn * 1.0, Y + WCY - 1.6)], INK))
    S.box(X, Y, Z + Z_LIDB, X + OUT_X, Y + OUT_Y, Z + Z_TOP, holes=holes, decals=dec)


def block(S, o=(0, 0, 0), pockets=False):
    X, Y, Z = o
    bot = [("circle", 2, Z + Z_BLK, X + x, Y + y, 2.0, HOLE) for x, y in BLOCK_SCREWS] if pockets else []
    S.box(X + LED_FACE, Y + 3.5, Z + Z_BLK, X + 44.1, Y + 19.7, Z + Z_LIDB,
          decals=[d for d in bot if d[3] - X > LED_FACE])
    S.box(X + 44.1, Y + 2.5, Z + Z_BLK, X + SEN_FACE, Y + 20.7, Z + Z_LIDB,
          decals=[("rect", 0, X + SEN_FACE, Y + 9.1, Z + 21.5, Y + 14.1, Z + 26.5, HOLE)])
    S.box(X + WCX - COLLAR_H, Y + WCY - COLLAR_H, Z + Z_LIDB, X + WCX + COLLAR_H, Y + WCY + COLLAR_H,
          Z + Z_COLLAR, holes=[(X + WCX - WH, Y + WCY - WH, X + WCX + WH, Y + WCY + WH, 36, 2)])
    S.box(X + BLK_X0, Y + WCY - 4.5, Z + Z_BLK, X + LED_FACE, Y + WCY + 4.5, Z + BEAM_Z + 4.5,
          decals=[("circle", 0, X + BLK_X0, Y + WCY, Z + BEAM_Z, 3.1, "#fff"),
                  ("circle", 0, X + BLK_X0, Y + WCY, Z + BEAM_Z, 2.6, HOLE)]
          + [d for d in bot if d[3] - X < LED_FACE])
    pil = lambda cc: ("poly3", ring(0, cc, 0.85, 16), HOLE, 0.6)
    for y, z in LTR_BOSSES:
        S.cyl(0, (X + SEN_FACE, Y + y, Z + z), LTR_FRONT - SEN_FACE, 2.3, cap_decals=(pil,))


def ltr(S, o=(0, 0, 0)):
    X, Y, Z = o
    dec = [("rect", 0, X + LTR_FRONT, Y + WCY - 1.2, Z + BEAM_Z - 1.2, Y + WCY + 1.2, Z + BEAM_Z + 1.2, INK)]
    dec += [("circle", 0, X + LTR_FRONT, Y + y, Z + z, 1.25, "#fff") for y, z in LTR_BOSSES]
    dec += [("rect", 0, X + LTR_FRONT, Y + 4.0, Z + 11.8, Y + 9.0, Z + 16.0, "#fff"),
            ("rect", 0, X + LTR_FRONT, Y + 14.2, Z + 32.0, Y + 19.2, Z + 36.2, "#fff")]
    S.box(X + LTR_FRONT, Y + 2.71, Z + 11.3, X + LTR_BACK, Y + 20.49, Z + 36.7, tone=1, decals=dec)


def led(S, o=(0, 0, 0), leads=True):
    X, Y, Z = o
    c = (X + BLK_X0, Y + WCY, Z + BEAM_Z)
    S.cyl(0, c, 1.0, 3.1)
    S.cyl(0, (c[0] + 1.0, c[1], c[2]), 6.1, 2.5)
    S.cyl(0, (c[0] + 7.1, c[1], c[2]), 2.5, 2.5, 1.0)
    if leads:
        a = [(c[0], c[1] - 1.27, c[2]), (c[0] - 4, c[1] - 1.27, c[2]), (c[0] - 4, c[1] - 1.27, c[2] - 20)]
        k = [(c[0], c[1] + 1.27, c[2]), (c[0] - 4, c[1] + 1.27, c[2]), (c[0] - 4, c[1] + 1.27, c[2] - 16)]
        S.items.append(Item((c[0] - 4, c[1] - 1.5, c[2] - 20, c[0], c[1] + 1.5, c[2]),
                            [("line3", a, None, 1.6), ("line3", k, None, 1.6)]))
        return a[-1], k[-1]


def cuvette(S, o=(0, 0, 0)):
    X, Y, Z = o
    S.box(X + WCX - 6.25, Y + WCY - 6.25, Z + SEAT_Z, X + WCX + 6.25, Y + WCY + 6.25, Z + SEAT_Z + 46,
          tone=3, holes=[(X + WCX - 5, Y + WCY - 5, X + WCX + 5, Y + WCY + 5, 44, 0)])


def cap(S, o=(0, 0, 0)):
    X, Y, Z = o
    S.box(X + WCX - 10, Y + WCY - 10, Z + Z_TOP, X + WCX + 10, Y + WCY + 10, Z + Z_TOP + 19.1)


def pi(S, o=(0, 0, 0)):
    X, Y, Z = o
    z1 = Z + RPI_Z + 1.4
    dec = [("circle", 2, z1, X + x, Y + y, 1.4, "#fff") for x, y in RPI_HOLES]
    S.box(X + 9.6, Y + 27.1, Z + RPI_Z, X + 74.6, Y + 57.1, z1, tone=1, decals=dec)
    S.box(X + 16.5, Y + 28.0, z1, X + 67.7, Y + 33.2, z1 + 2.5, tone=2)
    pins = []
    for i in range(20):
        for yy in (29.3, 31.9):
            x = X + 17.8 + 2.54 * i
            pins.append(("line3", [(x, Y + yy, z1 + 2.5), (x, Y + yy, z1 + 8.5)], None, 1.1))
    S.items.append(Item((X + 16.5, Y + 28.0, z1 + 2.5, X + 67.7, Y + 33.2, z1 + 8.5), pins))
    S.box(X + 36, Y + 38, z1, X + 48, Y + 50, z1 + 1.2, tone=2)
    for x0 in (PWR_X - 4, PWR_X + 8.6):                                           # micro-USB
        S.box(X + x0, Y + 52.0, z1, X + x0 + 8, Y + 57.8, z1 + 2.6)
    S.box(X + 54, Y + 50.5, z1, X + 65.5, Y + 57.8, z1 + 3.2)                    # mini HDMI


def lcd(S, o=(0, 0, 0)):
    X, Y, Z = o
    dec = [("circle", 2, Z + LCD_FRONT, X + x, Y + y, 1.5, "#fff") for x, y in LCD_HOLES]
    S.box(X + 2.4, Y + 21.85, Z + LCD_BACK, X + 82.4, Y + 57.85, Z + LCD_FRONT, tone=1, decals=dec)
    S.box(X + 6.75, Y + 25.05, Z + LCD_FRONT, X + 78.05, Y + 51.85, Z + 43.7, tone=2,
          decals=[("rect", 2, Z + 43.7, X + 13, Y + 30.5, X + 72, Y + 46.5, SH[3][0])])


def switch(S, x, y, z, label=None):
    S.box(x - 3.1, y - 3.1, z, x + 3.1, y + 3.1, z + 3.5, tone=2)
    S.cyl(2, (x, y, z + 3.5), 1.5, 1.75, tone=0)
    legs = [("line3", [(x + sx * 3.25, y + sy * 2.25, z), (x + sx * 3.25, y + sy * 2.25, z - 3.5)], None, 1.2)
            for sx in (-1, 1) for sy in (-1, 1)]
    S.items.append(Item((x - 3.3, y - 2.3, z - 3.5, x + 3.3, y + 2.3, z), legs))
    if label:
        S.label((x, y, z + 5), label, dy=-10, size=13)


def carrier(S, o=(0, 0, 0)):
    X, Y, Z = o
    x0, y0, z0, x1, y1, z1 = CARRIER
    dec = [("circle", 2, Z + z1, X + x, Y + y, 1.2, HOLE) for x, y in CARRIER_SCREWS]
    S.box(X + x0, Y + y0, Z + z0, X + x1, Y + y1, Z + z1, decals=dec)


def ltr_flat(S):
    """LTR-329 breakout lying on its chip side: back with the header and SJ1."""
    S.box(0, 0, 0, 25.4, 17.78, 1.6, tone=1,
          decals=[("circle", 2, 1.6, 2.54, 2.54, 1.25, "#fff"), ("circle", 2, 1.6, 22.86, 15.24, 1.25, "#fff"),
                  ("rect", 2, 1.6, 15.0, 9.8, 18.4, 12.2, "#fff"),
                  ("line", 2, 1.6, [(16.7, 9.3), (16.7, 12.7)])])
    S.box(5.1, 1.27, 1.6, 20.3, 3.81, 4.1, tone=2)
    pins = [("line3", [(7.62 + 2.54 * i, 2.54, 4.1), (7.62 + 2.54 * i, 2.54, 10.0)], None, 1.2) for i in range(5)]
    S.items.append(Item((6.0, 2.3, 4.1, 19.5, 2.8, 10.0), pins))


# ----------------------------------------------------------------------------- figure
class Fig:
    def __init__(s, w=900, h=620):
        s.w, s.h, s.parts_svg = w, h, []

    def number(s, n):
        s.parts_svg.append(text(28, 70, str(n), 60, "bold", "start"))

    def parts(s, entries, x=None, y=18, slot=104, h=132):
        """entries: [(builder(scene), 'label', 'count')]"""
        n = len(entries)
        bw = n * slot + 20
        x = s.w - bw - 20 if x is None else x
        out = [f'<rect x="{x}" y="{y}" width="{bw}" height="{h}" rx="10" fill="#fff" stroke="{INK}" stroke-width="1.6"/>']
        for i, (fn, lab, cnt) in enumerate(entries):
            S = Scene()
            fn(S)
            sx = x + 10 + i * slot
            out.append(S.render(sx, y + 8, slot, h - 58))
            out.append(text(sx + slot / 2, y + h - 30, cnt, 18, "bold"))
            out.append(text(sx + slot / 2, y + h - 11, lab, 12.5))
        s.parts_svg.append("\n".join(out))

    def add(s, svg):
        s.parts_svg.append(svg)

    def save(s, name):
        body = "\n".join(s.parts_svg)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s.w} {s.h}" width="{s.w}" height="{s.h}">\n'
               f'<rect width="{s.w}" height="{s.h}" fill="#ffffff"/>\n{body}\n</svg>\n')
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


def screw_part(d, L, head, axis=2):
    return lambda S: S.screw((0, 0, 0), axis=axis, head_dir=1, d=d, L=L, head=head)


def insert_part(S):
    S.insert((0, 0, 0))


# ----------------------------------------------------------------------------- figures
def fig_parts():
    f = Fig(900, 760)
    rows = [
        ("printed", [(lambda S: base(S), "base"), (lambda S: lid(S), "lid"), (lambda S: block(S), "optical block"),
                     (lambda S: carrier(S), "button carrier"), (lambda S: cap(S), "cap")]),
        ("elec", [(lambda S: pi(S), "Raspberry Pi Zero 2 W"), (lambda S: lcd(S), "LCD 1602 I²C"),
                  (lambda S: ltr(S), "LTR-329"), (lambda S: led(S, leads=False), "LED 5 mm"),
                  (lambda S: switch(S, 0, 0, 0), "switch 6×6  (2×)"), (lambda S: cuvette(S), "cuvette")]),
    ]
    y = 20
    for _, entries in rows:
        n = len(entries)
        slot = (f.w - 40) / n
        f.add(f'<rect x="20" y="{y}" width="{f.w - 40}" height="200" rx="10" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
        for i, (fn, lab) in enumerate(entries):
            S = Scene(25, 62) if lab == "lid" else Scene()
            fn(S)
            sx = 20 + i * slot
            f.add(S.render(sx + 8, y + 10, slot - 16, 150))
            f.add(text(sx + slot / 2, y + 185, lab, 13.5))
        y += 215
    hw = [(insert_part, "M3 insert", "5×"), (screw_part(3, 8, "csk"), "M3×8", "3×"),
          (screw_part(3, 6, "csk"), "M3×6", "2×"), (screw_part(2, 10, "csk"), "M2×10", "4×"),
          (screw_part(2, 6, "pan"), "M2×6", "2×"), (screw_part(2, 5, "pan"), "M2×5", "4×"),
          (screw_part(2, 4, "pan"), "M2×4", "2×")]
    slot = (f.w - 40) / len(hw)
    f.add(f'<rect x="20" y="{y}" width="{f.w - 40}" height="150" rx="10" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
    for i, (fn, lab, cnt) in enumerate(hw):
        S = Scene()
        fn(S)
        sx = 20 + i * slot
        f.add(S.render(sx + 30, y + 14, slot - 60, 80))
        f.add(text(sx + slot / 2, y + 118, cnt, 19, "bold"))
        f.add(text(sx + slot / 2, y + 138, lab, 13.5))
    y += 165
    f.add(f'<rect x="20" y="{y}" width="{f.w - 40}" height="125" rx="10" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
    f.add(tool_screwdriver(70, y + 85, 1.1) + text(125, y + 113, "PH0 / PH1", 13.5))
    f.add(tool_iron(250, y + 85, 1.0) + text(300, y + 113, "soldering iron", 13.5))
    f.add(tool_knife(445, y + 85, 1.0) + text(480, y + 113, "craft knife", 13.5))
    f.add(text(700, y + 40, "14× Dupont F-F", 15, "bold") + text(700, y + 62, "wires", 13.5)
          + text(700, y + 92, "PLA black matte", 15, "bold") + text(700, y + 112, "≈ 60 g", 13.5))
    f.save("build_00_parts.svg")


def fig_inserts():
    f = Fig()
    f.number(1)
    f.add(tool_iron(150, 60, 1.1))
    S = Scene(35, -30)                                  # optical block seen from below
    block(S, pockets=True)
    for x, y in BLOCK_SCREWS:
        S.insert((x, y, -14))
        S.arrow((x, y, -16), (x, y, -1))
    f.add(S.render(30, 150, 400, 450))
    f.parts([(insert_part, "M3 insert", "5×")])
    S = Scene()
    base(S)
    for x, y in FRONT_POSTS:
        S.insert((x, y, 58))
        S.arrow((x, y, 76), (x, y, 66))
        S.dash((x, y, 58), (x, y, Z_LIDB))
    f.add(S.render(440, 150, 440, 450))
    f.save("build_01_inserts.svg")


def fig_ltr_prep():
    f = Fig(900, 520)
    f.number(2)
    S = Scene(30, 38)
    ltr_flat(S)
    S.label((16.7, 14.5, 1.6), "SJ1", dy=-10, size=16)
    f.add(S.render(120, 60, 520, 440))
    f.add(tool_knife(560, 250, 1.4))
    f.add(tool_iron(560, 420, 1.2))
    f.add(icon_warn(805, 120))
    f.add(text(805, 175, "SJ1 ✂", 18, "bold"))
    f.save("build_02_ltr_prep.svg")


def fig_ltr_mount():
    f = Fig()
    f.number(3)
    f.parts([(screw_part(2, 6, "pan"), "M2×6", "2×")])
    S = Scene()
    block(S)
    off = 22
    ltr(S, (off, 0, 0))
    for y, z in LTR_BOSSES:
        S.screw((LTR_BACK + off + 12, y, z), axis=0, head_dir=1, d=2, L=6, head="pan")
        S.dash((LTR_FRONT, y, z), (LTR_BACK + off + 12, y, z))
    S.arrow((LTR_BACK + off + 2, 26, 46), (LTR_BACK + 4, 26, 46))
    f.add(S.render(40, 150, 820, 450))
    f.add(icon_ok(830, 560))
    f.save("build_03_ltr_mount.svg")


def fig_led():
    f = Fig()
    f.number(4)
    S = Scene()
    block(S)
    off = -24
    a, k = led(S, (off, 0, 0))
    S.dash((BLK_X0 + off + 9.6, WCY, BEAM_Z), (BLK_X0, WCY, BEAM_Z))
    S.arrow((BLK_X0 + off - 6, WCY, BEAM_Z + 12), (BLK_X0 + off + 10, WCY, BEAM_Z + 12))
    S.label(a, "+", dx=-12, dy=8, size=22)
    S.label(k, "−", dx=-12, dy=8, size=22)
    f.add(S.render(40, 110, 600, 490))
    # zoom: flange against the block
    f.add(f'<circle cx="760" cy="300" r="105" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
    Z = Scene()
    block(Z)
    led(Z, leads=False)
    f.add(f'<clipPath id="zl"><circle cx="760" cy="300" r="103"/></clipPath><g clip-path="url(#zl)">'
          + Z.render(660, 200, 200, 200, scale=9, center=(BLK_X0 + 2, WCY, BEAM_Z)) + "</g>")
    f.add(icon_ok(840, 395))
    f.add(text(760, 450, "+ = long lead", 15, "normal"))
    f.save("build_04_led.svg")


def fig_block_in_base():
    f = Fig(900, 680)
    f.number(5)
    f.parts([(screw_part(3, 8, "csk"), "M3×8", "3×")])
    S = Scene()
    base(S)
    up = 54
    block(S, (0, 0, up))
    ltr(S, (0, 0, up))
    led(S, (0, 0, up), leads=False)
    S.arrow((WCX, WCY, Z_COLLAR + up + 18), (WCX, WCY, Z_COLLAR + up + 4))
    for x, y in BLOCK_SCREWS:
        S.screw((x, y, -18), axis=2, head_dir=-1, d=3, L=8, head="csk")
        S.arrow((x, y, -34), (x, y, -28))
    f.add(S.render(40, 150, 820, 520))
    f.save("build_05_block_in_base.svg")


def fig_pi():
    f = Fig(900, 640)
    f.number(6)
    f.parts([(screw_part(2, 5, "pan"), "M2×5", "4×")])
    S = Scene()
    base(S)
    block(S)
    ltr(S)
    led(S, leads=False)
    up = 50
    pi(S, (0, 0, up))
    for x, y in RPI_HOLES:
        S.screw((x, y, up + RPI_Z + 1.4 + 14), axis=2, head_dir=1, d=2, L=5, head="pan")
        S.dash((x, y, RPI_Z), (x, y, up + RPI_Z + 15))
    S.dash((PWR_X, 57.8, up + RPI_Z + 2.7), (PWR_X, OUT_Y - W, 7.5))
    f.add(S.render(40, 150, 820, 480))
    f.save("build_06_pi.svg")


def fig_buttons():
    f = Fig(900, 640)
    f.number(7)
    f.parts([(lambda S: switch(S, 0, 0, 0), "6×6", "2×"), (screw_part(2, 4, "pan"), "M2×4", "2×")])
    # A: switches into the carrier (seen from above)
    A = Scene(35, 35)
    carrier(A)
    for (x, y), lab in zip(BTN, ("OK", "MODE")):
        switch(A, x, y, CARRIER[5] + 14)
        A.dash((x, y, CARRIER[5]), (x, y, CARRIER[5] + 10.5))
        A.label((x, y, CARRIER[5] + 21), lab, dy=-6, size=16)
    f.add(A.render(30, 160, 330, 440))
    f.add(text(195, 610, "A", 22, "bold"))
    f.add(f'<line x1="375" y1="190" x2="375" y2="600" stroke="{INK}" stroke-width="1" stroke-dasharray="3 5"/>')
    # B: carrier under the lid (lid seen from below)
    S = Scene(35, -30)
    lid(S)
    down = -24
    carrier(S, (0, 0, down))
    for x, y in BTN:
        S.box(x - 3.1, y - 3.1, CARRIER[5] + down, x + 3.1, y + 3.1, CARRIER[5] + down + 3.5, tone=2)
        S.items.append(Item((x - 3.3, y - 2.3, CARRIER[2] + down - 2, x + 3.3, y + 2.3, CARRIER[2] + down),
                            [("line3", [(x + sx * 3.25, y + sy * 2.25, CARRIER[2] + down),
                                        (x + sx * 3.25, y + sy * 2.25, CARRIER[2] + down - 2)], None, 1.2)
                             for sx in (-1, 1) for sy in (-1, 1)]))
    for x, y in CARRIER_SCREWS:
        S.screw((x, y, CARRIER[2] + down - 12), axis=2, head_dir=-1, d=2, L=4, head="pan")
        S.dash((x, y, CARRIER[2] + down - 12), (x, y, Z_LIDB))
    S.arrow((34, 11.6, CARRIER[2] + down - 6), (34, 11.6, CARRIER[2] + down + 12))
    f.add(S.render(390, 160, 490, 440))
    f.add(text(635, 610, "B", 22, "bold"))
    f.save("build_07_buttons.svg")


def fig_close():
    f = Fig(900, 700)
    f.number(9)
    f.parts([(screw_part(2, 10, "csk"), "M2×10", "4×"), (screw_part(3, 6, "csk"), "M3×6", "2×")])
    S = Scene()
    base(S)
    block(S)
    ltr(S)
    pi(S)
    l_up, t_up = 26, 56
    lcd(S, (0, 0, l_up))
    lid(S, (0, 0, t_up))
    for x, y in LCD_HOLES:
        S.screw((x, y, Z_TOP + t_up + 8), axis=2, head_dir=1, d=2, L=10, head="csk")
        S.dash((x, y, LCD_BACK), (x, y, Z_TOP + t_up + 8))
    for x, y in FRONT_POSTS:
        S.screw((x, y, Z_TOP + t_up + 8), axis=2, head_dir=1, d=3, L=6, head="csk")
        S.dash((x, y, Z_LIDB), (x, y, Z_TOP + t_up + 8))
    f.add(S.render(40, 150, 820, 540))
    f.save("build_09_close.svg")


def fig_finish():
    f = Fig(900, 640)
    f.number(10)
    S = Scene()
    base(S, posts=False)
    lid(S)
    lcd(S)
    for x, y in BTN:
        S.cyl(2, (x, y, Z_TOP), 1.5, 1.75)
    lift_c, lift_cap = 48, 76
    cuvette(S, (0, 0, lift_c))
    cap(S, (0, 0, lift_cap))
    S.arrow((WCX - 16, WCY, SEAT_Z + lift_c + 34), (WCX - 16, WCY, SEAT_Z + lift_c + 8))
    S.arrow((WCX - 18, WCY, Z_TOP + lift_cap + 18), (WCX - 18, WCY, Z_TOP + lift_cap + 2))
    f.add(S.render(40, 40, 560, 590))
    lx, ly = S.P((LCD_CX + 20, LCD_CY + 6, 43.7))
    px, py = S.P((PWR_X, OUT_Y, 7.5))
    f.add(f'<rect x="640" y="120" width="230" height="70" rx="8" fill="#555" stroke="{INK}" stroke-width="2"/>'
          f'<rect x="652" y="132" width="206" height="46" rx="3" fill="{SH[3][0]}"/>'
          + text(665, 152, "PRATICO 3", 17, "bold", "start") + text(665, 172, "fw 3.0.0", 15, "normal", "start"))
    f.add(f'<path d="M640,185 L{lx:.0f},{ly:.0f}" stroke="{INK}" stroke-width="1.4" stroke-dasharray="5 4"/>')
    f.add(f'<rect x="680" y="420" width="150" height="80" rx="12" fill="#fff" stroke="{INK}" stroke-width="1.8"/>'
          f'<rect x="692" y="435" width="40" height="12" rx="3" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
          + text(755, 485, "5 V", 18, "bold")
          + f'<path d="M680,460 C600,460 {px + 60:.0f},{py:.0f} {px:.0f},{py:.0f}" fill="none" stroke="{INK}" '
            f'stroke-width="2.2" stroke-dasharray="7 4"/>'
          + text(690, 530, "USB (PWR), back", 14, "normal", "start"))
    f.save("build_10_finish.svg")


def fig_wiring():
    """Pi header (pin 1 top-left, as seen from above with the ports at the back) and connections."""
    f = Fig(900, 760)
    f.number(8)
    x0, y0, p = 400, 60, 16.5            # header grid
    used = {
        1: ("3V3", "LTR-329  VIN", "#c0392b"), 3: ("GPIO 2", "LTR-329  SDA", "#d4a017"),
        5: ("GPIO 3", "LTR-329  SCL", "#2e8b57"), 9: ("GND", "LTR-329  GND", INK),
        2: ("5V", "LCD  VCC", "#c0392b"), 6: ("GND", "LCD  GND", INK),
        11: ("GPIO 17", "LCD  SDA", "#d4a017"), 13: ("GPIO 27", "LCD  SCL", "#2e8b57"),
        7: ("GPIO 4", "OK button", "#1f6fb2"), 14: ("GND", "OK button", INK),
        37: ("GPIO 26", "LED  +  (long lead)", "#8e44ad"), 39: ("GND", "LED  −", INK),
        40: ("GPIO 21", "MODE button", "#1f6fb2"), 34: ("GND", "MODE button", INK),
    }
    f.add(f'<rect x="{x0 - 14}" y="{y0 - 14}" width="{p + 28}" height="{19 * p + 28}" rx="6" fill="#fff" '
          f'stroke="{INK}" stroke-width="1.6"/>')
    for n in range(1, 41):
        r, c = (n - 1) // 2, (n - 1) % 2
        cx, cy = x0 + c * p, y0 + r * p
        if n in used:
            f.add(f'<rect x="{cx - 6}" y="{cy - 6}" width="12" height="12" fill="{INK}"/>')
        else:
            f.add(f'<circle cx="{cx}" cy="{cy}" r="3.5" fill="#fff" stroke="{INK}" stroke-width="1.2"/>')
    for n, (sig, dest, col) in used.items():
        r, c = (n - 1) // 2, (n - 1) % 2
        cx, cy = x0 + c * p, y0 + r * p
        if c == 0:
            f.add(f'<line x1="{cx - 7}" y1="{cy}" x2="{cx - 70}" y2="{cy}" stroke="{col}" stroke-width="3"/>')
            f.add(text(cx - 76, cy + 5, f"{n}", 13, "bold", "end"))
            f.add(text(cx - 104, cy + 5, f"{sig}  →  {dest}", 14, "normal", "end"))
        else:
            f.add(f'<line x1="{cx + 7}" y1="{cy}" x2="{cx + 70}" y2="{cy}" stroke="{col}" stroke-width="3"/>')
            f.add(text(cx + 76, cy + 5, f"{n}", 13, "bold", "start"))
            f.add(text(cx + 104, cy + 5, f"{sig}  →  {dest}", 14, "normal", "start"))
    f.add(text(x0 + p / 2, y0 + 19 * p + 44, "Raspberry Pi Zero 2 W — GPIO header, top view", 14, "normal"))
    f.add(text(x0 - 22, y0 + 4, "1", 15, "bold", "end"))
    # buttons / LED detail
    yb = 470
    f.add(f'<rect x="60" y="{yb}" width="780" height="250" rx="10" fill="#fff" stroke="{INK}" stroke-width="1.6"/>')
    # switch: diagonal pins
    for i, (lab, col) in enumerate((("OK", "#1f6fb2"), ("MODE", "#1f6fb2"))):
        cx = 160 + i * 200
        f.add(f'<rect x="{cx - 34}" y="{yb + 60}" width="68" height="68" rx="4" fill="#6c6c6c" stroke="{INK}" stroke-width="1.6"/>'
              f'<circle cx="{cx}" cy="{yb + 94}" r="16" fill="#fff" stroke="{INK}" stroke-width="1.4"/>')
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            f.add(f'<circle cx="{cx + sx * 34}" cy="{yb + 94 + sy * 34}" r="6" fill="#fff" stroke="{INK}" stroke-width="1.4"/>')
        f.add(f'<line x1="{cx - 34}" y1="{yb + 60}" x2="{cx - 70}" y2="{yb + 40}" stroke="{col}" stroke-width="3"/>'
              f'<line x1="{cx + 34}" y1="{yb + 128}" x2="{cx + 70}" y2="{yb + 150}" stroke="{INK}" stroke-width="3"/>')
        f.add(text(cx, yb + 190, lab, 17, "bold"))
        f.add(text(cx - 74, yb + 36, "GPIO", 12, "normal", "end") + text(cx + 74, yb + 166, "GND", 12, "normal", "start"))
    # LED + optional resistor
    lx = 620
    f.add(f'<circle cx="{lx}" cy="{yb + 80}" r="22" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
          f'<line x1="{lx - 8}" y1="{yb + 102}" x2="{lx - 8}" y2="{yb + 175}" stroke="#8e44ad" stroke-width="3"/>'
          f'<line x1="{lx + 8}" y1="{yb + 102}" x2="{lx + 8}" y2="{yb + 150}" stroke="{INK}" stroke-width="3"/>'
          + text(lx - 16, yb + 170, "+", 22, "bold", "end") + text(lx + 16, yb + 148, "−", 22, "bold", "start")
          + text(lx + 100, yb + 70, "optional", 13, "normal")
          + f'<rect x="{lx + 70}" y="{yb + 80}" width="60" height="18" rx="6" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
          + text(lx + 100, yb + 120, "100 Ω", 14, "bold") + text(lx, yb + 220, "LED", 17, "bold"))
    f.save("build_08_wiring.svg")


if __name__ == "__main__":
    fig_parts()
    fig_inserts()
    fig_ltr_prep()
    fig_ltr_mount()
    fig_led()
    fig_block_in_base()
    fig_pi()
    fig_buttons()
    fig_wiring()
    fig_close()
    fig_finish()
