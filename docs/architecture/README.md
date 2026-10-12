# Arquitectura modular y contrato del generador

Los entrypoints [`nftables.rules.sh`](../../nftables.rules.sh) e
[`iptables.rules.sh`](../../iptables.rules.sh) invocan el mismo CLI Python aislado
(`core/fw.py`); [`ipp.sh`](../firewall/persistence.md) delega en él. `core/config.py` interpreta
configuración y metadata; `core/compiler.py` valida módulos y convierte las
llamadas registradas a una política JSON; `core/engine.py` inspecciona y prepara
transacciones Netfilter; `core/store.py` serializa operaciones, journal y
rollback temporizado.

## Composición y generación

Cada módulo declara metadata en un heredoc literal: `ID`, `ALIASES`, `DESCRIPTION`,
`REQUIRED_VARS`, `OPTIONAL_VARS` y `DEFAULTS`. El núcleo lee esos campos como
datos, resuelve los módulos/perfiles efectivos y defaults únicamente para claves
ausentes, comprueba dependencias, incompatibilidades y valores, y después ejecuta
validadores/generadores de los módulos seleccionados en un entorno controlado.
Los entrypoints antiguos `preload.sh` y `run_target_modules` no son rutas de
aplicación; fallan explícitamente. No interpretes metadata como configuración de
confianza: los scripts seleccionados siguen siendo código y deben pertenecer a
una instalación root no modificable por usuarios.

El entorno de generación reemplaza `nft` e `iptables` por funciones de registro.
Los generadores no aplican reglas, no reinician servicios ni reparan Docker. El
resultado incluye backend, configuración resuelta, selección, grants y objetos
o cadenas/reglas para ese motor. `validate`, `generate` y `plan` realizan esta
composición sin consultar el kernel; `check` compila las transacciones y hace
preflight/kernel check; `apply` pasa por el mismo preflight antes de escribir.
La CLI también puede recuperar un journal ya vencido antes de estas operaciones
privilegiadas. Ver [operación](../firewall/transactions.md) para el contrato completo,
[configuración](../configuration/README.md) para la selección efectiva y el
[índice documental](../README.md) para otras guías.

## Política y límites

La política del núcleo separa servicios de host, forwarding y contenedores.
`HOST_SERVICES`, `ROUTED_POLICY` y `CONTAINER_POLICY` son controles independientes;
por defecto forwarding es `drop` y contenedores están `off`. Los grants describen
direcciones, interfaces, protocolo y puertos; grants de contenedor incluyen IP y
puertos públicos/internos y validan DNAT. NAT por sí solo no autoriza tráfico.
`TYPECHAIN` es compatibilidad de configuración y no concede permisos sin grants.

El núcleo posee setup/finalize, loopback, controles ICMP/ICMPv6, transacciones y
registro de objetos. Los módulos de juego se seleccionan como grupo con validación,
A2S y UDP base. SourceTV se separa de login GameServer. `nftables` compara longitud
del datagrama UDP y puede aplicar política dual; `iptables` juego requiere
`FAMILY_POLICY=ipv4-block-ipv6`. Meter/hashlimit tienen capacidad limitada por
`STATE_CAPACITY` y timeouts; los registros de descarte están separados de los
presupuestos de rate limit.

Las garantías de reemplazo difieren por motor: nftables cambia las tablas propias
en una transacción; iptables confirma cada tabla/familia por separado y no garantiza
atomicidad conjunta. No se vacía el ruleset global, no se cambia política de cadenas
compartidas ni se adopta un objeto solo por su nombre. Los límites detallados de
Docker, VPN, familias y pruebas están en [capacidades](../firewall/backends.md)
y [aprobación](../security/approval.md).


## Extender o cambiar un módulo

Lee el [catálogo](modules.md) y la guía del servicio; compara metadata de ambos
motores antes de añadir una variable. Mantén ID/alias inequívocos, declara variables
requeridas/opcionales/defaults y conserva generación sin escrituras al kernel.
Si cambia la composición, revisa dependencias/conflictos y el emisor común; no
introduzcas un camino de aplicación paralelo al escritor. Código principal:
[config.py](../../core/config.py), [compiler.py](../../core/compiler.py),
[render.sh](../../core/render.sh), [record.py](../../core/record.py).

Regresión lógica y generación desde raíz, sin root:

```sh
bash tests/smoke-modules.sh
bash tests/generate.sh
```

Prueban metadata/composición/bundles, no aceptación kernel. Para nuevas reglas añade
[checks/tráfico aislado](../testing/README.md) y evidencia de paridad/familias según
[CONTRIBUTING](../../CONTRIBUTING.md). Una opción aceptada debe implementarse o
rechazarse explícitamente; no ignores configuraciones de seguridad.
