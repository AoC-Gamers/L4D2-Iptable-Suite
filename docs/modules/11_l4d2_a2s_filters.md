# `l4d2_a2s_filters` — consultas UDP Source

El módulo aplica límites por clase a A2S INFO/PLAYERS/RULES y a clasificadores de login/Steam-group en los puertos de juego. Seleccionarlo requiere `l4d2_udp_base` y `l4d2_packet_validation`. Los defaults declarados por ambos motores incluyen 16/80, 12/60, 8/40, Steam Group 6/30 y login 4/16; `0` desactiva el limitador de esa clase. nftables tiene timeouts de medidor validados por el núcleo.

Las firmas internas 54/55/56 identifican los clasificadores A2S. `71` solo activa el clasificador corto connect/reserve de GameServer; SourceTV no hereda esa excepción. El filtro de firmas Steam Group es configurable y activo por defecto, con `STEAM_GROUP_SIGNATURES=69`; el valor 69 no se acredita como firma oficial exclusiva de Steam Group. Véase la [política de firmas](../source-query-bypass-policy.md).

La evidencia observada cubre paquetes sintéticos de consulta/login/TV, no una sesión L4D2 real ni descubrimiento Steam completo. No generalice las tasas a cualquier servidor sin capturas y validación de clientes propios: [resultados](../security/results.md).
