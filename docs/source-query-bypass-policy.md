# Política de clasificación y bypass para consultas Source

Esta página describe únicamente el tratamiento que implementa el compilador actual. No establece una especificación oficial de Valve para cada byte ni certifica la compatibilidad con todos los clientes.

## Flujo

Con `ENABLE_UDP_NEW_FFFFFFFF_BYPASS=true` (default), el clasificador base UDP puede dejar pasar el límite NEW genérico solo si hay un clasificador posterior habilitado para ese paquete:

- `0xFFFFFFFF54`, `55` y `56`: clasificadores A2S INFO, PLAYERS y RULES cuando `l4d2_a2s_filters` está activo.
- `0xFFFFFFFF71`: subclasificador corto `connect`/`reserve`, únicamente en puertos GameServer.
- Bytes listados en `STEAM_GROUP_SIGNATURES`: clasificador Steam Group de la suite cuando `ENABLE_STEAM_GROUP_FILTER=true`.

El bypass significa “llega al control específico siguiente”; no significa `ACCEPT` incondicional ni omitir todos los límites. Lo que no coincide continúa bajo el limitador NEW genérico. SourceTV no recibe el subfiltro 71 de GameServer y conserva ese tráfico bajo el límite genérico. El grupo UDP de juego requiere los módulos `l4d2_udp_base`, `l4d2_packet_validation` y `l4d2_a2s_filters` juntos.

## Valores y compatibilidad

El default actual es `ENABLE_STEAM_GROUP_FILTER=true` y `STEAM_GROUP_SIGNATURES=69`. El 69 es compatibilidad del proyecto; no debe presentarse como firma oficial exclusiva de Steam Group. Otros bytes pueden configurarse explícitamente, por ejemplo `STEAM_GROUP_SIGNATURES="69,00"`, pero la modificación se aplica en los puertos de juego configurados y debe seguirse con prueba de tráfico propia.

Los documentos públicos de Valve describen protocolos de consulta y APIs relacionadas, pero no fundamentan una firma exclusiva de Steam Group a nivel de byte ni validan la interpretación interna de cada payload. En particular, no se deduce de esas fuentes que `00` sea un formato universal. Véanse [Server queries](https://developer.valvesoftware.com/wiki/Server_queries), [Master Server Query Protocol](https://developer.valvesoftware.com/wiki/Master_Server_Query_Protocol) e [ISteamMatchmaking](https://partner.steamgames.com/doc/api/ISteamMatchmaking).

## Ajustes y límites

1. Observe `UDP_NEW_LIMIT` y capture payloads del servidor afectado antes de variar firmas o tasas.
2. Añada un byte solo si las capturas repetidas justifican que esos paquetes deben alcanzar el clasificador específico. Compruebe después tasa, contadores y comportamiento de A2S/login/SourceTV.
3. Quite valores experimentales si no se necesitan. No relaje globalmente el límite NEW para corregir un solo tipo de consulta.

La evidencia publicada usa paquetes sintéticos A2S/login/TV y no demuestra una sesión real de jugador, descubrimiento completo de Steam Group, ni una firma de cliente oficial. Consulte los límites de [resultados](security/results.md) y el comportamiento de [`l4d2_udp_base`](modules/09_l4d2_udp_base.md) / [`l4d2_a2s_filters`](modules/11_l4d2_a2s_filters.md).
