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
TRAIT_NUDGE_SCALE = 0.1          # per-event trait deltas are scaled so the daily cap rarely binds
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

# --- Task 9 ---
SNN_INPUT_HZ = 150.0
SNN_SUBSTEPS = 20                # 1 ms substeps per bin
SNN_POP = 4                      # Poisson neurons per input unit
SNN_WMAX = 2.0
SNN_TARGET_HZ = 10.0
SNN_HOMEO_TAU_BINS = 50
SNN_HOMEO_GAIN = 0.5
SNN_PRED_LR = 0.3
SNN_BIAS_LR = 0.2                # slow: the bias is a base rate, not a short-term memory
SNN_FMEAN_RATE = 0.02            # running mean used to centre the readout features
SNN_LIF_DECAY = 0.9              # membrane decay per ms (tau ~ 10 ms)
SNN_V_THRESH = 1.0
SNN_REFRAC_MS = 2
SNN_P_IN = 0.2                   # Input->E density
SNN_P_EE = 0.1                   # E->E density
SNN_W_IN = 3.0                   # weight scale, divided by sqrt(fan_in)
SNN_W_EE = 1.0
SNN_W_EI = 2.0
SNN_W_IE = 2.0
SNN_TRACE_DECAY = 0.95           # STDP trace decay per ms
SNN_STDP_APLUS = 0.01
SNN_STDP_AMINUS = 0.0125
SNN_READOUT_DECAY = 0.5          # per-bin carry of the hidden rate vector (short memory)
SNN_SURPRISE_EMA = 0.3            # weight kept from the previous smoothed value
SNN_FAMILIARITY_BINS = 200

# --- Task 10 ---
QL_ALPHA = 0.1
QL_GAMMA = 0.5
FOOD_LIKING_INIT_SD = 0.3
FOOD_NOVELTY_COUNT = 3
FOOD_NOVELTY_GAIN = 0.05
FOOD_COMFORT_GAIN = 0.03
FOOD_NOISE_SD = 0.02

# --- Task 3 ---
INTERACT_WINDOW_S = 60.0   # seconds of a step during which an interaction suppresses tedio/carinho growth

# --- Task 8 ---
# M1 calibration: with 45-60 s actions and one action per tick, the base per-hour effects cannot offset
# tedio/curiosidade growth (needs >100% of awake time), so wellbeing stayed ~0.02. x3 gives ~0.69.
ACTION_RELIEF_SCALE = 3.0

# --- Final review fixes ---
SNN_BIN_S = 60.0                 # the SNN advances on fixed sim-time bins of this length (dt-invariant)
SNN_MAX_BINS_PER_STEP = 5        # a very long step (offline gap) runs at most this many bins
MODULE_MIN_RATE_FACTOR = 0.125   # live budget demotion never slows a module below 1/8 of its rate
MODULE_RECOVERY_RUNS = 50        # consecutive in-budget runs after which a demoted module speeds back up
SNN_BUDGET_MS = 10.0
