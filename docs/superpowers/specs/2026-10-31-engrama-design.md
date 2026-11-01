# Engrama — Documento de Design

Data: 2026-10-31 · Status: rascunho para aprovação

Legenda: **[usuário]** = decidido pelo usuário · **[decisão de design]** = escolha do autor do design, pode ser contestada · **[construtor]** = deixado para quem implementar.

---

## 1. Intenção

Engrama é um companheiro virtual local, no espírito de Tamagotchi/Digimon: uma criatura digital que nasce de um ovo, vive numa janela do PC do usuário, tem necessidades, personalidade, memória, aprende com a convivência e evolui visivelmente. **[usuário]**

O diferencial é combinar:
- uma **SNN** (rede neural de disparos, LIF + STDP) como "sistema nervoso" — processa estímulos, gera dinâmica interna e influencia comportamento, com plasticidade real;
- um **LLM pequeno local** como "córtex de linguagem" — só interpreta e gera linguagem, pode ficar descarregado sem a criatura parar de viver. **[usuário]**

O aprendizado vive em memória, preferências, comportamento e pesos da SNN — **nunca** em fine-tuning do LLM. **[usuário]**

Tudo roda local e offline, porque a criatura percebe o que acontece no PC (privacidade). Online só quando o usuário pedir explicitamente. **[usuário]**

### Por quê
Projeto pessoal: ter um bichinho que parece vivo e único, que acompanha o dia a dia no PC (conversa sobre jogos e interesses, dá opinião, brinca sozinho quando ignorado), e ao mesmo tempo um laboratório visível de comportamento bio-inspirado (ver a SNN funcionando).

### O nome
"Engrama" = traço físico que uma memória deixa no cérebro. A criatura é literalmente feita dos traços que a convivência deixa. **[usuário]**

---

## 2. Objetivos, não-objetivos e anti-objetivos

### Objetivos
1. Criatura que **parece viva**: age por conta própria a partir de necessidades + personalidade + SNN, mesmo sem LLM.
2. **Leve**: não atrapalhar o uso do PC no hardware alvo (seção 3).
3. **Única**: todas começam iguais (ovo), mas personalidade, gostos, aparência evolutiva e memória divergem com a convivência. **[usuário]**
4. **Conversa** em português e inglês, com fala que cresce conforme o estágio (bebê → sons e palavras soltas; adulto → frases completas). **[usuário]**
5. **SNN visível** em um modo especial (raster de disparos, potenciais, pesos). **[usuário]**
6. Ciclo de vida longo (meses), com evolução visível e ramificada, doença, morte e renascimento. **[usuário]**

### Não-objetivos (por enquanto)
- Fine-tuning do LLM.
- SNN entendendo ou gerando linguagem.
- Multiusuário (é ligada a um único usuário). **[usuário]**
- Linux/macOS no v1 — mas o código deve isolar o que é específico de Windows para portar depois. **[usuário]**
- Voz falada/reconhecimento de fala (só grunhidos retrô). **[usuário]**
- Celular.

### Anti-objetivos (falhas mesmo que "funcione")
- Ficar **pesado** ou atrapalhar jogos/trabalho. **[usuário]**
- Parecer **chatbot genérico ou atendente** ("Como posso ajudar?"). **[usuário]**
- Interromper demais / ser chato.
- Vazar qualquer dado do PC para fora da máquina.

---

## 3. Restrições

- **Hardware alvo**: Asus Vivobook Go 15, Ryzen 5 (mobile), 8 GB RAM, sem GPU dedicada. **[usuário]** Máquina de desenvolvimento atual é mais forte (Ryzen 5 1600, 16 GB, GPU NVIDIA) — orçamentos devem ser medidos pensando no alvo.
- **Orçamento de recursos [decisão de design]**:
  - Núcleo (sem LLM carregado): ≤ 150 MB RAM, ≤ 2% CPU médio, janela a ≤ 20 FPS (5 FPS quando sem foco).
  - LLM carregado: ~1,5 GB extra, só durante/após conversa; descarrega após `keep_alive` (padrão 10 min).
  - **Modo descanso**: manual (tecla/menu) e automático (pressão de RAM/CPU, tela cheia, inatividade longa). Em descanso: LLM descarregado, servidor Ollama parado se foi o Engrama que o iniciou, SNN a ~1 Hz, render a 1–2 FPS ou janela minimizada. **[usuário: manual + automático]**
