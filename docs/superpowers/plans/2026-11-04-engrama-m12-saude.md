# Engrama M12: Saúde do projeto, plano de implementação

**Objetivo:** o repositório se verifica sozinho (CI Linux + Windows, lint) e os quatro arquivos que mais crescem são divididos sem mudar comportamento, para que M13 (calibração) e M14 (arte) possam correr em paralelo sem conflito.

**Roadmap:** `docs/superpowers/specs/2026-11-04-engrama-m12-m15-roadmap.md` (seção M12).

**Execução:** orquestração pelo Opus; cada tarefa vai para um subagente com o modelo indicado, no seu próprio worktree (scratchpad da sessão), partindo de `m12`. O orquestrador integra na branch `m12`, roda a suíte inteira e abre **um PR** (sem linhas de coautoria de IA).

## Restrições globais

- **Zero mudança de comportamento.** Nada em `engrama/kernel/**`, `engrama/mind/**`, `engrama/modules/**`, `engrama/lab/**`, `recipes/**`. `SAVE_VERSION`, schema SQLite, `vocab`, `balance` e i18n intocados.
- **Gabaritos existentes** (`tests/fixtures/*.json`) continuam batendo.
- **APIs públicas preservadas:** `engrama.app.host:main` (entry point do `pyproject`), `engrama.app.host.Host`, `engrama.services.memory.store.MemoryStore`, `WorkingMemory`, e toda função importada por testes ou outros módulos. Antes de mover algo, `git grep` os usos; reexports no módulo antigo onde testes/código importam nomes privados (`_MemoryProvider` etc.).
- **Divisão = mover código.** Sem renomear, sem "melhorar" lógica no caminho. Se encontrar bug, anotar no relatório da tarefa, não corrigir.
- Python 3.13, sem dependência nova de runtime. `ruff` entra só em `[dev]`.
- Testes rodam com `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m pytest -q`.
- Commits pequenos, mensagem `tipo(m12): ...`, **sem** `Co-Authored-By`.

## Tarefas

Ordem: **T0 → T1 → {T2, T3, T4, T5, T6 em paralelo} → T7**. T2–T6 tocam arquivos disjuntos.

### T0: Ambiente e linha de base (Haiku)

- [ ] Criar `.venv` com Python 3.13 na raiz do repositório (já ignorado pelo git) e `pip install -e .[dev]`.
- [ ] Rodar a suíte inteira e gravar tempo total e resultado em `docs/superpowers/reports/2026-11-04-m12-baseline.md` (inclui os 10 testes mais lentos via `--durations=10`).
- [ ] Linha de base medida em 2026-11-04: **1269 passed, 1 failed, 2 skipped em 41 min 52 s** (serial). A falha (`test_m9_acceptance.py::test_search_budget`, mediana 37,9 ms contra o orçamento) foi carga da máquina (download do Ollama em paralelo); isolado passa 3/3.
- [ ] **Testes de relógio de parede:** listar todo teste que compara `perf_counter`/CPU/FPS com um orçamento (`git grep -n "BUDGET\|perf_counter" tests`). Marcar com `@pytest.mark.perf` (registrar o marcador no `pyproject`). Na CI eles rodam num passo separado com `continue-on-error: true`; localmente continuam no padrão.
- [ ] **Paralelismo:** adicionar `pytest-xdist` ao `[dev]` e verificar que `pytest -n auto` passa (testes que usam `.pytest_tmp`, portas, locks de instância ou `data/` compartilhado precisam de `tmp_path`; corrigir só fixtures de teste). Meta: suíte local abaixo de ~12 min em 8 núcleos. Registrar o tempo.
- [ ] **Gabarito de sprites** `tests/app/test_sprite_golden.py`: para sementes 1..24, todos os estágios (`egg`..`final`) e as animações do app, SHA-256 do `np.ndarray` de `creature_frames`/`egg_array` (ramos `base` e um ramo de negligência). Hashes gravados em `tests/fixtures/m12_sprite_hashes.json` com o código **atual**. O teste compara. Commit antes de qualquer outra tarefa.

