# Misinformation Nudging Tool — Project Guide

## Project Overview

A browser extension that intercepts social media posts before a user shares them, runs them through a fact-checking pipeline, and issues a warning nudge if the content is likely false or misleading. Behavioral interaction data is collected (anonymized) to empirically validate the theoretical model in `factchecking_with_LLMs.pdf`.

**Team:** Research engineers + professors, academic lab  
**Deadline:** End of July 2026  
**Languages:** English + French  
**Starting platforms:** Twitter/X, Facebook  

---

## Fact-Checking Pipeline

### Step 1 — Claim detection (fast, same model as step 2)
Lightweight LLM assesses whether the post makes any fact-checkable claims at all. Binary yes/no. If no checkable claims, exit early — no nudge.

### Step 2 — Claim decomposition (fast, same model as step 1, parallel)
Same LLM decomposes the post into a list of atomic, independently checkable claims.

Steps 1 and 2 use a single shared model instance, prompts batched or run in fast sequence.

### Steps 3+4 — Database lookup (collapsed into one step)
- Embed each claim with a lightweight multilingual embedding model (`paraphrase-multilingual-MiniLM-L12-v2` or similar)
- Query a growing vector database (seeded from Google Fact Check Tools API)
- If cosine similarity to a known verified claim exceeds threshold: return that claim's verdict
- Database grows over time: every novel claim that gets verified in step 5 is added

### Step 5 — Novel claim verification (slow, async)
For claims not found in the database:
- Web search via Brave Search API (or similar), prioritizing trusted domains (ranked list TBD)
- LLM synthesizes evidence from top results into a verdict
- Result stored in database for future lookups
- **This runs asynchronously** — the first user encountering a novel claim may not receive a nudge, but triggers the slow check; subsequent users get the cached result

### Step 6 — Verdict aggregation
Per-claim verdict follows PolitiFact's scale:
`True / Mostly True / Half True / Mostly False / False / Pants on Fire`

Post-level confidence score: float in [0, 1]. Aggregation method TBD — depends on what produces the best nudging outcomes empirically. Candidates: worst-case (min), weighted average by claim centrality.

Warning threshold is a tunable parameter — one of the key experimental variables.

---

## Research Ideas Backlog

Ideas to prototype and evaluate. Not committed to, but worth testing.

### [IDEA-001] Encoder ensemble as fast language-based pre-filter
*Added: 2026-05-03 | Updated: 2026-05-03 after literature sweep*

Before the full fact-checking pipeline, run an ensemble of small fine-tuned **encoder classifiers** (not the generative LLM) to assess language-level signals: logical fallacies, bias, clickbait, and propaganda/manipulation markers. Literature sweep confirms these outperform prompted small LLMs on all these tasks and are 10-50x faster.

**Recommended ensemble (all run in parallel, ~100-250ms total on M1):**
- `q3fer/distilbert-base-fallacy-classification` — 14 logical fallacy classes, 67M params, ~20-50ms
- `himel7/bias-detector` — RoBERTa-base on BABE dataset, 92% accuracy, 125M params, ~30-60ms (EN)
- `mediabiasgroup/da-roberta-babe-ft` — XLM-RoBERTa-base, F1=0.804, 100M params (EN+FR fallback)
- `mradermacher/XLM_RoBERTa-Multilingual-Clickbait-Detection-GGUF` — 96.9% FR / 97.8% EN macro-F1 (quantized)
- `valurank/distilroberta-propaganda-2class` — propaganda/manipulation signal, 82M params, ~15-30ms
- Rule-based features: VADER sentiment extremity, TextBlob subjectivity, LanguageTool error count (~5ms)

**Use case:** Ensemble scores are combined into a single risk float [0,1]. If above threshold → nudge user immediately + trigger Tier 2 async. If below → skip nudge.

