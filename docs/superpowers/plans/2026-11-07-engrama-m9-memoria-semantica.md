# Engrama M9 — Memória semântica: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** a criatura lembra pelo significado, não só pela palavra:
- fatos, tópicos, episódios e memórias ancestrais ganham um vetor de um modelo de embedding local (Ollama);
- a mensagem do usuário vira vetor e o que está perto dela entra no prompt, somado ao que as palavras do M4 já acham;
- funciona entre PT e EN;
- sem o modelo, tudo é exatamente o M4/M8.

**Arquitetura:**
- `OllamaClient.embed` chama `/api/embed`. Um `Embedder` novo (`engrama/services/language/embedder.py`) cuida de estado, prefixos de tarefa, normalização, validação e tempo limite.
- A memória (`store.py`, schema v3) guarda os vetores numa tabela `vectors` da mesma `memory.sqlite`, em `float16`, e responde `similar(qvec, kind, k, min_sim)` com numpy sobre uma matriz em cache. Ela não sabe nada do Ollama.
- `recall.py` ganha `qvec`; com `qvec is None` o caminho é o do M4, sem mudança.
- O `LanguageService` pede o vetor da mensagem antes do prompt (só com o embedder `ready`), aquece e descarrega o modelo de embedding junto com o de conversa e indexa em segundo plano por um job novo de prioridade 4.
- F5 ganha a linha "Busca por significado"; F7 e F2 mostram o estado.
- Kernel, mente, módulos, lab e vocabulário não mudam.

