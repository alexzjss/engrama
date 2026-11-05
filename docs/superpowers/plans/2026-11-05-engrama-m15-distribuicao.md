# Engrama M15: Distribuição, plano de implementação

**Objetivo:** alguém que não é o dev baixa um build do Release, abre, e o Engrama funciona: dados na pasta certa do SO, Ollama encontrado sem disco fixo, atalho no menu, início automático opcional.

**Roadmap:** `docs/superpowers/specs/2026-11-04-engrama-m12-m15-roadmap.md` (seção M15). Parte de `main` depois do merge do M13 e do M14 (rebase da branch `m15` se ela nascer antes).

**Execução:** orquestração pelo Opus; subagentes Sonnet (caminhos, empacotamento, integração com o desktop) e Haiku (docs, testes mecânicos) em worktrees no scratchpad da sessão, partindo da branch `m15`. Um PR no fim. **Sem** linhas de coautoria de IA em commits e PR.

**Pontos de decisão humanos (decididos em 2026-11-05: as três recomendações aprovadas):**
1. **Bandeja do sistema**: (a) não ter no M15; (b) `pystray` opcional (extra `tray`), só no Windows e no X11; (c) `pystray` obrigatório. Recomendação: **(a)**. A janela já é o ícone vivo, `pystray` no Wayland é instável e é mais uma dependência no build.
2. **Formato do build Linux**: (a) pasta única do PyInstaller em `.tar.gz`; (b) AppImage. Recomendação: **(a)** agora; AppImage depois, se pedirem.
3. **Assinatura do build Windows**: sem assinatura (o SmartScreen avisa na primeira abertura; o README explica). Assinar exige certificado pago, fora do ciclo.

## Estado atual (diagnóstico do código)

| Ponto | Onde | Problema |
|---|---|---|
| Pasta de dados | `engrama/config.py:13` `default_data_dir()` = `<repo>/data` | Instalado fora do checkout, grava dentro do site-packages ou do bundle |
| Receitas | `engrama/app/cli.py:29,115`, `engrama/lab/suite.py:16` usam `parents[2] / "recipes"` | `recipes/` fica fora do pacote: `pip install .` (não editável) e o PyInstaller não acham a receita |
| i18n | `engrama/app/i18n/*.json` | Não declarados como package data; um wheel sai sem eles |
| Ollama no Windows | `config.py:17-32` | `E:\Ollama\...` como padrão de `ollama_exe`, `ollama_home`, `ollama_models` |
| Integração | nenhuma | Sem `.desktop`, sem atalho, sem autostart |
| Release | `.github/workflows/ci.yml` só lint + testes | Nenhum build, nenhum Release |

## Desenho

- **Recursos do pacote**: `recipes/` passa a viver em `engrama/recipes/` (mover com `git mv`; `recipes/` na raiz vira só o que o lab usa, se precisar, ou some). Acesso por um único helper `engrama.resources.recipes_dir()` via `importlib.resources`, que funciona instalado, editável e no bundle (`sys._MEIPASS`). `pyproject.toml` declara `package-data` para `*.toml` e `*.json`.
- **Pasta de dados** (`engrama/paths.py`, novo):
  - ordem: `--data-dir` > variável `ENGRAMA_DATA_DIR` > **modo dev** (o pacote está num checkout git: existe `<raiz>/.git` e `<raiz>/pyproject.toml`) usa `<repo>/data` como hoje > pasta do SO;
  - pasta do SO: Windows `%APPDATA%\Engrama`; Linux `$XDG_DATA_HOME/engrama` (padrão `~/.local/share/engrama`); macOS `~/Library/Application Support/Engrama` (sem build, só o caminho);
  - **migração explícita**: `engrama --migrate-from PATH` copia (não move) um `data/` antigo para a pasta nova, se a nova estiver vazia; recusa se a nova já tiver save. Nunca automática. Na primeira abertura sem save, se existir `<repo>/data/save` acessível, só uma linha no log sugerindo o comando.
