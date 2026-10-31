# Engrama — Arquitetura v2 (proposta)

Data: 2026-10-31 · Status: proposta para aprovação · Substitui as seções 4, 5.4, 5.5 e 9.4 do design v1.

Legenda: **[usuário]** = decidido pelo usuário · **[proposta]** = escolha do arquiteto, contestável.

---

## 1. O problema que a arquitetura resolve

O v1 tinha uma única aposta (SNN no centro), soldada a todo o resto. Trocar a aposta exigia reconstruir tudo.

O objetivo agora é outro **[usuário]**: o Engrama precisa ser, ao mesmo tempo,

1. **uma criatura** que parece viva, leve, local e com personalidade;
2. **um laboratório**, onde dá para experimentar diferentes aplicações de machine learning: SNN, redes contínuas, RL, bandits, modelos de mundo, LLM, inferência ativa e o que vier depois. Os experimentos precisam ser comparáveis, e nada pode quebrar a criatura.

Princípio central **[proposta]**: separar **o corpo** (fixo, determinístico, sem ML) **da mente** (um grafo de módulos trocáveis, que se comunicam por contratos estáveis). Todo experimento de ML é um módulo, ou uma receita de módulos.

---

## 2. Visão geral

```
┌──────────────────────────────────────────────────────────────────────┐
│ APRESENTAÇÃO (pygame)   corpo visual · chat · menus · Visão da Mente │
└───────────────▲──────────────────────────────────────┬───────────────┘
                │ snapshot (só leitura)                │ eventos do usuário
┌───────────────┴──────────────────────────────────────▼───────────────┐
│ KERNEL (corpo + mundo, determinístico, sem ML)                       │
│  relógio · necessidades · ciclo de vida · saúde · genoma · ações     │
│  sensores (usuário, tempo, PC com permissões) → Observações          │
│  executor de ações ← Ação escolhida                                  │
│  recompensas primitivas (necessidade aliviada, resposta do usuário)  │
└───────────────┬──────────────────────────────────────▲───────────────┘
                │ Observações + Recompensas            │ Ação + motivo
┌───────────────▼──────────────────────────────────────┴───────────────┐
│ MENTE (grafo de módulos, configurado por uma "receita")              │
│                                                                      │
│   BLACKBOARD: canais tipados (vetores nomeados), escritos/lidos      │
│   por módulos a cada tick, todos gravados                            │
│                                                                      │
│   módulos de percepção ─► módulos de estado interno ─► propositores  │
│   (codificam, detectam      (afeto, impulsos,           (sugerem     │
│    padrões no tempo)         modelo de mundo)            ações)      │
│                                        │                    │        │
│                                        ▼                    ▼        │
│                                   APRENDIZES ◄──── ÁRBITRO → Ação    │
│                                   (recebem recompensa, ajustam)      │
└───────────────┬──────────────────────────────────────────────────────┘
                │ chamadas assíncronas
┌───────────────▼──────────────────────────────────────────────────────┐
│ SERVIÇOS   Memória (episódica/semântica/reflexões) · Linguagem (LLM, │
│            fila de jobs) · Persistência · Registro de modelos        │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────┐
│ LABORATÓRIO  log de experiência · replay · modo sombra · usuário     │
│              simulado · métricas · avaliação offline · comparar      │
│              receitas                                                │
└──────────────────────────────────────────────────────────────────────┘
```

A **mente e o kernel rodam sem interface** (headless). Isso permite simular dias de vida em minutos, para treinar e comparar experimentos.

---

## 3. Kernel: o corpo

Não tem ML, não depende de nenhum módulo e é determinístico, dada uma seed. É a "física" da criatura.

- **Estado**: necessidades (fome, sono, tédio, carinho, curiosidade, apoio), estágio, genoma, saúde e idade. Estado de humor **não** fica aqui: humor é da mente.
- **Ações**: um catálogo fechado e versionado (ociosa, passear, brincar, dormir, pedir atenção, explorar, mostrar algo, comer, falar, esconder…). Cada ação tem pré-condições, duração, efeitos nas necessidades e o estágio mínimo para desbloquear. A mente **só escolhe**; quem executa e valida é o kernel. Se nenhum módulo propuser nada, entra uma política padrão segura (regras simples). Assim a criatura **nunca para**, mesmo que um experimento quebre.
- **Sensores**: transformam o mundo em **Observações** padronizadas, com timestamp: clique, mensagem, comida dada, hora, ociosidade do usuário, app ativo (com permissão, lista de bloqueio e "fechar os olhos"), tela cheia, uso de RAM/CPU.
- **Recompensas primitivas**: o kernel emite sinais crus, não um número único:
  - necessidade aliviada ou agravada;
  - usuário respondeu ou ignorou;
  - carinho;
  - valência da mensagem;
  - novidade.
  
  Cada módulo aprendiz combina esses sinais em sua própria função de recompensa. Isso deixa experimentar **formatos de recompensa** sem mexer no corpo.

