# Engrama: roadmap do ciclo M12–M15

Data: 2026-11-04. Estado de partida: `main` em `66dabb9` (M1–M11 entregues, PR #13 mergeado).

## Decisões do usuário (2026-11-04)

- Frentes do ciclo: **saúde do projeto**, **arte e animação**, **distribuição**.
- Modelos reais do Ollama **liberados** (`qwen3:1.7b`, `embeddinggemma`): fazer os smokes manuais pendentes e calibrar os limiares da busca por significado.
- Overlay no Wayland: **fora do ciclo**.
- Jogabilidade nova (minijogos, conquistas): **fora do ciclo**.
- Fluxo: Opus escreve spec + plano, o usuário aprova, a execução é feita por subagentes Sonnet (tarefas de design/integração) e Haiku (tarefas mecânicas), em worktrees, **um PR por marco**.

## Diagnóstico do estado atual

| Área | Situação | Problema |
|---|---|---|
| CI | Não existe (`.github/` ausente) | Nada verifica PRs; Windows nunca é testado automaticamente desde M8 |
| Ambiente | Sem `.venv` no repositório; Python do sistema é 3.14 sem dependências | Reproduzir o ambiente depende de memória de sessões anteriores |
| Lint | Nenhum | Estilo só por convenção |
| Arquivos grandes | `families.py` 1171, `store.py` 1008, `host.py` 1005, `service.py` 773 linhas | Difícil de revisar e de dividir trabalho entre agentes sem conflito |
| Bench | `tools/bench.py --overlay` segfault em `pygame.display.get_wm_info` no Wayland real | Bench de overlay inutilizável na máquina de dev |
| Calibração | `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM` nos valores iniciais; smokes manuais de M3–M9 sem relato | Qualidade da conversa e da memória real desconhecida |
| Persona | Nunca avaliada com o modelo real de forma sistemática | Risco do anti-objetivo "chatbot atendente" |
| Distribuição | Só `pip install -e .`; dados em `data/` do repo; caminhos `E:\Ollama` no `Config` | Ninguém além do dev consegue instalar; Windows assume disco E: |
| Arte | Animação só por transformação do sprite inteiro; dragão quadrúpede adulto carregado | Limitação declarada no README |
| Spec original | Backups diários e recuperação de save: **feitos**; grunhidos: feitos | — |

## Marcos

### M12: Saúde do projeto (primeiro, bloqueia os outros)

Objetivo: o repositório se verifica sozinho e aguenta trabalho paralelo.

1. **CI no GitHub Actions**: Linux (ubuntu) e Windows, Python 3.13, `SDL_VIDEODRIVER=dummy`; roda `pytest`. Job separado e rápido de lint.
2. **Lint com ruff**: configuração mínima no `pyproject.toml` (erros reais: `F`, `E9`, `B` seletivo, imports não usados), sem reformatação em massa. Corrigir o que aparecer.
3. **Ambiente reproduzível**: seção de dev no README atualizada; `pip install -e .[dev]` passa a incluir `ruff`; nada de gerenciador novo.
4. **Bench no Wayland**: `bench --overlay` força o driver dummy (usa `FakeDesktop`, não precisa de janela real) e `_hwnd()`/`_own_hwnd()` não chamam `get_wm_info` em sessão Wayland.
5. **Divisão dos arquivos grandes, sem mudança de comportamento**:
   - `engrama/app/host.py` → `host.py` (classe `Host`), `providers.py` (`_MemoryProvider`, `_PerceptionProvider`, `_GenerationsProvider`, `_Activity`, `_NullServer`), `cli.py` (`main`, `_main`, `resolve_recipe_arg`, `open_in_display_mode`). `engrama = engrama.app.host:main` continua funcionando (reexport).
   - `engrama/services/memory/store.py` → mixins ou módulos por responsabilidade (episódios/fatos/assuntos, percepção, opiniões, vetores, esquecimento/gerações), mantendo a classe pública `MemoryStore` e o schema intactos.
   - `engrama/app/art/vpet/families.py` → um módulo por família em `families/` + `families/common.py` (`D`, `lerp`, `leg`, `upright`, `markings`). **Saída de pixels idêntica**: teste de regressão com hash dos sprites de um conjunto de sementes antes/depois.
6. `tests/test_architecture.py` atualizado para os novos módulos.

Aceite: CI verde nos dois SOs; `ruff check` limpo; hashes de sprites idênticos; suíte local inteira passa; `bench --overlay` roda no Hyprland.

### M13: Calibração com modelos reais

Objetivo: saber, com números, se a conversa e a memória funcionam com o modelo real, e ajustar.

1. **Harness de smoke** (`tools/smoke_llm.py`): roda roteiros de conversa (PT e EN, por estágio: bebê, criança, adulto, final) contra o Ollama real, grava transcrições e métricas em JSON/Markdown. Detecta frases de atendente ("como posso ajudar", "how can I help", "sou uma IA"...), tamanho por estágio, idioma certo, uso de fatos lembrados.
2. **Conjunto rotulado de similaridade**: pares (consulta, memória, deve-casar sim/não) em PT, EN e cruzado. Script mede precisão/recall de `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM` com `embeddinggemma` e escolhe limiares; os valores novos vão para `balance`/config com o relatório.
3. **Ajuste de persona/prompts** guiado pelos resultados do harness (sem mudar quem decide as ações).
4. **Smokes manuais**: checklist por marco (M3–M9) executada e relatada em `docs/superpowers/reports/`; o que exigir interação humana vira lista para o usuário.
5. Testes automatizados continuam sem Ollama (o harness é ferramenta, não teste da suíte).

Aceite: relatório com transcrições, taxa de frases de atendente ≈ 0, limiares escolhidos com precisão/recall publicados, checklist de smokes preenchida.

### M14: Arte: animação de membros e poses

Objetivo: a criatura se mexe por partes, não só como um bloco.

1. **Poses por parte**: o `Builder` já nomeia partes (`leg`, braços, cauda, asas...). Adicionar transformações por parte (rotação em torno de uma junta, deslocamento) e renderizar quadros a partir de poses.
2. **Ciclos por animação**: `walk` (pernas alternadas / ondulação na serpente / bater de asas no voo), `eat` (cabeça desce), `happy` (braços/asas sobem), `sleep` (corpo deitado com respiração), `idle` (respiração + cauda). Por plano de corpo, com fallback para as transformações atuais quando o plano não tem a parte.
3. **Orçamento**: quadros cacheados como hoje; custo de geração medido; nenhuma regressão de FPS/CPU no bench.
4. **Limpeza do dragão quadrúpede adulto** (menos partes no estágio adulto).
5. Showcase e folhas de revisão regeneradas; GIFs curtos no README.

Aceite: folhas de revisão aprovadas pelo usuário (ponto de decisão humano), bench dentro do orçamento, testes de sprites atualizados.

### M15: Distribuição

Objetivo: alguém que não é o dev instala e usa.

1. **Pasta de dados do SO**: `%APPDATA%\Engrama` no Windows, `$XDG_DATA_HOME/engrama` no Linux; `--data-dir` e `data/` do repo continuam valendo (modo dev detectado por checkout git). Migração opcional e explícita do `data/` antigo, nunca silenciosa.
2. **Ollama sem disco fixo**: Windows detecta `ollama` no `PATH`/instalação padrão; `E:\Ollama` vira só um valor de config possível.
3. **Builds**: PyInstaller (pasta única) para Windows e Linux, gerados pelo CI em tag `v*` e anexados ao Release; tamanho e tempo de abertura medidos.
4. **Integração com o desktop**: arquivo `.desktop` + ícone no Linux; atalho no menu Iniciar no Windows; **início automático opt-in** nas Configurações (F6).
5. **Bandeja do sistema**: avaliar no spec do M15 (dependência extra, `pystray`, vs. não ter); decidir com o usuário antes de implementar.

Aceite: build baixado do Release roda numa máquina limpa (Windows e Linux), dados no lugar certo, autostart liga e desliga.

## Ordem e paralelismo

```
M12 (saúde) ──┬── M13 (calibração: language/memory)
              └── M14 (arte: app/art)
                         └── M15 (distribuição: config, CI, empacotamento)
```

- M12 vem primeiro: a CI protege as divisões de arquivo, e as divisões evitam conflito entre M13 e M14.
- M13 e M14 tocam áreas disjuntas e podem rodar em paralelo, cada um no seu worktree e PR.
- M15 depois, porque mexe em `Config`, CI e caminhos que todos usam.

## Fora do ciclo (registrado para depois)

Overlay no Wayland (layer-shell), minijogos/conquistas, agir no PC com permissão, promoção de receitas de ML (relatório do M10 recomendou não promover).
