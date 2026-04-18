# Módulo unificado — l4d2_udp_base (ip/nf)

## Objetivo
Aplicar base de control UDP para tráfico de juego (NEW/ESTABLISHED) e ICMP.

## Backends
- iptables: `modules/ip/ip_50_l4d2_udp_base.sh` (`ID=ip_l4d2_udp_base`)
- nftables: `modules/nf/nf_50_l4d2_udp_base.sh` (`ID=nf_l4d2_udp_base`)

## Variables
- `L4D2_GAMESERVER_UDP_PORTS`, `L4D2_SOURCETV_UDP_PORTS`, `L4D2_CMD_LIMIT`
- `LOG_PREFIX_UDP_NEW_LIMIT`, `LOG_PREFIX_UDP_EST_LIMIT`, `LOG_PREFIX_ICMP_FLOOD`
- `UDP_NEW_SRC_RATE`, `UDP_NEW_SRC_BURST`
- `UDP_NEW_GLOBAL_RATE`, `UDP_NEW_GLOBAL_BURST`
- `ENABLE_UDP_NEW_FFFFFFFF_BYPASS`
- `ENABLE_UDP_NEW_LARGE_FILTER`, `UDP_NEW_LARGE_DROP_MIN_LEN`
- `ENABLE_UDP_BASELINE_LOGS` (`false` recomendado en producción)
- nftables: `STEAM_GROUP_SIGNATURES` para bypass temprano de firmas `0xFFFFFFFFxx` observadas o documentadas

## Bypass de firmas Source
El módulo deja pasar antes del limitador base solo las firmas que realmente tienen un clasificador downstream en `l4d2_a2s_filters` o `l4d2loginfilter`:

- `54` -> `A2S_INFO`
- `55` -> `A2S_PLAYER`
- `56` -> `A2S_RULES`
- `71` -> heartbeat / login short-query según flujo observado, solo en `L4D2_GAMESERVER_UDP_PORTS`
- firmas extra definidas en `STEAM_GROUP_SIGNATURES` cuando `ENABLE_STEAM_GROUP_FILTER=true`

Esto evita que el módulo base bloquee tráfico que luego será clasificado por `l4d2_a2s_filters`. Si una firma no tiene clasificador posterior activo, se mantiene bajo el limitador genérico en vez de caer a `DROP` por el policy final.

SourceTV también puede emitir handshakes cortos `0xFFFFFFFF71 connect...` en `L4D2_SOURCETV_UDP_PORTS`; esos paquetes no pasan por el subfiltro `connect/reserve` de GameServer y por eso se mantienen bajo el limitador `NEW` genérico para evitar falsos positivos.

## Nota operativa importante
Si `serverbrowser` o `steamgroup` dejan de mostrar servidores, revisar primero que el backend activo realmente esté leyendo:

- `UDP_NEW_SRC_RATE`
- `UDP_NEW_SRC_BURST`
- `UDP_NEW_GLOBAL_RATE`
- `UDP_NEW_GLOBAL_BURST`
- `ENABLE_UDP_NEW_FFFFFFFF_BYPASS`
- `ENABLE_STEAM_GROUP_FILTER`

Con el perfil actual del proyecto se recomienda `8/24` por origen+puerto y `240/960` global por puerto como piso operativo para no romper descubrimiento.

## Hardening para sprays UDP grandes
Cuando `UDP_NEW_LIMIT` muestra datagramas `NEW` claramente sobredimensionados y sin firma Source clasificada downstream, el módulo puede cortar ese tráfico antes del rate limit genérico:

- `ENABLE_UDP_NEW_LARGE_FILTER=true` activa el pre-filtro.
- `UDP_NEW_LARGE_DROP_MIN_LEN` usa longitud IP total, no el `LEN` final de cabecera UDP del log.
- Un umbral conservador como `1024` corta sprays cercanos a MTU (por ejemplo paquetes de ~1228 bytes IP totales) sin tocar short queries/login.

Si el patrón observado es de paquetes pequeños y repetitivos, el endurecimiento principal sigue siendo `UDP_NEW_SRC_RATE` y `UDP_NEW_SRC_BURST`; para clasificar mejor esos casos hace falta captura `pcap` del payload.

## Politica de logging
`UDP_NEW_LIMIT` y `UDP_EST_LIMIT` pertenecen al filtro preventivo/base, no a la clasificación final de abuso.

Por eso:

- `ENABLE_UDP_BASELINE_LOGS=false` es el default recomendado en producción.
- `ENABLE_UDP_BASELINE_LOGS=true` sirve para diagnóstico cuando quieres ver falsos positivos o ajustar thresholds base.
- `ICMP_FLOOD` se mantiene logueado porque representa una categoría de abuso más clara.

## Límites del conocimiento público
Valve documenta claramente las firmas de `Server Queries` y del `Master Server Query Protocol`, pero no publica una firma exclusiva y oficial para "Steam Group" a nivel de byte comparable a `54/55/56/57/69`.

Por eso:

- `STEAM_GROUP_SIGNATURES` debe tratarse como compatibilidad operacional, no como estándar oficial.
- `00` puede mantenerse si aparece en capturas reales.
- cualquier firma nueva debe entrar por observación en pcap/logs antes de hardcodearse.

## Referencias oficiales
- [Valve Developer Community: Server queries](https://developer.valvesoftware.com/wiki/Server_queries)
- [Valve Developer Community: Master Server Query Protocol](https://developer.valvesoftware.com/wiki/Master_Server_Query_Protocol)
- [Valve Developer Community: Add-on](https://developer.valvesoftware.com/wiki/Add-on) (`sv_steamgroup`, `sv_search_key`, private matchmaking tags)
- [Politica interna: Source Query Bypass](../source-query-bypass-policy.md)

## Nota operativa
Desactivar en nodos sin juegos excluyendo `l4d2_udp_base` de `MODULES_ONLY`.
