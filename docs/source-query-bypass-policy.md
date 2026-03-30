# Politica de Bypass de Firmas Source

## Objetivo
Definir que firmas UDP con prefijo `0xFFFFFFFF` pueden recibir bypass temprano en el firewall y bajo que criterio deben mantenerse, agregarse o retirarse.

## Principios
- Solo se hardcodean por defecto firmas documentadas publicamente por Valve o necesarias para el flujo base de publicacion/consulta Source.
- Las firmas no documentadas publicamente se tratan como empiricas y deben entrar por configuracion, no por hardcode.
- Una firma empirica no pasa a default global sin evidencia repetible en capturas o incidentes reales.

## Firmas documentadas
- `54` -> `A2S_INFO`
- `55` -> `A2S_PLAYER`
- `56` -> `A2S_RULES`
- `57` -> `A2S_SERVERQUERY_GETCHALLENGE` legacy
- `69` -> `A2A_PING` legacy
- `71` -> flujo de heartbeat/login corto asociado a publicacion y conexion Source

Estas firmas pueden recibir bypass temprano en `l4d2_udp_base` solo cuando existe un clasificador downstream activo que las procese; de lo contrario deben permanecer bajo el limitador generico `ct state new` para no caer por el policy final.

## Firmas empiricas
- `00` no se considera una firma oficial de Steam Group documentada por Valve.
- `00` puede usarse cuando aparezca en capturas reales relacionadas con visibilidad, browser o matchmaking privado.
- Cualquier otro byte adicional debe incorporarse via `STEAM_GROUP_SIGNATURES`.

## Politica de defaults
- `STEAM_GROUP_SIGNATURES` debe privilegiar firmas documentadas. Default recomendado: `69`.
- `00` queda como compatibilidad opt-in. Si un nodo lo necesita, usar `STEAM_GROUP_SIGNATURES="69,00"`.
- Si no hay evidencia de que `00` participe en el problema de visibilidad, no debe habilitarse por defecto.

## Politica operativa
- Revisar primero `UDP_NEW_LIMIT` en logs antes de aumentar `STEAM_GROUP_RATE`.
- Si hay nueva firma candidata, capturar `pcap`, verificar payload y documentar fecha, contexto y razon de inclusion.
- Si una firma empirica deja de ser necesaria, retirarla del perfil del nodo antes de convertirla en default del proyecto.

## Fuentes oficiales
- [Valve Developer Community: Server queries](https://developer.valvesoftware.com/wiki/Server_queries)
- [Valve Developer Community: Master Server Query Protocol](https://developer.valvesoftware.com/wiki/Master_Server_Query_Protocol)
- [Valve Developer Community: Add-on](https://developer.valvesoftware.com/wiki/Add-on)
- [Steamworks API: ISteamMatchmaking](https://partner.steamgames.com/doc/api/ISteamMatchmaking)
