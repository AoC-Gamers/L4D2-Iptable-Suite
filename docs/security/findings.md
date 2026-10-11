# Matriz inicial — 2026-10-11

Revisión directa: main limpio, aeabda7cbba25ecd94629797f5637a9a6987c147.
Rama de implementación: security/modular-safe-apply. No hay AGENTS.md aplicable.

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
La matriz final y versiones se completan tras implementar y ejecutar las pruebas.
