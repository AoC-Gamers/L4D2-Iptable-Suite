# Módulo específico ip — ip_l4d2_tcpfilter_chain

## Módulo
- `modules/ip/ip_35_tcpfilter_chain.sh` (`ID=ip_l4d2_tcpfilter_chain`)

## Objetivo
Crear/llenar cadena `TCPfilter` para control de nuevos TCP en backend `iptables`.

## Nota operativa
En `nft` existe `nf_l4d2_tcpfilter_chain` como compatibilidad (no-op); la protección TCP L4D2 efectiva se implementa en `nf_l4d2_tcp_protect`.
