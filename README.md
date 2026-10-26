# ScholarEval's own pipeline vs. simple reviewers, with Qwen, on ScholarIdeas (AI, soundness)

This repo holds the outputs of running **ScholarEval's own soundness pipeline** ([paper](https://arxiv.org/abs/2510.16234),
[code](https://github.com/skai-research/ScholarEval), MIT) with `qwen/qwen3.8-27b` through OpenRouter on the 40 AI ideas of
**ScholarIdeas**, and scoring each review against the experts' soundness rubrics. The same rubrics and the same judge also score
four systems of our own (a plain LLM reviewer and six "thought experiment" agents, each in two prompt setups), so the numbers are
comparable. It is a **work in progress**: results are added here as each idea finishes (6 of 40 reviews done,
6 scored).

Not affiliated with the ScholarEval authors. Their pipeline, data and metric are theirs; see the licenses below.

## Results so far

Ideas scored so far: **6** of 40 (41 soundness rubrics). Every system is compared on exactly these rubrics.

| System | Mean score (1-5) | Covered (score 4-5) | Score 1 |
|---|---|---|---|
| ScholarEval pipeline (theirs) | **2.29** | 5 / 41 | 5 / 41 |
| plain reviewer, 2 briefs | **2.95** | 14 / 41 | 5 / 41 |
| plain reviewer, 1 brief | **2.61** | 11 / 41 | 7 / 41 |
| six agents, 2 briefs | **2.37** | 8 / 41 | 12 / 41 |
| six agents, 1 brief | **2.07** | 7 / 41 | 17 / 41 |

Rubric by rubric, against ScholarEval's own pipeline (higher / lower / equal score):

| System | Higher | Lower | Equal |
|---|---|---|---|
| plain reviewer, 2 briefs | 17 | 7 | 17 |
| plain reviewer, 1 brief | 17 | 13 | 11 |
| six agents, 2 briefs | 11 | 17 | 13 |
| six agents, 1 brief | 9 | 19 | 13 |

Mean score per idea:

| Idea | Rubrics | ScholarEval pipeline (theirs) | plain reviewer, 2 briefs | plain reviewer, 1 brief | six agents, 2 briefs | six agents, 1 brief |
|---|---|---|---|---|---|---|
| ai_1 | 9 | 1.89 | 3.22 | 3.00 | 2.67 | 2.56 |
| ai_2 | 8 | 2.12 | 3.12 | 2.25 | 2.38 | 1.62 |
| ai_3 | 6 | 2.33 | 2.00 | 1.83 | 1.50 | 1.17 |
| ai_4 | 5 | 2.20 | 2.20 | 2.00 | 1.80 | 2.20 |
| ai_5 | 5 | 2.60 | 2.40 | 3.00 | 2.60 | 3.20 |
| ai_6 | 8 | 2.75 | 4.00 | 3.25 | 2.88 | 1.88 |


**How to read the scores.** For each expert rubric statement (e.g. "the choice of X is unclear") a judge model reads the whole review
and gives 1-5 for how well the review expresses that statement: 1 = not mentioned, 3 = partly, 5 = clearly. The table's mean is the
average over rubrics, as in ScholarEval's own evaluation script. "Covered" (4 or 5) is our own extra cut-off. Soundness rubrics only:
the contribution rubrics and ScholarEval's contribution pipeline are not used.

## Please read before trusting the numbers

- **Small and early.** Few ideas so far; rubrics within an idea are not independent. Treat differences below about 0.3 as noise.
- **One judge, and it is the same model that wrote most reviews.** The judge is Qwen (thinking on) with ScholarEval's coverage rubric
  and a re-created Prometheus-style prompt (not their GPT-4o judge), so scores are close to, not comparable with, the paper's.
- **The "plain reviewer" is not a bare prompt.** It has no thought experiments, but it gets the same detailed task text as the agents
  (`prompts/`): check each part, ask whether it follows, whether it is supported, whether that is enough to prove it. That wording
  resembles what the experts write. A minimal-prompt control has not been run yet.
- **Setups differ.** ScholarEval's pipeline searches the literature (up to each idea's cutoff date) and runs Qwen at its default
  thinking setting; our systems use only the plan and the model's own knowledge, with thinking set to high.
- **Their pipeline needed local fixes to run with Qwen** (below). Their contribution half was not run.
- Reviews were produced under a shared, rate-limited Semantic Scholar key; failures and retries are in `results/*/pipeline.log`.

## What was run

| | |
|---|---|
| Their pipeline | `run_soundness_pipeline` from ScholarEval at commit `b8391a0`: extract methods, write queries, Semantic Scholar snippet search, download PDFs and parse them with GROBID, per-method synthesis, meta-review, TL;DR. |
| Model | `qwen/qwen3.8-27b` via OpenRouter, default sampling and thinking, for every step. |
| Services | Semantic Scholar API, GROBID (`lfoppiano/grobid:latest-crf`, 6 GB heap), Unpaywall. |
| Judge | Qwen, thinking high, ScholarEval's coverage criterion, 1-5 per rubric statement (`scripts/score_scholareval.py`). |
| Our systems | Plain reviewer; six thought-experiment agents (three kinds x two prompt styles); each with one or two briefs per idea. Their code is not in this repo; their per-rubric scores are in `comparison/per_rubric_scores.csv`. |

### Local edits to ScholarEval's code (`patches/scholareval-local-edits.diff`)

1. `utils/string_utils.py`, one line: Qwen's replies start with blank lines, which their JSON reader did not accept
   (`response.startswith` became `response.strip().startswith`).
2. `utils/semantic_scholar.py`: retry HTTP 429/5xx replies from Semantic Scholar with exponential backoff (their code read an
   error reply as data and crashed).

Also: their code waits for a Docker container built from the image tag `lfoppiano/grobid:latest-crf`, so GROBID has to run from that
tag, and it must have enough memory (the default Java heap ran out).

## Layout

- `results/ai_N/`: their final review (`meta_review.md`, `tldr_soundness.md`), extracted methods, queries, paper ids found, costs, run log.
- `scores/ai_N.json`: our judge's score for each rubric of that idea.
- `comparison/per_rubric_scores.csv`: every system's score on every rubric (blank = not run).
- `scripts/`: launcher, scorer and the script that builds this repo. `prompts/`: the plain reviewer's prompt and task text.
- `patches/`: the two local edits.

**Not included:** the downloaded paper PDFs, their parsed text and the retrieved snippets (third-party content), and any keys.

## Licenses and credits

- Our scripts and write-up: MIT (`LICENSE`).
- ScholarEval code and ScholarIdeas data (rubric statements are quoted in the comparison file): MIT, (c) 2025 skai-research.
- The reviews in `results/` are model output built on papers found via Semantic Scholar; links point to the papers.
- Cite the original: Moussa et al., "ScholarEval: Research Idea Evaluation Grounded in Literature", arXiv 2510.16234.
