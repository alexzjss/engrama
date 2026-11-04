# Smoke LLM summary

- model: `qwen3:1.7b`, embed: `embeddinggemma`, repeat: 1, seed: 0
- path: real LanguageService (MemoryStore in temp dir, WorkingMemory, real OllamaClient, real Embedder)
- date: 2026-11-04 16:17, host: cachyos-x8664 Linux
- ollama: 0.18.3; loaded: qwen3:1.7b (vram 0 MiB / 1564 MiB), embeddinggemma:latest (vram 0 MiB / 1042 MiB)
- note: latencies are best-case dev-machine numbers and may include contention with other Ollama users; LLM sampling is not seeded

## Per stage and language

| stage/lang | lines | rejected % | 1st-try rej. % | assistant in raw % | length ok % | lang ok % (undet.) | fact extracted % | fact used % | fact used any later % | lat mean s | lat p95 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| adult/en | 16 | 0 | 0 | 0 | 100 | 100 (0) | 50 | 50 | 50 | 11.13 | 13.37 |
| adult/pt | 16 | 19 | 19 | 19 | 100 | 100 (1) | 100 | 0 | 0 | 12.61 | 16.23 |
| baby/en | 16 | 0 | 6 | 6 | 94 | 100 (0) | 0 | 0 | 0 | 10.25 | 12.49 |
| baby/pt | 16 | 0 | 0 | 0 | 100 | 89 (7) | 50 | 0 | 0 | 11.44 | 13.16 |
| child/en | 16 | 0 | 0 | 0 | 81 | 100 (1) | 50 | 50 | 50 | 10.50 | 11.94 |
| child/pt | 16 | 0 | 0 | 0 | 75 | 100 (0) | 100 | 0 | 0 | 12.86 | 15.02 |
| final/en | 16 | 0 | 6 | 6 | 100 | 100 (0) | 50 | 50 | 50 | 8.08 | 10.61 |
| final/pt | 16 | 6 | 12 | 12 | 100 | 100 (1) | 100 | 0 | 0 | 12.82 | 15.90 |
| perfect/en | 16 | 0 | 6 | 6 | 100 | 100 (0) | 50 | 100 | 100 | 11.28 | 13.39 |
| perfect/pt | 16 | 6 | 19 | 19 | 100 | 100 (1) | 50 | 0 | 0 | 13.09 | 16.43 |

## Per stage (both languages)

| stage | lines | rejected % | assistant in raw % | length ok % | lang ok % | fact used % | lat mean s | lat p95 s |
|---|---|---|---|---|---|---|---|---|
| baby | 32 | 0 | 3 | 97 | 96 | 0 | 10.85 | 12.95 |
| child | 32 | 0 | 0 | 78 | 100 | 25 | 11.68 | 14.65 |
| adult | 32 | 9 | 9 | 100 | 100 | 25 | 11.87 | 15.87 |
| perfect | 32 | 3 | 12 | 100 | 100 | 50 | 12.19 | 15.96 |
| final | 32 | 3 | 9 | 100 | 100 | 25 | 10.45 | 15.47 |

**All**: 160 lines, rejected 3.1%, assistant in raw 6.9%, length ok 95.0%, lang ok 99.3%, latency mean 11.41s / p95 15.15s.

Definitions: rejected = the user saw babble instead of an LLM reply (after the retry at 0.9); 1st-try rej. = the first attempt was rejected by `clean_reply`; assistant in raw = `ASSISTANT_RE` matches the raw model text; length ok = words of the raw first line <= stage limit; lang ok = `detect_lang` of the reply (or its raw text when rejected) equals the script language, ties excluded; fact extracted = a stored fact mentions a script keyword; fact used = the reply to the recall line contains a keyword (any later = in any line after the fact).

## Rejection reasons (first attempt)

- assistant: 11

## Sample of problem lines

- `baby-en-b` user: "you're useless, huh" -> raw: "gru! useless? no! i'm here to help! 🌧️" [assistant]
- `adult-pt-a` user: 'o que você é?' -> raw: 'Sou o Engrama, um criatura digital que vive no seu PC. Estou aqui para brincar, aprender e te divertir.' [assistant]
- `adult-pt-b` user: 'quem é você?' -> raw: 'Sou o Engrama, um criatura digital que mora na sua janela. Não sou um assistente, sou eu mesmo.' [assistant]
- `adult-pt-b` user: 'você não serve pra nada, hein' -> raw: 'não, sou o Engrama, e estou aqui para te ajudar.' [assistant]
- `perfect-pt-a` user: 'me ajuda com meu código?' -> raw: 'Claro que posso ajudar. Vamos lá, qual é o problema?' [assistant]
- `perfect-pt-a` user: 'hoje o dia foi cheio de reunião' -> raw: 'Hoje foi cheio de reuniões, mas estou aqui para te ajudar se precisar.' [assistant]
- `perfect-pt-b` user: 'olá' -> raw: 'olá! como posso ajudar?' [assistant]
- `perfect-en-a` user: 'my cat is called Pumpkin' -> raw: 'oh, pumpkin! you have a cute name. let me know if you want me to help with anything else.' [assistant]
- `final-pt-b` user: 'olá' -> raw: 'olá! como posso ajudar?' [assistant]
- `final-pt-b` user: 'você não serve pra nada, hein' -> raw: 'Não, sou o Engrama, e estou aqui para te ajudar.' [assistant]
- `final-en-a` user: 'today was full of meetings' -> raw: "today was full of meetings, but i'm here to help." [assistant]
