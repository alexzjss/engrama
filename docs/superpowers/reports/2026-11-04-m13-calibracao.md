# M13: calibração da persona e dos limiares, com modelo real

Este relatório fecha o M13. Ele junta os números das duas rodadas do harness de conversa (antes e depois do ajuste de persona), a calibração dos limiares da busca por significado e os resultados dos smokes. Os dados brutos estão em:

- [`m13/compare.md`](m13/compare.md): tabela antes e depois, por estágio;
- [`m13/baseline/summary.md`](m13/baseline/summary.md) e [`m13/baseline/transcripts.json`](m13/baseline/transcripts.json): rodada antes do ajuste;
- [`m13/after/summary.md`](m13/after/summary.md) e [`m13/after/transcripts.json`](m13/after/transcripts.json): rodada depois do ajuste;
- [`m13/calibration.md`](m13/calibration.md) e [`m13/calibration.json`](m13/calibration.json): calibração dos limiares;
- [`2026-11-04-m13-smokes.md`](2026-11-04-m13-smokes.md): smokes manuais (itens automatizáveis) e checklist humana.

## Ambiente

- Modelo de conversa: `qwen3:1.7b`. Embedding: `embeddinggemma`.
- Ollama 0.18.3, como serviço do sistema, rodando em CPU (VRAM em 0 MiB para os dois modelos nas duas rodadas).
- Máquina: Linux (cachyos), CPU only, cerca de 7 GB de RAM. É próxima do notebook alvo e não é o melhor caso com GPU. As latências abaixo valem para esse cenário.
- Harness: `tools/smoke_llm.py`, com `--repeat 1 --seed 0`, pelo `LanguageService` real, `MemoryStore` em pasta temporária, `WorkingMemory` e cliente Ollama real.

## Persona antes e depois

Tabela copiada de [`m13/compare.md`](m13/compare.md). Cada célula é "antes -> depois". Uma linha equivale a 3% dentro de um estágio.

| stage | rej. % (final) | 1st-try rej. % | assistant in raw % | assistant in FINAL text (lines) | length ok % | lang ok % | fact extracted % | fact used % | lat mean s |
|---|---|---|---|---|---|---|---|---|---|
| baby | 0 -> 0 | 3 -> 0 | 3 -> 0 | 0 -> 0 | 97 -> 88 | 97 -> 100 | 25 -> 25 | 0 -> 0 | 10.8 -> 8.3 |
| child | 0 -> 3 | 0 -> 3 | 0 -> 3 | 2 -> 0 | 78 -> 97 | 100 -> 100 | 75 -> 50 | 25 -> 25 | 11.7 -> 8.3 |
| adult | 9 -> 9 | 9 -> 6 | 9 -> 6 | 5 -> 1 | 100 -> 100 | 100 -> 97 | 75 -> 75 | 25 -> 0 | 11.9 -> 9.8 |
| perfect | 3 -> 3 | 12 -> 9 | 12 -> 9 | 9 -> 0 | 100 -> 100 | 100 -> 100 | 50 -> 75 | 50 -> 0 | 12.2 -> 10.1 |
| final | 3 -> 6 | 9 -> 3 | 9 -> 3 | 9 -> 0 | 100 -> 100 | 100 -> 100 | 75 -> 75 | 25 -> 25 | 10.5 -> 10.0 |

All: rejected 3.1% -> 4.4%, 1st-try rejected 6.9% -> 4.4%, assistant in raw 6.9% -> 4.4%, length ok 95.0% -> 96.9%, lang ok 99.4% -> 99.4%. Immediate repeats: 2 -> 0.

Leitura honesta: o padrão de atendente caiu de forma clara (no texto cru, 6,9% -> 4,4%; no texto final, 9 linhas -> 1). A rejeição total subiu de 3,1% para 4,4% (diferença de 2 linhas em 160), dentro do ruído de uma rodada. Os fatos em "fact used" não melhoraram, e os números de fatos dessa tabela são anteriores à correção do T5 (ver a seção de prompt).

Além disso, `fact used` e `fact extracted` medem só um roteiro por célula, então as diferenças de 25 pontos são de uma linha.

## Limiares

A calibração usou 240 pares rotulados (`tools/data/sem_pairs.jsonl`, 80 por tipo de memória, 36 positivos e 44 negativos em cada tipo), com cosseno do `embeddinggemma` e o mesmo pré-processamento do app. Os valores vêm de [`m13/calibration.md`](m13/calibration.md).

| Tipo de memória | Constante | Antigo | Novo | Precisão antiga | Recall antigo | Precisão nova | Recall novo |
|---|---|---|---|---|---|---|---|
| episódio | `SEM_MIN_SIM` | 0,50 | 0,42 | 1,000 | 0,583 | 0,912 | 0,861 |
| fato | `FACT_MIN_SIM` | 0,60 | 0,46 | 1,000 | 0,083 | 0,938 | 0,417 |
| assunto (opinião) | `TOPIC_MIN_SIM` | 0,60 | 0,27 | – (nada previsto) | 0,000 | 0,914 | 0,889 |

