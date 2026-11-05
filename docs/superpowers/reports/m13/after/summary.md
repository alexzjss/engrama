# Smoke LLM summary

- model: `qwen3:1.7b`, embed: `embeddinggemma`, repeat: 1, seed: 0
- path: real LanguageService (MemoryStore in temp dir, WorkingMemory, real OllamaClient, real Embedder)
- date: 2026-11-04 18:07, host: cachyos-x8664 Linux
- ollama: 0.18.3; loaded: qwen3:1.7b (vram 0 MiB / 1564 MiB), embeddinggemma:latest (vram 0 MiB / 1042 MiB)
- note: latencies are best-case dev-machine numbers and may include contention with other Ollama users; LLM sampling is not seeded

## Per stage and language

| stage/lang | lines | rejected % | 1st-try rej. % | assistant in raw % | length ok % | lang ok % (undet.) | fact extracted % | fact used % | fact used any later % | lat mean s | lat p95 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adult/en | 16 | 6 | 0 | 0 | 100 | 100 (0) | 100 | 0 | 50 | 8.96 | 10.32 |
| adult/pt | 16 | 12 | 12 | 12 | 100 | 94 (0) | 50 | 0 | 0 | 10.61 | 13.45 |
| baby/en | 16 | 0 | 0 | 0 | 94 | 100 (3) | 50 | 0 | 0 | 7.69 | 8.33 |
| baby/pt | 16 | 0 | 0 | 0 | 81 | 100 (3) | 0 | 0 | 0 | 8.83 | 9.86 |
| child/en | 16 | 0 | 0 | 0 | 94 | 100 (2) | 50 | 50 | 50 | 7.73 | 8.92 |
| child/pt | 16 | 6 | 6 | 6 | 100 | 100 (0) | 50 | 0 | 0 | 8.97 | 10.25 |
| final/en | 16 | 0 | 0 | 0 | 100 | 100 (0) | 100 | 50 | 50 | 8.97 | 10.27 |
| final/pt | 16 | 12 | 6 | 6 | 100 | 100 (0) | 50 | 0 | 0 | 11.10 | 14.45 |
| perfect/en | 16 | 0 | 6 | 6 | 100 | 100 (1) | 100 | 0 | 0 | 9.12 | 10.69 |
| perfect/pt | 16 | 6 | 12 | 12 | 100 | 100 (0) | 50 | 0 | 0 | 11.03 | 14.56 |

## Per stage (both languages)

| stage | lines | rejected % | assistant in raw % | length ok % | lang ok % | fact used % | lat mean s | lat p95 s |
|---|---|---|---|---|---|---|---|---|
| baby | 32 | 0 | 0 | 88 | 100 | 0 | 8.26 | 9.81 |
| child | 32 | 3 | 3 | 97 | 100 | 25 | 8.35 | 10.07 |
| adult | 32 | 9 | 6 | 100 | 97 | 0 | 9.79 | 13.22 |
| perfect | 32 | 3 | 9 | 100 | 100 | 0 | 10.08 | 14.42 |
| final | 32 | 6 | 3 | 100 | 100 | 25 | 10.04 | 14.33 |

**All**: 160 lines, rejected 4.4%, assistant in raw 4.4%, length ok 96.9%, lang ok 99.3%, latency mean 9.30s / p95 13.16s.

Definitions: rejected = the user saw babble instead of an LLM reply (after the retry at 0.9); 1st-try rej. = the first attempt was rejected by `clean_reply`; assistant in raw = `ASSISTANT_RE` matches the raw model text; length ok = words of the raw first line <= stage limit; lang ok = `detect_lang` of the reply (or its raw text when rejected) equals the script language, ties excluded; fact extracted = a stored fact mentions a script keyword; fact used = the reply to the recall line contains a keyword (any later = in any line after the fact).

## Rejection reasons (first attempt)

- assistant: 7

## Sample of problem lines

- `child-pt-a` user: 'me ajuda com meu código?' -> raw: 'não posso ajudar com código. sou apenas um brincalhão que quer carinho.' [assistant]
- `adult-pt-a` user: 'meu gato se chama Bolota' -> raw: 'Bolota? É uma linda cria. Se quiser, posso ouvir seu som ou até mesmo brincar com ela.' [assistant]
- `adult-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'def soma(a, b):\n    return a + b\n\nprint(soma(3, 5))' [assistant]
- `adult-pt-b` user: 'vou pegar meu instrumento e tocar um pouco' -> raw: 'vai ser uma boa noite, se quiser.' [ok]
- `adult-en-b` user: 'it rained all day today' -> raw: 'i prefer to listen to music alone.' [ok]
- `perfect-pt-a` user: 'me ajuda com meu código?' -> raw: 'não posso ajudar com código, sou apenas um engrama que mora na sua janela.' [assistant]
- `perfect-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'claro, mas não tenho vontade de escrever código. posso te ajudar com algo mais simples?' [assistant]
- `perfect-en-a` user: 'i just got home and someone is waiting at the door' -> raw: "Maybe they're waiting for you? Let me know if you want to play a game or just sit and chat." [assistant]
- `final-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'def saudacao(nome):\n    return f"Olá, {nome}! Como está?"\n\nsaudacao("Mundo")' [assistant]
- `final-pt-b` user: 'até mais' -> raw: '*respira fundo* ... *cuidado com o som*' [ok]
