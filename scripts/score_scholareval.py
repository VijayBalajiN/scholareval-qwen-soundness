"""Scores ScholarEval's own soundness review of an idea with the SAME judge, prompt and rubrics as our other systems
(thoughtlab's LLMRubricJudge, Qwen with thinking high). Reads from ScholarEval-results, writes to ScholarEval-results/scores.
Usage: score_scholareval.py ai_1 ai_2 ..."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
REPO = Path("/path/to/project/AIScientist-scholareval")
sys.path.insert(0, str(REPO))
for line in (REPO / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.split(" #")[0].strip().strip("'\""))
from thoughtlab.adapters.scholareval import ScholarEvalAdapter
from thoughtlab.aggregators.scholareval.judge import LLMRubricJudge
from thoughtlab.benchmarks import BENCHMARKS
from thoughtlab.llm.litellm_client import LiteLLMClient
from thoughtlab.llm.resilient import CallBudget, ResilientClient, Throttle

OUT = Path("/path/to/project/ScholarEval-results")
items = {i.id: i for i in ScholarEvalAdapter(BENCHMARKS["scholareval"].data_dir, "ai", ("soundness",)).items()}
llm = ResilientClient(LiteLLMClient("openrouter/qwen/qwen3.8-27b", reasoning_effort="high"), budget=CallBudget(120),
                      throttle=Throttle(3.0), timeout_s=480)
judge = LLMRubricJudge(llm, ("soundness",))
for idea in sys.argv[1:]:
    d = OUT / idea / "soundness"
    review = "\n\n".join((d / f).read_text().strip() for f in ("meta_review.md", "tldr_soundness.md") if (d / f).exists())
    item = items[idea]
    with ThreadPoolExecutor(4) as pool:
        scores = list(pool.map(lambda a: judge.score(item, review, a[1], f"scholareval#{a[0]}"), enumerate(item.rubrics)))
    rows = [{"statement": r.statement, "type": r.type, "severity": r.severity, "score": s} for r, s in zip(item.rubrics, scores)]
    json.dump({"idea": idea, "review_words": len(review.split()), "rubrics": rows}, open(OUT / "scores" / f"{idea}.json", "w"), indent=1)
    v = [s for s in scores if s is not None]
    print(f"{idea}: {len(v)}/{len(scores)} rubrics scored | mean {sum(v)/len(v):.2f} | covered(>=4) {sum(s>=4 for s in v)}/{len(v)} | score 1: {sum(s==1 for s in v)}/{len(v)} | review {len(review.split())} words")
