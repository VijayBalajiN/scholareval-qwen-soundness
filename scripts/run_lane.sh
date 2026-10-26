#!/bin/bash
# Runs ScholarEval's own SOUNDNESS pipeline (their run_soundness_pipeline, unmodified) from the pristine clone on the given
# ScholarIdeas folders, one after another. Keys are loaded from the project .env without being printed.
#   usage: run_scholareval_soundness.sh ai_1 ai_2 ...          env: EMAIL=<unpaywall email> (optional), CAP_IDEA=4 CAP_TOTAL=10 (USD)
set -u
PROJECT=/path/to/project
CLONE=$PROJECT/ScholarEval-clone
OUT=$PROJECT/ScholarEval-results
MODEL="qwen/qwen3.8-27b"
ABS_LIMIT=${ABS_LIMIT:?set ABS_LIMIT (usage counter value at which to stop)}; LANE=${LANE:-lane}

# Keys must already be in the environment (launch through start_scholareval.sh, which loads .env the way the app does:
# split on the first "=", strip spaces; the file is never sourced or printed).
for k in OPENROUTER_API_KEY S2_API_KEY; do [ -n "${!k:-}" ] || { echo "STOP: $k is not set in .env"; exit 2; }; done
export API_KEY="$OPENROUTER_API_KEY" API_KEY_1="$OPENROUTER_API_KEY" API_ENDPOINT="https://openrouter.ai/api/v1"
[ -n "${EMAIL:-}" ] && export email="$EMAIL"                      # Unpaywall (optional)
export PATH="$CLONE/.venv/bin:$PATH"                              # their steps call a bare `python`
curl -s -m 5 http://localhost:8070/api/isalive | grep -q true || { echo "STOP: GROBID is not answering on :8070"; exit 3; }

usage() { curl -s -m 20 -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/auth/key |
          python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["usage"])'; }
start_total=$(usage); echo "$(date +%T) [$LANE] start; spend counter $start_total, stop at $ABS_LIMIT" | tee -a "$OUT/progress.log"
if [ -n "${WAIT_PID:-}" ]; then echo "$(date +%T) [$LANE] waiting for pid $WAIT_PID" | tee -a "$OUT/progress.log"; while kill -0 $WAIT_PID 2>/dev/null; do sleep 20; done; fi
cd "$CLONE"
fails=0
for idea in "$@"; do
  [ -f "$OUT/$idea/soundness/tldr_soundness.md" ] && { echo "$idea already done, skipped" | tee -a "$OUT/progress.log"; continue; }
  mkdir -p "$OUT/$idea"; mkdir "$OUT/$idea/.lock" 2>/dev/null || { echo "[$LANE] $idea is taken by another lane, skipped" | tee -a "$OUT/progress.log"; continue; }
  cutoff=$(tr -d '[:space:]' < "ScholarIdeas/$idea/cutoff.txt"); before=$(usage)
  echo "$(date +%T) [$LANE] $idea cutoff=$cutoff" | tee -a "$OUT/progress.log"
  attempt=0
  while :; do
    attempt=$((attempt+1))
    D="$OUT/$idea/soundness"
    if [ -f "$D/methods_analysis.json" ] && [ ! -f "$D/tldr_soundness.md" ]; then LOG="$OUT/$idea/pipeline.resume$attempt.log"; else LOG="$OUT/$idea/pipeline.log"; fi
    if [ -f "$D/methods_analysis.json" ] && [ ! -f "$D/tldr_soundness.md" ]; then
      # Steps 1-4 already finished for this idea: run only steps 5-6, with the same commands their run_soundness_pipeline uses.
      echo "$(date +%T) [$LANE] $idea: steps 1-4 found, resuming at step 5 (meta review)" | tee -a "$OUT/progress.log"
      ( export PYTHONPATH="$CLONE"
        python -m ScholarEval.soundness.meta_review --research_plan "$D/research_plan.txt" --mr_analysis_file "$D/methods_analysis.json" \
          --methods_and_ref_file "$D/snippet_references.json" --output_file "$D/meta_review.json" --markdown_output "$D/meta_review.md" \
          --llm_engine_name "$MODEL" --cost_log_file "$D/soundness_costs.jsonl" &&
        python -m ScholarEval.soundness.tldr_soundness --input_file "$D/research_plan.txt" --meta_review_file "$D/meta_review.json" \
          --llm_engine_name "$MODEL" --output_file "$D/tldr_soundness.txt" --markdown_file "$D/tldr_soundness.md" --cost_log_file "$D/soundness_costs.jsonl"
      ) > "$LOG" 2>&1 &
    else
      python -c "import sys; from ScholarEval.ScholarEval import run_soundness_pipeline as run; sys.exit(0 if run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], None) else 1)" \
          "ScholarIdeas/$idea/$idea.txt" "$OUT/$idea" "$cutoff" "$MODEL" > "$LOG" 2>&1 &
    fi
    pid=$!
    while kill -0 $pid 2>/dev/null; do
      sleep 45; now=$(usage)
      if python3 -c "import sys; sys.exit(0 if $now > $ABS_LIMIT else 1)"; then
        echo "$(date +%T) [$LANE] STOP: key usage counter $now passed the limit $ABS_LIMIT while running $idea" | tee -a "$OUT/progress.log"
        pkill -P $pid; kill $pid 2>/dev/null; rmdir "$OUT/$idea/.lock" 2>/dev/null; exit 4
      fi
    done
    wait $pid; code=$?
    # Qwen sometimes spends its whole output budget thinking and returns no text; their code then sees "0 methods" and fails.
    if [ $code -ne 0 ] && grep -qE "for 0 methods|object has no attribute .get.|KeyError: 0" "$LOG" && [ $attempt -lt 3 ]; then
      echo "$(date +%T) [$LANE] $idea attempt $attempt: transient failure (empty model reply, or a Semantic Scholar 429 their code cannot read), retrying" | tee -a "$OUT/progress.log"
      continue
    fi
    break
  done
  after=$(usage)
  echo "$(date +%T) [$LANE] $idea exit=$code; counter moved \$$(python3 -c "print(round($after-$before,3))") during this idea (includes the other lane)" | tee -a "$OUT/progress.log"
  if [ $code -ne 0 ]; then
    fails=$((fails+1)); rmdir "$OUT/$idea/.lock" 2>/dev/null
    echo "$(date +%T) [$LANE] FAILED $idea (see $LOG); $fails failure(s) in a row" | tee -a "$OUT/progress.log"
    [ $fails -ge 3 ] && { echo "$(date +%T) [$LANE] STOP: 3 failures in a row, not spending more" | tee -a "$OUT/progress.log"; exit 5; }
  else fails=0; fi
done
echo "$(date +%T) [$LANE] all done" | tee -a "$OUT/progress.log"
