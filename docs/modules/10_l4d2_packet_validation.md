# Módulo unificado — l4d2_packet_validation (ip/nf)

## Objetivo
Bloquear tamaños UDP inválidos/malformados típicos de abuso sobre puertos de juego.

## Backends
- iptables: `modules/ip/ip_60_l4d2_packet_validation.sh` (`ID=ip_l4d2_packet_validation`)
- nftables: `modules/nf/nf_60_l4d2_packet_validation.sh` (`ID=nf_l4d2_packet_validation`)

## Variables
- `L4D2_GAMESERVER_PORTS`, `L4D2_TV_PORTS`
- `LOG_PREFIX_INVALID_SIZE`, `LOG_PREFIX_MALFORMED`
- `ENABLE_PACKET_NORMALIZATION_LOGS` (`false` recomendado en producción)

## Diferencias por backend
- Ambos aplican validación de tamaños inválidos/malformados sobre puertos de juego.

## Politica de logging
Este módulo hace saneamiento/normalización de tráfico, no clasificación principal de abuso.

Por eso:

- `ENABLE_PACKET_NORMALIZATION_LOGS=false` es el default recomendado en producción.
- `ENABLE_PACKET_NORMALIZATION_LOGS=true` se reserva para diagnóstico o captura forense.
- Los drops siguen ocurriendo aunque el logging esté desactivado.

## Nota operativa
- Mantener fuera de `MODULES_ONLY` en nodos sin tráfico L4D2 para minimizar reglas innecesarias.
