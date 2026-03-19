# Módulos OpenVPN (ip/nf)

## Objetivo
Separar explícitamente los dos modos de operación de OpenVPN:

- **openvpn_server**: clientes remotos acceden al host/LAN.
- **openvpn_sitetosite**: enrutamiento entre subredes de dos sitios.

## Backends

### openvpn_server
- iptables: `modules/ip/ip_30_openvpn_server.sh` (`ID=ip_openvpn_server`)
- nftables: `modules/nf/nf_30_openvpn_server.sh` (`ID=nf_openvpn_server`)

### openvpn_sitetosite
- iptables: `modules/ip/ip_31_openvpn_sitetosite.sh` (`ID=ip_openvpn_sitetosite`)
- nftables: `modules/nf/nf_31_openvpn_sitetosite.sh` (`ID=nf_openvpn_sitetosite`)

## Variables

### openvpn_server
- `OVPNSRV_PROTO`, `OVPNSRV_PORT`
- `OVPNSRV_SUBNET`, `OVPNSRV_INTERFACE`
- `OVPNSRV_LAN_SUBNET`, `OVPNSRV_ENABLE_NAT`
- extras en `ip`: `OVPNSRV_DOCKER_INTERFACE`, `OVPNSRV_LAN_INTERFACE`, `OVPNSRV_LOG_*`, `OVPNSRV_ROUTER_*`

### openvpn_sitetosite
- `OVPNS2S_INTERFACE`
- `OVPNS2S_LOCAL_SUBNETS`
- `OVPNS2S_REMOTE_SUBNETS`
- extras en `ip`: `OVPNS2S_ENABLE_NAT`, `OVPNS2S_LOCAL_INTERFACE`, `OVPNS2S_LOG_*`, `OVPNS2S_ROUTER_ALIAS`, `OVPNS2S_ROUTER_REAL_IP`, `OVPNS2S_ROUTER_ALIAS_IP`, `OVPNS2S_ROUTER_ALIAS_SNAT`
- extras en `nf`: `OVPNS2S_ENABLE_NAT`, `OVPNS2S_LOCAL_INTERFACE`, `OVPNS2S_ROUTER_ALIAS`, `OVPNS2S_ROUTER_REAL_IP`, `OVPNS2S_ROUTER_ALIAS_IP`, `OVPNS2S_ROUTER_ALIAS_SNAT`

## Activación
- Se activan por inclusión en `MODULES_ONLY` usando tokens:
	- `openvpn_server`
	- `openvpn_sitetosite`

## Incompatibilidad
- `openvpn_server` y `openvpn_sitetosite` son **mutuamente excluyentes**.
- El loader aborta si detecta ambos en `MODULES_ONLY` / `--only`.

## Diferencias por backend
- `ip` incluye más opciones avanzadas (NAT/log/DNAT).
- `nf` mantiene implementación directa para input/forward y soporta NAT S2S en tabla dedicada `ip vpn_s2s_nat` para alias de router y MASQUERADE opcional.
