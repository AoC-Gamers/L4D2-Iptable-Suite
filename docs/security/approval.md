# Aprobación con observaciones — 12 de octubre de 2026

> Aprobado con observaciones dentro del alcance implementado y probado.
> La aceptación operativa de cada despliegue requiere validar su configuración,
> versiones, servicios e integración de arranque.

Decisión de cierre técnico del alcance revisado, no certificación externa.
**Commit aprobado:** `93096dea2d7854a4d580a0b4922d5d1426c8149e`.
Los cambios documentales posteriores no reciben automáticamente una nueva
aceptación funcional. No se hizo una nueva auditoría de seguridad al reorganizar.

## Cierre H1–H3

| Hallazgo | Estado dentro del alcance | Código y regresiones |
|---|---|---|
| H1: ruta efectiva Docker | Implementado/probado: preflight estructural por familia exige FORWARD→DOCKER-USER primero, único, incondicional, y hook propio primero; rechaza sin mover reglas externas | [engine.py](../../core/engine.py), [diagnose en fw.py](../../core/fw.py), [unitarios](../../tests/test_docker_topology.py), [tráfico](../../tests/docker-topology-flows.py) |
| H2: normalización y estado | Implementado/probado: traducción TYPECHAIN solo input, schema 2, migración en memoria, ACL parseada durable, partial/remove sin reinterpretar ni reabrir rutas | [config.py](../../core/config.py), [schema.py](../../core/schema.py), [store.py](../../core/store.py), [unitarios](../../tests/test_h2.py), [ciclo real](../../tests/h2-flows.py) |
| H3: arranque comprobado | Implementado/probado con integración opt-in: barrera independiente, boot ID/digest/fingerprint y readiness antes de consumidores; restore fallido conserva guard | [boot.py](../../core/boot.py), [unidades](../../systemd/), [unitarios](../../tests/test_boot.py), [tráfico guard](../../tests/boot-flows.py), [VM H3](../../tests/vm/closure_boot.py) |

El [informe histórico H1–H3](../archive/audits/h1-h3-plan-results.md) conserva la
corrida local `20261012T053512Z-f950c62d` sobre `0d20286` y sus **178** sondas.
No se la presenta como prueba directa del commit aprobado. Después se corrigieron
presupuestos temporales del arnés (`72f8371`) y acceso KVM del runner CI (`93096de`);
por ello se registra por separado la siguiente ejecución del commit exacto.

## Evidencia del commit exacto

Reconsulta de API GitHub: **2026-10-12**, ambos runs `head_sha=93096dea…`,
`conclusion=success`:

- [Firewall validation, run 38214356935](https://github.com/AoC-Gamers/L4D2-Iptable-Suite/actions/runs/38214356935), terminado `2026-10-12T06:52:42Z`.
- [Disposable QEMU validation, run 38214356944](https://github.com/AoC-Gamers/L4D2-Iptable-Suite/actions/runs/38214356944), terminado `2026-10-12T07:04:50Z`.

El runner QEMU reportó salida satisfactoria completa a `07:04:46Z`, run-id
`20261012T064855Z-02d23fec`, sin SKIP aceptado. Artifact `qemu-validation-logs`
no estaba expirado al verificar; fecha de expiración anunciada `2026-10-26T07:04:46Z`.
Los enlaces a runs conservan metadata; **no garantizan retención de logs** después
de expirar el artifact. Si ya no está disponible, reproducir con el runner y
registrar nueva evidencia, sin inventar el contenido perdido.

| Capa | Resultado y límite |
|---|---|
| Revisión estática | Sintaxis Bash, Python y ShellCheck en CI aprobados; no prueban kernel/tráfico |
| Unitarios/mocks | 118 casos Python (103 guest + 15 runner anfitrión), incluyendo contratos del producto y arneses; no equivalen a 118 sesiones de tráfico |
| Generación | Candidatas de perfiles/servicios aprobadas sin privilegios; sin prometer conectividad |
| Comprobación motor | 20 comprobaciones kernel, diez por frontend; incluye variantes NAT/S2S cuya comprobación no acredita todos sus flujos |
| Tráfico aislado | 58 métodos de integración/regresión kernel, incluidos subcasos; SSH/web v4/v6, UDP establecido/A2S/TV sintéticos, independencia TCP/UDP, rollback/concurrencia/conservación |
| Daemons/clientes reales | Cinco combinaciones Docker en régimen normal, OpenVPN TLS y actualizador GeoIP con ZIP sintético offline; no cliente L4D2/SourceTV real ni base MaxMind actual |
| VM/systemd/reboots | Timer de producción, SIGKILL, abandono de sesión, conexión SSH nueva; dos reboots TX y dos H3 (cuatro total), persistencia válida/inválida, socket y Docker live-restore |
| Destino | No se validó cada configuración productiva; queda aceptación operativa por despliegue |

Entorno QEMU/KVM: Ubuntu Noble imagen `20260926`, kernel guest
`6.8.0-142-generic`, systemd `255.4-1ubuntu8.17`, Python 3.12, nftables 1.0.9,
iptables/ip6tables 1.8.10 (nft y legacy), OpenVPN 2.6.19, Docker 29.8.2.
Hashes fijados de imagen/Docker y reproducción: [runner VM](../testing/vm.md)
y [informe histórico](../archive/audits/h1-h3-plan-results.md). Se ejecutó KVM;
no se acredita con este run una matriz final completa TCG.

H3 midió **354 intentos externos: 177 TCP y 177 UDP**, cero respuestas de aplicación
no autorizadas. Gaps máximos entre inicios: TCP `0.952676718 s`, UDP `0.952838911 s`.
La regla de cobertura exige ≤3 s, con controles positivos. No descarta ventanas
arbitrariamente breves ni certifica tráfico externo IPv6 durante reboots.
La combinación de arranque H3 fue **suite nftables + Docker iptables/frontend nft**;
las otras cuatro combinaciones solo tienen la evidencia Docker normal.

## Condiciones y nueva revisión

Lee [limitaciones vigentes](limitations.md) antes de aceptar un destino. En especial:
opt-in de barrera/unidades y consumidores, orden real de Docker/ExecStop, conservación
frente a escritores externos, atomicidad parcial iptables, B01/B02 solo unitarios,
clientes reales de juego, PMTU/variantes VPN y carga sostenida pendientes.

Cambios de reglas, defaults, ACL, composición, schema, ownership, motor/frontend,
versiones, watchdog/rollback, unidades/orden de arranque, topología o servicios
requieren reevaluar el alcance afectado. `--accept-version-change` registra una
decisión explícita de mantenimiento; no sustituye pruebas ni migra frontend.
Equivalencia documental se revisa aparte mediante diff y checks; no vuelve a
etiquetar un run histórico como ejecución de otro HEAD.
