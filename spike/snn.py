"""Tiny spiking net: 10 input -> 20 hidden (recurrent) -> 10 output. LIF + pair STDP. numpy only."""
import numpy as np

NI, NH, NO = 10, 20, 10
NB = 6  # behaviors: idle, wander, play_alone, sleep, ask_attention, explore
OUT_MAP = np.array([0, 1, 1, 2, 2, 3, 4, 4, 5, 5])  # output neuron -> behavior group
IN_NAMES = ["click", "chat", "feed", "hunger", "boredom", "time", "noise", "sleepy", "lonely", "curious"]
# which behavior groups each input is (initially) wired to
PRIOR = [[4, 0], [4], [0], [4], [2, 1], [3], [5, 1], [3], [4], [5]]

DECAY = 0.95      # membrane leak per 1 ms step (tau ~ 20 ms)
THRESH = 1.0
REFRAC = 2
P_MAX = 0.2       # max Poisson spike prob per step for a stimulus of 1.0
TR_DECAY = 0.95   # STDP trace decay
A_PLUS, A_MINUS, WMAX = 0.004, 0.0045, 1.2


class SNN:
    def __init__(self, weights=None, seed=1):
        self.rng = np.random.default_rng(seed)
        hg = np.arange(NH) % NB
        prior = np.zeros((NI, NB))
        for i, gs in enumerate(PRIOR):
            prior[i, gs] = 1
        self.W_ih = self.rng.uniform(0, 0.12, (NI, NH)) + 0.42 * prior[:, hg]
        self.W_ho = self.rng.uniform(0, 0.04, (NH, NO)) + 0.55 * (hg[:, None] == OUT_MAP[None, :])
        same = (hg[:, None] == hg[None, :]).astype(float)
        self.W_hh = 0.05 * same - 0.006 * (1 - same)
        np.fill_diagonal(self.W_hh, 0)
        if weights:
            self.W_ih = np.array(weights["ih"]); self.W_ho = np.array(weights["ho"])
        self.v_h = np.zeros(NH); self.v_o = np.zeros(NO)
        self.ref_h = np.zeros(NH, int); self.ref_o = np.zeros(NO, int)
        self.sp_h = np.zeros(NH); self.sp_o = np.zeros(NO)
        self.tr_x = np.zeros(NI); self.tr_h = np.zeros(NH); self.tr_o = np.zeros(NO)
        self.T = 200
        self.raster = np.zeros((self.T, NI + NH + NO), bool)
        self.vm = np.zeros((self.T, 4))
        self.ptr = 0
        self.h_rate = 0.0                       # Hz-equivalent, mean over hidden
        self.out_rate = np.zeros(NO)            # Hz-equivalent per output neuron
        self.group_rate = np.zeros(NB)          # Hz-equivalent per behavior group
        self.arousal = 0.3

    def weights(self):
        return {"ih": self.W_ih.tolist(), "ho": self.W_ho.tolist()}

    def run(self, stim, n=30):
        """Run n 1ms steps with Poisson input of rates stim (10 values in 0..1)."""
        p = np.clip(np.asarray(stim, float), 0, 1) * P_MAX
        rng = self.rng
        cnt_h = np.zeros(NH); cnt_o = np.zeros(NO)
        for _ in range(n):
            x = (rng.random(NI) < p).astype(float)
            # hidden
            self.v_h = self.v_h * DECAY + x @ self.W_ih + self.sp_h @ self.W_hh
            self.v_h[self.ref_h > 0] = 0
            self.ref_h = np.maximum(self.ref_h - 1, 0)
            s_h = self.v_h >= THRESH
            self.v_h[s_h] = 0; self.ref_h[s_h] = REFRAC
            sh = s_h.astype(float)
            # output
            self.v_o = self.v_o * DECAY + sh @ self.W_ho
            self.v_o[self.ref_o > 0] = 0
            self.ref_o = np.maximum(self.ref_o - 1, 0)
            s_o = self.v_o >= THRESH
            self.v_o[s_o] = 0; self.ref_o[s_o] = REFRAC
            so = s_o.astype(float)
            # STDP (pair-based with traces), soft upper bound, clip
            self.tr_x *= TR_DECAY; self.tr_h *= TR_DECAY; self.tr_o *= TR_DECAY
            if sh.any() or x.any():
                self.W_ih += A_PLUS * (1 - self.W_ih / WMAX) * np.outer(self.tr_x, sh) - A_MINUS * np.outer(x, self.tr_h)
                np.clip(self.W_ih, 0, WMAX, out=self.W_ih)
            if so.any() or sh.any():
                self.W_ho += A_PLUS * (1 - self.W_ho / WMAX) * np.outer(self.tr_h, so) - A_MINUS * np.outer(sh, self.tr_o)
                np.clip(self.W_ho, 0, WMAX, out=self.W_ho)
            self.tr_x += x; self.tr_h += sh; self.tr_o += so
            self.sp_h = sh; self.sp_o = so
            cnt_h += sh; cnt_o += so
            self.raster[self.ptr, :NI] = x > 0
            self.raster[self.ptr, NI:NI + NH] = sh > 0
            self.raster[self.ptr, NI + NH:] = so > 0
            self.vm[self.ptr] = (self.v_h[0], self.v_h[7], self.v_o[0], self.v_o[8])
            self.ptr = (self.ptr + 1) % self.T
        a = 0.3
        self.h_rate = (1 - a) * self.h_rate + a * cnt_h.mean() / n * 1000
        self.out_rate = (1 - a) * self.out_rate + a * cnt_o / n * 1000
        for b in range(NB):
            self.group_rate[b] = self.out_rate[OUT_MAP == b].mean()
        self.arousal = 0.9 * self.arousal + 0.1 * float(np.clip(self.h_rate / 30.0, 0, 1))

    def ordered(self):
        """raster/vm in chronological order for drawing"""
        return np.roll(self.raster, -self.ptr, axis=0), np.roll(self.vm, -self.ptr, axis=0)
