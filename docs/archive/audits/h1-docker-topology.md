# Cierre H1: recorrido iptables hacia Docker

> Archivo histórico. Se conserva el contenido del informe/manual anterior; no es
> la guía operativa vigente. Consulta el [índice actual](../../README.md) y
> [la aprobación por commit](../../security/approval.md).

H1 verifica el recorrido iptables hacia `DOCKER-USER` antes de aplicar una
política que concede grants de contenedor. No reordena ni repara reglas ajenas.
La validación corre en el preflight común usado por `check`, `apply` y `load`,
después de inspeccionar el frontend y antes de preparar/escribir transacciones.

## Regla conservadora

Para **cada familia IPv4 e IPv6** se requiere:

- cadenas `filter/FORWARD` y `filter/DOCKER-USER` existentes;
- exactamente un salto desde `FORWARD` a `DOCKER-USER`;
- ese salto debe ser la primera regla de `FORWARD`, incondicional y con sintaxis
  reconocida (`-j`/`--jump`, comentarios inertes opcionales).

Una condición, `goto`, salto duplicado, prefijo desconocido o regla previa,
incluido `ACCEPT`, produce error con familia y causa. Si ya está instalada la
suite, el hook registrado también debe aparecer exactamente una vez y primero
en `DOCKER-USER`. Una validación fallida no escribe reglas. El preflight no
impone esta topología a la suite nftables nativa, cuyos grants usan hooks nft.

El diagnóstico estructural puro está en `engine.docker_forward_diagnostic()`;
solo analiza snapshots `iptables-save`, no consulta ni modifica el sistema. El
preflight lo usa para aplicar la política; el diagnóstico pasivo puede reutilizar
la función sin pasar por operaciones del journal.

`disable` sigue disponible aunque Docker falte o haya cambiado el recorrido.
También puede retirarse un grant de contenedor sin exigir integración Docker
si la candidata ya no protege publicaciones. El bloqueo de escritor no impide
cambios de administradores externos después del preflight.

## Regresión y evidencia

La corrida VM `20261012T053512Z-f950c62d` pasó los cuatro métodos reales
H1 en cada frontend iptables 1.8.10, nft y legacy; ambos inspeccionan IPv4/IPv6.
La suite unitaria actual tiene 9 casos, incluida la reserva de nombre del guard.
La matriz Docker real de cinco combinaciones pasó por separado. El
[informe de cierre](h1-h3-plan-results.md) registra entorno y límites.

La siguiente evidencia conserva la primera ejecución sobre el kernel anfitrión
mediante namespaces; su limitación legacy no se aplica a la nueva VM:

En Linux `7.0.0-38-generic`, nftables `1.0.9` e iptables `1.8.10 (nf_tables)`:

- `python3 -I tests/test_docker_topology.py`: **8/8 PASS**. Incluye saltos
  condicionales, `goto`, comentarios lookalike, duplicados, ambas familias,
  integridad del hook propio, retirada sin Docker y no aplicación del criterio
  iptables a nft nativo.
- `bash tests/isolated-run.sh tests/docker-topology-flows.py`: **4/4 PASS**.
  El tráfico TCP publicado pasó para la fuente autorizada y fue bloqueado para
  otra fuente; `ACCEPT` delante de `DOCKER-USER` fue rechazado sin cambios en
  el ruleset; mover el hook propio delante de una regla externa también fue
  rechazado sin reordenarla. También se retiró el grant y se ejecutó `disable`
  después de desaparecer las cadenas Docker; la limpieza de la suite quedó
  disponible y eliminó sus objetos.

El ensayo isolated usa cadenas/NAT y peers de tráfico sintéticos en namespaces
desechables; **no usa un daemon Docker real** ni demuestra operación en cada
host. Se intentó iptables-legacy 1.8.10 en el mismo aislamiento, pero el kernel
denegó la lectura de `/proc/net/ip_tables_names` (`Permission denied`) durante
la preparación; no se cargaron módulos ni se tocó el firewall anfitrión. Por
eso esta evidencia de H1 no cubre el frontend legacy.

Comandos de reproducción:

```sh
python3 -I tests/test_docker_topology.py
bash tests/isolated-run.sh tests/docker-topology-flows.py
SUITE_TEST_FRONTEND=legacy bash tests/isolated-run.sh tests/docker-topology-flows.py
```
