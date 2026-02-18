# Módulo específico ip — tcpfilter_chain

## Módulo
- `modules/ip/ip_35_tcpfilter_chain.sh` (`ID=ip_tcpfilter_chain`)

## Objetivo
Crear/llenar cadena `TCPfilter` para control de nuevos TCP en backend `iptables`.

## Nota operativa
No tiene equivalente 1:1 en `nft`; la protección TCP L4D2 en `nft` se implementa en `nf_l4d2_tcp_protect`.
