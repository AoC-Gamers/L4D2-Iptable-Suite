# Módulo unificado — http_https_protect (ip/nf)

## Objetivo
Limitar abuso de conexiones nuevas HTTP/HTTPS.

## Backends
- iptables: `modules/ip/ip_45_http_https_protect.sh` (`ID=ip_http_https_protect`)
- nftables: `modules/nf/nf_45_http_https_protect.sh` (`ID=nf_http_https_protect`)

## Variables
- `HTTP_HTTPS_PORTS`
- `HTTP_HTTPS_RATE`, `HTTP_HTTPS_BURST`
- `LOG_PREFIX_HTTP_HTTPS_ABUSE`

## Nota operativa
- La activación depende de incluir `http_https_protect` en `MODULES_ONLY`; no se usa flag `ENABLE_*`.

## Diferencias por backend
- `nf` normaliza `sec/min` a formato nativo (`second/minute`) cuando corresponde.
