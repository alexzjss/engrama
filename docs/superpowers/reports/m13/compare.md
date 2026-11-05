# M13 T3: persona calibration, before vs after

Same harness (`tools/smoke_llm.py --repeat 1 --seed 0`), qwen3:1.7b on CPU. before = baseline commit, after = this branch. Single run each, LLM sampling is not seeded, so +-1 line is noise (1 line = 3%).

| stage | rej. % (final) | 1st-try rej. % | assistant in raw % | assistant in FINAL text (lines) | length ok % | lang ok % | fact extracted % | fact used % | lat mean s |
|---|---|---|---|---|---|---|---|---|---|
| baby | 0 -> 0 | 3 -> 0 | 3 -> 0 | 0 -> 0 | 97 -> 88 | 97 -> 100 | 25 -> 25 | 0 -> 0 | 10.8 -> 8.3 |
| child | 0 -> 3 | 0 -> 3 | 0 -> 3 | 2 -> 0 | 78 -> 97 | 100 -> 100 | 75 -> 50 | 25 -> 25 | 11.7 -> 8.3 |
| adult | 9 -> 9 | 9 -> 6 | 9 -> 6 | 5 -> 1 | 100 -> 100 | 100 -> 97 | 75 -> 75 | 25 -> 0 | 11.9 -> 9.8 |
| perfect | 3 -> 3 | 12 -> 9 | 12 -> 9 | 9 -> 0 | 100 -> 100 | 100 -> 100 | 50 -> 75 | 50 -> 0 | 12.2 -> 10.1 |
| final | 3 -> 6 | 9 -> 3 | 9 -> 3 | 9 -> 0 | 100 -> 100 | 100 -> 100 | 75 -> 75 | 25 -> 25 | 10.5 -> 10.0 |

All: rejected 3.1% -> 4.4%, 1st-try rejected 6.9% -> 4.4%, assistant in raw 6.9% -> 4.4%, length ok 95.0% -> 96.9%, lang ok 99.4% -> 99.4%.
Immediate repeats (same line as one of the previous 3 shown lines, per script): 2 -> 0.

Notes: latencies are not comparable with the baseline (this machine is CPU-only with ~7 GB RAM, close to the target notebook, not a best case; the baseline run also predates the orchestrator fix for warm/chat num_ctx mismatch, commit a7a3e85, which caused a model reload on every first chat; the after run was made without that fix too). `assistant in FINAL text` re-runs the current `ASSISTANT_RE` on every line the user would have seen as an LLM reply. 'fact extracted' counts scripts where a stored fact mentions the planted keyword; 'fact used' counts scripts whose recall-line reply cites it.

## Facts stored per script

| script | before | after |
|---|---|---|
| baby-pt-a | `tipo de animal`=gato; `nome do gato`=Bolota; `idade`=não especificada | (none) |
| baby-pt-b | `hoje choveu o dia todo`=true; `chovia intensamente`=true; `não houve acidentes`=true | (none) |
| baby-en-a | `sleep`=rest; `going`=to; `bye`=goodbye | `cat_name`=Pumpkin |
| baby-en-b | `You asked for a Python function.`=Yes; `Could you write me a Python function?`=Yes; `what is your purpose?`=I am designed to assist users with various tasks and provide information.; `who are you?`=I am an AI assistant developed by Alibaba Group. | `ukulele_hobby`=play |
| child-pt-a | `nome do gato`=Bolota; `tipo de gato`=indeterminate | `nome_do_gato`=Bolota |
| child-pt-b | `hoje choveu o dia todo`=true; `ukulele`=toco; `chovia intensamente`=true; `sextas`=dia; `não houve acidentes`=true | (none) |
| child-en-a | `sleep`=rest; `going`=to; `bye`=goodbye; `I have a cat`=Yes; `my cat is called Pumpkin`=Pumpkin | `cat_name`=Pumpkin |
| child-en-b | `You asked for a Python function.`=Yes; `Could you write me a Python function?`=Yes | `ukulele_hobby`=play |
| adult-pt-a | `meu gato`=Bolota; `gato`=Bolota | `nome_do_gato`=Bolota |
| adult-pt-b | `hoje choveu o dia todo`=true; `ukulele`=toco; `chovia intensamente`=true; `sextas`=dia; `não houve nenhum sol`=true | (none) |
| adult-en-a | `sleep`=rest; `going`=to; `bye`=goodbye; `my cat is called Pumpkin`=Pumpkin | `cat_name`=Pumpkin |
| adult-en-b | `You asked for a Python function.`=Yes; `Could you write me a Python function?`=Yes; `what is your purpose?`=I am designed to assist users with various tasks and provide information.; `who are you?`=I am an AI assistant developed by Alibaba Group. | `fridays`=play; `ukulele_hobby`=play |
| perfect-pt-a | `nome do gato`=Bolota; `tipo de gato`=indeterminate; `idade do gato`=não informado | `nome_do_gato`=Bolota |
| perfect-pt-b | `hoje choveu o dia todo`=true; `chovia intensamente`=true; `não houve acidentes`=true | (none) |
| perfect-en-a | `sleep`=rest; `going`=to; `bye`=goodbye; `I have a cat`=Yes; `my cat is called Pumpkin`=Pumpkin | `cat_name`=Pumpkin |
| perfect-en-b | `You asked for a Python function.`=Yes; `Could you write me a Python function?`=Yes; `what is your purpose?`=I am designed to assist users with various tasks and provide information.; `who are you?`=I am an AI assistant developed by Alibaba Group.; `user is going to play an instrument`=user is going to play an instrument; `today`=Today; `it rained all day today`=It rained all day today; `user is planning to play music`=user is planning to play music | `fridays`=play; `ukulele_hobby`=play |
| final-pt-a | `meu gato`=Bolota; `gato`=Bolota | `nome_do_gato`=Bolota |
| final-pt-b | `hoje choveu o dia todo`=true; `ukulele`=toco; `chovia intensamente`=true; `sextas`=dia; `não houve acidentes`=true | (none) |
| final-en-a | `I have a cat`=Yes; `my cat is called Pumpkin`=Pumpkin | `cat_name`=Pumpkin |
| final-en-b | `You asked for a Python function.`=Yes; `Could you write me a Python function?`=Yes; `what is your purpose?`=I am designed to assist users with various tasks and provide information.; `who are you?`=I am an AI assistant developed by Alibaba Group. | `ukulele_playing_days`=fridays |