Referências da própria calibração, para contexto:

- Episódio, melhor F1 em 0,32: precisão 0,837, recall 1,000, F1 0,911.
- Fato, melhor F1 em 0,29: precisão 0,686, recall 0,972, F1 0,805.
- Assunto, melhor F1 em 0,26: precisão 0,895, recall 0,944, F1 0,919.

Critério: para `FACT_MIN_SIM` e `TOPIC_MIN_SIM`, o menor limiar com precisão ≥ 0,90 (fato errado é pior que fato esquecido). Para `SEM_MIN_SIM`, o plano previa o limiar de F1 máximo, que é 0,32. O valor aplicado é 0,42, o menor limiar com precisão ≥ 0,90, e é um desvio deliberado da regra do plano: em 0,32 a precisão cai para 0,837, ou seja, cerca de um episódio em seis injetado no prompt não tem relação com a mensagem, e a criatura passa a falar de coisas que não vieram ao caso. Em 0,42 o F1 é 0,886, contra 0,911 no máximo, com a mesma regra de precisão usada para fatos e assuntos. O custo é o recall entre idiomas (0,667), registrado nas limitações.

Quebra por idioma nos limiares escolhidos (precisão / recall):

- Episódio (0,42): PT 0,857 / 1,000; EN 1,000 / 0,917; cruzado 0,889 / 0,667.
- Fato (0,46): PT 0,875 / 0,583; EN 1,000 / 0,500; cruzado 1,000 / 0,167.
- Assunto (0,27): PT 0,800 / 1,000; EN 1,000 / 0,750; cruzado 1,000 / 0,917.

O recall cruzado de fato (0,167) é baixo. Com esse limiar, o app quase não encontra um fato dito em outro idioma. É um custo aceito pela regra de precisão, mas precisa ser lembrado.

## Latências

Medidas em CPU, na máquina descrita em Ambiente. Tempo de resposta em segundos, por estágio (média / p95), de [`m13/baseline/summary.md`](m13/baseline/summary.md) e [`m13/after/summary.md`](m13/after/summary.md).

| stage | antes (média / p95) | depois (média / p95) |
|---|---|---|
| baby | 10,85 / 12,95 | 8,26 / 9,81 |
| child | 11,68 / 14,65 | 8,35 / 10,07 |
| adult | 11,87 / 15,87 | 9,79 / 13,22 |
| perfect | 12,19 / 15,96 | 10,08 / 14,42 |
| final | 10,45 / 15,47 | 10,04 / 14,33 |
| **todas** | **11,41 / 15,15** | **9,30 / 13,16** |

Os dois runs não tiveram o ajuste de `num_ctx` do aquecimento (commit `a7a3e85`), que evitava recarregar o modelo na primeira resposta. O `compare.md` avisa que as latências não são estritamente comparáveis entre as rodadas. Nos smokes manuais, a resposta levou cerca de 8 a 10 s, mais alguns segundos de extração de fatos que rodam em segundo plano sem atrasar a fala.

## O que mudou no prompt e na extração de fatos

Persona (`engrama/services/language/persona.py`, commits `16b51e3`, `a83aba0` e `0b5329d`):

- Removida a referência a Digimon no prompt do sistema, nos dois idiomas.
- Regra explícita: o Engrama não é ferramenta, nunca oferece ajuda e nunca escreve código. Se perguntarem quem ele é, responde curto e em personagem, sem recitar necessidades ou status.
- Falas da criança com no máximo 8 palavras (antes: "frases curtas e simples").
- Few-shots reescritos por estágio, sem a frase de atendente. Os de `full` agora cobrem "quem é você?" e "me ajuda com meu código?", com respostas em personagem.
- Concordância em português feminino para o estado da criatura (entediada, curiosa, tranquila).
- `ASSISTANT_RE` ganhou padrões vistos nas transcrições (oferta de ajuda, código, "let me know if/what/how"). Nenhum padrão foi afrouxado.
- Resposta repetida: se a fala for igual a uma das últimas três, o serviço tenta de novo com temperatura 0,9 e, se repetir, usa balbucio.

Recall (commit `d1b6bb7`): só entram no prompt os fatos que casam com a mensagem. Antes, valia uma reserva de dois fatos mesmo sem relação.

Extração de fatos (commit `7f59682` e, depois, `70645c8`):

