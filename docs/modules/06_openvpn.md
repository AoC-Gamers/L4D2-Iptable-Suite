# Módulo unificado — openvpn (ip/nf)

## Objetivo
Permitir entrada de OpenVPN y conectividad VPN↔LAN según configuración.

## Backends
- iptables: `modules/ip/ip_30_openvpn.sh` (`ID=ip_openvpn`)
- nftables: `modules/nf/nf_30_openvpn.sh` (`ID=nf_openvpn`)

## Variables
- `TYPECHAIN`, `VPN_PROTO`, `VPN_PORT`
- `VPN_SUBNET`, `VPN_INTERFACE`, `VPN_LAN_SUBNET`
- extras en `ip`: `VPN_DOCKER_INTERFACE`, `VPN_ENABLE_NAT`, `VPN_LAN_INTERFACE`, `VPN_LOG_*`, `VPN_ROUTER_*`

## Activación
- El módulo se activa por inclusión en `MODULES_ONLY`/`MODULES_EXCLUDE`.
- `VPN_ENABLED` queda deprecada y ya no se usa.

## Diferencias por backend
- `ip` incluye más opciones avanzadas (NAT/log/DNAT).
- `nf` mantiene implementación más directa para input/forward.
