# Misinformation Nudging Tool — Project Guide

## Project Overview

A browser extension that intercepts social media posts before a user shares them, runs them through a fact-checking pipeline, and issues a warning nudge if the content is likely false or misleading. Behavioral interaction data is collected (anonymized) to empirically validate the theoretical model in `factchecking_with_LLMs.pdf`.

**Team:** Research engineers + professors, academic lab  
**Deadline:** End of July 2026  
**Languages:** English + French  
**Starting platforms:** Twitter/X, Facebook  

---

## Fact-Checking Pipeline

### Tier 1 — Language pre-filter (< 1s, synchronous)
Encoder ensemble runs in parallel on the raw post:
- Fallacy classifier (`q3fer/distilbert-base-fallacy-classification`, 14 classes)
- Bias detector (`mediabiasgroup/da-roberta-babe-ft`, XLM-R, EN+FR)
- Clickbait detector (XLM-RoBERTa multilingual, 96.9% FR / 97.8% EN)
- Propaganda classifier (`valurank/distilroberta-propaganda-2class`)
- Rule-based: VADER sentiment extremity, TextBlob subjectivity, LanguageTool error count

Outputs a risk float [0,1]. Above threshold → nudge user immediately + trigger Tier 2 async. Below → no action.

**Caveat:** Works on sensationalist/clickbait content. Politically-neutral misinformation is linguistically indistinguishable from truth (LIAR ceiling: weighted F1 ≈ 0.32). Do not over-index on this signal for political content.

### Tier 2 — Claim pipeline (5–30s, async)
1. **Claim detection** — lightweight LLM: does this post make any fact-checkable claims? Binary yes/no. Exit early if no.
2. **Claim decomposition** — same LLM: decompose post into atomic, independently checkable claims. Steps 1+2 share a single model instance.
3. **DB lookup** — embed each claim (`paraphrase-multilingual-MiniLM-L12-v2`), query vector DB by cosine similarity. Match above threshold → return cached verdict immediately.
4. Novel claim → trigger Tier 3 async. First user may not receive nudge; all subsequent users get cached result.

### Tier 3 — Novel claim verification (async, 5–60s)
For each novel claim:
1. **Question generation** — LLM generates 5–8 targeted verifying questions (factual, contextual, source-attribution, contradicting evidence angles).
2. **Hybrid retrieval** — BM25 (lexical) + dense (MiniLM) → cross-encoder rerank → MMR diversity rerank (λ=0.75/0.25, k=40→l=10). Serper date-ceiling prevents future-evidence leakage.
3. **Evidence preparation** — each retrieved page summarized into claim-relevant excerpt; reformulated into answer-form text. Enforces temporal anchoring on evidence, not model parametric knowledge.
4. **FIRE iterative verification** — retrieve → Likert confidence assessment (1–5 per label: Supported / Refuted / NEI / CE) → if confident, output verdict; if not, generate targeted follow-up query → repeat (max 5 iterations, redundancy check at cosine sim > 0.9).
5. **Misleadingness detection** — 4-step stripping algorithm: establish literal truth with qualifiers → strip qualifiers (misleading by scope?) → derive reasonable implication (misleading by implication?) → augment with silent assumptions (misleading by omission?). Each derived claim fed through retrieval + verification.
6. **Verdict aggregation** — calibrated weighted scoring: claim salience × evidence quality × source diversity × recency match → logistic/isotonic regression. Confidence threshold: 0.65. Result cached in DB.

**Verdict scale (PolitiFact):** True / Mostly True / Half True / Mostly False / False / Pants on Fire  
**Post score:** Float [0,1]. Warning threshold is a key experimental variable.

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

### [IDEA-005] Multi-hop QA-driven retrieval
*[RESOLVED → incorporated into Tier 3, Step 1. Full notes: clog/110526.md]*

### [IDEA-006] FIRE-style iterative confidence-gated retrieval
*[RESOLVED → incorporated into Tier 3, Step 4. Full notes: clog/110526.md]*

### [IDEA-007] Document summarization + answer reformulation
*[RESOLVED → incorporated into Tier 3, Step 3. Full notes: clog/110526.md]*

### [IDEA-008] Hybrid retrieval stack: BM25 + dense + cross-encoder reranking
*[RESOLVED → incorporated into Tier 3, Step 2. Full notes: clog/110526.md]*

### [IDEA-009] Misleadingness detection via 4-step claim-stripping algorithm
*[RESOLVED → incorporated into Tier 3, Step 5. Full notes: clog/110526.md]*

### [IDEA-010] Likert per-label confidence + MMR diversity reranking
*[RESOLVED → incorporated into Tier 3, Steps 2+4. Full notes: clog/110526.md]*

---

### [IDEA-011] Source-retrieval evaluation using ClaimReview `appearance` URLs
*Added: 2026-05-18*

The Data Commons ClaimReview live feed (discovered 2026-05-18, see `clog/180526.md`) exposes `itemReviewed.appearance[].url` — the source URLs cited by human fact-checkers. ~60% of entries have these. This is a free gold standard for evaluating Tier 3 **retrieval quality**, orthogonal to verdict-level evaluation.

**Eval setup:** For each ClaimReview entry, run Tier 3 retrieval on the claim, then compare retrieved URLs/domains against the fact-checker's cited sources.

**Candidate metrics:**
- **Domain-level recall** — did we surface ≥1 source from a domain the fact-checker used?
- **URL-level recall** — exact URL overlap (likely sparse, but worth measuring)
- **Domain-level precision** — what fraction of our top-K domains overlap with the fact-checker's domains?
- **Trust correlation** — do our high-credibility-scored domains overlap more with fact-checker sources than our low-scored ones? (Validates the domain trust ranking, currently an open question.)

**Caveat:** fact-checker sources are *one* valid retrieval; ours may surface different-but-equally-valid sources. Treat low overlap as a signal worth investigating, not as a hard failure.

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
