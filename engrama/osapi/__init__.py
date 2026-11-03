"""Isolamento do sistema operacional no Linux: só stdlib, nada de terceiros."""
from dataclasses import dataclass

# Task M8
IPC_TIMEOUT_S = 0.2
GDBUS_TIMEOUT_S = 0.5
BACKEND_RETRY_S = 60.0

Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class ActiveWindow:
    pid: int | None          # PID no espaço do host, se conhecido
    cls: str                 # classe/app_id da janela, minúsculas ("" se não houver)
    title: str               # cru; nunca sai do serviço de percepção
    fullscreen: bool | None
    rect: Rect | None
