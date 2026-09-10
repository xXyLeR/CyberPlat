"""
Rate limiter para submissão de flags.

Por que isso é crítico: sem rate limit, um script poderia tentar
milhares de valores de flag por segundo (brute-force). No MVP usamos um
contador em memória por processo (aceitável porque o MVP roda um único
worker); a partir da Fase 4, com múltiplas réplicas do Core API, isso
DEVE migrar para Redis (INCR + EXPIRE), pois um limiter em memória local
não é compartilhado entre processos/pods.
"""
import time
from collections import defaultdict

from app.config import get_settings

settings = get_settings()

_attempts: dict[str, list[float]] = defaultdict(list)


def is_rate_limited(key: str) -> bool:
    now = time.time()
    window_start = now - 60
    _attempts[key] = [t for t in _attempts[key] if t > window_start]
    if len(_attempts[key]) >= settings.flag_submission_max_attempts_per_minute:
        return True
    _attempts[key].append(now)
    return False


def reset_for_tests() -> None:
    _attempts.clear()
