# Módulo unificado — allowlist_ports (ip/nf)

## Objetivo
Abrir puertos TCP/UDP explícitos como excepción operacional.

## Backends
- iptables: `modules/ip/ip_20_allowlist_ports.sh` (`ID=ip_allowlist_ports`)
- nftables: `modules/nf/nf_20_allowlist_ports.sh` (`ID=nf_allowlist_ports`)

## Variables
- `TYPECHAIN`
- `UDP_ALLOW_PORTS`
- `TCP_ALLOW_PORTS`

## Nota
Usar para puertos puntuales de infraestructura; evitar mezclar con lógica L4D2 de protección.
