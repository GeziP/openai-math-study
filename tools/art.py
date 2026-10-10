# -*- coding: utf-8 -*-
"""学科配图：用程序生成的 SVG（只依赖标准库，输出是确定的）。

render(viz, hue) -> 完整的 <svg> 字符串；hue 是该学科的主色相（0~359）。
每个学科对应一幅"数学本身画出来的图"：素数螺旋、椭圆曲线、纽结、双曲树、元胞自动机……
"""
import math
import random

W, H = 480, 320


# ----------------------------------------------------------------------------
# 小工具
# ----------------------------------------------------------------------------
def n1(x):
    s = "%.1f" % x
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


def hsl(h, s, l, a=None):
    h = int(round(h)) % 360
    if a is None:
        return "hsl(%d,%d%%,%d%%)" % (h, s, l)
    return "hsla(%d,%d%%,%d%%,%.2f)" % (h, s, l, a)


def frame(body, hue):
    c1, c2 = hsl(hue, 42, 11), hsl(hue + 30, 46, 21)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" aria-hidden="true" preserveAspectRatio="xMidYMid slice">'
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
        '<radialGradient id="gl" cx="0.5" cy="0.5" r="0.62"><stop offset="0" stop-color="%s" stop-opacity="0.30"/><stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient></defs>'
        '<rect width="%d" height="%d" fill="url(#bg)"/><rect width="%d" height="%d" fill="url(#gl)"/>%s</svg>'
        % (W, H, c1, c2, hsl(hue + 20, 85, 60), hsl(hue, 80, 50), W, H, W, H, body)
    )


def runs_paths(grid, cols, rows, cell, colorfn, ox=0.0, oy=0.0, gap=0.0):
    """grid[j][i] 是类别（None 表示不画）；同一行里相邻的同类格子合并成一个矩形。gap 让每个方块略小一点，留出缝隙。"""
    byc = {}
    for j in range(rows):
        row = grid[j]
        i = 0
        while i < cols:
            c = row[i]
            if c is None:
                i += 1
                continue
            s = i
            while i < cols and row[i] == c:
                i += 1
            w = (i - s) * cell - gap
            byc.setdefault(c, []).append("M%s %sh%sv%sh-%sz" % (n1(ox + s * cell), n1(oy + j * cell), n1(w), n1(cell - gap), n1(w)))
    return "".join('<path d="%s" fill="%s"/>' % ("".join(v), colorfn(c)) for c, v in sorted(byc.items(), key=lambda kv: str(kv[0])))


def poly(points, close=False):
    d = "M" + "L".join("%s %s" % (n1(x), n1(y)) for x, y in points)
    return d + ("Z" if close else "")


