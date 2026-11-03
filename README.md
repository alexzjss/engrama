# Engrama

**PT** | [EN](#en)

## O que é

Engrama é um companheiro virtual local e offline, no estilo tamagotchi: uma criatura com necessidades, humor, personalidade e gostos próprios que mora no seu computador. Nada sai da máquina.

### Arquitetura: corpo, mente, laboratório

- **Corpo** (`engrama/kernel`): núcleo determinístico. Necessidades, estágios, ações e recompensas. Mesma semente, mesmo resultado; uma simulação completa também é determinística, pois o laboratório não rebaixa módulos por tempo real (ver `--enforce-budgets`).
- **Mente** (`engrama/mind`, `engrama/modules`): módulos trocáveis (drives, SNN temporal, afeto PAD, traços, preferências, políticas) que escrevem em um quadro-negro e propõem ações; um árbitro softmax escolhe.
- **Laboratório** (`engrama/lab`): runtime de simulação, log de experiência (SQLite), replay, métricas e CLI.

### Receitas

Uma receita TOML em `recipes/` escolhe quais módulos formam a mente e seus pesos. `minimal-v1.toml` e `default-v1.toml` são os exemplos. `--recipe` aceita um nome (`--recipe thompson-v1` lê `recipes/thompson-v1.toml`) ou um caminho; um nome inexistente sai com código 2. A receita só vale para uma criatura nova (pasta de dados nova), acompanha as gerações dela e é ignorada quando a pasta já tem um save (o app registra um aviso no log; a interface não muda).

### Instalar

Python 3.13 ou mais novo.

```
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate          # Linux (bash/zsh); no fish: source .venv/bin/activate.fish
pip install -e .[dev]   # pygame-ce, numpy e psutil
```

### O app (M3)

```
pip install -e .[dev]
python -m engrama                     # ou o comando `engrama`
python -m engrama --dev --time-scale 60 --seed 1
python -m engrama --no-llm --frames 600     # sem Ollama; encerra após 600 quadros (smoke test)
```

Flags: `--data-dir`, `--recipe` (nome ou caminho; só vale em pasta de dados nova), `--seed`, `--time-scale`, `--dev` (mostra números e escala de tempo), `--no-llm`, `--frames N`, `--seconds S`, `--eyes toggle` (alterna os olhos da instância aberta e sai).

- **Pré-requisito da conversa:** Ollama em `E:\Ollama` (`ollama.exe`, `home`, `models`; os caminhos vêm de `Config`). O Engrama inicia o `ollama serve` sozinho, em segundo plano, com tudo apontado para o E:, e o encerra ao sair se foi ele quem o iniciou. O modelo padrão é `qwen3:1.7b`; baixe pelo menu de modelos (F5). O modelo só fica carregado durante e logo após a conversa (`keep_alive` de 600 s).
- **Teclas:** F2 Visão da Mente, F3 descanso manual, F4 comidas, F5 modelos e busca por significado, F6 configurações, F7 Memórias, F12 modo dev (números, `PgUp`/`PgDn` mudam a escala de tempo), Esc fecha o painel. Enter envia a mensagem.
- **Descanso:** manual (F3) ou automático (app em tela cheia, pouca RAM livre ou 30 min sem uso). Em descanso a janela cai para 2 FPS, a mente roda em ritmo reduzido e o LLM é descarregado. Sem foco a janela usa 5 FPS; com foco, 20 FPS.
- **Visão da Mente (F2):** o grafo da receita, as propostas do tick (a vencedora destacada), o custo em ms de cada módulo e as visualizações de cada um, como o raster de disparos e a surpresa da SNN. Só aqui e no modo dev aparecem números.
- **Dados:** em `Config.data_dir` (padrão `data/`, no drive do repositório): `config.json`, `save/` (estado da mente e do corpo), `host.json`, `explog.sqlite` (log de experiência) e `memory.sqlite` (memória da conversa). Nada vai para o C:.
- **Sem o LLM:** tudo funciona. Se o Ollama estiver ausente, parado ou sem o modelo, a UI mostra o estado ("Ollama não encontrado", "baixando modelo") e a conversa vira balbucio; a criatura segue viva. O LLM só produz fala, nunca escolhe ações.

### Memória viva (M4)

- **O que ela guarda:** fatos sobre você, assuntos (atuais e passados), opiniões próprias e reflexões depois das conversas. Tudo em `memory.sqlite`, com os tetos de 2000 episódios, 300 fatos e 300 assuntos. Episódios antigos e pouco importantes são compactados (`forget()` roda ao abrir e a cada 6 h).
- **Opiniões:** a posição vem de uma inclinação inata (semente + traços) e da experiência dela, nunca do que você gosta. O LLM só escreve a frase. Ela pode discordar de você.
- **Reflexão:** depois de uma conversa que esfriou, um job de baixa prioridade resume o que foi dito. Nunca carrega o LLM: só roda com o modelo já pronto e a máquina livre.
- **Iniciativa:** rara e por estágio (criança puxa o assunto atual, adulto opina, perfeito/final retoma algo antigo). Cota de cerca de um comentário por hora de uso ativo; nunca em descanso, em tela cheia ou sem o LLM pronto.
- **Painel Memórias (F7):** lista fatos, assuntos, opiniões e reflexões. Apague um item (Enter ou o x) ou "esquecer tudo" (pede confirmação em etapas).
- **Privacidade:** tudo fica local, no seu disco. Apagar é definitivo: o item sai do banco, dos episódios que o citam e da memória de curto prazo, e só volta se você mencionar de novo.

### Percepção do PC (M5)

- **Só com permissão:** na primeira execução uma tela pergunta, fonte por fonte, o que ela pode olhar (app em foco, título da janela, ociosidade, horário, tela cheia e carga do PC). Tudo começa desligado; "agora não" é uma resposta válida. O painel **Permissões (F8)** muda isso a qualquer momento, além do intervalo de leitura (15, 30 ou 60 s).
- **Olhos fechados (F9 ou atalho global, padrão Ctrl+Alt+E):** pausa toda a percepção, mesmo com a janela sem foco. O estado é salvo e aparece na tela ("olhos fechados" e pálpebras). Se o atalho estiver ocupado, o painel F8 avisa.
- **Lista de bloqueio:** apps e títulos com termos como banco, senha ou gerenciador de senhas já vêm bloqueados; você adiciona os seus no F8. Um app bloqueado chega como `privado`: nem o nome nem o título saem do serviço.
- **O que é guardado:** só a categoria do app (jogo, música, programação...) e, quando dá, um tema curto tirado do título (por exemplo o nome do jogo), na memória com origem `percepcao`. Apagar esse assunto no F7 o silencia (e o F8 deixa desfazer).
- **O que nunca é guardado:** título cru, caminho de arquivo, conteúdo de arquivo e nome de processo bloqueado. Nada sai do PC.
- **Comentários de atividade:** um novo tipo de iniciativa que divide a cota do M4 (cerca de um por hora de uso ativo). Nunca em app privado, em tela cheia ou de olhos fechados.
- **PC pesado:** CPU acima de 85% por 2 min faz a criatura descansar até aliviar.
- **Arrastar arquivo:** solte um arquivo ou pasta na janela e ela comenta. Lê só os primeiros 8 KB de texto/código; pasta lista o primeiro nível; imagem dá só nome e tipo; arquivo bloqueado é recusado.

### Vida longa (M6)

- **Ramos:** ao evoluir (criança, jovem), a criatura escolhe um ramo conforme o cuidado recebido, a personalidade e os interesses; o nome do ramo aparece na tela. A linhagem de ramos fica registrada.
- **Doença e remédio:** descuido prolongado ou um resfriado ocasional deixam a criatura doente (sinal visível na tela). O remédio cura; doença grave sem tratamento leva à morte. Nada disso corre enquanto o app está fechado.
- **Velhice:** no fim do ciclo a criatura fica velha. Velhice só acaba em morte com o app aberto e a criatura calma (acordada, sem tela cheia, sem conversa recente).
- **Morte e herança:** a criatura se despede (texto do LLM, ou balbucio se estiver offline; clique para pular). Depois de 10 s, e nunca em tela cheia, a memória da vida é arquivada em `data/generations/<n>/` (com cópia do save), a vida vira um registro em `data/generations.json` e nasce um ovo novo. O ovo herda parte da personalidade e até 3 lembranças ancestrais (sem números e sem nada bloqueado); fatos, assuntos e opiniões do usuário não passam. Configurações, permissões e lista de bloqueio continuam.
- **Gerações (F10):** lista as vidas passadas (ramo, duração, causa) e deixa apagar o arquivo de uma geração; o registro permanece.

### Presença (M7)

- **Modo sobreposição (F11):** a criatura sai do terrário e passa a andar sobre a barra de tarefas, numa janela sem borda e transparente (Windows). F11 alterna entre os dois modos; a escolha é salva e o app reabre no último modo. Se o sistema não oferece o modo, o app avisa e fica no terrário.
- **Mini-menu:** clique nela para abrir Comida, Remédio (oculto no ovo), Digital, Conversar (caixa de chat pequena acima dela) e Terrário (volta ao modo normal). Em tela cheia ela se esconde até acabar.
- **Mundo digital (F1):** itens de manutenção de brincadeira (RAM fresquinha, desfragmentar, instalar atualização, limpar cache, soprar o cooler). De vez em quando, ao pedir atenção, a criatura pede um deles em voz alta e mostra o ícone num balão; atender dentro de 30 min a deixa feliz. No máximo um pedido a cada 2 h. É só jogo: nada é feito no seu PC.
- **Variantes:** a mesma ação ganha jeitos diferentes (pular, dançar, bocejar, cavar e achar algo, tirar um cochilo olhando o relógio) conforme humor e personalidade.
- **Privacidade do cursor:** só a posição do cursor, só no modo sobreposição, lida poucas vezes por segundo e nunca guardada nem registrada. A criatura pode virar para o cursor ou persegui-lo. A janela ativa só é consultada (para espiar a borda dela) se a permissão "Título da janela" do F8 estiver ligada.

### Linux (M8)

O Engrama roda no Linux com o que cada sessão permite; o que a sessão não oferece fica inerte, sem erro. No Windows nada mudou.

| Sessão | App em foco, título, tela cheia | Ociosidade | Atalho dos olhos | Overlay (F11) |
|---|---|---|---|---|
| X11 (qualquer gerenciador EWMH) | sim | sim (XScreenSaver) | sim, global (`ctrl+alt+e`) | sim |
| Wayland: Hyprland | sim (IPC do Hyprland) | sim (`ext-idle-notify`) | comando `engrama --eyes toggle` | não (aviso no F11) |
| Wayland: Sway | sim (IPC do Sway) | sim (`ext-idle-notify`) | comando `engrama --eyes toggle` | não (aviso no F11) |
| Wayland: KDE (Plasma 6) | não | sim (`ext-idle-notify` ou DBus) | comando `engrama --eyes toggle` | não (aviso no F11) |
| Wayland: GNOME | não | sim (DBus do Mutter) | comando `engrama --eyes toggle` | não (aviso no F11) |

- **Ollama do sistema:** usa o `ollama` do `PATH` (em geral o serviço systemd); não mexe em `HOME` nem em `OLLAMA_MODELS`. Se não estiver rodando e o binário existir, o Engrama inicia `ollama serve` e o encerra ao sair. Os caminhos `E:\` de um `config.json` vindo do Windows são ignorados no Linux.
- **Sessão Wayland nunca usa X11:** mesmo com `DISPLAY` presente (XWayland), a percepção e o overlay não consultam o X.
- **Olhos por comando:** `engrama --eyes toggle` abre ou fecha os olhos da instância aberta (sai com 1 e avisa se não houver nenhuma). O Engrama nunca mexe na configuração do compositor; você liga o comando a um atalho dele. Como o app costuma rodar do ambiente virtual, use o caminho completo (ou `python -m engrama --eyes toggle` a partir da pasta do repositório; sem `--data-dir`, os dois usam o `data/` do repositório):
  - Hyprland (`~/.config/hypr/hyprland.conf`): `bind = CTRL ALT, E, exec, /caminho/do/engrama/.venv/bin/engrama --eyes toggle`
  - Sway (`~/.config/sway/config`): `bindsym ctrl+alt+e exec /caminho/do/engrama/.venv/bin/engrama --eyes toggle`
  - KDE: Configurações do Sistema > Atalhos > Adicionar comando, com o mesmo comando.
  - GNOME: Configurações > Teclado > Atalhos personalizados, com o mesmo comando.
- **Overlay só no X11.** Em sessão Wayland o F11 mostra "o overlay ainda não funciona no Wayland" e fica no terrário.
- **Privacidade igual à do Windows (M5):** nada de `/dev/input`, teclado, tela ou área de transferência; título e nome de processo nunca saem do serviço de percepção.

### Busca por significado (M9)

- **O que é:** com um modelo de embedding, a criatura lembra pelo sentido e não só por palavras iguais: "meu bichinho anda doente" traz o cachorro que você contou dias antes, e "my dog is sick" traz a lembrança escrita em português. Vale para fatos, episódios, assuntos de opinião e lembranças ancestrais.
- **É opcional:** sem o modelo (não instalado, Ollama parado, `--no-llm`, busca desligada) tudo funciona exatamente como no M8, por palavras. Nada de erro, nada de espera: a consulta tem tempo limite de 1 s e cai para palavras.
- **Como ligar:** no menu de modelos (F5), a linha "Busca por significado" baixa o `embeddinggemma` (cerca de 0,6 GB de RAM no Ollama enquanto carregado; o disco leva algumas centenas de MB). Ou, no terminal, `ollama pull embeddinggemma`. A mesma linha liga, desliga e troca o modelo (`embeddinggemma`, `nomic-embed-text` ou `bge-m3`). O Engrama nunca baixa o modelo sozinho.
- **Quando roda:** o modelo de embedding só é usado com o modelo de conversa já pronto e a máquina livre (nunca em descanso), e nunca na thread da interface. Os vetores são feitos em segundo plano, em lotes pequenos. Ele nunca carrega modelo sozinho.
- **F7 e F2:** o painel Memórias mostra "lembra pelo sentido" ou "lembra só por palavras"; a Visão da Mente mostra quantas memórias já têm vetor e o estado do modelo.
- **Privacidade:** os vetores ficam na `memory.sqlite`, no seu disco, e saem só de textos que ela já guarda (nada novo é coletado). Apagar uma memória (fato, assunto, "esquecer tudo", teto, compactação ou nova geração) apaga o vetor dela junto. Desligar a busca ou trocar de modelo apaga todos os vetores. O arquivo de uma geração (`data/generations/<n>/memory.sqlite`) não leva vetores.
- **Teclas:** F5 agora também controla a busca por significado.

### Laboratório

```
python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --profile gamer --seed 1 --log data/run.db
python -m engrama.lab report --log data/run.db
python -m engrama.lab compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10
python -m engrama.lab replay --log data/run.db --module temporal.snn --param readout_hidden=false
python -m engrama.lab suite --recipes default-v1 thompson-v1 --profiles attentive --seeds 1 --days 1 --out suite.json --md suite.md
python -m engrama.lab suite --preset m10 --jobs 4 --out suite.json --md tabela.md   # 8 receitas x 4 perfis x 3 sementes
```

`suite` roda receitas x perfis x sementes (nomes de receita valem como em `--recipe`), grava o JSON (corridas e resumo pareado contra `--baseline`, padrão `default-v1`) e a tabela em Markdown; `--jobs N` usa N processos e não muda o resultado. O `--preset m10` leva cerca de 5 min com `--jobs 4` (medido em 8 núcleos).

Perfis (`--profile`): `attentive`, `absent`, `night_owl`, `gamer`. Outras flags: `--dt` (passo em segundos simulados, padrão 60), `--save DIR` (salva o estado ao fim do `sim`), `--run ID` (escolhe a execução dentro de um log, em `report` e `replay`), `--seed` (também em `replay`), `--enforce-budgets` (rebaixa módulos lentos pelo relógio de parede; não determinístico, desligado por padrão). Cada `sim --log` cria uma execução com `run_id` único (uuid4), impresso nas métricas junto com o nome e a versão da receita; rodar de novo no mesmo log não mistura linhas.

### Experimentos de ML (M10)

Quatro ideias de aprendizado de máquina entram como **receitas opcionais**, para medir no laboratório e, se você quiser, rodar no app. **São opt-in e o padrão não mudou**: `default-v1` é o mesmo do M9 (mesmos gabaritos) e nenhum experimento foi promovido a padrão.

- **CTRNN** (`temporal.ctrnn`): rede recorrente de tempo contínuo, com constantes de tempo de 1 min a 1 dia, que prevê o próximo evento no lugar da SNN.
- **Modelo de mundo + curiosidade** (`world.model`, `policy.curious`): um modelo prevê as consequências das ações; o erro dele vira bônus intrínseco no Q-learning (por erro bruto ou por progresso de aprendizado).
- **Thompson** (`policy.thompson`): Q-learning bayesiano simplificado; a incerteza de cada par estado-ação vira exploração.
- **Inferência ativa** (`policy.aif`): escolhe a ação de menor energia livre esperada (resultado preferido mais novidade), sem sorteio próprio.

| Receita | O que troca em relação a `default-v1` |
|---|---|
| `ctrnn-v1` | SNN temporal por CTRNN |
| `shadow-ctrnn-v1` | CTRNN só em sombra (ações iguais às do padrão; dá o Brier próprio da CTRNN) |
| `curious-v1` | Q-learning por Q curioso + modelo de mundo (bônus por erro) |
| `curious-lp-v1` | o mesmo, com bônus por progresso de aprendizado |
| `thompson-v1` | Q-learning por Thompson |
| `aif-v1` | Q-learning somado à inferência ativa |
| `aif-solo-v1` | inferência ativa no lugar da utilidade e do Q-learning (linha exploratória) |
| `lab-shadow-all-v1` | padrão ao vivo, com CTRNN, Thompson, inferência ativa e modelo de mundo em sombra |

Resumo do relatório (3 sementes × `attentive`/`absent`/`neglectful` × 7 dias, mais `routine` × 4 dias): nenhuma receita supera o padrão de forma consistente e relevante, e todas cabem no orçamento; a recomendação é **não promover** nenhuma. Veja o [relatório de comparação](docs/superpowers/reports/2026-11-08-m10-experimentos.md). Para rodar um experimento no app, use uma pasta de dados **nova**: `python -m engrama --recipe curious-v1 --data-dir ~/engrama-curious`.

### O que a SNN comprova (e o que não)

- Comprovado: em um usuário periódico roteirizado, a SNN prevê o próximo evento melhor que uma leitura só com viés (Brier 4,0% a 5,1% menor nas sementes 1, 2 e 3; o teste exige pelo menos 2% em cada uma).
- O sinal de novidade e a habituação vêm principalmente da taxa-base de cada tipo de evento, não da rede de disparos (a ablação só com viés dá a mesma razão raro/comum).
- `minimal` contra `default` é uma diferença de receita (SNN, Q-learning, preferências e traços juntos), não um efeito só da SNN.
- A SNN avança em compassos fixos de 60 s de tempo simulado, então o resultado não depende do `--dt`.

### Escrever um módulo

1. Subclasse `engrama.mind.contracts.Module`: declare `reads`, `writes`, `rate_hz`; implemente `step(bb, dt)`, `propose(bb)`, `learn(exp)`, `state_dict`/`load_state_dict` (o `state_dict` leva um `version` inteiro; `load_state_dict({})` volta ao estado inicial e versão maior levanta `ValueError`).
2. Registre em `engrama/mind/registry.py` (`REGISTRY["familia.nome"] = "pacote.arquivo:Classe"`).
3. Adicione a uma receita como `[[module]]` (vivo, com `weight`) ou `[[shadow]]` (roda e é registrado, mas não decide; útil para comparar).
4. Opcional: `lab_metrics()` devolve um dict de números do módulo; a suíte do laboratório os agrega por corrida.

Regra de dependência (verificada por `tests/test_architecture.py`): `kernel` não importa `mind`, `modules`, `lab` nem `services`; `mind` não importa `kernel` nem `modules`; um módulo só importa `engrama.mind`, `engrama.vocab`, `engrama.balance`, a própria família, numpy e a stdlib.

### Testes e bench

```
python -m pytest -q                      # inclui testes lentos (marcador slow)
python tools/bench.py --seconds 120      # (--profile, --seed) JSON: pico de RSS, CPU médio, mean_ms por módulo
python tools/bench.py --app --seconds 60 --fake-perception   # o app inteiro com fontes de percepção falsas
python tools/bench.py --app --seconds 60 --threads           # CPU por thread (Linux, via /proc)
python tools/bench.py --app --seconds 60 --first-use         # mede a tela de primeiro uso, à parte
python tools/bench.py --overlay --seconds 30                 # overlay com desktop e cursor falsos
```

O bench mede o estado estável por padrão (primeiro uso já respondido, todas as permissões desligadas); o limite é de 150 MB e 2% de CPU médio, em qualquer plataforma.

### Onde ficam os arquivos

A CLI do laboratório usa os caminhos explícitos `--log` e `--save` (não lê `Config`); o padrão sugerido nos exemplos é `data/`, ignorado pelo git. `Config.data_dir` (padrão: `data/` na raiz do repositório) é o diretório de dados do app. Com o repositório no drive E:, nada vai para o C:. No Linux a pasta de dados é a mesma, `data/` na raiz do repositório (sem XDG, sem migração); `--data-dir` continua valendo.

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

A TOML recipe in `recipes/` chooses which modules make up a mind and their weights. See `minimal-v1.toml` and `default-v1.toml`. `--recipe` takes a name (`--recipe thompson-v1` reads `recipes/thompson-v1.toml`) or a path; an unknown name exits with code 2. The recipe only applies to a new creature (a fresh data dir), follows its generations and is ignored when the dir already has a save (the app logs a warning; the UI does not change).

### Install

Python 3.13 or newer.

```
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate          # Linux (bash/zsh); on fish: source .venv/bin/activate.fish
pip install -e .[dev]   # pygame-ce, numpy and psutil
```

### The app (M3)

```
pip install -e .[dev]
python -m engrama                     # or the `engrama` command
python -m engrama --dev --time-scale 60 --seed 1
python -m engrama --no-llm --frames 600     # no Ollama; exits after 600 frames (smoke test)
```

Flags: `--data-dir`, `--recipe` (name or path; only applies to a fresh data dir), `--seed`, `--time-scale`, `--dev` (shows numbers and the time scale), `--no-llm`, `--frames N`, `--seconds S`, `--eyes toggle` (toggles the running instance's eyes and exits).

- **Chat prerequisite:** Ollama in `E:\Ollama` (`ollama.exe`, `home`, `models`; paths come from `Config`). Engrama starts `ollama serve` itself, in the background, with everything pointed at E:, and stops it on exit if it started it. The default model is `qwen3:1.7b`; download it from the models menu (F5). The model stays loaded only during and shortly after a conversation (`keep_alive` 600 s).
- **Keys:** F2 Mind View, F3 manual rest, F4 foods, F5 models and recall by meaning, F6 settings, F7 Memories, F12 dev mode (numbers; `PgUp`/`PgDn` change the time scale), Esc closes the panel. Enter sends the message.
- **Rest:** manual (F3) or automatic (a fullscreen app, low free RAM, or 30 min without input). While resting the window drops to 2 FPS, the mind runs at a reduced rate and the LLM is unloaded. Unfocused the window runs at 5 FPS; focused, 20 FPS.
- **Mind View (F2):** the recipe graph, the tick's proposals (winner highlighted), each module's cost in ms and each module's visualisations, such as the SNN spike raster and surprise. Numbers appear only here and in dev mode.
- **Data:** in `Config.data_dir` (default `data/`, on the repo's drive): `config.json`, `save/` (mind and body state), `host.json`, `explog.sqlite` (experience log) and `memory.sqlite` (chat memory). Nothing goes to C:.
- **Without the LLM:** everything works. If Ollama is missing, stopped or lacks the model, the UI shows the state ("Ollama not found", "downloading model") and chat turns into babble; the creature keeps living. The LLM only produces speech, it never picks actions.

### Living memory (M4)

- **What it keeps:** facts about you, subjects (current and past), opinions of its own and reflections after conversations. All in `memory.sqlite`, capped at 2000 episodes, 300 facts and 300 subjects. Old, low-importance episodes are compacted (`forget()` runs at start-up and every 6 h).
- **Opinions:** the position comes from an innate lean (seed + traits) and its own experience, never from what you like. The LLM only writes the phrase. It can disagree with you.
- **Reflection:** after a conversation goes quiet, a low-priority job summarises what was said. It never loads the LLM: it runs only with the model already ready and the machine idle.
- **Initiative:** rare and stage-gated (child brings up the current subject, adult gives an opinion, perfect/final revisits something old). A quota of about one remark per hour of active use; never while resting, in fullscreen or without the LLM ready.
- **Memories panel (F7):** lists facts, subjects, opinions and reflections. Delete one item (Enter or the x) or "forget everything" (asks for confirmation in steps).
- **Privacy:** everything stays local, on your disk. Deleting is final: the item leaves the database, the episodes that mention it and the short-term memory, and only returns if you mention it again.

### PC perception (M5)

- **Only with permission:** on first run a screen asks, source by source, what it may look at (focused app, window title, idleness, time, fullscreen and PC load). Everything starts off; "not now" is a valid answer. The **Permissions panel (F8)** changes this at any time, plus the read interval (15, 30 or 60 s).
- **Eyes closed (F9 or the global hotkey, default Ctrl+Alt+E):** pauses all perception, even when the window is unfocused. The state is saved and shown on screen ("eyes closed" and lids). If the hotkey is taken, F8 says so.
- **Block list:** apps and titles with terms like bank, password or a password manager are blocked from the start; you add your own in F8. A blocked app arrives as `privado`: neither its name nor its title leaves the service.
- **What is kept:** only the app category (game, music, programming...) and, when possible, a short theme from the title (such as a game name), in memory with source `percepcao`. Deleting that subject in F7 silences it (F8 lets you undo).
- **What is never kept:** raw titles, file paths, file contents and blocked process names. Nothing leaves the PC.
- **Activity remarks:** a new kind of initiative sharing the M4 quota (about one per hour of active use). Never on a private app, in fullscreen or with eyes closed.
- **Heavy PC:** CPU above 85% for 2 min makes the creature rest until it eases.
- **Drag a file:** drop a file or folder on the window and it comments. It reads only the first 8 KB of text/code; a folder lists its first level; an image gives just name and type; a blocked file is refused.

### Long life (M6)

- **Branches:** on evolving (child, young), the creature picks a branch from the care it received, its personality and its interests; the branch name shows on screen. The branch lineage is recorded.
- **Illness and medicine:** prolonged neglect or an occasional cold makes the creature sick (a visible sign on screen). Medicine cures it; severe untreated illness leads to death. None of this runs while the app is closed.
- **Old age:** at the end of the cycle the creature turns old. Old age only ends in death while the app is open and the creature is calm (awake, not in fullscreen, no recent chat).
- **Death and inheritance:** the creature says goodbye (LLM text, or babble when offline; click to skip). After 10 s, and never in fullscreen, the life's memory is archived in `data/generations/<n>/` (with a save copy), the life becomes a record in `data/generations.json` and a new egg is born. The egg inherits part of the personality and up to 3 ancestral memories (no digits, nothing blocked); the user's facts, topics and opinions do not carry over. Settings, permissions and the block list stay.
- **Generations (F10):** lists past lives (branch, length, cause) and lets you delete a generation's archive; the record stays.

### Presence (M7)

- **Overlay mode (F11):** the creature leaves the terrarium and walks along the taskbar in a borderless, transparent window (Windows). F11 toggles between the two modes; the choice is saved and the app reopens in the last mode. If the system does not offer the mode, the app says so and stays in the terrarium.
- **Mini-menu:** click the creature to open Food, Medicine (hidden for the egg), Digital, Talk (a small chat box above it) and Terrarium (back to normal mode). In fullscreen it hides until you are done.
- **Digital world (F1):** joke maintenance items (fresh RAM, defragment, install update, clear cache, blow the cooler). Now and then, when asking for attention, the creature asks for one out loud and shows its icon in a bubble; answering within 30 min makes it happy. At most one request every 2 h. It is only a game: nothing is done to your PC.
- **Variants:** the same action looks different (jump, dance, yawn, dig and find something, nap while watching the clock) depending on mood and personality.
- **Cursor privacy:** only the cursor position, only in overlay mode, read a few times per second and never stored or logged. The creature may turn toward the cursor or chase it. The active window is queried (to peek at its edge) only if the F8 "Window title" permission is on.

### Linux (M8)

Engrama runs on Linux with whatever each session allows; anything the session does not offer stays inert, without errors. Nothing changed on Windows.

| Session | Focused app, title, fullscreen | Idle | Eyes hotkey | Overlay (F11) |
|---|---|---|---|---|
| X11 (any EWMH window manager) | yes | yes (XScreenSaver) | yes, global (`ctrl+alt+e`) | yes |
| Wayland: Hyprland | yes (Hyprland IPC) | yes (`ext-idle-notify`) | `engrama --eyes toggle` command | no (notice on F11) |
| Wayland: Sway | yes (Sway IPC) | yes (`ext-idle-notify`) | `engrama --eyes toggle` command | no (notice on F11) |
| Wayland: KDE (Plasma 6) | no | yes (`ext-idle-notify` or DBus) | `engrama --eyes toggle` command | no (notice on F11) |
| Wayland: GNOME | no | yes (Mutter DBus) | `engrama --eyes toggle` command | no (notice on F11) |

- **System Ollama:** uses the `ollama` on your `PATH` (usually the systemd service); it does not touch `HOME` or `OLLAMA_MODELS`. If it is not running and the binary exists, Engrama starts `ollama serve` and stops it on exit. `E:\` paths in a `config.json` carried over from Windows are ignored on Linux.
- **A Wayland session never uses X11:** even with `DISPLAY` set (XWayland), perception and the overlay do not query X.
- **Eyes by command:** `engrama --eyes toggle` opens or closes the running instance's eyes (exit code 1 with a message if none is running). Engrama never edits your compositor config; you bind the command to a key there. Since the app usually runs from the virtual environment, use the full path (or `python -m engrama --eyes toggle` from the repo folder; without `--data-dir` both use the repo's `data/`):
  - Hyprland (`~/.config/hypr/hyprland.conf`): `bind = CTRL ALT, E, exec, /path/to/engrama/.venv/bin/engrama --eyes toggle`
  - Sway (`~/.config/sway/config`): `bindsym ctrl+alt+e exec /path/to/engrama/.venv/bin/engrama --eyes toggle`
  - KDE: System Settings > Shortcuts > Add command, with the same command.
  - GNOME: Settings > Keyboard > Custom shortcuts, with the same command.
- **Overlay on X11 only.** On a Wayland session F11 shows "the overlay does not work on Wayland yet" and stays in the terrarium.
- **Same privacy as Windows (M5):** no `/dev/input`, keyboard, screen or clipboard; titles and process names never leave the perception service.

### Recall by meaning (M9)

- **What it is:** with an embedding model the creature remembers by meaning, not only by shared words: "my pet is sick" brings back the dog you mentioned days earlier, and "my dog is sick" brings back a memory written in Portuguese. It covers facts, episodes, opinion topics and ancestral memories.
- **Optional:** without the model (not installed, Ollama stopped, `--no-llm`, search switched off) everything works exactly as in M8, by words. No errors and no waiting: the query has a 1 s time limit and falls back to words.
- **How to enable:** in the models menu (F5), the "Recall by meaning" row downloads `embeddinggemma` (about 0.6 GB of RAM in Ollama while loaded, a few hundred MB on disk). Or, in a terminal, `ollama pull embeddinggemma`. The same row switches it on and off and changes the model (`embeddinggemma`, `nomic-embed-text` or `bge-m3`). Engrama never downloads the model by itself.
- **When it runs:** the embedding model is only used while the chat model is ready and the machine is idle (never during rest), and never on the UI thread. Vectors are built in the background, in small batches. It never loads a model on its own.
- **F7 and F2:** the Memories panel says "remembers by meaning" or "remembers by words only"; the Mind View shows how many memories already have a vector and the model state.
- **Privacy:** vectors live in `memory.sqlite`, on your disk, and come only from text it already stores (nothing new is collected). Deleting a memory (fact, topic, "forget everything", caps, compaction or a new generation) deletes its vector too. Switching the search off or changing the model deletes every vector. A generation archive (`data/generations/<n>/memory.sqlite`) carries no vectors.
- **Keys:** F5 now also controls recall by meaning.

### Lab

```
python -m engrama.lab sim --recipe recipes/default-v1.toml --days 7 --profile gamer --seed 1 --log data/run.db
python -m engrama.lab report --log data/run.db
python -m engrama.lab compare --a recipes/minimal-v1.toml --b recipes/default-v1.toml --days 10
python -m engrama.lab replay --log data/run.db --module temporal.snn --param readout_hidden=false
python -m engrama.lab suite --recipes default-v1 thompson-v1 --profiles attentive --seeds 1 --days 1 --out suite.json --md suite.md
python -m engrama.lab suite --preset m10 --jobs 4 --out suite.json --md table.md   # 8 recipes x 4 profiles x 3 seeds
```

`suite` runs recipes x profiles x seeds (recipe names work as in `--recipe`), writes the JSON (runs and a paired summary against `--baseline`, default `default-v1`) and the Markdown table; `--jobs N` uses N processes and does not change the result. `--preset m10` takes about 5 min with `--jobs 4` (measured on 8 cores).

Profiles (`--profile`): `attentive`, `absent`, `night_owl`, `gamer`. Other flags: `--dt` (step in simulated seconds, default 60), `--save DIR` (save state at the end of `sim`), `--run ID` (pick a run inside a log, for `report` and `replay`), `--seed` (also on `replay`), `--enforce-budgets` (demote slow modules by wall-clock time; not deterministic, off by default). Every `sim --log` creates a run with a unique `run_id` (uuid4), printed with the metrics together with the recipe name and version; rerunning into the same log does not mix rows.

### ML experiments (M10)

Four machine-learning ideas ship as **optional recipes**, to measure in the lab and, if you want, run in the app. **They are opt-in and the default did not change**: `default-v1` is the M9 one (same fixtures) and no experiment was promoted to default.

- **CTRNN** (`temporal.ctrnn`): a continuous-time recurrent network, with time constants from 1 min to 1 day, that predicts the next event in place of the SNN.
- **World model + curiosity** (`world.model`, `policy.curious`): a model predicts what actions lead to; its error becomes an intrinsic bonus in Q-learning (raw error or learning progress).
- **Thompson** (`policy.thompson`): a simplified Bayesian Q-learning; the uncertainty of each state-action pair drives exploration.
- **Active inference** (`policy.aif`): picks the action with the lowest expected free energy (preferred outcome plus novelty), with no RNG of its own.

| Recipe | What it swaps relative to `default-v1` |
|---|---|
| `ctrnn-v1` | temporal SNN replaced by the CTRNN |
| `shadow-ctrnn-v1` | CTRNN in shadow only (same actions as the default; gives the CTRNN's own Brier) |
| `curious-v1` | Q-learning replaced by curious Q + world model (error bonus) |
| `curious-lp-v1` | the same, with a learning-progress bonus |
| `thompson-v1` | Q-learning replaced by Thompson |
| `aif-v1` | Q-learning plus active inference |
| `aif-solo-v1` | active inference in place of utility and Q-learning (exploratory row) |
| `lab-shadow-all-v1` | the default live, with CTRNN, Thompson, active inference and the world model in shadow |

Report summary (3 seeds x `attentive`/`absent`/`neglectful` x 7 days, plus `routine` x 4 days): no recipe beats the default consistently and meaningfully, and all fit the budget; the recommendation is **not to promote** any. See the [comparison report](docs/superpowers/reports/2026-11-08-m10-experimentos.md) (in Portuguese). To try one in the app, use a **fresh** data dir: `python -m engrama --recipe curious-v1 --data-dir ~/engrama-curious`.

### What the SNN does and does not show

- Evidenced: on a scripted periodic user, the SNN predicts the next event better than a bias-only readout (Brier 4.0% to 5.1% lower on seeds 1, 2 and 3; the test requires at least 2% on each).
- The novelty signal and habituation come mostly from each event kind's base rate, not from the spiking network (the bias-only ablation gives the same rare/common ratio).
- `minimal` versus `default` is a recipe difference (SNN, Q-learning, preferences and traits together), not an SNN-only effect.
- The SNN advances on fixed 60 s sim-time bins, so its behaviour does not depend on `--dt`.

### Writing a module

1. Subclass `engrama.mind.contracts.Module`: declare `reads`, `writes`, `rate_hz`; implement `step(bb, dt)`, `propose(bb)`, `learn(exp)`, `state_dict`/`load_state_dict` (`state_dict` carries an integer `version`; `load_state_dict({})` returns to the initial state and a newer version raises `ValueError`).
2. Register it in `engrama/mind/registry.py` (`REGISTRY["family.name"] = "package.file:Class"`).
3. Add it to a recipe as `[[module]]` (live, with `weight`) or `[[shadow]]` (runs and is logged but does not decide; useful for comparisons).
4. Optional: `lab_metrics()` returns a dict of numbers for the module; the lab suite aggregates them per run.

Dependency rule (enforced by `tests/test_architecture.py`): `kernel` imports none of `mind`, `modules`, `lab`, `services`; `mind` imports neither `kernel` nor `modules`; a module may import only `engrama.mind`, `engrama.vocab`, `engrama.balance`, its own family, numpy and the stdlib.

### Tests and bench

```
python -m pytest -q                      # includes slow tests (slow marker)
python tools/bench.py --seconds 120      # JSON: peak RSS, mean CPU, per-module mean_ms
python tools/bench.py --app --seconds 60   # the whole app (dummy SDL, --no-llm): peak RSS and mean CPU
python tools/bench.py --app --seconds 60 --fake-perception   # same, with scripted perception sources
python tools/bench.py --app --seconds 60 --threads           # per-thread CPU (Linux, via /proc)
python tools/bench.py --app --seconds 60 --first-use         # measures the first-use screen separately
python tools/bench.py --overlay --seconds 30                 # overlay with a fake desktop and cursor
```

The bench measures the steady state by default (first use answered, all permissions off); the limit is 150 MB and 2% mean CPU on every platform.

### Where files live

The lab CLI takes explicit `--log` and `--save` paths (it does not read `Config`); the examples use `data/`, which is git-ignored. `Config.data_dir` (default: `data/` at the repo root) is the app's data directory. With the repo on drive E:, nothing goes to C:. On Linux the data directory is the same, `data/` at the repo root (no XDG, no migration); `--data-dir` still applies.