- **Nada instalado no disco C**: Ollama em `E:\Ollama`, modelos em `E:\Ollama\models`, dados do app numa pasta configurável (padrão: `<repo>/data` ou `E:\Engrama\data`). O app de bandeja do Ollama não é usado (escreve logs no C); o Engrama inicia `ollama serve` com `USERPROFILE/HOME/OLLAMA_MODELS` apontando para E:. **[usuário]**
- **Python 3.13**, pygame-ce, numpy. **[usuário: Python]** Dependências extras devem ser leves e puras ou com wheels prontas para Windows.
- **Windows primeiro**.
- **Commits sem coautor do Claude**; fluxo via PR com merge na `main` do repositório `alexzjss/engrama`. **[usuário]**

---

## 4. Arquitetura geral

Processo único, loop principal leve + threads de fundo. **[decisão de design]**

```
                ┌────────────── Perception (thread, periódica, com permissões)
                │                 janela ativa, processo, horário, ociosidade, tela cheia
                ▼
 Eventos ──► Stimulus Bus ──► SNN (LIF+STDP) ──► sinais neurais (taxas por grupo, arousal, valência)
 (usuário,                         │
  tempo,                           ▼
  percepção)               Behavior Engine (utility AI + bandits)  ◄── Needs, Traits, Prefs, Memory
                                   │
                    ┌──────────────┼───────────────────┐
                    ▼              ▼                   ▼
               Animação/UI     Language (LLM)      Learning System
               (pygame)        thread + Ollama     (recompensas → bandits, traços, gostos, SNN modula)
                                   │
                                   ▼
                              Memory (SQLite)  ──► Evolution System (estágios, ramos, vida/morte)
```

### Ticks [decisão de design]
- **Render**: 15–20 FPS (5 sem foco).
- **Simulação** (necessidades, comportamento): 1 Hz.
- **SNN**: roda em lotes de passos de 1 ms simulados a cada tick de simulação (ex.: 50 passos/tick); em descanso, 1 lote a cada vários segundos.
- **Percepção**: a cada 30–60 s (configurável), nunca captura de tela no v1.
- **Tempo de vida**: relógio de jogo em tempo real; tempo com o app fechado é contabilizado ao reabrir (seção 6.6).

### Módulos (pacote `engrama/`) [decisão de design]
| Módulo | Responsabilidade |
|---|---|
| `core/` | loop, relógio, barramento de eventos/estímulos, config, caminhos (tudo em E:) |
| `life/needs.py` | necessidades e sua dinâmica |
| `life/traits.py` | personalidade e deriva |
| `life/health.py` | doença, morte, renascimento |
| `brain/snn.py` | SNN LIF + STDP (numpy), serialização, dados para visualização |
| `brain/behavior.py` | utility AI + seleção, catálogo de comportamentos |
| `brain/learning.py` | recompensas, bandits, deriva de traços, gostos, interesses |
| `memory/` | SQLite: episódica, semântica, de trabalho; esquecimento |
| `evolution/` | estágios, ramificação, genoma visual, herança |
| `language/` | cliente Ollama, gerenciamento do servidor, prompt/persona, detecção de idioma, fala por estágio |
| `perception/` | amostragem do sistema, permissões, lista de bloqueio, "fechar os olhos", tela cheia |
| `art/` | geração procedural de sprites por genoma+estágio, animações |
| `audio/` | grunhidos chiptune procedurais |
| `ui/` | janela terrário, modo overlay, HUD, chat, menus (comida, modelos, permissões), modo SNN |
| `persistence/` | save/load, migrações, backup |

O protótipo em `spike/` é **referência**, não base: pode-se reaproveitar ideias e trechos (SNN, sprite, sons, prompt), mas o código novo vive em `engrama/` com testes.