**Stack:** Python 3.13, stdlib (`sqlite3`, `hashlib`, `threading`, `urllib`), numpy, pygame-ce 2.5 e psutil. Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-07-engrama-m9-memoria-semantica-design.md` (as seções 2, 3, 5, 6, 7 e 9 são requisito; a §10 explica por que os limiares são valores de partida). Contexto: spec e plano M4 (memória viva), M5 (privacidade), M6 (gerações).

**Antes de começar:** as decisões da spec §2 foram respondidas pelo usuário (2026-11-03), que aceitou todas as recomendações; este plano as segue. Nenhum modelo é instalado ou baixado agora.

## Restrições globais

- Branch `m9`. Cada agente começa com `git reset --hard m9` no seu worktree.
- **Não mudam:** `EVENT_KINDS`, `ACTIONS`, `FOOD_IDS`, `NEED_KEYS`, `CHANNELS`, `DIGITAL_IDS`, `VARIANTS`, `DISPLAY_MODES`. Kernel, `mind`, `modules` e `lab` não são editados (se um teste provar bug, reportar).
- **Sem modelo = M8:** com embedder ausente, `off`, `missing`, `cold`, `failed`, `--no-llm`, tempo esgotado ou exceção, `recall` e as mensagens do prompt são idênticas ao gabarito gravado na Tarefa 0 com o código do M8. Os testes do M4 continuam passando sem edição.
- **Nunca carregar modelo sozinho:** o embedder só é chamado com o LLM de conversa `ready` (consulta) ou `ready` e `idle()` (índice). O aquecimento do embedder acontece no fim do `warm` do LLM; o descarregamento, no `unload`.
- **Threads:** chamadas ao embedder só nas threads `language-service` e `language-io` (ou no `pump()` em `sync=True`). Nunca na thread principal (UI) nem na da simulação. Nenhuma exceção do embedder sai do serviço.
- **Camadas** (`tests/test_architecture.py`, atualizado na Tarefa 0):
  - `engrama/services/memory/**` não importa `engrama.services.language` (a memória não conhece o Ollama);
  - `engrama/app/{ui,art,audio,i18n}/**` continua sem importar `services` (falam com adaptadores duck-typed montados em `host.py`);
  - as regras antigas continuam.
- **Privacidade:**
  - o texto que vira vetor é sempre um texto já gravado na memória (resumo de episódio, "chave: valor" do fato, nome do tópico, resumo ancestral); nunca título, processo ou conteúdo de arquivo;
  - todo caminho que apaga uma memória apaga o vetor dela **na mesma transação**;
  - um vetor só é gravado se a referência ainda existe, com o mesmo hash de texto e o mesmo modelo, conferido dentro do lock da memória;
  - `PRAGMA secure_delete = ON` na conexão da memória.
- **Fila do LLM:** chat 0 > comentário 1 > reflexão 2 > fatos 3 > **índice 4**. A latência do chat não piora mais que uma consulta de embedding com o modelo aquecido (tempo limite `EMBED_QUERY_TIMEOUT_S`).
- **Constantes** num bloco `# Task M9` de `engrama/services/memory/__init__.py` (sem importar `balance`):

  | Constante | Valor | Uso |
  |---|---|---|
  | `EMBED_BATCH` | 16 | textos por job de índice |
  | `EMBED_MAX_CHARS` | 500 | texto cortado antes de ir ao Ollama |
  | `EMBED_QUERY_TIMEOUT_S` | 1.0 | consulta na hora do chat |
  | `EMBED_BATCH_TIMEOUT_S` | 10.0 | lote de índice e aquecimento |
  | `EMBED_RETRY_S` | 60 | embedder `failed` antes de tentar de novo |
  | `EMBED_CHECK_S` | 300 | intervalo mínimo entre consultas a `tags()` |
  | `EMBED_DIM_MAX` | 4096 | dimensão acima disso = resposta inválida |
  | `INDEX_EVERY_S` | 5 | intervalo mínimo entre jobs de índice |
  | `SEM_MIN_SIM` | 0.5 | cosseno abaixo disso não conta como relacionado |
  | `FACT_MIN_SIM` | 0.6 | fato entra por significado |
  | `TOPIC_MIN_SIM` | 0.6 | tópico da opinião por significado |
  | `W_SEM` | 0.7 | peso do significado na relevância |
  | `W_WORD` | 0.3 | peso das palavras na relevância |
  | `W_IMPORTANCE` | 0.35 | episódio com `qvec` |
  | `W_RECENCY` | 0.15 | episódio com `qvec` |
  | `W_RELEVANCE` | 0.5 | episódio com `qvec` |
  | `VECTOR_RAM_MAX_MB` | 16 | teto da matriz em memória |
  | `SEARCH_BUDGET_MS` | 20 | `recall` com `qvec` e tetos cheios |

  `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM` e os dois tempos limite são valores de partida (spec §10): a Tarefa 6 mede com o modelo real, se instalado, e ajusta.
- **`Config`** (Tarefa 0): `embed_model: str = "embeddinggemma"`, `semantic_recall: bool = True`, `recommended_embed_models: tuple[str, ...] = ("embeddinggemma", "nomic-embed-text", "bge-m3")`. Vazio ou `semantic_recall=False` = desligado.
- **Orçamento:** ≤150 MB RSS e ≤2% de CPU em `test_core_budget` e `test_overlay_bench_within_budget`, **sem mudar os limites dos testes**. O M9 não acrescenta nada ao caminho sem LLM.
- **Testes sem Ollama:** todo teste usa o `FakeEmbedder` da Tarefa 0 ou um `http_json` falso. Nenhum teste automático fala com o Ollama de verdade.
- PT/EN em todo texto novo (`engrama/app/i18n/{pt,en}.json`); sem dígitos no modo normal.
- Commits sem `Co-Authored-By` e sem atribuição a IA. Mensagem exata dada em cada tarefa. Não fazer push.
- Python: `.venv/bin/python` do worktree (no Windows, `.venv\Scripts\python.exe`). Testes com `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`. Os testes gravam em `.pytest_tmp`. **Nunca rode dois pytest ao mesmo tempo.**
- Máquina de referência: CachyOS + Hyprland, Ollama 0.18.3 do sistema, **sem nenhum modelo instalado** no momento do plano (spec §10). Não baixar modelos sem o usuário pedir.

## Foco de revisão

1. **Paridade sem modelo:** o caminho `qvec is None` de `recall`, `retrieve` e `retrieve_ancestral` é byte a byte o do M8; o gabarito da T0 passa em todos os casos de degradação. (T0, T2, T3, T4)
2. **Corrida apagar × indexar:** um lote em voo para um item apagado (ou com valor trocado) não grava vetor; um lote do modelo antigo não grava depois de uma troca de modelo. (T2, T4)
3. **Todo caminho de apagar apaga o vetor:** `delete_fact`, `delete_topic`, `forget_all_about_user`, `_enforce_caps` (fatos e tópicos apagados por SQL), `forget` (compactação), `new_generation`, troca/desligamento do modelo, `upsert_fact` que troca o valor. (T2)
4. **Respostas estranhas do Ollama:** lista vazia, dimensão que muda, `NaN`/`inf`, vetor nulo, erro HTTP, "does not support embeddings" → `failed`, nunca exceção. (T1)
5. **Nada na thread da UI:** o adaptador do F7/F2 só lê contagens e estado; nada de embedding na UI. (T4, T5)
6. **Latência do chat:** a consulta só acontece com o embedder `ready`; com um embedder falso lento, o chat responde e cai para palavras em ≤ `EMBED_QUERY_TIMEOUT_S` a mais. (T4)

---

## Mapa de arquivos

```
engrama/services/memory/__init__.py        constantes M9
engrama/services/memory/store.py           schema v3, tabela vectors, unindexed, put_vectors, similar, apagar vetores, secure_delete, arquivo sem vetores
engrama/services/memory/recall.py          recall(..., qvec=None), relevância híbrida
engrama/services/language/client.py        OllamaClient.embed, unload_embed
engrama/services/language/embedder.py      Embedder (estado, prefixos, validação, tempo limite)
engrama/services/language/service.py       consulta no chat, aquecer/descarregar, job de índice P_INDEX, troca de modelo
engrama/config.py                          embed_model, semantic_recall, recommended_embed_models
engrama/app/host.py                        _MemoryProvider (estado semântico), main() (Embedder)
engrama/app/ui/menus.py                    ModelsPanel: linha "Busca por significado"
engrama/app/ui/memories.py                 linha de estado
engrama/app/ui/mind_view.py                vetores / memórias e estado do modelo
engrama/app/i18n/{pt,en}.json              textos novos
tests/services/fake_embedder.py            FakeEmbedder (conceitos PT/EN)
tests/services/memory/golden_recall.py     roteiro do gabarito
tests/fixtures/m8_recall_golden.json       gabarito gravado com o código do M8
tests/services/memory/test_vectors.py, tests/services/memory/test_recall_semantic.py
tests/services/language/test_embedder.py, tests/services/language/test_service_semantic.py
tests/app/test_models_panel_embed.py, tests/test_architecture.py, tests/test_m9_acceptance.py
README.md, pyproject.toml
```

## Ondas e modelos

| Onda | Tarefas | Modelo |
|---|---|---|
| 0 | T0 | haiku |
| A | T1, T2, T3 (sonnet), paralelas | sonnet |
| B | T4 (sonnet), T5 (haiku), paralelas; dependem de T1–T3 | sonnet / haiku |
| C | T6 | sonnet |

Arquivos por onda não se cruzam: em A, só a T1 toca `client.py`/`embedder.py`, só a T2 toca `store.py` e só a T3 toca `recall.py`; em B, só a T4 toca `service.py` e só a T5 toca `menus.py`/`memories.py`/`mind_view.py`/`host.py` (só a classe `_MemoryProvider`). A T6 é a única que mexe em `main()`.

---

### Tarefa 0: gabarito do M8, constantes, `Config`, textos, `FakeEmbedder` e regra de camadas — onda 0 (haiku)

**Arquivos:**
- Criar: `tests/services/fake_embedder.py`, `tests/services/memory/golden_recall.py`, `tests/fixtures/m8_recall_golden.json`, `tests/services/memory/test_golden.py`.
- Modificar: `engrama/services/memory/__init__.py` (bloco `# Task M9`), `engrama/config.py`, `engrama/app/i18n/pt.json`, `engrama/app/i18n/en.json`, `tests/test_architecture.py`.
- Testes: `tests/services/memory/test_golden.py`, `tests/test_config.py` (acréscimos), `tests/test_architecture.py` (acréscimos), `tests/app/test_i18n.py` (acréscimos).

**Interfaces:**
- Produz:
  ```python
  # tests/services/memory/golden_recall.py
  def build_store(path) -> MemoryStore          # relógio falso fixo; fatos, tópicos (atuais e passados), opiniões com e sem frase,
                                               # episódios (chat, reflexão, atividade, compactação), ancestrais, um tópico apagado
  CASES: tuple[tuple[str, str, str], ...]      # (texto, estágio, idioma): PT e EN, com e sem palavra em comum, estágios egg..final,
                                               # mensagem vazia, mensagem com dígitos
  def snapshot(store) -> list[dict]            # por caso: asdict(RecallContext) e build_messages(apply_recall(PersonaState(...)))
  # tests/services/fake_embedder.py
  CONCEPTS: dict[str, tuple[str, ...]]         # ~12 conceitos, cada um com palavras PT e EN sem acento
                                               # (ex.: "pet": cachorro, cao, bichinho, gato, dog, puppy, pet, biscoito)
  class FakeEmbedder:
      model: str; status: str                  # "ready" por padrão; atributo gravável
      dim: int = 32
      calls: list[tuple[str, int, str]]        # (método, n de textos, nome da thread)
      delay: float = 0.0; fail: bool = False
      def refresh(self) -> str
      def warm(self) -> bool
      def unload(self) -> None
      def query(self, text: str) -> np.ndarray | None
      def documents(self, texts: list[str]) -> list[np.ndarray] | None
  ```
  - Vetor do `FakeEmbedder`: uma coordenada por conceito (contagem das palavras do conceito em `plain_text`) mais algumas coordenadas de hash estável das outras palavras com peso pequeno; norma 1; texto sem nada → vetor fixo de "ruído". Textos do mesmo conceito ficam com cosseno ≥ 0,7; de conceitos diferentes, ≤ 0,3.
  - `fail=True` levanta `RuntimeError`; `delay` dorme antes de responder; `status != "ready"` → `query`/`documents` devolvem `None` sem contar chamada.
  - O JSON do gabarito é gerado **com o código do M8, antes de qualquer outra mudança**, por `python -m tests.services.memory.golden_recall --write` e commitado.
  - Constantes do bloco `# Task M9` (tabela das Restrições globais).
  - `Config`: os três campos novos; `load` aceita `embed_model` como `str`, `semantic_recall` como `bool`, `recommended_embed_models` como tupla.
  - i18n (PT e EN, sem dígitos): `ui.models.embed_title` ("Busca por significado" / "Recall by meaning"), `ui.models.embed_hint` ("Opcional: ela lembra pelo sentido, não só pela palavra" / "Optional: she remembers by meaning, not only by word"), `ui.models.embed_on`, `ui.models.embed_off`, `ui.models.embed_missing` ("modelo não instalado" / "model not installed"), `ui.memories.semantic_on` ("lembra pelo sentido" / "remembers by meaning"), `ui.memories.semantic_off` ("lembra só por palavras" / "remembers by words only"), `ui.mind.vectors`.
  - Arquitetura: `services/memory/**` proibido de importar `engrama.services.language`.

- [x] **Passo 1:** com o código do M8 intacto, escreva `golden_recall.py` e gere `tests/fixtures/m8_recall_golden.json`.
- [x] **Passo 2:** escreva os testes:
  - `test_recall_matches_m8_golden` (gera o snapshot de novo e compara com o JSON);
  - `test_fake_embedder_concepts` (cachorro × bichinho ≥ 0,7; cachorro × dog ≥ 0,7; cachorro × trabalho ≤ 0,3; norma 1; determinístico), `test_fake_embedder_fail_delay_status`;
  - `test_config_embed_defaults_roundtrip` (padrões; salvar e carregar; config do M8 sem os campos carrega com os padrões);
  - `test_memory_cannot_import_language` (árvore falsa com `services/memory/a.py` importando `engrama.services.language.client` → 1 violação) e `test_real_tree_respects_dependency_rules` continua verde;
  - `test_m9_i18n_keys_pt_en_no_digits`;
  - `test_m9_constants` (valores da tabela).
- [x] **Passo 3:** rode os testes. Esperado: FAIL nos novos (o gabarito já passa).
- [x] **Passo 4:** implemente.
- [x] **Passo 5:** rode `-m pytest -q tests/services/memory tests/test_config.py tests/test_architecture.py tests/app/test_i18n.py`. Esperado: PASS.
- [x] **Passo 6:** commit `feat(m9): M8 recall golden, constants, config, texts and fake embedder`.

---

### Tarefa 1: cliente de embedding e `Embedder` — onda A (sonnet)

Afetada pelas decisões "modelo de embedding" e "download" (spec §2).

**Arquivos:**
- Modificar: `engrama/services/language/client.py`.
- Criar: `engrama/services/language/embedder.py`.
- Testes: `tests/services/language/test_client.py` (acréscimos), `tests/services/language/test_embedder.py` (novo).

**Interfaces:**
- Consome: constantes M9, `Config.embed_model`/`semantic_recall` (T0).
- Produz:
  ```python
  # client.py
  class OllamaClient:
      def embed(self, model: str, texts: list[str], timeout: float) -> list[list[float]]
          # POST /api/embed {"model", "input": texts, "truncate": True, "keep_alive": self._keep_alive()}
          # devolve d["embeddings"]; {"error": ...} → RuntimeError; tempo → LLMTimeout; rede → LLMOffline
      def unload_embed(self, model: str) -> None
          # keep_alive 0 para o modelo de embedding (o builder confirma o pedido que o Ollama 0.18 aceita
          # para modelo só de embedding e registra num comentário)
  # embedder.py
  STATES = ("off", "missing", "cold", "ready", "failed")
  PREFIXES: dict[str, tuple[str, str]]   # família → (prefixo de consulta, prefixo de documento)
  def family(model: str) -> str          # "embeddinggemma:300m" → "embeddinggemma"
  def installed(model: str, tags: set[str]) -> bool   # "x" casa com "x" e "x:latest"
  class Embedder:
      def __init__(self, client, cfg, now: Callable[[], float] = time.monotonic) -> None
      model: str                         # property: cfg.embed_model.strip() se cfg.semantic_recall, senão ""
      status: str                        # property; "off" se model == ""
      dim: int | None                    # dimensão vista no último sucesso
      def refresh(self) -> str           # tags() no máximo a cada EMBED_CHECK_S (com now injetado); missing ou cold
      def warm(self) -> bool             # embed([" "]) com EMBED_BATCH_TIMEOUT_S; sucesso → ready
      def unload(self) -> None           # unload_embed; ready → cold; nunca lança
      def query(self, text: str) -> np.ndarray | None              # só ready; prefixo de consulta; EMBED_QUERY_TIMEOUT_S
      def documents(self, texts: list[str]) -> list[np.ndarray] | None   # só ready; prefixo de documento; EMBED_BATCH_TIMEOUT_S
  ```
  - Todo texto é cortado em `EMBED_MAX_CHARS` antes do prefixo.
  - Validação de toda resposta: quantidade igual à de textos; todos com a mesma dimensão, `1 ≤ dim ≤ EMBED_DIM_MAX`; finitos; norma > 0. Saída `float32` com norma 1.
  - Qualquer falha (exceção, resposta inválida, tempo) → `status = "failed"` por `EMBED_RETRY_S`, devolve `None`; depois do prazo volta a `cold` e o próximo `refresh`/`warm` tenta de novo. `LLMOffline` também zera o cache de `tags()`.
  - Dimensão diferente da anterior com o mesmo modelo → `dim` atualizado e `dim_changed: bool` levantado (a T4 trata como troca de modelo).
  - `model` mudou desde a última chamada → estado volta a `cold` (sem `tags()` velho).
  - Nunca chama `pull`: baixar é só pelo F5 (T5).

- [x] **Passo 1:** escreva os testes (com `http_json` falso no `OllamaClient` e cliente falso no `Embedder`):
  - `test_embed_request_body` (URL `/api/embed`, `input` lista, `truncate`, `keep_alive`), `test_embed_error_raises`, `test_embed_timeout_and_offline`;
  - `test_family_and_installed` (`embeddinggemma` × `embeddinggemma:latest`; `nomic-embed-text:v1.5` não casa com `nomic-embed-text`);
  - `test_status_off_missing_cold_ready` (config vazia → off; `tags` sem o modelo → missing; com → cold; `warm` ok → ready);
  - `test_tags_checked_at_most_every_check_s` (relógio falso);
  - `test_query_prefix_and_normalized` (prefixo de consulta do `embeddinggemma`; norma 1; `float32`), `test_documents_prefix_and_cut` (texto de 2000 caracteres chega com `EMBED_MAX_CHARS` + prefixo);
  - `test_invalid_responses_fail` (vazio, contagem errada, dimensões mistas, `NaN`, vetor nulo, dim > `EMBED_DIM_MAX`) e `test_failed_retry_after_retry_s`;
  - `test_not_ready_never_calls_client` (off/missing/cold/failed → `query`/`documents` sem chamada);
  - `test_dim_change_flag`, `test_model_change_resets_to_cold`;
  - `test_never_pulls` (cliente falso cujo `pull` falha o teste).
- [x] **Passo 2:** rode os testes. Esperado: FAIL.
- [x] **Passo 3:** implemente.
- [x] **Passo 4:** rode `-m pytest -q tests/services/language tests/test_architecture.py`. Esperado: PASS.
- [x] **Passo 5:** commit `feat(m9): Ollama embed client and Embedder`.

---

### Tarefa 2: vetores na memória (schema v3) — onda A (sonnet)

Afetada pelas decisões "onde guardar", "troca de modelo", "ancestrais" e "arquivo da geração" (spec §2).

**Arquivos:**
- Modificar: `engrama/services/memory/store.py`.
- Testes: `tests/services/memory/test_vectors.py` (novo), `tests/services/memory/test_store_v2.py` (acréscimo da migração v2 → v3).

**Interfaces:**
- Consome: constantes M9 (T0), `FakeEmbedder` (T0, só nos testes).
- Produz:
  ```python
  VECTOR_KINDS = ("episode", "fact", "topic", "ancestral")
  class MemoryStore:
      schema_version = 3
      # tabela: vectors(kind TEXT, ref TEXT, model TEXT, dim INTEGER, h TEXT, vec BLOB, t REAL, PRIMARY KEY(kind, ref))
      def vector_model(self) -> str                       # meta 'vector_model' ("" se nenhum)
      def set_vector_model(self, model: str) -> bool      # se mudou: apaga todos os vetores, grava o nome; True se apagou
      def drop_vectors(self) -> None                      # apaga todos e limpa 'vector_model'
      def unindexed(self, limit: int) -> list[tuple[str, str, str, str]]
          # (kind, ref, texto, h) sem vetor do modelo atual; ordem: fatos (confiança), tópicos (saliência),
          # ancestrais, episódios (importância desc, t desc); texto = o que está gravado, sem dígitos; h = blake2b(texto, 8 bytes)
      def put_vectors(self, model: str, items: list[tuple[str, str, str, np.ndarray]]) -> int
          # (kind, ref, h, vec); grava só se model == vector_model(), a referência existe e o h confere; float16; devolve quantos gravou
      def similar(self, qvec: np.ndarray, kind: str, k: int, min_sim: float) -> list[tuple[str, float]]
          # (ref, cosseno) desc, só do modelo atual e de dimensão igual à de qvec; [] sem vetores
      def release_vectors(self) -> None                   # solta a matriz em cache
      def vector_counts(self) -> dict                     # {"vectors": n, "items": episódios + fatos + tópicos}
      def retrieve(self, words, k=5, sims: dict[int, float] | None = None) -> list[str]
      def retrieve_ancestral(self, words, k=1, sims: dict[int, float] | None = None) -> list[str]
  ```
  - Migração v2 → v3: cria `vectors`, `schema_version = 3`, na mesma transação, sem tocar nas outras tabelas. Um banco v3 abre sem migrar.
  - `PRAGMA secure_delete = ON` em `_init`.
  - Texto por tipo: episódio = `summary` (+ `topic` se houver); fato = `"chave com espaços: valor"`; tópico = nome; ancestral = `summary`. Dígitos removidos como no `_clean` do recall.
  - Matriz em cache por tipo: `(refs, float32 [n, dim])`, refeita quando um contador de versão dos vetores muda (toda escrita ou apagamento em `vectors` incrementa). Construída sob o lock.
  - Apagar o vetor, na mesma transação, em: `_drop_episodes` (`episode` e `ancestral`), `delete_fact`, `delete_topic`, `forget_all_about_user` (todos), `_enforce_caps` (fatos e tópicos apagados), `forget` (os episódios compactados), `new_generation` (todos), `upsert_fact` quando o valor muda (o vetor velho codifica o valor velho).
  - `retrieve(..., sims=None)` e `retrieve_ancestral(..., sims=None)`: **o código do M4 sem mudança**. Com `sims` (id → cosseno), `sim' = max(0, (sim - SEM_MIN_SIM) / (1 - SEM_MIN_SIM))`, relevância = `W_SEM·sim' + W_WORD·overlap`; episódio: `W_IMPORTANCE·importância + W_RECENCY·recência + W_RELEVANCE·relevância`; ancestral: entra se `hit > 0` ou `sim ≥ SEM_MIN_SIM`, ordenado por relevância.
  - `archive_to(path)`: depois do backup, apaga `vectors` e `vector_model` na cópia e faz `VACUUM` nela (decisão "arquivo da geração").

- [x] **Passo 1:** escreva os testes (vetores do `FakeEmbedder`):
  - `test_migrate_v2_to_v3_keeps_everything` (banco montado com o schema v2 do M8: episódios, fatos, tópicos, opiniões, ligações, bloqueios e `app_categories` iguais depois de abrir);
  - `test_secure_delete_on`;
  - `test_unindexed_order_and_texts` (ordem dos tipos; texto do fato "jogo favorito: hollow knight"; sem dígitos; nada com vetor válido volta);
  - `test_put_vectors_checks_model_ref_hash` (modelo diferente → 0; ref apagada → 0; fato com valor trocado depois do `unindexed` → 0);
  - `test_similar_ranks_and_threshold` (cachorro perto de bichinho; trabalho abaixo de `min_sim` fora), `test_similar_ignores_other_dim`, `test_similar_cache_invalidated_on_write_and_delete`;
  - `test_every_delete_path_drops_vectors` (parametrizado: `delete_fact`, `delete_topic`, `forget_all_about_user`, `enforce_caps` com tetos baixos via `monkeypatch`, `forget` com episódios antigos de baixa importância, `new_generation`, `upsert_fact` com valor novo) → nenhuma linha de `vectors` aponta para referência inexistente e `similar` não devolve o item;
  - `test_set_vector_model_switch_drops` e `test_drop_vectors`;
  - `test_retrieve_without_sims_is_m4` (mesmo resultado que o gabarito da T0 para os casos de episódio) e `test_retrieve_with_sims_hybrid` (episódio sem palavra em comum e `sim` alto sobe para o topo; `sim < SEM_MIN_SIM` não muda a ordem do M4 além do termo de palavras);
  - `test_retrieve_ancestral_semantic`;
  - `test_archive_has_no_vectors` (a cópia não tem linhas em `vectors` nem `vector_model`; o original continua com elas);
  - `test_vector_ram_and_search_budget` (`slow`: 2.000 episódios + 300 fatos + 300 tópicos com vetores aleatórios de 768 dimensões; matriz ≤ `VECTOR_RAM_MAX_MB`; mediana de 20 chamadas de `similar` por tipo somadas ≤ `SEARCH_BUDGET_MS`).
- [x] **Passo 2:** rode os testes. Esperado: FAIL.
- [x] **Passo 3:** implemente.
- [x] **Passo 4:** rode `-m pytest -q tests/services/memory tests/test_m4_acceptance.py tests/test_m6_acceptance.py tests/test_architecture.py`. Esperado: PASS (os testes do M4 e do M6 sem edição).
- [x] **Passo 5:** commit `feat(m9): vector table, similarity search and vector-aware deletion`.

---

### Tarefa 3: recuperação híbrida — onda A (sonnet)

Afetada pela decisão "pontuação" (spec §2).

**Arquivos:**
- Modificar: `engrama/services/memory/recall.py`.
- Testes: `tests/services/memory/test_recall_semantic.py` (novo), `tests/services/memory/test_recall.py` (sem edição; tem que continuar passando).

**Interfaces:**
- Consome: constantes M9 (T0); a interface de memória da T2 (`similar`, `retrieve(..., sims)`, `retrieve_ancestral(..., sims)`), usada nos testes por uma memória falsa com a mesma assinatura.
- Produz:
  ```python
  def recall(memory, text: str, stage: str, lang: str, qvec: np.ndarray | None = None) -> RecallContext
  ```
  - `qvec is None`, ou a memória sem o método `similar` (duck typing, como o `retrieve_ancestral` do M6): exatamente o código atual.
  - Com `qvec`:
    - `_facts`: candidatos = achados por palavra (M4) ∪ `similar(qvec, "fact", 6, FACT_MIN_SIM)`; ordem por `W_SEM·sim' + W_WORD·(1 se casou palavra)`, empate pela ordem do M4; até 3; nenhum → os dois mais confiáveis (M4);
    - episódios: `memory.retrieve(words, 2, sims=dict(similar(qvec, "episode", 20, SEM_MIN_SIM)))` (refs convertidos para `int`);
    - ancestrais: `memory.retrieve_ancestral(words, 1, sims=...)` com `similar(qvec, "ancestral", 3, SEM_MIN_SIM)`;
    - opinião: primeiro as palavras (M4); sem nenhuma, os tópicos de `similar(qvec, "topic", 3, TOPIC_MIN_SIM)` em ordem, o primeiro que tem opinião;
    - assuntos atuais e passados: como no M4 (não dependem da mensagem).
  - `_clean` (sem dígitos) em tudo, como hoje. Qualquer exceção no caminho semântico → refaz pelo caminho do M4 (não devolve `RecallContext()` vazio por causa do significado).

- [x] **Passo 1:** escreva os testes (memória falsa com `similar` roteirizado e `FakeEmbedder`):
  - `test_qvec_none_identical_to_m4` (para cada caso do gabarito da T0 com a memória real do gabarito: `recall(..., qvec=None)` == JSON);
  - `test_memory_without_similar_is_m4`;
  - `test_fact_found_by_meaning` ("meu bichinho está doente" traz "animal de estimacao: cachorro biscoito");
  - `test_fact_word_hit_beats_weak_meaning`;
  - `test_episode_by_meaning_two_max`, `test_ancestral_by_meaning`;
  - `test_opinion_by_nearest_topic` (adulto; nenhuma palavra casa; tópico "cachorro" com opinião é o mais próximo);
  - `test_unrelated_message_adds_nothing` (mensagem de outro conceito → mesmo resultado que `qvec=None`);
  - `test_semantic_failure_falls_back_to_m4` (`similar` levanta → resultado do M4);
  - `test_stage_gating_unchanged_with_qvec` (bebê sem opinião; ovo vazio);
  - `test_no_digits_with_qvec`.
- [x] **Passo 2:** rode os testes. Esperado: FAIL.
- [x] **Passo 3:** implemente.
- [x] **Passo 4:** rode `-m pytest -q tests/services/memory tests/test_m4_acceptance.py`. Esperado: PASS.
- [x] **Passo 5:** commit `feat(m9): hybrid recall by words and meaning`.

---

### Tarefa 4: serviço de linguagem — consulta, aquecimento e índice — onda B (sonnet; depende de T1, T2, T3)

Afetada pelas decisões "indexar as memórias que já existem" e "troca de modelo" (spec §2).

**Arquivos:**
- Modificar: `engrama/services/language/service.py`.
- Testes: `tests/services/language/test_service_semantic.py` (novo); `tests/services/language/test_service.py` e os testes do M4/M6 sem edição.

**Interfaces:**
- Consome: `Embedder` (T1; `FakeEmbedder` nos testes), `MemoryStore` v3 (T2), `recall(..., qvec)` (T3).
- Produz:
  ```python
  P_INDEX = 4
  class LanguageService:
      def __init__(..., embedder=None)                  # None = sem busca por significado (M8)
      @property
      def embed_status(self) -> str                     # "off" sem embedder; senão embedder.status
      def embed_counts(self) -> dict                    # memory.vector_counts(); {} em erro
      def set_embed_model(self, name: str) -> None      # grava cfg.embed_model; troca de modelo (abaixo)
      def set_semantic_recall(self, on: bool) -> None   # False: drop_vectors + embedder.unload; True: refresh no próximo warm
  ```
  - `_qvec(text) -> np.ndarray | None`: só se `self.status == "ready"` e `embedder.status == "ready"`; chama `embedder.query`; qualquer exceção → `None`.
  - `_chat`, `_answer_pending` e `_spontaneous` passam `qvec=self._qvec(texto)` para `recall`. A chamada de `recall` continua no mesmo lugar do M8; com `qvec None` nada muda.
  - `_warm`: depois que o LLM fica `ready` (mesma geração), se há embedder e ele não está `off`: `refresh()`; se `cold`, `warm()`; se der `ready`, `memory.set_vector_model(embedder.model)`. Falha do embedder nunca muda o estado do LLM.
  - `unload()`: também `embedder.unload()` e `memory.release_vectors()`.
  - `tick(now)`: com embedder `ready`, LLM `ready`, nenhum job de índice na fila e `now ≥ próximo índice` (`INDEX_EVERY_S`), enfileira um job `P_INDEX`. O job: `model = embedder.model`; `memory.set_vector_model(model)`; `items = memory.unindexed(EMBED_BATCH)`; nada → para de agendar até a próxima escrita na memória (`_record`, `_extract`, `_reflect` religam); senão `vecs = embedder.documents(textos)`; `memory.put_vectors(model, ...)`.
  - O job de índice é elegível como os jobs ≥1 do M4 (`ready` e `idle()`), então nunca carrega modelo e para no descanso.
  - Troca de modelo (`set_embed_model` com nome diferente, ou `embedder.dim_changed`): `memory.set_vector_model(novo)` (apaga os vetores), `embedder.unload()` do antigo, estado `cold`; o índice recomeça no próximo `warm`. Um lote do modelo antigo em voo não grava porque `put_vectors` confere o modelo.
  - Novos itens (episódio de chat, fatos, tópicos, reflexão) não são indexados na hora: entram pelo próximo job de índice.

- [ ] **Passo 1:** escreva os testes (`sync=True`, `ScriptedClient` do M4, `FakeEmbedder`, relógio falso):
  - `test_chat_uses_meaning_when_ready` (o prompt de sistema enviado ao cliente traz o fato do cachorro para "meu bichinho anda doente");
  - `test_degraded_paths_match_m8_golden` (parametrizado: sem embedder, `off`, `missing`, `cold`, `failed`, `fail=True`, `delay > EMBED_QUERY_TIMEOUT_S` com um embedder que respeita o tempo limite): mensagens enviadas ao cliente == gabarito da T0;
  - `test_no_embedder_calls_when_llm_not_ready` (`offline` e `loading`: zero chamadas em `calls`, inclusive com `tick` e `pump`);
  - `test_warm_also_warms_embedder` e `test_unload_also_unloads_embedder`;
  - `test_index_job_batches_and_stops` (60 itens → 4 jobs de no máximo 16; depois nenhum job até um episódio novo);
  - `test_index_not_when_resting` (`idle()` falso → nenhum job roda);
  - `test_delete_during_index_not_written` (job tira o lote, o teste apaga um fato antes de `documents` devolver — via `FakeEmbedder` com gancho — e o vetor não aparece);
  - `test_model_switch_drops_and_reindexes`, `test_dim_change_treated_as_switch`, `test_semantic_off_drops_vectors`;
  - `test_embedder_threads_are_language_threads` (`sync=False`: os nomes de thread em `calls` são só `language-service`/`language-io`);
  - `test_chat_priority_still_first` (com jobs de índice na fila, uma mensagem nova é respondida antes deles).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente.
- [ ] **Passo 4:** rode `-m pytest -q tests/services tests/test_m4_acceptance.py tests/test_m6_acceptance.py`. Esperado: PASS.
- [ ] **Passo 5:** commit `feat(m9): semantic recall in the language service and background indexing`.

---

### Tarefa 5: F5, F7 e Visão da Mente — onda B (haiku; depende de T0; usa a interface da T4 por objetos falsos)

Afetada pelas decisões "download do modelo" e "painel Memórias" (spec §2).

**Arquivos:**
- Modificar: `engrama/app/ui/menus.py` (`ModelsPanel`), `engrama/app/ui/memories.py`, `engrama/app/ui/mind_view.py`, `engrama/app/host.py` (só a classe `_MemoryProvider`).
- Testes: `tests/app/test_models_panel_embed.py` (novo), `tests/app/test_memories_panel.py` (acréscimos), `tests/app/test_mind_view.py` (acréscimos), `tests/app/test_host.py` (acréscimo do adaptador).

**Interfaces:**
- Consome: i18n M9 (T0); duck typing da T4 em `window.language`: `embed_status`, `embed_counts()`, `set_embed_model(name)`, `set_semantic_recall(on)`, `installed_models()`, `pull(name, on_progress)`; `cfg.embed_model`, `cfg.semantic_recall`, `cfg.recommended_embed_models`.
- Produz:
  - `ModelsPanel`: abaixo da lista de modelos de conversa, um bloco `ui.models.embed_title` com `ui.models.embed_hint`, o modelo de embedding atual (de `recommended_embed_models`, trocável com as setas quando o bloco tem foco), o estado (instalado / `ui.models.embed_missing`), o botão de baixar (mesmo `pull` e a mesma barra de progresso dos modelos de conversa) e a chave ligar/desligar. Escolher chama `language.set_embed_model`; a chave chama `language.set_semantic_recall`; os dois salvam o config (`window.save_config`). Sem `language`, o bloco aparece desabilitado. O fluxo dos modelos de conversa não muda (teclas, seleção e download existentes).
  - `_MemoryProvider.summary()` ganha `"semantic": "on" | "words"` (`on` só com `embed_status == "ready"` ou com vetores gravados e o embedder não `off`), `"vectors"` e `"items"` (de `embed_counts()`); o provider recebe `language` opcional (`_memory_provider(memory, working, language=None)`).
  - `MemoriesPanel`: uma linha no rodapé, `ui.memories.semantic_on` ou `ui.memories.semantic_off`, sem números.
  - Visão da Mente: na linha de memória, `ui.mind.vectors` com `vectors/items` e o estado do embedder (números permitidos ali).
  - Nada disso chama o embedder: só lê estado e contagens já calculados.

- [x] **Passo 1:** escreva os testes (window e language falsos, pygame dummy):
  - `test_embed_block_shows_missing_and_download` (modelo fora de `installed_models` → texto de não instalado; clicar em baixar chama `pull("embeddinggemma", ...)`);
  - `test_embed_select_and_toggle_save_config` (trocar → `set_embed_model` + `save_config`; desligar → `set_semantic_recall(False)` + `save_config`);
  - `test_chat_models_flow_unchanged` (os testes existentes do `ModelsPanel` em `tests/app/test_menus.py` passam sem edição);
  - `test_embed_block_without_language_disabled`;
  - `test_memories_semantic_line_no_digits` (on e words);
  - `test_mind_view_shows_vector_counts`;
  - `test_memory_provider_semantic_summary` (language falso `ready` → `on`; `off` → `words`; sem language → `words`).
- [x] **Passo 2:** rode os testes. Esperado: FAIL.
- [x] **Passo 3:** implemente.
- [x] **Passo 4:** rode `-m pytest -q tests/app tests/test_architecture.py`. Esperado: PASS.
- [x] **Passo 5:** commit `feat(m9): recall-by-meaning controls in models, memories and mind view`.

---

### Tarefa 6: wiring, acceptance and README — onda C (sonnet)

**Arquivos:**
- Modificar: `engrama/app/host.py` (`main()`), `README.md` (PT e EN), `pyproject.toml` (versão `0.9.0`), `engrama/services/memory/__init__.py` (só se a calibração do Passo 6 mudar limiares).
- Criar: `tests/test_m9_acceptance.py` (marcado `slow` onde roda subprocesso, bench ou 30 dias simulados).

**Interfaces:**
- Consome: tudo acima.
- Produz:
  - `main()`: sem `--no-llm`, `embedder = Embedder(OllamaClient(cfg), cfg)`; com `--no-llm`, `None`. `LanguageService(..., embedder=embedder)`; `_memory_provider(memory, working, language)`. Encerramento igual ao M8 (o `language.shutdown()` não chama o Ollama; o `server.stop()` só se foi o Engrama que iniciou).
  - Um log de uma linha (`logging`, nunca na UI) quando o estado do embedder muda (`off`/`missing`/`cold`/`ready`/`failed`) com o nome do modelo, sem nenhum texto de memória.

- [ ] **Passo 1:** escreva `tests/test_m9_acceptance.py`, cobrindo os critérios da spec §7 com `MemoryStore` e `LanguageService` reais (`sync=True`), `ScriptedClient` do M4, `FakeEmbedder` e relógio falso; o `Host` real com `--no-llm` onde indicado:
  - `test_remembers_by_meaning` (critério 1: dia 1 "adotei um cachorro, o nome dele é Biscoito" com fato extraído; índice rodado; dia 5 "meu bichinho anda doente" → o prompt de sistema traz o cachorro; sem embedder, não traz);
  - `test_cross_language` (critério 2);
  - `test_no_model_is_m8` (critério 3: os casos de degradação contra o gabarito da T0, inclusive `main(["--no-llm", "--frames", "60", ...])` sem nenhuma chamada a `/api/embed` — `http_json` simulado que falha o teste se a URL terminar em `/api/embed`);
  - `test_never_loads_model_alone` (critério 4);
  - `test_embedder_off_ui_thread` (critério 5, `sync=False`);
  - `test_delete_drops_vectors_end_to_end` (critério 6: pelo `_MemoryProvider` do F7, apagar fato, tópico, "esquecer tudo"; e lote em voo);
  - `test_model_switch_end_to_end` (critério 7);
  - `test_migrates_m8_database` (critério 8: um `memory.sqlite` criado com o schema do M8);
  - `test_thirty_days_bounded` (critério 9, `slow`);
  - `test_search_budget` (critério 10, `slow`);
  - `test_generation_archive_and_ancestral_meaning` (critério 11: `Host` com fim de vida forçado como nos testes do M6);
  - `test_odd_ollama_answers_harmless` (critério 13, pelo `OllamaClient` real com `http_json` falso);
  - `test_lab_identical_to_m8` (critério 14: mesma fixture de métricas do M8) e `test_vocab_frozen`;
  - `test_smoke_frames` (`python -m engrama --frames 120 --no-llm --data-dir <tmp>` sai com 0).
- [ ] **Passo 2:** rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** implemente o resto da ligação.
- [ ] **Passo 4:** rode `-m pytest -q tests/test_m9_acceptance.py` e depois `-m pytest -q`, a suíte inteira. Esperado: tudo PASS, incluindo os dois testes de orçamento (critério 12).
- [ ] **Passo 5:** rode `tools/bench.py --app --seconds 60` e `--overlay --seconds 30`. Esperado: ≤150 MB e ≤2%, iguais ao M8 dentro do ruído. Anote no PR.
- [ ] **Passo 6:** **só se o usuário tiver instalado o modelo de embedding** (nunca baixar por conta própria): meça na máquina de referência a latência de `/api/embed` com o modelo frio e quente (1 texto e 16 textos) e o cosseno de pares relacionados e não relacionados em PT e EN; ajuste `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM`, `EMBED_QUERY_TIMEOUT_S` e `EMBED_BATCH_TIMEOUT_S` se preciso e registre a tabela no corpo do commit e no PR. Sem o modelo, registre "não medido" e mantenha os valores de partida.
- [ ] **Passo 7:** atualize o README em PT e EN:
  - seção nova "Busca por significado (M9)" / "Recall by meaning (M9)": o que é, que é opcional, como baixar o modelo pelo F5, quanto ocupa, que sem ele tudo funciona como antes;
  - "Privacidade": os vetores ficam na `memory.sqlite`, saem só de texto que ela já guarda, e apagar uma memória apaga o vetor; o arquivo de uma geração não leva vetores;
  - "Teclas": F5 agora também tem a busca por significado.
- [ ] **Passo 8:** commit `feat(m9): semantic memory wiring, M9 acceptance and README`.
- [ ] **Passo 9:** o controlador pede ao usuário o smoke manual na máquina de referência:
  - baixar `qwen3:1.7b` e o modelo de embedding pelo F5;
  - conversar sobre um assunto (por exemplo um animal de estimação com nome);
  - no modo dev, avançar alguns dias com `PgUp` e falar do mesmo assunto com outras palavras, e depois em inglês: a criatura retoma;
  - apagar o fato no F7 e conferir que ela não lembra mais;
  - desligar a busca no F5 e conferir que a conversa continua normal;
  - anotar no PR a latência medida no Passo 6.