### T1: Lint com ruff (Haiku)

- [ ] `[project.optional-dependencies] dev = ["pytest", "ruff"]`.
- [ ] `[tool.ruff]` com `target-version = "py313"`, `line-length = 130`, `extend-exclude = ["spike", "art-review"]`; `[tool.ruff.lint] select = ["F", "E9", "B006", "B008", "B904"]`. Sem `ruff format`.
- [ ] Corrigir os achados (imports não usados, variáveis não usadas, etc.) só quando a correção é trivial e sem efeito; `# noqa` com motivo onde o import é reexport intencional.
- [ ] Suíte e gabarito de sprites passam.

### T2: CI no GitHub Actions (Sonnet)

Arquivo: `.github/workflows/ci.yml` (só ele).
- [ ] Gatilhos: `push` em `main`, `pull_request`.
- [ ] Job `lint` (ubuntu-latest): Python 3.13, `pip install ruff`, `ruff check .`.
- [ ] Job `test`: matriz `ubuntu-latest` e `windows-latest`, Python 3.13, cache de pip, `pip install -e .[dev]`, env `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`, `pytest -q -n auto -m "not perf" --durations=15`, `timeout-minutes: 45`. Passo seguinte `pytest -q -m perf` com `continue-on-error: true` (runners compartilhados não garantem tempo).
- [ ] No Ubuntu, instalar o mínimo que o pygame-ce precisar para o driver dummy (verificar; provavelmente nada).
- [ ] Validar o YAML localmente (`python -c "import yaml"` se disponível, ou `actionlint` se instalado); o teste real é o push do PR. Se o Windows falhar no PR por diferença real de plataforma, o orquestrador investiga: **marcar `skipif` só com motivo escrito**, nunca para esconder bug.

### T3: Bench no Wayland (Haiku)

Arquivos: `tools/bench.py`, `engrama/app/ui/overlay.py` (só `_hwnd`), `engrama/app/desktop.py` (só `_own_hwnd`).
- [ ] Reproduzir: `python tools/bench.py --overlay --seconds 5` numa sessão Hyprland (o `setdefault` do driver não vence um `SDL_VIDEODRIVER=wayland` do ambiente).
- [ ] `bench_overlay` força `os.environ["SDL_VIDEODRIVER"] = "dummy"` e `SDL_AUDIODRIVER` (usa `FakeDesktop`, nunca precisa de janela real).
- [ ] `_hwnd()` e `_own_hwnd()`: não chamar `pygame.display.get_wm_info()` quando o driver de vídeo atual (`pygame.display.get_driver()`) for `wayland` ou `dummy`; devolver 0.
- [ ] Teste em `tests/app/test_overlay.py` ou `test_desktop.py`: com driver dummy, `_hwnd()` devolve 0 sem chamar `get_wm_info` (monkeypatch que explode se chamado).
- [ ] Rodar o bench de verdade no Hyprland e colar o JSON no relatório da tarefa.

### T4: Dividir `engrama/app/host.py` (Sonnet)

- [ ] `engrama/app/providers.py`: `_GenerationsProvider`, `_MemoryProvider`, `_memory_provider`, `_PerceptionProvider`, `_Activity`, `_NullServer`, `_build_persona`, `_safe` (se usado pelos providers; senão fica).
- [ ] `engrama/app/cli.py`: `main`, `_main`, `resolve_recipe_arg`, `open_in_display_mode` e o parsing de argumentos.
- [ ] `host.py` fica com `Host` e reexporta (`from engrama.app.cli import main` etc.) tudo que testes, `__main__` e `pyproject` usam. Entry point `engrama.app.host:main` continua válido.
- [ ] Verificar com `git grep -n "host import\|host\._\|from engrama.app.host"` que nenhum import quebra; suíte passa; `python -m engrama --no-llm --frames 60` roda (SDL dummy).

### T5: Dividir `engrama/services/memory/store.py` (Sonnet)

