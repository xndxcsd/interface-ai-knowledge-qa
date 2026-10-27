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

`eval/public_eval.jsonl` is the kit public set. **`eval/holdout_eval.jsonl` is a dev set we wrote and revised while iterating** (gold labels changed when we fixed bugs). Retrieval weights in `kb/evidence_weights.py` were tuned against that dev set — treat it as a local benchmark, not an independent hold-out.

The public kit has no `conflicts_gold.json`, so the harness does not score the conflicts pillar unless you pass `--conflicts-gold`.

## With OpenAI

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_MAX_TOKENS=768    # answer JSON size (default 768)
export OPENAI_TIMEOUT_S=15      # per HTTP request to OpenAI
export LLM_WALL_S=20            # wall-clock cap per answer (daemon thread)
export KB_LOG_LLM=1             # optional timing on stderr

python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
```

Without `OPENAI_API_KEY`, a deterministic rules fallback runs (much lower accuracy). LLM failures log to stderr and fall back to rules.

## Architecture

Snapshots → `KnowledgeStore` (tables, prose APR, hours, contact, newsroom facts + BM25) → `gather_evidence` → OpenAI JSON → `apply_grounding` (numbers, rates, phones, URLs must match evidence).

Entry: `solution.py` (`build()` → `KnowledgeSystem`).

## Eval results (with-key, this branch)

Two public runs on the strict scorer: **~0.78** (0.779 and 0.781). Dev set: **~0.83** (0.831). Latency **p95 ~3.4–3.9 s** on public eval; **max observed ~12 s** on a single item. No-key rules-only on the agent VM: public **~0.38**, dev set **~0.42**.

## Known limitations

- Public **`dup-005`**: empty `must_include`, so strict correctness stays 0 without `--judge` for full certificate rate lists.
- Newsroom place tagging is heuristic and can still mismatch before grounding filters.
- List-style answers depend on retrieval and prompt caps.

## With more time

- Cross-encoder reranking; `--judge` for list rubric items; fixture tests without eval wording.

Built with AI-assisted development (Cursor Cloud Agent).
