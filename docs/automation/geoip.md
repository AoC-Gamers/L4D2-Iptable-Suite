# Actualizador GeoIP

Este flujo descarga GeoLite2 Country en formato CSV, genera archivos de
prefijos IPv4 por país y, en un paso separado, aplica la política nftables del
suite. El contenedor sólo descarga y escribe datos; no monta el socket del
daemon Docker ni recibe capacidades de red para cambiar Netfilter. Compose lo
ejecuta con el UID/GID propietario del checkout. Separa los dos usos: un
checkout de desarrollo propiedad de una cuenta no root sirve para descargar y
generar archivos; la aplicación privilegiada debe ejecutarse desde la
instalación confiable y root-owned (por ejemplo, `/opt/l4d2-firewall`) con
configuración y datos también confiables. Si `/opt/l4d2-firewall` pertenece a
root, el actualizador corre como UID 0 dentro del contenedor porque escribe en
ese checkout; no se debe presentar ese cron como una ejecución de menor
privilegio.

## Dos archivos de configuración

Los ejemplos de este apartado parten de raíz del checkout, usuario sin root con
acceso autorizado a Docker para generación. `cp` crea un archivo: no sobrescribir
uno privado existente; `chmod` restringe su lectura. No mezcles credenciales de
descarga con el KEY=VALUE del firewall. No se ejecutaron estos ejemplos en el host.

El actualizador usa dos archivos distintos:

- `geoip-updater/.env` contiene variables de descarga y ejecución del
  contenedor. Créalo desde el ejemplo y mantenlo fuera de Git:

  ```bash
  cp geoip-updater/.env.example geoip-updater/.env
  chmod 0600 geoip-updater/.env
  ```

- El `.env` de la raíz del repositorio contiene la política del firewall:
  `GEO_POLICY_ALLOWED_COUNTRIES`, `GEO_POLICY_DENIED_COUNTRIES` y
  `GEO_POLICY_DATA_DIR`. El script lo lee con el parser declarativo del suite;
  no lo ejecuta como shell.

`GEOIPUPDATE_LICENSE_KEY` es la clave de descarga; si no está definida se
acepta el alias `MAXMIND_LICENSE_KEY`. `GEOIPUPDATE_ACCOUNT_ID` (o
`MAXMIND_ACCOUNT_ID`) es opcional e informativo: el downloader autentica con la
license key. `GEOIPUPDATE_EDITION_IDS` (o `MAXMIND_EDITION_ID`) puede listar
ediciones separadas por espacios o comas; se elige la primera edición
reconocida, `GeoLite2-Country-CSV` o `GeoIP2-Country-CSV`, y se usa GeoLite2
Country CSV si ninguna coincide. `MAXMIND_DOWNLOAD_URL`, si se define,
reemplaza la URL calculada y permite usar una fuente compatible o una URL
`file://` de prueba sin license key.

Las variables de `geoip-updater/.env` entran al contenedor mediante Compose
`env_file`. El shell no carga ese archivo por sí mismo. El Makefile calcula
`HOST_UID` y `HOST_GID` con el propietario numérico del checkout y los pasa a
Compose para que el proceso escriba como ese usuario. En una ejecución Compose
directa, proporciona también esos dos valores correctos. En un checkout de
desarrollo propiedad de una cuenta no root, evita que la imagen escriba como root.

El `env_file` del servicio configura el entorno dentro del contenedor; no aporta
por sí solo variables para interpolar `user` en Compose. Para invocación directa,
exporta UID/GID o suminístralos con `docker compose --env-file`, como en el ejemplo
de esta guía. Una identidad incorrecta falla antes de descargar.

Variables de ejecución menos comunes:

| Variable | Valor predeterminado | Función |
| --- | --- | --- |
| `WORKSPACE_ROOT` | `/workspace` | Checkout montado en el contenedor |
| `ENV_FILE` | `$WORKSPACE_ROOT/.env` | Configuración de política de la raíz |
| `DOWNLOAD_DIR` | `/tmp/maxmind` | ZIP descargado dentro del contenedor |
| `KEEP_ARCHIVE` | `false` | Conserva el ZIP tras una generación exitosa si vale `true` |

