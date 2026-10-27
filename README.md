# interface-ai-knowledge-qa

Knowledge Q&A for the interface.ai hackathon kit: ingest five Dupaco website snapshots, answer with citations, list conflicts, and abstain when unsupported.

**Built with AI-assisted development** (see [NOTES.md](NOTES.md)).

Requires **Python 3.11+** (3.11+ works; tested on 3.11 and 3.13).

## Setup

```bash
git clone https://github.com/xndxcsd/interface-ai-knowledge-qa.git
cd interface-ai-knowledge-qa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## Snapshots (not in git)

Place the participant kit **`snapshots_zip/`** directory at the repo root (gitignored). On the **first run**, the harness unpacks those zips into **`./snapshots/`** (default `--snapshots` path). See [snapshots/README.md](snapshots/README.md).

```bash
python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
```

Optional explicit path (same layout as `snapshots_zip/`):

```bash
python3 harness/run_eval.py --submission . \
  --snapshots ./snapshots_zip \
  --eval eval/public_eval.jsonl \
  --out results/public
```

Hold-out (40 questions):

```bash
python3 harness/run_eval.py --submission . \
  --eval eval/holdout_eval.jsonl \
  --out results/holdout
```

The public kit has **no `conflicts_gold.json`**, so the harness **does not score the conflicts pillar** unless you pass `--conflicts-gold`.

## With OpenAI (recommended)

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_MAX_TOKENS=320
export KB_LOG_LLM=1   # optional timing on stderr

python3 harness/run_eval.py --submission . \
  --eval eval/public_eval.jsonl \
  --out results/public
```

Without `OPENAI_API_KEY`, a deterministic evidence-only fallback runs (lower accuracy).

## Design

- **Evidence:** BM25 snippets + structured table/contact facts; path hints for list and broad rate questions; facts labeled with page URL, section, row, column, snapshot.
- **Answer:** OpenAI JSON → **grounding** (numbers, times, phones, URLs must appear in retrieved evidence).
- **Conflicts:** Per-column cross-snapshot changes on high-authority product pages; resolution = newest snapshot value.

## Harness quirk

Public **`dup-005`** has empty `must_include`, so correctness stays **0** without `--judge` when listing all certificate rates.