**Critical caveat from literature (LIAR ceiling):** Fine-grained veracity classification on political text achieves only weighted F1 ≈ 0.32, and a linear SVM matches RoBERTa. Politically-phrased misinformation is linguistically indistinguishable from truth. This pre-filter works reliably on **sensationalist, emotionally charged, clickbait-style content** but not on neutral-sounding political claims. Do not over-index on this signal for political content.

**French coverage note:** Multilingual clickbait model covers FR well. Bias and fallacy models are English-primary; `da-roberta-babe-ft` (XLM-R) transfers to French but hasn't been formally evaluated. Fallacy detection in French has no public fine-tuned model — may need to fine-tune on translated LOGIC/CoCoLoFa data.

---

### [IDEA-002] Async fact-checking with user-population caching
*Added: 2026-05-03*

The first user to share a novel claim triggers the slow fact-check pipeline (steps 3-5) asynchronously. They may not receive a nudge (or receive a "we're checking this" soft nudge). All subsequent users sharing the same or semantically similar claim get the cached verdict immediately.

**Why it matters:** Transforms a latency problem into a population-level problem. Works well if content goes viral (many users share the same post), which is exactly the regime where misinformation is most harmful.

**Open question:** What do we show the first user? Nothing? A provisional "this claim is being checked" message? A language-based estimate (see IDEA-001)?

---

### [IDEA-003] Embedding-based growing claims database
*Added: 2026-05-03*

Instead of maintaining a static fact-check database, use semantic embeddings to build a living database where:
- Every verified claim (from step 5 or pre-seeded from Google Fact Check API) is stored with its embedding
- New claims are matched by cosine similarity — above threshold = treat as same claim
- Over time, the database covers more and more of the claim space, making the expensive step 5 rarer

**Key parameter:** The similarity threshold. Too tight = too many novel claims hitting step 5. Too loose = wrong verdicts applied to different claims.

---

### [IDEA-004] Tiered pipeline with fast pre-filter
*Added: 2026-05-03*

Combine IDEA-001 and IDEA-002 into a tiered architecture:

```
Post received
  └─ Tier 1 (< 1s): Language assessment (IDEA-001)
       ├─ Score low → no nudge, skip
       └─ Score high → nudge user now + trigger Tier 2 async
            └─ Tier 2 (5-30s): Full fact-check pipeline (steps 1-6)
                 └─ Result cached in DB (IDEA-003) for future users
```

This separates the nudging decision (needs to be fast) from the verification decision (can be slow).

---

### [IDEA-005] Multi-hop QA-driven retrieval for novel claims (ClaimCheck / HerO 2 style)
*Added: 080526 after literature sweep on 2025-2026 SOTA*

Instead of 3 pre-formulated search queries per claim, the pipeline first generates **5–8 targeted verifying questions** from multiple angles (factual, contextual, source-attribution, contradicting evidence). For each question, evidence is retrieved and a direct answer is extracted. The verifier reasons over structured Q&A pairs rather than raw scraped snippets.

**Empirical support:** ClaimCheck (arxiv 2510.01226, NAACL 2025) achieves 76.4% on AVeriTeC dev set with Qwen3-4B, outperforming GPT-4o. Our current pipeline gets ~50% on the same benchmark. The gap is pipeline architecture, not model quality.

**Why it works:** Each question isolates a specific dimension of the claim's truth value. Structured Q&A is far easier for the verifier to reason over than noisy scraped paragraphs.

---

### [IDEA-006] FIRE-style iterative confidence-gated retrieval
*Added: 080526*

Instead of fixed N-query retrieval, use an agent loop: retrieve → assess confidence → if confident, output verdict; if uncertain, generate a targeted follow-up query → repeat. Early termination when (a) confidence exceeds threshold, or (b) the new query would be redundant with a prior query.

**Empirical support:** FIRE (arxiv 2411.00784, NAACL 2025 Findings) achieves comparable accuracy with 7.6× fewer LLM calls and 16.5× fewer search calls. For Tier 3 (async, no user-facing latency pressure), early-exit on easy claims offsets additional iterations on hard ones.