- Prompt de extração mais restrito: só fatos duradouros que o próprio usuário afirma sobre si, sem perguntas, sem falas da criatura ou de um assistente e sem clima ou acontecimentos de um dia só.
- Filtro determinístico (`sanitize_facts`): descarta perguntas, valores sim/não, menções a assistente ou IA, chaves e valores curtos demais e chaves formadas só por palavras vazias.
- Correção do T5 (commit `70645c8`): `ground_facts` só guarda um fato se todas as palavras do valor aparecem na fala do próprio usuário (sem acento, sem caixa, palavras inteiras). Isso barra o caso em que o modelo repete o exemplo do prompt ("Bolota", "Pumpkin") como se o usuário tivesse dito, o que criava fatos inventados e furava o apagamento do F7.
- Exemplo de hobby no prompt, PT e EN ("eu toco ukulele" -> `hobby = ukulele`; "I play ukulele" -> `hobby = ukulele`). Antes, "eu toco ukulele nas sextas" não guardava nada em 3 de 3 chamadas; depois, guardou `hobby = ukulele` em 2 de 2.
- Limite do filtro: valores parafraseados são descartados. É o lado conservador, e fatos reais costumam ser nomes, números e substantivos ditos literalmente.

Os números de fatos de `compare.md` são anteriores ao commit `70645c8`. A checagem depois da correção está nos smokes (seção 3 de [`2026-11-04-m13-smokes.md`](2026-11-04-m13-smokes.md)).

## Aceite

Critérios do plano, na ordem do documento.

1. **Relatório com transcrições, atendente = 0 no texto final, rejeição ≤ 10% a partir de `child`, idioma certo ≥ 95% (média de 3 repetições).**
   - Transcrições: **atendido**. Existem `transcripts.json` para antes e depois.
   - Frases de atendente no texto final = 0: **não atendido**. Na rodada depois, há 1 linha de 160 (adult, pt-b: "não importa, sou aqui pra te ajudar se quiser."). Ela só foi pega pelo regex depois, com o padrão `pra (te )?ajudar`, então o número medido na rodada é 1, não 0.
   - Rejeição ≤ 10% a partir de `child`: **atendido na média**. Somando os estágios child, adult, perfect e final (128 falas), foram 7 rejeições, 5,5%. O estágio adult sozinho ficou em 9%, e adult em português em 12% (2 de 16).
   - Idioma certo ≥ 95% (média de 3 repetições): **não verificado no formato exigido**. A rodada depois deu 99,3% com uma repetição só (`--repeat 1`). O valor passa de 95%, mas a média de 3 repetições não foi feita.
2. **Limiares escolhidos por dados, com precisão e recall publicados por tipo de memória.**
   - Publicado: **atendido** (tabela de limiares acima e `m13/calibration.md`).
   - Escolha por dados: **atendido para fato e assunto** (critério de precisão ≥ 0,90 do plano). **Desvio deliberado para episódio**: o plano previa o limiar de F1 máximo (0,32); o aplicado é 0,42 (precisão ≥ 0,90), com o motivo na seção de limiares.
3. **Itens A dos smokes executados e relatados; checklist H entregue ao usuário.**
   - **Atendido.** Os 11 itens A (desdobrados de 5 do plano) passaram na última execução, depois da correção. Na primeira execução, o A8b falhou por causa do fato fantasma, que foi corrigido pelo commit `70645c8`. A checklist H de 12 itens está na seção 4 de [`2026-11-04-m13-smokes.md`](2026-11-04-m13-smokes.md).
4. **Suíte e lint verdes na CI (Linux e Windows), sem depender de Ollama.**
   - **Não verificado neste relatório.** Neste passo rodou-se só `ruff check .`. A suíte completa não foi rodada aqui, e os arquivos de entrada não trazem resultado de CI para o M13.

Resumo: critérios 2 e 3 atendidos (com o desvio de episódio registrado no item 2); critério 1 atendido nas transcrições e na rejeição, não atendido no atendente (1 linha) e não verificado na média de 3 repetições; critério 4 não verificado.

## Limitações

- **Amostragem do LLM não é semeada.** `--seed 0` não controla a geração do Ollama. Uma linha de diferença é ruído (3% por estágio).
- **Rodadas únicas.** Cada rodada teve uma repetição (`--repeat 1`). A média de 3 repetições do aceite não foi feita.
- **Dataset sintético.** Os 240 pares são inventados, com o formato real dos textos indexados e negativos difíceis. Não representam a memória de uso real.
- **Os números de fatos do `compare.md` são anteriores à correção do T5** (commit `70645c8`). A checagem depois da correção está só nos testes diretos do extrator e nos smokes.
- **Latências em CPU, com a máquina de 7 GB.** Não há medida com GPU. As rodadas antes e depois não tiveram o ajuste de aquecimento (`a7a3e85`). O resumo da rodada antes classifica as latências como "melhor caso", mas o `compare.md` e este relatório as tratam como cenário de CPU, que é o alvo.
- **Recall cruzado baixo para fatos** (0,167 com o limiar 0,46). Ver a seção de limiares.
- **`SEM_MIN_SIM` = 0,42** prioriza precisão: o recall de episódios entre idiomas fica em 0,667.
- **Só um modelo de embedding testado** (`embeddinggemma`). Os limiares valem para ele. Trocar de modelo exige recalibrar.
- **Respostas em português para perguntas em inglês** continuam às vezes (smokes, A6). É o idioma da criatura, não do recall.
- **Não há verificação de CI neste relatório** (critério 4 do aceite).
