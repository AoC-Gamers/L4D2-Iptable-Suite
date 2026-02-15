Módulo 07 — nf_40_tcp_ssh.sh

Descripción:
Este módulo añade reglas TCP orientadas a servicios comunes como SSH para el backend `nftables`. Incluye excepciones, límites (rate-limiting) y políticas para minimizar intentos de acceso no autorizados mientras permite administración remota segura.

Contextos recomendados:
- Usar en servidores que ofrezcan acceso SSH remoto; restringir por origen cuando sea posible (redes de administración).
- Aplicar límites de tasa y mecanismos de bloqueo temporales para mitigar fuerza bruta.
- En entornos gestionados, integrar con sistemas de gestión de accesos (VPN, jump hosts) en lugar de exponer SSH directamente.
