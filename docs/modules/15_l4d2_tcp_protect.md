# Módulo unificado — l4d2_tcp_protect (ip/nf)

## Objetivo
Aplicar protección TCP específica para puertos de juego/RCON de L4D2.

## Backends
- iptables: `modules/ip/ip_42_l4d2_tcp_protect.sh` (`ID=ip_l4d2_tcp_protect`)
- nftables: `modules/nf/nf_42_l4d2_tcp_protect.sh` (`ID=nf_l4d2_tcp_protect`)

## Variables
- `L4D2_GAMESERVER_PORTS`
- `LOG_PREFIX_TCP_RCON_BLOCK`
- `TYPECHAIN`

## Diferencias por backend
- `ip`: limita conexiones TCP `NEW` por `INPUT` y opcionalmente `DOCKER-USER` según `TYPECHAIN`.
- `nf`: aplica rate-limit por origen/puerto en cadenas objetivo nativas (`input`/`forward`) según `TYPECHAIN`.

## Nota operativa
- Se activa al incluir `l4d2_tcp_protect` en `MODULES_ONLY`.
- La exposición SSH se gestiona en `tcp_ssh`, separado de este módulo.
- Usa siempre `L4D2_GAMESERVER_PORTS` como referencia TCP y deja pasar tráfico normal; sólo registra y descarta exceso de conexiones nuevas.
