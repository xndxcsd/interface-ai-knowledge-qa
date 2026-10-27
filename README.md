# interface-ai-knowledge-qa

Knowledge Q&A for the interface.ai hackathon kit: ingest Dupaco website snapshots, answer with citations, list rate conflicts, and abstain when evidence does not support a claim.

Requires **Python 3.11+** (tested on 3.11 and 3.13). Built with AI-assisted development (Cursor Cloud Agent).

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

Place the participant **`snapshots_zip/`** directory at the repo root (gitignored). On the **first** harness run, zips unpack into **`./snapshots/`** (default `--snapshots`). See [snapshots/README.md](snapshots/README.md).

## One-command eval

Public set (40 questions):

```bash
python3 harness/run_eval.py --submission . --eval eval/public_eval.jsonl --out results/public
```

Hold-out (40 questions):

```bash
python3 harness/run_eval.py --submission . --eval eval/holdout_eval.jsonl --out results/holdout
```

With snapshots elsewhere:

```bash
python3 harness/run_eval.py --submission . \
  --snapshots /path/to/extracted/snapshots \
  --eval eval/public_eval.jsonl \
  --out results/public
```

The public kit has no `conflicts_gold.json`, so the harness **does not score the conflicts pillar** unless you pass `--conflicts-gold`.

## With OpenAI (recommended)

```bash
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_MAX_TOKENS=320
export LLM_WALL_S=20          # wall-clock cap per answer (default 20)
export OPENAI_TIMEOUT_S=15    # HTTP timeout per request
export KB_LOG_LLM=1           # optional timing on stderr

python3 harness/run_eval.py --submission . \
  --eval eval/public_eval.jsonl \
  --out results/public
```

Without `OPENAI_API_KEY`, a deterministic rules fallback runs (much lower accuracy).

## Architecture

```
Snapshots → KnowledgeStore (tables, prose APR, hours, contact, newsroom facts + BM25 chunks)
         → gather_evidence (path hints, segment URL matching, branch/newsroom filters)
         → OpenAI JSON answer (temperature 0, no response cache)
         → apply_grounding (numbers, rates, phones, URLs, branch hours must match evidence)
```

Entry point: `solution.py` implements the harness `KnowledgeSystem` contract; logic lives under `kb/`.

## Design decisions

| Choice | Rationale |
|--------|-----------|
| Structured facts + BM25 | Rates and hours need exact cells; prose fills gaps (e.g. card APR ranges). |
| Path hints from question shape | List/broad-rate questions pull whole product families without hard-coding answers. |
| URL **segment** matching | Avoids substring false positives (`rate` in `celebrates`). |
| Grounding after LLM | Model may paraphrase; post-check refuses unsupported numbers and wrong product rows. |
| `as_of` = latest snapshot per URL on or before date | Matches “what the site said then” for temporal eval items. |
| Newsroom place tags | Branch hours/size/phone in articles are tied to inferred city/branch, not the wrong article. |
| Personal vs business URL gate | Only when the question names **one** side; lists and “personal and business” allow both. |
| Per-call LLM thread pool | Wall-clock timeout returns without waiting on hung HTTP or blocking a global pool. |

## Eval results (with-key, best run on this branch)

Approximate scores after grounding/evidence iteration (your key, full pipeline):

| Split | Score |
|-------|--------|
| Public (strict / relaxed) | **~0.74 / ~0.72** |
| Hold-out | **~0.78** |
| Blind (private) | **~0.76** |
| Max latency (wall clock) | **~2–4 s** typical with `gpt-4o-mini` |

No-key (rules-only) public/hold-out are **~0.29–0.37** on the agent VM — expect a large gap without the LLM.

Reproduce with-key numbers locally using the commands above and your snapshots.

## Known limitations

- **Conflict pillar** not scored on the public kit without gold labels.
- **Judge / empty `must_include`** — e.g. public `dup-005` stays at 0 correctness without `--judge` when the rubric expects a full rate list.
- **Newsroom place inference** is heuristic; odd titles may tag the wrong city until the question grounding filters it.
- **Broad list questions** depend on retrieval surfacing every product page; very long lists may truncate in the prompt.
- **Stale snippets** are down-weighted for rate questions but can still appear when no fresher row exists.

## With more time

- Learned or cross-encoder reranking over chunks and facts.
- Stronger temporal reasoning (explicit effective dates in tables).
- Automated conflict resolution narratives for members.
- Eval-driven regression suite on snapshot subsets without leaking eval strings into `kb/`.
- Optional LLM judge aligned with hackathon rubric for list-style questions.

## Harness quirk

Public **`dup-005`** has empty `must_include`, so strict correctness is **0** without `--judge` when the expected answer is a full certificate rate list.
