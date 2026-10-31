"""Every tunable number. Constants only."""

# Time
HOUR = 3600.0
TICK_SIM_SECONDS = 1.0

# Needs (points per sim hour; high = urge)
NEED_RATES_PER_H = {"fome": 14.3, "sono": 6.25, "tedio": 66.7, "carinho": 25.0, "curiosidade": 33.3, "apoio": 0.0}
SLEEP_RECOVERY_PER_H = 25.0
EMPOLGACAO_DECAY_PER_H = 0.5
TRAIT_MAX_DRIFT_PER_DAY = 2.0

# Stages and care
STAGE_MIN_SECONDS = {"egg": 300.0, "baby": 36 * HOUR, "child": 7 * 24 * HOUR, "adult": 21 * 24 * HOUR, "perfect": 45 * 24 * HOUR}
CARE_MIN_TO_EVOLVE = 0.3
CARE_EMA_SECONDS = 6 * HOUR
EGG_HATCH_CLICKS = 5

# Brain
HIDDEN_BY_STAGE = {"egg": 32, "baby": 32, "child": 64, "adult": 96, "perfect": 128, "final": 160}
SNN_WEIGHT = 0.6
BANDIT_WEIGHT = 0.5

# Rewards: name -> (reward, trait nudges)
REWARDS = {
    "answered_ask": (1.0, {"sociabilidade": 0.5}),
    "ignored_ask": (-0.3, {"independencia": 0.3, "sociabilidade": -0.2}),
    "shared_project": (0.6, {"curiosidade": 0.5}),
    "played_together": (0.8, {}),
    "pet": (0.4, {}),
    "liked_food": (0.3, {}),
    "refused_food": (-0.1, {}),
}

# Behavior and asking
ASK_MIN_INTERVAL = 20 * 60.0
ASK_ANSWER_WINDOW = 120.0
BEHAVIOR_PERIOD = 5.0

# Offline and resources
OFFLINE_NEED_CAP = 70.0
AUTO_REST_MIN_FREE_MB = 1024
