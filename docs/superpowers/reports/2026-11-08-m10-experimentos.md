# M10 — Experimentos de ML: relatório de comparação do laboratório

Este relatório compara, no laboratório, a criatura padrão (`default-v1`) com sete receitas que trocam **uma peça** da mente (e uma linha exploratória, `aif-solo-v1`). O M10 **só mede**: nenhum experimento é promovido a padrão (spec §2). Tudo abaixo vem do usuário simulado, com 3 sementes; leia a seção 7 antes de tirar conclusões.

Regra de escrita: só se diz que um experimento "melhora" ou "piora" uma métrica quando a diferença pareada tem o **mesmo sinal nas 3 sementes** (marca `*` nas tabelas). Sem `*`: "sem efeito consistente". Mesmo com `*`, 3 sementes não dão significância (com sinal aleatório, a chance de 3 iguais é 25%), e o tamanho da diferença é comparado com o desvio entre sementes.

## 1. Como reproduzir

- Base: branch `m10` no commit `70d0346` (Tarefas 0–5 integradas), mais as duas receitas desta tarefa (`recipes/lab-shadow-all-v1.toml`, `recipes/aif-solo-v1.toml`). Máquina: CachyOS, 8 núcleos, 7 GB de RAM.
- Ambiente: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`, `./.venv/bin/python`.
- Suíte completa (8 receitas × 4 perfis × 3 sementes = 96 corridas; `attentive`/`absent`/`neglectful` com 7 dias, `routine` com 4; `dt = 60`):

```
python -m engrama.lab suite --preset m10 --jobs 4 \
  --out docs/superpowers/reports/2026-11-08-m10-experimentos.json --md tabela.md
```

  Tempo de parede medido: **4 min 52 s** (`--jobs 4`; ≈19 min de CPU). O JSON completo (corridas e resumo) está em `docs/superpowers/reports/2026-11-08-m10-experimentos.json`.
- Medidas extras desta análise (não fazem parte do preset): `default-v1` + `lab-shadow-all-v1` + duas receitas de ablação da CTRNN só com viés (`readout_hidden = false`, ao vivo e em sombra; as mesmas receitas `ctrnn-v1` e `shadow-ctrnn-v1` com essa linha a mais em `temporal.ctrnn`):

```
python -m engrama.lab suite --recipes recipes/default-v1.toml recipes/lab-shadow-all-v1.toml \
  ctrnn-bias-live.toml ctrnn-bias-shadow.toml --jobs 4 --out extra.json --md extra.md
