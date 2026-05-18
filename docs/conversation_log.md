# Conversation Log

Chronological summaries of project discussions. Append new entries as conversations happen. Load this into context at the start of new sessions to restore continuity.

---

## 030526 — Session 1: Project kickoff, pipeline design

**Context:** User (research engineer, AI/ML background) starting first day at academic lab tomorrow. Colleagues are professors. Goal: arrive with a plan to discuss.

**Source material:** `factchecking_with_LLMs.pdf` — a January 2026 theoretical model (connected to Guriev et al. 2025) formalizing LLM-issued warnings about misinformation as a dynamic game. Models three behavioral mechanisms: salience, habituation, loss of faith. Paper notes none of these have been empirically measured — this project is the empirical arm.

**What we're building:** A browser extension that intercepts social media posts before a user shares them, runs a fact-checking pipeline, and issues a warning nudge if content is likely false. Collects anonymized behavioral data to test the model's predictions.

**Constraints established:**
- Model must run on M1 MacBook with 8GB RAM (for local testing) — single small LLM instance
- Production: lightweight self-hosted endpoint (lab GPU or cheap cloud), not third-party APIs (privacy + cost)
- English + French from the start
- Start with Twitter/X and Facebook
- Deadline: end of July 2026
- Greenfield project

**Pipeline agreed on:**
1. Claim detection — does post make fact-checkable claims? (same model as step 2, batched)
2. Claim decomposition — break into atomic claims (same model, parallel/batched)
3+4. Database lookup — embed claim, query growing vector DB (seeded from Google Fact Check Tools API), return verdict if similarity exceeds threshold
5. Novel claim verification — Brave Search API + trusted domain ranking + LLM synthesis (async)
6. Verdict aggregation — PolitiFact 6-point scale per claim, post-level float [0,1] score, threshold is experimental variable

**Key ideas surfaced (logged in CLAUDE.md):**
- IDEA-001: LLM language-based fast veracity estimate from fallacies/inflammatory language/bias signals
- IDEA-002: Async fact-checking — first user triggers slow check, subsequent users get cached result
- IDEA-003: Growing embedding-based claims database
- IDEA-004: Tiered pipeline — fast language pre-filter → nudge + trigger slow async fact-check

**Adoption problem flagged:** Getting general public to install and use a misinformation warning tool is hard. Mitigations discussed: partner with fact-checkers (AFP for French), frame as empowering ("know before you share"), consider recruited participants vs. organic deployment for the study, explain rather than just warn.

**Phased MVP plan proposed:**
- Phase 1 (2 weeks): Core pipeline, CLI, no browser extension
- Phase 2 (3 weeks): Novel claim verification, end-to-end pipeline
- Phase 3 (3 weeks): Chrome extension + Twitter/Facebook content scripts + warning UI
- Phase 4 (remaining): Hosted endpoint, data collection, threshold experiments

**Open going into tomorrow:**
- Post-level score aggregation method (worst-case vs. weighted)
- What to show first user before async check completes
- IRB timeline
- Domain trust list for step 5
- Whether recruited participants or organic deployment is the study design

---

## 030526 — Session 1 (continued): Literature sweep on language-based misinformation detection

**Topic:** Whether to use a prompted small LLM or fine-tuned encoder models for IDEA-001 (fast language pre-filter).

**Key finding:** Literature clearly favors **fine-tuned encoder classifiers over prompted small LLMs** for fallacy, bias, and clickbait detection — both more accurate and 10-50x faster. IDEA-001 updated accordingly.

**Recommended pre-filter ensemble (run in parallel, ~100-250ms total on M1):**
- Fallacy detection: `q3fer/distilbert-base-fallacy-classification` (DistilBERT, 67M params, 14 classes)
- Bias detection EN: `himel7/bias-detector` (RoBERTa-base, 92% accuracy)
- Bias detection EN+FR: `mediabiasgroup/da-roberta-babe-ft` (XLM-RoBERTa-base, F1=0.804)
- Clickbait EN+FR: `mradermacher/XLM_RoBERTa-Multilingual-Clickbait-Detection-GGUF` (96.9% FR, 97.8% EN)
- Propaganda/manipulation: `valurank/distilroberta-propaganda-2class` (82M params)
- Rule-based features: VADER, TextBlob subjectivity, LanguageTool (~5ms, no model needed)