Si falla la descarga o generación, el proceso termina con error y el estado de
Netfilter no cambia. Un ZIP puede quedar en `DOWNLOAD_DIR` tras un fallo para
diagnóstico. Protege cualquier URL personalizada que contenga credenciales.

## Generación de prefijos

`make geoip-update` construye o reutiliza la imagen Docker y ejecuta
`geoip-updater/run-update.sh` con el checkout montado en `/workspace`. El
generador lee sólo `GEO_POLICY_ALLOWED_COUNTRIES`,
`GEO_POLICY_DENIED_COUNTRIES` y `GEO_POLICY_DATA_DIR` del `.env` principal.
Normaliza y une los dos listados de países sin duplicados, valida que cada
código sea ISO alfa-2 y extrae los CSV de ubicaciones y bloques IPv4 del ZIP.
Para cada código escribe `CC.ipv4.txt` bajo `GEO_POLICY_DATA_DIR` (por defecto
`geoip/generated/countries/`). Cada archivo se reemplaza atómicamente y se
sincroniza en disco.

Esto no aplica ninguna política. Los archivos se generan para la unión de los
códigos permitidos y denegados, independientemente de si el modo actual está
`off`, `allowlist` o `denylist`. No se borran automáticamente archivos de
códigos que ya no aparecen en la configuración; el compilador sólo consume los
códigos seleccionados por el `.env` actual. El conjunto GeoIP es IPv4. Si se
usa junto a una política dual-stack, el suite requiere una decisión explícita
para IPv6 mediante `GEO_IPV6_POLICY=deny`.

La actualización reemplaza cada país por separado; no es una transacción
atómica de todos los países. Evita ejecutar `make geoip-apply` mientras otra
ejecución genera los archivos. El directorio de prefijos generados está
ignorado por Git.

## Aplicación transaccional

`make geoip-apply` aplica los archivos existentes usando
`nftables.rules.sh apply`; no descarga datos ni usa el backend iptables. Debe
ejecutarse desde la instalación confiable root-owned, con su `.env`, archivos
GeoIP y todos sus directorios padres confiables y no modificables por grupo u
otros. El núcleo rechaza código, configuración y datos privilegiados si una
ruta puede modificarse por una cuenta no confiable. La aplicación entra al
mismo lock, journal y watchdog transaccional que las demás operaciones de
firewall del suite. El lock de firewall serializa escritores del suite,
incluido el watcher de IP pública, pero no controla administradores externos
que modifiquen Netfilter directamente.

Para una ejecución manual desde raíz de la instalación confiable en el destino:
`geoip-check` comprueba sintaxis/Compose y escribe un diagnóstico temporal; no aplica
reglas. `geoip-update` requiere acceso Docker, descarga y escribe prefijos.
`geoip-apply` eleva root mediante sudo y cambia Netfilter con el flujo temporizado.
El verificador de la ruta siguiente es un ejemplo a implementar/probar externamente.
Recuperación: [rollback y confirmación](../firewall/transactions.md).

```bash
make geoip-check
make geoip-update
make geoip-apply ADMIN_VERIFIER=/usr/local/libexec/check-new-admin-connection
```

`ADMIN_VERIFIER` debe ser un ejecutable root-confiable que verifique una
conexión administrativa nueva desde un equipo independiente. Si pasa, el
entrypoint confirma automáticamente la candidata. Sin verificador, `apply`
deja un cambio con rollback temporizado y muestra el token; hay que probar una
conexión nueva y confirmar explícitamente antes de que venza el plazo. Un
trabajo cron sin esa confirmación no deja el cambio aplicado: el watchdog
revierte la candidata.

Para programación desatendida desde la instalación root-owned, ejecuta el
trabajo como root y usa `geoip-refresh-safe`. El `flock` no bloqueante evita
dos refrescos seguros concurrentes. Como Compose elige el dueño del checkout,
el contenedor tendrá UID 0 en esta instalación; el apply necesita este árbol
confiable para cruzar la frontera privilegiada:

```bash
make geoip-refresh-safe ADMIN_VERIFIER=/usr/local/libexec/check-new-admin-connection
```

