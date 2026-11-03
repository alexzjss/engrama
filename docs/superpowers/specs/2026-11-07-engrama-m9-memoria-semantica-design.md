# Engrama M9 — Memória semântica: design

**Status:** proposta para aprovação · **Data:** 2026-11-07 · **Base:** branch `m8` (PR #9). Fontes: spec e plano M4 (memória viva), spec v1 §5.4 ("embeddings ficam fora do v1 [...] pode entrar depois com um modelo de embedding pequeno via Ollama"), arquitetura v2 §5 ("Embeddings via Ollama ficam como experimento") e §10, specs M5 (privacidade da percepção) e M6 (gerações e memórias ancestrais), e as medições da máquina de referência (§10).

Nome: no M4, "memória semântica" quer dizer **os fatos sobre o usuário**. No M9 o termo ganha o outro sentido, o de **recuperar por significado**: a criatura lembra de uma conversa sobre "meu cachorro" quando o usuário fala do "bichinho", sem palavra em comum. Os fatos, tópicos, opiniões e episódios do M4 continuam iguais; o que muda é **como eles são achados** para o prompt.

## 1. Intenção

Hoje a recuperação do M4 é só por palavras (`recall.py`): sobreposição de palavras, recência e importância. Ela falha sempre que o usuário diz a mesma coisa com outras palavras, em outro idioma ou de forma indireta ("estou triste com meu emprego" não acha a conversa sobre "o chefe me demitiu").

No M9 a criatura passa a **lembrar pelo sentido**:
- cada fato, tópico, episódio e memória ancestral ganha um vetor (embedding) calculado por um modelo de embedding **local**, no Ollama;
- a cada mensagem, a mensagem também vira vetor, e o que está perto dela no espaço dos vetores entra no prompt, somado ao que as palavras já acham;
- isso funciona entre PT e EN (um modelo multilíngue põe "dog" perto de "cachorro").

Sem o modelo de embedding (não instalado, Ollama parado, erro, `--no-llm`), **tudo é exatamente o M4**: mesma recuperação, mesmo prompt, mesma fala.

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Recuperação | **[usuário]** M9 = memória semântica: recuperar memórias por significado com embeddings do Ollama local, em cima da memória viva do M4 |
| Modelo de embedding | **[pendente — recomendação: `embeddinggemma` (300M parâmetros, ≈0,6 GB, multilíngue com PT, 768 dimensões). Alternativas: `nomic-embed-text` (≈0,27 GB, mais leve, fraco em PT), `bge-m3` (≈1,2 GB, forte em multilíngue, pesado para 7 GB de RAM com o `qwen3:1.7b` junto), `paraphrase-multilingual` (≈0,56 GB). O nome fica em `Config.embed_model`; qualquer modelo de embedding do Ollama funciona]** |
| Download do modelo | **[pendente — recomendação: o app nunca baixa sozinho. O menu de modelos (F5) ganha uma linha "Busca por significado" com o modelo recomendado, o estado (instalado / não instalado) e o botão de baixar, igual aos modelos de conversa. Sem o modelo, a recuperação é a do M4]** |
| Indexar as memórias que já existem | **[pendente — recomendação: em segundo plano, aos poucos (lotes pequenos), só com o LLM de conversa já pronto e a máquina livre, como a reflexão do M4. Nunca carrega um modelo só para indexar. Ordem: fatos, tópicos, ancestrais, depois episódios dos mais importantes e recentes para os mais antigos. Indexar tudo na abertura foi descartado porque carregaria o modelo sem conversa]** |
| Pontuação | **[pendente — recomendação: híbrida. As palavras continuam valendo e o significado soma: relevância = `W_SEM`·similaridade + `W_WORD`·sobreposição, e a pontuação final mistura relevância, importância e recência (§3, item 4). Item sem vetor usa só palavras. Pura por significado foi descartada porque nomes próprios ("Hollow Knight", "Biscoito") são achados melhor por palavra]** |
| Memórias ancestrais (M6) | **[pendente — recomendação: sim, também ganham vetor. São no máximo três por geração (`ANCESTRAL_MAX`), custo desprezível, e um "sonho de antes de nascer" lembrado pelo sentido é mais bonito]** |
| Painel Memórias (F7) | **[pendente — recomendação: só uma linha de estado discreta ("lembra pelo sentido" / "lembra só por palavras"), sem números. A Visão da Mente (F2) mostra quantas memórias têm vetor e o estado do modelo. Uma lista de "lembranças parecidas" por item fica para depois]** |
| Onde guardar os vetores | **[pendente — recomendação: na mesma `memory.sqlite`, numa tabela nova (schema v3), vetor como BLOB `float16`. Assim apagar uma memória e o vetor dela acontece na mesma transação, e um banco só continua sendo "tudo o que ela lembra". Arquivo separado foi descartado: dois arquivos podem divergir num travamento e o apagar deixaria de ser atômico]** |
| Trocar de modelo de embedding | **[pendente — recomendação: os vetores do modelo antigo são apagados na hora (vetores de modelos diferentes não se comparam) e tudo é reindexado em segundo plano pela mesma regra da indexação; enquanto isso a recuperação usa só palavras para o que ainda não tem vetor. Desligar a busca por significado também apaga todos os vetores]** |
| Arquivo da geração (M6) | **[pendente — recomendação: o arquivo `data/generations/<n>/memory.sqlite` é gravado sem vetores. Eles saem do texto, dependem do modelo e só aumentariam o arquivo]** |

Continuam valendo, por decisão do usuário em marcos anteriores:
- recuperação por palavras como base (M4), que agora vira o caminho sem modelo;
- reflexão e jobs de fundo nunca carregam o LLM (M4);
- painel Memórias em que o usuário vê e apaga; apagar apaga tudo que cita o item (M4);
- percepção: título cru e nome de processo nunca saem do serviço de percepção; temas silenciados não voltam (M5);
- memórias ancestrais sem dígitos, sem fatos do usuário e sem nada bloqueado (M6);
- tudo local e offline; PT/EN; sem números no modo normal; ≤150 MB e ≤2% de CPU (M3, M8).

## 3. Objetivos

1. **Cliente de embedding.**
   - `OllamaClient.embed(model, texts, timeout)` chama `POST /api/embed` (`input` como lista, `truncate: true`, `keep_alive` igual ao do chat) e devolve uma lista de vetores.
   - Um `Embedder` (`engrama/services/language/embedder.py`) envolve o cliente: normaliza o vetor (norma 1), corta texto longo, aplica o prefixo de tarefa do modelo quando ele pede (consulta × documento), guarda o estado (`off`, `missing`, `cold`, `ready`, `failed`) e desliga por um tempo depois de um erro.
   - O estado `missing` vem do `tags()` que já existe, consultado no máximo a cada `EMBED_CHECK_S`, nunca na thread da UI.
2. **Vetores na memória.**
   - Tabela `vectors` na `memory.sqlite` (schema v3, migração do v2 sem perda): tipo (`episode`, `fact`, `topic`, `ancestral`), referência (id do episódio, chave do fato, nome do tópico), modelo, dimensão, hash do texto, vetor (`float16`) e data.
   - O texto que vira vetor é sempre um texto **que já está na memória**: o resumo do episódio, "chave: valor" do fato, o nome do tópico, o resumo ancestral. Nada mais.
   - Um vetor cujo hash não bate com o texto atual (fato que mudou de valor) é ignorado e reindexado.
   - Para buscar, a memória monta uma matriz `float32` só dos vetores do modelo atual, em cache, refeita quando os vetores mudam, e calcula o cosseno com numpy. A matriz só existe enquanto o modelo de embedding está em uso; ao descarregar, é liberada.
3. **Indexação em segundo plano.**
   - Um job novo de prioridade mais baixa que os do M4 (chat 0 > comentário 1 > reflexão 2 > fatos 3 > **índice 4**) pega até `EMBED_BATCH` textos sem vetor e grava os vetores.
   - Só roda com o LLM de conversa `ready` e `idle()` (a mesma regra do M4); nunca inicia o Ollama nem carrega modelo por conta própria.
   - Item apagado enquanto o lote estava no Ollama não tem o vetor gravado (a gravação confere que a referência ainda existe com o mesmo texto).
4. **Recuperação híbrida** (`recall.py`).
   - `recall(memory, text, stage, lang, qvec=None)`: com `qvec is None` o resultado é **idêntico** ao do M4/M8 (mesmo código).
   - Com `qvec`, para episódios, ancestrais, fatos e opinião:
     - relevância = `W_SEM`·`sim'` + `W_WORD`·`overlap`, com `sim'` = cosseno reescalado a partir de `SEM_MIN_SIM` (abaixo dele, 0);
     - episódios: pontuação = `W_IMPORTANCE`·importância + `W_RECENCY`·recência + `W_RELEVANCE`·relevância (valores no bloco `# Task M9` do plano);
     - fatos: os de `sim ≥ FACT_MIN_SIM` entram junto com os achados por palavra, ordenados por relevância; sem nenhum, o fallback do M4 (os mais confiáveis);
     - opinião: se nenhuma palavra casa com um tópico, o tópico mais próximo com `sim ≥ TOPIC_MIN_SIM` e opinião;
     - ancestrais: o mais próximo com `sim ≥ SEM_MIN_SIM`, ou o achado por palavra.
   - Os limites de quantidade do M4 não mudam (3 fatos, 2 episódios, 1 ancestral) nem a regra de dígitos.
5. **Consulta na hora do chat.**
   - O vetor da mensagem é pedido na thread do serviço de linguagem, logo antes do prompt, só se o `Embedder` está `ready`, com tempo limite `EMBED_QUERY_TIMEOUT_S`. Erro ou tempo esgotado: `qvec = None` (M4).
   - O modelo de embedding é aquecido junto com o de conversa (depois dele, no mesmo `warm`) e descarregado junto (`unload`, descanso, `keep_alive`).
   - Também a fala espontânea (`_spontaneous`) e a resposta adiada (`_answer_pending`) usam a mesma consulta.
6. **Apagar continua definitivo.** Todo caminho que apaga uma memória apaga o vetor dela na mesma transação: apagar fato, apagar tópico, esquecer tudo, tetos, compactação, nova geração e troca de modelo.
7. **Interface.**
   - F5: linha "Busca por significado" (modelo recomendado, instalado ou não, baixar, ligar/desligar).
   - F7: uma linha de estado sem números.
   - F2 (Visão da Mente): vetores / memórias e o estado do modelo (números permitidos).
   - PT/EN em todo texto novo.
8. **README** PT/EN: o que é a busca por significado, como baixar o modelo, que sem ele tudo funciona como antes, e o que acontece ao apagar.

## 4. Não objetivos

- Banco vetorial ou índice aproximado (FAISS, `sqlite-vss`, `sqlite-vec`, hnswlib): com no máximo ≈2.600 vetores (tetos do M4), a busca exata com numpy custa poucos milissegundos.
- Embedding feito em Python (sentence-transformers, onnxruntime): só o Ollama, que já é dependência externa.
- Usar o significado para **agir** (o árbitro, a mente, o kernel). Como no M4, a memória influencia só a fala.
- Agrupar memórias por significado, deduplicar fatos parecidos, formar tópicos por clusters ou mudar a compactação do M4.
- Indexar texto que não está na memória: títulos de janela, nomes de processo, conteúdo de arquivo arrastado.
- Lista de "lembranças parecidas" no painel (fica para depois, ver §2).
- Baixar o modelo de embedding sem o usuário pedir.

## 5. Anti-objetivos (falha mesmo que "funcione")

- O comportamento sem modelo de embedding diferir do M8 em qualquer coisa (prompt, fala, banco, CPU).
- O app carregar um modelo no Ollama só para indexar ou para buscar, sem conversa.
- Uma chamada de embedding na thread da UI ou da simulação, ou uma exceção do embedder chegar a elas.
- O chat ficar perceptivelmente mais lento: a consulta só acontece com o modelo já aquecido e com tempo limite curto.
- Um vetor sobreviver ao apagamento da memória de onde saiu, ou um vetor de algo apagado ser gravado por um job atrasado.
- Vetores de dois modelos comparados entre si.
- Lembrar por significado algo sem relação com a mensagem e repetir sempre a mesma memória (o limiar `SEM_MIN_SIM` existe para isso).
- Título cru, nome de processo ou conteúdo de arquivo virarem vetor (ou irem ao Ollama como texto de embedding).
- O banco crescer além dos tetos do M4 por causa dos vetores (um vetor por item, no máximo).
- Afrouxar ≤150 MB / ≤2% de CPU.

## 6. Restrições

Todas as restrições globais dos marcos anteriores continuam valendo:
- `EVENT_KINDS`, `ACTIONS`, `FOOD_IDS`, `NEED_KEYS`, `CHANNELS`, `DIGITAL_IDS`, `VARIANTS`, `DISPLAY_MODES` não mudam;
- kernel determinístico; o lab fica bit-idêntico ao M8;
- regras de importação de `tests/test_architecture.py`;
- ≤150 MB RSS e ≤2% de CPU médio no bench sem LLM, sem mudar os limites dos testes;
- PT/EN em todo texto novo; sem números no modo normal;
- local e offline; dependências: pygame-ce, numpy, psutil (nenhuma nova); commits sem atribuição a IA.

Além disso:
- **A memória não conhece o Ollama.** `engrama/services/memory/**` não importa `engrama.services.language`; recebe e devolve vetores numpy. Quem chama o Ollama é o `Embedder`, no serviço de linguagem. Só o host liga as peças.
- **Nada de embedding fora das threads do serviço de linguagem** (o worker `language-service` e a `language-io` do aquecimento; em `sync=True`, o `pump()` dos testes).
- **Tempo limite** em toda chamada: consulta `EMBED_QUERY_TIMEOUT_S`, lote `EMBED_BATCH_TIMEOUT_S`. Depois de um erro, o embedder fica `failed` por `EMBED_RETRY_S`.
- **Testes não precisam de Ollama.** Um `FakeEmbedder` determinístico (tabela de conceitos PT/EN) faz o papel do modelo; nenhum teste automático fala com o Ollama de verdade.
- **Schema v3 com migração.** Um banco do M8 (v2) abre no M9 sem perder nada; um banco corrompido continua sendo posto de lado como no M4.
- **Privacidade do M5 igual.** Os textos de embedding são os que já estão na memória; a mensagem do usuário vai ao Ollama local como já vai para o chat.

## 7. Critérios de aceitação

Testes headless com `FakeEmbedder`, cliente LLM falso e relógio falso, salvo indicação:

1. **Lembra pelo sentido.** No dia 1 o usuário conta "adotei um cachorro, o nome dele é Biscoito". No dia 5 diz "meu bichinho anda doente" (nenhuma palavra em comum). Com o embedder, o prompt de sistema traz o episódio ou o fato do cachorro; sem o embedder, não traz (é o M4).
2. **Entre idiomas.** Uma mensagem em EN ("my dog is sick") traz a memória gravada em PT.
3. **Sem modelo = M4, igual.** Para um roteiro fixo de memórias e mensagens, `recall` e as mensagens do prompt são idênticas ao gabarito gravado do M8 nestes casos: embedder ausente, modelo não instalado, Ollama parado, `--no-llm`, tempo esgotado, exceção no embedder, índice vazio.
4. **Não carrega modelo sozinho.** Com o LLM `offline` ou `loading`, o embedder não é chamado nenhuma vez (contador em 0), nem para indexar nem para consultar. Com `ready` e `idle`, o índice anda em lotes de no máximo `EMBED_BATCH`.
5. **Fora da UI.** Com `sync=False`, toda chamada ao embedder acontece nas threads do serviço de linguagem (`language-service`, ou `language-io` no aquecimento), nunca na thread principal nem na da simulação.
6. **Apagar apaga o vetor.** Depois de apagar um fato, um tópico, de "esquecer tudo", dos tetos, da compactação e de uma nova geração, não sobra linha em `vectors` para referência que não existe, e `similar()` nunca devolve item apagado. Um lote em voo para um item apagado não grava o vetor.
7. **Troca de modelo.** Trocar `embed_model` apaga os vetores do modelo antigo; a busca nunca mistura modelos; a reindexação refaz tudo em segundo plano. Desligar a busca apaga todos os vetores.
8. **Migração.** Uma `memory.sqlite` do M8 abre como v3 com episódios, fatos, tópicos, opiniões, ligações e bloqueios intactos.
9. **Limitado.** Em 30 dias simulados, o número de vetores ≤ episódios + fatos + tópicos + ancestrais, e a matriz em memória ≤ `VECTOR_RAM_MAX_MB`.
10. **Rápido.** Com os tetos do M4 cheios (2.000 episódios, 300 fatos, 300 tópicos, 768 dimensões), um `recall` com `qvec` leva ≤ `SEARCH_BUDGET_MS` na máquina de referência.
11. **Gerações.** O arquivo da geração não tem vetores (se a recomendação for aceita); a geração nova começa só com os vetores das ancestrais (reindexadas pela regra normal); um ancestral é lembrado pelo sentido.
12. **Orçamento.** O bench sem LLM continua ≤150 MB e ≤2% de CPU (o M9 não acrescenta nada a esse caminho).
13. **Robustez.** Respostas estranhas do Ollama (`embeddings` vazio, dimensão diferente da anterior, `NaN`, erro HTTP, modelo que não faz embedding) viram `failed` ou `None` sem exceção para fora.
14. **Lab e vocabulário:** a corrida curta do lab é idêntica à do M8; as tuplas do vocabulário não mudam.
15. **Smoke manual** na máquina de referência, com o modelo baixado pelo F5, relatado no PR: conversa sobre um assunto, outra conversa dias depois (escala de tempo do modo dev) com outras palavras, e a criatura retoma o assunto; a latência medida de uma consulta e de um lote.

## 8. O que fica com o builder

- O formato exato da tabela `vectors` e da migração v2 → v3.
- A tabela de prefixos de tarefa por família de modelo (por exemplo `embeddinggemma`: "task: search result | query: " e "title: none | text: "; `nomic-embed-text`: "search_query: " e "search_document: "); modelo desconhecido vai sem prefixo.
- A calibração de `SEM_MIN_SIM`, `FACT_MIN_SIM` e `TOPIC_MIN_SIM` com o modelo recomendado, quando instalado; os valores do bloco `# Task M9` do plano são o ponto de partida.
- A tabela de conceitos do `FakeEmbedder`.
- O texto da linha do F5, do F7 e da Visão da Mente.
- Como o cache da matriz é invalidado (contador de versão dos vetores, recomendado).
- Como a `ModelsPanel` mostra a linha de embedding sem mexer no fluxo dos modelos de conversa.

## 9. Decisões minhas (para o usuário conferir)

- **Embedding no serviço de linguagem, vetores na memória.** O `Embedder` mora em `services/language` (é quem fala com o Ollama); a memória só guarda e compara vetores. A memória continua sem saber que existe um LLM.
- **Mesma fila do LLM, prioridade nova 4.** A indexação é o job menos importante. Não há thread nova: o worker do `LanguageService` já é a única thread que fala com o Ollama.
- **O modelo de embedding acompanha o de conversa.** Aquecido no fim do `warm`, descarregado no `unload` e no descanso, com o mesmo `keep_alive`. Assim ele nunca fica carregado sem conversa, e a consulta não paga o carregamento.
- **Consulta só com o embedder `ready`.** Enquanto o LLM está `loading`, a resposta é balbucio (M4) e não precisa de memória por significado; a resposta adiada faz a consulta quando o modelo fica pronto.
- **Paridade por gabarito.** Antes de mexer no código, a Tarefa 0 grava, com o código do M8, o `RecallContext` e as mensagens do prompt para um roteiro fixo. Os testes do M9 comparam o caminho sem modelo com esse arquivo.
- **`float16` no disco, `float32` na memória.** 2.600 × 768 × 2 bytes ≈ 4 MB no disco; a matriz `float32` ≈ 8 MB, só enquanto o embedder está em uso.
- **`PRAGMA secure_delete = ON`** na conexão da memória, para que o texto e o vetor apagados não fiquem nas páginas livres do arquivo. O custo é pequeno com os tetos do M4.
- **Nenhum texto novo chega ao Ollama.** O que vira vetor já está gravado na memória, e a consulta é a própria mensagem do usuário (que já vai para o chat). Episódios de atividade (M5) têm só o tema, nunca o título.
- **`Config`:** `embed_model: str = "embeddinggemma"` e `semantic_recall: bool = True`. Vazio ou `False` = desligado.
- **Versão 0.9.0.**

## 10. Medições na máquina de referência

Máquina: CachyOS, Hyprland, AMD Ryzen 5 7520U (4 núcleos / 8 threads), 7,2 GB de RAM (≈4,3 GB livres), Ollama 0.18.3 como serviço systemd (`/usr/local/bin/ollama serve`, usuário `ollama`).

| Medida | Valor |
|---|---|
| `ollama list` / `GET /api/tags` | **nenhum modelo instalado** (nem o `qwen3:1.7b` de conversa, nem modelo de embedding) |
| Latência de `/api/embed` | **não medida**: não há modelo instalado e o pedido foi não baixar nenhum |
| Custo da busca (estimativa) | matriz 2.600 × 768 `float32` (≈8 MB), produto matriz-vetor com numpy: ordem de 1 ms |
| Tamanho dos vetores (estimativa) | ≈4 MB no disco em `float16` com os tetos do M4 cheios |

Consequências:
- `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM`, `EMBED_QUERY_TIMEOUT_S` e `EMBED_BATCH_TIMEOUT_S` são valores de partida; a Tarefa 6 mede com o modelo recomendado instalado pelo usuário e ajusta, registrando a tabela no PR.
- Sem modelo, a máquina de referência roda o caminho do M4, que é exatamente o que o critério 3 exige.

## 11. Revisão — pontos de risco

1. **Paridade sem modelo:** qualquer mudança no caminho `qvec is None` quebra o critério 3. O código do M4 fica como está e o significado entra só como camada nova.
2. **Corrida entre apagar e indexar:** o lote sai do banco, vai ao Ollama por segundos, e o usuário apaga o item no F7 nesse meio tempo. A gravação confere existência e hash dentro do lock.
3. **Troca de modelo no meio de um lote:** o lote antigo não pode gravar vetores com o nome do modelo novo nem do antigo depois da troca.
4. **Dimensão diferente** devolvida pelo mesmo nome de modelo (modelo trocado por outro com o mesmo nome no Ollama): os vetores antigos são descartados como numa troca.
5. **Latência do chat:** o modelo de embedding frio pode levar segundos para carregar; por isso a consulta só acontece com o embedder `ready`.
6. **Limiar ruim:** limiar baixo demais traz memória sem relação em toda fala (anti-objetivo do M4). O gabarito de "não relacionado" do `FakeEmbedder` e a calibração com o modelo real cobrem isso.
7. **RAM do Ollama:** com 7,2 GB, `qwen3:1.7b` (≈1,4 GB) mais `embeddinggemma` (≈0,6 GB) cabem; `bge-m3` (≈1,2 GB) aperta. Essa memória é do processo do Ollama, fora do orçamento de 150 MB do Engrama.