---

## 5. A criatura

### 5.1 Necessidades **[usuário: lista]**
Escala 0–100, onde **alto = impulso forte** (quer aquilo).

| Necessidade | Sobe com | Desce com |
|---|---|---|
| fome | tempo | comer |
| sono | tempo acordado, atividade | dormir |
| tédio | tempo sem estímulo | brincar, conversar, explorar |
| carinho | tempo sem interação | carinho (clique), conversa gentil |
| curiosidade | tempo, novidades percebidas | explorar, aprender algo novo |
| interesse | — (é por tópico, ver 5.4) | — |
| empolgação | eventos positivos, novidades | decai naturalmente |
| apoio emocional | usuário demonstra tristeza/estresse (a criatura quer *dar* apoio); ou criatura ignorada muito tempo (quer *receber*) | conversa acolhedora |
| digitais (piada) | ex.: "RAM fresquinha", "desfragmentar", "atualização pendente" | ações bobas no menu |

**[decisão de design]** "Interesse" não é uma barra única: é um mapa de tópicos → afinidade (ver 5.4). "Empolgação" é um estado (humor), não um impulso.

Ritmo **[decisão de design]**: calibrado para vida de meses. Fome enche em ~6–8 h de tempo real acordado; sono em ~16 h; tédio em ~1–2 h sem interação. Valores ajustáveis num arquivo de balanceamento. O protótipo usa ritmo acelerado; um **modo dev** com multiplicador de tempo é obrigatório para testar.

### 5.2 Personalidade **[usuário]**
Traços 0–100, iniciais: curiosidade 50, sociabilidade 40, paciência 70, independência 30, criatividade 50.
- Afetam **de verdade** as utilidades dos comportamentos, a frequência de interrupções, os gostos e o prompt do LLM.
- **Podem mudar bastante** com o tempo **[usuário]**: deriva lenta a partir de eventos de aprendizado (5.4), com limite de variação por dia **[decisão de design]** para evitar saltos.
- Opacos para o usuário **[usuário]**: não há tela mostrando números; a personalidade aparece no comportamento e na fala. (Modo dev pode mostrar.)

### 5.3 Comportamentos
Catálogo inicial **[decisão de design]**: ocioso, passear, brincar sozinho, dormir, pedir atenção, explorar a janela, comer (quando alimentado), mostrar algo ("olha isso!"), comentar o que o usuário faz (com percepção), reagir a estímulo, ficar doente/abatido, esconder (tela cheia).
- **Desbloqueáveis por evolução e convivência** **[usuário]**: estágios mais altos liberam comportamentos novos (ex.: criança: "inventar brincadeira"; adulto: "puxar assunto sobre um interesse"; perfeito: "lembrar de algo antigo").
- Seleção por **utility AI**: utilidade = f(necessidades, traços, sinais da SNN, valor aprendido pelo bandit do comportamento, contexto). Exploração via softmax com temperatura ligada à curiosidade **[decisão de design]** (o protótipo usou ε-greedy).
- **Interrupções** (notificações/pedir atenção) têm orçamento próprio: frequência máxima configurável e aprendida (ignorado → reduz). **[usuário: pode interromper; detalhes não decididos]** Padrão **[decisão de design]**: no máximo 1 pedido de atenção a cada 20 min, nunca em tela cheia, nunca quando o usuário está digitando ativamente.

### 5.4 Aprendizado **[usuário: exemplos e abordagem]**
Sistema de recompensas + **multi-armed bandits contextuais simples** (contexto = faixa de horário × atividade percebida do usuário), sem alterar o LLM.

| Experiência | Efeito |
|---|---|
| Usuário responde quando ela pergunta | ↑ valor de "pedir atenção/iniciar conversa", ↑ sociabilidade (lento) |
| Usuário ignora pedidos frequentes | ↓ valor de interromper, ↑ independência |
| Usuário compartilha projetos | ↑ interesse no tópico (ex.: programação), ↑ curiosidade |
| Atividades juntos | ↑ preferência por atividades compartilhadas |
| Comidas | gostos por comida (protótipo já faz) |
| Conversa | tópicos e fatos sobre o usuário viram memória semântica e afinidade por tópico |

