# Módulo unificado — whitelist (ip/nf)

## Objetivo
Permitir tráfico completo desde IPs/dominios de confianza.

## Backends
- iptables: `modules/ip/ip_10_whitelist.sh` (`ID=ip_whitelist`)
- nftables: `modules/nf/nf_10_whitelist.sh` (`ID=nf_whitelist`)

## Variables
- `TYPECHAIN`
- `WHITELISTED_IPS` (separado por espacios)
- `WHITELISTED_DOMAINS` (resolución IPv4 al aplicar)

## Diferencias por backend
- Ambos resuelven dominios y deduplican IPs.
- En `nft`, las reglas se aplican a cadenas objetivo según `TYPECHAIN`.
