# Módulo unificado — http_https_protect (ip/nf)

## Objetivo
Limitar abuso de conexiones nuevas HTTP/HTTPS.

## Backends
- iptables: `modules/ip/ip_45_http_https_protect.sh` (`ID=ip_http_https_protect`)
- nftables: `modules/nf/nf_45_http_https_protect.sh` (`ID=nf_http_https_protect`)

## Variables
- `ENABLE_HTTP_PROTECT`
- `HTTP_HTTPS_PORTS`, `HTTP_HTTPS_DOCKER`
- `HTTP_HTTPS_RATE`, `HTTP_HTTPS_BURST`
- `LOG_PREFIX_HTTP_HTTPS_ABUSE`

## Diferencias
- `nf` normaliza `sec/min` a formato nativo (`second/minute`) cuando corresponde.