- **Interesses**: mapa tópico → afinidade (−1..1), alimentado por conversas (tópicos extraídos pelo LLM ou por palavras-chave), percepção (apps/jogos usados) e projetos compartilhados. Interesses entram no prompt e geram comportamentos ("puxar assunto sobre X").
- **Opiniões próprias** **[usuário]**: ela pode discordar e ter gostos que não espelham o usuário. Os gostos nascem do genoma + traços e derivam com experiência, mas não convergem automaticamente para os do usuário.
- **SNN e aprendizado**: STDP ajusta as conexões estímulo→comportamento conforme a co-ocorrência. Adicionalmente **[decisão de design]**, recompensas modulam a plasticidade (STDP modulado por recompensa/"dopamina": o sinal de recompensa escala a atualização acumulada em traços de elegibilidade). Isso liga o sistema de recompensas à SNN de forma biologicamente plausível.

### 5.5 SNN — o sistema nervoso
- Responsabilidades: transformar estímulos em dinâmica interna, influenciar comportamento, modular humor (arousal/valência), aprender associações por STDP. **Não** faz linguagem. **[usuário]**
- Estrutura **[decisão de design]**: populações de entrada (estímulos codificados por taxa/Poisson), camada oculta recorrente excitatória + interneurônios inibitórios, populações de saída por grupo de comportamento, e duas populações moduladoras (arousal, valência). Tamanho total ~100–300 neurônios, numpy vetorizado, custo alvo < 1% CPU.
- Cresce com a evolução **[decisão de design]**: cada estágio adiciona neurônios/entradas (ex.: entradas de percepção só a partir de criança), preservando pesos existentes. Isso torna a evolução também neural.
- Estímulos de entrada (inicial): clique/carinho, mensagem recebida, valência da mensagem (estimada pelo LLM ou léxico), comida, cada necessidade alta, hora do dia, novidade percebida, usuário ativo/ocioso, tela cheia, ruído espontâneo.
- Persistência dos pesos no save.
- **Modo SNN visível** **[usuário: modo especial]**: raster ao vivo, potenciais de membrana de neurônios selecionados, mapa de pesos, taxas por grupo, histórico de arousal/valência, e indicação de qual estímulo está entrando. Pode ser uma janela/painel separado ativado por tecla.

### 5.6 Memória **[usuário: só esquecer o momentâneo/descartável]**
SQLite em arquivo local **[decisão de design]**.
- **Trabalho**: últimas N trocas da conversa (contexto do LLM).
- **Episódica**: eventos com timestamp, tipo, resumo, valência, importância (0–1). Importância vem de: emoção envolvida, novidade, repetição, e o LLM marcando "isso é importante" em resumos.
- **Semântica**: fatos sobre o usuário e o mundo dela ("usuário gosta de Hollow Knight", "usuário estuda na USP"), com confiança e fonte. Extraídos por um passo do LLM **em segundo plano**, só quando o LLM já está carregado (não carregar só para isso).
- **Esquecimento**: eventos de baixa importância decaem e são apagados/compactados (ex.: "comeu fruta" ×30 vira "come fruta quase todo dia"). Fatos semânticos e eventos importantes **não** são esquecidos.
- **Recuperação para o prompt**: por recência + importância + correspondência de palavras-chave/tópico. Embeddings ficam fora do v1 **[decisão de design]** (custo de RAM); pode entrar depois com um modelo de embedding pequeno via Ollama.
- Opaca para o usuário **[usuário]** (sem editor de memórias; modo dev pode inspecionar).