---

## 4. Mente: o grafo de módulos

### 4.1 Contrato de módulo
Todo módulo implementa a mesma interface:

```python
class Module:
    name: str
    reads: list[Channel]        # canais do blackboard que consome
    writes: list[Channel]       # canais que produz
    rate_hz: float              # frequência própria (o scheduler respeita)
    budget_ms: float            # orçamento de CPU por chamada (medido)

    def step(self, bb: Blackboard, dt: float) -> None: ...
    def propose(self, bb) -> list[Proposal]: ...         # opcional
    def learn(self, exp: Experience) -> None: ...        # opcional
    def state_dict(self) -> dict: ...                    # persistência
    def load_state_dict(self, d: dict) -> None: ...
    def viz(self) -> VizSpec: ...                        # para a Visão da Mente
```

- **Canal**: um vetor numpy com nome, dimensão e significado declarados, por exemplo `affect.pad[3]`, `temporal.surprise[1]`, `drives[6]`. Os módulos só se conhecem pelos canais, nunca diretamente. Daí vem a troca livre: qualquer módulo que escreva `affect.pad` substitui outro.
- **Proposta**: `(ação, pontuação, motivo, origem)`. O motivo é obrigatório e legível ("fome alta + gosta de peixe"). Ele alimenta a Visão da Mente e o prompt do LLM.
- **Experiência**: `(obs, canais relevantes, ação, recompensas primitivas, próxima obs)`. É entregue a todos os aprendizes.

### 4.2 Árbitro
O árbitro combina propostas de vários módulos. Ele também é um módulo, então também é trocável:
- **Padrão [proposta]**: soma ponderada das pontuações, com amostragem softmax. A temperatura vem da curiosidade, e os traços de personalidade ajustam os pesos.
- **Alternativas para experimentar**:
  - árbitro aprendido, em que um bandit aprende em qual módulo confiar em cada contexto;
  - prioridade fixa (subsunção);
  - votação.

### 4.3 Receita
Uma receita (TOML) diz quais módulos rodam, com quais parâmetros e com quais pesos no árbitro. Trocar de experimento é trocar de receita. Cada receita tem nome e versão, e fica gravada em cada linha do log de experiência.

```toml
[recipe]
name = "default-v1"

[[module]]  type = "temporal.snn"       hidden = 96
[[module]]  type = "affect.pad"
[[module]]  type = "drives.needs"
[[module]]  type = "policy.utility"     weight = 1.0
[[module]]  type = "policy.qlearning"   weight = 0.6   context = ["hour", "user_active", "pad"]
[[module]]  type = "arbiter.softmax"
[[shadow]]  type = "temporal.ctrnn"     # roda e é medido, mas não age
```

### 4.4 Famílias de módulos (o que dá para plugar)
| Família | Canal que produz | Padrão v1 **[usuário: opção B + PAD]** | Experimentos possíveis |
|---|---|---|---|
| **temporal** | `temporal.surprise`, `temporal.familiarity`, `temporal.expectation[k]` | SNN LIF + STDP sobre o fluxo de eventos: novidade, habituação, rotina | CTRNN/liquid network, reservoir (ESN), HMM de rotina, contadores |
| **afeto** | `affect.pad[3]`, `affect.label` | PAD contínuo, alimentado por avaliação (appraisal) dos eventos | emoções discretas OCC, PAD aprendido |
| **impulsos** | `drives[n]` | necessidades → urgência (curvas não lineares) | homeostase aprendida |
| **modelo de mundo** | `world.pred_next[k]`, `world.error` | — (fora do v1) | prever a próxima atividade do usuário, RNN pequena online; o erro de previsão vira curiosidade intrínseca |
| **política** | propostas | utilidade (regras + traços) e Q-learning tabular contextual | bandits (UCB/Thompson), actor-critic linear, inferência ativa, árvore de comportamento |
| **aprendiz de preferências** | `prefs.*` | gostos por comida e por tópico (média móvel por recompensa) | filtragem colaborativa sobre o histórico |
| **personalidade** | `traits[5]` | deriva lenta e limitada por dia, a partir de estatísticas de experiência | deriva aprendida por gradiente |
| **linguagem** (via serviço) | `dialog.*` | LLM com persona por estágio | estilos de prompt, modelos diferentes, classificador de intenção leve |

