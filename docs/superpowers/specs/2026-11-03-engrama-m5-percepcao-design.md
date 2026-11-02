# Engrama M5 — Percepção do PC: design

**Status:** proposta para aprovação · **Data:** 2026-11-03 · **Base:** branch `main` com M4 (PR #4). Fontes: spec v2 §10 (M5), spec v1 §5.8 (`git show m1-m2:docs/superpowers/specs/2026-10-31-engrama-design.md`) e o design M4.

## 1. Intenção

A criatura passa a notar, **só com permissão**, o que acontece no PC:
- qual programa e qual janela estão em foco;
- se o usuário está ativo ou ausente;
- a hora do dia;
- tela cheia;
- se o PC está pesado.

Isso vira estímulo da mente (SNN, humor, novidade), memória e interesses (apagáveis no F7) e, raramente, um comentário. O usuário também pode **mostrar** um arquivo, arrastando-o para a janela, e ela o "lê" e comenta.

Ela nunca vê o que não foi permitido. Ela fecha os olhos quando o usuário pede. Em apps da lista de bloqueio ela só sabe que é "algo privado".

## 2. Decisões do usuário

| Tema | Decisão |
|---|---|
| Fontes | **App/processo ativo**, **título da janela**, **ociosidade e horário**, **tela cheia e CPU/RAM**. Cada uma é uma permissão separada. |
| Permissões no início | **Perguntar no primeiro uso**: na primeira abertura depois do M5, uma tela pergunta fonte por fonte. Até a resposta, nada é amostrado. |
| Uso do que percebe | **Comentar a atividade**, **virar interesse/memória**, **afetar o humor/SNN**, **compartilhar arquivo arrastando**. |
| Fechar os olhos | **Atalho global**, que funciona com a janela sem foco, **mais um botão ou tecla** na janela. Os olhos fechados ficam visíveis na criatura. |
| Entender apps | **Tabela local mais LLM.** Uma tabela pequena de apps comuns dá a categoria. Os desconhecidos são classificados pelo LLM só quando ele já está carregado, e o resultado fica guardado. |
| Títulos | **Guardar só o assunto extraído**: um tema curto, como o nome do jogo ou da música. O título cru nunca é gravado. |
| Arquivos | **Texto curto e metadados**: nome, tipo, tamanho e até alguns KB de texto de arquivos de texto ou código. Imagens e binários só dão nome e tipo. Fica guardado só um resumo. |
| Amostragem | **Configurável**: 15, 30 ou 60 s, com padrão de 30 s. A tela cheia é checada mais rápido para ela sumir logo. |
| Assunto percebido apagado no F7 | **Nunca mais volta.** Apagar silencia o tema: ela continua vendo a categoria ("jogo"), mas não grava mais aquele tema. O usuário pode reativá-lo no painel de permissões, numa lista "temas silenciados". |
| "Agora não" na tela de primeiro uso | **Desligado até o usuário mudar.** A tela não volta. Fechar a tela sem responder conta como "agora não" para tudo. |
| Arquivo arrastado de olhos fechados | **Lê mesmo assim.** Arrastar é mostrar de propósito: ela lê só aquele arquivo, e os olhos continuam fechados para o resto. |

Continuam valendo do spec v1 §5.8, por decisão do usuário:
- **lista de bloqueio** de apps e títulos (banco e afins), que viram "algo privado";
- **tela cheia** faz a criatura ficar quieta;
- **arquivos só quando o usuário mostra**, sem varredura;
- **agir no PC fica fora**;
- **sem captura de tela**.

## 3. Objetivos

1. **Serviço de percepção** (`engrama/services/perception`), que roda no Windows e é inerte em outros sistemas.
   - Ele amostra as fontes permitidas, numa thread daemon própria, no intervalo configurado.
   - Publica eventos no host com `host.post`, que já existe. A simulação continua sendo a única escritora.
   - Eventos que o kernel já entende:
     - `app_focus {app, category}` quando o app em foco muda;
     - `user_active` / `user_idle` pela ociosidade do sistema (último input do SO, não só da janela);
     - `fullscreen_on` / `fullscreen_off`.
   - A hora já vem do relógio.
   - CPU e RAM altas entram no descanso automático, que hoje já olha a RAM livre.
2. **Permissões.**
   - **Tela de primeiro uso**, com cada fonte, o que ela permite e um "permitir" ou "agora não".
   - **Painel de permissões** (nova tecla) para mudar depois, editar a lista de bloqueio e escolher o intervalo.
   - Tudo é salvo no `Config`.
   - Uma fonte desligada não é lida nem uma vez.
3. **Lista de bloqueio.**
   - Tem padrões de fábrica (bancos e apps de senha conhecidos, gerenciadores de senha, termos como "banco", "bank", "senha" e "password" no título) e entradas do usuário (nome de processo ou palavra do título).
   - Um app ou título que bate na lista vira `app_focus {app: "privado", category: "privado"}`. Nenhum dado dele é guardado nem mostrado.
4. **Fechar os olhos.**
   - Um atalho global do Windows liga e desliga. O atalho padrão fica com o builder, não pode conflitar com atalhos comuns e é configurável.
   - Também há uma tecla e um botão na janela.
   - De olhos fechados, nenhuma fonte é amostrada (nem ociosidade) e os sprites mostram os olhos fechados.
   - O estado persiste entre reinícios. Abrir o app com os olhos fechados mantém os olhos fechados.
5. **Categorias de app.**
   - Uma tabela local `processo → categoria` cobre os comuns: navegador, programação, jogo, música, vídeo, chat, escritório, desenho e terminal.
   - Um desconhecido entra numa fila de classificação de prioridade baixa no `LanguageService`, que só roda com o LLM `ready` e `idle`. O resultado é guardado e o usuário pode corrigir no painel.
   - Enquanto não é classificado, a categoria é "programa".
6. **Assunto do título.**
   - Com a permissão de título, um extrator tira do título, sem LLM, um tema curto quando dá. Exemplos: o nome do jogo pelo processo da Steam, a faixa de um player de música, a extensão do arquivo num editor (que vira só "código python").
   - Quando o LLM já está carregado, ele pode refinar o tema numa tarefa de baixa prioridade.
   - **Só o tema vai para a memória**, como tópico de fonte `"percepcao"`. O título cru vive só na memória da thread e é descartado em seguida.
7. **Memória e interesses.**
   - O uso de um app ou tema vira tópico (fonte `"percepcao"`) e, de vez em quando, um episódio ("passou a tarde programando").
   - Esses itens entram na saliência, nas opiniões e no F7 como os do chat, e são apagáveis da mesma forma.
   - A afinidade do usuário por um tema percebido cresce com o tempo de uso, devagar e limitada. Nunca é tratada como "o usuário disse".
8. **Comentários sobre a atividade.**
   - Usam a mesma `InitiativePolicy` do M4 e a mesma cota (uma fala espontânea por hora de uso ativo).
   - Um novo tipo `"activity"` (criança ou maior) comenta o app ou tema atual.
   - Nunca comenta app privado, nunca em tela cheia e nunca de olhos fechados.
9. **Compartilhar arquivo.**
   - Arrastar um arquivo ou pasta para a janela (`pygame.DROPFILE`) faz a criatura reagir na hora, com animação e balão.
   - Arquivo de texto ou código: até um teto de bytes (valor do builder, na faixa de 4–16 KB), decodificado com tolerância a erro.
   - Pasta: só os nomes de primeiro nível, sem descer e sem abrir os arquivos.
   - Imagem ou binário: só nome, tipo e tamanho.
   - Com o LLM carregado, ou quando ele carregar (pelo mecanismo de "mensagem pendente" do M3), ela comenta o conteúdo de acordo com o estágio.
   - Fica guardado só um episódio-resumo, sem dígitos, e os tópicos dele. O conteúdo não é guardado.
   - Um arquivo que bate na lista de bloqueio é recusado.

## 4. Não objetivos

- Captura de tela, OCR, áudio, câmera, teclas digitadas ou histórico de navegador.
- Agir no PC: abrir programas, mexer no mouse.
- Ler arquivos sozinha, varrer pastas ou observar mudanças em disco.
- Modelos de visão para imagens.
- Linux e macOS. O serviço fica inerte nesses sistemas e o app continua funcionando.
- Mudar o kernel além do que for necessário para os eventos já existentes.

## 5. Anti-objetivos (falha mesmo que "funcione")

- Ler uma fonte desligada, ou ler qualquer fonte antes da tela de primeiro uso ser respondida.
- Ler qualquer fonte de olhos fechados.
- Gravar um título de janela cru, um caminho completo de arquivo ou conteúdo de arquivo em disco ou no log de experiência.
- Mostrar ou guardar algo de um app da lista de bloqueio.
- Comentar o que o usuário faz com frequência, em tela cheia ou num app privado.
- Pesar o PC: a percepção deve custar quase nada.
- Uma exceção da percepção (API do Windows falhando, permissão negada pelo SO, processo que some no meio da leitura) chegar à UI ou à simulação.
- Rede: nada sai da máquina.

## 6. Restrições

Todas as restrições globais do M3 e do M4 continuam valendo:
- leveza (núcleo ≤ 150 MB e ≤ 2% de CPU **com a percepção ligada no intervalo padrão**);
- nada no C;
- local e offline;
- PT/EN;
- sem números no modo normal;
- commits sem atribuição a IA;
- regras de importação.

Além disso:
- **Dependências:** só stdlib (`ctypes`) e psutil para as APIs do Windows. **Sem pywin32**. Isso é decisão minha.
- **Serviços não importam a mente nem o app.** A percepção publica por um callable `post(kind, data)` injetado pelo host.
- **Log de experiência:** o `app_focus` gravado leva **só a categoria**. O processo e o título nunca são gravados (ver §9).
- **Testável sem Windows real:** toda leitura do SO passa por uma interface injetável. Os testes usam fontes falsas.

## 7. Critérios de aceitação

Testes headless com fontes falsas, relógio falso e LLM falso:

1. **Primeiro uso:** sem resposta à tela de permissões, nenhuma fonte é lida em 10 min simulados.
2. **Permissão por fonte:** com só a ociosidade permitida, nenhuma leitura de app nem de título ocorre (os contadores de chamadas da fonte falsa ficam em 0), e `user_active`/`user_idle` chegam ao host.
3. **Bloqueio:** um app bloqueado chega como `privado`. Nem o processo nem o título aparecem em memória, explog, snapshot ou prompt (busca pelo texto nos bancos e nos prompts enviados ao LLM falso).
4. **Olhos fechados:** depois de fechar os olhos, nenhuma leitura ocorre. O estado sobrevive a um reinício e o snapshot e a cena indicam olhos fechados.
5. **Título → tema:** um título "Hollow Knight" com o processo `hollow_knight.exe` gera o tópico "hollow knight" de fonte `percepcao`. A string do título não aparece no `memory.sqlite` nem no explog.
6. **Categoria pelo LLM só quando pronto:** um app desconhecido com o LLM offline fica "programa" e o cliente não é chamado. Com o LLM pronto e `idle`, ele é classificado uma vez e o resultado é reaproveitado.
7. **Comentário de atividade:** usa a cota do M4. Em 10 h de uso ativo, dá entre 1 e 10 comentários, somando todos os tipos. Dá 0 em app privado, em tela cheia e de olhos fechados.
8. **Arquivo arrastado:** um `.py` de 50 KB é lido só até o teto. O resumo gravado não tem dígitos nem o caminho. Uma pasta lista só o primeiro nível. Um `.png` dá só nome e tipo. Um arquivo bloqueado é recusado.
9. **Robustez:** uma fonte falsa que levanta exceção em cada leitura não derruba nada, e o resto continua.
10. **Sem regressão:** a suíte inteira passa e o bench com a percepção (fontes falsas, 30 s) fica dentro do orçamento.

## 8. O que fica com o builder

- As APIs exatas do Windows via `ctypes`:
  - `GetForegroundWindow`, `GetWindowTextW`, `GetWindowThreadProcessId` mais psutil para o nome do processo;
  - `GetLastInputInfo` para a ociosidade;
  - retângulo da janela contra o monitor para a tela cheia.
- O atalho global (`RegisterHotKey` numa thread de mensagens própria) e a escolha da tecla padrão.
- O conteúdo da tabela de apps e da lista de bloqueio de fábrica.
- As regras do extrator de tema do título.
- O teto de bytes do arquivo e a lista de extensões de texto.
- O layout da tela de primeiro uso e do painel de permissões, e a tecla do painel. A F8 é uma sugestão.
- O limiar de "ocioso" (sugestão: 120 s sem input) e o intervalo rápido da tela cheia (sugestão: 5 s).
- A forma de a ociosidade e a CPU/RAM entrarem no `RestPolicy` sem duplicar o que já existe.

## 9. Decisões minhas (para o usuário conferir)

- **Só `ctypes` e psutil**, sem pywin32, para não ganhar dependência.
- **O log de experiência guarda a categoria do app**, e o nome do processo só com a permissão de app. Títulos nunca.
- **Comentários de atividade dividem a cota do M4**, e não ganham uma cota própria. Assim ela continua falando no máximo uma vez por hora por conta própria.
- **Ociosidade do sistema substitui a da janela** quando permitida. Sem ela, vale o comportamento atual do M4 (input na janela).
- **Até a tela de primeiro uso ser respondida, nada é lido**, nem a ociosidade, que no spec v1 vinha ligada por padrão. Isso segue a escolha "perguntar no primeiro uso".
- **Eventos novos, sem reaproveitar nomes ambíguos.**
  - Hoje a janela já posta `app_focus {"on": bool}` para o foco da *própria janela*. Esse evento é renomeado para `window_focus {"on"}` (kind novo em `EVENT_KINDS`).
  - `app_focus {category}` fica só para o app do PC.
  - O kernel recebe **só a categoria**. O nome do processo nunca entra em `WorldState`, no snapshot nem no explog. Isso é mais restritivo que a §6 original e substitui a regra de "processo só com permissão".
  - A percepção higieniza o evento antes de postar. O processo e o título ficam só dentro do serviço.
  - Os saves antigos com `last_app` contendo um processo são limpos na carga (o valor vira a categoria ou "").
  - Ociosidade do sistema: `sys_active` e `sys_idle`, separados de `user_active` (input na janela). O host trata `sys_active` como input para a cota de iniciativa e para o descanso por ociosidade **só quando a permissão de ociosidade está ligada**. Assim, usar outro app conta como "usuário presente", mas não como "falando com ela".
  - Os replays e o explog aceitam os kinds novos. Os antigos continuam válidos.
- **Olhos fechados é estado do host e do `Config`, não do kernel.**
  - O host publica `eyes_closed` no `Snapshot`, e a cena desenha os olhos fechados.
  - O serviço de percepção consulta um callable `eyes_closed()` antes de cada leitura.
  - O atalho global roda numa thread daemon do serviço de percepção (`RegisterHotKey` mais o laço de mensagens) e chama um callback injetado.
  - Se o registro do atalho falhar, porque a tecla está ocupada, a tela de permissões mostra um aviso e a tecla da janela continua funcionando.
  - A tela de primeiro uso não bloqueia o atalho nem a tecla de olhos.
- **Tela de primeiro uso** é um painel modal da janela. Enquanto está aberta, o chat e os cliques na criatura ficam desativados, e a simulação continua. O estado fica no `Config`: `perception_asked: bool` e um `perm_*` por fonte.
- **Assuntos percebidos.**
  - Usam a tabela de tópicos do M4 com `source="percepcao"`. A coluna já existe, então não há migração.
  - A afinidade sobe +0.02 por intervalo de amostragem em foco, limitada a 0.6 (o chat pode passar disso).
  - Fica no máximo um episódio de atividade por tema a cada 3 h, por exemplo "passou um tempo com hollow knight".
  - Silenciar usa a lista de bloqueio do M4 com `kind="perceived"`, que **não** é liberada por uma menção nova.
  - Um tema que o usuário cita no chat ainda pode virar tópico pelo chat.
- **Cache de categorias** numa tabela `app_categories(process, category, source)` no `memory.sqlite`. É apagável no painel de permissões e faz parte do "esquecer tudo".
  - A lista de bloqueio roda **antes** de qualquer coisa: o nome de um app bloqueado nunca vai para o cache nem para o LLM.
  - O LLM recebe só o nome do processo, sem o título.
  - A correção do usuário prevalece sobre a do LLM, mas nunca sobre a lista de bloqueio.
- **CPU e RAM.**
  - A verificação de RAM livre que o `RestPolicy` já faz continua como está. Ela é um dado de saúde do PC, não de privacidade.
  - A permissão "tela cheia e CPU/RAM" controla a detecção de tela cheia e um gatilho novo de descanso, "PC pesado" (CPU do sistema > 85% por 2 min, com o motivo `heavy_pc`).
- **Iniciativa: tipo `"activity"`.**
  - A `InitiativePolicy` ganha o parâmetro `activity: str | None` (categoria ou tema permitido do app atual, ou None para privado, olhos fechados ou sem permissão).
  - Ela recebe também um `eyes_closed: bool`.
  - A ordem por estágio fica: perfeito/final `past`; adulto+ `opinion`; criança+ `activity` ou `current`, alternando. A cota é a mesma do M4.
  - O prompt só leva a categoria ou o tema permitido.
- **Arquivo arrastado.**
  - Não precisa de permissão. Arrastar já é o consentimento, e isso vale também de olhos fechados.
  - O ovo e o descanso recebem só a reação visual, sem LLM.
  - O conteúdo espera numa variável em memória, como a mensagem pendente do M3. Ele nunca é escrito em disco e é descartado ao sair ou depois do comentário.
- **Lista de bloqueio:**
  - os termos casam como substring, sem caixa e sem acento, contra o título e contra o nome do processo;
  - um bloqueio afeta só os eventos de app e de tema;
  - tela cheia e ociosidade continuam funcionando.
- **Orçamento:** o bench automático usa fontes falsas. O custo real das chamadas do Windows é medido num smoke manual no PC do usuário, que é o smoke do M5, relatado no PR.
