# Módulo unificado — l4d2_udp_base (ip/nf)

## Objetivo
Aplicar base de control UDP para tráfico de juego (NEW/ESTABLISHED) e ICMP.

## Backends
- iptables: `modules/ip/ip_50_l4d2_udp_base.sh` (`ID=ip_l4d2_udp_base`)
- nftables: `modules/nf/nf_50_l4d2_udp_base.sh` (`ID=nf_l4d2_udp_base`)

## Variables
- `L4D2_GAMESERVER_PORTS`, `L4D2_TV_PORTS`, `L4D2_CMD_LIMIT`
- `LOG_PREFIX_UDP_NEW_LIMIT`, `LOG_PREFIX_UDP_EST_LIMIT`, `LOG_PREFIX_ICMP_FLOOD`
- `UDP_NEW_SRC_RATE`, `UDP_NEW_SRC_BURST`
- `UDP_NEW_GLOBAL_RATE`, `UDP_NEW_GLOBAL_BURST`
- `ENABLE_UDP_NEW_FFFFFFFF_BYPASS`
- `ENABLE_UDP_BASELINE_LOGS` (`false` recomendado en producción)
- nftables: `STEAM_GROUP_SIGNATURES` para bypass temprano de firmas `0xFFFFFFFFxx` observadas o documentadas

## Bypass de firmas Source
En backend `nftables`, el módulo deja pasar antes del limitador `ct state new` las firmas de consulta/publicación Source que no deberían caer en el rate-limit genérico:

- `54` -> `A2S_INFO`
- `55` -> `A2S_PLAYER`
- `56` -> `A2S_RULES`
- `57` -> `A2S_SERVERQUERY_GETCHALLENGE` legacy
- `69` -> `A2A_PING` legacy
- `71` -> heartbeat / login short-query según flujo observado
- firmas extra definidas en `STEAM_GROUP_SIGNATURES`

Esto evita que el módulo base bloquee tráfico que luego será clasificado por `l4d2_a2s_filters`.

## Nota operativa importante
Si `serverbrowser` o `steamgroup` dejan de mostrar servidores, revisar primero que el backend activo realmente esté leyendo:

- `UDP_NEW_SRC_RATE`
- `UDP_NEW_SRC_BURST`
- `UDP_NEW_GLOBAL_RATE`
- `UDP_NEW_GLOBAL_BURST`
- `ENABLE_UDP_NEW_FFFFFFFF_BYPASS`

Con el perfil actual del proyecto se recomienda `8/24` por origen+puerto y `240/960` global por puerto como piso operativo para no romper descubrimiento.

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
