import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM: Step 1 — Claim extraction (Groq, Qwen3 32B) ---
EXTRACTION_BASE_URL = "https://api.groq.com/openai/v1"
EXTRACTION_MODEL = "qwen/qwen3-32b"
EXTRACTION_API_KEY = os.environ.get("GROQ_API_KEY", "")

# --- LLM: Step 2 — Claim verification (Groq, Llama 3.3 70B — temporary until DeepSeek funded) ---
VERIFICATION_BASE_URL = "https://api.groq.com/openai/v1"
VERIFICATION_MODEL = "llama-3.3-70b-versatile"
VERIFICATION_API_KEY = os.environ.get("GROQ_API_KEY", "")

# --- Search ---
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPER_ENDPOINT = "https://google.serper.dev/search"
SERPER_TOP_K = 3       # URLs per query
QUERIES_PER_CLAIM = 3  # search queries generated per atomic claim

# --- Retrieval ---
MAX_RETRIEVAL_ROUNDS = 5        # FIRE: max verification + retrieval iterations
FIRE_CONFIDENCE_THRESHOLD = 4  # label margin (top - 2nd) ≥ this → early exit (max possible = 4); NEI never exits early
FIRE_REDUNDANCY_THRESHOLD = 0.9  # cosine sim above this → redundant query, stop
SCRAPE_TIMEOUT = 10    # seconds per URL

# Evidence quality: reranking + MMR
RERANK_TOP_K = 10    # cross-encoder keeps top N items before MMR
MMR_FINAL_K = 5      # upper bound on items passed to the verifier
MMR_LAMBDA = 0.75    # λ: weight on relevance vs diversity in MMR
MMR_SCORE_THRESHOLD = 0.1  # stop adding items when best MMR score drops below this

# Per-domain scraping delay (randomized between min and max)
DOMAIN_DELAY_MIN = 2.0
DOMAIN_DELAY_MAX = 3.5

# --- Domain filtering ---
CRED1_MIN_SCORE = 0.3  # drop sources below this credibility score
CRED1_PATH = "domain_data/cred1.json"
IFFY_PATH = "domain_data/iffy.json"

# --- Scrape blocklist (login walls / hard paywalls — structurally unscrapable) ---
SCRAPE_BLOCKLIST = {
    "facebook.com", "m.facebook.com", "l.facebook.com",
    "twitter.com", "x.com", "t.co",
    "instagram.com",
    "reuters.com",
    "bloomberg.com", "bloomberg.net",
    "wsj.com",
    "ft.com",
    "tiktok.com",
    "linkedin.com",
    "youtube.com", "youtu.be",
}

# --- Google Fact Check Tools API ---
FCTAPI_KEY = os.environ.get("GOOGLE_FCTAPI_KEY", "")
FCTAPI_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
FCTAPI_MAX_RESULTS = 5

# --- Wikipedia ---
WIKIPEDIA_MAX_RESULTS = 2

# --- Verdict ---
VERDICT_OPTIONS = [
    "Supported",
    "Refuted",
    "Not Enough Evidence",
    "Conflicting Evidence",
]
VERDICT_CONFIDENCE_THRESHOLD = 0.65
