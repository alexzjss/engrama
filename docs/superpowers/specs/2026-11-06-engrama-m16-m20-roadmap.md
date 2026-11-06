# Engrama — roadmap M16–M20 (IA, visual e habitação no desktop)

Data: 2026-11-06. Estado de partida: M1–M15 no main (v0.15.0), README do MVP (PR #18).

## Diagnóstico

- **main está vermelho**: ruff F401 em `tools/screenshots.py`, e `tests/app/test_icon.py` ainda compara os bytes do `icon.ico` commitado (varia por build do SDL).
- **Testes**: a duração total depende de poucas simulações longas: `tests/lab/test_rebirth.py` (180 s + 122 s + 86 s + 72 s) e `tests/test_m2_acceptance.py` (~30–50 s cada). Várias rodam a mesma receita/semente/perfil de novo.
- **M13** continua parcial (média de 3 repetições do harness nunca terminou).
- **Habitação**: o overlay só funciona em X11/Windows, mas a máquina de desenvolvimento é Hyprland. Hoje a criatura só anda numa faixa sobre a barra de tarefas e não sabe onde estão as janelas.
- **IA**: a mente aprende (Q-learning, SNN de rotina, PAD), mas o usuário quase não vê isso acontecer. O LLM só fala. A rotina prevista pela SNN não muda o comportamento visível, e o sono não processa nada.

## Marcos

### M16 — Saúde 2: CI verde e testes mais rápidos (em execução)
Corrigir o lint e o teste do ícone (checagem estrutural). Compartilhar simulações determinísticas entre testes (fixtures por módulo + `xdist_group`), perfilar o hot path do laboratório (só otimizações que deixem a saída idêntica bit a bit), agendar os testes longos primeiro e documentar o loop rápido `pytest -n 4 -m "not slow and not perf"`. Aceite: suíte verde, tempos antes/depois medidos.

### M17 — Habitação no desktop
1. **Spike (1 dia, decide o caminho):** no Hyprland, (a) overlay atual via XWayland (`SDL_VIDEODRIVER=x11`) + `windowrulev2` (float, pin, noborder, noshadow, nofocus, transparência); (b) janela Wayland nativa do SDL com regras do hyprctl. Escolher a que dá fundo transparente e clique atravessando fora da criatura.
2. **Geometria de janelas:** `Desktop.windows()` → retângulos das janelas visíveis (Hyprland `hyprctl clients -j`, X11 `_NET_CLIENT_LIST_STACKING`, Win32 `EnumWindows`). Só geometria, nunca títulos (a percepção continua opt-in).
3. **Andar no mundo:** sentar na borda de cima da janela ativa, pular entre bordas, cair quando a janela some, dormir num canto à noite. Reagir ao cursor por traço (curioso olha, brincalhão segue, arisco foge).
Aceite: bench do overlay dentro do orçamento (2% CPU, 150 MB) nas três plataformas; testes de movimento com geometria falsa.

### M18 — Casa e ritmo visual
- Ciclo dia/noite pelo relógio real no terrário (paleta, luz), sono visível (olhos, Zzz, respiração).
- Emotes de partícula guiados pelo PAD (coração, nota, gota, raio), sempre dentro do orçamento de FPS.
- **Casa**: objetos que se acumulam com o cuidado (cama, prato, brinquedo, planta), procedurais a partir da semente e da família, com o mesmo pipeline de golden de sprites. No overlay, ela tem um "canto de casa" na tela.
Aceite: golden de sprites atualizado de propósito, screenshots novos em `tools/screenshots.py`.

### M19 — Mente visível: rotina e sonhos (IA)
- **Rotina:** a previsão da SNN vira comportamento: espera você no horário de costume, cumprimenta quando você volta, fica com sono junto com você, nota desvios ("chegou tarde hoje"). O sinal entra no quadro-negro e a mente decide; o LLM só verbaliza.
- **Sonhos = replay de experiência:** durante o sono, o Q-learning faz replay offline (estilo Dyna) dos episódios do log. Isso é ML de verdade e pode ser medido no laboratório. Ao acordar, o LLM narra um sonho curto a partir dos episódios repetidos e das memórias do dia (job de baixa prioridade, com fallback sem LLM).
- Aceite: suíte do laboratório (3 sementes) mostra que o replay não piora recompensa nem Brier. Só vira padrão se ganhar; senão entra como receita opcional, como no M10.

### M20 — Agir com permissão (IA, opt-in)
Ferramentas pequenas e seguras, cada uma com permissão própria no F8: lembretes/timers ("me lembra em 20 min"), companhia de foco (pomodoro: ela fica quieta e comemora no fim), "anota isso" vai para a memória. O LLM extrai a intenção com saída JSON estruturada (Ollama `format`), validada por esquema. **A mente decide se age**, e só existem ações da lista branca (nada de shell, nada de rede).
Aceite: harness de intenções (PT/EN) com taxa de extração medida; sem LLM, os comandos por menu continuam funcionando.

### Pendência avulsa — aceite do M13
Rodar `tools/smoke_llm.py --repeat 3` **sozinho** (sem suíte nem agentes em paralelo), de madrugada, e atualizar o relatório. Um PR pequeno.

## Ordem e paralelismo
1. M16 (agora).
2. M17 (overlay/osapi) **em paralelo** com M19 (mind/modules/services): arquivos disjuntos.
3. M18 depois do M17 (os dois mexem no desenho do overlay).
4. M20 por último (depende da UI de permissões e da fila do LLM).

No máximo 2 agentes ao mesmo tempo (7 GB de RAM), nunca com o Ollama carregado.

## Execução e custo
- **Opus**: spec e plano curtos por marco, revisão do diff final.
- **Sonnet**: tarefas de código em worktrees, uma PR por marco.
- **Haiku**: tarefas mecânicas (strings i18n, README, versão, regerar golden/screenshots, checagens de lint).
- **Testes**: cada tarefa roda só os testes da área + o loop rápido. A suíte completa roda uma vez por marco, antes da PR. Teste novo acima de ~5 s leva a marca `slow`.

## Fora do ciclo
Minijogos/conquistas, multi-criaturas, visão por câmera/tela, modelos maiores que ~2B.
