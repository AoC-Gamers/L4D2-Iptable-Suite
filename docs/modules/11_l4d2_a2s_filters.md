# Módulo unificado — l4d2_a2s_filters (ip/nf)

## Objetivo
Mitigar flood de consultas A2S/Steam Group y patrones de login (`connect/reserve`).

## Backends
- iptables: `modules/ip/ip_70_l4d2_a2s_filters.sh` (`ID=ip_l4d2_a2s_filters`)
- nftables: `modules/nf/nf_70_l4d2_a2s_filters.sh` (`ID=nf_l4d2_a2s_filters`)

## Variables principales
- `L4D2_GAMESERVER_PORTS`
- `L4D2_TV_PORTS`
- `LOG_PREFIX_A2S_INFO`, `LOG_PREFIX_A2S_PLAYERS`, `LOG_PREFIX_A2S_RULES`
- `LOG_PREFIX_STEAM_GROUP`, `LOG_PREFIX_L4D2_CONNECT`, `LOG_PREFIX_L4D2_RESERVE`

## Variables de tuning (flexibilidad)
- `A2S_INFO_RATE` (default `16`)
- `A2S_INFO_BURST` (default `80`)
- `A2S_PLAYERS_RATE` (default `12`)
- `A2S_PLAYERS_BURST` (default `60`)
- `A2S_RULES_RATE` (default `8`)
- `A2S_RULES_BURST` (default `40`)
- `STEAM_GROUP_RATE` (default `6`)
- `STEAM_GROUP_BURST` (default `30`)
- `L4D2_LOGIN_RATE` (default `4`)
- `L4D2_LOGIN_BURST` (default `16`)
- `ENABLE_STEAM_GROUP_FILTER` (`true|false`, default `true`)
- `STEAM_GROUP_SIGNATURES` (default `"69"`, formato `hex,hex`, por ejemplo `"69,00"`)

## Firmas que usa el módulo
El módulo inspecciona el prefijo Source `0xFFFFFFFF` y luego clasifica por byte de comando:

- `54` -> A2S_INFO (`A2S_LIMITS`)
- `55` -> A2S_PLAYERS (`A2S_PLAYERS_LIMITS`)
- `56` -> A2S_RULES (`A2S_RULES_LIMITS`)
- `69` -> `A2A_PING` legacy/obsoleto en documentación Valve
- `71` -> Login short-query L4D2 (subfiltro `connect/reserve`)
- `00` -> compatibilidad legacy observada en despliegues reales (si `ENABLE_STEAM_GROUP_FILTER=true`)

## Nota sobre Steam Group
Valve documenta `sv_steamgroup` y los filtros de matchmaking/grupo, pero no publica claramente un byte exclusivo de consulta "Steam Group" comparable a `54/55/56/57/69`.

Por eso la suite trata `STEAM_GROUP_SIGNATURES` como una lista configurable de firmas observadas en operación:

- `00` se mantiene por compatibilidad con despliegues donde esa firma aparece en el flujo de descubrimiento.
- `69` es el default porque Valve sí lo documenta como `A2A_PING`, y algunos clientes/herramientas legacy todavía lo emiten.
- Si aparecen otros bytes firmados válidos en captura, se pueden añadir sin tocar código.

## Lobby y publicación
La documentación pública de Valve/Steamworks describe el lobby y el matchmaking principalmente a nivel de API y metadata, no como un protocolo UDP público con firma equivalente a A2S:

- `SetLobbyGameServer` / `GetLobbyGameServer` exponen asociación lobby <-> servidor a nivel API.
- `sv_steamgroup`, `sv_search_key` y tags privadas se describen como metadata de matchmaking/publicación.
- el browser público sigue apoyándose en `Server Queries` y en el `Master Server Query Protocol`.

En consecuencia, el firewall no debería asumir que existe una firma pública exclusiva "de lobby" o "de steamgroup" si no fue observada en captura real.

### Detalle de firmas Steam Group
- La detección Steam Group ya no está hardcodeada a `00`.
- Ahora se controla con `STEAM_GROUP_SIGNATURES`.
- El módulo acepta lista CSV de bytes hex de 2 dígitos, por ejemplo:
  - `STEAM_GROUP_SIGNATURES="69"`
  - `STEAM_GROUP_SIGNATURES="69,00"`
- Si `ENABLE_STEAM_GROUP_FILTER=false`, no se crean reglas de match para firmas Steam Group.

