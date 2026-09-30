# Running Assistant — Candidate Models

> **Decision (2026-09-30):** use **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`), the rank-1 option below.
> The other rows are kept as fallbacks and for reference. Prices are from the Gemini API pricing page for the
> **paid tier**, retrieved 2026-09-30, in USD per 1M tokens. Re-check them before building; Google
> changes models and prices often.

## Why a small model is enough
The spec requires PACE, not the model, to compute every number (FR 7, FR 16). That leaves the
model three jobs:
- understand the question
- ask PACE for the right figures
- phrase a short, on-topic answer

This is light work, well within a "Flash-Lite" class model. Larger models add cost and latency for
little benefit here.

## Cost assumption
One question ≈ **4,000 input tokens** (instructions, a compact data summary, and the question) and
**≈400 output tokens**. "Thinking" tokens are billed as output. Keep thinking minimal or off for
this workload, or the costs below rise.

## Ranked shortlist

| Rank | Model (API id) | Input / Output per 1M | ≈ per question | ≈ 100 q / month | Best for |
|---|---|---|---|---|---|
| 1 | **Gemini 3.5 Flash-Lite** (`gemini-3.5-flash-lite`) | $0.30 / $2.50 | $0.0022 | **$0.22** | **Default.** Google's recommended Lite model for new projects; low latency, cheap. |
| 2 | Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`) | $0.25 / $1.50 | $0.0016 | $0.16 | Cheapest paid option; fallback if 3.5 Lite is unavailable or rate-limited. |
| 3 | Gemini 3.8 Flash (`gemini-3.8-flash`) | $0.75 / $3.75 until 2026-12-31, then $1.50 / $7.50 | $0.0045, then $0.009 | $0.45, then $0.90 | Upgrade path if coaching-style answers (Q7) need stronger reasoning. |
| 4 | **Gemma 4 E4B or 26B A4B, run locally** (Ollama / llama.cpp / LM Studio) | $0 (your hardware) | $0 | $0 | Maximum privacy: data never leaves the computer. Slower and less capable. The smallest variant (E2B) needs about 4 GB RAM; the largest needs up to about 19 GB. |

**Not recommended**
- **Gemini 2.5 Flash-Lite:** deprecated, and available only to projects that already used it.
- **Gemini 3.1 Pro / 2.5 Pro:** 5–10× the cost with no benefit for this workload.
- **Live, TTS, and image models:** built for other tasks.

## Access paths

| Path | Setup | Data use | Fit |
|---|---|---|---|
| **Google AI Studio, paid tier** (billing enabled on the key's project) | Create a key at aistudio.google.com and link a billing account. | Google does **not** use prompts or responses to improve products; data is logged only for safety and legal reasons. | **Recommended for v1:** one key, simplest local setup. |
| Google AI Studio, **free tier** | Key only. | Google **may use prompts and responses to improve products, and humans may review them**. The terms say not to submit personal information. Not available in the EEA, Switzerland, or UK. | **Do not use with real run data.** Use only with synthetic data during development. |
| GCP Vertex AI | GCP project, enabled API, and service-account or ADC credentials. | Enterprise data terms; IAM, quotas, and billing budgets via GCP. | Stronger governance, but heavier credential handling for a desktop app. Prices are similar; verify on the Vertex pricing page. |
| Local Gemma 4 | Install a local runtime and download the weights (Apache 2.0). | Nothing leaves the computer. | Optional "private mode". Quality and speed depend on the hardware. |

## To verify in `/plan`
- The chosen model's current support for function/tool calling and structured output.
- Current free- and paid-tier rate limits, shown per project at aistudio.google.com/rate-limit.
- Whether hosted Gemma 4 on the Gemini API is covered by unpaid-service terms. It is listed as free
  of charge.
- Set a GCP billing budget alert as a backstop to PACE's own cap (FR 24).

## Sources
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Models and recommendations: https://ai.google.dev/gemini-api/docs/models
- Data-use terms: https://ai.google.dev/gemini-api/terms
- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Gemma 4 overview: https://ai.google.dev/gemma/docs/core
