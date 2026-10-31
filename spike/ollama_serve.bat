@echo off
rem Inicia o servidor Ollama com tudo no disco E (nada no C)
set USERPROFILE=E:\Ollama\home
set HOME=E:\Ollama\home
set OLLAMA_MODELS=E:\Ollama\models
"E:\Ollama\ollama.exe" serve
