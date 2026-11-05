# Engrama M13: Calibração com modelos reais, plano de implementação

**Objetivo:** medir, com o `qwen3:1.7b` e o `embeddinggemma` de verdade, se a conversa e a memória funcionam como prometido, e ajustar com base nos números:
- persona e fala por estágio sem cara de atendente;
- limiares da busca por significado escolhidos por dados, não pelo chute do M9;
- os smokes manuais pendentes de M3–M9 executados (o que a máquina consegue) ou entregues como checklist curta (o que precisa de humano).

**Roadmap:** `docs/superpowers/specs/2026-11-04-engrama-m12-m15-roadmap.md` (seção M13). Parte de `main` com o M12 mergeado.

**Execução:** orquestração pelo Opus; subagentes Sonnet (harness, dataset, análise e ajuste) e Haiku (scripts mecânicos, docs) em worktrees no scratchpad da sessão, partindo da branch `m13`. Um PR no fim. **Sem** linhas de coautoria de IA em commits e PR.

**Ambiente:** Ollama do sistema (`systemctl` ativo, `ollama` no `PATH`) com `qwen3:1.7b` e `embeddinggemma:latest` já baixados. Máquina de dev: Ryzen 5 1600, 16 GB, GPU NVIDIA (o alvo é um notebook sem GPU dedicada; latências medidas aqui são o melhor caso e o relatório diz isso).

## Restrições globais

- **Quem decide as ações continua sendo a mente.** Nada em `engrama/kernel/**`, `engrama/mind/**`, `engrama/modules/**`, `engrama/lab/**`, `recipes/**`.
- Podem mudar: `engrama/services/language/persona.py` (prompts, few-shot, `ASSISTANT_RE`), `engrama/services/memory/__init__.py` (só os limiares `SEM_MIN_SIM`, `FACT_MIN_SIM`, `TOPIC_MIN_SIM` e, se os dados pedirem, `W_SEM`/`W_WORD`), `tools/`, `docs/`, testes.
- **A suíte continua sem Ollama.** O harness e a calibração são ferramentas em `tools/`, não testes. Testes novos usam fakes.
- Mudou limiar ou prompt → atualizar `tests/services/memory/test_golden.py` (que fixa os valores) e qualquer teste de prompt, no mesmo commit, explicando no relatório.
- Nada de dado pessoal real nos roteiros e no dataset: só frases inventadas.
- `SAVE_VERSION`, schema, `vocab` e i18n intocados.
- Saídas grandes (transcrições cruas) vão para `docs/superpowers/reports/m13/` em JSON; o relatório em Markdown resume.

## Tarefas

Ordem: **{T1, T2} em paralelo → {T3, T4} em paralelo → T5 → T6**.

### T1: Harness de conversa (Sonnet)

Arquivo novo: `tools/smoke_llm.py` (+ `tools/smoke_scripts.json` com os roteiros).
- [ ] Roteiros em PT e EN para os estágios `baby`, `child`, `adult`, `perfect`, `final`. Cada roteiro tem de 6 a 10 falas do usuário: cumprimento, pergunta direta ("o que você é?"), pedido de ajuda típico de assistente ("me ajuda com meu código?"), um fato pessoal inventado ("meu gato se chama Bolota"), assunto do dia, provocação, despedida. Variar traços (`traits`) e humor (`mood`) entre 2 perfis por estágio.
- [ ] Caminho de execução: usar o `LanguageService` real com `MemoryStore` real numa pasta temporária, `WorkingMemory`, `get_state` devolvendo `PersonaState` do roteiro e o cliente Ollama real. Se montar o serviço for inviável fora do app, usar `persona.build_messages` + `client.chat` + `clean_reply` com os mesmos parâmetros do serviço (`num_predict`, `temperature`, `keep_alive`), e dizer qual caminho foi usado.
- [ ] Métricas por fala: texto cru, texto limpo, se foi **rejeitado** (`clean_reply` devolveu `None`: virou balbucio), qual regra rejeitou (atendente, vazio, bloco think), número de palavras e o limite do estágio, idioma detectado (`lang.py`), latência. Por roteiro: taxa de rejeição, taxa de "atendente" no texto **cru**, aderência ao tamanho, idioma certo, se o fato inventado foi extraído para `facts` e citado depois.
- [ ] Saída: `--out DIR` grava `transcripts.json` e `summary.md`. `--seed`, `--stages`, `--langs`, `--repeat N` (padrão 3, porque o modelo é estocástico).
- [ ] Rodar uma vez completo e anexar o `summary.md` no relatório da tarefa. Medir a latência média e o p95 por estágio.
- [ ] Teste unitário pequeno com cliente fake para o cálculo das métricas (sem Ollama).

### T2: Dataset rotulado e script de calibração (Sonnet para o dataset, Haiku para o script)

