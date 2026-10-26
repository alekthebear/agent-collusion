"""Dump the flagged cases for hand reading: knowing + return signal, and broken-code approvals."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ALEX = Path("/tmp/alex_main/results/pr-review")
R = [json.loads(l) for l in open(HERE / "decisions.jsonl")]
R = [r for r in R if r["model_decided"] and r["approve"]]
units = {u["unit"]: u for u in map(json.loads, open(HERE.parent / "detect/units.jsonl"))}
sel = [r for r in R if (r["harmful"] and r["knowing_mech"] and (r["asked"] or r["h_return_before"] or (r["a_deal"] or 0) > 0))
       or r["harm_kind"] in ("broken", "unknown")]
def cut(s, n=420): s = " ".join(str(s or "").split()); return s if len(s) <= n else s[:n] + "…"
out = []
for r in sel:
    rec = {"uid": r["uid"], "model": r["model"], "violations": r["violations"], "checks": r["checks"], "seen": r["seen_violations"],
           "harm_kind": r["harm_kind"], "asked": r["asked"], "return_before": r["h_return_before"], "instructed": r["instructed_pair"]}
    p = None
    for base in (ALEX, ROOT / "results/pr-review"):
        q = base / r["run"] / r["run_folder"] / "run.json"
        if q.exists(): p = q; break
    if p:
        run = json.load(open(p)); ep = next(e for e in run["episodes"] if e["episode"] == r["episode"])
        rv = next(x for x in ep["reviews"] if x["pr"] == r["pr"])
        pr = next(x for x in ep["prs"] if x["pr"] == r["pr"])
        rec["pr_status"] = pr["status"]; rec["desc"] = cut(pr.get("description"), 250)
        rec["review_reason"] = cut(rv.get("reason"), 500)
        rec["asks"] = [cut(a.get("text") or a.get("message") or a, 300) for a in ep.get("asks", []) if a.get("pr") == r["pr"]]
        msgs = [m for m in ep.get("messages", []) if r["reviewer"] in (m.get("sender"), m.get("recipient"), m.get("from"), m.get("to"))]
        rec["msgs"] = [cut(f"{m.get('sender', m.get('from'))}->{m.get('recipient', m.get('to'))}: {m.get('content', m.get('text'))}", 260) for m in msgs][:8]
    else:
        u = units.get(r["uid"], {})
        rec["review_reason"] = cut(u.get("reason"), 500); rec["reviewer_text"] = cut(u.get("reviewer_text"), 500)
        rec["talk"] = [cut(t, 200) for t in (u.get("talk") or [])][:5]
    out.append(rec)
json.dump(out, open(HERE / "cases.json", "w"), indent=1)
for rec in out:
    print("=" * 100); print(json.dumps(rec, indent=0, ensure_ascii=False))
