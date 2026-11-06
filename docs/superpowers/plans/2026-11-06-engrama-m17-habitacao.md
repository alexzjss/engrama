# Engrama M17: Habitação no desktop, plano de implementação

**Objetivo:** a criatura deixa de andar só na faixa da barra de tarefas e passa a morar no desktop: senta na borda de cima da janela ativa, pula entre bordas, cai quando a janela some, dorme num canto e reage ao cursor pelo temperamento. E o overlay passa a funcionar no Hyprland (a máquina do dev), onde hoje só há terrário.

**Spec:** `docs/superpowers/specs/2026-11-06-engrama-m16-m20-roadmap.md` (seção M17). Parte de `main`, branch `m17`, em paralelo com o M19 (arquivos disjuntos: aqui só `app/ui/overlay`, `app/desktop`, `osapi`).

**Execução:** um agente Sonnet em worktree; spike com tempo contado antes do código. Um PR no fim.

## T1. Spike: como ter overlay no Hyprland

Duas rotas, medidas na máquina real (Hyprland 0.56, config em Lua):

| Rota | O que testar | Critério |
|---|---|---|
| (a) XWayland (`SDL_VIDEODRIVER=x11`) + regras | O caminho X11 atual (forma por XShape) mais regras de janela | Fundo transparente e clique atravessando fora do corpo |
| (b) Wayland nativo do SDL + regras | Superfície EGL com alfa (`SDL_VIDEO_EGL_ALLOW_TRANSPARENCY`), regras e `dispatch` do hyprctl | Fundo transparente; mover a janela; clique |

Verificação com `grim` e `hyprctl clients -j`; toda janela de teste é fechada. Resultado em `docs/superpowers/reports/2026-11-06-m17-spike.md`. Se nenhuma servir, só o X11 e o Windows ganham a geometria e o andar no mundo.

## T2. `Desktop.windows()`

- `Desktop.windows() -> list[Rect]`: retângulos das janelas visíveis, **da mais próxima para a mais distante**, só geometria (nunca título, classe ou PID saem do osapi).
- Hyprland (`osapi/hyprland.py`): `j/clients` e `j/monitors` pelo IPC que já existe; filtra não mapeada, escondida, outro workspace, janela própria e janela minúscula (`parse_windows`, pura).
- X11 (`osapi/x11.py`): `_NET_CLIENT_LIST_STACKING` (de cima para baixo), geometria com `_NET_FRAME_EXTENTS`, filtro puro `filter_x11_windows` (área de trabalho atual, não minimizada, tipo normal, sem a própria).
- Windows (`app/desktop.py`): `EnumWindows` (já de cima para baixo), `IsWindowVisible`, `DwmGetWindowAttribute` (limites estendidos, pula `CLOAKED`), filtro puro `filter_win_windows`.
- Wayland fora do Hyprland: `[]` (o overlay nem liga).

## T3. Andar no mundo

- `engrama/app/ui/world.py` (puro, sem pygame): `visible_edges` (bordas de cima, sem o que está tapado por janelas na frente), `Walker` (andar, pular até uma borda mais alta, cair por gravidade, pousar na primeira superfície), `temper_of` (arisco foge, brincalhão segue, curioso olha).
- `OverlayController`: junta a faixa da barra + as bordas; sondagem das janelas a no máximo 2 Hz (`balance.WINDOWS_POLL_HZ`); a janela do overlay passa a ter o pé na superfície atual; vontade de pular de tempos em tempos (preferindo a janela do topo); dormir e esconder-se descem para o chão; o cursor reage por temperamento (`balance.OVERLAY_FLEE_PX_S`).
- Testes com geometria falsa (`FakeDesktop(wins=...)`): sentar, pular, cair, dormir no canto, 2 Hz, temperamentos.

## T4. Habilitar e medir

- `HyprlandDesktop` (`app/desktop.py`): Wayland nativo, `GLPresenter` (`app/glpresent.py`, ctypes + libGL), regras e `dispatch` pelo IPC do Hyprland (sintaxe Lua e antiga), janela justa porque o SDL2 não deixa clicar através.
- `get_desktop()`: Hyprland + driver `wayland` = overlay; os outros compositores seguem sem. `prefer_wayland_on_hyprland()` escolhe o driver nativo quando o usuário não definiu.
- Bench do overlay com janelas falsas (uma deriva), dentro do orçamento (2% de CPU, 150 MB).
- README: tabela "Linux: o que cada sessão oferece", recursos, limitações, tabela de marcos. Versão 0.17.0 só se a `main` já estiver em 0.16.0 no fim.
