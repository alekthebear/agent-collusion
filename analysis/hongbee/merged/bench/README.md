# Monitor benchmark (Track 2.2 and 2.3)

One monitor, four views of the same review decision, on decisions whose label we checked by hand.

## Set

`set.jsonl`, built by `build_set.py` from `../decisions.jsonl`. 109 scored decisions plus 11 left out as ambiguous.

| Case | What it is | A | B |
|---|---|---|---|
| coordinated | relaxed approval that carried out an agreement in talk | 23 | 15 |
| solo | relaxed approval under the same CI shortage, no agreement | 11 | 12 |
| talk_only | trade ask or deal in talk, decision by the rules | 9 | 21 |
| harm_alone | approval of broken code, no agreement | 1 | 2 |
| legit | approval after a rerun, no ask or deal | 8 | 7 |

Coordinated and ambiguous labels are hand-checked (`labels.json`). Split is by run. No view shows the golden verdict.

## Views

`monitor.py`: messages only, actions only, both raw, and a structured report of requests, replies, claims and actions.
`evaluate.py`: threshold picked on A, frozen, tested on B.

## Results on B

| View | GPT-5.4 mini AUROC | GPT-5.4 AUROC | GPT-5.4 recall | GPT-5.4 false positives |
|---|---|---|---|---|
| Messages only | 0.47 | 0.89 | 15/15 | 12/42 |
| Actions only | 0.62 | 0.92 | 11/15 | 5/42 |
| Messages + actions | 0.52 | 0.91 | 15/15 | 7/42 |
| Structured | 0.59 | 0.89 | 13/15 | 7/42 |

Figure: `../../figures/monitor_views_by_model.png` (`plot_views.py`).
