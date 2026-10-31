# Engrama (spike descartável)

Engrama é um bichinho digital pixel-art (bebê, inspirado em Digimon mas original) que nasce de um ovo, com SNN minúscula (numpy), bandit, voz chiptune e chat (Ollama opcional).

## Rodar
```
cd E:\Documentos\GitHub\digimon\spike
.venv\Scripts\python main.py
```
(Recriar venv: `py -3.13 -m venv .venv` e `.venv\Scripts\pip install -r requirements.txt`.)

## Teclas
- **Clique** na criatura = carinho (no ovo: 5 cliques chocam; ou espere ~20s)
- **F** abre o menu de comida (**1-9** ou setas + **Enter**, **Esc** cancela), **P** brincar, **S** dormir/acordar
- **M** abre a tela de modelo do LLM (só quando o chat não está focado)
- **Enter** foca o chat, digite, **Enter** envia (Esc cancela). Também dá pra clicar na barra de baixo
- **Tab** ou **F1**: painel de debug da SNN (raster, Vm, pesos, taxas, bandit)
- **R**: modo descanso (SNN ~1Hz, ~5 FPS, sem LLM). Perder o foco >60s ativa descanso automático

Necessidades (fome, sono, tédio, carinho, curiosidade) são "vontades": barra cheia/vermelha = precisa de atenção.

## Comidas
Reais: carne, fruta, peixe, bolinho. Digitais: pacote de dados, cookie de navegador, bug frito, cache quentinho, byte crocante. Cada uma reduz a fome e mexe um pouco nas outras necessidades (ex.: bug frito = menos curiosidade/tédio, cache quentinho = mais sono). O ícone aparece ao lado da criatura ao comer.

A criatura tem gostos: cada comida tem uma nota (-1..1) que começa de forma determinística a partir da seed + traços (curiosa tende às digitais) e muda um pouco a cada refeição. Comida que ela gosta dá extra de carinho/tédio; a que odeia pode ser recusada (balão "bleh!" + rosnado) ou comida pela metade. Com o painel de debug (Tab) aberto, o menu mostra as notas. As notas ficam no `save.json`, e favoritas/odiadas entram no prompt do LLM.

## Chat / LLM
Usa Ollama se estiver rodando. Configuração em `config.json` (criado com padrões se faltar): `model` (padrão `qwen3:1.7b`), `ollama_url`, `keep_alive` (`10m`, descarrega o modelo quando ocioso; configs antigas mantêm o valor delas). A variável `CREATURE_MODEL` sobrescreve o modelo se definida. As requisições mandam `think: false` (Qwen3), `num_ctx` 2048 e `num_predict` 80, e blocos `<think>...</think>` são removidos da resposta. Ao abrir o app (e ao escolher modelo ou sair do descanso) um aquecimento em segundo plano (`POST /api/generate` com prompt vazio, timeout 300s) carrega o modelo: o rodapé mostra `llm: acordando...` e, enquanto isso, o chat responde com balbucio + "zzz... (cérebro carregando)" sem marcar o servidor como morto. Só conexão recusada/erro conta como offline (nova tentativa após 30s); timeout não. O descanso (R) descarrega o modelo (`keep_alive: 0`). O prompt nunca mostra números: necessidades viram palavras ("está com fome") e há exemplos few-shot PT/EN; respostas com números, emojis ou cara de assistente são descartadas (1 nova tentativa, depois balbucio). Sem Ollama usa um balbucio local. O rodapé mostra `llm: <modelo>` ou `llm: babble (offline)`.

Tela **M** (recomendados para notebook 8GB sem GPU dedicada; "[instalado]" vem de `GET /api/tags`):
- `qwen3:1.7b` - recomendado: bom PT/EN, ~1.4GB (padrão)
- `gemma3:1b` - mais leve, ~0.8GB
- `qwen2.5:1.5b` - alternativa leve, ~1GB
- `llama3.2:1b` - leve, inglês melhor que português
- `qwen3:4b` - mais esperto, mais pesado (~2.6GB), pode pesar com 8GB
- `outro...` - digite qualquer nome de modelo

Cima/Baixo + Enter seleciona; Esc fecha. Modelo não instalado é baixado em segundo plano (`/api/pull`, com % na tela) e vira o ativo ao terminar; a escolha vai para o `config.json`. Se o Ollama estiver inacessível a tela avisa, mas ainda deixa definir o nome (sem baixar).

## Save
`save.json` (ignorado no git) guarda necessidades, traços, gostos de comida, bandit, pesos da SNN e últimos 50 eventos. Se ficar fora >1h, a criatura comenta ("demorou...").

## Teste headless
`.venv\Scripts\python smoke_test.py`
