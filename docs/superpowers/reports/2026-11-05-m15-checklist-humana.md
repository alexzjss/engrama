# M15: checklist humana (sistemas reais)

Data: 2026-11-05. O que a CI não vê: SmartScreen, menu do sistema, início automático após reinício e login, Ollama instalado pelo instalador oficial, janela e ícone num desktop de verdade.

Medidas da CI e do build local (Linux): pacote `engrama/` com **98 MB**; primeiro quadro em cerca de **0,5 s**. Windows: preencher ao baixar o zip.

Antes de começar: baixe os pacotes do Release (rascunho) ou os artefatos do workflow `Release` (`workflow_dispatch`). Use um usuário de teste ou confirme que as pastas de dados abaixo não existem; não apague o seu save real. Ao final, registre para cada item **OK** ou **falhou** com o que você viu.

## Windows

1. **Baixar e extrair.** Baixe `engrama-<versão>-windows-x64.zip` e extraia numa pasta comum (por exemplo `C:\Users\<você>\Apps`).
   - Observe: a pasta `engrama\` contém `engrama.exe` e as DLLs; o zip tem uma única pasta na raiz.
   - Registre o tamanho do zip.
2. **SmartScreen.** Dê dois cliques em `engrama\engrama.exe`.
   - Observe: aparece "O Windows protegeu o computador". Clique em **Mais informações** e depois em **Executar assim mesmo**.
   - Observe: o app abre sem janela de console preta, e o `engrama.exe` no Explorer mostra o ícone da criatura.
3. **Primeira abertura.** Responda a tela de permissões (pode deixar tudo "agora não").
   - Observe: `%APPDATA%\Engrama` existe (Win+R, digite `%APPDATA%\Engrama`) com `host.json` e a pasta `save\`.
   - Observe: nenhuma tela ou mensagem cita `E:\`.
4. **Ollama do instalador oficial.** Instale o Ollama pelo instalador de ollama.com, sem alterar o PATH. Feche e reabra o Engrama.
   - Observe: `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` existe.
   - Observe: no F5 o menu não diz "Ollama não encontrado". Baixe `qwen3:1.7b` pelo F5 e envie uma mensagem com Enter; a criatura responde com o modelo.
   - Opcional: desinstale o Ollama (ou renomeie a pasta) e reabra o F5. Observe: o menu diz que o Ollama não foi encontrado, sem erro.
5. **Atalho no Menu Iniciar.** Num PowerShell, dentro de `engrama\`, rode `.\engrama.exe --install-desktop`.
   - Observe: a saída mostra "Instalado / Installed:" com o caminho de `Engrama.lnk`.
   - Observe: em `%APPDATA%\Microsoft\Windows\Start Menu\Programs` existe `Engrama.lnk`, e procurar "Engrama" no Menu Iniciar mostra o app com o ícone da criatura. Clicar abre o app.
6. **Início automático: ligar.** Com o app aberto, abra **F6** (Configurações) e ligue "Iniciar com o sistema".
   - Observe: no `regedit`, em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, existe o valor "Engrama".
   - Reinicie o computador e entre na sessão. Observe: o Engrama abre sozinho depois do login.
7. **Início automático: desligar e estado lido do sistema.** Abra o F6 e desligue a opção.
   - Observe: o valor "Engrama" sumiu do `regedit`. Reinicie e confirme que o app não abre sozinho.
   - Ligue de novo pelo F6, depois apague o valor "Engrama" à mão no `regedit`, feche e reabra o app e o F6. Observe: a opção aparece desligada.
8. **Desinstalar o atalho.** Rode `.\engrama.exe --uninstall-desktop`.
   - Observe: `Engrama.lnk` sumiu do Menu Iniciar (e o valor do início automático, se estava ligado). `%APPDATA%\Engrama` continua lá com o save.

## Linux

Teste num desktop com menu de aplicativos (GNOME, KDE ou similar) e, de preferência, numa conta sem Python de projeto.

1. **Extrair e rodar.** `tar -xzf engrama-<versão>-linux-x64.tar.gz` e depois `./engrama/engrama`.
   - Observe: a janela abre sem pedir Python, pip ou venv. Registre `du -sh engrama` (referência da CI: 98 MB).
2. **Pasta de dados.** Feche e confira.
   - Observe: `~/.local/share/engrama/` existe com `host.json` e `save/`.
   - Observe: nada foi criado dentro da pasta extraída (sem `data/`).
3. **Menu de aplicativos.** Dentro da pasta extraída, rode `./engrama/engrama --install-desktop`.
   - Observe: a saída mostra os arquivos gravados, incluindo `~/.local/share/applications/engrama.desktop` e o ícone em `~/.local/share/icons/hicolor/`.
   - Procure "Engrama" no menu de aplicativos. Pode ser preciso esperar ou sair e entrar de novo. Observe: aparece com o ícone da criatura, e clicar abre o app.
4. **Início automático após login.** Em **F6**, ligue "Iniciar com o sistema".
   - Observe: `~/.config/autostart/engrama.desktop` existe.
   - Saia da sessão e entre de novo. Observe: o Engrama abre sozinho.
5. **Início automático: desligar.** Em **F6**, desligue a opção.
   - Observe: `~/.config/autostart/engrama.desktop` foi removido. Saia e entre de novo para confirmar que o app não abre sozinho.
6. **Desinstalar.** Rode `./engrama/engrama --uninstall-desktop`.
   - Observe: a entrada do menu e o ícone foram removidos. `~/.local/share/engrama/` continua lá com o save.

## Nos dois sistemas

1. **Migração.** Prepare uma pasta `data/` antiga com um save de teste (por exemplo, a de um checkout com o app já usado) e uma pasta de dados nova vazia ou inexistente.
   - Rode `engrama --migrate-from <caminho>/data` (no Windows, `.\engrama.exe --migrate-from "<caminho>\data"`).
   - Observe: a saída diz "Copiado de ... para ..." e o save aparece na pasta de dados nova.
   - Observe: a pasta antiga continua intacta (copia, não move).
2. **Recusa com save existente.** Rode o mesmo comando de novo.
   - Observe: a mensagem "A pasta de destino já tem um save", código de saída 2, e nada muda nas pastas.
3. **Ícone da janela.** Com o app aberto, confira a barra de tarefas ou o alt-tab.
   - Observe: o ícone é a criatura (PNG no Linux, `.ico` no Windows), não o ícone padrão do pygame.

## Resultado

| Item | Sistema | OK / falhou | O que foi visto |
|---|---|---|---|
| Windows 1 a 8 | Windows | | |
| Linux 1 a 6 | Linux | | |
| Nos dois 1 a 3 | ambos | | |

Tamanhos e tempos: zip (Windows) ______ MB; tar.gz (Linux) 98 MB; primeiro quadro (Linux) ~0,5 s; Windows ______ s.
