# Validación y evidencia

Prueba cada capa por separado. Un mock no demuestra aceptación por el kernel ni
tráfico; una candidata aceptada no demuestra conectividad. Las pruebas privilegiadas
solo se autorizan dentro de VM/namespace desechable; nunca contra la red del host.

Desde raíz del checkout, usuario sin root, estos comandos ejecutan lógica/mocks y
generación sin tocar Netfilter:

```sh
bash tests/smoke-modules.sh
bash tests/generate.sh
python3 -I tests/test_docker_topology.py
python3 -I tests/test_h2.py
python3 -I tests/test_boot.py
```

`smoke-modules.sh` es una selección útil, no toda la suite de CI. Las clases
adicionales están en [workflows](../../.github/workflows/); consulta también
[CONTRIBUTING](../../CONTRIBUTING.md). Sintaxis Bash/ShellCheck y Python no prueban
kernel ni política. Documentación se verifica con `python3 -I tests/check_docs.py`.

| Capa | Cómo y qué acredita |
|---|---|
| Estática/lint | Diff, Bash, ShellCheck, Python; referencias y sintaxis |
| Unitaria/mocks | `tests/test_*.py`, arneses VM y scripts lógicos; contratos simulados |
| Generación | `tests/generate.sh`; perfiles/bundles, sin motor |
| Kernel | `tests/isolated-run.sh tests/check-engine.py`; candidatas reales, requiere herramientas/capacidades dentro de aislamiento |
| Tráfico/regresiones | `integration.py`, `transaction-flows.py`, `policy-flows.py`, `docker-topology-flows.py`, `h2-flows.py`, `boot-flows.py`, siempre con wrapper aislado |
| VM completa | [Runner](vm.md), [clientes](clients.md), [Docker](docker.md), [transacciones](transactions.md), [H3](boot.md): kernel propio, servicios de prueba y cuatro reboots |
| Destino | Configuración/topología/versiones/consumidores reales; pendiente de cada despliegue |

`isolated-run.sh` comprueba que el netns difiera del anfitrión y monta `/run`
privado para xtables.lock. El modo usuario requiere soporte de user namespaces;
`--root-net` corresponde solo a root **dentro de VM/contenedor desechable**. No
sustituyas un fallo de permisos por ejecutar tests directamente como root en host.
El [runner VM](vm.md) evita esa dependencia del host y también descarga dependencias.

CI separa unidades, generación, kernel, tráfico y QEMU. La matriz obligatoria falla
ante dependencias ausentes o códigos no cero, incluido 77: nunca SKIP=PASS.
Una combinación no soportada se rechaza/excluye expresamente del contrato, no
acredita compatibilidad. Informa versión/commit/comando/aislamiento/resultados y
pruebas no ejecutadas. Evidencia fechada: [aprobación](../security/approval.md) y
[límites](../security/limitations.md). Diagnóstico pasivo: [guía](diagnostics.md).

## Runtime de las acciones de CI

Los dos workflows usan acciones JavaScript con Node 24, fijadas por SHA:
[checkout v7.0.1](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml)
y [upload-artifact v7.0.2](https://github.com/actions/upload-artifact/blob/cf430e030ddbb5b0abf93d22962f4752f3646cd9/action.yml).
Node ejecuta esas acciones; el producto y los ensayos siguen usando Bash/Python
y los motores de Netfilter. No se necesita `setup-node` para elegir ese runtime.
Según [checkout](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/README.md),
Node 24 requiere Actions Runner 2.327.1 o posterior; los workflows seleccionan
el runner alojado `ubuntu-24.04`. Revisar el requisito al cambiar de runner.

La subida conserva `archive: true`, nombre `qemu-validation-logs`, directorio de
logs saneados, error si faltan archivos y retención de 14 días. Al actualizar
las acciones, comprobar tag/SHA y metadata oficial, validar workflows con
Actionlint y observar el CI remoto del commit nuevo. El lint local no demuestra
que se hayan ejecutado las acciones ni el guest QEMU.

## Regresiones conservadas

Los informes retirados describían estos defectos corregidos. Se mantienen sus
pruebas y los contratos actuales, sin duplicar diarios de auditoría ni atribuir
una ejecución nueva a las pruebas por el mero hecho de enlazarlas:

| IDs históricos | Contrato y regresión |
|---|---|
| CFG-01 | Selección CLI vacía explícita elige solo núcleo: [configuración](../configuration/profiles.md), [test_configuration_audit.py](../../tests/test_configuration_audit.py). |
| CFG-02 | GeoIP Compose usa UID/GID propietario del checkout: [guía](../automation/geoip.md), [test_configuration_audit.py](../../tests/test_configuration_audit.py); ejecución completa offline en [clientes](clients.md). |
| CFG-03 | Watcher bloquea antes de observar WAN/DDNS/estado: [guía](../automation/public-ip-watch.md), [watcher-audit.sh](../../tests/watcher-audit.sh), dos procesos con respuestas simuladas. |
| TX-01, TX-04 | Disable sin Docker y carga con ausencia total de objetos propios: [persistencia](../firewall/persistence.md), [transaction-flows.py](../../tests/transaction-flows.py). Objetos parcialmente presentes/hooks desplazados no se reparan silenciosamente. |
| TX-02 | Remove consume ACL nueva explícita y conserva la confirmada en su ausencia: [persistencia](../firewall/persistence.md), [test_transactions.py](../../tests/test_transactions.py). |
| TX-03, TX-05 | Presupuesto monotónico por comando y fallo del watchdog antes de escribir: [transacciones](../firewall/transactions.md), [test_transactions.py](../../tests/test_transactions.py). No se reproduce un bloqueo permanente del kernel. |
| POL-01 | Capacidad efectiva de hashlimit, tamaño/máximo y expiración: [configuración](../configuration/README.md), [test_policy_audit.py](../../tests/test_policy_audit.py), [policy-flows.py](../../tests/policy-flows.py). El escenario de capacidad usa 24 orígenes y un límite de 16; no es carga prolongada. |
| HAR-01 | Red y `/run/xtables.lock` privados antes de invocar motores: [isolated-run.sh](../../tests/isolated-run.sh); un netns por sí solo no aísla ese archivo. |
| H1–H3 | Recorrido Docker, estado canónico y barrera/readiness: [aprobación](../security/approval.md), [Docker](docker.md), [transacciones VM](transactions.md), [arranque VM](boot.md), [test_docker_topology.py](../../tests/test_docker_topology.py), [test_h2.py](../../tests/test_h2.py), [test_boot.py](../../tests/test_boot.py). |

Estos enlaces no ejecutan pruebas. Los scripts de kernel/tráfico de la tabla
requieren el aislamiento descrito arriba; nunca se invocan directamente con root
en el anfitrión. Las cantidades históricas pertenecen al commit y run registrados
en la aprobación, no al HEAD de un cambio documental.
