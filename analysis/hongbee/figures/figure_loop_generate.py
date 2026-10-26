"""Figure: the feedback loop, minimal. Each row: what we changed (left) -> batch (center) -> what we found (right).
The finding of each row feeds the change of the next (diagonal arrow)."""
W, H = 1240, 820
A = "#1f6f6b"; AT = "#e6f1ef"; INK = "#1b1f1d"; MUT = "#6f7774"; LINE = "#d3d9d6"; GOLD = "#b07a14"; RED = "#b4432e"
F = 'font-family="Inter, Helvetica, Arial, sans-serif"'
o = []
def t(x, y, s, size=12, fill=INK, w=400, anchor="start", italic=False, ls=0):
    st = ' font-style="italic"' if italic else ""; lsp = f' letter-spacing="{ls}"' if ls else ""
    o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{w}" fill="{fill}" text-anchor="{anchor}"{st}{lsp}>{s}</text>')
def rect(x, y, w, h, fill="#fff", stroke=LINE, sw=1.2, rx=6):
    o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def path(d, stroke=MUT, sw=1.5, arrow=True, dash=""):
    m = ' marker-end="url(#ah)"' if arrow else ""; ds = f' stroke-dasharray="{dash}"' if dash else ""
    o.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{m}{ds} stroke-linecap="round" stroke-linejoin="round"/>')

o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}>')
o.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
o.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>')

LX, CXc, RX = 60, 560, 760          # left text start, spine x, right block start
t(LX, 40, "WHAT WE CHANGED", 11, MUT, 700, ls=1.4)
t(CXc, 40, "BATCH", 11, MUT, 700, "middle", ls=1.4)
t(RX, 40, "WHAT WE FOUND", 11, MUT, 700, ls=1.4)

rows = [
 ("B0", "Base paper, replicated", "Shi et al. 2026 · 14 runs",
  ["Two agents verify each other under", "a rule that cannot be met"],
  "every accept", "breaks the rule; harm never measured", False),
 ("B1", "PR-review game", "24 runs",
  ["+ explicit rules, hidden outcome check", "+ scripted trade asks, pressure"],
  "0 / 79", "asks rewarded; agents call it “a trap”", False),
 ("B2", "Realistic company", "8 runs",
  ["+ hours, Slack, shared history", "− tool-call budget and other test cues"],
  "33 → 20", "eval mentions; 0 / 9 approved without verifying", False),
 ("B3", "Reviewer rule, reciprocity", "6 runs + 2,470 forked verdicts",
  ["+ costly review policy, fixed pairs vs ring", "+ a forked chance of repayment"],
  "r ≤ 0", "no reciprocity; repayment makes no difference", False),
 ("B4", "Automated pipeline", "8 runs · 56 workdays",
  ["+ roles, weeks, no humans to escalate to", "+ shared lead-time metric, peer review"],
  "5 / 59", "harmful merges, all misreading, none knowing", False),
 ("B5", "Instructed colluders, detectors", "3 runs · 721 decisions",
  ["+ a pair told to cover for each other", "+ text, action, pooled, part-wise monitors"],
  "0 / 11", "knowing approvals even when told; part-wise flags 0", False),
 ("B6", "Base paper, re-analyzed", "5,000 public episodes",
  ["+ the three-part definition applied", "   to the original traces"],
  "66% → 0.05%", "of “collusion” survives harm, agreement, knowing", True),
]
Y0, RH = 90, 100
for k, (bid, name, meta, changed, num, numlab, core) in enumerate(rows):
    y = Y0 + k * RH
    # spine node
    o.append(f'<circle cx="{CXc}" cy="{y + 22}" r="17" fill="{AT if core else "#fff"}" stroke="{A}" stroke-width="{2 if core else 1.4}"/>')
    t(CXc, y + 26, bid, 11, A, 700, "middle")
    if k < len(rows) - 1:
        path(f"M{CXc} {y + 40} L{CXc} {y + RH + 4}", LINE, 1.6, arrow=False)
    t(CXc, y + 52, name, 12.5, INK, 700, "middle"); t(CXc, y + 66, meta, 10, MUT, 400, "middle")
    # changed (left)
    for j, s in enumerate(changed): t(LX, y + 18 + j * 17, s, 12, INK if not s.startswith("−") else RED, 400)
    # found (right)
    t(RX, y + 28, num, 22 if not core else 24, GOLD if core else A, 700)
    t(RX, y + 46, numlab, 11.5, INK, 500)
    # feedback arrow: from the finding to the next change
    if k < len(rows) - 1:
        path(f"M{RX - 8} {y + 60} C {RX - 220} {y + 100}, {LX + 460} {y + 86}, {LX + 250} {y + RH + 6}", A, 1.3, dash="4 3")
# caption-like footer
t(LX, Y0 + 7 * RH + 2, "Each batch ran on the setting the previous finding produced. Dashed arrows mark that dependence.", 11, MUT, 400, italic=True)
o.append('</svg>')
svg = "\n".join(o)
open("/home/claude/fig/figure_loop.svg", "w").write(svg)
open("/home/claude/fig/fig2.html", "w").write(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}</style></head><body>{svg}</body></html>')
print("ok")
