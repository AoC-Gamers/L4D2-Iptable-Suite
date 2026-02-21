# Módulo unificado — l4d2_udp_base (ip/nf)

## Objetivo
Aplicar base de control UDP para tráfico de juego (NEW/ESTABLISHED) e ICMP.

## Backends
- iptables: `modules/ip/ip_50_l4d2_udp_base.sh` (`ID=ip_l4d2_udp_base`)
- nftables: `modules/nf/nf_50_l4d2_udp_base.sh` (`ID=nf_l4d2_udp_base`)

## Variables
- `L4D2_GAMESERVER_PORTS`, `L4D2_TV_PORTS`, `L4D2_CMD_LIMIT`
- `LOG_PREFIX_UDP_NEW_LIMIT`, `LOG_PREFIX_UDP_EST_LIMIT`, `LOG_PREFIX_ICMP_FLOOD`

## Nota operativa
Desactivar en nodos sin juegos excluyendo `l4d2_udp_base` de `MODULES_ONLY`.
