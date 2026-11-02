# Engrama M4 — Memória viva: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** dar à criatura memória semântica, assuntos atuais e passados, opiniões próprias, reflexão depois das conversas e iniciativa rara, além de um painel em que o usuário vê e apaga o que ela lembra.

**Arquitetura:**
- A memória continua num serviço (`engrama/services/memory`), em SQLite com migração de schema.
- A posição das opiniões é determinística (`opinions.py`). O LLM só escreve a frase.
- A recuperação por palavras alimenta o prompt da persona (`recall.py` → `PersonaState`).
- A reflexão e a extração rodam como jobs de prioridade 2 e 3 do `LanguageService`.
- A iniciativa é uma política pura (`initiative.py`), consultada pelo laço do `main()`.
- O painel Memórias é um painel de UI que fala com um adaptador duck-typed montado em `main()`. A UI nunca importa `services`.

**Stack:** Python 3.13, stdlib (sqlite3, unicodedata, hashlib), numpy e pygame-ce. Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-02-engrama-m4-memoria-viva-design.md` (as seções 2, 3, 6, 7, 8 e 10 valem como requisito). Contexto: o plano M3 `docs/superpowers/plans/2026-10-31-engrama-m3-corpo-e-voz.md` (restrições globais) e o `CLAUDE.md`.

## Restrições globais

- **Leveza:** núcleo com ≤ 150 MB de RSS e ≤ 2% de CPU, sem LLM.
- **Reflexão:** nunca carrega o LLM. Jobs de prioridade ≥ 1 só rodam com `status == "ready"` e `idle()`.
- **Fila do LLM:** chat 0 > comentário 1 > reflexão 2 > fatos 3. A latência do chat não pode piorar.
- **Local e offline.** Nada no C. Python em `E:/Documentos/GitHub/digimon/.venv/Scripts/python.exe`. Os testes gravam em `.pytest_tmp`.
- **Regras de importação** (`tests/test_architecture.py`):
  - `engrama/services/**` não importa `mind`, `modules`, `kernel`, `lab` nem `app`;
  - `engrama/app/{ui,art,audio,i18n}/**` só importa `engrama.app` (sem `engrama.app.host`), `engrama.vocab`, `engrama.balance`, stdlib, numpy e pygame;
  - só `engrama/app/host.py` liga tudo.
- **Persona:**
  - nenhum dígito no prompt de sistema nem na fala;
  - sem emoji;
  - sem fala de assistente;
  - PT/EN no idioma da mensagem.
- **UI no modo normal:** sem números. Números só no modo dev e na Visão da Mente.
- **Robustez:** nenhuma exceção da memória chega à thread da UI ou da simulação. Um `memory.sqlite` corrompido é renomeado para `memory.sqlite.corrupt-<ts>` e um novo é criado.
- **Commits:** sem `Co-Authored-By` e sem qualquer atribuição a IA ou Claude.
- **Estágios** (spec §7):

  | Capacidade | Estágios |
  |---|---|
  | Memória no prompt | bebê ou maior |
  | Puxar assunto atual | criança ou maior |
  | Opinar e discordar | adulto ou maior |
  | Retomar algo antigo | perfeito/final |
  
  Ordem: `egg < baby < child < adult < perfect < final`.
- **Constantes** num bloco `# Task M4` de `engrama/services/memory/__init__.py`, sem importar `balance`:

  | Constante | Valor |
  |---|---|
  | `SALIENCE_HALF_LIFE` | 3 dias |
  | `CURRENT_MIN_SALIENCE` | 0.35 |
  | `PAST_MIN_AGE` | 7 dias |
  | `PAST_MIN_AFFINITY` | 0.3 |
  | `MAX_EPISODES` | 2000 |
  | `MAX_FACTS` | 300 |
  | `MAX_TOPICS` | 300 |
  | `CONVERSATION_GAP_S` | 120 |
  | `INITIATIVE_PER_ACTIVE_S` | 3600 |
  | `ACTIVE_WINDOW_S` | 300 |
  | `OPPORTUNITY_EVERY_S` | 60 |

## Foco de revisão

1. **Tópico com acento, maiúsculas ou sinônimo PT/EN** ("Programação", "programacao", "programming") vira um tópico só. Teste em T1.
2. **Texto do LLM malformado** na reflexão ou na extração (JSON quebrado, chaves faltando, dígitos, emoji) é ignorado sem exceção e não grava lixo. Teste em T4.
3. **Apagar algo enquanto um job de extração ou reflexão sobre aquela conversa está na fila.** O item não volta. Teste em T1 (bloqueio) e T4 (job respeita bloqueio).
4. **Banco do M3 ou banco corrompido** abre sem derrubar o app. Teste em T1.
5. **Relógio que volta** (o usuário muda a hora do PC) não gera saliência negativa nem cota de iniciativa negativa. Teste em T1 e T5.

---

## Mapa de arquivos

```
engrama/services/memory/__init__.py      constantes M4
engrama/services/memory/topics.py        normalize_topic(), SYNONYMS
engrama/services/memory/store.py         schema v2, migração, saliência, ligações, apagar, bloqueio, tetos, compactação
engrama/services/memory/opinions.py      innate_lean(), stance(), Opinion
engrama/services/memory/recall.py        RecallContext, recall()
engrama/services/language/persona.py     PersonaState + campos de memória; build_messages usa-os; prompts de reflexão e comentário
engrama/services/language/service.py     recall no chat, reflexão pós-conversa, extração com ligações e bloqueio, spontaneous()
engrama/services/language/initiative.py  InitiativePolicy
engrama/app/ui/memories.py               MemoriesPanel (F7)
engrama/app/ui/window.py                 F7 → "memories"
engrama/app/ui/mind_view.py              seção de resumo da memória
engrama/app/host.py                      main(): seed/traits → lean, adaptador do painel, laço de iniciativa
engrama/app/i18n/{pt,en}.json            chaves ui.memories.*
tests/services/memory/test_{store_v2,topics,opinions,recall}.py
tests/services/language/test_{reflection,initiative}.py
tests/app/test_memories_panel.py
tests/test_m4_acceptance.py
```

Ondas: **A**: T1 · **B**: T2, T3, T6 (paralelas) · **C**: T4, então T5 · **D**: T7.

---

### Tarefa 1: Store v2 (schema, migração, tópicos, saliência, ligações, apagar, tetos)

**Arquivos:**
- Criar: `engrama/services/memory/topics.py`.
- Modificar: `engrama/services/memory/__init__.py` (constantes), `engrama/services/memory/store.py`.
- Testes: `tests/services/memory/test_topics.py` e `test_store_v2.py`. Os testes existentes de `test_store.py` continuam passando.

**Interfaces:**
- Produz:
  - `normalize_topic(name: str) -> str`: minúsculas, sem acento (NFKD), espaços colapsados, e `SYNONYMS` aplicados. `SYNONYMS` é um dict pequeno PT/EN → forma canônica PT, por exemplo `programming → programacao`, `games/game/jogos → jogo`, `music/musica → musica`.
  - `MemoryStore`, com `schema_version = 2`.
  - Tabelas novas ou alteradas:
    - `topics(name PK, affinity, salience, t_salience, first_t, last_t, mentions, source)`;
    - `episode_links(episode_id, kind ∈ {"topic","fact"}, ref)`;
    - `opinions(topic PK, lean, experience, confidence, phrase NULL, phrase_lang NULL, t)`;
    - `blocklist(kind, ref, t)`;
    - `meta` (já existe).
  - Métodos novos ou alterados:
    - `bump_topic(name, delta, source="chat") -> str`: normaliza, soma a afinidade (limitada a [-1, 1]), soma 1 à saliência decaída, incrementa `mentions` e devolve o nome normalizado. Não faz nada e devolve `""` se o nome estiver bloqueado.
    - `upsert_fact(key, value, confidence, source) -> bool`:
      - mesmo valor: a confiança sobe para `min(1, c_old + 0.5 × (1 - c_old) × c_new)`;
      - valor diferente com confiança nova ≥ 0.5 ou ≥ a antiga: troca o valor;
      - devolve False se a chave estiver bloqueada.
    - `add_episode(kind, summary, valence=0.0, importance=0.3, topic=None, topics=(), facts=()) -> int`: grava as ligações.
    - `current_topics(n=3) -> list[str]`: saliência decaída ≥ `CURRENT_MIN_SALIENCE`.
    - `past_topics(n=3) -> list[str]`: `now - last_t ≥ PAST_MIN_AGE`, afinidade ≥ `PAST_MIN_AFFINITY` e saliência abaixo do limiar.
    - `topic_rows() -> list[dict]`, `fact_rows() -> list[dict]`, `opinion_rows() -> list[dict]` e `recent_reflections(n=3) -> list[str]`, para o painel.
    - `delete_topic(name) -> int` e `delete_fact(key) -> int`: apagam o item, as opiniões do tópico, os episódios ligados e os episódios cujo texto normalizado contém o nome ou o valor, e põem o item no bloqueio. Devolvem quantos episódios apagaram.
    - `forget_all_about_user() -> None`:
      - apaga fatos, tópicos, episódios, ligações e reflexões;
      - mantém `opinions.lean` e zera `experience`, `phrase` e `confidence`;
      - mantém o `meta`;
      - põe no bloqueio os tópicos e fatos existentes.
    - `unblock_on_new_mention(kind, ref)`: o job de extração chama para uma menção nova vinda de uma mensagem **posterior** ao apagamento. O critério é o `t` da mensagem maior que o `t` do bloqueio.
    - `is_blocked(kind, ref, since: float | None = None) -> bool`.
    - `enforce_caps() -> None`: mantém os tetos `MAX_*`, removendo primeiro os de menor importância ou confiança e os mais antigos.
    - `forget(now=None)`: compacta por tipo e tópico num resumo sem dígitos, por exemplo "conversa sobre jogo, quase todo dia" (PT) ou "talked about jogo almost every day" (EN, conforme o idioma da maior parte). Chama `enforce_caps()` no fim.
  - A saliência decai assim: `salience_now = salience × 0.5 ** (max(0, now - t_salience) / SALIENCE_HALF_LIFE)`. O `max(0, …)` cobre o relógio que volta.
  - Abrir um banco corrompido ou ilegível renomeia o arquivo para `.corrupt-<int(now)>` e cria um novo.

- [ ] **Passo 1:** escreva os testes em `tests/services/memory/test_topics.py`. O teste `test_normalize_merges_accents_case_synonyms` verifica que "Programação", " programacao ", "PROGRAMMING" e "programming" normalizam para `"programacao"`.
- [ ] **Passo 2:** escreva os testes em `tests/services/memory/test_store_v2.py`, usando `now_fn` falso:
  - `test_migrates_m3_db`: crie um banco com o `_SCHEMA` do M3 literal (copie do `git show m3:engrama/services/memory/store.py`), com 2 episódios, 1 fato e o tópico "Jogos" com afinidade 0.4. Abra com o store novo:
    - `schema_version == "2"`;
    - os 2 episódios e o fato continuam;
    - o tópico vira `"jogo"` com afinidade 0.4.
  - `test_corrupt_db_is_set_aside`: escreva lixo no arquivo e abra. Não há exceção, existe `memory.sqlite.corrupt-*` e o store novo está vazio.
  - `test_salience_current_and_past`:
    - "jogo" é citado 5× no dia 0 e "musica" 3× no dia 20;
    - no dia 21, `current_topics() == ["musica"]` e `"jogo" in past_topics()`.
  - `test_salience_clock_backwards_is_safe`: com `now` menor que `t_salience`, a saliência fica ≤ o valor gravado e ≥ 0.
  - `test_fact_consolidation`:
    - repetir o mesmo valor sobe a confiança;
    - um valor novo com confiança 0.9 troca o antigo;
    - um valor novo com confiança 0.2, contra 0.8, não troca.
  - `test_delete_topic_removes_linked_and_mentioning_episodes`:
    - um episódio está ligado a "jogo", outro só tem "jogo" no texto, e um terceiro não tem relação;
    - `delete_topic("Jogos")` apaga os dois primeiros, a opinião e o tópico, e mantém o terceiro;
    - depois disso, `bump_topic("jogo", 0.5)` devolve `""`.
  - `test_blocked_until_newer_mention`: depois de `delete_fact("nome")`, `upsert_fact` com a mesma chave devolve False até `unblock_on_new_mention("fact", "nome")` ser chamado com um `t` posterior.
  - `test_forget_all_keeps_innate_lean`:
    - com uma opinião `lean=-0.7, experience=0.4, phrase="x"`, chame `forget_all_about_user()`;
    - a opinião fica com `lean == -0.7`, `experience == 0`, `phrase is None`;
    - fatos, tópicos e episódios ficam vazios.
  - `test_caps_and_compaction`: insira 2500 episódios de baixa importância ao longo de 30 dias e 400 fatos, e chame `forget(now)`:
    - o banco tem ≤ `MAX_EPISODES` episódios e ≤ `MAX_FACTS` fatos;
    - há um episódio de compactação;
    - nenhum resumo de compactação contém `\d`.
- [ ] **Passo 3:** rode os testes. Esperado: FAIL.
- [ ] **Passo 4:** implemente. A migração v1 → v2 roda dentro de uma transação:
  1. `ALTER TABLE`s com padrões;
  2. cria as tabelas novas;
  3. renormaliza os nomes de tópicos, fundindo duplicatas (soma das afinidades, limitada; maior `t`);
  4. grava `schema_version=2`.
  
  `retrieve` e `recent` continuam com a mesma assinatura.
- [ ] **Passo 5:** rode `-m pytest -q tests/services/memory tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 6:** commit `feat(m4): memory schema v2, topic salience, links, deletion and caps`.

### Tarefa 2: Opiniões determinísticas

**Arquivos:**
- Criar: `engrama/services/memory/opinions.py`.
- Modificar: `engrama/services/memory/store.py`, adicionando o método `update_opinion`.
- Teste: `tests/services/memory/test_opinions.py`.

**Interfaces:**
- Consome: T1 (tabela `opinions`, `normalize_topic`).
- Produz:
  - `innate_lean(seed: int, topic: str, traits: dict[str, float] | None = None) -> float`:
    - a base `b ∈ [-1, 1]` vem de `int.from_bytes(hashlib.blake2b(f"{seed}:{topic}".encode(), digest_size=8).digest(), "big")` mapeado para [-1, 1];
    - uma modulação pequena por traços (0–100) é somada: `+0.15 × (curiosidade - 50)/50` para todos os tópicos, sempre limitada a ±0.2;
    - o resultado é limitado a [-1, 1].
  - `stance(lean: float, experience: float) -> float`, que devolve `clamp(0.7 × lean + 0.3 × experience, -1, 1)`.
  - `stance_word(stance: float, lang: str) -> str`, sem dígitos. Faixas: ≤ -0.5 "detesta" / "hates"; < -0.15 "não curte muito" / "isn't fond of"; ≤ 0.15 "não tem opinião forte sobre" / "has no strong feelings about"; < 0.5 "gosta de" / "likes"; senão "adora" / "loves".
  - `MemoryStore.update_opinion(topic, lean_fn: Callable[[str], float], valence: float) -> None`:
    - cria a linha com `lean = lean_fn(topic)` congelado, se não existir;
    - atualiza `experience ← experience + 0.1 × (valence - experience)` e `confidence ← min(1, confidence + 0.05)`.
    
    A afinidade do usuário nunca entra na fórmula.
  - `MemoryStore.opinion(topic) -> dict | None`, com as chaves `topic, lean, experience, stance, confidence, phrase, phrase_lang`.
  - `MemoryStore.set_opinion_phrase(topic, phrase, lang) -> None`.

- [ ] **Passo 1:** escreva os testes:
  - `test_lean_is_deterministic_and_frozen`: o mesmo `(seed, topic)` dá o mesmo valor. Depois de criada a linha, mudar os traços passados ao `lean_fn` não muda o `lean` gravado.
  - `test_different_seeds_can_disagree`: existem sementes s1 e s2 em `range(50)` com `innate_lean(s1, "jogo") > 0.3` e `innate_lean(s2, "jogo") < -0.3`.
  - `test_does_not_converge_to_user`: um tópico com afinidade do usuário +1, e `update_opinion` 100× com valência +0.2, com `lean = -0.9`; a `stance` continua < 0.
  - `test_stance_word_has_no_digits`, para os dois idiomas.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services/memory`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m4): deterministic creature opinions`.

### Tarefa 3: Recuperação e prompt da persona

**Arquivos:**
- Criar: `engrama/services/memory/recall.py`.
- Modificar: `engrama/services/language/persona.py`.
- Testes: `tests/services/memory/test_recall.py`, e uma ampliação de `tests/services/language/test_persona.py`.

**Interfaces:**
- Consome: T1 (`facts`, `fact_rows`, `retrieve`, `current_topics`, `past_topics`, `normalize_topic`) e T2 (`opinion`, `stance_word`). Enquanto T2 não está mesclada, use `getattr(memory, "opinion", None)`.
- Produz:
  - `@dataclass RecallContext(facts: list[str], episodes: list[str], current: list[str], past: list[str], opinion: str | None)`. Todas as strings ficam sem dígitos (`re.sub(r"\d+", "", …)` e espaços colapsados).
  - `recall(memory, text: str, stage: str, lang: str) -> RecallContext`:
    - **palavras:** as palavras da mensagem normalizadas, sem stopwords PT/EN numa lista pequena local, com ≥ 3 letras;
    - **facts:** até 3 fatos `"chave: valor"` cuja chave ou valor normalizado contém alguma palavra; sem casamento, os 2 mais confiáveis;
    - **episodes:** `retrieve(palavras, 2)`;
    - **current:** `current_topics(2)`;
    - **past:** `past_topics(1)`, só se o estágio for perfect/final;
    - **opinion:** só se o estágio for adult ou maior e algum tópico normalizado da mensagem tiver opinião. O texto é `stance_word(...) + " " + topic`, ou a `phrase` se ela existir no mesmo idioma;
    - egg devolve um contexto vazio;
    - nunca levanta exceção: em erro, devolve um contexto vazio.
  - `PersonaState` ganha os campos `facts: list[str]`, `current_topics: list[str]`, `past_topics: list[str]` e `opinion: str | None`, com padrões vazios. `memories` continua e recebe `RecallContext.episodes`.
  - `build_messages` acrescenta, em PT e EN e só quando não vazios:
    - "O que você sabe do seu humano: …";
    - "Assuntos de agora: …";
    - "Um assunto antigo que você pode lembrar: …";
    - "Sua opinião: você … (pode discordar do humano)".
    
    A regra existente de remover `\d` do system continua.
  - `apply_recall(state: PersonaState, ctx: RecallContext) -> PersonaState` copia os campos.

- [ ] **Passo 1:** escreva os testes:
  - `test_recall_finds_fact_by_word`: o fato `jogo_favorito = hollow knight` e a mensagem "qual seu jogo preferido?" dão `"jogo_favorito: hollow knight"` em `facts`.
  - `test_recall_stage_gating`:
    - egg devolve tudo vazio;
    - baby tem `opinion None` e `past == []`;
    - adult tem `opinion` não None quando há opinião;
    - perfect tem `past` não vazio quando há tópico passado.
  - `test_recall_strips_digits`: o fato `"idade: 23 anos"` aparece sem dígitos.
  - `test_recall_never_raises`: um `memory` cujos métodos levantam exceção devolve `RecallContext([], [], [], [], None)`.
  - `test_prompt_includes_memory_without_digits`: um `PersonaState` com `facts=["time: 2 gatos"]` e `opinion="detesta jogo"` produz um system que contém "gatos" e "detesta jogo" e não contém `\d`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m4): word recall feeds facts, topics and opinions into the persona prompt`.

### Tarefa 4: Recall no chat, extração com ligações, reflexão pós-conversa e `spontaneous()`

**Arquivos:**
- Modificar: `engrama/services/language/service.py`, `engrama/services/language/persona.py` (prompts `REFLECT_PROMPT[lang]`, `OPINION_PROMPT[lang]`, `SPONTANEOUS_PROMPT[lang][kind]`).
- Teste: `tests/services/language/test_reflection.py`. Os testes atuais do serviço continuam passando.

**Interfaces:**
- Consome: T1, T2 e T3.
- Produz:
  - O construtor do `LanguageService` ganha `lean_fn: Callable[[str], float] | None = None`. Sem ele, `lean = 0`.
  - `_chat` monta o estado com `apply_recall(get_state(), recall(memory, text, stage, lang))`. O episódio de chat é gravado com `topics` igual aos tópicos normalizados detectados por palavras conhecidas (`topic_rows`).
  - `_extract(text, lang, t_msg)`:
    - para cada fato, se `is_blocked("fact", k, since=t_msg)` for falso, chama `upsert_fact`;
    - para cada tópico, chama `bump_topic(name, delta)`, e, se o nome devolvido não for vazio, chama `update_opinion(name, lean_fn, valence)`;
    - liga o episódio do chat aos tópicos e fatos extraídos.
    
    Um bloqueio criado **depois** de `t_msg` vence, e o item não volta.
  - **Fim de conversa:** `tick(now)` enfileira uma reflexão (`P_REFLECT = 2`) quando houve ao menos uma resposta `llm` e `now - last_reply ≥ CONVERSATION_GAP_S`, uma vez por conversa.
  - `_reflect()`:
    1. pede ao LLM `REFLECT_PROMPT` com as últimas mensagens da `WorkingMemory`;
    2. espera JSON `{"summary": str, "topic": str|null, "phrase": str|null}`;
    3. grava `add_episode("reflection", summary_sem_digitos, importance=0.6, topics=[topic])`;
    4. se houver tópico com opinião sem frase, ou com frase noutro idioma, gera a frase com `OPINION_PROMPT`, passando a `stance_word` e pedindo coerência com ela, e chama `set_opinion_phrase`.
    
    JSON inválido não grava nada. Nada roda se o status não for `ready`, o que a fila já garante.
  - `spontaneous(kind: str, topic: str | None = None) -> None`, com `kind ∈ {"current","opinion","past"}`: enfileira um comentário `P_COMMENT` com `SPONTANEOUS_PROMPT[lang][kind]` e o estado com recall. A resposta vai para `replies` como `Reply(text, lang, "llm")`, limpa por `clean_reply` (None é descartado).

- [ ] **Passo 1:** escreva os testes, com `sync=True`, cliente falso e `now_fn` falso:
  - `test_chat_prompt_contains_recalled_fact`: com o fato pré-gravado, o system enviado ao cliente contém o valor.
  - `test_extract_links_topics_and_updates_opinion`: o cliente falso de extração devolve `topics=[["Jogos", 0.5]]`; depois disso, `opinion("jogo")` não é None e o episódio de chat tem ligação `topic=jogo`.
  - `test_deleted_fact_not_recreated_by_queued_extract`:
    1. `request("meu nome é Ana")`;
    2. antes de `pump()` rodar a extração, `delete_fact("nome")`;
    3. `pump()`;
    4. a chave "nome" continua ausente.
  - `test_reflection_after_gap_only_when_ready`:
    - com o status `offline`, `tick(now + 200)` não chama o cliente;
    - com `ready` e depois de uma resposta llm, `tick(t + 121)` e `pump()` geram exatamente um episódio `reflection`, mesmo chamando `tick` de novo.
  - `test_reflection_bad_json_is_ignored`: o cliente devolve `"isso não é json 42 😀"`; não há exceção e nada é gravado.
  - `test_opinion_phrase_written_in_lang`.
  - `test_spontaneous_reply_clean`: o cliente devolve `"Como posso ajudar? 3"`; nada vai para `replies`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m4): recall in chat, linked extraction and post-conversation reflection`.

### Tarefa 5: Iniciativa rara e ligação no `main()`

**Arquivos:**
- Criar: `engrama/services/language/initiative.py`.
- Modificar: `engrama/app/host.py`, só em `main()` e em `_build_persona`, com acréscimos pequenos.
- Teste: `tests/services/language/test_initiative.py`.

**Interfaces:**
- Consome: T4 (`LanguageService.spontaneous`, `lean_fn`) e T1 (a `meta` do store e `current_topics`/`past_topics`/`opinion_rows`).
- Produz:
  - `InitiativePolicy(memory, now_fn)`, com `update(now, *, stage: str, user_active: bool, llm_ready: bool, resting: bool, fullscreen: bool, action: str) -> tuple[str, str | None] | None`. Ela devolve `(kind, topic)` para falar, ou None.
  - **Uso ativo:** cada chamada com `user_active` soma `min(now - last_call, OPPORTUNITY_EVERY_S)` ao uso. Um delta negativo, do relógio que volta, conta como 0.
  - **Gatilho:** com a cota disponível (uso desde o último comentário ≥ `INITIATIVE_PER_ACTIVE_S`), em cada oportunidade (a ação é `ask_attention`/`show_something`, ou passaram `OPPORTUNITY_EVERY_S` de uso desde a última verificação), o comentário dispara com probabilidade 0.25, sorteada por um `random.Random` semeado e injetável.
  - **Escolha do tipo, por estágio:**
    - perfect/final: `past` se houver tópico passado;
    - adult+: `opinion` se houver opinião com confiança ≥ 0.2;
    - child+: `current` se houver assunto atual;
    - senão, None.
  - **Bloqueios:** egg/baby, `not llm_ready`, `resting` ou `fullscreen` devolvem None.
  - O uso acumulado e o horário do último comentário são gravados na `meta` (`initiative_usage`, `initiative_last`), e sobrevivem a reinícios.
  - `main()`:
    - passa `lean_fn = lambda topic: innate_lean(int(snap.look.get("seed", 0)), topic, traits_snapshot_at_first_call)`, com os traços congelados na primeira chamada por tópico; o congelamento real vem do `update_opinion`;
    - no laço (1×/s), chama `policy.update(...)` com `user_active = time.time() - last_input < ACTIVE_WINDOW_S`; o `last_input` vem dos eventos pygame de teclado e mouse;
    - lê do snapshot `resting = snap.resting` e `fullscreen = snap.rest_reason == "fullscreen"`;
    - se `update` devolver um par, chama `language.spontaneous(kind, topic)`.

- [ ] **Passo 1:** escreva os testes:
  - `test_quota_one_per_active_hour`: em 10 h de uso ativo simuladas, com chamadas a cada 60 s, adulto, LLM pronto e opinião e tópico existentes, há entre 1 e 10 disparos.
  - `test_blocked_states`: baby, LLM offline, descanso e tela cheia nunca disparam em 10 h.
  - `test_inactive_time_does_not_count`: 10 h com `user_active=False` não disparam.
  - `test_quota_persists_across_restart`: depois de um disparo, uma nova `InitiativePolicy` sobre o mesmo store não dispara antes de mais 1 h de uso.
  - `test_clock_backwards_safe`: um `now` decrescente não gera exceção nem disparo extra.
  - `test_kind_by_stage`: child dá `"current"`; adult com opinião dá `"opinion"`; perfect com tópico passado dá `"past"`.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente a política e a ligação em `main()`.
- [ ] **Passo 4:** rode `-m pytest -q tests/services tests/app tests/test_m3_acceptance.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m4): rare stage-gated initiative`.

### Tarefa 6: Painel Memórias (F7) e resumo na Visão da Mente

**Arquivos:**
- Criar: `engrama/app/ui/memories.py`.
- Modificar:
  - `engrama/app/ui/window.py`: `KEY_PANELS[pygame.K_F7] = "memories"` e o registro do painel;
  - `engrama/app/ui/mind_view.py`: a seção "memória";
  - `engrama/app/i18n/{pt,en}.json`.
  
  Não mexa em `host.py`: o adaptador é feito em T7.
- Teste: `tests/app/test_memories_panel.py`.

**Interfaces:**
- Consome: um provedor duck-typed em `window.memory_provider`, com:
  - `facts() -> list[tuple[str, str]]`;
  - `topics() -> list[tuple[str, bool]]` (nome, é atual);
  - `opinions() -> list[tuple[str, str]]` (tópico, palavra de posição ou frase);
  - `reflections() -> list[str]`;
  - `delete_fact(key)`, `delete_topic(name)` e `forget_all()`;
  - `summary() -> dict` com `episodes, facts, topics, opinions: int` e `last_reflection: str`.
  
  A UI não importa `services`.
- Produz:
  - `MemoriesPanel(window)`:
    - seções Fatos, Assuntos (atuais marcados), Opiniões e Reflexões;
    - rolagem com a roda do mouse e ↑↓;
    - Delete ou clique no "x" apaga o item, com confirmação Enter/Esc;
    - o botão "esquecer tudo" pede confirmação dupla;
    - sem provedor, mostra `ui.memories.empty`.
    
    Todo texto passa por `hud.draw_text`, sem dígitos no modo normal: os valores de fatos com dígitos aparecem com os dígitos removidos fora do modo dev.
  - Chaves i18n PT/EN: `ui.memories.title`, `ui.memories.facts`, `ui.memories.topics`, `ui.memories.opinions`, `ui.memories.reflections`, `ui.memories.forget_all`, `ui.memories.confirm`, `ui.memories.empty` e `ui.memories.current`.
  - `MindView` lê `getattr(window_provider, "summary", None)`, passado por um atributo `MindView.memory_summary: Callable[[], dict] | None`, que `main()` define, e desenha as contagens e a última reflexão (números permitidos).

- [ ] **Passo 1:** escreva os testes, com provedor falso:
  - `test_lists_sections`: os textos capturados pelo hook contêm o título e um fato, um tópico e uma opinião.
  - `test_delete_requires_confirm`: Delete sem Enter não chama `delete_fact`; Delete seguido de Enter chama uma vez.
  - `test_forget_all_double_confirm`.
  - `test_no_digits_normal_mode`: o fato `"idade: 23"` aparece sem dígitos no modo normal e com dígitos no dev.
  - `test_f7_opens_panel`.
  - `test_mind_view_memory_summary_draws`, com um `summary` que levanta exceção: não quebra.
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/app tests/test_architecture.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m4): memories panel and mind view memory summary`.

### Tarefa 7: Ligação final, aceitação M4 e README

**Arquivos:**
- Modificar: `engrama/app/host.py` (`main()`: o adaptador `memory_provider` sobre `MemoryStore`; o `forget_all` também limpa a `WorkingMemory`; `delete_*` remove da `WorkingMemory` as mensagens que citam o item), `README.md` (PT e EN: memória, painel F7, iniciativa e privacidade), `pyproject.toml` (versão `0.4.0`).
- Criar: `tests/test_m4_acceptance.py`, marcado `slow`.

**Interfaces:**
- Consome: tudo acima.

- [ ] **Passo 1:** escreva a aceitação, cobrindo os critérios 1–8 da spec §8:
  - `test_remembers_fact_days_later`: o critério 1, com `LanguageService` `sync`, cliente falso e `now_fn` avançando 4 dias.
  - `test_current_vs_past_topics`: o critério 2.
  - `test_opinions_can_oppose_user_and_each_other`: o critério 3, com duas sementes do T2 e o mesmo histórico.
  - `test_reflection_never_loads_llm`: o critério 4. Com `offline`, o contador de `warm` e de `chat` do cliente fica em 0 depois de 1 h de `tick`.
  - `test_initiative_real_host`: o critério 5. Usa o `Host` real com `pump()` e relógio rápido, estágio forçado via `host.runtime.kernel` (como `tests/app/test_host.py` faz), `InitiativePolicy` e o serviço `sync`.
    - adulto dá entre 1 e 10 comentários em 10 h;
    - baby dá 0;
    - depois de `post("fullscreen_on")`, dá 0.
  - `test_delete_is_final`: o critério 6, pelo `memory_provider` de `main()`, construído com uma função auxiliar exportada `_memory_provider(memory, working)`.
  - `test_memory_bounded_30_days`: o critério 7. São 30 dias com 20 mensagens sintéticas por dia (textos PT/EN de uma lista) e `forget()` diário. O banco respeita os tetos e o arquivo fica ≤ 5 MB.
  - `test_m3_db_migrates`: o critério 8.
- [ ] **Passo 2:** rode `-m pytest -q tests/test_m4_acceptance.py`. Esperado: PASS.
- [ ] **Passo 3:** atualize o README e o pyproject.
- [ ] **Passo 4:** rode `-m pytest -q`, a suíte inteira. Esperado: tudo PASS.
- [ ] **Passo 5:** rode `tools/bench.py --app --seconds 30`. Esperado: pico de RSS ≤ 150 MB e CPU médio ≤ 2%. Registre os números no relatório.
- [ ] **Passo 6:** commit `feat(m4): wiring, M4 acceptance tests and README`.
