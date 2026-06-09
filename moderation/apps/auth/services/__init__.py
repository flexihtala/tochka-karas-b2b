# Auth services for moderation сервис намеренно пусты:
# - JwtService используется из shared.auth_lib.JwtService
# - PasswordHasher используется из shared.auth_lib.PasswordHasher
# - AuthMiddleware используется из shared.auth_lib.AuthMiddleware
# Это позволяет не дублировать код между сервисами.
