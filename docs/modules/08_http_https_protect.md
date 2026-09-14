# Módulo unificado — http_https_protect (ip/nf)

## Objetivo
Limitar abuso de conexiones nuevas HTTP/HTTPS sin compartir el presupuesto de
tráfico entre clientes independientes.

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
- Ambos backends aplican `HTTP_HTTPS_RATE` y `HTTP_HTTPS_BURST` por IP de origen
  y puerto de destino. En nftables esto se implementa con meters sobre
  `ip saddr . tcp dport`; no debe reemplazarse por un `limit` global, porque el
  tráfico agregado de Internet podría agotar el presupuesto y bloquear clientes
  legítimos.
- En la cadena nftables `forward_web`, el selector y el meter usan
  `ct original proto-dst`. El hook forward se ejecuta después de DNAT y el puerto
  efectivo puede haber cambiado (por ejemplo, `443` público a `8443` en el
  contenedor); filtrar allí por `tcp dport` dejaría fuera los puertos públicos
  declarados en `HTTP_HTTPS_PORTS`.
