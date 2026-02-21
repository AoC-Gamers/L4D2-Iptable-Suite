# Módulo unificado — tcp_ssh (ip/nf)

## Objetivo
Gestionar acceso SSH base (sin lógica específica de L4D2).

## Backends
- iptables: `modules/ip/ip_40_tcp_ssh.sh` (`ID=ip_tcp_ssh`)
- nftables: `modules/nf/nf_40_tcp_ssh.sh` (`ID=nf_tcp_ssh`)

## Variables
- SSH: `SSH_PORT`, `SSH_DOCKER`
- Protección: `SSH_RATE`, `SSH_BURST`, `LOG_PREFIX_SSH_ABUSE`

## Nota operativa
- La protección TCP de dominio L4D2 ahora vive en el módulo dedicado `l4d2_tcp_protect`.
- Este módulo `tcp_ssh` expone SSH y aplica limitación anti-abuso de nuevas conexiones.

## Diferencias por backend
- La cobertura real depende de `TYPECHAIN` (`input`, `forward` o ambos).