**Critical caveat (LIAR ceiling):** On political text, text-only veracity classification hits a ceiling of weighted F1 ≈ 0.32, matched by a linear SVM. Politically-phrased misinformation is linguistically indistinguishable from truth. The pre-filter works for sensationalist/emotional content; do not over-rely on it for political claims.

**French gap:** No public fine-tuned fallacy detection model for French. May need to fine-tune XLM-RoBERTa on translated LOGIC/CoCoLoFa data.

**Decision logged:** Pre-filter uses encoder ensemble, not prompted LLM. Added to Architectural Decisions table in CLAUDE.md.

---

## 080526 — Session 2: Tier 3 literature sweep + misleadingness detection algorithm

**Topic:** Improving Tier 3 (novel claim verification) for accuracy, dropping speed constraint. Reviewed 2025–2026 SOTA fact-checking systems and integrated user-provided misleadingness detection framework.

**Starting point:** Current Tier 3 achieves ~50% on a 10-claim AVeriTeC sample. Identified 3 distinct failure modes: retrieval coverage gaps (2 claims), date-sensitivity (1 claim), annotation disagreement (1 claim).

**Systems reviewed:**
- **ClaimCheck** (arxiv 2510.01226, NAACL 2025): 76.4% AVeriTeC with Qwen3-4B using multi-hop QA-driven retrieval. Two-track: claim-matching for known claims, targeted question generation + answer extraction for novel ones.
- **FIRE** (arxiv 2411.00784, NAACL 2025 Findings): Iterative confidence-gated retrieval loop. Retrieve → assess confidence → output verdict if confident, else generate follow-up query. 7.6× fewer LLM calls, 16.5× fewer searches at same accuracy.
- **HerO 2** (arxiv 2507.11004, AVeriTeC 2025 2nd place): Four key contributions — document summarization per retrieved source, answer reformulation into answer-form text, HyDE-style hypothetical document expansion for retrieval, fine-tuned + quantized veracity predictor.

**Gap analysis (current pipeline vs SOTA):**
1. We send 3 canned queries; SOTA generates 5–8 targeted verifying questions first → verifier reasons over Q&A, not raw snippets
2. We pass raw scraped text to the verifier; SOTA summarizes documents first → fixes date-anchoring failures
3. We use dense-only retrieval; SOTA uses BM25 + dense + cross-encoder reranking → fixes named-entity / numerical recall
4. We do fixed retrieval; FIRE does confidence-gated iteration → early exit on easy claims, more effort on hard ones
5. We use a hard worst-case priority aggregation rule; SOTA uses calibrated weighted scoring

**New research ideas logged (IDEA-005 through IDEA-008):**
- IDEA-005: Multi-hop QA-driven retrieval (ClaimCheck/HerO 2 style)
- IDEA-006: FIRE-style iterative confidence-gated retrieval
- IDEA-007: Document summarization + answer reformulation (HerO 2)
- IDEA-008: Hybrid retrieval: BM25 + dense + cross-encoder reranking

**Misleadingness detection algorithm (IDEA-009):** User provided a formal framework covering two categories not addressed by any SOTA system:
- *Misleading by scope*: true statement backed by a single narrow instance (one study, one example, one time period). Detection: strip qualifiers → Ã; if Ã is likely false → misleading by scope.
- *Misleading by implication*: true statement A suggests false implication B (often correlation → causality, or misleading by omission). Detection: derive first-order implication B; augment A with assumed circumstances → A⁺; verify B and A⁺.
- Algorithm produces derived claims (Ã, B, A⁺) that are each run through the retrieval+verification sub-pipeline. Misleadingness verdict increases post falsity score even when the literal claim is Supported.

**Key architectural decisions logged:**
- Tier 3 retrieval: multi-hop QA + FIRE iterative loop + hybrid BM25/dense + cross-encoder rerank
- Tier 3 evidence prep: document summarization + answer reformulation
- Tier 3 aggregation: calibrated weighted scoring (claim salience × evidence quality × source diversity × recency match)
- Misleadingness detection: 4-step stripping algorithm as differentiator vs SOTA benchmarks

