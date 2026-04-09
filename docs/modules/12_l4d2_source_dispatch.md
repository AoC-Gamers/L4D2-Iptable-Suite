# Módulo específico iptables — l4d2_source_dispatch

## Objetivo
Insertar despacho temprano para consultas Source firmadas (`0xFFFFFFFFxx`) antes del limitador genérico `ct state NEW` de `l4d2_udp_base`.

## Backend
- iptables: `modules/ip/ip_72_l4d2_source_dispatch.sh` (`ID=ip_l4d2_source_dispatch`)

## Cuándo usarlo
Útil cuando el browser/publicación de L4D2 funciona al hacer bypass total de puertos, pero falla al volver a pasar por la protección normal. Ese patrón suele indicar que parte del tráfico firmado está cayendo primero en `UDP_GAME_NEW_LIMIT` y no llega limpio a `l4d2_a2s_filters`.

## Dependencia operativa
Este módulo requiere que `l4d2_a2s_filters` esté activo, porque reutiliza sus cadenas:

- `A2S_LIMITS`
- `A2S_PLAYERS_LIMITS`
- `A2S_RULES_LIMITS`
- `STEAM_GROUP_LIMITS`
- `l4d2loginfilter`

Si esas cadenas no existen, el módulo falla con error explícito.

## Firmas despachadas temprano
Despacha al inicio de `INPUT` o `DOCKER-USER` según `TYPECHAIN`:

- `54` -> `A2S_LIMITS`
- `55` -> `A2S_PLAYERS_LIMITS`
- `56` -> `A2S_RULES_LIMITS`
- `57` -> `A2S_LIMITS` como tratamiento conservador para challenge legacy
- `69` -> `STEAM_GROUP_LIMITS` como firma documentada legacy
- `71` -> `l4d2loginfilter` solo en `L4D2_GAMESERVER_UDP_PORTS`
- firmas extra de `STEAM_GROUP_SIGNATURES` cuando `ENABLE_STEAM_GROUP_FILTER=true`

## Efecto estructural
En vez de depender de que `l4d2_udp_base` haga `RETURN` antes del limitador genérico, este módulo inserta reglas al tope de la cadena principal con `iptables -I`.

Eso logra que el tráfico Source firmado conocido:

1. se clasifique primero,
2. entre a su cadena específica,
3. y no dependa del camino genérico `UDP_GAME_NEW_LIMIT`.

## Variables
- `TYPECHAIN`
- `L4D2_GAMESERVER_UDP_PORTS`
- `L4D2_SOURCETV_UDP_PORTS`
- `ENABLE_STEAM_GROUP_FILTER`
- `STEAM_GROUP_SIGNATURES`

## Recomendación práctica
Si quieres probar este endurecimiento estructural, agrega el alias a `MODULES_ONLY` junto a `l4d2_a2s_filters`:

```env
MODULES_ONLY="chain_setup,loopback,whitelist,allowlist_ports,l4d2_tcpfilter_chain,http_https_protect,l4d2_tcp_protect,l4d2_udp_base,l4d2_packet_validation,l4d2_a2s_filters,l4d2_source_dispatch,finalize"
```

## Nota operativa
No reemplaza `l4d2_udp_base`. Lo complementa para que el tráfico firmado conocido no quede demasiado acoplado al limitador base.