**Implementation notes:** Max iterations = 5. Redundancy check via cosine similarity between new query embedding and previous query embeddings; if > 0.9, skip. Confidence estimated from entropy of the verifier's p_supported / p_refuted distribution.

---

### [IDEA-007] Document summarization + answer reformulation before verification (HerO 2 style)
*Added: 080526*

Two preprocessing steps added before the verifier receives any evidence:
1. **Document summarization:** Each retrieved page is summarized into a claim-relevant excerpt. Removes noise, enforces temporal anchoring on the evidence text rather than on the model's parametric knowledge.
2. **Answer reformulation:** Evidence excerpts are rephrased into answer-form text ("This evidence supports / refutes the claim because…"), making the verifier's reasoning task structurally cleaner.

**Empirical support:** HerO 2 (arxiv 2507.11004, AVeriTeC 2025) identifies these as two of its four key contributions. Document summarization directly addresses our "date sensitivity" failure (Claim 5 in the evaluation: model used its own knowledge of 2024 statistics instead of the 2020 evidence).

---

### [IDEA-008] Hybrid retrieval stack: BM25 + dense + cross-encoder reranking
*Added: 080526*

Replace dense-only retrieval with a three-stage stack:
1. **BM25 (lexical):** Strong recall for named entities, numbers, exact quotes — fills gaps where dense retrieval underperforms.
2. **Dense (semantic):** Existing MiniLM embeddings.
3. **Cross-encoder reranking:** Merge candidate sets from both, rerank with a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L6-v2`) before passing top-K to the verifier.

**Why it matters:** Our "Nigeria 52% urban" failure (Claim 5) is a pure BM25 problem. A lexical match on "Nigeria urban population 2020" would have surfaced a 2020-vintage source instead of letting the model fall back to its parametric 2024 knowledge.

---

### [IDEA-009] Misleadingness detection via 4-step claim-stripping algorithm
*Added: 080526*

A formal algorithm for detecting posts that are **technically true but misleading**. Two categories:

**Misleading by scope:** A post makes a broad factual claim but only provides a narrow supporting instance (one study, one example, one time period). "A study shows vaccines cause autism."

**Misleading by implication:** A true statement A naturally suggests a false implication B for a reasonable reader. Often correlation → causality. "Cities with more immigrants have higher crime rates" (implies immigrants cause crime). Also covers misleading by omission: the statement is true only under specific circumstances that are not stated.

**4-step detection algorithm (applied per claim A):**
1. Establish A is likely true, preserving all qualifiers (time period, sample size, population, study count, expert count).
2. Strip all qualifiers → Ã. If Ã is likely false → **misleading by scope.**
3. Derive implication B: the first factual inference a reasonable person would draw from A. If B is likely false → **misleading by implication.**
4. Augment A with circumstances a reasonable person would silently assume → A⁺. If A⁺ is likely false → **misleading by omission.**

**Implementation:** Applied in Tier 3 after explicit claim verification. Steps 2–4 each generate a new derived claim (Ã, B, A⁺) that is fed through the standard retrieval + verification sub-pipeline. A misleading verdict increases the post's overall falsity score even when the literal claim is Supported.

**Why this matters:** None of the SOTA benchmark systems (ClaimCheck, FIRE, HerO 2) address misleadingness — they target stated factual claims only. Detecting "true but misleading" content is our primary differentiator for social media misinformation.

---

### [IDEA-010] Likert per-label confidence + MMR diversity reranking (CTU AIC)
*Added: 080526 — CTU AIC won AVeriTeC 2025 shared task on combined evidence+verdict metric*

Two contributions from CTU AIC (arxiv 2508.04390) not covered by IDEA-005–008:

**Likert per-label confidence:** Instead of a single confidence float, the verifier rates each label independently on a 1–5 scale (1=Strongly disagree, 5=Strongly agree) for all four classes: Supported, Refuted, Not Enough Evidence, Conflicting Evidence. Verdict with highest score wins. This is richer than a single float because it exposes near-ties (e.g., Refuted=4, Conflicting=3) that a scalar collapses — valuable features for the calibrated aggregation layer.

**MMR diversity reranking:** After retrieval + cross-encoder relevance ranking, apply Maximal Marginal Relevance to the top-N candidates to diversify the final evidence set. CTU AIC used k=40 retrieved chunks → MMR with λ=0.75 (relevance) / 0.25 (diversity) → l=10 passed to verifier. Prevents the verifier from receiving 10 rephrased versions of the same source. Recommended stack: cross-encoder first (relevance), MMR second (diversity).

**Negative finding — thinking tokens:** Ablation showed extended reasoning tokens performed on par with standard output. Token budget is better spent on retrieval coverage than in-context chain-of-thought. Do not use thinking mode in the verifier.

**Metric note:** CTU AIC's 33.17% / 0.50 AVeriTeC score and ClaimCheck's 76.4% are not the same metric. AVeriTeC score combines label accuracy + evidence quality (how well retrieved evidence supports the verdict). ClaimCheck's figure is label accuracy only. CTU AIC won the official task; ClaimCheck is the strongest on raw label accuracy.

---

## Key Architectural Decisions (Resolved)

| Decision | Choice | Reason |
|---|---|---|
| Model size | Single small LLM (Qwen2.5-1.5B or Phi-3.5-mini) | M1 8GB constraint, shared instance for steps 1+2 |
| Pre-filter architecture | Ensemble of fine-tuned encoder classifiers, NOT prompted LLM | Literature: encoders outperform prompted small LLMs on fallacy/bias/clickbait, 10-50x faster |
| Multilingual | Yes, EN + FR from the start | Embedding model choice must support both |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` | Small, fast, EN+FR |
| Claim verdict scale | PolitiFact 6-point | SOTA convention, well understood |
| Post score | Float [0,1], aggregation TBD | Threshold is experimental variable |
| Claims DB seed | Google Fact Check Tools API | Free, broad coverage |
| Novel claim search | Brave Search API | Free tier, programmatic |
| Deployment | Self-hosted endpoint (lab GPU or cheap cloud) | Privacy + cost constraints |
| Browser target | Chrome extension first | Largest user base |
| Social platforms | Twitter/X + Facebook first | Highest misinformation surface area |
| Tier 3 retrieval architecture | Multi-hop QA generation + FIRE-style iterative confidence-gated loop + hybrid BM25/dense + cross-encoder rerank | SOTA: ClaimCheck 76.4% AVeriTeC vs our ~50%; gap is pipeline not model; hybrid retrieval fixes date-sensitivity failure |
| Tier 3 evidence preparation | Per-document summarization + answer reformulation before verification (HerO 2) | Eliminates noise, enforces temporal anchoring on evidence rather than model parametric knowledge |
| Tier 3 score aggregation | Calibrated weighted scoring: claim salience × evidence quality × source diversity × recency match → logistic/isotonic regression | Hard worst-case priority rule over-triggers on peripheral claims; calibration layer trained on labeled dev data |
| Misleadingness detection | 4-step stripping algorithm: qualifier removal (scope) + implication derivation + circumstance augmentation (IDEA-009) | "True but misleading" not addressed by any SOTA system; applied after explicit claim verification in Tier 3 |

---

## Open Questions

- Domain trust ranking for step 5 web search — how do we define and maintain the list?
- Post-level score aggregation — how to combine per-claim verdicts (worst-case? weighted?)
- What do we show the first user encountering a novel claim (before async check completes)?
- IRB approval process — timeline?
- Consent and data collection flow for general public users

---

## Conventions

- **Log every new research idea** under "Research Ideas Backlog" with the date and a `[IDEA-NNN]` tag.
- **Update "Key Architectural Decisions"** when a decision is made or reversed.
- **Do not delete open questions** — move them to decisions when resolved.
