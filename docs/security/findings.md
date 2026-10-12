# Matriz inicial — 2026-10-11

Revisión histórica directa: `main` limpio en aeabda7cbba25ecd94629797f5637a9a6987c147.
Rama de implementación: security/modular-safe-apply. No hay AGENTS.md aplicable.

Los estados de esta primera tabla corresponden a esa base, no al código actual.
La [matriz final](#matriz-final) registra las soluciones; el
[estado operativo](../operational-audit.md) y los [resultados](results.md)
distinguen implementación, evidencia posterior y pendientes.

| ID | Estado inicial | Evidencia y consecuencia | Solución prevista | Regresión |
|---|---|---|---|---|
| A1 | Confirmado | ip_chain_setup: políticas ACCEPT, flush global, restart Docker; nf_chain_setup: delete antes de add. Pérdida de reglas/ventanas parciales. | Candidata completa, propiedad, transacciones por motor. | Fallo previo sin cambios; reglas ajenas; idempotencia. |
| A2 | Confirmado | entrypoints, ipp y watcher sin bloqueo común ni rollback independiente. | Escritor único, lock, journal y watchdog separado. | Concurrencia, kill, timeout, confirmación. |
| A3 | Confirmado | common_loader selecciona todo con lista vacía; preload comprueba conflictos sobre lista literal. | Perfiles mínimos, conjunto efectivo, dependencias y núcleo automático. | Typos, vacío, conflicto tras exclusiones. |
| A4 | Confirmado | dry-run llama validate sin generar apply. | Validar/generar/plan/check separados. | Comparar candidata revisada y aplicada. |
| B1 | Confirmado | established temprano en ambos setup; UDP base acepta antes de packet_validation/A2S. | Validación → clasificación → límites → aceptación; established auxiliar después. | UDP bidireccional y contadores; A2S/TV. |
| B2 | Parcialmente confirmado | nf SSH global; logs con rate over en SSH/web/packet_validation. IP SSH ya usa hashlimit por origen. | Meters limitados por familia y logs bajo umbral; drops independientes. | Dos orígenes; carga sostenida. |
| B3 | Confirmado | ipp borra rules.v6; meters nf IPv4 dentro de inet. ICMPv6 parcialmente presente en núcleo nf. | Familia explícita; equivalencia o rechazo; ICMP núcleo. | Web/SSH/forward v4/v6; persistencia ajena. |
| B4 | Confirmado | TYPECHAIN controla rutas de módulos VPN y servicios; finalize IP DROP FORWARD incluso host. | Separar host, Docker y rutas explícitas. | Gateway nativo sin Docker. |
| B5 | Confirmado | whitelist y VPN aceptan subredes completas a INPUT; DNS validado solo con regex. | Grants por servicio, bypass explícito, DNS cerrado ante fallo. | Puertos/redes no autorizados bloqueados. |
| C1 | Confirmado | nf OpenVPN server omite NAT/DNAT/interfaz; SSH_DOCKER ignorado; web forward sin TCP. | Paridad, opciones rechazadas si faltan, protocolo y DNAT explícitos. | TCP/UDP coincidente, remapeo, opciones. |
| C2 | Confirmado | Se presupone DOCKER-USER y se crea/reinicia Docker. | Diagnóstico de motores y puntos de integración. | Chains ausentes sin cambios; remapeo aislado. |
| D1 | Confirmado | ipp reemplaza nftables.conf, limpieza global y nombres codificados. | Persistencia propia y registro de objetos. | Guardar/cargar/desactivar selectivo. |
| D2 | Confirmado | preload ejecuta .env; loader source antes de selección; validaciones incompletas. | Parser declarativo, metadata sin ejecución, trust de rutas. | Inyección, permisos, módulo deshabilitado. |
| D3 | Confirmado | Core especializado L4D2, sin perfiles. | Núcleo general incremental y perfiles combinables. | Web sin variables juego/VPN. |
| E | Confirmado | Smoke omite engine si falta root/dependencia y puede salir 0. HTTP tests solo captura strings. | Jobs visibles y pruebas reales aisladas obligatorias. | Falta de dependencia falla; tráfico real. |
| Meters | Ya corregido | UDP/A2S nf tienen timeout 5s; login 1s. | Conservar y cubrir expiración/capacidad. | Generación/engine. |
| SourceTV | Ya corregido parcialmente | FFFFFFFF71 solo deriva a login en GameServer. Sigue sujeto a orden global incorrecto. | Conservar distinción al corregir recorrido. | Handshake corto TV real sintético. |

La evidencia de tráfico sintético no demuestra compatibilidad de todos los clientes reales de L4D2.
La matriz siguiente registra la implementación final. Versiones, comandos y
limitaciones de aceptación están en [results.md](results.md).

## Matriz final

Estados de la revisión inicial: confirmados, parcialmente confirmados y ya
corregidos aparecen arriba. No se inventó un hallazgo "no reproducible" para
rellenar la categoría; las compatibilidades que faltan demostrar se indican como
pendientes de pruebas, no como problemas corregidos por suposición.

| ID / consecuencia confirmada | Archivos principales | Solución implementada | Regresión / nivel de evidencia |
|---|---|---|---|
| A1: flush/restart y configuración parcial | `core/{compiler,engine,store}.py`, entrypoints, `modules/{ip,nf}_chain_setup.sh` | Generación previa, validadores seleccionados antes de generar, check de todas las candidatas, reemplazo exclusivo de propios; nft transacción única; IP restore noflush por tabla/familia | Kernel10; integración01/02/07/12/17. Sin atomicidad global IP |
| A2: escritores paralelos y pérdida de acceso | `core/store.py`, `core/fw.py`, watcher/Makefile | Flock común, journal fsync, snapshot sólo propios, watchdog armado antes de escribir, token y conexión nueva, deadline monotónico/boot | Integración05/06/07/09/12/16; watchdog separado real; timer systemd de producción y SSH nuevo probados en VM; ver vm-transactions |
| A3: lista vacía activa módulos incompatibles | `core/config.py`, perfiles | Mínimo seguro, aliases estrictos, conjunto efectivo, dependencias y core obligatorio; parcial sólo con grafo existente | Unitarias; integración01/08/15 |
| A4: dry-run no representa reglas | `core/fw.py`, `core/compiler.py`, `core/render.sh` | Validate/generate/plan/check/apply separados; plan concreto y diff contra bundle | Generación8, kernel10; mensajes distinguen lógica/kernel/tráfico |
| B1: ACCEPT vuelve controles inalcanzables | `core/compiler.py`, módulos UDP/validación/A2S | Validación → clasificadores → límites → aceptación; established auxiliar después; controles por publicación | Integración04/13, UDP de ida/vuelta real v4/v6 según motor |
| B2: logs excedentes y SSH global | `modules/nf/nf_40_tcp_ssh.sh`, `core/{config,compiler}.py`, módulos web | SSH por origen/puerto/familia; logs limitados con descarte independiente; capacidad y timeout que cubre recarga del bucket | Integración03; unitarias de duración; carga prolongada/capacidad total pendiente |
| B3: reglas v6 borradas / protección desigual | `core/config.py`, `core/compiler.py`, `ipp.sh` | Familia explícita; ICMP/ICMPv6/ND núcleo; nf dual; IP juego exige decisión de bloqueo v6 sin deshabilitar stack; persistencia propia | Integración02/04/10/11, kernel10; clientes/PMTU representativos pendientes |
| B4: TYPECHAIN mezcla host y gateway | `core/{config,compiler}.py`, grants/perfiles | Host/contenedor/routing independientes; traducción sólo no ambigua; permisos direccionales | Integración10/14 sin Docker, dual pila |
| B5: VPN/whitelist conceden todo | VPN/whitelist metadata, `core/{config,compiler}.py` | NAT sin permisos; grants origen/destino/interfaces/protocolo/servicio; bypass host explícito; DNS limitado y fallo cerrado | Integración10/14; DNS unitario con fallos inyectados; whitelist DNS real pendiente |
| C1: opciones silenciosas / protocolo y DNAT | `core/{config,compiler}.py`, módulos HTTP/A2S | NAT/alias/SNAT compartidos; SSH_DOCKER y adaptaciones inseguras rechazan; tuple pública/interna; TCP/UDP separados; offsets IPv4 de carga exactos | Kernel VPN; integración04/11/13/14. S2S/alias con OpenVPN real probados en VM; NAT de servidor con tráfico, SNAT S2S sólo candidata kernel |
| C2: presupone Docker / reinicios | `core/engine.py` | Diagnóstico de frontend y objetos Docker; puntos de integración existentes, rechazo de combinaciones ambiguas, sin reparar servicios | Integración11/17 con topologías; daemon Docker real en cinco combinaciones y matriz legacy completa probados en VM |
| D1: persistencia/limpieza global | `core/{engine,store,fw}.py`, `ipp.sh`, unidad propia | Registro generado, nombres configurables, save/load/disable/remove sólo propios; ningún archivo sistema sobrescrito | Integración02/08/12/17; reboot: resultado detallado en vm-transactions.md |
| D2: .env ejecutable y source anticipado | `core/{config,fw,read_config}.py`, render, updater/watcher | Config declarativa sin eval/source, trust antes de importar código privilegiado, metadata literal, tipos completos, datos GeoIP y rutas acotadas | Unitarias de inyección/metadata/tipos/GeoIP; integración01/15 |
| D3: núcleo especializado / perfiles | `core/`, módulos existentes, `config/profiles/` | Núcleo operacional general incremental; preserva generadores de servicios y entrypoints; perfiles combinables | Generación8/kernel10; web dual sin VPN/juego en integración02 |
| E: omisiones verdes / mocks confundidos con kernel | `.github/workflows/{smoke-modules,vm}.yml`, `tests/` | Jobs separados, dependencias obligatorias y VM QEMU propia; fallos sin skip | 39 unitarias producto + 2 harness + 13 runner; generación8, kernel20, integración/regresión46; Docker/clientes/reboot VM. Estado CI remoto registrado aparte |
| Expiración / SourceTV parcialmente corregidos antes | módulos A2S/UDP, compilador | Conserva expiración y distinción GameServer/TV; añade tamaño/capacidad, deriva lifetime suficiente para rellenar tokens (login default efectivo4s) | Unitarias e integración04/13. No se restablecieron bypass established anteriores |

Los detalles de permisos, incompatibilidades deliberadas y migración están en
[capabilities.md](capabilities.md), [migration.md](migration.md) y
[operations.md](operations.md). Las limitaciones de pruebas no se ocultan como
hallazgos resueltos.

La evidencia ampliada en VM, sus versiones y las limitaciones actuales están en
[results.md](results.md). Los totales iniciales se conservan como históricos; la
continuación añade 20 comprobaciones de motor y 46 casos en matriz nft/legacy.
