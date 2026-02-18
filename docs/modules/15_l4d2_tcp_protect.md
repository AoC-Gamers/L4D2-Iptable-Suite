# Módulo unificado — l4d2_tcp_protect (ip/nf)

## Objetivo
Aplicar protección TCP específica para puertos de juego/RCON de L4D2.

## Backends
- iptables: `modules/ip/ip_42_l4d2_tcp_protect.sh` (`ID=ip_l4d2_tcp_protect`)
- nftables: `modules/nf/nf_42_l4d2_tcp_protect.sh` (`ID=nf_l4d2_tcp_protect`)

## Variables
- `ENABLE_L4D2_TCP_PROTECT`
- `L4D2_GAMESERVER_PORTS`
- `L4D2_TCP_PROTECTION` (opcional; si está vacío usa `L4D2_GAMESERVER_PORTS`)
- `LOG_PREFIX_TCP_RCON_BLOCK`
- `TYPECHAIN`

## Diferencias por backend
- `ip`: bloquea por `INPUT` y opcionalmente `DOCKER-USER` según `TYPECHAIN`.
- `nf`: aplica reglas en cadenas objetivo nativas (`input`/`forward`) según `TYPECHAIN`.

## Nota operativa
- Si `ENABLE_L4D2_TCP_PROTECT=false`, no se aplican bloqueos TCP de juego.
- La exposición SSH se gestiona en `tcp_ssh`, separado de este módulo.
