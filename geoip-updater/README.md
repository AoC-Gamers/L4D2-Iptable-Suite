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

Rellena `GEOIPUPDATE_LICENSE_KEY`. Si quieres mantener el formato mental de `GeoIP.conf`, también puedes usar `GEOIPUPDATE_ACCOUNT_ID` y `GEOIPUPDATE_EDITION_IDS`.
En `HOST_UID` y `HOST_GID`, usa los números que poseen el checkout (`stat -c '%u %g' ..` desde este directorio). `make geoip-update` los calcula automáticamente. Para ejecutar Compose directamente, pasa el archivo con `--env-file .env` o exporta ambos valores; el `env_file` del servicio sólo los pone dentro del contenedor y no configura la interpolación de `user`.

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
Para confirmar una recarga desatendida, pasar `ADMIN_VERIFIER=/ruta/verificador-root`
a `make geoip-refresh-safe`; debe comprobar una conexión administrativa nueva desde
fuera del host. Sin verificador, la recarga queda pendiente y revierte al expirar.
Si quieres ver el estado actual del filtro geo y los archivos cargados, usa `make status`.

## Notas

- Usa la ruta CSV de MaxMind, no `.mmdb`.
- El contenedor no toca `nftables` directamente; solo actualiza los archivos de prefijos.
- Los bypass requieren `PRIVILEGED_BYPASS=true`; DNS exige además `DNS_ALLOWED_CIDRS`.
  El updater no otorga permisos de filtrado por descargar prefijos.
