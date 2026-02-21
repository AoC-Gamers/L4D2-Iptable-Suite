# Módulo unificado — docker_dns_egress (ip/nf)

## Objetivo
Permitir salida DNS (`UDP/TCP 53`) desde subredes de contenedores Docker para evitar bloqueos en resolución (por ejemplo, ACME/Cloudflare en Traefik).

## Backends
- iptables: `modules/ip/ip_22_docker_dns_egress.sh` (`ID=ip_docker_dns_egress`)
- nftables: `modules/nf/nf_22_docker_dns_egress.sh` (`ID=nf_docker_dns_egress`)

## Alias de activación
- `docker_dns_egress`

## Variables
- `TYPECHAIN`
- `DOCKER_DNS_EGRESS_SUBNETS` (CIDRs separados por coma)

## Defaults
- `DOCKER_DNS_EGRESS_SUBNETS="172.16.0.0/12"`

## Alcance de reglas
- `nftables`: agrega reglas en cadena `forward`.
- `iptables`: agrega reglas en cadena `DOCKER-USER` (cuando `TYPECHAIN` incluye flujo Docker).

## Nota operativa
Este módulo abre únicamente DNS saliente para subredes Docker definidas; no expone servicios DNS del host a clientes externos.
