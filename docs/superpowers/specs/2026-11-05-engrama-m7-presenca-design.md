# Engrama M7: Presença — design

Status: rascunho para aprovação. Base: branch `m6`. Marcadores: **[usuário]** = decidido pelo usuário; **[construtor]** = decisão técnica minha, revisável.

## 1. Intenção

Até o M6 ela vive só dentro de uma janela. O M7 deixa ela **morar no PC**: sair da janela e andar sobre a barra de tarefas, reagir ao mouse, pedir coisas "digitais" de brincadeira e ganhar um repertório maior de jeitos de agir, que cresce conforme ela cresce. Tudo local, leve e sem atrapalhar o trabalho.

## 2. Decisões

| Tema | Decisão |
|---|---|
| Onde anda no overlay | **Sobre a barra de tarefas**: faixa logo acima dela, de ponta a ponta. **[usuário]** |
| Necessidades digitais | **Ações bobas no menu**: ela às vezes pede algo digital; você atende pelo menu e ela fica feliz. Não é necessidade real, não muda balanceamento. **[usuário]** |
| Pedir atenção | **Balão e animação**, só dentro do Engrama; nada de notificação do Windows. **[usuário]** |
| Alternar modos | **Tecla e menu**, abre no último modo usado. **[usuário]** Tecla: **F11**. **[construtor]** |
| Interação no overlay | **Clique abre mini-menu** ao lado dela (comida, remédio, digital, conversar, voltar ao terrário); conversar abre uma caixa de chat pequena sobre ela. **[usuário]** |
| Comportamentos extras | **Vários, no terrário e no overlay**, liberados por estágio. **[usuário]** Conjunto: dançar/pular, cochilar/bocejar, perseguir o cursor, espiar/cavar/trazer achados. **[usuário]** |
| Mouse | No overlay ela **às vezes olha e segue** o cursor. Só a posição é lida; nada sai do PC. **[usuário]** |
| Mente | Comportamentos extras são **variantes visuais das 8 ações atuais**; a mente não muda, saves não migram. **[usuário]** |

## 3. Restrições

- `ACTIONS`, `EVENT_KINDS`, `FOOD_IDS`, `NEED_KEYS` **não mudam** (tamanho do Q-learning, SNN e FoodPrefs).
- Orçamento: ≤150 MB RSS e ≤2% CPU médio (`test_core_budget`), também **com o overlay ativo**.
- Kernel continua determinístico; nada do overlay entra no kernel.
- Camadas: `app/ui` e `app/art` não importam `host`; o acesso a APIs do Windows fica num módulo só (`engrama/app/desktop.py`), com fallback inerte fora do Windows e nos testes (SDL dummy).
- PT/EN em todo texto novo; sem números visíveis no modo normal.
- Nada de internet. Nada gravado em C:.

## 4. Overlay **[construtor: técnica]**

- Uma **janela pequena** (cerca de 4× o sprite + margem para balão; maior só com mini-menu ou chat abertos), **sem borda, sempre no topo, sem ícone extra na barra**, que **se move** ao longo da faixa. Mover uma janela pequena é bem mais barato que uma janela transparente da tela toda.
- Transparência por **cor-chave** (`SetLayeredWindowAttributes` com `LWA_COLORKEY`) via `ctypes`: pixels da cor-chave ficam invisíveis **e deixam o clique passar**, então só a criatura (e balão/menu) é clicável.
- Posição: área de trabalho do monitor principal (`SPI_GETWORKAREA`); ela fica com os pés na borda de baixo da área útil, ou seja, logo acima da barra de tarefas, qualquer que seja o tamanho dela. Barra em outro lado (topo/lateral) → anda na borda de baixo da área útil mesmo. **[construtor]**
- **Tela cheia** (já percebida no M5): o overlay **se esconde** e volta quando ela termina.
- Sem cenário: só criatura, sombra, balão e efeitos. HUD reduzido: ícone de humor e sinais de vida (doente/grave) acima dela, pequenos.
- Movimento: `wander` vira caminhar pela faixa; `sleep`, `idle`, `play_alone` ficam no lugar; `hide` → encolhe atrás da borda da tela; `explore`/`show_something` usam as variantes do §6. Velocidade e destino vêm da UI, não do kernel.
- Arrastar com o mouse: segurar e soltar reposiciona na faixa (ela "cai" de volta nos pés). **[construtor]**
- Taxa de quadros no overlay: a mesma regra de hoje (baixa sem foco); posição da janela só é atualizada quando muda.
- Fora do Windows ou se a API falhar: F11 mostra aviso "overlay indisponível" e fica no terrário.

## 5. Ações digitais (piada)

