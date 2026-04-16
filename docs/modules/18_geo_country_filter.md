# Módulo específico nft — geo_country_filter

## Objetivo
Aplicar política geográfica IPv4 sobre los puertos UDP de juego usando allowlist o denylist por país, con excepciones manuales por IP/CIDR.

## Backend
- nftables: `modules/nf/nf_15_geo_country_filter.sh` (`ID=nf_geo_country_filter`)

## Alcance
- Solo afecta tráfico IPv4 hacia `L4D2_GAMESERVER_UDP_PORTS` y `L4D2_SOURCETV_UDP_PORTS`.
- No toca SSH, HTTP/HTTPS ni otros puertos del host.
- No reemplaza rate limits ni filtros A2S; corre antes y reduce superficie.

## Precedencia importante
- `WHITELISTED_IPS` y `WHITELISTED_DOMAINS` mantienen bypass completo porque el módulo `whitelist` acepta antes en `core_allow`.
- Luego se evalúa este módulo geográfico.
- Dentro de este módulo: deny manual > allow manual > política por país.

## Variables
- `GEO_POLICY_MODE`: `off`, `allowlist`, `denylist`
- `GEO_POLICY_ALLOWED_COUNTRIES`: CSV ISO 3166-1 alpha-2, por ejemplo `CL,AR,PE`
- `GEO_POLICY_DENIED_COUNTRIES`: CSV ISO 3166-1 alpha-2, por ejemplo `RU,CN`
- `GEO_POLICY_DATA_DIR`: directorio con ficheros `CC.ipv4.txt`
- `GEO_POLICY_MANUAL_ALLOW_FILE`: archivo plano con IPv4/CIDR permitidos dentro de la política geo
- `GEO_POLICY_MANUAL_DENY_FILE`: archivo plano con IPv4/CIDR bloqueados dentro de la política geo

## Diseño operativo
- `allowlist`: solo continúan IPs que estén en países permitidos o en allow manual.
- `denylist`: se bloquean países denegados y CIDRs/IPs del deny manual; el resto continúa.
- `off`: el módulo no hace nada, aunque esté incluido en `MODULES_ONLY`.

## Verificar una IP/CIDR
Puedes verificar cómo quedaría clasificada una IP o red antes de reaplicar reglas:

```bash
make geoip-check-ip IP=179.6.17.240
make geoip-check-ip IP=179.6.17.240/28
```

El checker replica la precedencia del módulo:

- `WHITELISTED_IPS` / `WHITELISTED_DOMAINS` como bypass previo.
- `GEO_POLICY_MODE=off` permite porque el filtro geográfico no aplica reglas.
- En modo activo: deny manual > allow manual > política por país.

Por defecto no resuelve `WHITELISTED_DOMAINS` para evitar depender de DNS durante la verificación. Si quieres incluir dominios confiables resueltos en el resultado:

```bash
make geoip-check-ip IP=203.0.113.10 RESOLVE_DOMAINS=1
```

## Datos MaxMind
La recomendación es usar GeoLite2 Country CSV como fuente offline y convertirla a archivos por país:

```bash
./scripts/geoip/update_geo_country_sets.sh --env-file ./.env --csv-zip /ruta/GeoLite2-Country-CSV.zip
```

Si ya estás trabajando desde la raíz del repo, también puedes usar el `Makefile`:

```bash
make geoip-update
```

También puedes usar un directorio ya extraído:

```bash
./scripts/geoip/update_geo_country_sets.sh --env-file ./.env --csv-dir /ruta/GeoLite2-Country-CSV_YYYYMMDD
```

## Automatización semanal
Si prefieres automatizar la descarga, regeneración y recarga de reglas, puedes usar el `Makefile` desde `crontab`:

```bash
15 4 * * 1 cd /home/lechuga/L4D2-Iptable-Suite && make geoip-refresh-safe >> /home/lechuga/L4D2-Iptable-Suite/geoip-updater/geoip-updater.log 2>&1
```

Ese target ejecuta el updater y luego reaplica `nftables` para cargar los cambios en el ruleset activo.

## Archivos recomendados
- `geoip/generated/countries/CL.ipv4.txt`
- `geoip/generated/countries/AR.ipv4.txt`
- `geoip/manual/allow_ipv4.txt`
- `geoip/manual/deny_ipv4.txt`

## Recomendación práctica
- Para este nodo, empieza con `GEO_POLICY_MODE=off` y deja el módulo incluido.
- Cuando tengas los archivos generados, cambia a `allowlist` con los países realmente necesarios.
- Si quitas `US`, solo debes editar `GEO_POLICY_ALLOWED_COUNTRIES` y regenerar los archivos.

## Limitaciones
- Actualmente el módulo filtra solo IPv4 para mantener bajo el peso operativo.
- Si el ataque viene desde un país permitido, seguirá pasando a los rate limits y filtros existentes.