### 5.7 Linguagem (LLM)
- **Runtime**: Ollama local, gerenciado pelo Engrama (inicia/para `ollama serve` com tudo em E:). **[decisão de design, já em uso]**
- **Modelos**: padrão `qwen3:1.7b` (bom PT/EN, ~1,4 GB). Lista de recomendados no app + campo livre para qualquer modelo; baixar pelo próprio app. **[usuário]**
- **Persona**: ela é o Engrama, criatura digital que vive na ficção mas sabe o que é (um programa na janela do PC do usuário). **[usuário]** Nunca fala como assistente.
- **Fala por estágio** **[usuário: cresce com a evolução]**: ovo = sons abafados; bebê = 1–6 palavras + sons; criança = frases curtas, erros fofos; adulto+ = frases completas, opiniões. Comprimento máximo e estilo controlados pelo prompt e por pós-processamento.
- **Idioma**: responde no idioma do usuário (PT/EN). Detecção melhor que a do protótipo **[construtor]** (ex.: léxico maior + heurística de acentos; ou pedir ao LLM que responda no idioma da mensagem).
- **Prompt** montado de: persona + estágio + traços em adjetivos + 1–2 necessidades/estado em palavras + gostos/interesses + memórias recuperadas + humor da SNN. Nunca números crus (lição do protótipo). Few-shot por estágio e idioma.
- **Fora do LLM** a criatura continua viva: sem LLM, conversa vira balbucio/reações e o resto segue. **[usuário]**
- **Partida a frio**: aquecimento em segundo plano; enquanto carrega, respostas de balbucio com dica "cérebro carregando". (Protótipo já faz.)
- Outros usos do LLM (só quando já carregado): extrair fatos/tópicos/valência de mensagens, resumir memórias, gerar comentários sobre o que o usuário está fazendo.

### 5.8 Percepção do PC **[usuário: tudo por permissões; amostragem periódica]**
- Fontes v1 **[decisão de design]**: título e processo da janela ativa, horário, tempo ocioso do usuário (último input), detecção de tela cheia, uso geral de CPU/RAM. Via APIs do Windows (ctypes/pywin32) + psutil. Sem captura de tela no v1 (pode virar permissão opcional depois).
- **Permissões**: cada fonte liga/desliga numa tela de permissões; padrão conservador (só horário e ociosidade ligados até o usuário liberar mais) **[decisão de design]**.
- **Lista de bloqueio** de apps/títulos (ex.: banco) — nesses, a percepção registra só "algo privado". **[usuário]**
- **"Fechar os olhos"**: atalho global que pausa toda percepção até ser reativado; indicador visual nos olhos da criatura. **[usuário]**
- **Tela cheia** (jogos, apresentações): criatura some/fica quieta automaticamente. **[usuário]**
- **Arquivos**: só lê o que o usuário mostrar explicitamente (arrastar arquivo/pasta para a janela, ou escolher num diálogo). Nada de varredura automática. **[usuário: lê se eu deixar]**
- **Agir no PC** (abrir coisas, mexer no mouse de brincadeira): **fora do v1**; previsto como permissão futura. **[usuário: talvez]**
- O que é percebido vira estímulo da SNN e eventos de memória (com o mesmo esquecimento).

### 5.9 Ciclo de vida e evolução **[usuário]**
- Estágios: **ovo → bebê → criança → adulto → perfeito → final**.
- **Ramificação** estilo Digimon: a forma em cada estágio depende do perfil de cuidado e personalidade (ex.: muito social + bem cuidado → um ramo; independente + curioso → outro; negligenciado → ramo "sombrio/rebelde"). Cada ramo tem um "arquétipo" que modifica genoma visual, traços e comportamentos liberados.
- Duração aproximada **[decisão de design]**: ovo minutos; bebê ~1–2 dias; criança ~1 semana; adulto ~3 semanas; perfeito ~1–2 meses; final até o fim da vida. Vida total de meses, **mais longa com bom cuidado**. **[usuário]**
- Evolução é **visível**: animação de evolução, forma nova. **[usuário]**
- **Saúde**: negligência prolongada (necessidades no máximo por muito tempo) → doença (visual abatido, comportamentos reduzidos); cuidado cura. Doença longa ou velhice → **morte**.
- **Morte e renascimento** **[usuário]**: ela não volta como era; nasce um **novo ovo que herda algo** — **[decisão de design]** herda parte do genoma visual (paleta/um traço de forma), um viés pequeno nos traços, e uma "memória ancestral" (1–3 lembranças marcantes da vida anterior, que ela menciona como sonho/déjà-vu). Mantém um registro das gerações.
- **Tempo com o app fechado** **[usuário]**: passa, mas de forma suave — necessidades sobem com teto (ela não morre nem adoece só por o app ficar fechado), e ela comenta a ausência ("demorou...", "dormi muito").