- Conjunto fixo em `vocab.DIGITAL_IDS`: `ram` (RAM fresquinha), `defrag` (desfragmentar), `update` (instalar atualização), `cache` (limpar cache), `cooler` (soprar o cooler). Nomes e falas em PT/EN. **[construtor: lista]**
- **Pedido:** de vez em quando, quando ela escolhe `ask_attention`, o pedido vem como um desejo digital: balão com ícone e uma fala curta ("tô precisando de RAM fresquinha..."). No máximo um pedido em aberto; expira em 30 min. Limite de 1 pedido a cada 2 h. **[construtor: números]**
- **Atender:** menu (terrário e mini-menu do overlay) ganha "Digital" com os 5 itens. Atender o pedido em aberto → animação própria do item (ex.: `defrag` = blocos se arrumando; `cooler` = ela venta) e ela fica feliz. Atender sem pedido → animação e reação neutra-curiosa.
- **No corpo:** atender posta o evento existente `pet` com `{"digital": id}`, ou seja, conta como carinho. Sem efeito novo no kernel. **[construtor]**
- Pedido é estado da UI/host, não do kernel; não entra no save do kernel, só no `host.json`.

## 6. Comportamentos extras (variantes)

Cada ação do kernel ganha variantes visuais; a UI escolhe uma quando a ação começa, com peso por humor (PAD), traços e estágio, por sorteio com seed da criatura (estável, mas variado).

| Variante | Ação base | Estágio mínimo | Quando |
|---|---|---|---|
| Pular de alegria | `play_alone`, `idle` | baby | humor alto |
| Dançar | `play_alone` | child | humor alto, ou música percebida (tema `musica` do M5) |
| Bocejar e se espreguiçar | `idle` | baby | sono alto ou ao acordar |
| Cochilar no relógio | `sleep` | child | só no overlay: anda até o canto direito da faixa (perto do relógio) antes de dormir |
| Perseguir o cursor | `play_alone`, `explore` | child | só no overlay, cursor perto; corre atrás, pula, cai sentada |
| Olhar o cursor | qualquer acordada | baby | só no overlay, cursor a menos de ~150 px: vira e olha |
| Espiar a janela ativa | `explore` | adult | só no overlay: anda até a faixa sob a janela em foco e olha pra cima |
| Cavar | `explore` | child | só no terrário: cava no chão do cenário |
| Trazer achado | `show_something` | adult | cava/volta e mostra um item pixel (osso, chip, pedrinha) ou, se houve arquivo compartilhado (M5), o ícone dele |

- As variantes reaproveitam as poses e transformações da arte V-Pet do M6 (pulos, giros, squash) e acrescentam poucos quadros novos (cavar, achado na mão). Sem novos sprites por arquétipo.
- Leitura do mouse: `GetCursorPos` no máximo 10×/s e só com overlay ativo. Janela ativa: retângulo da janela em foco, só com permissão `active_window` (M5) ligada; sem ela, a variante "espiar" fica desligada.

## 7. Configuração e persistência

- `Config` ganha `display_mode: "terrarium" | "overlay"` (padrão `terrarium`), salvo ao alternar.
- `host.json` ganha `digital_request` (id, quando) e `digital_last_t`.
- Saves M6 carregam com padrões.

## 8. Lab

- Nada muda no kernel nem na mente, então os resultados do lab ficam bit-idênticos ao M6 (teste de regressão compara uma corrida curta).

## 9. Testes **[construtor]**

- `desktop.py`: fake em testes; funções reais testadas só para "não lança fora do Windows".
- Overlay: geometria da faixa a partir de uma área de trabalho falsa; esconder em tela cheia; clique só na criatura; mini-menu posta os mesmos eventos do terrário; F11 alterna e salva `display_mode`; carga reabre no modo salvo.
- Digitais: pedido aparece só com `ask_attention`, respeita limite de 2 h e expira; atender posta `pet {"digital": id}`; textos PT/EN sem dígitos.
- Variantes: escolha determinística por seed; travas de estágio; variantes só-overlay nunca no terrário e vice-versa; "espiar" desligada sem permissão.
- Orçamento: `bench --app --overlay` ≤150 MB e ≤2% CPU.
- Regressão do lab idêntica ao M6.

## 10. Fora do escopo

- Notificações do Windows, vários monitores, andar por cima de outras janelas, novas ações reais na mente, novas necessidades reais.

## 11. Revisão — pontos de risco

1. Overlay e tela cheia/jogos: nunca ficar por cima de um jogo em tela cheia.
2. Clique atravessando: fora da criatura, o clique tem que ir para o que está embaixo.
3. Barra de tarefas com auto-ocultar ou em outro lado: ela não pode sumir fora da tela.
4. Mini-menu aberto perto da borda: tem que caber na tela.
5. CPU com overlay ativo e mouse se mexendo muito.
