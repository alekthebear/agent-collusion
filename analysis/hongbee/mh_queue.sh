#!/bin/zsh
# MH queue: pairs s1, ring s1, pairs s2, ring s2. Stops if a run costs more than $3
# (about 8x a normal run). WAIT_PID: an mh run already going; wait for it, check its
# cost, and skip it in the loop.
cd ~/collusion-sprint/hongbee-world || exit 1
PY=../agent-collusion/.venv/bin/python
LIMIT=3.0
COMMON=(--episodes 4 --tickets-per-day 1 --carryover --day1-extra priya,jordan --contradiction 1
        --contradiction-authors marcus,sam,priya,jordan --review-rule --verdict-feedback
        --merge-feedback --no-reviews-evaluated --ask none)

check_cost() {
  local id=$1 usage cost
  usage=$(ls -t results/pr-review/$id/run_*/llm_usage.jsonl | head -1)
  cost=$($PY -c "import json,sys; print(round(sum((json.loads(l).get('cost_usd') or 0) for l in open(sys.argv[1])),3))" $usage)
  echo "=== DONE $id $(date '+%H:%M:%S') cost \$$cost"
  if $PY -c "import sys; sys.exit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)" $cost $LIMIT; then
    echo "=== STOP: $id cost more than \$$LIMIT"; exit 2
  fi
}

done_ids=()
if [[ -n $WAIT_PID ]]; then
  echo "=== WAITING for $WAIT_ID (pid $WAIT_PID)"
  while kill -0 $WAIT_PID 2>/dev/null; do sleep 10; done
  episodes=$($PY -c "import json,glob,os; f=sorted(glob.glob('results/pr-review/$WAIT_ID/run_*/run.json'),key=os.path.getmtime)[-1]; print(len(json.load(open(f))['episodes']))")
  [[ $episodes == 4 ]] || { echo "=== FAILED $WAIT_ID ($episodes days)"; exit 1; }
  check_cost $WAIT_ID
  done_ids+=($WAIT_ID)
fi
for spec in "mh-pairs-s1 pairs4 1" "mh-ring-s1 ring4 1" "mh-pairs-s2 pairs4 2" "mh-ring-s2 ring4 2"; do
  parts=(${=spec}); id=$parts[1]; structure=$parts[2]; seed=$parts[3]
  (( ${done_ids[(Ie)$id]} )) && continue
  echo "=== START $id $(date '+%H:%M:%S')"
  $PY -m pr_review --id $id --structure $structure --seed $seed $COMMON || { echo "=== FAILED $id"; exit 1; }
  check_cost $id
done
echo "=== QUEUE DONE $(date '+%H:%M:%S')"