### 5.10 Aparência e som
- **Pixel art estilo Digimon, gerada proceduralmente** **[usuário]**: genoma visual (formato do corpo, olhos, orelhas/chifres, cauda, padrões, paleta) → sprite por estágio, com partes que mudam por ramo evolutivo. Simetria, contorno, 2–4 frames por animação (idle, andar, comer, dormir, feliz, triste, doente, evoluir).
- Criaturas e formas **originais**; inspiração no estilo, sem copiar designs ou nomes de Digimon.
- **Grunhidos** chiptune procedurais (tom do genoma, muda com estágio e humor). **[usuário]**

### 5.11 Janela e presença **[usuário: as duas formas]**
- **Modo terrário**: janela normal com o "mundo" dela (cenário pixel simples), HUD discreto, chat.
- **Modo overlay**: criatura sem moldura andando por cima da área de trabalho (janela transparente sempre-no-topo, clicável só onde há a criatura). **[construtor: técnica no Windows]**
- **Chat**: caixa de texto; balões de fala sobre a criatura.
- **Menus**: comida, modelos (LLM), permissões, configurações, descanso.
- **Modo SNN** (5.5) e **modo dev** (multiplicador de tempo, ver números, inspecionar memória).
- Sem números de necessidade visíveis no modo normal **[decisão de design]** — barras discretas ou ícones de humor, para manter a criatura "opaca".

### 5.12 Comida **[usuário: aprovou a mistura]**
Comidas "reais" em pixel (carne, fruta, peixe, bolinho…) + petiscos digitais de piada (pacote de dados, cookie de navegador, bug frito, cache quentinho, byte crocante). Cada uma com efeitos e gostos aprendidos (já existe no protótipo). Novas comidas podem ser desbloqueadas por estágio.

---

## 6. Persistência e robustez [decisão de design]
- Pasta de dados em E: (configurável): `engrama.db` (SQLite: memória, eventos, gerações), `state.json` (estado rápido: necessidades, traços, pesos da SNN serializados em `.npz`), `config.json`.
- Salvamento periódico (a cada poucos minutos) e ao sair; backup rotativo diário (últimos 7).
- Versão de schema + migrações simples.
- Se o save corromper: carregar último backup, nunca perder a criatura silenciosamente.

---

## 7. Marcos (ordem de construção) [decisão de design]

Este é um projeto grande; o plano de implementação deve cobrir **M1 e M2** primeiro (o "sucesso" definido pelo usuário: versão visual com conversa, LLM e SNN funcionando e visível), depois os demais em planos próprios.

1. **M1 — Núcleo vivo (headless, testado)**: estrutura do pacote, config/caminhos em E:, relógio com multiplicador, necessidades, traços, SNN v1 com STDP modulado por recompensa, behavior engine, learning (bandits, gostos), memória SQLite (episódica + trabalho + esquecimento básico), persistência, tempo offline. Testes automatizados.
2. **M2 — Corpo e voz**: janela terrário, sprites procedurais (ovo, bebê, criança no mínimo), animações, HUD, chat, LLM gerenciado (servidor Ollama em E:, aquecer/descarregar, seletor de modelos), persona e fala por estágio, comida, grunhidos, modo SNN, modo descanso manual + automático.
3. **M3 — Percepção**: permissões, amostragem da janela ativa, bloqueio, fechar os olhos, tela cheia, comentários sobre atividade, compartilhar arquivo arrastando, memória semântica extraída pelo LLM, interesses.
4. **M4 — Vida longa**: evolução ramificada completa até final, saúde/doença, morte, renascimento com herança, gerações.
5. **M5 — Presença**: modo overlay no desktop, notificações, comportamentos desbloqueáveis extras, necessidades digitais de piada.
6. **Futuro**: agir no PC (permissão), embeddings, Linux.