Traços iniciais: curiosidade 50, sociabilidade 40, paciência 70, independência 30, criatividade 50 **[usuário]**. Eles entram nos pesos do árbitro, nos parâmetros dos módulos (por exemplo, a temperatura) e no prompt.

### 4.5 Scheduler
O scheduler roda numa thread única, a 1 Hz no tick base. Cada módulo roda na própria taxa (`rate_hz`). Ele mede o tempo real de cada módulo:
- se um módulo estoura o orçamento várias vezes, é **rebaixado** (taxa menor) e marcado na Visão da Mente;
- em modo descanso, todos os módulos caem para a taxa mínima.

Esta thread é a única que escreve no estado; UI, LLM e percepção só publicam eventos.

---

## 5. Serviços

- **Memória**: interface `MemoryStore`, implementada em SQLite no v1.
  - Tipos: episódica (com importância e esquecimento do trivial **[usuário]**), semântica (fatos sobre o usuário), reflexões (resumos e opiniões gerados pelo LLM) e trabalho (conversa recente).
  - Recuperação plugável: palavras-chave, recência e importância no v1. Embeddings via Ollama ficam como experimento.
- **Linguagem**: interface `LanguageBackend`; o padrão é o **Ollama gerenciado** em E: **[usuário]**.
  - Fila de jobs com prioridade: conversa > comentário > reflexão > extração de fatos. Jobs de fundo só rodam se o modelo já estiver carregado e o PC estiver ocioso.
  - Modelos recomendados ficam configuráveis, com qualquer outro permitido **[usuário]**; o padrão é `qwen3:1.7b`.
  - Regras de persona mantidas: nunca números crus, nunca fala de assistente, fala cresce com o estágio, PT/EN.
- **Reflexão** (o que mais faz ela parecer viva): de tempos em tempos, com o LLM carregado, ela resume o dia em episódios, forma opiniões e atualiza interesses. O resultado volta como memória e como mudança de preferências. O LLM **nunca** decide ações em tempo real: ele é o córtex de linguagem e reflexão.
- **Persistência**: o save é `kernel.json` mais um `state_dict` por módulo (em `.npz`), versionados por módulo.
  - Trocar de receita mantém o corpo e a memória. Módulos novos começam do zero ou por "transplante": o novo é pré-treinado no replay do log antes de assumir.
  - Salvamento atômico e backups diários.
- **Registro de modelos**: catálogo dos tipos de módulo disponíveis (`type` → classe), com dependências opcionais declaradas. Um módulo que exige `torch` ou `onnxruntime` simplesmente não aparece se a dependência não estiver instalada. O núcleo depende só de numpy.

---

## 6. Laboratório: o que torna isto uma plataforma de ML

1. **Log de experiência** (append-only, SQLite com rotação): grava cada observação, os canais do blackboard (amostrados), as propostas, a ação, as recompensas e a receita/versão. É o dataset de tudo.
   - Com limite de tamanho, e respeitando a privacidade: títulos de janelas bloqueadas nunca entram.
2. **Replay**: roda qualquer módulo sobre o log gravado, para treinar offline ou comparar como dois módulos reagiriam à mesma vida.
3. **Modo sombra**: o módulo roda ao vivo, propõe e é medido, mas não age. Serve para comparar uma SNN e uma CTRNN, por exemplo, sem arriscar a criatura.
4. **Usuário simulado**: perfis de usuário scriptados (atento, ausente, noturno, gamer) e, opcionalmente, um usuário controlado pelo LLM. Somado ao kernel headless em tempo acelerado, dá semanas de vida em minutos, para testar estabilidade e calibrar.
5. **Métricas padronizadas por receita**:
   - bem-estar (tempo com necessidades críticas);
   - taxa de interrupções ignoradas;
   - diversidade de comportamento (entropia);
   - divergência entre duas criaturas;
   - custo de CPU/RAM por módulo;
   - surpresa prevista vs. observada.
6. **Avaliação offline de políticas**: estimativa por importância (IPS) sobre o log, para avaliar uma política nova antes de colocá-la no controle.
7. **CLI `engrama-lab`**: `run`, `replay`, `compare`, `sim --days N --profile X`, `report`.

