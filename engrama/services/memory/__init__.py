DAY = 86400.0

# Task M4
SALIENCE_HALF_LIFE = 3 * DAY
CURRENT_MIN_SALIENCE = 0.35
PAST_MIN_AGE = 7 * DAY
PAST_MIN_AFFINITY = 0.3
MAX_EPISODES = 2000
MAX_FACTS = 300
MAX_TOPICS = 300
CONVERSATION_GAP_S = 120
INITIATIVE_PER_ACTIVE_S = 3600
ACTIVE_WINDOW_S = 300
OPPORTUNITY_EVERY_S = 60

# Task M9 (semantic recall; starting values, spec §10: calibrated only if a model is installed)
EMBED_BATCH = 16               # texts per index job
EMBED_MAX_CHARS = 500          # text cut before it goes to Ollama
EMBED_QUERY_TIMEOUT_S = 1.0    # query at chat time
EMBED_BATCH_TIMEOUT_S = 10.0   # index batch and warm-up
EMBED_RETRY_S = 60             # embedder "failed" before trying again
EMBED_CHECK_S = 300            # minimum interval between tags() checks
EMBED_DIM_MAX = 4096           # dimension above this = invalid response
INDEX_EVERY_S = 5              # minimum interval between index jobs
SEM_MIN_SIM = 0.42             # cosine below this does not count as related; calibrated in M13 (embeddinggemma), see docs/superpowers/reports/m13/calibration.md
FACT_MIN_SIM = 0.46            # fact enters by meaning; calibrated in M13 (embeddinggemma), see docs/superpowers/reports/m13/calibration.md
TOPIC_MIN_SIM = 0.27           # topic of an opinion by meaning; calibrated in M13 (embeddinggemma), see docs/superpowers/reports/m13/calibration.md
W_SEM = 0.7                    # meaning weight in relevance
W_WORD = 0.3                   # words weight in relevance
W_IMPORTANCE = 0.35            # episode with qvec
W_RECENCY = 0.15               # episode with qvec
W_RELEVANCE = 0.5              # episode with qvec
VECTOR_RAM_MAX_MB = 16         # cap for the in-memory matrix
SEARCH_BUDGET_MS = 20          # recall with qvec and full caps
