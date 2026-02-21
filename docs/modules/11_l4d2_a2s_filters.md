# Módulo unificado — l4d2_a2s_filters (ip/nf)

## Objetivo
Mitigar flood de consultas A2S/Steam Group y patrones de login (`connect/reserve`).

## Backends
- iptables: `modules/ip/ip_70_l4d2_a2s_filters.sh` (`ID=ip_l4d2_a2s_filters`)
- nftables: `modules/nf/nf_70_l4d2_a2s_filters.sh` (`ID=nf_l4d2_a2s_filters`)

## Variables
- `L4D2_GAMESERVER_PORTS`
- `LOG_PREFIX_A2S_INFO`, `LOG_PREFIX_A2S_PLAYERS`, `LOG_PREFIX_A2S_RULES`
- `LOG_PREFIX_STEAM_GROUP`, `LOG_PREFIX_L4D2_CONNECT`, `LOG_PREFIX_L4D2_RESERVE`

## Diferencias por backend
- Ambos aplican mitigaciones A2S/Steam y patrones de login equivalentes por área.

## Nota operativa
- Excluir `l4d2_a2s_filters` de `MODULES_ONLY` en nodos sin servicios de juego.
