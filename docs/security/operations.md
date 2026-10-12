# Operación del núcleo transaccional

Los entrypoints se conservan: `iptables.rules.sh`, `nftables.rules.sh`, `ipp.sh`.
El código Python requiere 3.10+. Dependencias de operación: Bash, nftables,
iptables/ip6tables y restore/save, util-linux; systemd para cambios remotos.
Instalar previamente esas dependencias es responsabilidad del operador.
La suite no instala paquetes, reinicia servicios ni modifica sysctls.

## Flujo

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

## Configuración y propiedad

CLI `--set` > archivo > defaults. El entorno del proceso no configura el firewall.
Una variable ausente recibe default; una vaciada conserva vacío y, si es obligatoria,
falla. `--only`/`--skip` reemplazan las listas del archivo; no se fusionan. Sin lista
se usa `PROFILE=host-minimal`, que sólo incorpora SSH más el núcleo obligatorio.
Perfiles combinables: `--profile web --profile games`. `chain_setup`, `finalize` y
loopback pertenecen siempre al núcleo. `--only chain_setup,finalize` crea host cerrado.
`--only ''` explícito también selecciona sólo el núcleo; `MODULES_ONLY=''` en el
archivo, sin `--only`, conserva la selección por perfil.

`.env` es ahora un formato declarativo KEY=VALUE con comillas opcionales y comentarios.
No admite `export`, sustituciones, backticks, continuaciones, duplicados ni ejecución.
No hay fallback shell. Se validan IP/CIDR completos, puertos, interfaces exactas,
protocolos, booleanos, tasas, duraciones e identificadores. Las rutas de módulos
no son variables de configuración. La metadata se lee como datos de heredocs
literales; sólo se importa código seleccionado y validado. Los módulos ejecutados
por el generador tienen acceso de confianza como cualquier código root; no son una
sandbox para código malicioso. El generador sustituye comandos Netfilter por registros.

La expiración de buckets por origen debe cubrir su tiempo completo de recarga.
Si no se configuró un timeout, el núcleo amplía el default cuando hace falta;
un timeout explícito insuficiente falla. Esto incluye SSH/web, A2S/login y UDP NEW.
El default efectivo de login es 4s para burst16/rate4; mantener 1s permitiría
reiniciar el presupuesto prematuramente. Capacidad configurable: 16..65535 entradas
por meter/hashlimit, default8192, no capacidad ilimitada por origen.
iptables declara tanto el tamaño de tabla hash como su máximo: dejar el tamaño
implícito permite que el kernel eleve el máximo configurado.

Para operaciones privilegiadas, código, módulos, configuración, datos GeoIP y
verificadores deben ser root y no escribibles por grupo/otros, incluidos ancestros.
No se permiten symlinks en esas rutas. Usar una instalación revisada en
`/opt/l4d2-firewall` y configuración root en `/etc/l4d2-firewall`, en lugar del checkout
de desarrollo. La suite no cambia propietarios ni permisos automáticamente.

## Persistencia y operaciones parciales

`ipp.sh save` conserva sólo la política confirmada en
`/var/lib/l4d2-firewall/persisted.json`; `ipp.sh load` la comprueba y reaplica mediante
el mismo lock/journal/timer. No toca `/etc/nftables.conf`, `/etc/iptables/rules.v4`,
`rules.v6` ni unidades de otros administradores. La integración de arranque con
barrera temprana es opt-in y requiere preparar un manifiesto explícito. Sus unidades
no se instalan ni habilitan automáticamente, y los servicios/socket protegidos
requieren drop-ins individuales. La suite no intenta adivinar qué servicios deben
esperar. Con Docker, revisa la unidad instalada y el orden de cada `ExecStop` antes
de adaptar el ejemplo; el drop-in debe rearmar la barrera antes de detener el daemon.
El procedimiento, el alcance y los límites están en [protección de arranque](boot-protection.md).

```sh
sudo ./ipp.sh save
sudo ./ipp.sh load
sudo ./ipp.sh apply --partial --only tcp_ssh --set SSH_RATE=30/minute
sudo ./ipp.sh apply --remove http_https_protect
# Retirar simultáneamente los grants que referían al servicio:
sudo ./ipp.sh apply --remove http_https_protect --set ACCESS_POLICY=/etc/l4d2-firewall/remaining.json
sudo ./ipp.sh disable
```

La barrera H3 usa `boot-prepare` tras aplicar, confirmar, guardar y comprobar con
`ready` la política en el kernel de este arranque. `boot-guard` la instala;
`boot-restore` restaura la persistencia y solo la retira tras verificar; `ready`
comprueba boot ID, digest y objetos administrados. La tabla nftables temprana con
prioridad `-310` también requiere `nft` cuando la política usa iptables-legacy.
Para `disable` o cambiar el alcance de un manifiesto preparado, detén primero los
consumidores y ejecuta desde consola `boot-disarm --local`. Sin opt-in no se añade
la barrera temprana. Los [ensayos VM H3](closure-plan-results.md) pasaron
con fallos de restore, reboots inválido/válido, socket y reinicio Docker; su
matriz y límites no se extrapolan a otros destinos.

Especificar `--backend iptables` al operar ese motor. Operaciones parciales requieren
una política confirmada y módulos/dependencias existentes. Se recompone una candidata
completa; no se añaden fragmentos sobre cadenas desconocidas. La eliminación de un
módulo vuelve a comprobar dependencias y permisos de contenedores. Para retirar juego,
retirar sus tres módulos juntos. Desactivar retira solamente objetos y hooks propios;
no cambia políticas de terceros. La persistencia guardada permanece para restauración.

Desactivar no exige que Docker siga disponible. En iptables se permite deriva de
versión para desactivar, pero se exige el mismo frontend confirmado. La carga tras
un arranque admite ausencia total de cadenas propias; objetos parcialmente presentes
con hooks ausentes o desplazados requieren revisión antes de aplicar.
Para desinstalar definitivamente, borrar **sólo** el directorio de instalación/estado
propio y la unidad de la suite, tras desactivarla y cancelar cualquier cambio pendiente.
No se proporciona una operación de limpieza global de firewalls.

## Automatización

Watcher y recarga GeoIP llaman al mismo entrypoint y por tanto comparten lock.
El lock propio del watcher sólo evita consultas/estado duplicados; no sustituye al
lock del escritor ni se anida con él. `EXTERNAL_ADMIN_VERIFIER` es obligatorio para
recargas desatendidas del watcher. GeoIP usa `make geoip-apply ADMIN_VERIFIER=/ruta`;
sin verificador la recarga queda pendiente de confirmación y vuelve atrás al expirar.
El updater de CSV no escribe Netfilter; reemplaza archivos individuales atómicamente.
Una actualización multi-país no es una transacción de todos los archivos; revisar
la candidata generada si se necesita coherencia de una misma edición de datos.
