# scripts

Used as-is for the runs, with local paths replaced by `/path/to/project` and `/path/to/scripts`; edit them for your machine.

- `start_lane.sh`: loads the project `.env` into the environment (it is never printed) and starts `run_lane.sh`.
- `run_lane.sh`: runs ScholarEval's soundness pipeline on the ideas given, one after another, with a spend limit read from the
  OpenRouter usage counter, retries for the two transient failures seen, resume from step 5 when steps 1-4 exist, and a lock per idea.
- `score_scholareval.py`: scores a finished review against the rubrics with our judge (needs our `thoughtlab` code, not in this repo).
- `build_publish.py` + `README_template.md`: rebuild this repo's `results/`, `comparison/` and README from the local run folders.
