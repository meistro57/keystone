# filename: config.py
"""
Keystone — central config.

Anchored on cross-source CONCEPT THEMES (confirmed against live Qdrant 2026-07),
because vectoreology_findings in the current run carry no member lists. Everything
Keystone reads is named here so schema drift is a one-file fix.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _f(name, default): return float(os.getenv(name, default))
def _i(name, default): return int(os.getenv(name, default))


# ── Qdrant ────────────────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "") or None

REFLECTIONS_COLLECTION = os.getenv("REFLECTIONS_COLLECTION", "meta_reflections")
MISFIT_COLLECTION = os.getenv("MISFIT_COLLECTION", "misfit_reports")
FINDINGS_COLLECTION = os.getenv("FINDINGS_COLLECTION", "vectoreology_findings")  # future use
KEYSTONES_COLLECTION = os.getenv("KEYSTONES_COLLECTION", "keystones")

# meta_reflections is named-vector: claims_vec | summary_vec (both 3072d)
REFLECTION_VECTOR_NAME = os.getenv("REFLECTION_VECTOR_NAME", "summary_vec")

# ── Reflection payload fields (CONFIRMED via probe) ───────────────────────
R_SUMMARY = os.getenv("R_SUMMARY", "summary")
R_SOURCE = os.getenv("R_SOURCE", "source_id")
R_CONCEPTS = os.getenv("R_CONCEPTS", "concepts_norm")   # list[str], normalized
R_EMPTY = os.getenv("R_EMPTY", "is_empty_reflection")   # skip these
R_CONFIDENCE = os.getenv("R_CONFIDENCE", "reflection_confidence")

# ── Misfit rubric (parsed from the verdict text tail) ─────────────────────
M_VERDICT_FIELD = os.getenv("M_VERDICT_FIELD", "verdict")   # holds the JSON rubric
M_FALLBACK_FIELD = os.getenv("M_FALLBACK_FIELD", "report")
RUBRIC_CONSISTENCY = os.getenv("RUBRIC_CONSISTENCY", "logical_consistency_score")
RUBRIC_VALIDITY = os.getenv("RUBRIC_VALIDITY", "re_validity_score")
RUBRIC_DRIFT = os.getenv("RUBRIC_DRIFT", "drift_score")

# ── Theme selection ───────────────────────────────────────────────────────
MIN_MEMBERS = _i("MIN_MEMBERS", 6)       # reflections carrying the concept
MIN_SOURCES = _i("MIN_SOURCES", 3)       # distinct traditions it must span
COHERENCE_SAMPLE = _i("COHERENCE_SAMPLE", 60)   # cap vectors pulled per theme
# concepts too generic OR too boilerplate to be a thesis. The publishing/legal
# cluster below is Project Gutenberg license text polluting the reflections —
# worth a corpus_scrubber pass upstream too.
_DEFAULT_STOP = (
    "consciousness,reality,knowledge,truth,existence,mind,"
    "understanding,interaction,interpretation,influence,phenomena,"
    "derivative works,trademark license,digital distribution,redistribution,"
    "copyright,license,electronic works,project gutenberg,public domain,"
    "terms of use,digital format,royalty,copyright holder,copyright law,"
    "copyright notice,gutenberg"
)
STOP_CONCEPTS = {c.strip().lower() for c in os.getenv("STOP_CONCEPTS", _DEFAULT_STOP).split(",") if c.strip()}

# ── Convergence scoring ───────────────────────────────────────────────────
# convergence = centrality**Wc * coherence**Ws * survival**Wv   (multiplicative)
W_CENTRALITY = _f("W_CENTRALITY", 1.0)
W_COHERENCE = _f("W_COHERENCE", 1.0)
W_SURVIVAL = _f("W_SURVIVAL", 1.0)

# centrality = min(1, n_sources / SOURCE_SATURATION). Raised to 20 so breadth
# actually discriminates instead of everyone pinning at 1.0.
SOURCE_SATURATION = _f("SOURCE_SATURATION", 20.0)

# verbatim guard: coherence above this is suspiciously identical text (boilerplate,
# repeated passages) rather than genuine convergence — dock it. Set ceil to 1.0 to disable.
VERBATIM_CEIL = _f("VERBATIM_CEIL", 0.93)
VERBATIM_PENALTY = _f("VERBATIM_PENALTY", 0.4)

# members with no misfit report → neutral, not a fail
SURVIVAL_NEUTRAL = _f("SURVIVAL_NEUTRAL", 0.6)
MIN_CONVERGENCE = _f("MIN_CONVERGENCE", 0.45)

# ── LLM routing (OpenRouter, OpenAI-compatible) ───────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
SYNTH_MODEL = os.getenv("SYNTH_MODEL", "deepseek/deepseek-r1")
CRITIC_MODEL = os.getenv("CRITIC_MODEL", "google/gemma-3-27b-it")
LLM_TIMEOUT = _i("LLM_TIMEOUT", 180)

# DeepSeek direct (optional): if DEEPSEEK_API_KEY is set, the R1 synthesis call
# goes straight to DeepSeek instead of through OpenRouter (cheaper + faster for
# a 344-forge run). Gemma critic and embeddings are unaffected. Blank = fall
# back to OpenRouter with SYNTH_MODEL.
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
SYNTH_MODEL_DIRECT = os.getenv("SYNTH_MODEL_DIRECT", "deepseek-reasoner")

# ── Embeddings ────────────────────────────────────────────────────────────
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", OPENROUTER_BASE_URL)
EMBED_API_KEY = os.getenv("EMBED_API_KEY", OPENROUTER_API_KEY)
EMBED_MODEL = os.getenv("EMBED_MODEL", "google/gemini-embedding-001")  # matches your corpus
EMBED_DIM = _i("EMBED_DIM", 3072)

# ── Run behavior ──────────────────────────────────────────────────────────
LOG_DIR = os.getenv("LOG_DIR", "logs")
DATA_DIR = os.getenv("DATA_DIR", "data")
FORGE_WORKERS = _i("FORGE_WORKERS", 8)   # concurrent forge threads (R1+critic+embed are I/O-bound)
