# Módulo unificado — l4d2_packet_validation (ip/nf)

## Objetivo
Bloquear tamaños UDP inválidos/malformados típicos de abuso sobre puertos de juego.

## Backends
- iptables: `modules/ip/ip_60_l4d2_packet_validation.sh` (`ID=ip_l4d2_packet_validation`)
- nftables: `modules/nf/nf_60_l4d2_packet_validation.sh` (`ID=nf_l4d2_packet_validation`)

## Variables
- `L4D2_GAMESERVER_PORTS`, `L4D2_TV_PORTS`
- `LOG_PREFIX_INVALID_SIZE`, `LOG_PREFIX_MALFORMED`
- `ENABLE_MALFORMED_FILTER` (`true|false`, default `false` en `nft`)

## Diferencias por backend
- Ambos aplican validación de tamaños inválidos/malformados sobre puertos de juego.
- En `nft`, `ENABLE_MALFORMED_FILTER=false` deja activos solo cortes por tamaño extremo (`0-28`, `2521+`) para reducir falsos positivos.

## Nota operativa
- Mantener fuera de `MODULES_ONLY` en nodos sin tráfico L4D2 para minimizar reglas innecesarias.
