"""Moderation использует shared.auth_lib.AuthMiddleware напрямую.

Этот файл — re-export для соответствия структуре b2b/apps/auth/middleware.py.
Локальная middleware не требуется, потому что shared/AuthMiddleware уже корректно
устанавливает request.state.user из JWT-клеймов.
"""

from shared.auth_lib import AuthMiddleware as AuthMiddleware
