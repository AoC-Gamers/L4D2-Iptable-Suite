# Módulo unificado — chain_setup (ip/nf)

## Objetivo
Inicializar cadenas/tablas base y políticas por defecto antes de módulos funcionales.

## Backends
- iptables: `modules/ip_chain_setup.sh` (`ID=ip_chain_setup`)
- nftables: `modules/nf_chain_setup.sh` (`ID=nf_chain_setup`)

## Variables
- `TYPECHAIN` (`0=input`, `1=docker/forward`, `2=ambos`)
- `DOCKER_INPUT_COMPAT`, `DOCKER_CHAIN_AUTORECOVER` (principalmente `ip`)

## Alcance
- `chain_setup` no gestiona políticas de dominio L4D2.
- La protección TCP L4D2 se maneja en `l4d2_tcp_protect`; `l4d2_tcpfilter_chain` es cadena real en `ip` y compatibilidad no-op en `nf`.

## Diferencias por backend
- `ip`: limpieza amplia de tablas/cadenas y compatibilidad Docker opcional.
- `nf`: crea tabla `inet l4d2_filter` y cadenas hook `input/forward/output`.
