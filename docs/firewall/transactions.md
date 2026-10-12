# Operación del núcleo transaccional

Los entrypoints se conservan: `iptables.rules.sh`, `nftables.rules.sh`, `ipp.sh`.
El código Python requiere 3.10+. Dependencias de operación: Bash, nftables,
iptables/ip6tables y restore/save, util-linux; systemd para cambios remotos.
Instalar previamente esas dependencias es responsabilidad del operador.
La suite no instala paquetes, reinicia servicios ni modifica sysctls.

## Flujo

Los ejemplos lógicos se ejecutan desde raíz del checkout, **sin root**. Para los
bloques con `sudo ./...`, el cwd es la raíz de la instalación confiable
`/opt/l4d2-firewall` en el destino o guest desechable, **nunca** el checkout editable.
Son mutaciones root salvo la composición lógica; los ejemplos usan rutas ficticias
que requieren archivos reales revisados. Los bloques son alternativas/procedimientos,
no un script para ejecutar completo sin confirmar cada cambio.

Configuración declarativa → conjunto efectivo → validación de todos los módulos
→ generación → comprobación del motor → journal/watchdog → aplicación → confirmación.

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh generate --env-file config/profiles/web.conf > candidate.json
./nftables.rules.sh plan --env-file config/profiles/web.conf --against previous.json
```

Estas operaciones no necesitan root ni consultan el firewall. `validate` también
genera para descubrir errores de composición. `--dry-run` equivale a `plan`.
No se anuncia comprobación del kernel ni del tráfico. `generate` entrega un
bundle JSON con reglas concretas, permisos, familias, módulos y registro de
objetos; `plan` muestra esas reglas y, con `--against`, diferencias y eliminaciones.
Sin baseline no se puede afirmar qué objetos desaparecerán del firewall activo.

Los comandos privilegiados toman el lock y recuperan primero cualquier journal
vencido. Por ello `check`, `status` y `doctor` pueden ejecutar rollback de un
cambio anterior expirado; no son observación estrictamente pasiva. Para una
auditoría pasiva usar `diagnose` (root, sin abrir ni recuperar el journal), las
operaciones lógicas sin root o consultas directas de lectura del motor.
`diagnose --backend iptables --set IPTABLES_FRONTEND=legacy` muestra también
el recorrido estructural hacia Docker por familia. La candidata de `check` no se aplica.

Las siguientes operaciones necesitan privilegios. Probar primero en VM o
namespace desechable, nunca sobre el firewall que mantiene acceso al repositorio:

```sh
sudo ./nftables.rules.sh check --env-file /etc/l4d2-firewall/web.conf
sudo ./nftables.rules.sh apply --env-file /etc/l4d2-firewall/web.conf --timeout 120
# Desde una conexión administrativa NUEVA, probada desde otra máquina:
sudo ./nftables.rules.sh confirm --token TOKEN --admin-verified
# Para deshacer inmediatamente:
sudo ./nftables.rules.sh rollback
```

La aceptación de la confirmación requiere el token y la declaración explícita
`--admin-verified`. El operador debe abrir una conexión nueva; mantener una sesión
SSH establecida no es una comprobación suficiente. El software no puede demostrar
por sí solo que el operador realizó esa comprobación. Para automatización,
`--verify-with /ruta/ejecutable` ejecuta un verificador root de una conexión nueva
**desde fuera del host**; un código distinto de cero o timeout restaura la política
anterior. Un `ss`, ping local o comprobación de la sesión existente no sirve.
El verificador no debe invocar al escritor ni confirmar por su cuenta: el escritor
mantiene el bloqueo mientras espera su resultado.

El watchdog de producción es un timer transitorio `systemd-run`, independiente
del proceso y la sesión aplicadora. Se arma antes de modificar reglas. Si no se
puede armar, no se aplica. La reversión vuelve a tomar el mismo bloqueo. Un cambio
pendiente bloquea nuevas aplicaciones. Confirmación y rollback serializan con ellas.
El plazo usa reloj monotónico y boot ID; un journal de otro arranque expira al
recuperarlo. No depende de que el reloj de pared se mantenga estable.
Los comandos de aplicación usan el presupuesto monotónico restante; si se agota,
se restaura la política previa y no se entrega un token confirmable. La espera de
iptables por su lock también se acota a ese presupuesto. Esto no garantiza un
tiempo máximo de restauración si el kernel o un escritor externo bloquean el motor.
`--watchdog process` usa un proceso separado por doble fork, únicamente dentro de
namespaces aislados de prueba. No se acepta como sustituto de systemd en el host.

`--local` omite el timer y confirma explícitamente para consola/arranque. No usarlo
para cambios remotos. Si ese proceso muere, recuperar desde consola con `rollback`;
no existe garantía de reversión temporizada en este modo elegido por el operador.

## Garantías por motor

nftables reemplaza exclusivamente las tablas registradas mediante **un** archivo:
`nft -c -f -` antes de `nft -f -`. La eliminación de la versión previa y creación
de la nueva están dentro de la misma transacción. No se hace `flush ruleset`.
No se adoptan tablas preexistentes por su nombre: una tabla sin registro causa error.
`NF_TABLE_NAME` se respeta; las tablas NAT derivan de ese nombre (`_nat4`/`_nat6`).

iptables usa cadenas `L4S_…` deterministas y una regla con comentario
`l4d2-suite:integration` por punto de integración. `iptables-restore --noflush`
**sí puede vaciar cadenas declaradas**: se declaran/vacían solamente las propias.
No se declaran ni vacían INPUT, FORWARD, OUTPUT, DOCKER-USER, NAT o mangle compartidas,
ni se cambian sus políticas. Insertar/eliminar un hook usa su especificación exacta.
Cada tabla/familia se comprueba previamente con `--test --noflush --wait 10`.
El commit es por tabla y familia; **no hay atomicidad conjunta IPv4/IPv6 ni filter/NAT**.
Un fallo/interrupción puede producir un intervalo de versiones mixtas hasta rollback.
No se promete ausencia de ese intervalo ni restauración del estado conntrack/NAT,
tokens de rate limit, contadores o conexiones descartadas.

El snapshot exporta sólo objetos registrados; nunca restaura una copia global del
firewall. Reglas añadidas por terceros a otras tablas/cadenas o cadenas compartidas
se conservan, también durante rollback. Los nombres registrados y el interior de
las cadenas/tablas propias son de uso exclusivo de la suite: otro administrador
no debe escribir dentro de ellos. El lock no controla administradores externos.
Para iptables, si otro administrador mueve el hook debajo de otras reglas, la
siguiente aplicación falla y pide revisión; rollback conserva esas reglas externas.

## Confianza, estado y persistencia

Código, módulos, configuración, datos GeoIP y verificadores privilegiados deben ser
root y no escribibles por grupo/otros, incluidos ancestros; sin symlinks. La suite
no cambia propietarios/permisos automáticamente. Los generadores seleccionados
son código confiable, no una sandbox contra módulos maliciosos.

Formato, precedencia, defaults y estado derivado: [configuración](../configuration/README.md)
y [referencia](../configuration/reference.md). Los bundles schema 2 conservan
selección/dimensiones/ACL normalizadas, sin reabrir inputs de ACL ni resolver DNS.
Persistencia, partial/remove, carga, retirada y desinstalación:
[guía canónica](persistence.md). Sus mutaciones comparten este mismo lock/journal/timer.
Barrera de arranque y readiness tienen manifiesto independiente; guardar no las
activa: [preparación](../boot/README.md) y [recuperación](../boot/recovery.md).

## Automatización

Watcher y recarga GeoIP llaman al mismo entrypoint y por tanto comparten lock.
El lock propio del watcher sólo evita consultas/estado duplicados; no sustituye al
lock del escritor ni se anida con él. `EXTERNAL_ADMIN_VERIFIER` es obligatorio para
recargas desatendidas del watcher. GeoIP usa `make geoip-apply ADMIN_VERIFIER=/ruta`;
sin verificador la recarga queda pendiente de confirmación y vuelve atrás al expirar.
El updater de CSV no escribe Netfilter; reemplaza archivos individuales atómicamente.
Una actualización multi-país no es una transacción de todos los archivos; revisar
la candidata generada si se necesita coherencia de una misma edición de datos.