Ejemplo de cron semanal ejecutado como `root` desde `/opt/l4d2-firewall`,
instalación y datos propiedad de root y no modificables por grupo u otros.
`SUDO=` evita que Make intente invocar `sudo` dentro de cron; el lock se mueve
a un directorio administrado por root:

```cron
15 4 * * 1 cd /opt/l4d2-firewall && make geoip-refresh-safe SUDO= GEOIP_LOCK_FILE=/run/lock/l4d2-geoip-refresh.lock ADMIN_VERIFIER=/usr/local/libexec/check-new-admin-connection >> /var/log/l4d2-geoip-refresh.log 2>&1
```

El lock adicional por defecto es `/tmp/l4d2-geoip-refresh.lock`; se puede
seleccionar otro con `GEOIP_LOCK_FILE=/ruta/lock`. En producción, usa una ruta
en un directorio de lock controlado por root. Ese `flock` sólo serializa
invocaciones de `geoip-refresh-safe`; no sustituye el lock del writer ni cubre
ejecuciones manuales de `geoip-update` o `geoip-apply`.

## Ejecución directa de Compose

En un checkout de desarrollo propiedad de una cuenta no root, `make
geoip-update` calcula el UID/GID correcto y permite descargar/generar sin
ejecutar como root en el host. Ese árbol no es una fuente apta para una
aplicación privilegiada. Revisa los archivos generados y promuévelos mediante
un procedimiento controlado a la instalación root-owned; verifica propiedad
y permisos de cada archivo y directorio antes de aplicar. Para actualizar
directamente la instalación operativa, ejecuta el updater desde ese checkout
root-owned (el contenedor usará UID 0). Si necesitas invocar Compose
directamente:

```bash
cd geoip-updater
HOST_UID="$(stat -c '%u' ..)" HOST_GID="$(stat -c '%g' ..)" \
  docker compose --env-file .env run --rm geoip-updater
```

El comando requiere Docker Compose, un `.env` de updater configurado y
permisos de escritura del usuario elegido en el checkout. Para desarrollo,
usa un checkout propiedad de una cuenta no root. Para una actualización
operativa, usa el checkout root-owned y acepta que el proceso sea UID 0 dentro
del contenedor. No montes el socket Docker dentro del contenedor.

## Diagnóstico

Desde raíz, con acceso Docker para Compose y privilegio de lectura Netfilter si
se usa `status`: se comprueba sintaxis, listan/clasifican archivos y consulta estado.
`RESOLVE_DOMAINS=1` hace consultas DNS. `status` imprime `GEO_POLICY_*` del archivo
privado, por lo que no compartas su salida sin revisar. No cambia reglas.

```bash
make geoip-check
make geoip-list
make geoip-check-ip IP=203.0.113.10
make geoip-check-ip IP=203.0.113.10 RESOLVE_DOMAINS=1
make status
```

`geoip-check` valida sintaxis y configuración de Compose; `geoip-check-ip`
clasifica una IP/CIDR según el `.env` principal y archivos presentes; `status`
muestra la configuración GeoIP, los archivos generados y objetos nftables
visibles con los permisos disponibles. El actualizador no valida una sesión
real de juego ni certifica frescura/licencia de los datos descargados.

## Política GeoIP del servicio

El ID `geo_country_filter` solo existe en nftables y filtra IPv4 de entrada al host
en puertos GameServer/SourceTV. Puede seleccionarse independiente; para controles
de juego requiere seleccionar además su grupo completo. `GEO_POLICY_MODE` admite
`off`, `allowlist`, `denylist`; dentro del gate rige deny manual → allow manual →
decisión por país. No sustituye límites de tasa ni concede permisos de forwarding.
Datos `CC.ipv4.txt` y listas manuales deben ser inputs confiables; modo dual activo
exige `GEO_IPV6_POLICY=deny`. No hay GeoIPv6. La prueba offline usa ZIP sintético,
no acredita frescura/calidad/licencia MaxMind actual: [límites](../security/limitations.md).
Código: [generador CSV](../../scripts/geoip/build_geo_country_sets.py),
[módulo GeoIP](../../modules/nf/nf_15_geo_country_filter.sh).
Pruebas: [unitario](../../tests/test_geoip.py), [VM](../testing/clients.md).