---

## 7. Visão da Mente **[usuário: SNN visível em modo especial]**

Ela é gerada automaticamente a partir do `viz()` de cada módulo, então todo experimento novo aparece sem código de UI. Tipos de `VizSpec`:
- `raster` (disparos);
- `heatmap` (pesos);
- `series` (linhas no tempo);
- `bars`;
- `pad3d` (ponto no espaço de emoção);
- `table`.

O painel fixo mostra:
- o grafo da receita;
- as propostas do tick, com motivo e qual venceu;
- o custo por módulo;
- os módulos em sombra, lado a lado com o ativo.

No modo normal, a criatura continua opaca **[usuário]**.

---

## 8. Restrições mantidas
- Leve no Vivobook Go 15 com 8 GB **[usuário]**:
  - kernel e mente ≤ 150 MB e ≤ 2% de CPU médio;
  - o LLM só fica carregado durante e logo após a conversa;
  - modo descanso manual e automático.
- Local e offline, e nada instalado no C **[usuário]**.
- Python 3.13, pygame-ce, numpy e psutil. O resto é opcional, por módulo.
- Windows primeiro, com o código específico do sistema isolado em `kernel/sensors/windows.py`.
- Commits sem coautor do Claude **[usuário]**.

---

## 9. Estrutura de pacotes **[proposta]**

```
engrama/
  kernel/      clock, needs, lifecycle, genome, actions, sensors/, rewards, kernel.py
  mind/        blackboard, channels, module (contrato), scheduler, arbiter, recipe, registry
  modules/     temporal/{snn,ctrnn}, affect/pad, drives/, policy/{utility,qlearn,bandit},
               prefs/, traits/        (cada um isolado, com testes próprios)
  services/    memory/, language/{ollama,persona,jobs}, reflection, persistence
  lab/         explog, replay, shadow, simuser, metrics, ope, cli
  app/         ui/{window,hud,chat,menus,mind_view}, art/, audio/, i18n/
recipes/       default-v1.toml, ...
tests/
```

**Regra de dependência**: `kernel` não importa nada de `mind`; `modules` só importam `mind` (o contrato); `app` só lê snapshots. Um teste de arquitetura verifica isso.

---

## 10. Marcos **[proposta]**

1. **M1: Plataforma headless.**
   - Kernel, blackboard, contrato de módulo, scheduler, árbitro, receita e registro.
   - Módulos mínimos: impulsos, utilidade e PAD.
   - Log de experiência, usuário simulado e `engrama-lab sim`.
   - Critério: 30 dias simulados em menos de 2 min, com a criatura estável e as métricas reportadas.
2. **M2: Mente padrão.**
   - SNN temporal, Q-learning contextual, preferências e deriva de traços.
   - Modo sombra, replay e `compare`.
   - Critério: a SNN mede de forma comprovável novidade e habituação no replay, e a receita com SNN difere da receita sem SNN numa métrica definida.
3. **M3: Corpo e voz.**
   - Janela pygame, sprites e grunhidos procedurais, chat, LLM gerenciado, persona por estágio, Visão da Mente e descanso.
   - Critério: é o MVP do usuário (criatura visual, conversa, SNN visível).
4. **M4: Memória viva.** Reflexão com LLM, memória semântica, interesses e opiniões.
5. **M5: Percepção do PC.** Permissões, bloqueio, fechar os olhos, tela cheia e comentários.
6. **M6: Vida longa e presença.** Evolução ramificada, doença, morte, herança, overlay e necessidades digitais.
7. **Experimentos** (cada um vira apenas um módulo e uma receita): CTRNN, modelo de mundo com curiosidade intrínseca, Thompson sampling, inferência ativa, embeddings.

**Mudança de ordem em relação ao v1**: a plataforma e o laboratório vêm antes da janela. É isso que garante que trocar a ideia de ML no futuro não exija reconstruir de novo.

---

## 11. Riscos
- **Abstração demais cedo**: o contrato de módulo precisa nascer junto com 3–4 módulos reais, nunca no vácuo. M1 já inclui três módulos.
- **Log grande**: rotação e amostragem dos canais (ex.: blackboard a cada 10 s, eventos sempre).
- **O MVP visual chega mais tarde** (M3). Em troca, o MVP já nasce sobre a base certa.
- **Usuário simulado ≠ usuário real**: o simulado serve para estabilidade e calibração. A personalidade só se valida com uso real.