## Lógica de mitigación
- A2S (`54/55/56`): cada tipo entra a su propia cadena con rate/burst dedicado.
- A2S se aplica sobre `L4D2_GAMESERVER_PORTS + L4D2_TV_PORTS`.
- Steam Group (`00` y firmas configuradas): entra a `STEAM_GROUP_LIMITS`.
- Steam Group se aplica sobre `L4D2_GAMESERVER_PORTS + L4D2_TV_PORTS`.
- Si `ENABLE_STEAM_GROUP_FILTER=false`, las firmas Steam Group dejan de clasificarse aquí y quedan gobernadas por el limitador base (`l4d2_udp_base`) en vez de ser dropeadas por una regla fija.
- Login (`71`):
  - acepta a tasa controlada paquetes que contienen `connect`
  - acepta a tasa controlada paquetes que contienen `reserve`
  - `drop` para el resto de `71` en ventana corta (1..70 bytes)
  - se aplica solo sobre `L4D2_GAMESERVER_PORTS` para evitar falsos positivos en SourceTV
- El módulo mantiene logging con prefijos específicos para facilitar diagnóstico.

## Validaciones de configuración
Antes de aplicar reglas, el módulo valida:
- `TYPECHAIN` en `0|1|2`
- formato de `L4D2_GAMESERVER_PORTS`
- todos los `*_RATE` y `*_BURST` como enteros positivos
- `ENABLE_STEAM_GROUP_FILTER` en `true|false`
- `STEAM_GROUP_SIGNATURES` con regex hex CSV (`69` o `69,00`, etc.) cuando está habilitado

## Diferencias por backend
- Ambos aplican mitigaciones A2S/Steam y patrones de login equivalentes por área.
- `iptables` usa `-m string --hex-string '|FFFFFFFF..|'` con rate-limit por `srcip,dstport`, alineado con el backend `nftables`.
- `nftables` usa payload match (`@th,64,40 0xFFFFFFFF..`) con meter/rate.

## Qué mejorar con esta información
- Mantener el bypass temprano del módulo base sólo para firmas documentadas por Valve y para firmas empíricas controladas por `STEAM_GROUP_SIGNATURES`.
- Evitar hardcodear `00` como si fuera una firma oficial de Steam Group; documentarlo como heurística operacional.
- Revisar logs `UDP_NEW_LIMIT` antes de tocar `STEAM_GROUP_RATE`, porque muchos falsos positivos ocurren en el módulo base y no en `l4d2_a2s_filters`.
- Si reaparece un problema de visibilidad, capturar `pcap` y promover nuevas firmas sólo después de verificarlas en tráfico real.
- Mantener el logging de este módulo como logging de abuso real, separado del logging de normalización/base.

## Referencias oficiales
- [Valve Developer Community: Server queries](https://developer.valvesoftware.com/wiki/Server_queries)
- [Valve Developer Community: Master Server Query Protocol](https://developer.valvesoftware.com/wiki/Master_Server_Query_Protocol)
- [Valve Developer Community: Add-on](https://developer.valvesoftware.com/wiki/Add-on)
- [Steamworks API: ISteamMatchmaking](https://partner.steamgames.com/doc/api/ISteamMatchmaking)
- [Politica interna: Source Query Bypass](../source-query-bypass-policy.md)

## Nota operativa
- Excluir `l4d2_a2s_filters` de `MODULES_ONLY` en nodos sin servicios de juego.
- Recomendación: usar puertos reales de juego en `L4D2_GAMESERVER_PORTS` y dejar `UDP_ALLOW_PORTS=""` para evitar bypass de mitigaciones.

## Ejemplos de configuración
Perfil equilibrado (recomendado):

```env
A2S_INFO_RATE=16
A2S_INFO_BURST=80
A2S_PLAYERS_RATE=12
A2S_PLAYERS_BURST=60
A2S_RULES_RATE=8
A2S_RULES_BURST=40
STEAM_GROUP_RATE=6
STEAM_GROUP_BURST=30
L4D2_LOGIN_RATE=4
L4D2_LOGIN_BURST=16
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="69"
```

Perfil más estricto:

```env
A2S_INFO_RATE=10
A2S_INFO_BURST=40
A2S_PLAYERS_RATE=8
A2S_PLAYERS_BURST=30
A2S_RULES_RATE=5
A2S_RULES_BURST=20
STEAM_GROUP_RATE=3
STEAM_GROUP_BURST=12
L4D2_LOGIN_RATE=2
L4D2_LOGIN_BURST=6
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="69"
```

Perfil permisivo (tráfico alto legítimo):

```env
A2S_INFO_RATE=30
A2S_INFO_BURST=160
A2S_PLAYERS_RATE=24
A2S_PLAYERS_BURST=120
A2S_RULES_RATE=14
A2S_RULES_BURST=70
STEAM_GROUP_RATE=12
STEAM_GROUP_BURST=60
L4D2_LOGIN_RATE=8
L4D2_LOGIN_BURST=32
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="69,00"
```
