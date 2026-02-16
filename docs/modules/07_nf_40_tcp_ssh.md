Módulo 07 — nf_40_tcp_ssh.sh

Descripción:
Este módulo configura reglas TCP específicas para SSH en `nftables`. Incluye excepciones para puertos SSH, controles de tasa y comportamiento de exposición pública para reducir fuerza bruta manteniendo acceso administrativo seguro.

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
- Combinar con autenticación robusta (llaves, 2FA) y/o salto administrativo (VPN, jump host).
- Probar en entornos controlados antes de desplegar en producción para evitar cortes accidentales de SSH.