**Differentiator noted:** Misleadingness detection (IDEA-009) is not implemented by any current benchmark system. It is our main value-add for social media misinformation where "true but misleading" posts are at least as common as outright false ones.

---

## 080526 — Session 2 (continued): CTU AIC review + next steps

**Topic:** Evaluated CTU AIC (AVeriTeC 2025 winner, arxiv 2508.04390) for relevance to Tier 3 improvements.

**CTU AIC architecture:**
- Two-step RAG: FAISS retrieval (mxbai-embed-large-v1, 2048-char chunks) + MMR reranking (k=40→l=10, λ=0.75) → Qwen3-14b generates structured Q&A triples + Likert confidence
- Output schema: questions array (question + answer + source ID) + per-label Likert scores (1–5 for each of Supported/Refuted/NEI/Conflicting) + final verdict string

**What CTU AIC adds (logged as IDEA-010):**
1. **Likert per-label confidence**: four independent 1–5 scores expose near-ties between labels — richer features for the calibration layer than a single float
2. **MMR diversity reranking**: after cross-encoder relevance ranking, MMR diversifies the final evidence set so the verifier doesn't see 10 versions of the same source; recommended stack is cross-encoder → MMR
3. **Negative finding**: thinking tokens offer no accuracy gain; spend token budget on retrieval coverage instead

**Metric clarification noted:** CTU AIC's AVeriTeC score (33.17% / 0.50) measures label accuracy + evidence quality jointly; ClaimCheck's 76.4% is label accuracy only. Not directly comparable.

**Next steps agreed:**
1. Fix `is_checkable: False` prompt bug (false assertions being rejected as uncheckable)
2. Run 50–100 claim AVeriTeC baseline on A40 with Qwen3-32B to establish a stable measurement point
3. Implement IDEA-005 (question generation + QA-driven retrieval) as first Tier 3 change — highest single-step accuracy gain per literature

---

## 180526 — Session: CheckThat! 2025 Task 2 PoC eval (claim extraction)

**Topic:** Designed and ran a small evaluation of the claim extraction step using gold-standard datasets, as proposed in `docs/pipeline_slides.tex` § "Claim Extraction".

**Setup:** GPT-OSS 120B (Groq), 100 EN posts from the CheckThat! 2025 Task 2 dev split, METEOR metric. 6 systems compared: ours (single-claim adaptation of `pipeline/claim_extraction.py`), dfkinit2b (#1 EN leaderboard zero-shot prompt), DS@GT (#2, CoT), AKCIT-FN (fidelity-focused), TIFIN (5W1H JSON), baseline (post-as-is).

**Results (METEOR, N=100):** ours 0.2934 > dsgt 0.2764 ≈ dfkinit2b 0.2759 > akcit 0.2662 > tifin 0.2617 > baseline 0.1870. Our prompt edged the top published EN prompts by ~0.017 — at threshold of meaningful at N=100.

**Deeper insight:** METEOR rewards *literal phrase preservation*, not semantic accuracy. dfkinit2b's structured-criteria prompt produces near-verbatim extractions and scores 0.80-0.98 when the gold is itself a verbatim lift. Our prompt synthesizes/abstracts, losing on extractive golds but winning when gold requires picking the right specifics.

**Implication for claims DB (IDEA-003):** consider storing both verbatim and synthesized forms per claim, linked by `claim_id` — covers paraphrase-match and wording-match failure modes.

**New idea logged ([IDEA-011]):** Use Data Commons ClaimReview live feed's `itemReviewed.appearance[].url` field as a free gold standard for evaluating Tier 3 source retrieval quality (~60% of entries have cited sources). Orthogonal to verdict-level eval.

**Caveats:** N=100 (CI ~±0.02), single model, English only. Did NOT replicate leaderboard winners' full systems (retrieval/ensemble/fine-tuning) — only their published zero-shot prompts.

**Artifacts:** `eval/scripts/checkthat_t2/`, report at `eval/scripts/checkthat_t2/results/REPORT.md`, full clog at `clog/180526.md`.
