# NOTES — Dupaco knowledge Q&A

## What “current” means

1. **Page versions** — For each canonical URL, only the **latest snapshot at or before `as_of`** contributes facts and BM25 chunks.
2. **Fact keys** — `(url, subject, field)` after normalization (contact rows use distinct subjects per address ZIP or hours text).
3. **Authority** — Official product pages beat blogs and `info.dupaco.com`.
4. **Contact / hours** — Addresses and phones on `/contact`; **hours** regex runs on any page whose markdown mentions drive-up, lobby, or branch hours (e.g. newsroom articles).

## Conflicts

`conflicts()` compares **each table column separately** (rate vs APR vs dividend vs APY) on the same URL + row. Reports cross-snapshot value changes and same-snapshot contradictions among high-authority facts. Values are deduplicated, footnote markers stripped, dollar amounts in subjects normalized. Resolution = current value on the newest snapshot.

## Architecture

- Retrieve ranked facts + BM25 chunks → OpenAI with labeled evidence → **grounding** post-check only (no product-specific code rules).
- No LLM response cache (temperature 0).
- No-key: compose from top facts or abstain.

## API keys

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Production answers |
| `OPENAI_MODEL` | Default `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | Default `320` |

Built with AI-assisted development (Cursor Cloud Agent).
