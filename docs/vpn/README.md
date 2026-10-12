# OpenVPN servidor y site-to-site

La suite adapta el firewall; no instala/configura OpenVPN ni añade protocolos VPN.
Separa listener, acceso al host, acceso a redes remotas y NAT. El permiso NAT no
concede filtrado. Un host nativo puede ser gateway sin Docker mediante grants
`forward` y `ROUTED_POLICY=drop`.

## Servidor

El perfil [vpn-gateway.conf](../../config/profiles/vpn-gateway.conf) selecciona
`openvpn_server`. `OVPNSRV_PROTO=udp`, `OVPNSRV_PORT=1194`,
`OVPNSRV_INTERFACE=tun0`, `OVPNSRV_SUBNET=10.8.0.0/24` son defaults del módulo.
La LAN declarada por módulo es `192.168.1.0/24`; el ejemplo usa ficticiamente
`192.0.2.0/24` con `OVPNSRV_LAN_INTERFACE=lan0`, no un default universal.
NAT está desactivado; activarlo exige interfaz LAN explícita y familias compatibles.

[access.example.json](../../config/access.example.json) concede SSH a un
administrador VPN concreto y TCP/9100 a un monitor concreto de LAN. Los demás
puertos/subredes no se autorizan por pertenecer al túnel. Adaptar direcciones,
interfaces y grupos antes de aplicar. Listener publicado en Docker requiere grant
`containers` de `service=openvpn_server`; el túnel soportado debe correr en el host.
`OVPNSRV_DOCKER_INTERFACE` y logging VPN heredado se rechazan.

## Site-to-site

`openvpn_sitetosite` es excluyente con servidor y requiere `OVPNS2S_INTERFACE`,
`OVPNS2S_LOCAL_SUBNETS`, `OVPNS2S_REMOTE_SUBNETS`. No existe perfil S2S automático.
`OVPNS2S_ENABLE_NAT=false`; si se activa, exige `OVPNS2S_LOCAL_INTERFACE`.
Alias `OVPNS2S_ROUTER_ALIAS` usa pares IPv4 `real;alias` separados por coma; SNAT es opt-in mediante
`OVPNS2S_ROUTER_ALIAS_SNAT` y exige `OVPNS2S_LOCAL_INTERFACE` incluso si NAT
general está desactivado. Al configurar alias IPv4, la lista de subredes remotas
usada por ese modo también debe ser solo IPv4; una lista con IPv6 falla al generar.
Redes de una adaptación NAT deben ser de igual familia,
no listas mixtas. Los permisos direccionales siguen declarándose aparte.

## Revisión y recuperación

Desde la raíz del checkout, sin root, el siguiente comando genera un plan con
valores ficticios del perfil; no configura túneles ni aplica reglas:

```sh
./nftables.rules.sh plan --env-file config/profiles/vpn-gateway.conf
```

Revisa los grants de host/forward y la ausencia de bypass completo. Aplica desde
instalación confiable con [confirmación y reversión](../firewall/transactions.md),
y verifica conexión nueva administrativa más servicio permitido/denegado desde
ambos lados del túnel. Si falla, distingue rutas/iroute, interfaz, listener y ACL;
no autorices todo FORWARD para reparar conectividad.

La [prueba de clientes](../testing/clients.md) usa TLS OpenVPN real en namespaces
anidados de una VM; no acredita unidades systemd OpenVPN del destino. PMTU, algunas
variantes SNAT y TLS legacy quedan fuera del alcance demostrado; consulta
[capacidades](../firewall/backends.md) y [limitaciones](../security/limitations.md).

Código: [config.py](../../core/config.py), [compiler.py](../../core/compiler.py).
Pruebas: [clients.py](../../tests/vm/clients.py), [check-engine.py](../../tests/check-engine.py).

Usa únicamente `real;alias,real;alias`, no `|`: aunque el validador interno lo
admite, la generación lo rechaza. Discrepancia de separadores: [incidencia documentalmente detectada](../migration/documentation-review.md#incidencias-funcionales-fuera-del-cambio).
