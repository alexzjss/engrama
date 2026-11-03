# Engrama M8 — Suporte a Linux: design

**Status:** proposta para aprovação · **Data:** 2026-11-06 · **Base:** branch `m7` (PR #8). Fontes: specs M5 (percepção) e M7 (presença), e as medições feitas na máquina de desenvolvimento nova.

Máquina de referência do M8: **CachyOS, Hyprland, sessão Wayland** (`XDG_CURRENT_DESKTOP=Hyprland`, `XDG_SESSION_TYPE=wayland`, XWayland em `:1`), AMD Ryzen 5 7520U (4 núcleos / 8 threads, até 2,8 GHz, governador `powersave`), Python 3.13, pygame-ce 2.5.8 com SDL 2.32.10 (o SDL escolhe o driver `wayland` sozinho), Ollama 0.18 como serviço systemd em `/usr/local/bin/ollama`.

## 1. Intenção

Até o M7 o Engrama é um programa de Windows: o app abre no Linux, mas a percepção, o atalho dos olhos, o idioma do sistema e o overlay ficam mudos, o `Config` aponta para `E:\Ollama` e a suíte falha nos dois testes de orçamento de CPU.

O M8 faz o Engrama **morar no Linux tão bem quanto no Windows**, dentro do que cada sessão gráfica permite:
- a suíte inteira passa no Linux, incluindo o orçamento de CPU;
- caminhos e Ollama funcionam sem configuração no Linux;
- a percepção (app em foco, título, ociosidade, tela cheia, PC pesado) funciona no X11 e nos compositores Wayland que expõem essas informações, sempre com as mesmas permissões e a mesma ordem de checagem do M5;
- os olhos fecham por atalho global no X11 e por um comando que o usuário liga a um atalho do próprio compositor no Wayland;
- o overlay do M7 funciona em sessões X11;
- tudo o que não existe numa sessão fica **inerte**, como hoje fica fora do Windows.

No Windows nada muda.

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Sessões suportadas | **[pendente — recomendação: X11 completo (qualquer gerenciador EWMH); Wayland parcial: ociosidade por `ext-idle-notify` (Hyprland, Sway, KDE 6 e outros) e por DBus (GNOME, KDE); app em foco, título e tela cheia só em Hyprland e Sway (IPC deles); GNOME e KDE no Wayland ficam sem app em foco e sem tela cheia]** |
| Overlay no Wayland | **[pendente — recomendação: não objetivo no M8. O overlay funciona em sessão X11; no Wayland o F11 mostra "overlay ainda não funciona no Wayland" e fica no terrário]** |
| Atalho dos olhos no Wayland | **[pendente — recomendação: no X11, atalho global de verdade (`XGrabKey`); no Wayland, o comando `engrama --eyes toggle`, que o usuário liga a um atalho do compositor (o painel de permissões explica como). O Engrama nunca mexe na configuração do compositor. Portal `GlobalShortcuts` fica para depois]** |
| Pasta de dados | **[pendente — recomendação: manter `data/` na raiz do repositório em todas as plataformas (sem XDG, sem migração); `--data-dir` continua valendo]** |
| Ollama no Linux | **[pendente — recomendação: usar o Ollama do sistema (o do `PATH`, normalmente um serviço systemd), sem sobrescrever `HOME` nem `OLLAMA_MODELS`. Se não estiver rodando e o binário existir, o Engrama inicia `ollama serve` do usuário, como no Windows]** |
| Orçamento de CPU | **[pendente — recomendação: manter ≤2% em todas as plataformas, sem tolerância por sistema. O M8 conserta o custo por quadro e passa a medir o estado estável (tela de primeiro uso já respondida; overlay sem foco, que é como ele vive). Se o builder não chegar a 2% nesta máquina, para e pergunta antes de afrouxar]** |

Continuam valendo, por decisão do usuário em marcos anteriores:
- permissões por fonte e tela de primeiro uso (M5);
- lista de bloqueio, olhos fechados, sem captura de tela, sem agir no PC (M5);
- overlay andando sobre a barra, clique atravessando fora da criatura, sumir em tela cheia (M7);
- tudo local e offline; PT/EN; sem números no modo normal.

## 3. Objetivos

1. **Suíte verde no Linux.**
   - `python -m pytest -q` passa na máquina de referência, inclusive `test_core_budget` (M3) e `test_overlay_bench_within_budget` (M7).
   - Testes exclusivos de uma plataforma usam `skipif`; nenhum teste depende de um compositor real.
2. **Orçamento de CPU de volta ao limite** (causa no §10).
   - O bench mede o estado estável: config com o primeiro uso respondido (todas as permissões desligadas) por padrão; `--first-use` mede a tela modal à parte.
   - O quadro fica mais barato: `Look.from_dict` deixa de rodar duas vezes por quadro; quadros idênticos não refazem a ampliação nem o `flip`; o terrário com foco baixa de 20 para 10 quadros/s quando nada se move.
   - `tools/bench.py --threads` mostra a CPU por thread (Linux, via `/proc`), para diagnóstico.
3. **Config e Ollama multiplataforma.**
   - No Windows os padrões continuam `E:\Ollama\...`.
   - No Linux: `ollama_exe` vem do `PATH` (ou `/usr/local/bin/ollama`); `ollama_home` e `ollama_models` ficam vazios (`null`), ou seja, "não mexer".
   - Um `config.json` vindo do Windows (caminhos `X:\...`) carrega no Linux com os padrões do Linux nesses campos.
   - `OllamaServer` só passa `creationflags` no Windows (hoje o Linux levantaria `ValueError` ao iniciar o Ollama).
4. **Idioma do sistema no Linux:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`, nessa ordem, e depois `locale`. `pt*` → PT, o resto → EN.
5. **Camada de SO compartilhada** `engrama/osapi/`, só stdlib (`ctypes`, `socket`, `struct`, `subprocess`), importável pela percepção (serviços) e por `app/desktop.py`:
   - `session.py`: detecta plataforma, tipo de sessão e compositor a partir do ambiente;
   - `x11.py`: `ctypes` sobre `libX11`, `libXss` e `libXext` (janela ativa, PID, classe, título, retângulo, tela cheia, ociosidade, área útil, cursor, máscara de forma, captura de tecla);
   - `wayland.py`: cliente mínimo do protocolo Wayland em Python puro, só para `ext_idle_notifier_v1`;
   - `hyprland.py` e `sway.py`: IPC por socket Unix (janela ativa, PID, classe, título, tela cheia);
   - `dbus_idle.py`: ociosidade por `gdbus` (GNOME Mutter `IdleMonitor`, `org.freedesktop.ScreenSaver`).
6. **Percepção no Linux:** `LinuxSources` implementa o mesmo protocolo `Sources` do M5 (`foreground`, `idle_seconds`, `is_fullscreen`, `cpu_percent`) escolhendo, por sessão, o primeiro backend que funciona. O serviço de percepção, a ordem de checagem e a higienização não mudam.
   - Nomes de processo do Linux entram na tabela de categorias (`firefox`, `code`, `kitty`, `steam`, jogos nativos `.x86_64` e do Proton `.exe`). As chaves do Windows continuam iguais.
7. **Olhos no Linux.**
   - X11: `GlobalHotkey` ganha uma API X11 (`XGrabKey` numa conexão própria, numa thread), com o mesmo formato de atalho (`ctrl+alt+e`).
   - Todas as plataformas POSIX: `engrama --eyes toggle` alterna os olhos de uma instância aberta (sinal `SIGUSR1` para o PID do lock do M7).
   - Wayland: o painel de permissões troca o aviso "atalho indisponível" por uma dica de como ligar o comando a um atalho do compositor.
8. **Overlay em sessão X11:** `X11Desktop` implementa a interface `Desktop` do M7 (área útil, cursor, janela ativa, sempre no topo, fora da barra de tarefas, posição, mostrar/esconder, restaurar). A transparência e o clique atravessando vêm de uma **máscara de forma** (XShape) feita da cor-chave, atualizada só quando a silhueta muda.
9. **README** PT/EN com instalação no Linux, o que funciona em cada sessão e como ligar o atalho dos olhos no Hyprland, Sway, KDE e GNOME.

## 4. Não objetivos

- macOS.
- Overlay em sessão Wayland (layer-shell, XWayland forçado, `hyprctl dispatch`).
- App em foco e tela cheia em GNOME e KDE no Wayland (precisariam de extensão do shell ou script do KWin).
- Portal `org.freedesktop.portal.GlobalShortcuts` e qualquer biblioteca DBus em Python.
- Empacotamento: `.desktop`, AppImage, Flatpak, AUR.
- Vários monitores (como no M7).
- Dependências novas obrigatórias (`python-xlib`, `dbus-python`, `pywayland`, `pywin32`).
- Mudar o kernel, a mente, o lab ou o vocabulário.

## 5. Anti-objetivos (falha mesmo que "funcione")

- Ler `/dev/input`, eventos de teclado, a área de transferência ou a tela. A ociosidade vem só de APIs de ociosidade (bordas "ocioso/voltou" ou um número de milissegundos).
- Ler uma fonte sem permissão, antes do primeiro uso ou de olhos fechados (a ordem do M5 vale igual no Linux).
- Uma biblioteca ausente, um compositor sem suporte, um socket que não responde ou um `gdbus` que trava chegar à UI ou à simulação como exceção ou travamento.
- Qualquer chamada de SO bloqueante na thread principal: IPC e `gdbus` rodam só na thread da percepção ou do overlay, com tempo limite curto.
- Abrir subprocesso por quadro. `gdbus` no máximo uma vez por leitura de ociosidade (intervalo de percepção), nunca no laço rápido de tela cheia.
- Deixar processo zumbi ou conexão aberta depois de sair.
- Mexer na configuração do compositor, do gerenciador de janelas ou do sistema (atalhos, regras de janela, serviços).
- Gravar fora do data dir; rede além do LLM local.
- Mudar qualquer comportamento no Windows: padrões do `Config`, Ollama, percepção, atalho, overlay, textos.
- Afrouxar o orçamento de CPU sem decisão do usuário.

## 6. Restrições

Todas as restrições globais dos marcos anteriores continuam valendo:
- `EVENT_KINDS`, `ACTIONS`, `FOOD_IDS`, `NEED_KEYS`, `CHANNELS` não mudam;
- kernel determinístico; o lab fica bit-idêntico ao M7;
- regras de importação de `tests/test_architecture.py`;
- ≤150 MB RSS e ≤2% de CPU médio (ver §2);
- PT/EN em todo texto novo; sem números no modo normal;
- local e offline; commits sem atribuição a IA.

Além disso:
- **`engrama/osapi/` só importa stdlib** e nada de `engrama`. Pode ser importada por `engrama/services/perception` e por `engrama/app/desktop.py`; não pela UI, arte, áudio, kernel, mente ou módulos.
- **Tudo injetável:** cada backend recebe um `env` (dict) e, quando abre socket ou subprocesso, um conector/runner falso nos testes. Nenhum teste fala com um compositor ou servidor X de verdade (os testes "reais" são `skipif` sem a sessão certa).
- **Tempo limite:** IPC por socket ≤ 0,2 s; `gdbus` ≤ 0,5 s. Backend que falha fica desligado por 60 s antes de tentar de novo.
- **Detecção de sessão** pelo ambiente, nunca por subprocesso: `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`, `SWAYSOCK`, `XDG_CURRENT_DESKTOP`.
- **Numa sessão Wayland nunca se usa X11 para percepção ou overlay** (o XWayland só enxerga janelas X e daria dados errados).

## 7. Critérios de aceitação

Testes headless com fontes, sockets e runners falsos, salvo indicação:

1. **Suíte no Linux:** `python -m pytest -q` passa na máquina de referência, incluindo os dois testes de orçamento, com ≤2% de CPU e ≤150 MB.
2. **Windows igual:** com `sys.platform == "win32"` simulado, os padrões do `Config`, o ambiente e os `creationflags` do `OllamaServer` e a escolha `WinSources`/`WinDesktop`/`_WinApi` são os do M7.
3. **Config no Linux:** um config novo não contém `E:`; `ollama_home`/`ollama_models` são `null`; um config com `"ollama_exe": "E:\\Ollama\\ollama.exe"` carrega no Linux com o caminho do `PATH`; `OllamaServer.start()` com binário falso não passa `creationflags` nem muda `HOME`.
4. **Idioma:** `LANG=pt_BR.UTF-8` → `pt`; `LANGUAGE=en_US:pt_BR` → `en`; `LANG=C` → `en`.
5. **Hyprland:** com um socket falso respondendo `j/activewindow` (JSON gravado da máquina de referência), `foreground()` devolve `(nome do processo pelo PID, título)` e `is_fullscreen()` segue o campo `fullscreen`; socket ausente ou mudo → `None` em ≤ 0,2 s.
6. **Sway:** com um socket i3-ipc falso, a árvore com o nó focado dá o mesmo resultado.
7. **Ociosidade Wayland:** com um compositor falso que anuncia `ext_idle_notifier_v1`, depois do evento `idled` `idle_seconds()` ≥ `IDLE_AFTER_S`; depois de `resumed`, ≈ 0. Sem o global anunciado → `None`.
8. **Ociosidade DBus:** com um runner falso de `gdbus`, a resposta do Mutter (`(uint64 N,)`) ou do ScreenSaver (`(uint32 N,)`) vira segundos; erro ou tempo limite → próximo backend ou `None`.
9. **X11:** com uma API X falsa, `foreground`, `is_fullscreen` (`_NET_WM_STATE_FULLSCREEN`) e `idle_seconds` (XScreenSaver) funcionam; sem `DISPLAY` ou sem `libX11` → inerte.
10. **Permissões e privacidade no Linux:** o teste de "bloqueado nunca vaza" e o de "fonte desligada nunca é lida" do M5 passam também com `LinuxSources` sobre backends falsos (contadores de chamada em 0; título cru ausente de memória, explog e prompts).
11. **Categorias:** `firefox`, `code`, `kitty`, `hollow_knight.x86_64` e `HollowKnight.exe` caem nas categorias certas; todas as chaves do Windows continuam com a mesma categoria; `spotify` (Linux) dá tema de música.
12. **Olhos:** `engrama --eyes toggle --data-dir D` com uma instância aberta em `D` alterna os olhos em até um quadro; sem instância, sai com código 1 e uma mensagem PT/EN; no Windows, sai com código 2 e indica o atalho. A API X11 do atalho registra a tecla também com NumLock e CapsLock. No Wayland, o painel mostra a dica do comando.
13. **Overlay X11:** com uma API X falsa, `make_overlay` liga sempre-no-topo, fora da barra e a máscara; a máscara só é reenviada quando a silhueta muda; `restore` desfaz tudo. Numa sessão Wayland `get_desktop()` devolve `NullDesktop` e o F11 mostra o aviso próprio do Wayland.
14. **Robustez:** todo backend falso que levanta exceção em toda chamada não derruba nada; a percepção continua com os outros.
15. **Lab e vocabulário:** a corrida curta do lab é idêntica à do M7; as tuplas do vocabulário não mudam.
16. **Smoke manual** na máquina de referência (Hyprland), relatado no PR: o app abre, a tela de primeiro uso aparece, a criatura nota o app em foco e a tela cheia, a ociosidade chega depois de dois minutos sem mexer, `engrama --eyes toggle` ligado a um `bind` do Hyprland fecha os olhos, F11 avisa que o overlay não funciona no Wayland.

## 8. O que fica com o builder

- As chamadas exatas de `libX11`/`libXss`/`libXext` via `ctypes` (átomos EWMH, `XGetWindowProperty`, `XScreenSaverQueryInfo`, `XShapeCombineMask`, `XGrabKey`, tratador de erro X que não derruba o processo).
- O cliente Wayland mínimo: registro, `wl_seat`, `ext_idle_notifier_v1.get_idle_notification`, leitura não bloqueante dos eventos.
- Como a ociosidade em bordas ("ocioso há T") vira segundos contínuos.
- Os campos exatos do JSON do Hyprland e da árvore do Sway, e o que conta como tela cheia em cada um.
- Os nomes de processo do Linux na tabela de categorias e a normalização de sufixos.
- Como o X11 resolve PID errado de app em sandbox (Flatpak): cair para a classe da janela.
- Como o `X11Desktop` usa `pygame.Window` (posição, sempre no topo, mostrar/esconder) junto com `ctypes`.
- O texto da dica de atalho no Wayland e os exemplos do README por compositor.
- A técnica de "quadro idêntico" e o limiar de "nada se move" do FPS adaptativo, desde que o bench feche em ≤2%.

## 9. Decisões minhas (para o usuário conferir)

- **Camada `osapi` nova**, em vez de duplicar `ctypes` do X11 entre percepção e desktop. Ela não sabe nada do Engrama e só usa stdlib.
- **Sem subprocesso onde existe socket:** Hyprland e Sway por socket Unix (≈0,4 ms por pedido medido aqui), Wayland por socket, X11 por `ctypes`. `gdbus` só para a ociosidade no GNOME/KDE, porque fazer DBus à mão seria muito código.
- **`SIGUSR1` em vez de socket de controle** para o comando dos olhos: o lock do M7 já guarda o PID, e um sinal não abre porta nenhuma. O comando confere que o PID é um processo do Engrama antes de mandar o sinal.
- **O overlay no X11 usa XShape**, porque o X11 não tem cor-chave como o Windows; a máscara sai da mesma cor-chave do M7, então a UI do overlay não muda.
- **Wayland não usa XWayland para nada de percepção ou overlay**, mesmo quando o `DISPLAY` existe.
- **A chave do cache de categorias do M5 não muda** (nome do processo em minúsculas). A normalização de sufixos só vale para consultar a tabela, para não invalidar caches do Windows.
- **O bench do overlay mede a janela sem foco**, que é o caso real (o overlay não pega foco ao aparecer). Isso entra na decisão de orçamento do §2.
- **FPS adaptativo no terrário:** com foco, 20 quadros/s quando a criatura anda, pula ou há chat/painel ativo; 10 quando nada se move. As animações do V-Pet trocam de quadro a 3 por segundo, então a diferença não aparece.
- **Versão 0.8.0.**

## 10. Causa do orçamento de CPU estourado (medido na máquina de referência)

Medições com `SDL_VIDEODRIVER=dummy`, CPU em % de um núcleo:

| Medida | Valor |
|---|---|
| `bench --app` (data dir novo, igual ao `test_core_budget`) | 2,8–3,4% (o `main` também falha: 3,31%) |
| Mesmo bench com o primeiro uso já respondido | 2,5% |
| + cache de `Look.from_dict` (protótipo) | 2,2% |
| Laço vazio do pygame a 20 quadros/s (`event.get` + `flip` + `tick`) | 0,47% |
| Thread da simulação (1 tick/s, ≈0,7 ms) | ≈0,2% |
| Thread de áudio do SDL | ≈0,1% |
| `bench --overlay` (janela com foco, 20 quadros/s) | 2,9–3,0% |

Custo por quadro do terrário (≈0,6 ms em estado estável, ≈0,86 ms com a tela de primeiro uso):
- `pygame.transform.scale` de 160×120 para 640×480: **0,39 ms** (a maior parte);
- tela de primeiro uso desenhada a cada quadro: 0,22 ms — e ela está aberta no bench porque o bench usa um data dir novo, ou seja, **o teste mede uma tela que o usuário vê uma vez só**;
- `Look.from_dict` chamado duas vezes por quadro (cena e `_drain_host_events`, só para pegar o tom de voz): ≈0,2 ms;
- cena, HUD, chat: ≈0,07 ms.

Só 31 de 200 quadros seguidos mudam algum pixel quando a criatura está parada, então refazer a ampliação e o `flip` em quadros idênticos é desperdício; no driver real (Wayland/X11) o `flip` custa mais ≈0,5 ms, que o bench nem mede.

Conclusão: não é um problema do Linux em si. O orçamento de 2% é "por núcleo" e a máquina nova é um notebook de baixo consumo (Zen 2, 2,8 GHz, `powersave`), mais lento por núcleo que o PC Windows onde o orçamento foi calibrado; o custo fixo por quadro a 20 quadros/s, mais um bench que mede a tela de primeiro uso, passa do limite. As correções do §3.2 atacam exatamente esses itens.

## 11. Revisão — pontos de risco

1. Uma sessão sem nada (TTY, `SDL_VIDEODRIVER=dummy`, compositor desconhecido) tem que dar tudo inerte, sem exceção e sem atraso na abertura.
2. Socket do Hyprland/Sway que aceita a conexão mas não responde: tempo limite e desligar o backend por um minuto.
3. Cliente Wayland: mensagem cortada no meio do buffer, evento `wl_display.error`, compositor que fecha a conexão.
4. `SIGUSR1` chegando durante a escrita do config: o tratador só marca uma flag; a troca acontece no laço principal.
5. XShape com a janela redimensionada (mini-menu, chat): a máscara tem que acompanhar o novo tamanho no mesmo quadro.
6. Windows: nenhum caminho novo pode ser escolhido no `win32` (testes com `sys.platform` simulado).
7. Orçamento: os ganhos têm que aparecer no bench sem mudar o que o usuário vê (hash dos quadros com e sem o pulo de quadros idênticos).