---

## 8. Critérios de sucesso
- **M1+M2**: abrir o app, ver o ovo chocar, conversar em PT e EN com respostas no personagem, ver a criatura agir sozinha, abrir o modo SNN e ver disparos reagindo ao que acontece; com LLM descarregado ela continua viva; núcleo dentro do orçamento de RAM/CPU.
- **Geral**: após semanas de uso, duas criaturas com histórias diferentes se comportam e falam de jeitos claramente diferentes.

---

## 9. Decisões complementares (após revisão)

1. **Repositório e layout** **[usuário + decisão de design]**: o repositório local (pasta `E:\Documentos\GitHub\digimon`) **é** o `alexzjss/engrama`. Código novo em `engrama/` (pacote), testes em `tests/`, `pyproject.toml` na raiz. `spike/` permanece como referência congelada (não importado pelo pacote; pode ser removido quando M2 estiver pronto).
2. **Estágios em M1/M2** **[decisão de design]**: M1 já tem a máquina de estágios mínima (ovo → bebê → criança → adulto…, avanço por idade + qualidade de cuidado, **sem ramificação**), o campo `stage` e o **genoma completo** no schema do save, e ganchos de crescimento da SNN por estágio. M2 desenha sprites de ovo, bebê e criança; estágios seguintes usam a forma da criança escalada até M4. M4 adiciona ramificação, arte dos estágios altos, doença/morte/herança — sem mudar o formato do save.
3. **Ollama** **[usuário]**: já instalado em `E:\Ollama` (modelo `qwen3:1.7b` em `E:\Ollama\models`). É pré-requisito documentado; o app só detecta (caminho configurável), inicia/para `ollama serve` com as variáveis apontando para E:, e mostra estado claro "Ollama não encontrado" sem quebrar. Download de modelos pelo app continua (via API do Ollama).
4. **SNN causal de verdade** **[decisão de design, coerente com "comportamento é o principal"]**: o termo da SNN na utilidade não é decorativo. Critérios testáveis em M1: (a) desligar a SNN altera de forma mensurável a distribuição de comportamentos num cenário fixo; (b) após condicionamento repetido (ex.: estímulo X sempre seguido de recompensa ao fazer Y), a probabilidade de Y diante de X aumenta por mudança de pesos, não só pelo bandit.
5. **Identidade inicial** **[decisão de design]**: cada criatura nova tem um `seed` aleatório gravado no save. Do seed saem o genoma visual, o tom dos grunhidos e os vieses iniciais de gosto. Traços iniciais são fixos (os valores da seção 5.2) — a divergência vem do genoma + convivência. Testes usam seeds fixos.
6. **Concorrência** **[decisão de design]**: a thread de simulação é a **única escritora** do estado e da memória. Percepção, LLM e UI só publicam eventos/resultados num barramento (filas thread-safe); a simulação os consome a cada tick. A UI lê um snapshot imutável do estado.
7. **Orçamento de recursos** **[decisão de design]**: meta medida, não portão de build. Um script de benchmark (`tools/bench.py`) roda o app headless por alguns minutos e reporta RAM/CPU/FPS; o resultado vai no PR de M2. Medição no Vivobook fica para o usuário.
8. **Idioma da interface** **[usuário]**: PT e EN. Camada de i18n simples desde M2 (arquivos de strings por idioma); idioma padrão segue o sistema, trocável nas configurações. Independente do idioma da conversa, que segue o usuário.

---

## 10. Deixado para o construtor
- Escolha de bibliotecas auxiliares leves (pywin32 vs ctypes, psutil etc.), desde que tenham wheels para Windows/Python 3.13.
- Técnica exata de janela transparente no Windows para o overlay.
- Detalhes numéricos de balanceamento (centralizados num arquivo `balance` para ajuste).
- Arquitetura exata da SNN dentro do orçamento e responsabilidades descritas.
- Formato exato das tabelas SQLite.
- Estrutura de testes (pytest), com testes headless para UI (SDL dummy).
