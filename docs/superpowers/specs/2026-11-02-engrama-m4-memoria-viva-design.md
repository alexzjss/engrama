# Engrama M4 — Memória viva: design

**Status:** proposta para aprovação · **Data:** 2026-11-02 · **Base:** branch `m3` (PR #3), spec v2 §5 e §10 (M4), spec v1 (`git show m1-m2:docs/superpowers/specs/2026-10-31-engrama-design.md`) §5.4 e §5.10.

## 1. Intenção

Hoje a criatura reage só à mensagem do momento. O prompt leva as 3 lembranças mais recentes. Os fatos e tópicos que o serviço de linguagem já extrai de cada conversa são gravados, mas nunca voltam para a fala.

No M4 ela passa a ter vida mental contínua sobre o usuário:
- lembra o que importa;
- acompanha os assuntos atuais e os antigos;
- reflete sobre o que viveu e forma opiniões próprias, que podem discordar das do usuário;
- às vezes puxa assunto ou retoma algo antigo por conta própria.

O usuário pode ver e apagar o que ela lembra.

Critério de sucesso, nas palavras do usuário: ela "deve lembrar das informações importantes e dos assuntos atuais ou tópicos passados e refletir, julgar isso".

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Recuperação na conversa | **Busca por palavras**, sem modelo de embeddings. |
| Reflexão | **Depois de conversas**: só quando o LLM já está carregado e o usuário parou de falar. Nunca carrega o LLM só para refletir. |
| Opiniões | **Próprias e às vezes discordantes.** Nascem de traços e genoma mais a experiência, e mudam devagar. |
| Iniciativa | **Puxar assunto de interesse**, **lembrar algo antigo** e **mostrar o que pensa** (painel). |
| Frequência espontânea | **Rara**: no máximo uma fala espontânea por hora de uso. Só com o usuário ativo e o LLM já carregado. Nunca em descanso nem em tela cheia. |
| Privacidade | Painel **Memórias**, em que o usuário **vê e apaga** itens ou tudo. Tudo continua local. |
| Apagar um item | Apaga **tudo que o cita**: o fato ou o tópico, as opiniões sobre ele, as conversas guardadas, as reflexões e os resumos compactados que o mencionam, e as mensagens recentes da `WorkingMemory` que o citam. |
| Esquecer tudo | Apaga **tudo sobre o usuário**: fatos, tópicos, conversas, reflexões e compactações. O que é dela fica: gostos de comida e traços (no kernel e na mente, fora do `memory.sqlite`) e as posições inatas das opiniões. As frases ligadas a conversas são apagadas. |
| Estágio | **Como no spec**: bebê só lembra, criança puxa assunto, adulto dá opinião e discorda, perfeito/final lembra coisas antigas. |
| Prova | Aceitação headless com **LLM falso** e **memória limitada** em 30 dias simulados. |

## 3. Objetivos

1. **Memória semântica útil.**
   - Os fatos sobre o usuário (já extraídos em `_extract`) são consolidados: mesma chave atualiza, confiança sobe com a repetição, contradição troca o valor.
   - Fatos e episódios importantes **não** são esquecidos.
2. **Interesses com linha do tempo.**
   - Cada tópico guarda afinidade do **usuário** (quanto ele fala e com que humor), a **saliência atual** (decai com o tempo) e a última vez citado.
   - Daí saem "assuntos atuais" (saliência alta) e "assuntos passados" (afinidade alta, saliência baixa, citados há dias).
3. **Recuperação por palavras no prompt.** A cada mensagem, o prompt recebe:
   - até 3 fatos relevantes, ou os mais confiáveis quando nenhum casa;
   - até 2 episódios relevantes (o `retrieve` existente, por sobreposição de palavras e recência);
   - os assuntos atuais;
   - a opinião dela sobre o tópico da mensagem, se houver.
   
   Nada disso pode conter dígitos (regra da persona).
4. **Reflexão pós-conversa.**
   - Depois de uma conversa, com o LLM ainda carregado e o usuário parado, um job de reflexão (prioridade 2, que já existe na fila) resume a conversa num episódio "reflexão".
   - O mesmo job pode criar ou ajustar uma **opinião** da criatura sobre um tópico.
5. **Opiniões próprias.**
   - Cada opinião é um registro (tópico, posição −1..1, uma frase curta no idioma da conversa, confiança, data).
   - A **posição** é calculada de forma determinística, sem o LLM:
     - uma inclinação inata do genoma e dos traços para aquele tópico;
     - mais a experiência dela com o tópico (valência dos episódios em que ele apareceu).
     
     Ela **não** converge para a afinidade do usuário. Por isso pode discordar.
   - O LLM só escreve a frase que justifica a posição, coerente com ela. Ele nunca decide a posição. Isso segue a regra da v2 de que o LLM só produz fala.
6. **Iniciativa rara.** Quando o árbitro escolhe `ask_attention` ou `show_something`, e o estágio, a frequência e o estado do LLM permitem, o host pede ao serviço um **comentário** (prioridade 1, que já existe) sobre:
   - um assunto atual (criança ou maior);
   - uma opinião (adulto ou maior);
   - um assunto ou fato antigo (perfeito/final).
   
   A fala aparece no balão como as respostas.
7. **Painel Memórias** (nova tecla, a do builder; sugestão: **F7**).
   - Lista fatos, assuntos (atuais e passados) e opiniões, com as reflexões recentes.
   - O usuário apaga um item ou "esquecer tudo", com confirmação.
   - Apagar um tópico apaga também as opiniões sobre ele.
   - O que for apagado não volta a ser extraído da mesma conversa já gravada, porque episódios antigos não são reprocessados.
8. **Visão da Mente.** Um resumo da memória (contagens, assuntos atuais, última reflexão) aparece na Visão da Mente, onde números são permitidos.

## 4. Não objetivos

- Embeddings ou busca semântica por significado. Ficam para os "Experimentos" do spec v2.
- Reflexão diária ou "sonhos". Não há reflexão que carregue o LLM.
- Percepção do PC (apps, jogos) como fonte de interesses. É o M5. O formato de tópico deve aceitar uma fonte futura `"percepcao"` sem migração.
- Mudar o comportamento (o árbitro) com base em opiniões. A memória influencia a **fala**. Ações continuam vindo da mente.
- Sincronizar ou enviar dados para fora da máquina.

## 5. Anti-objetivos (falha mesmo que "funcione")

- Ela papagaia o usuário: toda opinião igual à afinidade dele.
- Ela repete o mesmo fato em toda fala, ou cita memória sem relação com a mensagem.
- Números crus na fala ou no prompt ("você disse 3 vezes..."), emoji ou fala de assistente.
- O LLM carregado só para refletir ou comentar, ou o PC pesando por causa da memória.
- O banco cresce sem limite.
- Uma exceção da memória na thread da UI ou da simulação.
- Iniciativa chata: falar sozinha com frequência, em descanso ou em tela cheia.
- O usuário apaga algo e isso reaparece sozinho.

## 6. Restrições

Todas as restrições globais do plano M3 continuam valendo:
- leveza (núcleo ≤ 150 MB e ≤ 2% de CPU, sem LLM);
- nada no C;
- local e offline;
- dependências: pygame-ce, numpy e psutil;
- regras de importação (`services` não importa `mind`, `modules`, `kernel`, `lab` nem `app`; a UI não importa `services`);
- commits sem atribuição a IA;
- PT/EN.

Além disso:
- **Só o host liga as peças.** O serviço de memória não conhece o kernel. As inclinações inatas chegam ao serviço por uma função injetada pelo host, calculada do genoma e dos traços do snapshot. Essa função é determinística: mesma semente e mesmo tópico dão a mesma inclinação.
- **O schema do `memory.sqlite` evolui com migração.**
  - Hoje `meta.schema_version = 1`.
  - Um banco do M3 abre no M4 sem perder dados, e um banco corrompido não derruba o app.
- **Limite de tamanho.** Em 30 dias simulados com usuário ativo, o banco fica limitado:
  - teto de linhas por tabela, valor do builder;
  - episódios de baixa importância compactados ("comeu fruta" ×30 vira "come fruta quase todo dia"), como no spec v1 §5.10.
- **Fila do LLM.** A ordem atual continua: chat 0 > comentário 1 > reflexão 2 > fatos 3. Jobs de prioridade ≥ 1 só rodam com o LLM `ready` e `idle()`. O tempo de resposta do chat não pode piorar por causa da reflexão.

## 7. Comportamento por estágio

| Estágio | Usa memória no prompt | Puxa assunto atual | Opina e discorda | Retoma algo antigo |
|---|---|---|---|---|
| ovo | não (não fala) | não | não | não |
| bebê | sim (fala curta) | não | não | não |
| criança | sim | sim | não | não |
| adulto | sim | sim | sim | não |
| perfeito/final | sim | sim | sim | sim |

A reflexão e a formação de opiniões rodam desde o bebê, para que a criança e o adulto já tenham material. A opinião só aparece na fala a partir do adulto.

## 8. Critérios de aceitação

Testes `slow` e headless, com cliente LLM falso e relógio falso:

1. **Lembra fato.**
   - No dia 1 o usuário diz um fato. O cliente falso extrai `("jogo_favorito", "hollow knight")`.
   - No dia 5, numa mensagem que cita "jogo", o prompt de sistema contém o valor, sem dígitos.
2. **Assunto atual × passado.** Um tópico muito citado na semana 1 e não citado depois aparece como "passado" na semana 3. Um tópico da semana 3 aparece como "atual".
3. **Opinião própria.**
   - Com duas criaturas de sementes diferentes, ou com inclinação inata oposta por construção, e o mesmo histórico de usuário, as posições sobre o mesmo tópico têm sinais opostos.
   - Com uma afinidade do usuário fortemente positiva, existe ao menos um caso determinístico em que a posição dela é negativa.
4. **Reflexão sem carregar o LLM.**
   - Com o LLM `offline`, nenhuma reflexão chama o cliente.
   - Com o LLM `ready` e `idle`, uma conversa encerrada gera um episódio de reflexão.
5. **Iniciativa rara e por estágio.**
   - Em 10 h simuladas com usuário ativo, LLM pronto e estágio adulto, há no máximo 10 comentários espontâneos e pelo menos 1.
   - Com estágio bebê, nenhum.
   - Em descanso ou tela cheia, nenhum.
6. **Apagar é definitivo.** Apagar um fato ou tópico pelo painel o remove do banco e do prompt. Ele não reaparece sem nova menção do usuário.
7. **Memória limitada.** Em 30 dias simulados, com usuário simulado conversando todo dia (texto sintético), o `memory.sqlite` respeita os tetos, e episódios antigos de baixa importância foram compactados.
8. **Migração.** Um `memory.sqlite` no schema do M3 abre, migra e mantém episódios, fatos e tópicos.
9. **Sem regressão.**
   - A suíte inteira passa.
   - O bench do app sem LLM continua dentro do orçamento do M3: ≤ 150 MB de RSS e ≤ 2% de CPU. O usuário não escolheu este item como critério de prova do M4, mas ele é uma restrição global.

## 9. O que fica com o builder

- O formato exato das tabelas novas e a migração.
- A fórmula da inclinação inata (hash estável de tópico com semente e traços) e da mistura com a experiência, respeitando o anti-objetivo de não convergir para o usuário.
- A meia-vida da saliência e o limiar de "atual" e "passado".
- Os tetos de tamanho e a política de compactação.
- A normalização de tópicos: minúsculas, sem acento, sinônimos simples PT/EN por tabela pequena.
- A tecla e o layout do painel Memórias, desde que use o registro de painéis do M3 e a regra de "sem números no modo normal".
- Os prompts de reflexão, opinião e comentário, por estágio e idioma, sempre sem dígitos, sem emoji e sem fala de assistente.
- Como o host detecta "fim de conversa" (sugestão: 2 min sem mensagem depois de uma resposta do LLM).

## 10. Decisões minhas (para o usuário conferir)

- **A posição da opinião vem da mente, não do LLM.** Ela é calculada de forma determinística e o LLM só a verbaliza. Assim respeito a regra da v2 de que o LLM nunca escolhe e garanto que ela possa discordar.
- **A iniciativa usa ações que já existem** (`ask_attention`, `show_something`). Nenhuma ação nova no kernel.
- **Tecla F7** para o painel Memórias.
- **O orçamento de leveza continua sendo restrição**, mesmo sem ter sido marcado como critério de prova.
- **Ligação de episódios a tópicos e fatos.**
  - Cada episódio (conversa, reflexão, compactação) guarda os tópicos e as chaves de fato que menciona, numa tabela de ligação.
  - Apagar um item usa essa ligação e também busca o valor no texto (normalizado), para pegar episódios antigos sem ligação.
  - Itens apagados entram numa lista de bloqueio, que guarda só o nome normalizado. Ela impede que um job de extração ou reflexão já na fila recrie o item a partir da mesma conversa. Uma menção **nova** do usuário depois do apagamento é aceita.
- **Opiniões existem sem o LLM.**
  - A linha da opinião (tópico, posição, confiança) é criada e atualizada no caminho determinístico, a cada atualização de tópico, sem LLM.
  - A frase é opcional e é preenchida depois, pela reflexão.
  - Sem frase, a opinião entra no prompt como uma indicação em palavras ("ela não curte muito esse assunto"), e o LLM a verbaliza na resposta. Ela nunca é falada sozinha, sem o LLM.
- **Inclinação inata congelada por criatura.**
  - A inclinação vem de um hash estável de (semente do genoma, tópico normalizado) e é congelada.
  - Os traços entram só como uma pequena modulação, calculada uma vez quando a opinião nasce. Assim a deriva lenta dos traços não vira opiniões.
  - O que muda com o tempo é a parte da experiência, devagar.
- **Tópicos do M3 migrados.**
  - A `affinity` atual vira a "afinidade do usuário".
  - A saliência inicial é calculada a partir do `t`.
  - Nomes que se fundem pela nova normalização somam as afinidades, limitadas a [-1, 1], e ficam com o `t` mais recente.
- **Iniciativa: relógio, cota e bloqueio.**
  - A cota é de **uma por hora de uso**. A hora de uso conta só o tempo de relógio real (vezes `time_scale`, para os testes) em que o usuário está ativo, isto é, com uma entrada nos últimos 5 minutos.
  - A cota e o horário do último comentário espontâneo ficam no `memory.sqlite` (tabela `meta`) e sobrevivem a reinícios.
  - Se a cota, o estágio, o LLM, o descanso ou a tela cheia bloquearem o comentário, a ação escolhida pelo árbitro segue normal (animação e balão "!" como hoje), só sem fala.
  - Se o árbitro escolher essas ações raramente demais, o gatilho espontâneo fica independente do árbitro: um teste de oportunidade no host, a cada minuto de uso, com a cota como teto. Nada muda no kernel nem no árbitro.
- **Testes de aceitação.**
  - O critério 5 (iniciativa por estágio, descanso e tela cheia) usa o `Host` real com `pump()` e relógio falso, cliente LLM falso e estágio forçado. O descanso e a tela cheia vêm de eventos postados.
  - Os critérios 1, 2, 3, 4, 6, 7 e 8 usam `MemoryStore` e `LanguageService` diretamente (`sync=True`, `now_fn` falso), com chamadas roteirizadas. Assim os 30 dias simulados não exigem 30 dias de ticks do host e cabem na suíte `slow`.
