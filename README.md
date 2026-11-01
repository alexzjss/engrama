# Engrama

**PT** | [EN](#en)

## O que é

Engrama é um companheiro virtual local e offline, no estilo tamagotchi: uma criatura com necessidades, humor, personalidade e gostos próprios que mora no seu computador. Nada sai da máquina.

### Arquitetura: corpo, mente, laboratório

- **Corpo** (`engrama/kernel`): núcleo determinístico. Necessidades, estágios, ações e recompensas. Mesma semente, mesmo resultado; uma simulação completa também é determinística, pois o laboratório não rebaixa módulos por tempo real (ver `--enforce-budgets`).
- **Mente** (`engrama/mind`, `engrama/modules`): módulos trocáveis (drives, SNN temporal, afeto PAD, traços, preferências, políticas) que escrevem em um quadro-negro e propõem ações; um árbitro softmax escolhe.
- **Laboratório** (`engrama/lab`): runtime de simulação, log de experiência (SQLite), replay, métricas e CLI.

### Receitas

Uma receita TOML em `recipes/` escolhe quais módulos formam a mente e seus pesos. `minimal-v1.toml` e `default-v1.toml` são os exemplos.

### Instalar

Python 3.13 ou mais novo.

```
python -m venv .venv
.venv\Scripts\activate
pip install numpy psutil pytest
```

### Laboratório

```
python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --profile gamer --seed 1 --log data/run.db
python -m engrama.lab report --log data/run.db
python -m engrama.lab compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10
python -m engrama.lab replay --log data/run.db --module temporal.snn --param readout_hidden=false
```

Perfis (`--profile`): `attentive`, `absent`, `night_owl`, `gamer`. Outras flags: `--dt` (passo em segundos simulados, padrão 60), `--save DIR` (salva o estado ao fim do `sim`), `--run ID` (escolhe a execução dentro de um log, em `report` e `replay`), `--seed` (também em `replay`), `--enforce-budgets` (rebaixa módulos lentos pelo relógio de parede; não determinístico, desligado por padrão). Cada `sim --log` cria uma execução com `run_id` único (uuid4), impresso nas métricas junto com o nome e a versão da receita; rodar de novo no mesmo log não mistura linhas.

### O que a SNN comprova (e o que não)

- Comprovado: em um usuário periódico roteirizado, a SNN prevê o próximo evento melhor que uma leitura só com viés (Brier 4,0% a 5,1% menor nas sementes 1, 2 e 3; o teste exige pelo menos 2% em cada uma).
- O sinal de novidade e a habituação vêm principalmente da taxa-base de cada tipo de evento, não da rede de disparos (a ablação só com viés dá a mesma razão raro/comum).
- `minimal` contra `default` é uma diferença de receita (SNN, Q-learning, preferências e traços juntos), não um efeito só da SNN.
- A SNN avança em compassos fixos de 60 s de tempo simulado, então o resultado não depende do `--dt`.

### Escrever um módulo

1. Subclasse `engrama.mind.contracts.Module`: declare `reads`, `writes`, `rate_hz`; implemente `step(bb, dt)`, `propose(bb)`, `learn(exp)`, `state_dict`/`load_state_dict`.
2. Registre em `engrama/mind/registry.py` (`REGISTRY["familia.nome"] = "pacote.arquivo:Classe"`).
3. Adicione a uma receita como `[[module]]` (vivo, com `weight`) ou `[[shadow]]` (roda e é registrado, mas não decide; útil para comparar).

Regra de dependência (verificada por `tests/test_architecture.py`): `kernel` não importa `mind`, `modules`, `lab` nem `services`; `mind` não importa `kernel` nem `modules`; um módulo só importa `engrama.mind`, `engrama.vocab`, `engrama.balance`, a própria família, numpy e a stdlib.

### Testes e bench

```
python -m pytest -q                      # inclui testes lentos (marcador slow)
python tools/bench.py --seconds 120      # (--profile, --seed) JSON: pico de RSS, CPU médio, mean_ms por módulo
```

### Onde ficam os arquivos

A CLI do laboratório usa os caminhos explícitos `--log` e `--save` (não lê `Config`); o padrão sugerido nos exemplos é `data/`, ignorado pelo git. `Config.data_dir` (padrão: `data/` na raiz do repositório) é o diretório de dados do app. Com o repositório no drive E:, nada vai para o C:.

---

<a id="en"></a>
**[PT](#engrama)** | EN

## What it is

Engrama is a local, offline virtual companion in the tamagotchi tradition: a creature with needs, mood, personality and tastes of its own, living on your computer. Nothing leaves the machine.

### Architecture: body, mind, lab

- **Body** (`engrama/kernel`): a deterministic core. Needs, stages, actions and rewards. Same seed, same outcome; a full simulation is deterministic too, because the lab does not demote modules on wall-clock time (see `--enforce-budgets`).
- **Mind** (`engrama/mind`, `engrama/modules`): swappable modules (drives, temporal SNN, PAD affect, traits, preferences, policies) write to a blackboard and propose actions; a softmax arbiter picks.
- **Lab** (`engrama/lab`): simulation runtime, experience log (SQLite), replay, metrics and CLI.

### Recipes

A TOML recipe in `recipes/` chooses which modules make up a mind and their weights. See `minimal-v1.toml` and `default-v1.toml`.

### Install

Python 3.13 or newer.

```
python -m venv .venv
.venv\Scripts\activate
pip install numpy psutil pytest
```

### Lab

```
python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --profile gamer --seed 1 --log data/run.db
python -m engrama.lab report --log data/run.db
python -m engrama.lab compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10
python -m engrama.lab replay --log data/run.db --module temporal.snn --param readout_hidden=false
```

Profiles (`--profile`): `attentive`, `absent`, `night_owl`, `gamer`. Other flags: `--dt` (step in simulated seconds, default 60), `--save DIR` (save state at the end of `sim`), `--run ID` (pick a run inside a log, for `report` and `replay`), `--seed` (also on `replay`), `--enforce-budgets` (demote slow modules by wall-clock time; not deterministic, off by default). Every `sim --log` creates a run with a unique `run_id` (uuid4), printed with the metrics together with the recipe name and version; rerunning into the same log does not mix rows.

### What the SNN does and does not show

- Evidenced: on a scripted periodic user, the SNN predicts the next event better than a bias-only readout (Brier 4.0% to 5.1% lower on seeds 1, 2 and 3; the test requires at least 2% on each).
- The novelty signal and habituation come mostly from each event kind's base rate, not from the spiking network (the bias-only ablation gives the same rare/common ratio).
- `minimal` versus `default` is a recipe difference (SNN, Q-learning, preferences and traits together), not an SNN-only effect.
- The SNN advances on fixed 60 s sim-time bins, so its behaviour does not depend on `--dt`.

### Writing a module

1. Subclass `engrama.mind.contracts.Module`: declare `reads`, `writes`, `rate_hz`; implement `step(bb, dt)`, `propose(bb)`, `learn(exp)`, `state_dict`/`load_state_dict`.
2. Register it in `engrama/mind/registry.py` (`REGISTRY["family.name"] = "package.file:Class"`).
3. Add it to a recipe as `[[module]]` (live, with `weight`) or `[[shadow]]` (runs and is logged but does not decide; useful for comparisons).

Dependency rule (enforced by `tests/test_architecture.py`): `kernel` imports none of `mind`, `modules`, `lab`, `services`; `mind` imports neither `kernel` nor `modules`; a module may import only `engrama.mind`, `engrama.vocab`, `engrama.balance`, its own family, numpy and the stdlib.

### Tests and bench

```
python -m pytest -q                      # includes slow tests (slow marker)
python tools/bench.py --seconds 120      # JSON: peak RSS, mean CPU, per-module mean_ms
```

### Where files live

The lab CLI takes explicit `--log` and `--save` paths (it does not read `Config`); the examples use `data/`, which is git-ignored. `Config.data_dir` (default: `data/` at the repo root) is the app's data directory. With the repo on drive E:, nothing goes to C:.
