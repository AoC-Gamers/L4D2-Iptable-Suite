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
[archivo](../archive/audits/README.md). Diagnóstico pasivo: [guía](diagnostics.md).
