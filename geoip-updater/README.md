# GeoIP Updater

Subdirectorio para descargar semanalmente GeoLite2 Country CSV de MaxMind y regenerar los prefijos IPv4 usados por el filtro geográfico de nftables.

## Archivos

- `docker-compose.yml`
- `Dockerfile`
- `.env.example`
- `run-update.sh`

## Configuración

```bash
cd /home/lechuga/L4D2-Iptable-Suite/geoip-updater
cp .env.example .env
```

Rellena `MAXMIND_LICENSE_KEY`.
Rellena `GEOIPUPDATE_LICENSE_KEY`. Si quieres mantener el formato mental de `GeoIP.conf`, también puedes usar `GEOIPUPDATE_ACCOUNT_ID` y `GEOIPUPDATE_EDITION_IDS`.

## Ejecución manual

```bash
cd /home/lechuga/L4D2-Iptable-Suite
make geoip-update
```

Esto descarga el ZIP CSV y regenera los archivos bajo `geoip/generated/countries/` según `GEO_POLICY_ALLOWED_COUNTRIES` y `GEO_POLICY_DENIED_COUNTRIES` del `.env` principal.

Variables esperadas en `geoip-updater/.env`:

```dotenv
GEOIPUPDATE_ACCOUNT_ID=20000
GEOIPUPDATE_LICENSE_KEY=tu_license_key
GEOIPUPDATE_EDITION_IDS="GeoLite2-Country-CSV"
```

Nota: este updater no usa `.mmdb`; toma el mismo estilo de credenciales que `geoipupdate`, pero descarga el CSV porque ese formato es el que necesitamos para generar sets de nftables.

## Cron semanal

Ejemplo todos los lunes a las 04:15:

```bash
15 4 * * 1 cd /home/lechuga/L4D2-Iptable-Suite && make geoip-refresh-safe >> /home/lechuga/L4D2-Iptable-Suite/geoip-updater/geoip-updater.log 2>&1
```

Si prefieres separar pasos, también puedes usar `make geoip-update` y luego `make geoip-apply`.
Si quieres ver el estado actual del filtro geo y los archivos cargados, usa `make status`.

## Notas

- Usa la ruta CSV de MaxMind, no `.mmdb`.
- El contenedor no toca `nftables` directamente; solo actualiza los archivos de prefijos.
- `WHITELISTED_IPS` y `WHITELISTED_DOMAINS` siguen siendo bypass fuera de este flujo.