Módulo 18 — ip_40_tcp_ssh.sh

Descripción:
Este módulo configura reglas TCP específicas para SSH en `iptables`. Suele incluir excepciones para el puerto SSH, controles de tasa (rate limiting), y listas de confianza para reducir la exposición a ataques de fuerza bruta, manteniendo al mismo tiempo acceso administrativo seguro.

Variables relevantes:
- `SSH_PORT`: puertos SSH del host.
- `SSH_REQUIRE_WHITELIST`:
	- `false` (default): crea regla pública para `SSH_PORT`.
	- `true`: **no** crea regla pública para `SSH_PORT`; acceso SSH solo por whitelist.
- `WHITELISTED_IPS` / `WHITELISTED_DOMAINS`: orígenes de confianza que conservan acceso cuando `SSH_REQUIRE_WHITELIST=true`.

Recomendación operativa:
- Para endurecer exposición de administración, usar `SSH_REQUIRE_WHITELIST=true` junto a whitelist de contingencia LAN y/o dominio/IP de administración remota.

Contextos recomendados:
- Usar en servidores con acceso SSH público o administrativo; preferir restricciones por origen cuando sea posible.
- Combinar con mecanismos de autenticación robustos (llaves, 2FA) y sistemas de gestión de accesos para minimizar riesgos.
- Probar en entornos controlados antes de desplegar en producción para evitar cortes accidentales del servicio SSH.
