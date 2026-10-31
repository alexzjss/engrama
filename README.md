# Engrama

**PT** | [EN](#en)

## O que e

Engrama e um companheiro virtual local e offline, no estilo tamagotchi: uma criatura com necessidades, humor, personalidade e gostos proprios que mora no seu computador. Nada sai da maquina.

### Arquitetura: corpo, mente, laboratorio

- **Corpo** (`engrama/kernel`): nucleo deterministico. Necessidades, estagios, acoes e recompensas. Mesma semente, mesmo resultado.
- **Mente** (`engrama/mind`, `engrama/modules`): modulos trocaveis (drives, SNN temporal, afeto PAD, tracos, preferencias, politicas) que escrevem em um quadro-negro e propoem acoes; um arbitro softmax escolhe.
- **Laboratorio** (`engrama/lab`): runtime de simulacao, log de experiencia (SQLite), replay, metricas e CLI.

### Receitas

Uma receita TOML em `recipes/` escolhe quais modulos formam a mente e seus pesos. `minimal-v1.toml` e `default-v1.toml` sao os exemplos.

### Instalar

```
python -m venv .venv
.venv\Scripts\activate
pip install numpy psutil pytest
```

### Laboratorio

```
python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --profile gamer --seed 1 --log data/run.db
python -m engrama.lab report --log data/run.db
python -m engrama.lab compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10
python -m engrama.lab replay --log data/run.db --module affect.pad --param k=v
```

Perfis: `attentive`, `absent`, `night_owl`, `gamer`.

### Escrever um modulo

1. Subclasse `engrama.mind.contracts.Module`: declare `reads`, `writes`, `rate_hz`; implemente `step(bb, dt)`, `propose(bb)`, `learn(exp)`, `state_dict`/`load_state_dict`.
2. Registre em `engrama/mind/registry.py` (`REGISTRY["familia.nome"] = "pacote.arquivo:Classe"`).
3. Adicione a uma receita como `[[module]]` (vivo, com `weight`) ou `[[shadow]]` (roda e e registrado, mas nao decide; util para comparar).

Regra de dependencia (verificada por `tests/test_architecture.py`): `kernel` nao importa `mind`, `modules`, `lab` nem `services`; `mind` nao importa `kernel` nem `modules`; um modulo so importa `engrama.mind`, `engrama.vocab`, `engrama.balance`, a propria familia, numpy e a stdlib.

### Testes e bench

```
python -m pytest -q                      # inclui testes lentos (marcador slow)
python tools/bench.py --seconds 120      # JSON: pico de RSS, CPU medio, mean_ms por modulo
```

### Onde ficam os arquivos

Saves e logs ficam em `Config.data_dir` (padrao: `data/` na raiz do repositorio, ignorado pelo git). Tudo no drive E:, nada no C:.

---

<a id="en"></a>
**[PT](#engrama)** | EN

## What it is

Engrama is a local, offline virtual companion in the tamagotchi tradition: a creature with needs, mood, personality and tastes of its own, living on your computer. Nothing leaves the machine.

### Architecture: body, mind, lab

- **Body** (`engrama/kernel`): a deterministic core. Needs, stages, actions and rewards. Same seed, same outcome.
- **Mind** (`engrama/mind`, `engrama/modules`): swappable modules (drives, temporal SNN, PAD affect, traits, preferences, policies) write to a blackboard and propose actions; a softmax arbiter picks.
- **Lab** (`engrama/lab`): simulation runtime, experience log (SQLite), replay, metrics and CLI.

### Recipes

A TOML recipe in `recipes/` chooses which modules make up a mind and their weights. See `minimal-v1.toml` and `default-v1.toml`.

### Install

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
python -m engrama.lab replay --log data/run.db --module affect.pad --param k=v
```

Profiles: `attentive`, `absent`, `night_owl`, `gamer`.

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

Saves and logs live under `Config.data_dir` (default: `data/` at the repo root, git-ignored). Everything stays on drive E:, nothing on C:.
