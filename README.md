# interface-ai-knowledge-qa

Knowledge Q&A for the interface.ai hackathon kit: ingest Dupaco website snapshots, answer with citations, list rate conflicts, and abstain when evidence does not support a claim.

Requires **Python 3.11+** (tested on 3.11 and 3.13).

## Setup

```bash
git clone https://github.com/xndxcsd/interface-ai-knowledge-qa.git
cd interface-ai-knowledge-qa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Runtime-only install: `pip install -r requirements.txt`.

## Snapshots (not in git)

Place the participant **`snapshots_zip/`** directory at the repo root (gitignored). On the **first** harness run, zips unpack into **`./snapshots/`** (default `--snapshots`). See [snapshots/README.md](snapshots/README.md).

## One-command eval

```bash
python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
python3 harness/run_eval.py --submission . --eval eval/holdout_eval.jsonl --out results/holdout
```

`eval/public_eval.jsonl` is the kit public set. **`eval/holdout_eval.jsonl` is a dev set we wrote and revised while iterating on the agent** (gold labels changed when we fixed bugs). Treat it as a second local benchmark, not an independent hold-out.

The public kit has no `conflicts_gold.json`, so the harness does not score the conflicts pillar unless you pass `--conflicts-gold`.

## With OpenAI

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_MAX_TOKENS=768
export LLM_WALL_S=20
export KB_LOG_LLM=1   # optional timing on stderr

python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
```

Without `OPENAI_API_KEY`, a deterministic rules fallback runs (much lower accuracy). LLM failures log to stderr and fall back to rules.

## Architecture

Snapshots → `KnowledgeStore` (tables, prose APR, hours, contact, newsroom facts + BM25) → `gather_evidence` → OpenAI JSON → `apply_grounding` (numbers, rates, phones, URLs must match evidence).

Entry: `solution.py` (`build()` → `KnowledgeSystem`).

## Eval results (with-key, this branch)

Two full public runs on the same strict scorer: **~0.72** each (0.719 and 0.724). Dev set (`holdout_eval.jsonl`): **~0.83**. Typical latency **p95 2–4 s**; **max observed ~12.3 s** on one public item.

No-key rules-only on the agent VM: public **~0.35**, dev set **~0.42**.

## Known limitations

- Public **`dup-005`**: empty `must_include`, so strict correctness stays 0 without `--judge` for full certificate rate lists.
- Newsroom place tagging is heuristic; wrong tags can still appear until grounding filters them.
- List-style answers depend on retrieval and prompt caps.

## With more time

- Cross-encoder reranking over facts and chunks.
- Explicit effective-date handling in tables.
- `--judge` integration for list rubric items.
- Pin a small golden fixture suite that does not reuse eval wording.

Built with AI-assisted development (Cursor Cloud Agent).
