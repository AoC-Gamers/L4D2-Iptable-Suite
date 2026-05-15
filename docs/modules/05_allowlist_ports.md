# Módulo unificado — bypass_ports (ip/nf)

## Objetivo
Abrir puertos TCP/UDP explícitos como excepción operacional.

## Backends
- iptables: `modules/ip/ip_20_allowlist_ports.sh` (`ID=ip_allowlist_ports`)
- nftables: `modules/nf/nf_20_allowlist_ports.sh` (`ID=nf_allowlist_ports`)

## Variables
- `TYPECHAIN`
- `BYPASS_UDP_PORTS`
- `BYPASS_TCP_PORTS`

## Nota operativa
Usar para puertos puntuales de infraestructura; evitar mezclar con lógica L4D2 de protección.
