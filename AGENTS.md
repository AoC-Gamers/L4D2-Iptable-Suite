# Trabajo en L4D2 Iptable Suite

Suite Bash/Python de políticas de red con iptables y nftables nativo. El núcleo
compone, valida y aplica objetos propios; los módulos generan controles de servicios.
Lee [CONTRIBUTING](CONTRIBUTING.md) y el [índice](docs/README.md) antes de cambiar código.

## Elegir contexto

| Tarea | Código | Guías que leer |
|---|---|---|
| Configuración/selección/schema | `core/config.py`, `schema.py` | [Configuración](docs/configuration/README.md), [referencia](docs/configuration/reference.md), [migración](docs/migration/README.md) |
| Permisos/paridad/módulos | `core/compiler.py`, `render.sh`, `modules/{ip,nf}` | [Arquitectura](docs/architecture/README.md), [catálogo](docs/architecture/modules.md), guía del servicio, [motores](docs/firewall/backends.md) |
| Aplicación/lock/rollback/persistencia | `core/engine.py`, `store.py`, `fw.py`, wrappers | [Transacciones](docs/firewall/transactions.md), [persistencia](docs/firewall/persistence.md) |
| Arranque/systemd | `core/boot.py`, `systemd/` | [Arranque](docs/boot/README.md), [recuperación](docs/boot/recovery.md), [systemd/AGENTS](systemd/AGENTS.md) |
| Automatización/logs | `scripts/`, `geoip-updater/`, `log-summary/` | [Automatización](docs/automation/README.md), [observabilidad](docs/observability/README.md) |
| Pruebas | `tests/`, `tests/vm/` | [Testing](docs/testing/README.md), [tests/AGENTS](tests/AGENTS.md) |
| Documentación | `docs/<feature>/` | [docs/AGENTS](docs/AGENTS.md), [mapa](docs/migration/documentation-map.md) |

## Invariantes

- No apliques reglas sobre el firewall que sostiene el acceso al entorno ni vacíes
  tablas/reglas globales. No adoptes objetos por nombre ni modifiques objetos ajenos.
- No reinicies Docker, red, SSH, VPN u otros servicios anfitriones para validar.
  Pruebas privilegiadas y de reinicio solo en entorno aislado y desechable autorizado.
- Conserva escritor/bloqueo comunes, preflight, journal, confirmación y rollback.
  Los módulos generan; no reparan servicios ni aplican fragmentos por fuera del núcleo.
- No debilites confianza/propiedad, ACL o aserciones para obtener PASS. Verifica
  que tests y expectativas representen la política efectiva, también con tráfico.
- No abras, cambies ni versiones `.env` privado, secretos, tokens o capturas de terceros
  sin necesidad y autorización específica. Usa ejemplos versionados ficticios.
- Guardar política no activa barrera de arranque. Aceptar versión no autoriza migrar
  frontend. No extrapoles la aprobación de un commit a otros o a un despliegue.

## Validación ordinaria

Desde raíz del checkout, **sin root**, Bash y Python 3.10+:

```sh
git diff --check
python3 -I tests/check_docs.py
python3 -I tests/test_docs.py
bash tests/smoke-modules.sh
bash tests/generate.sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./iptables.rules.sh validate --env-file config/profiles/web.conf
```

Lógica/mocks y generación no consultan Netfilter; usa archivo explícito para evitar
el `.env` implícito. No invoques wrappers de motor sin operación: aplican por defecto.
Las pruebas de motor/tráfico requieren [aislamiento](docs/testing/README.md); el
[runner QEMU](docs/testing/vm.md) requiere dependencias/red y crea su guest sin root
anfitrión. No ejecutes helpers privilegiados directamente en host ni contabilices SKIP
como PASS. `status`, `doctor` y `check` pueden recuperar journal vencido; para lectura
pasiva privilegiada existe `diagnose`.

## Cambios y entrega

Inspecciona rama/HEAD, instrucciones locales y diff antes de editar; conserva trabajo
ajeno e ignorados. Usa rama dedicada y commits coherentes, separando documentación
y comportamiento. Actualiza guías canónicas/configuración/evidencia según el cambio;
no reescribas resultados históricos. No publiques ni mezcles sin instrucción.
Reporta commit, entorno/versiones, comandos, qué capa probaste, resultado y límites;
indica explícitamente pruebas no ejecutadas y motivo. Una nueva función requiere
regresión adecuada y revisión de paridad/familias/propiedad/recuperación afectadas.