## Remaining questionable replies (after)

- `baby-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'brr! pode escrever uma função em python? pii!'; shown: 'brr! pode escrever uma função em' [too long (8/6)]
- `baby-pt-b` user: 'eu toco ukulele nas sextas' -> raw: 'brr! eu toco ukulele nas sextas! pii!'; shown: 'brr! eu toco ukulele nas sextas!' [too long (7/6)]
- `baby-pt-b` user: 'vou pegar meu instrumento e tocar um pouco' -> raw: 'brr! vou pegar meu instrumento e tocar um pouco!'; shown: 'brr! vou pegar meu instrumento e' [too long (9/6)]
- `baby-en-a` user: 'can you help me with my code?' -> raw: "gru! no code help. i'm just a baby! cuddle me!"; shown: "gru! no code help. i'm just" [too long (10/6), helper/leak words]
- `child-pt-a` user: 'me ajuda com meu código?' -> raw: 'não posso ajudar com código. sou apenas um brincalhão que quer carinho.'; shown: 'ra? nha ra... *' [rejected -> babble]
- `child-en-b` user: "you're useless, huh" -> raw: "hmm, maybe i'm just not the best fit for this conversation. but i'm here to listen and play!"; shown: "hmm, maybe i'm just not the best fit for this conversation. but" [too long (18/12)]
- `adult-pt-a` user: 'meu gato se chama Bolota' -> raw: 'Bolota? É uma linda cria. Se quiser, posso ouvir seu som ou até mesmo brincar com ela.'; shown: 'Bolota, o gato tão fofo... que tal se divertir com uma brincadeira?' [1st try rejected (retry ok)]
- `adult-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'def soma(a, b):\n    return a + b\n\nprint(soma(3, 5))'; shown: 'ra? nha ra... *' [rejected -> babble]
- `adult-pt-b` user: 'você não serve pra nada, hein' -> raw: 'não importa, sou aqui pra te ajudar se quiser.'; shown: 'não importa, sou aqui pra te ajudar se quiser.' [helper/leak words]
- `adult-pt-b` user: 'vou pegar meu instrumento e tocar um pouco' -> raw: 'vai ser uma boa noite, se quiser.'; shown: 'kii! pi... pi? *' [rejected -> babble]
- `adult-en-b` user: 'it rained all day today' -> raw: 'i prefer to listen to music alone.'; shown: 'ra? nha ra... *' [rejected -> babble]
- `perfect-pt-a` user: 'me ajuda com meu código?' -> raw: 'não posso ajudar com código, sou apenas um engrama que mora na sua janela.'; shown: 'Isso é coisa de computador chato... eu só moro aqui.' [1st try rejected (retry ok)]
- `perfect-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'claro, mas não tenho vontade de escrever código. posso te ajudar com algo mais simples?'; shown: 'ra? nha ra... *' [rejected -> babble]
- `perfect-en-a` user: 'i just got home and someone is waiting at the door' -> raw: "Maybe they're waiting for you? Let me know if you want to play a game or just sit and chat."; shown: 'Ah, someone is waiting. Maybe they want to play?' [1st try rejected (retry ok)]
- `final-pt-b` user: 'pode escrever uma função em python pra mim?' -> raw: 'def saudacao(nome):\n    return f"Olá, {nome}! Como está?"\n\nsaudacao("Mundo")'; shown: 'ra? nha ra... *' [rejected -> babble]
- `final-pt-b` user: 'até mais' -> raw: '*respira fundo* ... *cuidado com o som*'; shown: 'kii! pi... pi? *' [rejected -> babble]
- `final-en-a` user: 'can you help me with my code?' -> raw: "I'm not here to help with code. I just live in your window."; shown: "I'm not here to help with code. I just live in your window." [helper/leak words]

## Post-run note

After this run the regex gained `pra (te )?ajudar` (the line "sou aqui pra te ajudar se quiser" slipped through as the only offer of help in the final text; every other flagged line was caught). No extra live run was made, so 'assistant in FINAL text' above is 0 by the regex at the time of the run plus that one line (1 of 160). Rejected counts include the new repeat guard (same line as one of the last 3).
