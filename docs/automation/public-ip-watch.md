# Vigilancia de IP pública

`l4d2-public-ip-watch` detecta cambios de IPv4 pública y coordina una
reaplicación controlada de la política nftables del suite. El router sigue
actualizando el registro DDNS; este servicio no inicia sesión en No-IP ni cambia
registros DNS.

La unidad systemd es un servicio `oneshot` root, endurecido y limitado a una
ejecución de tres minutos. El timer comienza dos minutos después del arranque y
vuelve a programarlo cada diez minutos, con una variación de hasta 30 segundos
y recuperación de ejecuciones perdidas. El servicio espera a la red y a
`l4d2-firewall.service`.

## Verificación y decisión

En cada ejecución normal, el watcher:

1. Consulta el detector IPv4 de No-IP con `curl -4`, límite de tiempo y un
   reintento. Valida el formato y descarta rangos privados, loopback,
   link-local, multicast y los rangos reservados/documentación que enumera el
   script.
2. Si `REQUIRE_DDNS_MATCH=true`, pregunta por el registro A configurado a los
   nameservers indicados y exige al menos `DDNS_MIN_MATCHES` respuestas iguales
   a la IP detectada. Cada servidor cuenta como máximo una coincidencia.
3. Lee el estado guardado, compara las direcciones y decide si debe recargar.
4. Ante un cambio confirmado (o `--force`), la IP nueva sólo dispara la
   operación: primero valida y luego reaplica la configuración nftables
   indicada por `FIREWALL_ENV_FILE`. El watcher no inserta la IP detectada en
   reglas ni la pasa como argumento al entrypoint.
5. Ejecuta el hook opcional y guarda la nueva IP después de que todas las
   acciones anteriores terminen correctamente.

Una primera ejecución sin `current-ip` sólo inicializa el estado: no aplica
firewall ni llama el hook. Un fallo de consulta o una discrepancia DNS no
cambia el firewall ni avanza el estado. El estado se actualiza de forma
atómica en `/var/lib/l4d2-public-ip-watch/current-ip`.

`--check` consulta WAN y DDNS y muestra la IP guardada; no crea el lock del
watcher ni modifica estado o firewall. `--dry-run` hace la misma evaluación
bajo el lock y muestra la acción que tomaría, sin actualizar la IP guardada,
ejecutar el hook ni cambiar el firewall. `--force` solicita una reaplicación
aunque la IP guardada no haya cambiado; igualmente exige la validación DDNS
configurada. Se pueden combinar `--dry-run --force` para ver esa decisión sin
aplicarla.

## Configuración

La unidad lee `/etc/default/l4d2-public-ip-watch`. Es un archivo declarativo
`CLAVE=VALOR`; no se ejecuta como shell. `PUBLIC_IP_WATCH_CONFIG` permite elegir
otro archivo para una ejecución manual. Una clave presente en el archivo
prevalece sobre una variable de entorno del mismo nombre; si falta, el watcher
usa la variable de entorno y luego su valor predeterminado.

Las opciones principales son:

| Clave | Uso |
| --- | --- |
| `NOIP_CHECK_URL`, `NOIP_USER_AGENT`, `HTTP_TIMEOUT_SECONDS` | Endpoint de detección, agente y timeout HTTP |
| `DDNS_HOSTNAME` | Nombre cuyo registro A se compara con la IP WAN |
| `DDNS_NAMESERVERS` | Lista de servidores consultados; por defecto `ns1.no-ip.com` a `ns4.no-ip.com` |
| `DDNS_MIN_MATCHES` | Coincidencias mínimas; por defecto 2 |
| `REQUIRE_DDNS_MATCH` | `true` (predeterminado) exige la coincidencia; `false` omite sólo esa comprobación |
| `FIREWALL_SCRIPT` | Entry point ejecutable, normalmente `/opt/l4d2-firewall/nftables.rules.sh` |
| `FIREWALL_ENV_FILE` | Archivo de configuración pasado al entrypoint, normalmente `/opt/l4d2-firewall/.env` |
| `EXTERNAL_ADMIN_VERIFIER` | Ejecutable confiable que verifica una conexión administrativa nueva desde otro host |
| `POST_CHANGE_HOOK` | Ejecutable opcional llamado con `IP_ANTERIOR IP_ACTUAL` |
| `STATE_FILE`, `LOCK_FILE` | Estado persistente y lock propio del watcher |

El ejemplo versionado está en
[`config/l4d2-public-ip-watch.env.example`](../../config/l4d2-public-ip-watch.env.example).
Reemplaza `games.example.net`, las rutas del host y el verificador de ejemplo
por valores reales. Protege la configuración como archivo root-owned modo
`0600`; el servicio valida la confianza de sus rutas antes de ejecutar el
firewall, el archivo de entorno o el hook. Mantén el archivo del watcher en
`/etc/default/l4d2-public-ip-watch`; el `.env` raíz del suite configura la
política que se reaplica y debe estar en la instalación confiable, normalmente
`/opt/l4d2-firewall/.env`.