```

  (2 min 29 s.) Nessa execução, as ações e métricas vivas de `lab-shadow-all-v1` saíram idênticas às de `default-v1` nas 12 corridas (bem-estar, retorno, satisfação, entropia).
- Bench headless de cada receita: `python tools/bench.py --recipe recipes/<r>.toml --seconds 30`.

## 2. Tabela da suíte

Células: média ± dp entre sementes; para as receitas que não são a base, `Δ` é a diferença pareada média para `default-v1`, com `*` quando o sinal é o mesmo nas 3 sementes. Saída direta de `to_markdown` (colunas padrão). `shadow-ctrnn-v1` é idêntica ao padrão nas métricas vivas por construção (Δ = 0); ela existe para o Brier da sombra (seção 3). `lives/*` só tem sentido no `neglectful`, o único perfil em que a criatura morre.

### absent

| recipe | wellbeing | need_satisfaction | return_per_day | behavior_entropy | decision_entropy | answered_rate | ignored_rate | novelty_per_day | pred_brier/temporal.expectation | world_error_mean/world.error | lives/life_days_mean | lives/generations_finished |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aif-solo-v1 | 0.02867 ± 0.003211 (Δ+0.00172) | 0.4937 ± 0.003319 (Δ-0.0061*) | -15.49 ± 2.529 (Δ-1.55) | 2.633 ± 0.01828 (Δ-0.0932*) | 2.624 ± 0.002346 (Δ-0.0847*) | 0.01396 ± 0.006485 (Δ+7.99e-05) | 0.8371 ± 0.008594 (Δ+0.0218*) | 0.1429 ± 0 (Δ+0) | 0.0008307 ± 0.0001287 (Δ-3.39e-05) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| aif-v1 | 0.02648 ± 0.0005734 (Δ-0.000463) | 0.498 ± 0.0006806 (Δ-0.0018*) | -13.2 ± 0.5089 (Δ+0.746) | 2.714 ± 0.002744 (Δ-0.0121) | 2.714 ± 0.002744 (Δ+0.0061*) | 0.01367 ± 0.004636 (Δ-0.000211) | 0.8083 ± 0.01518 (Δ-0.00707) | 0.1429 ± 0 (Δ+0) | 0.0008057 ± 7.947e-05 (Δ-5.89e-05*) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| ctrnn-v1 | 0.02549 ± 0.0005734 (Δ-0.00146) | 0.5004 ± 0.001615 (Δ+0.000597) | -14.36 ± 0.4164 (Δ-0.416) | 2.72 ± 0.02203 (Δ-0.00612) | 2.708 ± 0.00126 (Δ+8.83e-05) | 0.00978 ± 0.004114 (Δ-0.0041) | 0.8275 ± 0.02176 (Δ+0.0121) | 0.1429 ± 0 (Δ+0) | 0.0008007 ± 8.861e-05 (Δ-6.39e-05) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-lp-v1 | 0.02691 ± 0.002249 (Δ-3.31e-05) | 0.5004 ± 0.0009433 (Δ+0.000557) | -13.79 ± 0.2788 (Δ+0.154) | 2.721 ± 0.02295 (Δ-0.00518) | 2.709 ± 0.002195 (Δ+0.00103) | 0.01615 ± 0.0009841 (Δ+0.00228) | 0.8197 ± 0.02028 (Δ+0.00432) | 0.1429 ± 0 (Δ+0) | 0.000805 ± 5.959e-05 (Δ-5.96e-05) | 0.004361 ± 7.036e-05 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-v1 | 0.02662 ± 0.002291 (Δ-0.000331) | 0.5012 ± 0.0007587 (Δ+0.00135) | -14.04 ± 0.1812 (Δ-0.0921) | 2.709 ± 0.001942 (Δ-0.0176) | 2.709 ± 0.001942 (Δ+0.000635) | 0.01382 ± 0.00647 (Δ-5.91e-05) | 0.8158 ± 0.01867 (Δ+0.000421) | 0.1429 ± 0 (Δ+0) | 0.000818 ± 0.000115 (Δ-4.66e-05) | 0.004291 ± 6.489e-05 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| default-v1 | 0.02695 ± 0.002853 | 0.4998 ± 0.001178 | -13.95 ± 0.6441 | 2.726 ± 0.02982 | 2.708 ± 0.003021 | 0.01388 ± 0.002299 | 0.8154 ± 0.01161 | 0.1429 ± 0 | 0.0008646 ± 6.361e-05 | — | 0 ± 0 | 0 ± 0 |
| shadow-ctrnn-v1 | 0.02695 ± 0.002853 (Δ+0) | 0.4998 ± 0.001178 (Δ+0) | -13.95 ± 0.6441 (Δ+0) | 2.726 ± 0.02982 (Δ+0) | 2.708 ± 0.003021 (Δ+0) | 0.01388 ± 0.002299 (Δ+0) | 0.8154 ± 0.01161 (Δ+0) | 0.1429 ± 0 (Δ+0) | 0.0008646 ± 6.361e-05 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| thompson-v1 | 0.02582 ± 0 (Δ-0.00113) | 0.4999 ± 0.001829 (Δ+4.11e-05) | -13.86 ± 0.6173 (Δ+0.0875) | 2.723 ± 0.02438 (Δ-0.0038) | 2.708 ± 0.0006137 (Δ+1.22e-05) | 0.01478 ± 0.002128 (Δ+0.0009*) | 0.8185 ± 0.00905 (Δ+0.00311) | 0.1429 ± 0 (Δ+0) | 0.0008649 ± 0.0001267 (Δ+3.21e-07) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |

### attentive

| recipe | wellbeing | need_satisfaction | return_per_day | behavior_entropy | decision_entropy | answered_rate | ignored_rate | novelty_per_day | pred_brier/temporal.expectation | world_error_mean/world.error | lives/life_days_mean | lives/generations_finished |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aif-solo-v1 | 0.6524 ± 0.01384 (Δ-0.0249) | 0.6658 ± 0.007901 (Δ+0.0368*) | 42.78 ± 2.234 (Δ+2.13) | 2.786 ± 0.02768 (Δ+0.0424*) | 2.73 ± 0.004097 (Δ+0.0337*) | 0.4822 ± 0.01415 (Δ+0.0426*) | 0.4385 ± 0.007255 (Δ-0.0398*) | 0.4286 ± 0 (Δ+0) | 0.007674 ± 0.0002813 (Δ+0.000667*) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| aif-v1 | 0.6597 ± 0.01229 (Δ-0.0176) | 0.6253 ± 0.009591 (Δ-0.00362) | 41.11 ± 1.252 (Δ+0.461) | 2.807 ± 0.02214 (Δ+0.0639*) | 2.74 ± 0.007362 (Δ+0.0428*) | 0.4435 ± 0.01391 (Δ+0.00397*) | 0.4532 ± 0.01357 (Δ-0.0251*) | 0.4286 ± 0 (Δ+0) | 0.007464 ± 0.0004121 (Δ+0.000458) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| ctrnn-v1 | 0.6337 ± 0.01823 (Δ-0.0436*) | 0.6174 ± 0.01108 (Δ-0.0116*) | 40.41 ± 2.209 (Δ-0.244) | 2.759 ± 0.01545 (Δ+0.0154*) | 2.708 ± 0.0117 (Δ+0.0117*) | 0.4468 ± 0.01425 (Δ+0.00728) | 0.4682 ± 0.02295 (Δ-0.01) | 0.4286 ± 0 (Δ+0) | 0.006901 ± 0.0002164 (Δ-0.000106) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-lp-v1 | 0.6517 ± 0.008671 (Δ-0.0256) | 0.6226 ± 0.002169 (Δ-0.0064) | 40.8 ± 1.519 (Δ+0.151) | 2.757 ± 0.01131 (Δ+0.0134*) | 2.706 ± 0.0005659 (Δ+0.00944*) | 0.4424 ± 0.02278 (Δ+0.00287) | 0.4696 ± 0.01844 (Δ-0.00867) | 0.4286 ± 0 (Δ+0) | 0.007084 ± 0.0002004 (Δ+7.75e-05) | 0.01303 ± 0.000147 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-v1 | 0.6663 ± 0.001918 (Δ-0.011) | 0.6223 ± 0.00566 (Δ-0.00664) | 41.24 ± 1.736 (Δ+0.592) | 2.761 ± 0.01464 (Δ+0.0174*) | 2.706 ± 0.002811 (Δ+0.00961*) | 0.4376 ± 0.01183 (Δ-0.00191) | 0.4629 ± 0.02591 (Δ-0.0153) | 0.4286 ± 0 (Δ+0) | 0.007071 ± 0.000328 (Δ+6.42e-05) | 0.01291 ± 0.0002895 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| default-v1 | 0.6773 ± 0.02898 | 0.629 ± 0.01047 | 40.65 ± 1.428 | 2.743 ± 0.01603 | 2.697 ± 0.004919 | 0.4395 ± 0.01429 | 0.4782 ± 0.01732 | 0.4286 ± 0 | 0.007007 ± 0.0003468 | — | 0 ± 0 | 0 ± 0 |
| shadow-ctrnn-v1 | 0.6773 ± 0.02898 (Δ+0) | 0.629 ± 0.01047 (Δ+0) | 40.65 ± 1.428 (Δ+0) | 2.743 ± 0.01603 (Δ+0) | 2.697 ± 0.004919 (Δ+0) | 0.4395 ± 0.01429 (Δ+0) | 0.4782 ± 0.01732 (Δ+0) | 0.4286 ± 0 (Δ+0) | 0.007007 ± 0.0003468 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| thompson-v1 | 0.6443 ± 0.05612 (Δ-0.033) | 0.6184 ± 0.01353 (Δ-0.0106*) | 38.94 ± 0.631 (Δ-1.71) | 2.751 ± 0.02683 (Δ+0.008) | 2.687 ± 0.01597 (Δ-0.00956*) | 0.4316 ± 0.004446 (Δ-0.00795) | 0.4865 ± 0.02086 (Δ+0.00821) | 0.4286 ± 0 (Δ+0) | 0.006889 ± 0.0003548 (Δ-0.000118) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |

### neglectful

| recipe | wellbeing | need_satisfaction | return_per_day | behavior_entropy | decision_entropy | answered_rate | ignored_rate | novelty_per_day | pred_brier/temporal.expectation | world_error_mean/world.error | lives/life_days_mean | lives/generations_finished |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aif-solo-v1 | 0.04965 ± 0.004029 (Δ+0.0185*) | 0.3335 ± 0.01527 (Δ+0.00627) | -12.11 ± 0.4757 (Δ+1.69*) | 2.247 ± 0.09946 (Δ+0.118*) | 2.446 ± 0.04008 (Δ+0.134*) | 0 ± 0 (Δ+0) | 0.8651 ± 0.01246 (Δ-0.0208*) | 0.2857 ± 0 (Δ+0.0952) | 0.006299 ± 0.0006296 (Δ+0.000118) | — | 3.569 ± 1.041 (Δ+1.9) | 1 ± 0 (Δ+0.667) |
| aif-v1 | 0.03561 ± 0.01202 (Δ+0.0045) | 0.3313 ± 0.005221 (Δ+0.00409*) | -14.3 ± 1.295 (Δ-0.5) | 2.222 ± 0.08829 (Δ+0.092*) | 2.353 ± 0.1131 (Δ+0.0411) | 0 ± 0 (Δ+0) | 0.8649 ± 0.01436 (Δ-0.021*) | 0.2381 ± 0.08248 (Δ+0.0476) | 0.006347 ± 0.0005894 (Δ+0.000166) | — | 3.044 ± 2.651 (Δ+1.37) | 0.6667 ± 0.5774 (Δ+0.333) |
| ctrnn-v1 | 0.03464 ± 0.012 (Δ+0.00354) | 0.329 ± 0.01188 (Δ+0.00176) | -14.51 ± 2.132 (Δ-0.714) | 2.173 ± 0.1231 (Δ+0.0436*) | 2.362 ± 0.1127 (Δ+0.0504*) | 0 ± 0 (Δ+0) | 0.8805 ± 0.007436 (Δ-0.00545) | 0.2381 ± 0.08248 (Δ+0.0476) | 0.006281 ± 9.249e-05 (Δ+0.0001) | — | 4.015 ± 3.528 (Δ+2.34) | 0.6667 ± 0.5774 (Δ+0.333) |
| curious-lp-v1 | 0.04414 ± 0.002514 (Δ+0.013) | 0.3315 ± 0.003255 (Δ+0.00427*) | -14.22 ± 1.414 (Δ-0.42) | 2.188 ± 0.118 (Δ+0.0584*) | 2.401 ± 0.05583 (Δ+0.0893*) | 0 ± 0 (Δ+0) | 0.8658 ± 0.01689 (Δ-0.0201*) | 0.2857 ± 0 (Δ+0.0952) | 0.006553 ± 0.0003294 (Δ+0.000372*) | 0.01141 ± 0.0001654 | 5.819 ± 0.9438 (Δ+4.15) | 1 ± 0 (Δ+0.667) |
| curious-v1 | 0.02928 ± 0.01131 (Δ-0.00183) | 0.3317 ± 0.001566 (Δ+0.00452*) | -14.98 ± 1.048 (Δ-1.19*) | 2.162 ± 0.05444 (Δ+0.0326*) | 2.333 ± 0.02106 (Δ+0.0207) | 0 ± 0 (Δ+0) | 0.9021 ± 0.0197 (Δ+0.0162) | 0.1905 ± 0.08248 (Δ+0) | 0.006237 ± 0.0005161 (Δ+5.57e-05) | 0.01077 ± 0.001416 | 1.618 ± 2.803 (Δ-0.0532) | 0.3333 ± 0.5774 (Δ+0) |
| default-v1 | 0.03111 ± 0.01377 | 0.3272 ± 0.00589 | -13.8 ± 0.7409 | 2.13 ± 0.07614 | 2.312 ± 0.07552 | 0 ± 0 | 0.8859 ± 0.01182 | 0.1905 ± 0.08248 | 0.006181 ± 0.0002317 | — | 1.671 ± 2.895 | 0.3333 ± 0.5774 |
| shadow-ctrnn-v1 | 0.03111 ± 0.01377 (Δ+0) | 0.3272 ± 0.00589 (Δ+0) | -13.8 ± 0.7409 (Δ+0) | 2.13 ± 0.07614 (Δ+0) | 2.312 ± 0.07552 (Δ+0) | 0 ± 0 (Δ+0) | 0.8859 ± 0.01182 (Δ+0) | 0.1905 ± 0.08248 (Δ+0) | 0.006181 ± 0.0002317 (Δ+0) | — | 1.671 ± 2.895 (Δ+0) | 0.3333 ± 0.5774 (Δ+0) |
| thompson-v1 | 0.03041 ± 0.0136 (Δ-0.000694*) | 0.3281 ± 0.003955 (Δ+0.000847) | -14.31 ± 2.009 (Δ-0.511) | 2.15 ± 0.0446 (Δ+0.02) | 2.325 ± 0.05857 (Δ+0.0129) | 0 ± 0 (Δ+0) | 0.8696 ± 0.03301 (Δ-0.0163) | 0.1905 ± 0.08248 (Δ+0) | 0.005935 ± 0.0004016 (Δ-0.000246) | — | 0.8521 ± 1.476 (Δ-0.819) | 0.3333 ± 0.5774 (Δ+0) |

### routine

| recipe | wellbeing | need_satisfaction | return_per_day | behavior_entropy | decision_entropy | answered_rate | ignored_rate | novelty_per_day | pred_brier/temporal.expectation | world_error_mean/world.error | lives/life_days_mean | lives/generations_finished |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| aif-solo-v1 | 0.06505 ± 0.001254 (Δ+0.00383*) | 0.5388 ± 0.004148 (Δ+0.00254) | 23.83 ± 1.411 (Δ-2.07*) | 2.718 ± 0.003429 (Δ+0.0355*) | 2.718 ± 0.003429 (Δ+0.0355*) | 0.1745 ± 0.009679 (Δ+0.00367) | 0.672 ± 0.007561 (Δ-0.0307*) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| aif-v1 | 0.06227 ± 0.001254 (Δ+0.00104) | 0.534 ± 0.002171 (Δ-0.00226*) | 27.57 ± 1.064 (Δ+1.67*) | 2.743 ± 0.001544 (Δ+0.0602*) | 2.743 ± 0.001544 (Δ+0.0602*) | 0.1738 ± 0.007715 (Δ+0.00292) | 0.6691 ± 0.01473 (Δ-0.0336*) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| ctrnn-v1 | 0.06123 ± 0 (Δ+0) | 0.5357 ± 0.00172 (Δ-0.000577*) | 25.76 ± 0.7661 (Δ-0.146) | 2.685 ± 0.005904 (Δ+0.00187) | 2.685 ± 0.005904 (Δ+0.00187) | 0.1669 ± 0.009828 (Δ-0.00396*) | 0.697 ± 0.005253 (Δ-0.0057*) | 0 ± 0 (Δ+0) | 0.004796 ± 0.0001264 (Δ-0.000467*) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-lp-v1 | 0.05937 ± 0.001004 (Δ-0.00186*) | 0.5376 ± 0.002558 (Δ+0.00131) | 25.09 ± 0.3977 (Δ-0.807) | 2.683 ± 0.003582 (Δ+0.000276) | 2.683 ± 0.003582 (Δ+0.000276) | 0.1634 ± 0.002295 (Δ-0.00747*) | 0.7076 ± 0.02183 (Δ+0.00485) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | 0.01177 ± 1.54e-05 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| curious-v1 | 0.05937 ± 0.001004 (Δ-0.00186*) | 0.5373 ± 0.002029 (Δ+0.0011) | 25.83 ± 0.2686 (Δ-0.0668) | 2.682 ± 0.002988 (Δ-0.000448) | 2.682 ± 0.002988 (Δ-0.000448) | 0.1741 ± 0.003671 (Δ+0.00321) | 0.7044 ± 0.01901 (Δ+0.00166) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | 0.01178 ± 1.664e-05 | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| default-v1 | 0.06123 ± 0 | 0.5362 ± 0.001711 | 25.9 ± 0.8419 | 2.683 ± 0.003337 | 2.683 ± 0.003337 | 0.1708 ± 0.009588 | 0.7027 ± 0.003185 | 0 ± 0 | 0.005262 ± 3.251e-05 | — | 0 ± 0 | 0 ± 0 |
| shadow-ctrnn-v1 | 0.06123 ± 0 (Δ+0) | 0.5362 ± 0.001711 (Δ+0) | 25.9 ± 0.8419 (Δ+0) | 2.683 ± 0.003337 (Δ+0) | 2.683 ± 0.003337 (Δ+0) | 0.1708 ± 0.009588 (Δ+0) | 0.7027 ± 0.003185 (Δ+0) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |
| thompson-v1 | 0.06158 ± 0.001254 (Δ+0.000348) | 0.536 ± 0.002271 (Δ-0.000207) | 26.2 ± 1.265 (Δ+0.295) | 2.682 ± 0.002041 (Δ-0.000248) | 2.682 ± 0.002041 (Δ-0.000248) | 0.1756 ± 0.01593 (Δ+0.00478) | 0.6999 ± 0.01332 (Δ-0.00279) | 0 ± 0 (Δ+0) | 0.005262 ± 3.251e-05 (Δ+0) | — | 0 ± 0 (Δ+0) | 0 ± 0 (Δ+0) |

### Resumo dos sinais consistentes (`*`) contra o padrão

Direção boa: mais bem-estar, satisfação das necessidades, retorno, respostas e vida. Entropias não têm direção boa; só se registra o sentido. `Brier`: menor é melhor.

| receita | attentive | absent | neglectful | routine |
|---|---|---|---|---|
| `ctrnn-v1` | bem-estar −0,044 e satisfação −0,012 (piora); entropia + | nada | entropia + | satisfação −0,0006 e respostas −0,004 (piora irrelevante); Brier −0,00047 (melhora, ver §3) |
| `curious-v1` | entropia + | nada | satisfação +0,0045 (melhora); retorno −1,2 (piora) | bem-estar −0,0019 (piora) |
| `curious-lp-v1` | entropia + | nada | satisfação +0,0043; Brier +0,00037 (piora) | bem-estar −0,0019 e respostas −0,0075 (piora) |
| `thompson-v1` | satisfação −0,011 (piora); entropia de decisão − | respostas +0,0009 | bem-estar −0,0007 (piora irrelevante frente ao dp de 0,014) | nada |
| `aif-v1` | respostas +0,004; entropia + | satisfação −0,0018 (piora) | satisfação +0,004 | satisfação −0,0023 (piora); retorno +1,7 (melhora) |
| `aif-solo-v1` (exploratória) | satisfação +0,037, respostas +0,043 (melhora); Brier +0,0007 (piora) | satisfação −0,006 (piora) | bem-estar +0,019 e retorno +1,7 (melhora) | bem-estar +0,004 (melhora); retorno −2,1 (piora) |

Não houve, em nenhum perfil, um experimento que domine o padrão: o bem-estar do `attentive` é menor (média) em todas as receitas, e só `ctrnn-v1` o faz com sinal consistente. Perdas e ganhos são pequenos perto do desvio entre sementes, salvo `aif-solo-v1`.

## 3. Efeitos diretos

### 3.1 CTRNN: Brier contra a SNN e contra a ablação só com viés

Brier do próximo bin (média da segunda metade da corrida, por semente 1/2/3, ×10⁻³; menor é melhor). "Sombra" é a CTRNN em `shadow-ctrnn-v1` na **mesma vida** da SNN viva do padrão; "ao vivo" é `ctrnn-v1`. A ablação só com viés usa `readout_hidden = false`.

| perfil | SNN (padrão, ao vivo) | CTRNN sombra | só viés sombra | CTRNN ao vivo | só viés ao vivo |
|---|---|---|---|---|---|
| routine | 5,275 / 5,225 / 5,286 | **4,939 / 4,576 / 4,380** | 5,508 / 5,508 / 5,508 | 4,823 / 4,907 / 4,658 | 5,508 / 5,508 / 5,508 |
| attentive | 7,181 / 7,232 / 6,607 | 7,102 / 7,158 / 6,547 | 7,154 / 7,203 / 6,585 | 7,151 / 6,780 / 6,772 | 7,426 / 7,203 / 6,879 |
| neglectful | 6,180 / 5,949 / 6,413 | 6,094 / 5,932 / 6,382 | 6,266 / 5,929 / 6,379 | 6,201 / 6,260 / 6,382 | 6,266 / 5,874 / 6,379 |
| absent | 0,891 / 0,911 / 0,792 | 0,883 / 0,902 / 0,788 | 0,891 / 0,911 / 0,793 | 0,903 / 0,748 / 0,751 | 0,851 / 0,575 / 0,812 |

- **`routine` (o caso do teste R21):** a CTRNN ganha da ablação só com viés nas 3 sementes: em sombra 10,3%, 16,9% e 20,5%; ao vivo 12,4%, 10,9% e 15,4%. Contra a SNN: em sombra 6,4%, 12,4% e 17,1%; ao vivo 8,6%, 6,1% e 11,9%. (A SNN ganha 4,2–4,5% do viés, como no M2.) O alvo do teste (CTRNN não pior que o viés) foi cumprido; o ganho é **reportado, não exigido**.
- **`attentive`:** em sombra, a CTRNN é um pouco melhor que a SNN e que o viés nas 3 sementes (≈1% e ≈0,6%), diferenças minúsculas, na prática empate. Ao vivo, o ganho sobre o viés é +3,7% / +5,9% / +1,6%, mas sobre a SNN o sinal muda (+0,4 / +6,2 / −2,5%): sem efeito consistente.
- **`neglectful` e `absent`:** sem efeito consistente (ao vivo, no `absent`, o ganho sobre o viés oscila entre −30% e +8% conforme a semente, e o Brier é da ordem de 10⁻³). Perfis com poucos eventos têm Brier baixo e pouco a aprender.
- Em `ctrnn_h_abs_mean` e `ctrnn_surprise_mean` (`lab_metrics`), o estado oculto fica limitado (|h| médio 0,28–0,41) em todas as corridas: não houve saturação nem `NaN`.

### 3.2 Modelo de mundo e curiosidade (`curious-v1`, `curious-lp-v1`)

| perfil | erro do `world.model` (média, ×10⁻³) | `bonus_share` (surprise) | `bonus_share` (progress) |
|---|---|---|---|
| attentive | 12,9 | 0,102 | 0,051 |
| absent | 4,3 | 0,103 | 0,100 |
| neglectful | 10,8 | 0,094 | 0,059 |
| routine | 11,8 | 0,065 | 0,052 |

`bonus_share` é a fração do retorno total vinda do bônus intrínseco (`beta = 0,3`). Ele fica entre 5% e 10%: o bônus existe e não domina. O erro do modelo de mundo (`world_error_ema`) cai a 10⁻⁴–10⁻³ nas vidas estáveis e sobe no `neglectful` (4–8×10⁻³), onde a criatura adoece e morre e o ambiente muda. Efeito indireto sobre o comportamento: a entropia do comportamento sobe (+0,013 a +0,06) com `*` no `attentive` e no `neglectful`, mas o bem-estar não melhora em nenhum perfil. O modo `"progress"` (`curious-lp-v1`) tem menos bônus e comportamento quase igual ao `"surprise"`; não há sinal de "TV com chiado" (risco 2 da spec): no `attentive` nenhuma ação passa de 21% do tempo, e a entropia das decisões fica em 2,7 bits, igual ao padrão.

### 3.3 Thompson (`thompson-v1`)

| perfil | `sd_mean` | `explore_rate` |
|---|---|---|
| attentive | 0,042 | 0,331 |
| absent | 0,041 | 0,419 |
| neglectful | 0,078 (dp 0,030) | 0,104 |
| routine | 0,041 | 0,468 |

O desvio posterior encolhe de 0,5 (`TS_SIGMA0`) para ≈0,04 na média da vida. `explore_rate` é a fração de decisões em que a ação de maior amostra difere da de maior média. Um `explore_rate` de 33–47% com `sd_mean` baixo sugere que muitas ações têm valores próximos (a amostra desempata entre elas), e não incerteza alta; o `neglectful` tem `explore_rate` menor (0,10) e `sd_mean` maior e mais variável entre sementes (0,078, dp 0,030). Não investiguei a causa; é uma leitura, não um resultado.

### 3.4 Inferência ativa (`aif-v1`, `aif-solo-v1`)

| perfil | `novelty_share` (v1 / solo) | `g_spread_mean` (v1 / solo) |
|---|---|---|
| attentive | 0,011 / 0,010 | 0,58 / 0,52 |
| absent | 0,011 / 0,011 | 0,97 / 0,76 |
| neglectful | 0,014 / 0,014 | 0,49 / 0,41 |
| routine | 0,017 / 0,017 | 0,76 / 0,63 |

O termo epistêmico (ganho de informação) responde por cerca de 1–1,7% da energia livre esperada: na prática, a inferência ativa decide pelo termo pragmático (`pragmatic_mean` ≈ 7,6–7,8 nats). Ou seja, com `AIF_NOVELTY_WEIGHT = 1,0` ela se comporta como um escolhedor de recompensa esperada com preferências, e o que ela traz de "curiosidade" é pequeno. O `g_spread_mean` (diferença entre a melhor e a pior ação) é de 0,4–1,0 nat, contra uma temperatura do árbitro de 0,5: o sinal chega ao árbitro, e por isso `aif-solo-v1`, sem a utilidade, se sustenta.

### 3.5 Todas as sombras juntas (`lab-shadow-all-v1`)

Sombras sempre ao lado do padrão vivo (média das 3 sementes; ×10⁻³ onde indicado):

| perfil | Brier CTRNN sombra | erro `world.model` sombra | `explore_rate` Thompson sombra | `novelty_share` AIF sombra |
|---|---|---|---|---|
| routine | 4,63 | 11,8 | 0,47 | 0,0187 |
| attentive | 6,94 | 13,0 | 0,34 | 0,0121 |
| neglectful | 6,13 | 10,7 | 0,11 | 0,0119 |
| absent | 0,85 | 4,3 | 0,41 | 0,0117 |

Os valores batem com os das receitas ao vivo, o que indica que o modelo de mundo, o Thompson e a inferência ativa aprendem do mesmo fluxo de experiências mesmo sem decidir. As ações vivas ficaram idênticas às do padrão.

## 4. Efeitos indiretos

Bem-estar, satisfação, retorno, entropia, respostas e sobrevivência estão na tabela da seção 2. Ressalva da spec §11, item 8: o que aparece aqui é efeito **da receita** (peça nova mais o que ela muda no PAD, nos traços e nas preferências pela vida afora), e não da peça sozinha. Em `ctrnn-v1`, por exemplo, o PAD usa a expectativa da CTRNN; em políticas novas, as ações mudam, e com elas o que as preferências e os traços aprendem.

Leitura honesta:

- **Onde os experimentos perdem.** No `attentive`, `ctrnn-v1` tem bem-estar −0,044 (−6%, mesmo sinal nas 3 sementes) e satisfação −0,012; `thompson-v1` tem satisfação −0,011 (mesmo sinal) e bem-estar −0,033 sem sinal consistente (dp 0,056); `curious-v1` e `curious-lp-v1` ficam abaixo do padrão no bem-estar (−0,011 e −0,026) sem sinal consistente; `aif-v1` também (−0,018). No `routine`, `curious-*` tem bem-estar −0,0019 consistente, e `aif-solo-v1` tem retorno −2,1 (−8%, consistente).
- **Onde empatam (sem efeito consistente).** `absent`: praticamente tudo, as criaturas quase não têm usuário e o bem-estar é ≈0,03 em todas. `routine`: bem-estar entre 0,059 e 0,065, com dp de 0 a 0,001 (o usuário é determinístico e há poucas decisões que variem).
- **Onde ganham.** `aif-solo-v1`, a linha exploratória, é a única receita com ganhos grandes e consistentes: satisfação +0,037 e respostas +0,043 no `attentive`, bem-estar +0,019 e retorno +1,7 no `neglectful`. Mas ela também perde no `absent` (satisfação −0,006) e no retorno do `routine`, e o bem-estar do `attentive` é menor (−0,025, sem sinal consistente). Como não tem utilidade, ela troca o desenho do padrão por outro, e o ganho pode vir de a utilidade estar "diluída" no padrão: é uma linha para olhar, não uma troca de uma peça. `aif-v1` fica entre as duas.
- **Sobrevivência no `neglectful`.** Dias de vida médios por geração: padrão 1,67 (dp 2,9), `ctrnn-v1` 4,0, `curious-lp-v1` 5,8, `aif-solo-v1` 3,6, `aif-v1` 3,0, `curious-v1` 1,6, `thompson-v1` 0,85. Os desvios são da ordem da média (às vezes maiores) e as gerações terminadas são 0 a 1 por corrida. Nenhuma diferença tem sinal consistente (as diferenças têm `Δ` > 0 para quase todas, mas a tabela não marca `*`). **Sem efeito consistente.**
- **Entropia.** A entropia do comportamento sobe com `*` em quase todas as receitas no `attentive` e no `neglectful` (+0,02 a +0,12). Mais entropia não é melhor nem pior por si só; no `absent`, `aif-solo-v1` cai (−0,09).
- **Calibração degenerada.** Nenhum experimento ficou degenerado no `attentive` (ver seção 6): nenhum módulo foi desabilitado, a ação mais frequente tem 20–23% do tempo (`sleep`) em todas as receitas, e o menor bem-estar é 0,634 contra 0,677 do padrão.

## 5. Custo

Bench headless por receita, 30 s em tempo real, `attentive`, semente 1 (`tools/bench.py`; pico de RSS em MB, CPU médio em %, `mean_ms` por tick de 1 s; todos os módulos novos com `disabled = []`):

| receita | RSS pico | CPU médio | módulo(s) novo(s), `mean_ms` |
|---|---|---|---|
| `default-v1` (referência) | 42,6 | 0,10 | (`temporal.snn` 0,120; `policy.qlearning` 0,0005) |
| `ctrnn-v1` | 42,8 | 0,10 | `temporal.ctrnn` 0,056 |
| `shadow-ctrnn-v1` | 42,8 | 0,10 | `temporal.ctrnn` (sombra) 0,055 |
| `curious-v1` | 42,6 | 0,13 | `policy.curious` 0,0004; `world.model` 0,013 |
| `curious-lp-v1` | 42,6 | 0,13 | `policy.curious` 0,0004; `world.model` 0,014 |
| `thompson-v1` | 42,6 | 0,13 | `policy.thompson` 0,0006 |
| `aif-v1` | 42,6 | 0,13 | `policy.aif` 0,0006 |
| `aif-solo-v1` | 42,6 | 0,10 | `policy.aif` 0,0008 |
| `lab-shadow-all-v1` | 42,9 | 0,17 | `temporal.ctrnn` 0,048; `policy.thompson` 0,0008; `policy.aif` 0,0005; `world.model` 0,014 |

Tudo dentro do orçamento: ≤150 MB, ≤2% de CPU e `mean_ms` bem abaixo de `EXP_BUDGET_MS = 2,0` (a `CTRNN_BUDGET_MS` é 5,0). O custo no laboratório (`dt = 60`, média nas 96 corridas da suíte) vai na mesma direção: `temporal.ctrnn` 0,12–0,14 ms por tick (ante 0,83 ms da SNN), `world.model` 0,009, `policy.curious` 0,0003, `policy.thompson` 0,0003–0,0008, `policy.aif` 0,0003–0,0007. O bench é de 30 ticks e o CPU medido tem granularidade grossa (0,10 → 0,17% são ruído de uma máquina compartilhada); a conclusão é "todos muito abaixo do limite", não "a CTRNN custa X% menos". A CTRNN é mais barata que a SNN por ter tamanho fixo (64 unidades).

## 6. Calibrações feitas

**Nenhuma.** O critério da calibração (Passo 3) é um experimento degenerado no `attentive`: módulo desabilitado, uma ação com mais de 60% do tempo, ou bem-estar abaixo de metade do padrão. Em todas as receitas, nenhum módulo ficou desabilitado (`disabled = []` no bench e `module_ms` em toda corrida da suíte); a ação mais frequente é `sleep` com 20,1–22,7% do tempo; e o menor bem-estar é o da `ctrnn-v1` (0,634) contra 0,677 do padrão (limite: 0,339). Por isso, `CUR_BETA` (0,3), `TS_SIGMA0` (0,5), `AIF_PREF_SCALE` (2,0), `AIF_NOVELTY_WEIGHT` (1,0) e os pesos de `policy.aif` (0,6 em `aif-v1`; 1,0 em `aif-solo-v1`, onde ele é o único decisor) ficaram como na T0–T5. O bloco `# Task M10` de `engrama/balance.py` não foi alterado.

Observação: o `novelty_share` da inferência ativa (1–1,7%) mostra que `AIF_NOVELTY_WEIGHT` na faixa 0,25–2,0 mudaria pouco o comportamento (o termo epistêmico seria no máximo ≈3%). Não foi calibrado porque nada estava degenerado, e ajustar para melhorar a métrica seria escolher o valor olhando o resultado.

## 7. O que não se conclui

- **Só 3 sementes.** Não há significância estatística. "Mesmo sinal nas 3 sementes" é o critério mínimo, e, mesmo ele, ocorre por acaso em 25% dos casos sem efeito algum. A maior parte das diferenças marcadas com `*` é menor que o desvio entre sementes (por exemplo, `thompson-v1` no `neglectful`: bem-estar −0,0007 contra dp de 0,014).
- **Usuário simulado ≠ usuário real.** Os perfis (`attentive`, `absent`, `neglectful`) são Poisson por hora e o `routine` é determinístico (dp zero, daí o Brier idêntico entre sementes na ablação só com viés). Eventos aleatórios não são explicados por nenhuma ação, e não se sabe como as criaturas se comportariam com pessoas.
- **IPS não vale para o Thompson.** A probabilidade gravada por `policy.thompson` no log é condicional à amostra (o árbitro softmax roda por cima da proposta amostrada), e não a probabilidade marginal com que a ação foi escolhida; por isso a avaliação fora da política por IPS (`engrama.lab.ope`) **não é válida** para essa receita (spec §11). Nenhuma estimativa de OPE foi usada neste relatório.
- **Ganho da CTRNN: reportado, não exigido.** A CTRNN ganha da ablação só com viés no `routine` (10–20% em sombra, 11–15% ao vivo), mas isso é um usuário perfeitamente periódico, o melhor caso para uma rede com constantes de tempo de até 1 dia. No `attentive`, `neglectful` e `absent` o ganho é ≈1% ou sem sinal. Ela custa menos que a SNN, mas piora o bem-estar do `attentive` (−6%, consistente) por efeitos indiretos que este relatório não isola.
- **Efeitos indiretos são da receita.** Bem-estar e satisfação mudam por uma cadeia (PAD → traços → preferências → ações); este relatório não separa essa cadeia.
- **`aif-solo-v1` é exploratória.** Ela não faz parte da aceitação do M10 e tira uma peça (a utilidade) além de trocar o Q-learning; não deve ser lida como "inferência ativa vence".
- **Dias de vida.** Com 0–1 geração terminada por corrida e desvios do tamanho da média, a sobrevivência no `neglectful` é ruído neste desenho.
- **`dt` e escala.** O erro do modelo de mundo e o bônus são do laboratório (`dt = 60 s`); no app (tick de 1 s), a escala muda (spec §11, item 5).

**Recomendação (spec §2): não promover nenhum experimento a padrão no M10.** Nenhuma receita supera o padrão de forma consistente e relevante em bem-estar no `attentive`; as que ganham em algum ponto perdem em outro; os custos estão dentro do orçamento, então manter todos como receitas de laboratório (acessíveis por `--recipe`) não custa nada. Se algum dia um experimento for promovido, as candidatas mais interessantes para um estudo maior (≥ 10 sementes, usuário real) são a CTRNN, pelo ganho de previsão em usuários periódicos e o custo menor, e a inferência ativa sem utilidade, pelas métricas de satisfação e resposta; ambas exigem antes um critério claro de bem-estar, porque hoje a CTRNN o piora.
