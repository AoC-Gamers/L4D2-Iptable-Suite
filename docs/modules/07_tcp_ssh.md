# Módulo unificado — tcp_ssh (ip/nf)

## Objetivo
Gestionar acceso SSH y protección TCP de dominio L4D2.

## Backends
- iptables: `modules/ip/ip_40_tcp_ssh.sh` (`ID=ip_tcp_ssh`)
- nftables: `modules/nf/nf_40_tcp_ssh.sh` (`ID=nf_tcp_ssh`)

## Variables
- SSH: `SSH_PORT`, `SSH_REQUIRE_WHITELIST`, `WHITELISTED_IPS`, `WHITELISTED_DOMAINS`
- L4D2 TCP: `ENABLE_L4D2_TCP_PROTECT`, `L4D2_GAMESERVER_PORTS`, `L4D2_TCP_PROTECTION`
- logging: `LOG_PREFIX_TCP_RCON_BLOCK`

## Diferencias
- `SSH_REQUIRE_WHITELIST=true` evita apertura pública SSH en este módulo.
- La cobertura real depende de `TYPECHAIN` (`input`, `forward` o ambos).
