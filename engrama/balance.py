HOUR = 3600.0
NEED_RATES_PER_H = {"fome": 14.3, "sono": 6.25, "tedio": 66.7, "carinho": 25.0, "curiosidade": 33.3, "apoio": 0.0}
SLEEP_RECOVERY_PER_H = 25.0
STAGE_MIN_SECONDS = {"egg": 300.0, "baby": 36 * HOUR, "child": 7 * 24 * HOUR, "adult": 21 * 24 * HOUR, "perfect": 45 * 24 * HOUR}
CARE_MIN_TO_EVOLVE = 0.3
CARE_EMA_SECONDS = 6 * HOUR
EGG_HATCH_CLICKS = 5
NEED_URGENT = 60.0              # a need above this (kernel scale, 0-100) shows in the HUD and colours her speech
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

# Task M3-5
HOST_TICK_S = 1.0               # real seconds between host ticks
AUTOSAVE_S = 300.0              # wall seconds between autosaves
REST_RAM_FREE_MB = 1000         # free RAM below this triggers rest
REST_IDLE_S = 1800.0            # no user input for this long triggers rest
SURPRISE_CURIOUS = 0.5          # temporal.surprise above this makes the creature "curious"

# M6
FINAL_LIFESPAN_S = 30 * 24 * HOUR
OLD_AGE_WARN_S = 3 * 24 * HOUR
NEGLECT_NEED_MEAN = 70.0
NEGLECT_SICK_AFTER_S = 6 * HOUR
CARE_RECOVER_NEED_MEAN = 40.0
SICK_SEVERITY_START = 0.3
SICK_SEVERITY_UP_PER_H = 0.03
SICK_SEVERITY_DOWN_PER_H = 0.05
GRAVE_SEVERITY = 0.8
GRAVE_DEATH_AFTER_S = 24 * HOUR
COLD_PER_ONLINE_H = 1.0 / (30 * 24)
COLD_MIN_S, COLD_MAX_S = 3 * HOUR, 8 * HOUR
COLD_MAX_SEVERITY = 0.4
MEDICINE_COOLDOWN_S = 6 * HOUR
MEDICINE_NEGLECT_RELIEF = 0.5
NEGLECT_BRANCH_CARE = 0.45
REDEEM_CARE = 0.7
TRAIT_INHERIT = 0.25
ANCESTRAL_MAX = 3
FAREWELL_S = 10.0

# M7
DIGITAL_REQUEST_MIN_GAP_S = 2 * HOUR
DIGITAL_REQUEST_TTL_S = 30 * 60
DIGITAL_REQUEST_P = 0.35          # chance de um ask_attention virar pedido digital
CURSOR_POLL_HZ = 10
CURSOR_NEAR_PX = 150
OVERLAY_WALK_PX_S = 40
# M17: living on the desktop
WINDOWS_POLL_HZ = 2          # window geometry is polled slower than the cursor
OVERLAY_FLEE_PX_S = 110      # a skittish creature running from the cursor
OVERLAY_HOP_S = (8.0, 20.0)  # how long it stays on a ledge before thinking of another one
FPS_OVERLAY_AIR = 30         # falling or hopping needs smoother frames than walking

# Task M8
FPS_FOCUSED = 20
FPS_STILL = 10
FPS_UNFOCUSED = 5
FPS_RESTING = 2
FPS_OVERLAY_MOVING = 10

# Task M10 (experimentos de ML; lab only, default-v1 unchanged)
M10_STATE_VERSION = 1             # versão do state_dict dos módulos novos
EXP_BUDGET_MS = 2.0               # mean_ms máximo de um módulo novo no lab (dt = 60)
CTRNN_HIDDEN = 64
CTRNN_TAU_MIN_BINS = 1.0          # bins de SNN_BIN_S
CTRNN_TAU_MAX_BINS = 1440.0       # 1 dia
CTRNN_SUBSTEPS = 4                # passos de Euler por bin
CTRNN_SPECTRAL_RADIUS = 0.9
CTRNN_P_REC = 0.2
CTRNN_W_IN = 1.0
CTRNN_BUDGET_MS = 5.0
WM_LR = 0.05                      # LMS normalizado do modelo de mundo
WM_ERR_EMA = 0.99                 # média móvel do erro (visualização e lab_metrics)
CUR_BETA = 0.3                    # peso do bônus intrínseco
CUR_BASELINE_EMA = 0.99           # média do erro no modo "surprise"
CUR_LP_FAST = 0.9                 # média rápida por ação no modo "progress"
CUR_LP_SLOW = 0.99                # média lenta por ação no modo "progress"
TS_SIGMA0 = 0.5                   # desvio inicial do Thompson
TS_NOISE_FLOOR = 0.05             # piso do desvio do erro de TD
TS_TD_VAR_EMA = 0.99              # média móvel da variância do erro de TD
TS_N_HALF_LIFE_DAYS = 7.0         # esquecimento das visitas
AIF_PRIOR = 1.0                   # contagem Beta inicial por resultado
AIF_PREF_SCALE = 2.0              # nats por unidade de REWARD_WEIGHTS
AIF_NOVELTY_WEIGHT = 1.0          # peso do ganho de informação
AIF_SOCIAL_GAIN = 1.0             # sociabilidade na preferência por resposta
AIF_COUNT_HALF_LIFE_DAYS = 7.0    # esquecimento das contagens em direção ao prior
SUITE_DAYS = 7.0                  # dias por corrida da suíte padrão
SUITE_ROUTINE_DAYS = 4.0          # dias do perfil routine (como no teste R21)
SUITE_SEEDS = (1, 2, 3)
SUITE_PROFILES = ("attentive", "absent", "neglectful", "routine")
