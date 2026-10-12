# Contribuir

Lee [AGENTS](AGENTS.md), [arquitectura](docs/architecture/README.md) y la guía de la
funcionalidad afectada. Bash y Python 3.10+ bastan para la composición lógica;
ShellCheck es necesario para lint shell. Motor/tráfico necesitan Netfilter y
herramientas de aislamiento; [VM](docs/testing/vm.md) lista las dependencias QEMU.
No se proporciona un instalador general de dependencias del host.

## Ramas y alcance

Parte de una revisión identificada de `main`, inspecciona `git status`/HEAD y usa
rama dedicada. Preserva cambios locales/ignorados. Commits deben explicar problema,
cambio y validación; separa ajustes documentales de funcionales. No mezcles/push sin
instrucción. No cambies valores efectivos de ejemplos durante una reorganización de textos.

Actualiza la guía canónica cuando cambien opciones/defaults/permisos/operación y
registra incompatibilidades en [migración](docs/migration/README.md). Una nueva
aprobación necesita evidencia de ese código; los informes históricos se conservan.
Reglas de estilo/enlaces: [docs/AGENTS](docs/AGENTS.md).

## Elegir pruebas

Desde raíz, sin root, para documentación:

```sh
git diff --check
python3 -I tests/check_docs.py
python3 -I tests/test_docs.py
```

Para cambios de composición o generación (lógica/mocks, no kernel):

```sh
bash tests/smoke-modules.sh
bash tests/generate.sh
```

Añade las regresiones del área: configuración `test_configuration_audit.py`/`test_h2.py`,
política `test_policy_audit.py`, transacciones `test_transactions.py`, topología
`test_docker_topology.py`, arranque `test_boot.py`, arneses `tests/vm/test_*.py`.
Se invocan `python3 -I tests/NOMBRE.py`, con un nombre real, sin root.
No sustituyas regresiones funcionales por expectativas que reproduzcan un fallo.

Para sintaxis/lint shell, desde raíz y sin root (ShellCheck instalado):

```sh
git ls-files -z -- '*.sh' ':(exclude)log-summary/venv.loggin.sh' | xargs -0 shellcheck -x
git ls-files -z '*.sh' | xargs -0 -n1 bash -n
```

La exclusión venv es la existente en CI; no amplíes exclusiones para forzar éxito.
Ejecuta controles pertinentes Python y revisa workflows según el cambio. Los jobs
versionados enumeran la matriz obligatoria; un smoke local no equivale a todo CI.
Para reglas/propiedad/rollback/Docker/systemd añade [motor y tráfico aislado](docs/testing/README.md)
y [VM/reboots](docs/testing/vm.md), con autorización y recursos desechables.
Nunca ejecutes pruebas con root en la red anfitriona ni reinicies sus servicios.

## Propuesta revisable

Incluye commit base, problema/reproducción mínima ficticia, comportamiento antes/después,
archivos/guías afectados, opciones incompatibles/migración, pruebas con entorno y
versiones, evidencia por capa y pruebas no realizadas con motivo/riesgo residual.
Conserva secretos y logs sin sanear fuera de Git; [SECURITY](SECURITY.md) delimita
los canales de reporte. No prometas seguridad por la sola salida exitosa de scripts.