El watcher exige `EXTERNAL_ADMIN_VERIFIER` para una reaplicación desatendida.
Ese verificador se ejecuta después de aplicar la candidata y debe comprobar
desde un equipo independiente que se puede abrir una conexión administrativa
nueva; el suite confirma automáticamente sólo si devuelve éxito. Si falla, el
watchdog transaccional restaura la política anterior. El verificador recibe el
token de confirmación en `SUITE_CONFIRM_TOKEN`; no debe imprimirlo en logs.

`POST_CHANGE_HOOK` corre como root, después de que el verificador confirmó el
firewall, con la IP previa y la nueva como dos argumentos. Debe ser un
ejecutable root confiable, acotado y probado. Si el hook falla, no revierte la
política nftables ya confirmada y el watcher no actualiza `current-ip`; una
ejecución posterior reintentará el flujo. El hook no debe reiniciar servidores
como efecto implícito.

## Locks y recuperación

El watcher adquiere `/run/l4d2-public-ip-watch/watch.lock` antes de consultar WAN/DDNS
y leer el estado, y lo mantiene durante consulta,
comparación, recarga, hook y guardado. Esto evita ejecuciones duplicadas del
watcher y serializa su estado. La recarga llama `nftables.rules.sh --dry-run`
y luego `nftables.rules.sh --verify-with VERIFICADOR`; el entrypoint usa el
mismo lock, journal y watchdog del resto de operaciones del suite. El lock del
watcher no sustituye al lock global del escritor y no coordina herramientas
externas que modifiquen Netfilter por fuera del suite.

El firewall no se actualiza con un flush global. La operación recompone la
política completa del suite a partir de `FIREWALL_ENV_FILE` y la aplica como
transacción, conservando las reglas ajenas. Si el verificador no confirma la
candidata antes del plazo, systemd ejecuta el rollback. El watcher deja la IP
anterior guardada para que la próxima ejecución reintente.

## Instalación y operación

Ejecutar desde raíz de la instalación confiable `/opt/l4d2-firewall` del destino,
tras ensayo desechable. `make public-ip-watch-test` es lógico sin root;
`sudo test` consulta existencia, `install` crea configuración, `sudoedit` la edita
y el target install modifica archivos/unidades y **habilita/inicia el timer** como
root. Los comandos de status/check/journal posteriores consultan; `--dry-run`
puede crear/tomar el lock local del watcher, pero no cambia Netfilter ni IP guardada.
La desactivación del timer también es una mutación privilegiada del destino.

Prueba primero el script aislado. Antes de instalar el timer, prepara una
configuración real: el instalador copia el ejemplo sólo si
`/etc/default/l4d2-public-ip-watch` no existe y luego habilita el timer.
Conserva y revisa cualquier archivo existente.

```bash
make public-ip-watch-test
if ! sudo test -e /etc/default/l4d2-public-ip-watch; then
  sudo install -o root -g root -m 0600 \
    config/l4d2-public-ip-watch.env.example \
    /etc/default/l4d2-public-ip-watch
fi
sudoedit /etc/default/l4d2-public-ip-watch
make public-ip-watch-install
```

`make public-ip-watch-install` instala el script en
`/usr/local/sbin/l4d2-public-ip-watch`, copia la unidad y el timer, conserva
una configuración ya existente, ejecuta `systemctl daemon-reload` y habilita
el timer. Las rutas de `FIREWALL_SCRIPT` y `FIREWALL_ENV_FILE` deben apuntar a
la instalación real del suite.

```bash
make public-ip-watch-status
sudo /usr/local/sbin/l4d2-public-ip-watch --check
sudo /usr/local/sbin/l4d2-public-ip-watch --dry-run
systemctl list-timers l4d2-public-ip-watch.timer
journalctl -u l4d2-public-ip-watch.service -f
```

`make public-ip-watch-status` muestra el resultado de `--check`, el timer y la
IP guardada. Para dejar de sondear, deshabilita y detén el timer:

```bash
sudo systemctl disable --now l4d2-public-ip-watch.timer
```

Esto no borra `current-ip`, no revierte una política confirmada ni elimina un
timer de rollback que ya estuviera activo. Reactivar el timer reanuda el
sondeo; una IP sin guardar vuelve a evaluarse en la siguiente ejecución.

## Límites

- El watcher detecta IPv4; no administra IPv6 ni actualiza No-IP.
- La comprobación DNS depende de las respuestas disponibles y de la lista de
  nameservers configurada; no sustituye supervisión DNSSEC ni verifica que el
  router haya recibido una dirección correcta fuera del detector consultado.
- Un timeout, bloqueo de red o respuestas inconsistentes se reintentan en
  ejecuciones futuras; no se aplica una regla basada en una respuesta parcial.
- La política sólo cambia cuando el watcher confirma una IP distinta o se usa
  `--force`. El hook opcional no forma parte de una transacción conjunta con
  Netfilter.
- El comportamiento y la configuración del daemon/router DDNS quedan fuera de
  este servicio.