# ----------------------------------------------------------------------------
# 1 数论：Ulam 素数螺旋
# ----------------------------------------------------------------------------
def ulam(hue):
    cell = 4
    cols, rows = W // cell, H // cell
    N = 14600
    sv = bytearray([1]) * (N + 2)
    sv[0] = sv[1] = 0
    for i in range(2, int(N ** 0.5) + 1):
        if sv[i]:
            sv[i * i::i] = bytearray(len(sv[i * i::i]))
    grid = [[None] * cols for _ in range(rows)]
    x = y = 0
    dx, dy = 1, 0
    seg, left, turns = 1, 1, 0
    cx, cy = cols // 2, rows // 2
    for n in range(1, N + 1):
        gx, gy = cx + x, cy + y
        if 0 <= gx < cols and 0 <= gy < rows and sv[n]:
            grid[gy][gx] = min(5, n * 6 // N)
        x += dx
        y += dy
        left -= 1
        if left == 0:
            dx, dy = -dy, dx
            turns += 1
            if turns % 2 == 0:
                seg += 1
            left = seg
    return runs_paths(grid, cols, rows, cell, lambda b: hsl(hue + b * 16, 92, 70), 0.5, 0.5, 1.0)


# ----------------------------------------------------------------------------
# 2 代数：模 n 乘法表（素数模 = 域；合数模 = 有零因子）
# ----------------------------------------------------------------------------
def cayley(hue):
    out = []
    cell = 6
    for n, ox in ((31, 40), (30, 40 + 31 * cell + 30)):
        grid = [[(i * j) % n for j in range(n)] for i in range(n)]
        oy = (H - n * cell) / 2.0

        def col(v, n=n):
            if v == 0:
                return hsl(hue, 30, 7)
            return hsl(hue + 300.0 * v / n, 78, 36 + 30.0 * v / n)

        out.append(runs_paths(grid, n, n, cell, col, ox, oy))
    return "".join(out)


# ----------------------------------------------------------------------------
# 3 代数几何：椭圆曲线族与"弦切法"
# ----------------------------------------------------------------------------
def _cubic_roots(a, b):
    f = lambda x: x ** 3 + a * x + b
    roots = []
    prev_x, prev_f = -8.0, f(-8.0)
    for i in range(1, 1601):
        x = -8.0 + i * 0.01
        fx = f(x)
        if prev_f == 0:
            roots.append(prev_x)
        elif prev_f * fx < 0:
            lo, hi = prev_x, x
            for _ in range(60):
                mid = (lo + hi) / 2
                if f(lo) * f(mid) <= 0:
                    hi = mid
                else:
                    lo = mid
            roots.append((lo + hi) / 2)
        prev_x, prev_f = x, fx
    return sorted(roots)


def elliptic(hue):
    S = 50.0
    ox, oy = W / 2 + 6, H / 2
    ymax = (H / 2) / S * 0.98
    X = lambda x: ox + S * x
    Y = lambda y: oy - S * y
    a = -3.0
    out = []
    g = []
    for i in range(-9, 10):
        gx = X(i)
        if 0 < gx < W:
            g.append("M%s 0V%d" % (n1(gx), H))
    for j in range(-3, 4):
        g.append("M0 %sH%d" % (n1(Y(j)), W))
    out.append('<path d="%s" stroke="%s" stroke-width="0.7" fill="none"/>' % ("".join(g), hsl(hue, 30, 80, 0.10)))
    out.append('<path d="M0 %sH%d M%s 0V%d" stroke="%s" stroke-width="1.1" fill="none"/>' % (n1(Y(0)), W, n1(X(0)), H, hsl(hue, 30, 85, 0.28)))
    bs = [-1.5, -0.7, 0.2, 0.9, 1.6, 2.5]
    for k, b in enumerate(bs):
        f = lambda x, b=b: x ** 3 + a * x + b
        rts = _cubic_roots(a, b)
        comps = []
        if len(rts) >= 3:
            comps.append((rts[0], rts[1], True))
            comps.append((rts[2], None, False))
        elif rts:
            comps.append((rts[0], None, False))
        col = hsl(hue + 30 + 26 * k, 86, 66)
        for r0, r1, closed in comps:
            if r1 is None:
                lo, hi = r0, 12.0
                for _ in range(60):
                    mid = (lo + hi) / 2
                    if f(mid) < ymax * ymax:
                        lo = mid
                    else:
                        hi = mid
                r1 = hi
            L = r1 - r0
            pts = []
            N = 90
            for i in range(N + 1):
                th = -math.pi + 2 * math.pi * i / N
                x = r0 + L * (1 - math.cos(th)) / 2
                y = math.copysign(math.sqrt(max(f(x), 0.0)), th)
                pts.append((X(x), Y(y)))
            out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="2.2" stroke-linejoin="round"/>' % (
                poly(pts, closed), hsl(hue + 30 + 26 * k, 86, 66, 0.10) if closed else "none", col))
    # 弦切法：直线与曲线交于 P、Q、R，加法 P+Q 是 R 关于 x 轴的对称点
    b = 0.9
    f = lambda x: x ** 3 + a * x + b
    x1, x2 = -1.5, 2.0
    y1, y2 = math.sqrt(f(x1)), math.sqrt(f(x2))
    m = (y2 - y1) / (x2 - x1)
    x3 = m * m - x1 - x2
    y3 = y1 + m * (x3 - x1)
    xa, xb = -3.6, 3.6
    out.append('<path d="M%s %sL%s %s" stroke="%s" stroke-width="1.4" fill="none" stroke-dasharray="5 4"/>' % (
        n1(X(xa)), n1(Y(y1 + m * (xa - x1))), n1(X(xb)), n1(Y(y1 + m * (xb - x1))), hsl(hue + 200, 20, 92, 0.85)))
    out.append('<path d="M%s %sL%s %s" stroke="%s" stroke-width="1.2" fill="none" stroke-dasharray="2 3"/>' % (
        n1(X(x3)), n1(Y(y3)), n1(X(x3)), n1(Y(-y3)), hsl(hue + 200, 20, 92, 0.6)))
    for (px, py, c, r) in ((x1, y1, hsl(hue + 200, 20, 96), 4.5), (x2, y2, hsl(hue + 200, 20, 96), 4.5), (x3, y3, hsl(hue + 200, 20, 96), 4.5), (x3, -y3, hsl(hue + 50, 100, 70), 5.5)):
        out.append('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="1.2"/>' % (n1(X(px)), n1(Y(py)), r, c, hsl(hue, 40, 12)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 4 拓扑：三叶结（先画远处的线段，近处的盖在上面，才有"上下穿过"的感觉）
# ----------------------------------------------------------------------------
def knot(hue):
    """三叶结。先把整条曲线画一遍，再在每个交叉点处把"在上面的那一股"补画一小段，这样才有上下穿过的感觉。"""
    N = 360
    S = 50.0
    ox, oy = W / 2, H / 2
    P = []
    for i in range(N):
        t = 2 * math.pi * i / N
        r = 2 + math.cos(3 * t)
        P.append((ox + S * r * math.cos(2 * t), oy + S * r * math.sin(2 * t), math.sin(3 * t)))

    def inter(i, j):
        p, q, r_, s = P[i], P[(i + 1) % N], P[j], P[(j + 1) % N]
        d1x, d1y, d2x, d2y = q[0] - p[0], q[1] - p[1], s[0] - r_[0], s[1] - r_[1]
        den = d1x * d2y - d1y * d2x
        if abs(den) < 1e-12:
            return None
        ex, ey = r_[0] - p[0], r_[1] - p[1]
        u = (ex * d2y - ey * d2x) / den
        v = (ex * d1y - ey * d1x) / den
        if 0 <= u < 1 and 0 <= v < 1:
            return u, v
        return None

    centers = []
    for i in range(N):
        for j in range(i + 2, N):
            if i == 0 and j == N - 1:
                continue
            uv = inter(i, j)
            if uv:
                u, v = uv
                za = P[i][2] + u * (P[(i + 1) % N][2] - P[i][2])
                zb = P[j][2] + v * (P[(j + 1) % N][2] - P[j][2])
                centers.append(i if za > zb else j)

    edge = hsl(hue, 42, 13)
    col = lambda i: hsl(hue + 360.0 * (i % N) / N, 86, 62)

    def seg_d(i0, i1):  # 从第 i0 个点画到第 i1 个点（按圈取模）
        return poly([(P[k % N][0], P[k % N][1]) for k in range(i0, i1 + 1)])

    def colored(i0, i1, G=3):
        res = []
        for a in range(i0, i1 + 1, G):
            b = min(a + G, i1 + 1)
            res.append('<path d="%s" stroke="%s" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' % (seg_d(a, b), col(a)))
        return res

    out = ['<path d="%s" stroke="%s" stroke-width="12" stroke-linejoin="round" fill="none"/>' % (poly([(p[0], p[1]) for p in P], True), edge)]
    out += colored(0, N - 1)
    for c in centers:
        out.append('<path d="%s" stroke="%s" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" fill="none"/>' % (seg_d(c - 5, c + 6), edge))
        out += colored(c - 8, c + 9)
    return "".join(out)


# ----------------------------------------------------------------------------
# 5 群论：自由群 F2 的 Cayley 图，画在双曲圆盘里（边是测地线）
# ----------------------------------------------------------------------------
def _geodesic(p, q, R, cx, cy):
    ax, ay = cx + R * p.real, cy - R * p.imag
    bx, by = cx + R * q.real, cy - R * q.imag
    cross = p.real * q.imag - p.imag * q.real
    if abs(cross) < 1e-9:
        return "M%s %sL%s %s" % (n1(ax), n1(ay), n1(bx), n1(by))
    pp = p / (abs(p) ** 2)

    def circ(z1, z2, z3):
        x1, y1, x2, y2, x3, y3 = z1.real, z1.imag, z2.real, z2.imag, z3.real, z3.imag
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        s1, s2, s3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
        ux = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / d
        uy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / d
        return complex(ux, uy)

    try:
        c = circ(p, q, pp)
    except ZeroDivisionError:
        return "M%s %sL%s %s" % (n1(ax), n1(ay), n1(bx), n1(by))
    rad = abs(p - c) * R
    cxs, cys = cx + R * c.real, cy - R * c.imag
    z = (ax - cxs) * (by - cys) - (ay - cys) * (bx - cxs)
    return "M%s %sA%s %s 0 0 %d %s %s" % (n1(ax), n1(ay), n1(rad), n1(rad), 1 if z > 0 else 0, n1(bx), n1(by))


def freetree(hue):
    tau = math.tanh(1.0 / 2)
    R, cx, cy = 150.0, W / 2, H / 2
    maxd = 5

    def apply(M, z):
        a, b, c, d = M
        return (a * z + b) / (c * z + d)

    def mul(M, Nn):
        a, b, c, d = M
        e, f, g, h = Nn
        return (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)

    def T(phi):
        t = tau * complex(math.cos(phi), math.sin(phi))
        return (1, t, t.conjugate(), 1)

    levels = [[] for _ in range(maxd + 1)]

    def rec(M, back, depth):
        p = apply(M, 0j)
        for k in range(4):
            phi = k * math.pi / 2
            if back is not None and abs(((phi - back + math.pi) % (2 * math.pi)) - math.pi) < 1e-6:
                continue
            M2 = mul(M, T(phi))
            q = apply(M2, 0j)
            levels[depth].append(_geodesic(p, q, R, cx, cy))
            if depth < maxd:
                rec(M2, phi + math.pi, depth + 1)

    rec((1, 0j, 0j, 1), None, 0)
    out = ['<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="1.2"/>' % (n1(cx), n1(cy), n1(R), hsl(hue, 40, 80, 0.25))]
    widths = [2.4, 1.9, 1.5, 1.1, 0.8, 0.55]
    for d, segs in enumerate(levels):
        out.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round"/>' % ("".join(segs), hsl(hue + 22 * d, 88, 68), widths[d]))
    return "".join(out)


# ----------------------------------------------------------------------------
# 6 数理逻辑：规则 110（图灵完备的元胞自动机）
# ----------------------------------------------------------------------------
def rule110(hue):
    cell = 4
    cols, rows = W // cell, H // cell
    rnd = random.Random(110)
    row = [1 if rnd.random() < 0.45 else 0 for _ in range(cols)]
    grid = []
    for r in range(rows):
        grid.append([(r * 6 // rows) if v else None for v in row])
        row = [(110 >> (4 * row[(i - 1) % cols] + 2 * row[i] + row[(i + 1) % cols])) & 1 for i in range(cols)]
    return runs_paths(grid, cols, rows, cell, lambda b: hsl(hue + b * 20, 84, 62))


# ----------------------------------------------------------------------------
# 7 微分几何：环面（有正曲率，也有负曲率）
# ----------------------------------------------------------------------------
def mesh(hue):
    R, r = 1.5, 0.62
    nu, nv = 40, 16
    tilt = math.radians(62)
    S = 62.0
    ox, oy = W / 2, H / 2 + 4
    ct, st = math.cos(tilt), math.sin(tilt)

    def P(u, v):
        x = (R + r * math.cos(v)) * math.cos(u)
        y = (R + r * math.cos(v)) * math.sin(u)
        z = r * math.sin(v)
        return (x, y * ct - z * st, y * st + z * ct)

    L = (-0.4, -0.5, 0.77)
    nl = math.sqrt(sum(c * c for c in L))
    L = tuple(c / nl for c in L)
    quads = []
    for i in range(nu):
        u0, u1 = 2 * math.pi * i / nu, 2 * math.pi * (i + 1) / nu
        for j in range(nv):
            v0, v1 = 2 * math.pi * j / nv, 2 * math.pi * (j + 1) / nv
            p00, p10, p11, p01 = P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)
            ux, uy, uz = p10[0] - p00[0], p10[1] - p00[1], p10[2] - p00[2]
            wx, wy, wz = p01[0] - p00[0], p01[1] - p00[1], p01[2] - p00[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            nn = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            sh = abs((nx * L[0] + ny * L[1] + nz * L[2]) / nn)
            depth = (p00[1] + p10[1] + p11[1] + p01[1]) / 4
            quads.append((depth, sh, j, (p00, p10, p11, p01)))
    quads.sort(key=lambda q: -q[0])
    out = []
    for depth, sh, j, ps in quads:
        d = poly([(ox + S * p[0], oy - S * p[2]) for p in ps], True)
        fill = hsl(hue + 40.0 * j / nv, 72, 20 + 48 * sh)
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="0.5"/>' % (d, fill, hsl(hue, 50, 10, 0.45)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 8 凸几何：点集的"凸壳洋葱"
# ----------------------------------------------------------------------------
def _hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def onion(hue):
    rnd = random.Random(7)
    pts = []
    while len(pts) < 120:
        x, y = rnd.gauss(0, 1), rnd.gauss(0, 1)
        if x * x + y * y <= 6.5:
            pts.append((round(W / 2 + x * 68, 1), round(H / 2 + y * 44, 1)))
    rest = list(set(pts))
    layers = []
    while len(rest) >= 3:
        h = _hull(rest)
        if len(h) < 3:
            break
        layers.append(h)
        hs = set(h)
        rest = [p for p in rest if p not in hs]
    out = []
    for k, h in enumerate(layers):
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="1.7" stroke-linejoin="round"/>' % (
            poly(h, True), hsl(hue + 17 * k, 80, 62, 0.08), hsl(hue + 17 * k, 84, 66)))
    for x, y in pts:
        out.append('<circle cx="%s" cy="%s" r="2" fill="%s"/>' % (n1(x), n1(y), hsl(hue + 180, 25, 94, 0.9)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 9 偏微分方程：三个点源的波干涉
# ----------------------------------------------------------------------------
def waves(hue):
    cell = 6
    cols, rows = W // cell, H // cell
    src = [(0.27, 0.36), (0.58, 0.72), (0.82, 0.30)]
    k = 0.40
    levels = 14
    vals = []
    for j in range(rows):
        row = []
        for i in range(cols):
            x, y = i * cell + cell / 2.0, j * cell + cell / 2.0
            v = 0.0
            for sx, sy in src:
                r = math.hypot(x - sx * W, y - sy * H)
                v += math.cos(k * r) / math.sqrt(1 + r / 22.0)
            row.append(v)
        vals.append(row)
    lo, hi = min(min(r) for r in vals), max(max(r) for r in vals)
    grid = [[max(0, min(levels - 1, int((v - lo) / (hi - lo) * levels))) for v in row] for row in vals]
    return runs_paths(grid, cols, rows, cell, lambda c: hsl(hue + 90.0 * c / levels, 78, 10 + 62.0 * (c / float(levels - 1)) ** 1.4))


# ----------------------------------------------------------------------------
# 10 复分析：域着色（色相 = 辐角，明暗条纹 = 模长的对数）
# ----------------------------------------------------------------------------
def domain(hue):
    cell = 5
    cols, rows = W // cell, H // cell
    grid = []
    for j in range(rows):
        row = []
        for i in range(cols):
            z = complex(-3.6 + 7.2 * (i + 0.5) / cols, 2.4 - 4.8 * (j + 0.5) / rows)
            try:
                w = (z * z - 1) * (z - complex(2, 1)) ** 2 / (z * z + complex(2, 2))
                ang = math.atan2(w.imag, w.real)
                hq = int((ang / (2 * math.pi) + 0.5) * 36) % 36
                m = abs(w)
                lq = int(((math.log2(m) % 1.0) if m > 0 else 0.0) * 4)
                row.append((hq, lq))
            except ZeroDivisionError:
                row.append(None)
        grid.append(row)
    return runs_paths(grid, cols, rows, cell, lambda c: hsl(hue + c[0] * 10, 80, 30 + 9 * c[1]))


# ----------------------------------------------------------------------------
# 11 泛函分析：l^p 单位球（p<1 时不再是范数）
# ----------------------------------------------------------------------------
def lp(hue):
    S = 118.0
    ox, oy = W / 2, H / 2
    out = ['<path d="M%s %sH%s M%s %sV%s" stroke="%s" stroke-width="1" fill="none"/>' % (
        n1(ox - 190), n1(oy), n1(ox + 190), n1(ox), n1(oy - 150), n1(oy + 150), hsl(hue, 30, 85, 0.3))]
    ps = [None, 6, 3, 2, 1.5, 1, 0.5]
    for k, p in enumerate(ps):
        pts = []
        N = 260
        for i in range(N):
            t = 2 * math.pi * i / N
            c, s = math.cos(t), math.sin(t)
            if p is None:
                m = max(abs(c), abs(s))
                x, y = c / m, s / m
            else:
                e = 2.0 / p
                x, y = math.copysign(abs(c) ** e, c), math.copysign(abs(s) ** e, s)
            pts.append((ox + S * x, oy - S * y))
        out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>' % (
            poly(pts, True), hsl(hue + 24 * k, 80, 60, 0.10), hsl(hue + 24 * k, 88, 68), 2.4 if p in (1, 2) else 1.6))
    return "".join(out)


# ----------------------------------------------------------------------------
# 12 动力系统：逻辑斯蒂映射的分岔图
# ----------------------------------------------------------------------------
def bifurcation(hue):
    rlo, rhi = 2.85, 4.0
    cols = 380
    ox, ow = 12, W - 24
    seen = {}
    for i in range(cols):
        r = rlo + (rhi - rlo) * i / (cols - 1)
        x = 0.5
        for _ in range(300):
            x = r * x * (1 - x)
        px = int(round(ox + ow * i / (cols - 1.0)))
        for _ in range(60):
            x = r * x * (1 - x)
            py = int(round(H - 14 - (H - 28) * x))
            seen[(px, py)] = i
    bands = {}
    for (px, py), i in seen.items():
        bands.setdefault(i * 8 // cols, []).append("M%d %dh1" % (px, py))
    out = []
    for b in sorted(bands):
        out.append('<path d="%s" stroke="%s" stroke-width="1.3" fill="none"/>' % ("".join(bands[b]), hsl(hue + 18 * b, 90, 68)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 13 组合学：17 个点的 Paley 着色（Ramsey 数 R(4,4)=18 的极端例子）
# ----------------------------------------------------------------------------
def ramsey(hue):
    n = 17
    R = 142.0
    cx, cy = W / 2, H / 2
    qr = set((i * i) % n for i in range(1, n))
    pos = [(cx + R * math.cos(2 * math.pi * k / n - math.pi / 2), cy + R * math.sin(2 * math.pi * k / n - math.pi / 2)) for k in range(n)]
    A, B = [], []
    for i in range(n):
        for j in range(i + 1, n):
            seg = "M%s %sL%s %s" % (n1(pos[i][0]), n1(pos[i][1]), n1(pos[j][0]), n1(pos[j][1]))
            (A if (j - i) % n in qr else B).append(seg)
    out = ['<path d="%s" stroke="%s" stroke-width="1.4" fill="none"/>' % ("".join(B), hsl(hue + 55, 92, 66, 0.55))]
    out.append('<path d="%s" stroke="%s" stroke-width="1.4" fill="none"/>' % ("".join(A), hsl(hue + 200, 92, 74, 0.55)))
    for x, y in pos:
        out.append('<circle cx="%s" cy="%s" r="5" fill="%s" stroke="%s" stroke-width="1.5"/>' % (n1(x), n1(y), hsl(hue, 30, 96), hsl(hue, 45, 12)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 14 理论计算机科学：16 路双调排序网络
# ----------------------------------------------------------------------------
def sortnet(hue):
    n = 16
    comps = []
    stage = 0
    k = 2
    while k <= n:
        j = k // 2
        while j >= 1:
            for i in range(n):
                l = i ^ j
                if l > i:
                    comps.append((stage, i, l, j))
            stage += 1
            j //= 2
        k *= 2
    nst = stage
    left, right = 20.0, W - 20.0
    top = 24.0
    gap = (H - 48.0) / (n - 1)
    colw = (right - left - 20.0) / nst
    out = ['<path d="%s" stroke="%s" stroke-width="1.2" fill="none"/>' % (
        "".join("M%s %sH%s" % (n1(left), n1(top + i * gap), n1(right)) for i in range(n)), hsl(hue, 30, 85, 0.35))]
    for st_i in range(nst):
        lines, dots = [], []
        for (s, i, l, j) in comps:
            if s != st_i:
                continue
            x = left + 10 + colw * s + colw * (0.12 + 0.76 * ((i % j) / float(j) if j > 1 else 0.5))
            y0, y1 = top + i * gap, top + l * gap
            lines.append("M%s %sV%s" % (n1(x), n1(y0), n1(y1)))
            dots.append((x, y0))
            dots.append((x, y1))
        col = hsl(hue + 300.0 * st_i / nst, 86, 66)
        out.append('<path d="%s" stroke="%s" stroke-width="2.2" fill="none" stroke-linecap="round"/>' % ("".join(lines), col))
        out.append('<path d="%s" stroke="%s" stroke-width="5.5" fill="none" stroke-linecap="round"/>' % ("".join("M%s %sh0" % (n1(x), n1(y)) for x, y in dots), col))
    return "".join(out)


# ----------------------------------------------------------------------------
# 15 概率与统计力学：临界渗流（p = 1/2 的键渗流），最大的簇高亮
# ----------------------------------------------------------------------------
def percolation(hue):
    cols, rows, cell = 48, 32, 10
    ox, oy = (W - (cols - 1) * cell) / 2.0, (H - (rows - 1) * cell) / 2.0

    def build(seed):
        rnd = random.Random(seed)
        parent = list(range(cols * rows))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        edges = []
        for j in range(rows):
            for i in range(cols):
                v = j * cols + i
                for dv, ok in ((1, i + 1 < cols), (cols, j + 1 < rows)):
                    if ok and rnd.random() < 0.5:
                        edges.append((v, v + dv))
                        ra, rb = find(v), find(v + dv)
                        if ra != rb:
                            parent[ra] = rb
        return edges, find

    chosen = None
    for seed in range(1, 400):
        edges, find = build(seed)
        size = {}
        for v in range(cols * rows):
            r = find(v)
            size[r] = size.get(r, 0) + 1
        big = max(size, key=size.get)
        xs = [v % cols for v in range(cols * rows) if find(v) == big]
        ys = [v // cols for v in range(cols * rows) if find(v) == big]
        chosen = (edges, find, size, big)
        if min(xs) == 0 and max(xs) == cols - 1 and min(ys) == 0 and max(ys) == rows - 1:
            break
    edges, find, size, big = chosen
    groups = {0: [], 1: [], 2: []}
    for u, v in edges:
        r = find(u)
        g = 0 if r == big else (1 if size[r] >= 15 else 2)
        groups[g].append("M%s %sL%s %s" % (n1(ox + (u % cols) * cell), n1(oy + (u // cols) * cell), n1(ox + (v % cols) * cell), n1(oy + (v // cols) * cell)))
    out = ['<path d="%s" stroke="%s" stroke-width="1.2" fill="none" stroke-linecap="round"/>' % ("".join(groups[2]), hsl(hue, 20, 90, 0.22)),
           '<path d="%s" stroke="%s" stroke-width="1.8" fill="none" stroke-linecap="round"/>' % ("".join(groups[1]), hsl(hue + 170, 75, 62, 0.8)),
           '<path d="%s" stroke="%s" stroke-width="2.6" fill="none" stroke-linecap="round"/>' % ("".join(groups[0]), hsl(hue + 25, 95, 66))]
    return "".join(out)


# ----------------------------------------------------------------------------
# 16 算子代数：随机矩阵与半圆律
# ----------------------------------------------------------------------------
def _jacobi_eigs(A, sweeps=14):
    n = len(A)
    A = [row[:] for row in A]
    for _ in range(sweeps):
        off = sum(A[i][j] ** 2 for i in range(n) for j in range(i + 1, n))
        if off < 1e-14:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = A[p][q]
                if abs(apq) < 1e-15:
                    continue
                theta = (A[q][q] - A[p][p]) / (2.0 * apq)
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = A[k][p], A[k][q]
                    A[k][p] = c * akp - s * akq
                    A[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = A[p][k], A[q][k]
                    A[p][k] = c * apk - s * aqk
                    A[q][k] = s * apk + c * aqk
    return [A[i][i] for i in range(n)]


def semicircle(hue):
    rnd = random.Random(16)
    n = 40
    first = None
    eigs = []
    for rep in range(6):
        A = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                v = rnd.gauss(0, 1) / math.sqrt(n)
                if i == j:
                    v *= math.sqrt(2.0)
                A[i][j] = A[j][i] = v
        if first is None:
            first = [row[:] for row in A]
        eigs.extend(_jacobi_eigs(A))
    out = []
    cell = 4.6
    ox, oy = 26.0, (H - n * cell) / 2.0
    grid = []
    for i in range(n):
        row = []
        for j in range(n):
            v = first[i][j] * math.sqrt(n)
            row.append(max(-4, min(4, int(round(v * 1.6)))))
        grid.append(row)

    def col(c):
        if c == 0:
            return hsl(hue, 20, 20)
        if c > 0:
            return hsl(hue + 30, 85, 38 + 7 * c)
        return hsl(hue + 190, 80, 38 + 7 * (-c))

    out.append(runs_paths(grid, n, n, cell, col, ox, oy))
    hx0, hx1 = 258.0, 458.0
    base = H - 52.0
    lo, hi = -2.6, 2.6
    nb = 22
    cnt = [0] * nb
    for e in eigs:
        b = int((e - lo) / (hi - lo) * nb)
        if 0 <= b < nb:
            cnt[b] += 1
    bw = (hx1 - hx0) / nb
    scale = 200.0
    total = float(len(eigs))
    bars = []
    for b in range(nb):
        dens = cnt[b] / total / ((hi - lo) / nb)
        h = dens * scale
        bars.append("M%s %sh%sv%sh-%sz" % (n1(hx0 + b * bw + 1), n1(base), n1(bw - 2), n1(-h), n1(bw - 2)))
    out.append('<path d="%s" fill="%s"/>' % ("".join(bars), hsl(hue + 190, 70, 56, 0.85)))
    pts = []
    for i in range(121):
        x = -2.0 + 4.0 * i / 120.0
        y = math.sqrt(max(4 - x * x, 0.0)) / (2 * math.pi)
        pts.append((hx0 + (x - lo) / (hi - lo) * (hx1 - hx0), base - y * scale))
    out.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.4"/>' % (poly(pts), hsl(hue + 40, 100, 74)))
    out.append('<path d="M%s %sH%s" stroke="%s" stroke-width="1.2"/>' % (n1(hx0), n1(base), n1(hx1), hsl(hue, 20, 90, 0.5)))
    return "".join(out)


# ----------------------------------------------------------------------------
# 17 数学物理：单摆的相图（摆动、旋转与分隔线）
# ----------------------------------------------------------------------------
def pendulum(hue):
    S = 34.0
    ox, oy = W / 2, H / 2
    X = lambda q: ox + S * q
    Y = lambda p: oy - S * p
    out = ['<path d="M0 %sH%d M%s 0V%d" stroke="%s" stroke-width="1" fill="none"/>' % (n1(oy), W, n1(ox), H, hsl(hue, 30, 85, 0.25))]
    for k, E in enumerate([-0.93, -0.8, -0.62, -0.4, -0.15, 0.1, 0.38, 0.66, 0.9]):
        qt = math.acos(-E)
        col = hsl(hue + 14 * k, 85, 66)
        for shift in (-2 * math.pi, 0.0, 2 * math.pi):
            up, dn = [], []
            N = 70
            for i in range(N + 1):
                th = math.pi * i / N
                q = qt * math.cos(th)
                p = math.sqrt(max(2 * (E + math.cos(q)), 0.0))
                up.append((X(q + shift), Y(p)))
                dn.append((X(q + shift), Y(-p)))
            out.append('<path d="%s" fill="%s" stroke="%s" stroke-width="1.8" stroke-linejoin="round"/>' % (
                poly(up + dn[::-1], True), hsl(hue + 14 * k, 85, 66, 0.05), col))
    for k, E in enumerate([1.25, 1.9, 2.8, 4.0, 5.4]):
        col = hsl(hue + 190 + 12 * k, 85, 66)
        upper, lower = [], []
        N = 200
        for i in range(N + 1):
            q = -7.5 + 15.0 * i / N
            p = math.sqrt(2 * (E + math.cos(q)))
            upper.append((X(q), Y(p)))
            lower.append((X(q), Y(-p)))
        out.append('<path d="%s %s" fill="none" stroke="%s" stroke-width="1.8"/>' % (poly(upper), poly(lower), col))
    sep1, sep2 = [], []
    for i in range(241):
        q = -7.5 + 15.0 * i / 240
        sep1.append((X(q), Y(2 * math.cos(q / 2))))
        sep2.append((X(q), Y(-2 * math.cos(q / 2))))
    out.append('<path d="%s %s" fill="none" stroke="%s" stroke-width="2.6"/>' % (poly(sep1), poly(sep2), hsl(hue + 60, 100, 90)))
    return "".join(out)


_VIZ = {
    "ulam": ulam, "cayley": cayley, "elliptic": elliptic, "knot": knot, "freetree": freetree, "rule110": rule110,
    "mesh": mesh, "onion": onion, "waves": waves, "domain": domain, "lp": lp, "bifurcation": bifurcation,
    "ramsey": ramsey, "sortnet": sortnet, "percolation": percolation, "semicircle": semicircle, "pendulum": pendulum,
}


def render(viz, hue):
    fn = _VIZ[viz.strip()]
    return frame(fn(hue), hue)
