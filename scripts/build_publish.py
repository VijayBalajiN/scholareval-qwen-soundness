"""Builds/updates the public repo folder from ScholarEval-results and our runs. Idempotent. No network.
Copies only: their final reviews + small metadata + costs + (sanitised) pipeline log, our judge scores, comparison tables.
Never copies: downloaded paper PDFs, parsed paper text (GROBID XML), snippet text, .env, anything with a key."""
import csv, glob, json, re, shutil, statistics
from pathlib import Path
PROJECT = Path("/path/to/project")
RES, RUNS, STAGE = PROJECT / "ScholarEval-results", PROJECT / "AIScientist-scholareval" / "runs", PROJECT / "scholareval-qwen-soundness"
SCRATCH = Path(__file__).parent
KEEP = ("meta_review.md", "tldr_soundness.md", "methods.json", "queries.json", "snippet_references.json", "soundness_costs.jsonl")

def clean(text: str) -> str:
    text = text.replace(str(PROJECT), "<project>").replace("~", "~")
    text = re.sub(r"/private/tmp/claude-[^\s\"')]*", "<scratch>", text)
    text = re.sub(r"[\w.+-]+@iitd\.ac\.in", "<email>", text)
    return text

def done_ideas():
    return sorted((p.parent.parent.name for p in RES.glob("ai_*/soundness/tldr_soundness.md")), key=lambda n: int(n.split("_")[1]))

def copy_idea(idea):
    out = STAGE / "results" / idea; out.mkdir(parents=True, exist_ok=True)
    src = RES / idea / "soundness"
    for name in KEEP:
        if (src / name).exists(): (out / name).write_text(clean((src / name).read_text()))
    # the log of the run that produced the review: the last resume log if there is one, else the main log
    logs = sorted((RES / idea).glob("pipeline.resume*.log")) or [RES / idea / "pipeline.log"]
    if logs[-1].exists(): (out / "pipeline.log").write_text(clean(logs[-1].read_text())[-20000:])
    if (RES / "scores" / f"{idea}.json").exists():
        d = STAGE / "scores"; d.mkdir(exist_ok=True); (d / f"{idea}.json").write_text(clean((RES / "scores" / f"{idea}.json").read_text()))

def run_scores(tags, group="all"):
    o = {}
    for tag in tags:
        for folder in glob.glob(str(RUNS / f"*{tag}")):
            for line in open(folder + "/items.jsonl"):
                it = json.loads(line)
                for i, s in enumerate(it["metrics"]["groups"][group]["scores"]): o[(it["item_id"], i)] = s
    return o

SYSTEMS = {  # name -> (how it was run, the run folders it comes from)
    "ScholarEval pipeline (theirs)": None,
    "plain reviewer, 2 briefs": ["run5-qwen-baseline", "run8-qwen-baseline-ai6-40"],
    "plain reviewer, 1 brief": ["run13-single-baseline-ai1-40"],
    "six agents, 2 briefs": ["run4-sound-2briefs", "run9-qwen-agents-ai6-22", "run10b-resume-split-agents-ai23-40"],
    "six agents, 1 brief": ["run11-single-agents-ai1-20", "run12-single-agents-ai21-40"],
}

def build_tables(ideas):
    se = {}
    for idea in ideas:
        f = RES / "scores" / f"{idea}.json"
        if f.exists():
            for k, r in enumerate(json.load(open(f))["rubrics"]): se[(idea, k)] = r["score"]
    systems = {"ScholarEval pipeline (theirs)": se}
    for name, tags in SYSTEMS.items():
        if tags: systems[name] = run_scores(tags)
    scored = sorted({k[0] for k in se}, key=lambda n: int(n.split("_")[1]))
    keys = sorted(se, key=lambda k: (int(k[0].split("_")[1]), k[1]))
    meta = {}
    for line in open(next(iter(glob.glob(str(RUNS / "*run13-single-baseline-ai1-40"))[0:1])) + "/items.jsonl"):
        it = json.loads(line)
        for i, m in enumerate(it["metrics"]["rubric_meta"]): meta[(it["item_id"], i)] = m
    (STAGE / "comparison").mkdir(exist_ok=True)
    with open(STAGE / "comparison" / "per_rubric_scores.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["idea", "rubric", "type", "severity", "statement"] + list(systems))
        for k in sorted(set().union(*[set(s) for s in systems.values()]), key=lambda k: (int(k[0].split("_")[1]), k[1])):
            m = meta.get(k, {}); w.writerow([k[0], k[1], m.get("type", ""), m.get("severity", ""), m.get("statement", "")] + [systems[n].get(k, "") for n in systems])
    def stats(s, ks):
        v = [s[k] for k in ks if s.get(k) is not None]
        return (len(v), statistics.mean(v), sum(x >= 4 for x in v), sum(x == 1 for x in v)) if v else (0, 0, 0, 0)
    lines = [f"Ideas scored so far: **{len(scored)}** of 40 ({len(keys)} soundness rubrics). Every system is compared on exactly these rubrics.", "",
             "| System | Mean score (1-5) | Covered (score 4-5) | Score 1 |", "|---|---|---|---|"]
    for n, s in systems.items():
        c, m, cov, ones = stats(s, keys); lines.append(f"| {n} | **{m:.2f}** | {cov} / {c} | {ones} / {c} |" if c else f"| {n} | - | - | - |")
    lines += ["", "Rubric by rubric, against ScholarEval's own pipeline (higher / lower / equal score):", "", "| System | Higher | Lower | Equal |", "|---|---|---|---|"]
    for n, s in list(systems.items())[1:]:
        d = [s[k] - se[k] for k in keys if s.get(k) is not None]; lines.append(f"| {n} | {sum(x>0 for x in d)} | {sum(x<0 for x in d)} | {sum(x==0 for x in d)} |")
    lines += ["", "Mean score per idea:", "", "| Idea | Rubrics | " + " | ".join(systems) + " |", "|---|---|" + "---|" * len(systems)]
    for idea in scored:
        ks = [k for k in keys if k[0] == idea]
        lines.append(f"| {idea} | {len(ks)} | " + " | ".join(f"{stats(s, ks)[1]:.2f}" for s in systems.values()) + " |")
    return "\n".join(lines) + "\n", len(scored)

def write_readme(tables, n_scored, n_done):
    tmpl = (SCRATCH / "README_template.md").read_text()
    (STAGE / "README.md").write_text(tmpl.replace("{{TABLES}}", tables).replace("{{N_DONE}}", str(n_done)).replace("{{N_SCORED}}", str(n_scored)))

if __name__ == "__main__":
    STAGE.mkdir(exist_ok=True)
    ideas = done_ideas()
    for idea in ideas: copy_idea(idea)
    tables, n_scored = build_tables(ideas)
    write_readme(tables, n_scored, len(ideas))
    print(f"staged {len(ideas)} finished ideas, {n_scored} scored")
