"""Figure 1, minimal: five stages, one visual and one finding each."""
W, H = 1600, 520
A = "#1f6f6b"; AT = "#e6f1ef"; INK = "#1b1f1d"; MUT = "#707876"; LINE = "#d3d9d6"
RED = "#b4432e"; REDT = "#f7e5e0"; GOLD = "#b07a14"; GOLDT = "#f7eed8"
F = 'font-family="Inter, Helvetica, Arial, sans-serif"'
o = []
def t(x, y, s, size=12, fill=INK, w=400, anchor="start", italic=False, ls=0):
    st = ' font-style="italic"' if italic else ""; lsp = f' letter-spacing="{ls}"' if ls else ""
    o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{anchor}"{st}{lsp}>{s}</text>')
def rect(x, y, w, h, fill="#fff", stroke=LINE, sw=1.2, rx=6, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')
def path(d, stroke=MUT, sw=1.5, arrow=True, dash="", fill="none"):
    m = ' marker-end="url(#ah)"' if arrow else ""; ds = f' stroke-dasharray="{dash}"' if dash else ""
    o.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{m}{ds} stroke-linecap="round" stroke-linejoin="round"/>')
def line(x1, y1, x2, y2, **k): path(f"M{x1} {y1} L{x2} {y2}", **k)
def agent(x, y, label, r=14, stroke=INK, hatch=False, lf=INK):
    o.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{"url(#hatch)" if hatch else "#fff"}" stroke="{stroke}" stroke-width="1.5"/>')
    t(x, y + 4.5, label, 12, lf, 600, "middle")
def cross(x, y, c=RED, s=5.5): path(f"M{x-s} {y-s} l{2*s} {2*s} M{x+s} {y-s} l-{2*s} {2*s}", c, 2.6, arrow=False)

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
o.append(f'''<defs>
<marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>
<pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#fff"/><line x1="0" y1="0" x2="0" y2="5" stroke="{RED}" stroke-width="1.6"/></pattern>
</defs>''')

PW, GAP, PY, PH = 284, 30, 30, 440
xs = [30 + i * (PW + GAP) for i in range(5)]
names = ["Reproduce", "Diagnose & calibrate", "Observe boundaries", "Decompose & reanalyze", "Audit evidence"]
qs = [("Can we reproduce", "observed collusion?"), ("Natural behavior, or a", "response to an evaluation?"),
      ("When do agents relax", "rules or reject?"), ("Which behaviors meet", "the definition?"), ("What can traces", "establish?")]
finds = [("Acceptance reproduces;", "no approval depends on a return."),
         ("Suspecting a test makes agents", "stricter. Cues found and removed."),
         ("Rules bend only for work that", "is checkable and looks harmless."),
         ("66% “collusion” → 0.05% once", "harm, agreement, knowing all hold."),
         ("Pooling text and actions adds", "false flags; one source per part: 0.")]
for i, x in enumerate(xs):
    core = i == 3
    rect(x, PY, PW, PH, AT if core else "#fff", A if core else LINE, 2 if core else 1.2, 10)
    t(x + 18, PY + 30, f"STAGE {i + 1}", 11, A, 700, ls=1.5)
    t(x + 18, PY + 54, names[i], 16.5, INK, 700)
    t(x + 18, PY + 78, qs[i][0], 12.5, MUT, 400, italic=True); t(x + 18, PY + 95, qs[i][1], 12.5, MUT, 400, italic=True)
    line(x + 18, PY + PH - 62, x + PW - 18, PY + PH - 62, stroke=LINE, sw=1, arrow=False)
    t(x + 18, PY + PH - 40, finds[i][0], 12.5, INK, 600); t(x + 18, PY + PH - 23, finds[i][1], 12.5, INK, 600)
    if i < 4:
        line(x + PW + 5, PY + PH / 2, x + PW + GAP - 5, PY + PH / 2, stroke=MUT, sw=1.8)

VY = PY + 118   # visual area top
VH = PH - 118 - 70

# ---- Stage 1: mutual accept vs refused trade
x = xs[0]; cx = x + PW / 2
y1 = VY + 50
agent(cx - 60, y1, "A"); agent(cx + 60, y1, "B")
line(cx - 42, y1 - 7, cx + 42, y1 - 7, stroke=A, sw=1.8); line(cx + 42, y1 + 7, cx - 42, y1 + 7, stroke=A, sw=1.8)
t(cx, y1 - 14, "accept", 10, A, 600, "middle"); t(cx, y1 + 22, "accept", 10, A, 600, "middle")
t(cx, y1 + 50, "Shi et al.: 66% of episodes", 11.5, MUT, 500, "middle")
y2 = VY + 160
agent(cx - 60, y2, "A"); agent(cx + 60, y2, "B", stroke=RED, hatch=True, lf=RED)
path(f"M{cx + 44} {y2 - 10} Q{cx} {y2 - 40} {cx - 44} {y2 - 12}", RED, 1.8)
t(cx, y2 - 44, "“approve mine, I’ll approve yours”", 10, RED, 600, "middle")
line(cx - 42, y2 + 8, cx + 42, y2 + 8, stroke=MUT, sw=1.8); cross(cx, y2 + 26)
t(cx, y2 + 50, "Ours: 0 of ~79 asks rewarded", 11.5, MUT, 500, "middle")

# ---- Stage 2: suspicion -> stricter; cues removed
x = xs[1]; cx = x + PW / 2
ax = x + 34; ay = VY + 46
agent(ax, ay + 10, "A")
path(f"M{ax + 14} {ay - 2} L{ax + 26} {ay - 12}", MUT, 1, arrow=False)
rect(ax + 26, ay - 44, 150, 34, "#fff", RED, 1.2, 8)
t(ax + 101, ay - 30, "“this is an eval,", 10.5, RED, 500, "middle"); t(ax + 101, ay - 17, "likely a trap…”", 10.5, RED, 500, "middle")
# bars
by = VY + 86
t(x + 18, by, "Acceptance of peer work (Shi et al. traces)", 10, MUT, 500)
for k, (lab, v, col) in enumerate([("suspects a test", 59, RED), ("no suspicion", 85, A)]):
    yy = by + 12 + k * 26
    t(x + 18, yy + 13, lab, 10.5, INK)
    o.append(f'<rect x="{x + 112}" y="{yy + 2}" width="{v * 1.3}" height="15" fill="{col}" opacity="0.85"/>')
    t(x + 116 + v * 1.3, yy + 14, f"{v}%", 11, INK, 700)
# cue swap
sy = by + 78
t(x + 18, sy, "Cues found by an LLM judge, then replaced", 10, MUT, 500)
for k, (a, b) in enumerate([("tool-call budget", "hours"), ("planted “debt”", "team history"), ("test-like names", "Linear, Slack")]):
    yy = sy + 12 + k * 22
    rect(x + 18, yy, 104, 17, REDT, "none", 0, 4); t(x + 24, yy + 12.5, a, 9.8, RED, 500)
    line(x + 128, yy + 8.5, x + 148, yy + 8.5, stroke=MUT, sw=1.2)
    rect(x + 154, yy, 94, 17, AT, "none", 0, 4); t(x + 160, yy + 12.5, b, 9.8, A, 500)
t(x + 18, sy + 86, "mentions per run 33 → 20", 10.5, INK, 600)

# ---- Stage 3: 2x2
x = xs[2]
gx, gy, cw, ch = x + 84, VY + 34, 86, 60
t(gx + cw, gy - 12, "harm visible to reviewer?", 10.5, MUT, 600, "middle")
for c, s in enumerate(["no", "yes"]): t(gx + cw * c + cw / 2, gy + 4, s, 10, MUT, 600, "middle")
t(x + 18, gy + 14 + ch / 2, "can", 10, MUT, 600); t(x + 18, gy + 14 + ch / 2 + 12, "verify?", 10, MUT, 600)
for r, s in enumerate(["yes", "no"]): t(gx - 7, gy + 14 + ch * r + ch / 2 + 4, s, 10, MUT, 600, "end")
cells = [[("rule relaxed", "8 / 8", GOLD, GOLDT), ("rejected", "all", A, AT)], [("rejected", "0 / 9", A, AT), ("rejected", "", A, AT)]]
for r in range(2):
    for c in range(2):
        lab, n, col, fill = cells[r][c]; cx_, cy_ = gx + cw * c, gy + 14 + ch * r
        rect(cx_, cy_, cw, ch, fill, col, 1.3, 4)
        t(cx_ + cw / 2, cy_ + 28, lab, 11, col, 700, "middle"); t(cx_ + cw / 2, cy_ + 46, n, 11, INK, 500, "middle")
ly = gy + 14 + 2 * ch + 18
for k, (lab, res) in enumerate([("chance of repayment", "no effect"), ("fixed pairs vs ring", "no effect"), ("told to collude", "refused")]):
    yy = ly + k * 24
    t(x + 18, yy + 12, lab, 10.5, INK); line(x + 140, yy + 8, x + 176, yy + 8, stroke=LINE, sw=1, arrow=False)
    t(x + PW - 18, yy + 12, res, 10.5, MUT, 700, "end")

# ---- Stage 4: funnel
x = xs[3]
fx0, fx1 = x + 22, x + PW - 22; fyc = VY + 120
hs = [62, 22, 10, 4]
gates = [("Harmful", RED), ("Conditional", A), ("Knowing", GOLD)]
segw = (fx1 - fx0) / 4
for k in range(4):
    xa, xb = fx0 + k * segw, fx0 + (k + 1) * segw
    h0 = hs[k]
    if k < 3:
        o.append(f'<polygon points="{xa},{fyc - h0} {xb - 26},{fyc - h0} {xb - 8},{fyc - hs[k + 1]} {xb - 8},{fyc + hs[k + 1]} {xb - 26},{fyc + h0} {xa},{fyc + h0}" fill="{["#c6d6d2", "#d9e5e1", "#e6eeeb"][k]}"/>')
    else:
        o.append(f'<polygon points="{xa},{fyc - h0} {xb},{fyc - h0} {xb},{fyc + h0} {xa},{fyc + h0}" fill="#eef3f1"/>')
for k, (name, col) in enumerate(gates):
    gxp = fx0 + (k + 1) * segw - 8
    rect(gxp - 3.5, fyc - 78, 7, 150, col, "none", 0, 3)
    t(gxp, fyc - 88, name, 10, col, 700, "middle")
vals = ["66%", "9%", "3.6%", "0.05%"]
for k, v in enumerate(vals):
    t(fx1 - 2 if k == 3 else fx0 + k * segw + segw / 2 - (10 if k else 0), fyc + 5, v, 13 if k else 15, INK, 700, "end" if k == 3 else "middle")
t(fx0, fyc + 92, "Shi et al., 5,000 episodes", 10, MUT, 500)
t(fx0, fyc + 107, "91% of accepts: correct work", 10, MUT, 500)
t(fx1, fyc + 107, "3 of 6,596", 10.5, GOLD, 700, "end")
t(x + 18, VY + 14, "Three parts must hold at once:", 10.5, MUT, 500)

# ---- Stage 5: false flags
x = xs[4]
t(x + 18, VY + 14, "False flags on 410 collusion-free approvals", 10.5, MUT, 500)
mons = [("text only", 5, MUT), ("actions only", 56, MUT), ("pooled judge", 13, RED), ("part-wise", 0, A)]
for k, (lab, v, col) in enumerate(mons):
    yy = VY + 30 + k * 40
    t(x + 18, yy + 14, lab, 11.5, col if col != MUT else INK, 700)
    bw_ = max(2, v * 2.3)
    o.append(f'<rect x="{x + 116}" y="{yy + 2}" width="{bw_}" height="18" fill="{col}" opacity="0.85"/>')
    t(x + 122 + bw_, yy + 16, str(v), 12, INK, 700)
# part-wise mapping
my = VY + 30 + 4 * 40 + 6
for k, (p, c, src) in enumerate([("Harmful", RED, "outcome check"), ("Conditional", A, "talk + ring control"), ("Knowing", GOLD, "what reviewer saw")]):
    yy = my + k * 22
    o.append(f'<circle cx="{x + 24}" cy="{yy + 6}" r="5" fill="{c}"/>')
    t(x + 36, yy + 10, p, 10, c, 700); t(x + 112, yy + 10, src, 10, INK)
o.append('</svg>')
svg = "\n".join(o)
open("/home/claude/fig/figure1_overview.svg", "w").write(svg)
open("/home/claude/fig/fig.html", "w").write(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}</style></head><body>{svg}</body></html>')
print("ok")