- [ ] Criar `engrama/services/memory/store/` **ou** módulos irmãos (escolha o que mantém `from engrama.services.memory.store import MemoryStore, WorkingMemory, <helpers usados em testes>` funcionando; se virar pacote, `store/__init__.py` reexporta).
- [ ] Separar por responsabilidade em mixins sem estado próprio, combinados em `MemoryStore`: base (conexão, `_init`, migrações, `meta_*`, `close`); episódios/fatos/assuntos; percepção/apps/temas; opiniões; vetores; bloqueio/apagar/esquecer-tudo; gerações/ancestrais/limites (`enforce_caps`, `forget`).
- [ ] Helpers de módulo (`_sem`, `_vtext`, `_vhash`, `_unit`, `_clamp`, `_decay`, `_term_regex`, `_lang_of`, `_compact_summary`) num `_util.py`, reexportados.
- [ ] Schema e SQL byte a byte iguais (diff só de movimento: conferir com `git diff --stat` e `git diff -M`).
- [ ] Suíte de memória (`tests/services/memory/**`, M4/M9 acceptance) passa.

### T6: Dividir `engrama/app/art/vpet/families.py` (Sonnet)

- [ ] Pacote `engrama/app/art/vpet/families/`: `common.py` (`lerp`, `D`, `markings`, `leg`, `upright` e demais utilitários compartilhados), um módulo por família (`dragon.py`, `beast.py`, `bird.py`, `insect.py`, `plant.py`, `spirit.py`, `aquatic.py`, `machine.py`) e `__init__.py` com a mesma tabela/dispatch e os mesmos nomes públicos de hoje.
- [ ] Ordem de chamadas e de uso de RNG **idêntica**: o gabarito da T0 é o juiz. Qualquer hash diferente = reverter e mover de novo.
- [ ] `tests/app/test_sprites_m11.py` e o gabarito passam; `spike/vpet2` (se importa `families`) continua funcionando ou o import é ajustado.

### T7: Integração e aceite (orquestrador + Haiku para docs)

- [ ] Merge de T2–T6 em `m12`; resolver conflitos (esperado: nenhum).
- [ ] `tests/test_architecture.py`: confirmar que as regras cobrem os novos arquivos (`providers.py`, `cli.py` são `app`; `families/` é `art`, logo apresentação). Ajustar listas só se necessário.
- [ ] README (PT e EN), seção "Para desenvolvedores": instalação dev com `.venv` e `[dev]`, `ruff check .`, como rodar a suíte com SDL dummy, CI. Seção de limitações: remover nada que não foi resolvido; o bench no Wayland sai da lista se T3 resolveu.
- [ ] `ruff check .` limpo; suíte inteira verde; tempo comparado com a linha de base (T0).
- [ ] Bump `version = "0.12.0"`.
- [ ] Push de `m12`, PR para `main` com resumo, tabela de tarefas e resultado da CI. O usuário aprova e mergeia.

## Aceite do M12

1. CI verde em Linux e Windows no PR.
2. `ruff check .` limpo.
3. `tests/fixtures/m12_sprite_hashes.json` e gabaritos de simulação idênticos.
4. Nenhum arquivo de `engrama/` acima de ~600 linhas entre os divididos.
5. `tools/bench.py --overlay` roda no Hyprland.

## Riscos

| Risco | Mitigação |
|---|---|
| Windows na CI revela falhas acumuladas desde M8 | Tratar como achado real; corrigir no M12 se pequeno, senão `skipif` com issue aberta e motivo |
| Divisão do `families.py` muda ordem de RNG | Gabarito de hashes antes de tudo; o agente trabalha comparando a cada passo |
| Testes importam nomes privados de `host`/`store` | Reexports no módulo original; `git grep` antes de mover |
| Suíte lenta na CI (42 min serial localmente; runners têm 2–4 núcleos) | `pytest-xdist` na T0; se ainda passar de ~20 min na CI, discutir com o usuário rodar `slow` só em `main`/nightly antes de excluir qualquer coisa |
| Testes de orçamento instáveis em runner compartilhado | marcador `perf`, passo não bloqueante na CI |
