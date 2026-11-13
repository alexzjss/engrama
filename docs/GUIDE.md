<a id="top"></a>

# Guia de uso / User guide

**PT** | [EN](#en)

## Requisitos e instalação

**Requisitos**

- Python 3.13 ou mais novo (dependências: `pygame-ce`, `numpy`, `psutil`).
- Windows ou Linux.
- Para conversar: [Ollama](https://ollama.com) e um modelo (padrão `qwen3:1.7b`). Opcional: um modelo de embedding (`embeddinggemma`, cerca de 0,6 GB de RAM no Ollama enquanto carregado). Sem Ollama o app funciona, com balbucio.

**Instalar**

Para usar, sem instalar Python: baixe o pacote da [página de Releases](https://github.com/alexzjss/engrama/releases) e extraia.

- *Windows:* `engrama-<versão>-windows-x64.zip`. Extraia e rode `engrama\engrama.exe`. O SmartScreen avisa na primeira vez, porque o build não é assinado: clique em **Mais informações** e depois em **Executar assim mesmo**.
- *Linux:* `engrama-<versão>-linux-x64.tar.gz`. Extraia (`tar -xzf engrama-<versão>-linux-x64.tar.gz`) e rode `./engrama/engrama`.

Para desenvolver, instale a partir do código:

```
python -m venv .venv
.venv\Scripts\activate             # Windows
source .venv/bin/activate          # Linux (bash/zsh)
source .venv/bin/activate.fish     # Linux (fish)
pip install -e .[dev]              # pygame-ce, numpy, psutil (+ pytest)
```

**Ollama**

- O Ollama é instalado à parte, pelo [instalador oficial](https://ollama.com). O app o procura no PATH e, no Windows, também na pasta do instalador (`%LOCALAPPDATA%\Programs\Ollama`) e em `%ProgramFiles%\Ollama`. Se não achar, a tela de Modelos (F5) diz que o Ollama não foi encontrado.
- *Windows:* o app inicia o `ollama serve` sozinho, em segundo plano, e o encerra ao sair se foi ele quem iniciou. Não há caminho fixo em `E:\`.
- *Linux:* usa o `ollama` do `PATH` (em geral o serviço systemd) e não mexe em `HOME` nem em `OLLAMA_MODELS`. Se não estiver rodando e o binário existir, o Engrama inicia `ollama serve` e o encerra ao sair. Caminhos `E:\` de um `config.json` vindo do Windows são ignorados.
- O modelo só fica carregado durante e logo após a conversa (`keep_alive` de 600 s).

**Modelos**

- Pelo app: **F5** abre o menu de modelos (baixar o de conversa; ligar/desligar/trocar a busca por significado).
- Pelo terminal: `ollama pull qwen3:1.7b` e, opcionalmente, `ollama pull embeddinggemma`.

## Primeiro uso

```
python -m engrama                    # ou o comando `engrama`
python -m engrama --dev --time-scale 60 --seed 1     # modo dev: tempo acelerado, mostra números
python -m engrama --no-llm --frames 600              # sem Ollama; encerra após 600 quadros (smoke test)
```

1. Uma tela pergunta, fonte por fonte, o que ela pode olhar (tudo começa desligado). Dá para mudar depois no F8.
2. Um ovo aparece. Clique nele até chocar; ela pede um nome (dá para deixar para depois, em Ajustes). Faça carinho (clique), alimente (botão da maçã ou F4), converse (Enter envia).
3. Para conversar, baixe o modelo pelo F5 (ou veja "Ollama não encontrado"/"baixando modelo" na tela). Sem ele, a conversa vira balbucio.
4. Deixe o app aberto: a criatura cresce com o tempo real. Com o app fechado o tempo passa de forma suave (ela não adoece nem morre só por isso).

## Privacidade e offline

Este é o ponto central do projeto, não um detalhe.

- **Tudo local.** O LLM roda no seu Ollama; o app não fala com nenhum servidor remoto. Os dados ficam numa pasta no seu disco (no Windows, `%APPDATA%\Engrama`; no Linux, `~/.local/share/engrama`), que você pode apagar ou copiar quando quiser.
- **Percepção é opt-in, fonte por fonte.** Na primeira execução uma tela pergunta o que ela pode olhar. Tudo começa **desligado**; "agora não" é uma resposta válida. O painel Permissões (F8) muda isso a qualquer momento.
- **Olhos fechados** (F9 ou atalho global `Ctrl+Alt+E`) pausam toda a percepção, mesmo com a janela sem foco.
- **Lista de bloqueio.** Apps e títulos com termos como banco, senha ou gerenciador de senhas já vêm bloqueados; você adiciona os seus. Um app bloqueado chega como `privado`: nem nome nem título saem do serviço de percepção.
- **O que é guardado:** só a categoria do app (jogo, música, programação...) e, quando dá, um tema curto tirado do título. **Nunca:** título cru, caminho de arquivo, conteúdo de arquivo, nome de processo bloqueado.
- **Sem espionagem de entrada:** nada de teclado, tela, área de transferência ou `/dev/input`. O cursor só é lido no modo sobreposição, poucas vezes por segundo, e nunca é guardado.
- **Você controla a memória.** Apague fatos, assuntos, opiniões ou "esquecer tudo" (com confirmação em etapas). Apagar é definitivo: sai do banco, dos episódios que citam o item, da memória de curto prazo e dos vetores de busca.
- **O que passa para a próxima geração** não inclui fatos, assuntos nem opiniões sobre você; só traços de personalidade e até 3 lembranças ancestrais sem números e sem nada bloqueado.
- **Ações são uma lista fechada.** Lembretes, foco e anotações, cada um ligado por você. O pedido é lido por regras fixas; só quando elas não entendem uma frase que parece um pedido o LLM local é consultado, com saída JSON validada por esquema, e o resultado passa pela mesma checagem (tipo de ação, duração, tamanho do texto). Ela repete o tempo que entendeu, para você pegar um engano na hora.
- **Sem LLM funciona.** `--no-llm` nunca inicia nem contata o Ollama.
- **Nada é baixado sozinho.** O Engrama nunca baixa modelos por conta própria; você pede, pelo menu F5 ou pelo terminal.

## Como usar

### Botões e teclas

Tudo tem botão: a barra no canto de baixo da janela abre cada painel (passe o mouse para ver o nome e a tecla), e o **?** abre a ajuda. Um painel fecha no **x**, com Esc ou clicando fora dele. As teclas abaixo são atalhos para as mesmas coisas.

| Tecla | O que faz |
|---|---|
| F1 | Mundo digital (itens de manutenção de brincadeira; nada é feito no seu PC) |
| F2 | Visão da Mente: grafo da receita, propostas do tick (a vencedora destacada), custo em ms por módulo, raster de disparos e surpresa da SNN |
| F3 | Descanso manual |
| F4 | Comidas |
| F5 | Modelos e busca por significado |
| F6 | Configurações |
| F7 | Memórias (fatos, assuntos, opiniões, reflexões; apagar um item ou "esquecer tudo") |
| F8 | Permissões da percepção, lista de bloqueio, intervalo de leitura (15, 30 ou 60 s) |
| F9 | Olhos fechados/abertos (atalho global padrão `Ctrl+Alt+E`) |
| F10 | Gerações: vidas passadas (ramo, duração, causa); apagar o arquivo de uma geração (o registro permanece) |
| F11 | Alterna terrário e modo sobreposição (a escolha é salva) |
| F12 | Modo dev (números; `PgUp`/`PgDn` mudam a escala de tempo) |
| Esc | Fecha o painel |
| Enter | Envia a mensagem |

Clique na criatura no modo sobreposição para abrir o mini-menu: Comida, Remédio (oculto no ovo), Digital, Conversar, Terrário. Solte um arquivo ou pasta na janela e ela comenta (lê só os primeiros 8 KB de texto/código; pasta lista o primeiro nível; imagem dá só nome e tipo; arquivo bloqueado é recusado).

### Linha de comando do app

| Flag | Efeito |
|---|---|
| `--data-dir DIR` | Pasta de dados (padrão: a variável `ENGRAMA_DATA_DIR` se definida; em checkout de desenvolvimento, `data/` na raiz do repositório; instalado, a pasta do sistema) |
| `--migrate-from PATH` | Copia (não move) uma pasta de dados antiga para a pasta de dados atual, se a atual ainda não tiver save. Recusa se já houver save; nunca roda sozinho |
| `--install-desktop` / `--uninstall-desktop` | Cria ou remove o atalho do sistema (Linux: entrada no menu de aplicativos com ícone; Windows: atalho no Menu Iniciar) e sai |
| `--recipe NOME\|CAMINHO` | Receita da mente (`engrama/recipes/NOME.toml` ou caminho). Só vale em pasta de dados **nova**; com save existente é ignorada (aviso no log). Nome inexistente sai com código 2 |
| `--seed N` | Semente da criatura nova |
| `--time-scale N` | Multiplicador de tempo (para testar) |
| `--dev` | Mostra números e escala de tempo |
| `--no-llm` | Nunca inicia nem contata o Ollama (só balbucio) |
| `--frames N` | Encerra após N quadros (smoke test, sem limite de FPS) |
| `--seconds S` | Encerra após S segundos de relógio (bench) |
| `--eyes toggle` | Abre/fecha os olhos da instância aberta e sai (sai com 1 e avisa se não houver instância) |
| `--fake-perception` | Bench: máquina roteirizada no lugar da real |

Exemplo com uma mente experimental: `python -m engrama --recipe curious-v1 --data-dir ~/engrama-curious`.

### Descanso e desempenho

- **Descanso:** manual (F3) ou automático (app em tela cheia, pouca RAM livre ou 30 min sem uso). Em descanso a janela cai para 2 FPS, a mente roda em ritmo reduzido e o LLM é descarregado. Sem foco: 5 FPS; com foco: 20 FPS quando algo se mexe e 10 FPS com a criatura parada.
- **PC pesado:** CPU acima de 85% por 2 min faz a criatura descansar até aliviar.
- **Orçamento:** o app mira no máximo 150 MB de RAM e 2% de CPU médio (medido pelo bench).

### Iniciativa da criatura

Rara e por estágio: criança puxa o assunto atual, adulto opina, perfeito/final retoma algo antigo; comentários sobre a atividade do PC dividem a mesma cota (cerca de um por hora de uso ativo). Nunca em descanso, em tela cheia, de olhos fechados, em app privado ou sem o LLM pronto. Pedidos do mundo digital: no máximo um a cada 2 h; atender em 30 min a deixa feliz.

### Onde ficam os dados

A pasta de dados é, nesta ordem: `--data-dir`; a variável `ENGRAMA_DATA_DIR`; em um checkout do repositório (modo de desenvolvimento), o `data/` da raiz; e, no restante, a pasta do sistema:

- Windows: `%APPDATA%\Engrama`
- Linux: `$XDG_DATA_HOME/engrama` (padrão `~/.local/share/engrama`)

Na primeira abertura com a pasta vazia, o app cria a criatura nova ali. Se você tinha um `data/` antigo (de um checkout), copie o save com `engrama --migrate-from "<pasta antiga>"`: o comando copia e mantém a pasta original; não move nada e não roda sozinho. Se a pasta nova já tiver save, ele recusa. Sem save na pasta nova, mas com `data/save` ao lado do pacote, o app só escreve uma linha no log sugerindo o comando.

| Arquivo | Conteúdo |
|---|---|
| `config.json` | Configurações |
| `save/` | Estado da mente e do corpo |
| `host.json` | Metadados da criatura (nascimento, semente) |
| `explog.sqlite` | Log de experiência |
| `memory.sqlite` | Memória da conversa (fatos, assuntos, opiniões, episódios, vetores) |
| `actions.json` | Lembretes pendentes e a sessão de foco em andamento |
| `generations.json`, `generations/<n>/` | Registro das vidas e arquivo (memória + save) de cada uma |

Tetos da memória: 2000 episódios, 300 fatos, 300 assuntos; episódios antigos e pouco importantes são compactados (ao abrir e a cada 6 h).

### Atalho e início automático

- `engrama --install-desktop` cria o atalho: no Linux, `~/.local/share/applications/engrama.desktop` com o ícone (aparece no menu de aplicativos); no Windows, `Engrama.lnk` no Menu Iniciar. `engrama --uninstall-desktop` remove só o que ele gravou.
- **Iniciar com o sistema** é opcional e vem desligado. Ligue em **F6** (Configurações). Linux: `~/.config/autostart/engrama.desktop`; Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. A tela lê o estado do próprio sistema, então não diverge do que está gravado.
- Em checkout de desenvolvimento (rodando do repositório) nada disso é instalado, e a opção do F6 aparece indisponível, com a explicação.

## Linux: o que cada sessão oferece

O que a sessão não oferece fica inerte, sem erro. No Windows nada mudou.

| Sessão | App em foco, título, tela cheia | Ociosidade | Atalho dos olhos | Overlay (F11) |
|---|---|---|---|---|
| X11 (qualquer gerenciador EWMH) | sim | sim (XScreenSaver) | sim, global (`ctrl+alt+e`) | sim |
| Wayland: Hyprland | sim (IPC do Hyprland) | sim (`ext-idle-notify`) | comando `engrama --eyes toggle` | sim (Wayland nativo + regras do Hyprland) |
| Wayland: Sway | sim (IPC do Sway) | sim (`ext-idle-notify`) | comando `engrama --eyes toggle` | não (aviso no F11) |
| Wayland: KDE (Plasma 6) | não | sim (`ext-idle-notify` ou DBus) | comando `engrama --eyes toggle` | não (aviso no F11) |
| Wayland: GNOME | não | sim (DBus do Mutter) | comando `engrama --eyes toggle` | não (aviso no F11) |

- Sessão Wayland nunca usa X11: mesmo com `DISPLAY` presente (XWayland), percepção e overlay não consultam o X.
- **Overlay no Hyprland (M17):** o app usa a janela Wayland nativa do SDL (num Hyprland, ele já escolhe `SDL_VIDEODRIVER=wayland` se você não definiu nada). A transparência vem de uma superfície OpenGL com alfa, e a posição e as flags vêm do próprio Hyprland: ao ligar o overlay o Engrama registra, na sessão em andamento, regras para a janela de classe `engrama-overlay` (flutuante, fixa, sem borda, sombra, desfoque nem animação, sem foco inicial) e a move por `hyprctl dispatch`. Nada é gravado nos seus arquivos de configuração; as regras somem no próximo `hyprctl reload` (ligar o overlay de novo as refaz). Funciona com a sintaxe Lua (Hyprland 0.5x) e com a antiga. O SDL2 não deixa o clique atravessar pixels transparentes no Wayland, então a janela fica justa em volta do corpo e só cresce para balões, menu, conversa e painéis.
- O Engrama nunca mexe na configuração do compositor. Ligue `engrama --eyes toggle` a um atalho seu. Como o app costuma rodar do ambiente virtual, use o caminho completo (ou `python -m engrama --eyes toggle` na pasta do repositório; sem `--data-dir`, os dois usam a pasta de dados padrão):
  - Hyprland (`~/.config/hypr/hyprland.conf`): `bind = CTRL ALT, E, exec, /caminho/do/engrama/.venv/bin/engrama --eyes toggle`
  - Sway (`~/.config/sway/config`): `bindsym ctrl+alt+e exec /caminho/do/engrama/.venv/bin/engrama --eyes toggle`
  - KDE: Configurações do Sistema > Atalhos > Adicionar comando, com o mesmo comando.
  - GNOME: Configurações > Teclado > Atalhos personalizados, com o mesmo comando.
- Nos outros compositores Wayland (Sway, KDE, GNOME) o F11 mostra "o overlay só funciona no Hyprland (Wayland) por enquanto" e fica no terrário.

## Roteiro de demonstração (5 minutos)

Para apresentar sem esperar dias de vida, use uma pasta de dados só da demonstração. Há dois caminhos:

```
engrama --data-dir demo --seed 5 --time-scale 300          # do ovo: choca na hora, vira criança em uns 7 min
```

```
# do código-fonte: uma adulta já criada (12 dias simulados em cerca de 20 s), aberta no tempo normal
python -m engrama.lab sim --recipe engrama/recipes/default-v1.toml --days 12 --profile attentive --seed 5 --save demo-adulta/save
python -m engrama --data-dir demo-adulta
```

O segundo caminho abre uma adulta do ramo companheiro, com fome e querendo carinho: boa para mostrar o cuidado. Vale ter as duas pastas prontas.

1. **Ovo e nome:** clique no ovo até chocar e dê um nome. Mostre o ninho, o céu na hora real e a barra de botões.
2. **Cuidado:** carinho (corações), comida (maçã), o ícone de necessidade que some. A casa cresce com ela: pote no bebê, bola na criança, cama na adulta, planta depois.
3. **Mente:** abra a Visão da Mente (cérebro): módulos, propostas do tick e a vencedora, ao vivo.
4. **Ações:** no painel do relógio, ligue Lembretes e Foco; escreva no chat `me lembra em 30 segundos de testar` e `foco por 1 min`.
5. **Privacidade:** painel do olho (tudo desligado por padrão) e Memórias (ver e apagar).
6. **Voz:** com o Ollama instalado ela conversa; sem ele, balbucia, e a tela Modelos explica o que fazer.

A escala de tempo também acelera necessidades e doença: deixe `--time-scale` em 1 quando não estiver mostrando o crescimento.

---

<a id="en"></a>
**[PT](#top)** | EN

## Requirements and install

**Requirements**

- Python 3.13 or newer (dependencies: `pygame-ce`, `numpy`, `psutil`).
- Windows or Linux.
- To chat: [Ollama](https://ollama.com) and a model (default `qwen3:1.7b`). Optional: an embedding model (`embeddinggemma`, about 0.6 GB of RAM in Ollama while loaded). Without Ollama the app works, babbling.

**Install**

For use, without installing Python: download the bundle from the [Releases page](https://github.com/alexzjss/engrama/releases) and extract it.

- *Windows:* `engrama-<version>-windows-x64.zip`. Extract it and run `engrama\engrama.exe`. SmartScreen warns the first time because the build is not signed: click **More info**, then **Run anyway**.
- *Linux:* `engrama-<version>-linux-x64.tar.gz`. Extract it (`tar -xzf engrama-<version>-linux-x64.tar.gz`) and run `./engrama/engrama`.

For development, install from the source:

```
python -m venv .venv
.venv\Scripts\activate             # Windows
source .venv/bin/activate          # Linux (bash/zsh)
source .venv/bin/activate.fish     # Linux (fish)
pip install -e .[dev]              # pygame-ce, numpy, psutil (+ pytest)
```

**Ollama**

- Ollama is installed separately, from the [official installer](https://ollama.com). The app looks for it on `PATH` and, on Windows, also in the installer's folder (`%LOCALAPPDATA%\Programs\Ollama`) and in `%ProgramFiles%\Ollama`. If it is not found, the Models screen (F5) says Ollama was not found.
- *Windows:* the app starts `ollama serve` itself, in the background, and stops it on exit if it was the one that started it. There is no fixed `E:\` path.
- *Linux:* uses the `ollama` on `PATH` (usually the systemd service) and does not touch `HOME` or `OLLAMA_MODELS`. If it is not running and the binary exists, Engrama starts `ollama serve` and stops it on exit. `E:\` paths in a `config.json` coming from Windows are ignored.
- The model stays loaded only during and shortly after a conversation (`keep_alive` of 600 s).

**Models**

- From the app: **F5** opens the models menu (download the chat model; turn semantic search on/off or change its model).
- From the terminal: `ollama pull qwen3:1.7b` and, optionally, `ollama pull embeddinggemma`.

## First run

```
python -m engrama                    # or the `engrama` command
python -m engrama --dev --time-scale 60 --seed 1     # dev mode: fast time, shows numbers
python -m engrama --no-llm --frames 600              # no Ollama; exits after 600 frames (smoke test)
```

1. A screen asks, source by source, what it may look at (everything starts off). You can change it later in F8.
2. An egg appears. Click it until it hatches; it asks for a name (you can leave that for later, in Settings). Pet it (click), feed it (the apple button or F4), talk to it (Enter sends).
3. To chat, download the model via F5 (or see "Ollama not found"/"downloading model" on screen). Without it, the conversation becomes babble.
4. Leave the app open: the creature grows in real time. While the app is closed, time passes gently (it neither falls ill nor dies just because of that).

## Privacy and offline

This is the central point of the project, not a detail.

- **Everything local.** The LLM runs in your Ollama; the app talks to no remote server. Data lives in a folder on your disk (on Windows, `%APPDATA%\Engrama`; on Linux, `~/.local/share/engrama`) that you can delete or copy at any time.
- **Perception is opt-in, source by source.** On first run a screen asks what it may look at. Everything starts **off**; "not now" is a valid answer. The Permissions panel (F8) changes this at any time.
- **Closed eyes** (F9 or the global hotkey `Ctrl+Alt+E`) pause all perception, even when the window is unfocused.
- **Blocklist.** Apps and titles with terms such as bank, password or password manager are blocked by default; you add your own. A blocked app arrives as `privado`: neither name nor title leaves the perception service.
- **What is stored:** only the app category (game, music, programming...) and, when possible, a short topic taken from the title. **Never:** raw title, file path, file content, blocked process name.
- **No input snooping:** no keyboard, screen, clipboard or `/dev/input`. The cursor is read only in overlay mode, a few times per second, and never stored.
- **You control memory.** Delete facts, topics, opinions or "forget everything" (with stepwise confirmation). Deleting is final: it leaves the database, the episodes that cite the item, short-term memory and the search vectors.
- **What passes to the next generation** excludes facts, topics and opinions about you; only personality traits and up to 3 ancestral memories with no numbers and nothing blocked.
- **Actions are a closed list.** Reminders, focus and notes, each turned on by you. The request is read by fixed rules; only when they cannot read a sentence that looks like a request is the local LLM asked, with schema-validated JSON output, and the result goes through the same checks (kind of action, duration, text length). The creature says back the time it understood, so you catch a mistake at once.
- **Works without the LLM.** `--no-llm` never starts or contacts Ollama.
- **Nothing is downloaded by itself.** Engrama never downloads models on its own; you ask for it, via the F5 menu or the terminal.

## Usage

### Buttons and keys

Everything has a button: the bar at the bottom of the window opens each panel (hover to see its name and key), and **?** opens the help. A panel closes with its **x**, with Esc or by clicking outside it. The keys below are shortcuts for the same things.

| Key | What it does |
|---|---|
| F1 | Digital world (playful maintenance items; nothing is done to your PC) |
| F2 | Mind View: recipe graph, tick proposals (winner highlighted), cost in ms per module, spike raster and SNN surprise |
| F3 | Manual rest |
| F4 | Foods |
| F5 | Models and semantic search |
| F6 | Settings |
| F7 | Memories (facts, topics, opinions, reflections; delete one item or "forget everything") |
| F8 | Perception permissions, blocklist, read interval (15, 30 or 60 s) |
| F9 | Eyes closed/open (default global hotkey `Ctrl+Alt+E`) |
| F10 | Generations: past lives (branch, duration, cause); delete a generation's archive (the record stays) |
| F11 | Toggle terrarium and overlay mode (the choice is saved) |
| F12 | Dev mode (numbers; `PgUp`/`PgDn` change the time scale) |
| Esc | Closes the panel |
| Enter | Sends the message |

Click the creature in overlay mode to open the mini-menu: Food, Medicine (hidden for the egg), Digital, Chat, Terrarium. Drop a file or folder on the window and it comments (reads only the first 8 KB of text/code; a folder lists its first level; an image gives only name and type; a blocked file is refused).

### App command line

| Flag | Effect |
|---|---|
| `--data-dir DIR` | Data folder (default: the `ENGRAMA_DATA_DIR` variable if set; in a development checkout, `data/` at the repository root; installed, the OS data folder) |
| `--migrate-from PATH` | Copies (does not move) an old data folder into the current one, if the current one has no save yet. Refuses if there is a save; never runs by itself |
| `--install-desktop` / `--uninstall-desktop` | Creates or removes the system shortcut (Linux: applications menu entry with icon; Windows: Start menu shortcut), then exits |
| `--recipe NAME\|PATH` | Mind recipe (`engrama/recipes/NAME.toml` or a path). Only applies to a **new** data dir; with an existing save it is ignored (warning in the log). An unknown name exits with code 2 |
| `--seed N` | Seed of a new creature |
| `--time-scale N` | Time multiplier (for testing) |
| `--dev` | Shows numbers and the time scale |
| `--no-llm` | Never starts or contacts Ollama (babble only) |
| `--frames N` | Exit after N frames (smoke test, unthrottled) |
| `--seconds S` | Exit after S wall-clock seconds (bench) |
| `--eyes toggle` | Opens/closes the eyes of the running instance and exits (exits 1 with a message if none is running) |
| `--fake-perception` | Bench: scripted machine instead of the real one |

Example with an experimental mind: `python -m engrama --recipe curious-v1 --data-dir ~/engrama-curious`.

### Rest and performance

- **Rest:** manual (F3) or automatic (fullscreen app, low free RAM or 30 min without use). While resting the window drops to 2 FPS, the mind runs at a reduced rate and the LLM is unloaded. Unfocused: 5 FPS; focused: 20 FPS while something moves and 10 FPS when the creature is still.
- **Heavy PC:** CPU above 85% for 2 min makes the creature rest until it eases.
- **Budget:** the app aims for at most 150 MB of RAM and 2% average CPU (measured by the bench).

### Creature initiative

Rare and per stage: a child brings up the current topic, an adult gives an opinion, perfect/final revisit something old; comments about PC activity share the same quota (about one per hour of active use). Never while resting, in fullscreen, with eyes closed, on a private app or without the LLM ready. Digital-world requests: at most one every 2 h; answering within 30 min makes it happy.

### Where the data lives

The data folder is, in this order: `--data-dir`; the `ENGRAMA_DATA_DIR` variable; in a repository checkout (development mode), the `data/` at the root; otherwise the OS folder:

- Windows: `%APPDATA%\Engrama`
- Linux: `$XDG_DATA_HOME/engrama` (default `~/.local/share/engrama`)

On first open with an empty folder, the app creates a new creature there. If you had an old `data/` folder (from a checkout), copy its save with `engrama --migrate-from "<old folder>"`: the command copies and keeps the original folder; it moves nothing and never runs by itself. If the new folder already has a save, it refuses. With no save in the new folder but a `data/save` next to the package, the app only writes one log line suggesting the command.

| File | Contents |
|---|---|
| `config.json` | Settings |
| `save/` | Mind and body state |
| `host.json` | Creature metadata (birth, seed) |
| `explog.sqlite` | Experience log |
| `memory.sqlite` | Conversation memory (facts, topics, opinions, episodes, vectors) |
| `actions.json` | Pending reminders and the running focus session |
| `generations.json`, `generations/<n>/` | Record of the lives and each one's archive (memory + save) |

Memory caps: 2000 episodes, 300 facts, 300 topics; old, unimportant episodes are compacted (on open and every 6 h).

### Shortcut and autostart

- `engrama --install-desktop` creates the shortcut: on Linux, `~/.local/share/applications/engrama.desktop` with the icon (it shows in the applications menu); on Windows, `Engrama.lnk` in the Start menu. `engrama --uninstall-desktop` removes only what it wrote.
- **Start with the system** is optional and off by default. Turn it on in **F6** (Settings). Linux: `~/.config/autostart/engrama.desktop`; Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. The screen reads the state from the system itself, so it cannot disagree with what is written.
- In a development checkout (running from the repository) none of this is installed, and the F6 option shows as unavailable, with the explanation.

## Linux: what each session offers

What the session does not offer stays inert, without error. Nothing changed on Windows.

| Session | Focused app, title, fullscreen | Idle time | Eyes hotkey | Overlay (F11) |
|---|---|---|---|---|
| X11 (any EWMH window manager) | yes | yes (XScreenSaver) | yes, global (`ctrl+alt+e`) | yes |
| Wayland: Hyprland | yes (Hyprland IPC) | yes (`ext-idle-notify`) | `engrama --eyes toggle` command | yes (native Wayland + Hyprland rules) |
| Wayland: Sway | yes (Sway IPC) | yes (`ext-idle-notify`) | `engrama --eyes toggle` command | no (notice on F11) |
| Wayland: KDE (Plasma 6) | no | yes (`ext-idle-notify` or DBus) | `engrama --eyes toggle` command | no (notice on F11) |
| Wayland: GNOME | no | yes (Mutter DBus) | `engrama --eyes toggle` command | no (notice on F11) |

- A Wayland session never uses X11: even with `DISPLAY` set (XWayland), perception and overlay do not query X.
- Engrama never edits the compositor configuration. Bind `engrama --eyes toggle` to a shortcut of yours. Since the app usually runs from the virtual environment, use the full path (or `python -m engrama --eyes toggle` from the repository folder; without `--data-dir`, both use the default data folder):
  - Hyprland (`~/.config/hypr/hyprland.conf`): `bind = CTRL ALT, E, exec, /path/to/engrama/.venv/bin/engrama --eyes toggle`
  - Sway (`~/.config/sway/config`): `bindsym ctrl+alt+e exec /path/to/engrama/.venv/bin/engrama --eyes toggle`
  - KDE: System Settings > Shortcuts > Add command, with the same command.
  - GNOME: Settings > Keyboard > Custom shortcuts, with the same command.
- On the other Wayland compositors (Sway, KDE, GNOME), F11 shows "the overlay only works on Hyprland under Wayland (for now)" and stays in the terrarium.
- **Overlay on Hyprland (M17):** the app uses SDL's native Wayland window (on Hyprland it picks `SDL_VIDEODRIVER=wayland` itself when you set nothing). Transparency comes from an OpenGL surface with alpha; position and flags come from Hyprland: when the overlay turns on, Engrama registers, in the running session, rules for the window with class `engrama-overlay` (floating, pinned, no border, shadow, blur or animation, no initial focus) and moves it with `hyprctl dispatch`. Nothing is written to your config files; the rules go away on the next `hyprctl reload` (turning the overlay on again recreates them). It works with the Lua syntax (Hyprland 0.5x) and the old one. SDL2 cannot let clicks fall through transparent pixels on Wayland, so the window stays tight around the body and only grows for bubbles, menu, chat and panels.

## Demo script (5 minutes)

To present without waiting days of life, use a data folder just for the demo. There are two ways:

```
engrama --data-dir demo --seed 5 --time-scale 300          # from the egg: hatches at once, a child in about 7 min
```

```
# from source: an adult already raised (12 simulated days in about 20 s), opened at normal speed
python -m engrama.lab sim --recipe engrama/recipes/default-v1.toml --days 12 --profile attentive --seed 5 --save demo-adult/save
python -m engrama --data-dir demo-adult
```

The second one opens an adult of the companion branch, hungry and wanting affection: good for showing care. It is worth having both folders ready.

1. **Egg and name:** click the egg until it hatches and name the creature. Show the nest, the sky at the real hour and the toolbar.
2. **Care:** petting (hearts), food (apple), the need icon that goes away. The home grows with the creature: a bowl for the baby, a ball for the child, a bed for the adult, a plant later.
3. **Mind:** open the Mind View (brain): modules, the tick's proposals and the winner, live.
4. **Actions:** in the clock panel, turn on Reminders and Focus; type `remind me in 30 seconds to test` and `focus for 1 min` in the chat.
5. **Privacy:** the eye panel (everything off by default) and Memories (see and delete).
6. **Voice:** with Ollama installed it talks; without it, it babbles, and the Models screen explains what to do.

The time scale also speeds up needs and sickness: keep `--time-scale` at 1 when you are not showing growth.
