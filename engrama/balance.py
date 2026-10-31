HOUR = 3600.0
NEED_RATES_PER_H = {"fome": 14.3, "sono": 6.25, "tedio": 66.7, "carinho": 25.0, "curiosidade": 33.3, "apoio": 0.0}
SLEEP_RECOVERY_PER_H = 25.0
STAGE_MIN_SECONDS = {"egg": 300.0, "baby": 36 * HOUR, "child": 7 * 24 * HOUR, "adult": 21 * 24 * HOUR, "perfect": 45 * 24 * HOUR}
CARE_MIN_TO_EVOLVE = 0.3
CARE_EMA_SECONDS = 6 * HOUR
EGG_HATCH_CLICKS = 5
OFFLINE_NEED_CAP = 70.0
DECISION_PERIOD = 5.0            # sim-seconds between action decisions (at least once per tick)
ASK_MIN_INTERVAL = 20 * 60.0
ASK_ANSWER_WINDOW = 120.0
TRAIT_MAX_DRIFT_PER_DAY = 2.0
REWARD_WEIGHTS = {"need_relief": 1.0, "need_pain": -1.0, "user_response": 1.0, "ignored": -0.3,
                  "petting": 0.4, "msg_valence": 0.5, "novelty": 0.2}
MODULE_DEFAULT_BUDGET_MS = 5.0
MODULE_OVERBUDGET_STRIKES = 5
PAD_HALF_LIFE_S = 30 * 60.0
SNN_HIDDEN_BY_STAGE = {"egg": 32, "baby": 32, "child": 64, "adult": 96, "perfect": 128, "final": 160}
EXPLOG_CHANNEL_SAMPLE_S = 600.0  # blackboard snapshot into the log at most every 10 sim-minutes
EXPLOG_MAX_ROWS = 2_000_000

# --- Task 6 ---
DRIVE_MIDPOINTS = {"fome": 0.55, "sono": 0.6, "tedio": 0.5, "carinho": 0.5, "curiosidade": 0.5, "apoio": 0.6}
DRIVE_SLOPE = 0.08
# event kind -> (dP, dA, dD); "message" dP is multiplied by valence
APPRAISAL = {
    "pet": (0.15, 0.05, 0.0),
    "click": (0.05, 0.1, 0.0),
    "message": (0.2, 0.1, 0.0),
    "food": (0.1, 0.0, 0.05),
    "answered": (0.2, 0.1, 0.05),
    "fullscreen_on": (-0.05, -0.1, 0.0),
}
PAD_PRESSURE_P_PER_H = 0.3
PAD_PRESSURE_A_PER_H = 0.2
PAD_SURPRISE_GAIN = 0.3
PAD_NEUTRAL_RADIUS = 0.15

# --- Task 10 ---
QL_ALPHA = 0.1
QL_GAMMA = 0.5
FOOD_LIKING_INIT_SD = 0.3
FOOD_NOVELTY_COUNT = 3
FOOD_NOVELTY_GAIN = 0.05
FOOD_COMFORT_GAIN = 0.03
FOOD_NOISE_SD = 0.02
