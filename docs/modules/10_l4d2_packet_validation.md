# `l4d2_packet_validation` — validación UDP

Seleccionado junto con `l4d2_udp_base` y `l4d2_a2s_filters`, valida longitudes inválidas y, de forma opt-in, patrones malformados en puertos GameServer/SourceTV. `ENABLE_MALFORMED_FILTER` y `ENABLE_PACKET_NORMALIZATION_LOGS` son `false` por defecto. El logging diagnóstico no controla si las reglas de bloqueo activadas están presentes.

No trate longitudes observadas en una captura sintética como prueba de que todo cliente legítimo las evita. Habilite el filtro malformado tras contrastar capturas representativas de su tráfico. Consulte límites de evidencia en [resultados](../security/results.md).
