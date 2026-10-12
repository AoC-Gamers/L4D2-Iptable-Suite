# Auditoría de selección y automatización

Esta nota registra las correcciones a tres errores de configuración y
automatización. Las pruebas usan configuración vacía, datos temporales y
ejecutables simulados; no consultan servicios públicos ni modifican Netfilter.

## Selección explícita vacía

`--only ''` o `--only` con una lista que se normaliza a vacío ahora significa
seleccionar sólo el núcleo. El valor ausente de `--only` conserva la precedencia
de configuración: si `MODULES_ONLY` está vacío, se carga `PROFILE` como antes.
Por ejemplo:

```sh
./nftables.rules.sh generate --env-file tests/empty.conf --only '' --profile games
```

La candidata no debe seleccionar módulos de servicio.

## GeoIP en el contenedor

El updater escribe en el checkout montado. Compose debe ejecutarlo con el UID/GID
que posee ese checkout; `make geoip-update` los obtiene de la raíz del repositorio.
Al ejecutar Compose directamente, exportar `HOST_UID` y `HOST_GID` o pasar
`geoip-updater/.env` con `--env-file`; el `env_file` del servicio sólo configura
el entorno del contenedor. La configuración de ejemplo usa UID/GID 1000 y debe
ajustarse a la propiedad real del checkout. `run-update.sh` comprueba la identidad antes de descargar;
las comprobaciones root de `read_config.py` y del generador permanecen activas.

La comprobación sin daemon de Docker es:

```sh
HOST_UID="$(stat -c '%u' .)" HOST_GID="$(stat -c '%g' .)" \
  docker compose --env-file geoip-updater/.env \
    -f geoip-updater/docker-compose.yml config
```

Debe mostrar `user` con los mismos números. Para validar la ejecución real sin
descargar MaxMind se requiere una imagen construida y un ZIP CSV mínimo local; la
prueba unitaria de propiedad por sí sola no afirma que el contenedor completo
haya corrido.

## Watcher concurrente

En modo normal y dry-run, el watcher toma su lock antes de consultar WAN/DDNS y
leer el estado guardado. Así el segundo proceso observa el estado ya actualizado
por el primero y no repite la recarga ni `POST_CHANGE_HOOK`. `--check` conserva su
comportamiento de sólo lectura y no toma ese lock.

La regresión usa dos procesos, respuestas WAN/DDNS simuladas y una barrera sobre
la adquisición del lock:

```sh
bash tests/watcher-audit.sh
```

El resultado esperado es una sola ejecución del hook para una transición de IP.