- **Ollama** (`config.py`): Windows procura, nesta ordem, `shutil.which("ollama")`, `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` (instalador oficial), `%ProgramFiles%\Ollama\ollama.exe`; nenhum achado = `ollama_exe` vazio e a UI de Modelos já mostra "Ollama não encontrado". `ollama_home` e `ollama_models` padrão `None` em todos os SOs. Configs antigos com `E:\Ollama` continuam valendo (é só um valor salvo).
- **Builds** (`packaging/engrama.spec` + `.github/workflows/release.yml`):
  - PyInstaller, pasta única (`onedir`), sem console no Windows (`--windowed`), com `recipes`, `i18n` e ícone;
  - gatilho: tag `v*`; jobs `ubuntu-latest` e `windows-latest`; smoke no próprio job: `engrama --frames 120 --no-llm --data-dir <tmp>` com `SDL_VIDEODRIVER=dummy`;
  - artefatos: `engrama-<versão>-windows-x64.zip` e `engrama-<versão>-linux-x64.tar.gz` anexados ao Release (rascunho; o usuário publica);
  - medir e registrar tamanho do pacote e tempo até o primeiro quadro.
- **Integração com o desktop** (`engrama/app/integration/`):
  - Linux: `engrama --install-desktop` grava `~/.local/share/applications/engrama.desktop` e o ícone em `~/.local/share/icons/hicolor/<n>x<n>/apps/engrama.png`; `--uninstall-desktop` remove só o que gravou;
  - Windows: atalho `.lnk` no Menu Iniciar (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Engrama.lnk`) criado por PowerShell (`WScript.Shell`), sem dependência nova;
  - **autostart opt-in** em Configurações (F6), desligado por padrão: Linux `~/.config/autostart/engrama.desktop`; Windows chave `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` via `winreg`. Ligar e desligar escreve e apaga; o estado na UI é lido do SO (não de um campo do config), para não divergir.
  - Ícone gerado do próprio sprite (ovo ou bebê de uma semente fixa) por script em `tools/`, PNG 256 e `.ico` multi-tamanho, versionado em `engrama/app/assets/`.

## Restrições globais

- Nada em `engrama/kernel/**`, `engrama/mind/**`, `engrama/modules/**`, `engrama/services/**` (salvo o caminho das receitas no `lab`, se mover).
- `SAVE_VERSION`, schema do save, `vocab` intocados. Saves existentes abrem iguais (o conteúdo da pasta não muda, só onde ela está).
- **Nenhum teste toca o HOME real nem o registro real**: tudo por injeção (`env`, `platform`, `home`, uma fachada de registro falsa). Testes de Windows rodam na CI Windows; no Linux, por simulação com `platform="win32"` onde fizer sentido.
- i18n: chaves novas em PT e EN (`settings.autostart`, mensagens de migração).
- Dependências de runtime: nenhuma nova (decisão 1 pode mudar isso). `pyinstaller` só num extra `build`.

## Tarefas

Ordem: **{T1, T2} em paralelo → T3 → {T4, T5} em paralelo → T6**.

### T1: Recursos dentro do pacote (Sonnet)

- [ ] `git mv recipes engrama/recipes`; `engrama/resources.py` com `recipes_dir()` e `i18n_dir()`; trocar os três `parents[2] / "recipes"` e o carregamento do i18n.
- [ ] `pyproject.toml`: `[tool.setuptools.package-data] engrama = ["recipes/*.toml", "app/i18n/*.json", "app/assets/*"]`.
- [ ] Teste: construir um wheel (`python -m build --wheel` ou `pip wheel . --no-deps`) num tmp, instalar num venv descartável **não editável** e rodar `engrama --frames 30 --no-llm --data-dir <tmp>` (marcado `slow`).
- [ ] Commit `refactor(m15): recipes and i18n ship inside the package`.

### T2: Pasta de dados e Ollama sem disco fixo (Sonnet)

- [ ] `engrama/paths.py`: `resolve_data_dir(cli_arg, env, platform, home, package_root)` pura e testada para cada ramo; `default_data_dir()` passa a chamá-la.
- [ ] `--migrate-from PATH` no CLI, com as recusas descritas; testes com pastas temporárias.
- [ ] `config.py`: busca do Ollama no Windows como no desenho; `ollama_home`/`ollama_models` padrão `None`; teste de que um config salvo com `E:\Ollama` ainda carrega igual no Windows.
- [ ] Commit `feat(m15): OS data dir, explicit migration, Ollama found without a fixed drive`.

### T3: Build com PyInstaller (Sonnet), depois de T1

- [ ] `packaging/engrama.spec` (onedir, windowed no Windows, dados e ícone); extra `build = ["pyinstaller"]`.
- [ ] Build local no Linux; rodar o binário com `--frames 120 --no-llm`; medir tamanho e tempo até o primeiro quadro.
- [ ] `.github/workflows/release.yml`: tag `v*`, matriz Linux/Windows, smoke, artefatos no Release em rascunho. `workflow_dispatch` também, para testar sem tag (artefato do job, sem Release).
- [ ] Commit `build(m15): PyInstaller bundles and release workflow`.

### T4: Atalho e autostart (Sonnet), depois de T2

- [ ] `engrama/app/integration/{linux,windows}.py` com fachada injetável (`fs`, `registry`, `run_powershell`); `--install-desktop`/`--uninstall-desktop`.
- [ ] Opção de autostart em F6, lida do SO; o comando gravado aponta para o executável atual (`sys.executable` no bundle, `python -m engrama` instalado; em modo dev, a opção aparece desabilitada com explicação).
- [ ] Testes com fachadas falsas: liga, desliga, idempotência, não apaga arquivo que não gravou.
- [ ] Commit `feat(m15): desktop entry, Start menu shortcut and opt-in autostart`.

### T5: Ícone (Haiku), depois de T1

- [ ] `tools/make_icon.py`: sprite de semente fixa → `engrama/app/assets/icon-256.png` e `icon.ico` (16, 32, 48, 256). Ícone da janela do pygame passa a usar o PNG.
- [ ] Commit `feat(m15): app icon from the creature sprite`.

### T6: Smoke em máquina limpa, docs e PR (Haiku para docs, orquestrador para o resto)

- [ ] Rodar o `release.yml` por `workflow_dispatch`; baixar os dois artefatos; Linux: extrair num container ou usuário limpo (`podman run` com HOME vazio, driver dummy) e conferir pasta de dados e `--install-desktop`.
- [ ] Checklist H para o usuário: Windows real (abrir o zip, SmartScreen, Ollama do instalador oficial, autostart após reiniciar), Linux real (menu do desktop, autostart após login).
- [ ] README PT/EN: seção "Instalar" (download do Release primeiro, `pip` para devs), pasta de dados por SO, migração, autostart; tirar "só `pip install -e .`" das limitações; linha M15 no roadmap.
- [ ] `version = "0.15.0"`; `ruff check .` e suíte verdes; push; PR com tamanhos, tempos e a checklist H.

## Aceite do M15

1. Wheel não editável e bundle rodam fora do checkout, com receitas e i18n.
2. Dados na pasta do SO por padrão; modo dev e `--data-dir` como antes; migração só por comando.
3. Nenhum `E:\` como padrão; Ollama do instalador oficial encontrado no Windows.
4. Release (rascunho) com builds Windows e Linux gerados pela CI, com smoke verde no job.
5. Atalho e autostart ligam e desligam (testes com fachada + checklist H no SO real).

## Riscos

| Risco | Mitigação |
|---|---|
| PyInstaller esquece módulo importado de forma lazy (`cli.py` importa dentro de `_main`) | `hiddenimports` gerado por um script que lista `engrama.*`; smoke no job pega a falta |
| `numpy` + `pygame-ce` deixam o bundle grande | Medir; `excludes` de `tkinter`, testes do numpy; aceitar até ~120 MB e registrar |
| Mover `recipes/` quebra o lab e testes que leem caminho fixo | T1 troca todos os usos pelo helper; grep de `"recipes"` no aceite da tarefa |
| Usuário perde o save ao trocar de pasta | Pasta nova vazia + mensagem sugerindo `--migrate-from`; cópia, nunca move |
| Antivírus marca o executável sem assinatura | Documentar; onedir (menos falso positivo que onefile) |
| Conflito com M13/M14 no README e na versão | M15 nasce depois dos dois merges; se não, rebase antes do PR |
