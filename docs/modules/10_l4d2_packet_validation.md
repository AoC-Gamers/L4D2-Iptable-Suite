# Módulo unificado — l4d2_packet_validation (ip/nf)

## Objetivo
Bloquear tamaños UDP inválidos/malformados típicos de abuso sobre puertos de juego.

## Backends
- iptables: `modules/ip/ip_60_l4d2_packet_validation.sh` (`ID=ip_l4d2_packet_validation`)
- nftables: `modules/nf/nf_60_l4d2_packet_validation.sh` (`ID=nf_l4d2_packet_validation`)

## Variables
- `L4D2_GAMESERVER_UDP_PORTS`, `L4D2_SOURCETV_UDP_PORTS`
- `LOG_PREFIX_INVALID_SIZE`, `LOG_PREFIX_MALFORMED`
- `ENABLE_PACKET_NORMALIZATION_LOGS` (`false` recomendado en producción)
- `ENABLE_MALFORMED_FILTER` (`false` recomendado si discovery/Steam Group es sensible)

## Diferencias por backend
- Ambos aplican validación de tamaños inválidos/malformados sobre puertos de juego.

## Recomendación práctica
- Mantener `ENABLE_MALFORMED_FILTER=false` cuando el objetivo principal sea compatibilidad con `serverbrowser` y `steamgroup`.
- Reservar `ENABLE_MALFORMED_FILTER=true` para entornos donde ya exista captura/pcap que confirme que las longitudes `30-32`, `46` y `60` son realmente basura en tu tráfico.

## Politica de logging
Este módulo hace saneamiento/normalización de tráfico, no clasificación principal de abuso.

Por eso:

- `ENABLE_PACKET_NORMALIZATION_LOGS=false` es el default recomendado en producción.
- `ENABLE_PACKET_NORMALIZATION_LOGS=true` se reserva para diagnóstico o captura forense.
- Los drops siguen ocurriendo aunque el logging esté desactivado.

## Nota operativa
- Mantener fuera de `MODULES_ONLY` en nodos sin tráfico L4D2 para minimizar reglas innecesarias.
