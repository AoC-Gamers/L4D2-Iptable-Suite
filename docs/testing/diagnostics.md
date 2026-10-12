# Revisión de compatibilidad asistida: Docker y Netfilter

Usa este procedimiento para recopilar evidencia antes de recomendar un backend.
Una auditoría no autoriza cambios. No ejecutes `apply`, `disable`, `load`,
`confirm`, `rollback`, instalaciones ni reinicios. Una excepción importante:
`status`, `doctor` y `check` pueden primero recuperar un journal de aplicación
vencido; si se requiere una observación estrictamente pasiva, limita la revisión
a los comandos de lectura del sistema y a `validate`/`plan` sin privilegios.
Consulta el [índice de documentación](../README.md) y la
[referencia de configuración](../configuration/README.md) antes de interpretar una candidata.

## Evidencia local sin privilegios

Desde el repositorio, describe el código y genera la configuración objetivo sin
consultar ni cambiar el firewall:

```sh
git status --short --branch
git rev-parse --short HEAD
./nftables.rules.sh validate --env-file /ruta/config.conf
./nftables.rules.sh generate --env-file /ruta/config.conf > /tmp/candidate.json
./nftables.rules.sh plan --env-file /ruta/config.conf --against /ruta/previous.json
bash tests/smoke-modules.sh
```

Repite la composición con `iptables.rules.sh` si se evalúa ese backend. `validate`
y `generate` no acceden al kernel; `plan` compara políticas generadas, no prueba
el kernel ni el tráfico. `smoke-modules.sh` ejecuta pruebas lógicas y no aplica
reglas. Mantén la salida candidata en una ubicación privada si revela configuración.

## Lectura del host

Con autorización operativa y privilegios apropiados, recoge sin alterar estado:

```sh
uname -a
cat /etc/os-release
docker --version
nft --version
iptables --version
ip6tables --version
sudo nft list ruleset
sudo iptables-save
sudo ip6tables-save
```

No hace falta `sudo` para un binario ausente: regístralo como faltante. La suite
no cambia alternativas de iptables. Si el backend depende de iptables, comprueba
qué frontend usa Docker y qué frontend será seleccionado (`IPTABLES_FRONTEND`);
no infieras integración por la sola presencia de `DOCKER-USER` o por el nombre de
una tabla. `doctor` es útil para inspeccionar versiones y objetos reconocidos,
pero requiere root y puede recuperar una transacción vencida.

## Pruebas de motor y tráfico

`check` requiere root/capacidades de Netfilter y comprueba una candidata contra
el estado del motor, sin aplicarla salvo posible recuperación de un journal vencido.
Para parser de kernel o tráfico real utiliza únicamente la prueba aislada, que
crea namespaces de usuario, red y montaje y un `/run` privado:

```sh
bash tests/isolated-run.sh
```

Si no se permiten namespaces, marca la prueba como omitida con el motivo; no
ejecutes estas pruebas contra el namespace de red del host ni uses un `dry-run`
privilegiado como sustituto. La prueba aislada valida el kernel local disponible,
pero no demuestra compatibilidad del Docker daemon de producción ni conectividad
desde clientes reales. Para esos casos consulta las [capacidades y combinaciones
probadas](../firewall/backends.md) y su evidencia en
[resultados históricos](../archive/audits/2026-10-11-results.md).

## Criterios y formato de informe

Separa claramente: herramientas/versiones observadas; motor y frontend efectivos;
reglas y cadenas previas relevantes; resultado de composición; resultado de
check/prueba aislada; limitaciones no cubiertas. Recomienda un backend solo si
coincide con la integración Docker observada y la combinación consta como probada.
Marca `NO-GO` si la configuración no genera, el preflight falla, objetos externos
entran en conflicto, o la política candidata cortaría rutas que el operador necesita.
La ausencia de un test real no es un PASS.

```json
{
  "host": {"os": "...", "docker": "version|missing", "nft": "version|missing", "iptables": "version|missing"},
  "checks": [
    {"id": "policy-generation", "status": "PASS|FAIL|SKIPPED", "evidence": "..."},
    {"id": "existing-firewall", "status": "PASS|WARN|FAIL|SKIPPED", "evidence": "..."},
    {"id": "isolated-kernel-test", "status": "PASS|FAIL|SKIPPED", "evidence": "..."},
    {"id": "docker-combination", "status": "PASS|WARN|SKIPPED", "evidence": "..."}
  ],
  "recommended_backend": "iptables|nftables|none",
  "go_live": "GO|NO-GO|NOT-ASSESSED",
  "actions": ["..."]
}
```

Un veredicto `GO` es solo una recomendación de compatibilidad y no despliega la
política. La aplicación productiva requiere revisión humana del plan, acceso de
consola y confirmación tras probar una conexión administrativa nueva. Consulta
[flujo transaccional](../firewall/transactions.md) y
[migración](../migration/README.md).
