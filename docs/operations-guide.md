# Guía operativa

La suite compone una política declarativa y administra únicamente los objetos
registrados como propios. Antes de un cambio, entiende la política activa del
host y revisa la candidata. Para migraciones o cambios de backend, ensaya primero
en una VM. El contrato detallado y sus límites están en [operaciones](security/operations.md),
[capacidades probadas](security/capabilities.md) y [migración](security/migration.md).
El [índice de documentación](README.md) y la [referencia de configuración](configuration.md)
describen perfiles y permisos disponibles.

Los entrypoints `nftables.rules.sh` e `iptables.rules.sh` aplican por defecto si
se invocan sin operación; escribe siempre `validate`, `generate`, `plan`, `check`
o `apply` explícitamente. `ipp.sh` sin argumentos solo muestra ayuda.

## Preparar y revisar una candidata

Usa una configuración declarativa `KEY=VALUE`, por ejemplo uno de los archivos
de [perfiles](../config/profiles/). Un archivo vacío no carga todos los módulos:
se usa `PROFILE=host-minimal`. La precedencia es `--set`, archivo y defaults;
una clave vacía sigue vacía y no recibe el default. `--only` y `--skip` reemplazan
la selección del archivo. Perfiles y módulos deben escogerse conscientemente.

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh generate --env-file config/profiles/web.conf > /tmp/web-candidate.json
./nftables.rules.sh plan --env-file config/profiles/web.conf --against /tmp/previous.json
./iptables.rules.sh plan --env-file /etc/l4d2-firewall/server.conf
```

`validate` valida y genera lógicamente, pero no consulta el kernel. `generate`
imprime el bundle JSON; `plan` muestra reglas y, si se proporciona una candidata
anterior, diferencias y objetos/cadenas que desaparecerían. `--dry-run` es alias
de `plan`, no una simulación del kernel ni del tráfico. Redirige la salida JSON a
un archivo protegido si contiene datos de configuración sensibles.

Prueba el comportamiento del motor solo en un entorno aislado. Las pruebas
unitarias y de generación no requieren root; `tests/isolated-run.sh` crea namespaces
de usuario, red y montaje desechables, y mantiene `/run` privado para que el lock
de xtables no comparta archivo con el host:

```sh
bash tests/smoke-modules.sh
bash tests/isolated-run.sh
```

El script requiere `unshare`, `mount`, `nft`, iptables/ip6tables, `ip` y Python.
Si el kernel no permite namespaces, no lo sustituyas por ejecución directa de
pruebas con root sobre la red anfitriona.

## Comprobación y aplicación

### Instalar desde una ruta confiable

Las operaciones privilegiadas requieren el árbol revisado completo bajo una ruta
confiable, por ejemplo `/opt/l4d2-firewall`, y configuración/ACL/GeoIP que use
la operación bajo `/etc/l4d2-firewall`. Los archivos, directorios y ancestros
relevantes deben ser root-owned, no escribibles por grupo/otros y sin symlinks.
El checkout editable bajo el home de un usuario no sirve como instalación root:
la suite valida la propiedad antes de cargar código y configuración. Despliega
una versión revisada y conserva los permisos ejecutables de los entrypoints.
La suite no copia el árbol ni corrige propietarios/permisos por sí sola.

Haz la composición y revisión con rutas explícitas:

```sh
/opt/l4d2-firewall/nftables.rules.sh validate --env-file /etc/l4d2-firewall/server.conf
/opt/l4d2-firewall/nftables.rules.sh plan --env-file /etc/l4d2-firewall/server.conf
```

`check` requiere privilegios y consulta el estado actual para verificar la
candidata contra el motor, sin aplicarla, excepto que la CLI primero recupera un
journal de aplicación ya vencido. `status`, `doctor`, `save`, `load` y `disable`
también procesan una transacción vencida antes de continuar. Antes de producción,
comprueba la configuración en VM y establece consola fuera de banda. Los comandos
siguientes son una secuencia operativa: elige un solo backend y usa la misma configuración.

```sh
sudo /opt/l4d2-firewall/nftables.rules.sh check --env-file /etc/l4d2-firewall/server.conf
sudo /opt/l4d2-firewall/nftables.rules.sh apply --env-file /etc/l4d2-firewall/server.conf --timeout 120
```

El comando prepara y comprueba todas las transacciones antes de registrar el
journal. Después arma el watchdog systemd y solo entonces modifica Netfilter.
Si aplica sin `--local` ni `--verify-with`, entrega un token y deja
la candidata pendiente durante el timeout. Desde otra máquina, abre y prueba una
conexión administrativa **nueva**; una sesión SSH ya establecida no demuestra
acceso futuro. `--admin-verified` es una declaración del operador; la suite no
puede demostrar que hiciste la conexión. Solo entonces confirma:

```sh
sudo /opt/l4d2-firewall/nftables.rules.sh confirm --token TOKEN --admin-verified
```

Si la prueba falla, o si prefieres revertir de inmediato, ejecuta `rollback`:

```sh
sudo /opt/l4d2-firewall/nftables.rules.sh rollback
```

Al expirar el plazo, el watchdog independiente restaura los objetos anteriores.
La suite no garantiza una reversión si el kernel o un escritor externo bloquea
Netfilter. `--local` omite el watchdog y confirma para uso desde consola/arranque;
no lo uses para cambios remotos. `--verify-with` solo es apropiado con un verificador
root confiable que pruebe una conexión nueva desde fuera del host.

## Operación y persistencia

`/opt/l4d2-firewall/ipp.sh status` muestra el registro de política; `doctor` inspecciona los motores
y objetos presentes. `disable` inicia un cambio temporizado que retira únicamente
los objetos y hooks registrados por la suite; pruébalo y confírmalo igual que
`apply`. `save` guarda la política
confirmada de la suite en `/var/lib/l4d2-firewall/persisted.json`; `load` vuelve a
comprobarla y la aplica con el mismo flujo de confirmación. Ninguna de estas
operaciones edita persistencia global de nftables/iptables ni adopta objetos por
su nombre. Revisa [gestión selectiva y persistencia](ipp.md) antes de usar esas
operaciones.

```sh
sudo /opt/l4d2-firewall/ipp.sh status
sudo /opt/l4d2-firewall/ipp.sh doctor
sudo /opt/l4d2-firewall/ipp.sh save
sudo /opt/l4d2-firewall/ipp.sh load --timeout 120
```

Una política pendiente impide iniciar otra aplicación: confirma o revierte antes
de continuar. Cambios parciales requieren una política confirmada y se recomponen
como candidata completa; no admiten `--env-file`. Si eliminas un módulo con grants
de contenedor, actualiza `ACCESS_POLICY` con un archivo que retire esos grants en
la misma operación. Para Docker, grants o cambios de backend, consulta las
garantías y requisitos de [operaciones](security/operations.md) y [migración](security/migration.md).

## Configuración y límites de lectura

`HOST_SERVICES`, `CONTAINER_POLICY` y `ROUTED_POLICY` son controles independientes;
el forwarding por defecto se descarta. NAT o una publicación de Docker no otorgan
permiso por sí solos. Los grants declaran origen, destino, interfaces, protocolo,
puertos y, para contenedores, los extremos público e interno. `TYPECHAIN` es un
alias heredado y no sustituye grants ni política de routing.

Los módulos publican metadata literal (`ID`, aliases, variables requeridas,
opcionales y defaults). La configuración se valida antes de que generadores de
módulo produzcan registros; los módulos no invocan el motor durante la generación.
El código de módulos sigue siendo código confiable, no una sandbox. Los detalles
de familia IP, Docker, VPN, límites de estado y garantías por motor están en
[capacidades](security/capabilities.md).

Los registros y capturas solo describen tráfico que las reglas decidieron registrar;
ausencia de evento no demuestra ausencia de bloqueo. Para diagnosticar, consulta
el estado del motor y las guías específicas, y no reapliques una política sin pasar
por `check` y la confirmación temporizada.
