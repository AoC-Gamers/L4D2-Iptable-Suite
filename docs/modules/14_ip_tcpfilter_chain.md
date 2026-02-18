# Módulo específico ip — tcpfilter_chain

## Módulo
- `modules/ip/ip_35_tcpfilter_chain.sh` (`ID=ip_tcpfilter_chain`)

## Objetivo
Crear/llenar cadena `TCPfilter` para control de nuevos TCP en backend `iptables`.

## Nota
No tiene equivalente 1:1 en `nft`; la lógica se expresa dentro de reglas del módulo TCP/SSH.
