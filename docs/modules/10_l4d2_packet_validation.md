# Módulo unificado — l4d2_packet_validation (ip/nf)

## Objetivo
Bloquear tamaños UDP inválidos/malformados típicos de abuso sobre puertos de juego.

## Backends
- iptables: `modules/ip/ip_60_l4d2_packet_validation.sh` (`ID=ip_l4d2_packet_validation`)
- nftables: `modules/nf/nf_60_l4d2_packet_validation.sh` (`ID=nf_l4d2_packet_validation`)

## Variables
- `ENABLE_L4D2_PACKET_VALIDATION`
- `L4D2_GAMESERVER_PORTS`, `L4D2_TV_PORTS`
- `LOG_PREFIX_INVALID_SIZE`, `LOG_PREFIX_MALFORMED`

## Diferencias por backend
- Ambos aplican validación de tamaños inválidos/malformados sobre puertos de juego.

## Nota operativa
- Mantener desactivado en nodos sin tráfico L4D2 para minimizar reglas innecesarias.
