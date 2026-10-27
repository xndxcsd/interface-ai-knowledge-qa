# interface-ai-knowledge-qa

Knowledge Q&A for the interface.ai hackathon kit: ingest five Dupaco website snapshots, answer with citations, list conflicts, and abstain when unsupported.

**Built with AI-assisted development** (see [NOTES.md](NOTES.md)).

Requires **Python 3.11+** (tested on 3.11 and 3.13).

## Setup

```bash
git clone https://github.com/xndxcsd/interface-ai-knowledge-qa.git
cd interface-ai-knowledge-qa
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Snapshots (not in git)

Copy the participant kit `snapshots_zip/` directory into the repo root (gitignored), **or** unzip the five zips to any folder. Details: [snapshots/README.md](snapshots/README.md).

Example with zips in-repo:

```bash
python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
```

Example with an external unpack directory:

```bash
python3 harness/run_eval.py --submission . \
  --snapshots /tmp/dupaco-snapshots/extracted \
  --eval eval/public_eval.jsonl \
  --out results/public
```

Hold-out set (40 questions, local generalization check):

```bash
python3 harness/run_eval.py --submission . \
  --snapshots /tmp/dupaco-snapshots/extracted \
  --eval eval/holdout_eval.jsonl \
  --out results/holdout
```

The public participant kit has **no `conflicts_gold.json`**, so the harness **does not score the conflicts pillar** locally unless you pass `--conflicts-gold` yourself.

## With OpenAI (recommended)

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini      # or gpt-4.1-mini
export OPENAI_MAX_TOKENS=320         # optional, default 320
export KB_LOG_LLM=1                  # optional stderr timing per LLM answer

python3 harness/run_eval.py --submission . \
  --snapshots /tmp/dupaco-snapshots/extracted \
  --eval eval/public_eval.jsonl \
  --out results/public
```

Per-question latency is in `results/public/per_question.jsonl`. LLM responses are **not cached** (temperature 0); harness repeat questions call the model again.

Without `OPENAI_API_KEY`, a deterministic evidence-only fallback runs (lower accuracy).

## Design

- **Current facts:** For each URL, only the **latest snapshot at or before `as_of`** contributes table facts; dedupe by URL + subject + field (not by value).
- **Evidence:** Ranked facts + BM25 snippets (parallel fetch), path hints for list questions (e.g. personal + business card pages).
- **Answer:** OpenAI JSON → sources tied to evidence `snapshot_id` → **grounding** post-check (rates, phones, URLs, times, addresses must appear in retrieved evidence; product/page alignment for rates).
- **Conflicts:** Cross-snapshot rate changes (and same-snapshot contradictions) on high-authority product pages; rate/APR and dividend/APY pairs merged per row; resolution uses newest snapshot date (e.g. 2026-09-28).

## Harness quirk

Public item **`dup-005`** has empty `must_include`, so correctness stays **0** without `--judge` even when listing all certificate rates.

## Tradeoffs

- No-key path is for CI only; real accuracy needs the LLM.
- Conflicts pillar needs a gold file not shipped in the public kit.