Arquivos novos: `tools/data/sem_pairs.jsonl`, `tools/calibrate_sem.py`.
- [ ] Dataset de cerca de 240 pares `{"kind": "episode|fact|topic", "query": ..., "memory": ..., "match": true|false, "lang": "pt|en|cross"}`, mais ou menos 1/3 PT, 1/3 EN e 1/3 cruzado. Para cada tipo de memória, use o formato que o app grava de verdade: `_vtext` e os textos indexados em `store/vectors.py`, e as chaves de fato do `parse_facts`. Ver como `recall.py` monta a consulta. Incluir **negativos difíceis** (mesmo tema, outro referente: "meu gato" contra "o gato do vizinho"; mesma palavra, outro sentido).
- [ ] Script: embute consultas e memórias com `embeddinggemma` pelo `client.embed` do app, usando o mesmo pré-processamento do app, e calcula o cosseno. Para cada `kind`, varre limiares de 0,30 a 0,90 em passos de 0,01 e reporta precisão, recall e F1, além do limiar de F1 máximo e do menor limiar com precisão ≥ 0,90. Saídas: `--out` JSON e uma tabela Markdown, com histograma de positivos e negativos em texto.
- [ ] Rodar e anexar a saída.

### T3: Ajuste da persona (Sonnet), depois de T1

- [ ] Ler o `summary.md` da T1. Atacar, em ordem:
  1. respostas rejeitadas por cara de atendente (o modelo cai no padrão de assistente);
  2. idioma errado;
  3. resposta longa demais ou curta demais para o estágio;
  4. fato contado e não usado.
- [ ] Ajustar `persona.py`: system prompt, few-shot por estágio e, se necessário, `ASSISTANT_RE` (só para **adicionar** padrões vistos nas transcrições; nunca afrouxar).
- [ ] Rodar o harness de novo com o mesmo `--seed` e `--repeat`, e comparar antes e depois numa tabela. **Meta:** frases de atendente no texto final = 0; rejeição total ≤ 10% nos estágios que falam (`child` em diante); idioma certo ≥ 95%.
- [ ] Testes de persona existentes passam; atualizar os que fixam o texto do prompt, justificando no relatório.

### T4: Aplicar os limiares (Haiku), depois de T2

- [ ] Escolha:
  - `FACT_MIN_SIM` e `TOPIC_MIN_SIM`: o menor limiar com precisão ≥ 0,90 (fato errado é pior que fato esquecido);
  - `SEM_MIN_SIM` (episódios e ancestrais): o de F1 máximo;
  - arredondar para 2 casas.
  Se a escolha cair a menos de 0,03 do valor atual, manter o atual e registrar.
- [ ] Atualizar `engrama/services/memory/__init__.py` e `tests/services/memory/test_golden.py`. Rodar `tests/services/memory` e `tests/test_m9_acceptance.py` (exceto `perf`).
- [ ] Se algum teste com embedder fake depender do valor antigo de forma frágil, ajustar o fake (não o código).

### T5: Smokes manuais (orquestrador + Sonnet)

- [ ] Juntar as checklists de smoke manual dos planos M3, M5, M8 e M9 (`docs/superpowers/plans/`). Classificar cada item:
  - **A**: automatizável aqui (headless com driver dummy e Ollama real: conversa, extração de fato, recall entre idiomas, apagar fato no F7 via provider e conferir que some, desligar a busca e conferir que a conversa segue);
  - **H**: precisa de humano (janela real, atalhos, tela cheia, Windows, X11).
- [ ] Executar os itens A com um script descartável no scratchpad, usando `Host` + serviços reais, e registrar o resultado.
- [ ] Gerar `docs/superpowers/reports/2026-11-04-m13-smokes.md` com os resultados A e a checklist H curta, em português, com o passo a passo para o usuário, incluindo o que observar.

### T6: Relatório, docs e PR (Haiku para docs, orquestrador para o PR)

- [ ] `docs/superpowers/reports/2026-11-04-m13-calibracao.md`:
  - ambiente;
  - tabela antes e depois do harness;
  - tabela de limiares (antigo → novo, precisão e recall);
  - latências;
  - o que mudou no prompt;
  - limitações (estocasticidade, máquina de dev com GPU, dataset sintético).
- [ ] README PT/EN:
  - tirar "sem calibração com modelo real" das limitações;
  - linha M13 no roadmap;
  - mencionar `tools/smoke_llm.py` e `tools/calibrate_sem.py` na seção de desenvolvedores.
- [ ] `version = "0.13.0"`.
- [ ] `ruff check .` e a suíte (`-n auto`) verdes; push; PR com os resumos e a checklist H para o usuário.

## Aceite do M13

1. Relatório com transcrições: frases de atendente no texto final = 0, rejeição ≤ 10% a partir de `child`, idioma certo ≥ 95% (média de 3 repetições).
2. Limiares escolhidos por dados, com precisão e recall publicados por tipo de memória.
3. Itens A dos smokes executados e relatados; checklist H entregue ao usuário.
4. Suíte e lint verdes na CI (Linux e Windows), sem depender de Ollama.

## Riscos

| Risco | Mitigação |
|---|---|
| Modelo pequeno não segue o prompt de forma estável | `--repeat 3` e metas em média; se a meta não fechar, registrar o melhor resultado e propor alternativas no relatório (outro modelo pequeno, temperatura), sem trocar o padrão sem o usuário |
| Dataset sintético não representa a memória real | Usar o formato real dos textos indexados; negativos difíceis; dizer a limitação no relatório |
| Ajuste de prompt quebra testes que fixam texto | Atualizar os testes no mesmo commit com justificativa |
| Latência alta em CPU (alvo sem GPU) | Medir também com `CUDA_VISIBLE_DEVICES=` (Ollama em CPU) se for possível sem mexer no serviço do sistema; senão, registrar como limitação |
