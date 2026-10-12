# Resumen ligero, informes y entorno Python

La pila opcional consume eventos del log; no configura el firewall ni expone API
HTTP. `fw_log_summary.py` genera resumen JSON/TXT y estado; `iptable.loggin.py`
genera informes detallados por IP/puerto/día/semana/mes/tipo. El segundo conserva
menú de administración rsyslog/permisos: esas acciones son mutaciones privilegiadas,
no parte de un análisis pasivo. Esta guía integra el contenido vigente de los
manuales anteriores de análisis y venv.

## Configuración y privacidad

Fuente canónica: [log-summary/.env.example](../../log-summary/.env.example).
Es independiente del KEY=VALUE del firewall. El Compose vigente también declara
`../.env` como `env_file` de ambos servicios: necesita ese archivo raíz y pasa sus
variables al contenedor, aunque el parser del firewall no acepte claves de logging.
Revisa ese alcance de exposición antes de usarlo; no almacenes credenciales ajenas
al análisis allí. No se cambió este comportamiento en la reorganización documental; queda registrado
como [F-DOC-02](../security/limitations.md#incidencias-funcionales-pendientes).
El mount de logs es de solo lectura y `./output` se escribe desde el contenedor.

| Variable | Ejemplo declarado | Alcance |
|---|---|---|
| `SUMMARY_LOG_MOUNT_DIR`, `SUMMARY_LOG_PATH` | `/var/log`, `/var/log/firewall-suite.log` | Directorio host montado y archivo con misma ruta dentro; acceso real depende de permisos/ACL/rotación |
| `SUMMARY_OUTPUT_DIR` | `/output/summary` | En host: `log-summary/output/summary/` |
| `SUMMARY_TOP_N`, `SUMMARY_WINDOW_MINUTES` | `20`, `60` | Rankings y ventana; 0 minutos analiza archivo completo |
| `SUMMARY_POLL_SECONDS`, `SUMMARY_RUN_MODE` | `60`, `loop` | Intervalo y modo loop/once |
| `SUMMARY_STATUS_PATH` | `/output/summary/summary.status.json` | JSON usado por healthcheck |
| `SUMMARY_HEALTHCHECK_MAX_EMPTY_CYCLES` | `10` | Healthcheck falla si ciclos vacíos exceden umbral; no demuestra ataque ni fallo del firewall |
| `REPORTS_OUTPUT_DIR`, `REPORTS_ANALYSIS_TYPE` | `/output/reports`, `all` | Informes del servicio log-reports |

Son valores del ejemplo Compose; defaults internos sin entorno pueden diferir:
`fw_log_summary.py` usa `/output` si falta `SUMMARY_OUTPUT_DIR`. No garantices rutas
sin revisar la configuración resuelta. Trata salidas como datos sensibles y aplica
retención/permisos apropiados. No uses lectura pública `chmod 644` para reparar un log.

## Contenedores

En un checkout dedicado a análisis, desde raíz, sin root pero con acceso autorizado
al daemon Docker (privilegio equivalente a administración), este comando crea un
archivo nuevo; omítelo si ya existe y conserva la configuración privada:

```sh
cp log-summary/.env.example log-summary/.env
```

Adapta el archivo y los permisos de lectura del log. Desde `log-summary/`,
`config --quiet` comprueba Compose sin mostrar valores; `up` construye/inicia dos
servicios y escribe informes, **no es diagnóstico pasivo**:

```sh
cd log-summary
docker compose config --quiet
docker compose up -d --build
```

No ejecutes ese inicio como prueba documental en el anfitrión. Para una muestra
única sin servicio continuo, desde el mismo directorio, `run` inicia contenedor,
lee el log y escribe salidas (no modifica Netfilter):

```sh
docker compose run --rm -e SUMMARY_RUN_MODE=once log-summary
```

Comprueba `output/summary/summary.latest.json`, `.txt` y `summary.status.json`, y
`output/reports/` para informes detallados, según las rutas configuradas. Un archivo
vacío/inexistente, falta de FW_EVT o ventana sin eventos pueden producir ciclos
vacíos; no los interpretes como ausencia de bloqueo. El parser reconoce claves
largas (`backend/module/chain/action/severity`) y compactas (`be/mod/ch/act/sev`).

Para parar **solo esta pila** desde `log-summary/`, con el mismo permiso Docker:

```sh
docker compose down
```

Retira los contenedores/red Compose de esta pila; no borra archivos bind-mounted
ni revierte firewall. Conservar informes antes de limpiar datos es decisión del operador.

## Analizador local y venv

[venv.loggin.sh](../../log-summary/venv.loggin.sh) gestiona dependencias del
[requirements.txt](../../log-summary/requirements.txt) y lanza el analizador como
usuario actual; no eleva sudo automáticamente. Es tooling Bash/Linux; no se promete
compatibilidad Windows/macOS por detectar OSTYPE. Desde raíz, sin root, con esas
dependencias ya instaladas, la ayuda solo enumera opciones:

```sh
python3 log-summary/app/iptable.loggin.py --help
```

Para análisis directo usa `--analysis-type` (`by_ip`, `by_port`, `by_day`, `by_week`,
`by_month`, `by_attack_type`, `all`), `--env-file` explícito del analizador,
`--output-dir` y opcional `--year` 1970..2100. Requiere log legible; escribe informes.
Sin `--analysis-type` abre menú interactivo. Las acciones de instalar rsyslog o
agregar usuario a adm necesitan autorización root y pueden reiniciar rsyslog;
no se deben usar para validar este cambio ni ejecutar en el host de acceso.
La pertenencia a adm no garantiza lectura: comprobar modo/ACL y rotación.

El gestor tiene opciones para crear `log-summary/venv`, abrir un shell con ese
entorno, comprobar dependencias, reinstalarlas y lanzar el analizador. Crear o
reinstalar el entorno escribe archivos y puede descargar paquetes: no es consulta
pasiva. La opción de lanzamiento pasa automáticamente el `.env` de la raíz del
proyecto al analizador; para separar esa configuración usa la CLI Python con
`--env-file` explícito. No es necesario activar el entorno si se invoca directamente
su intérprete. Los ejemplos antiguos de sudo automático o soporte multiplataforma
no acreditan el comportamiento actual.

### Entradas e informes detallados

La CLI detallada lee `LOGFILE` (default interno `/var/log/firewall-suite.log`) y
los puertos `L4D2_GAMESERVER_UDP_PORTS`/`L4D2_SOURCETV_UDP_PORTS` del archivo
explícito y entorno del proceso. Los puertos clasifican las salidas; no abren
servicios. `RSYSLOG_CONF` (default `/etc/rsyslog.d/firewall-suite.conf`) solo
selecciona el archivo que puede **sobrescribir** la acción de instalación del menú.
El ejemplo Compose usa `SUMMARY_LOG_PATH` para el resumen; esas claves no son
intercambiables con `LOGFILE` de la CLI detallada. Revisa la configuración y las
rutas efectivas de cada servicio por separado.

| `--analysis-type` | Archivo JSON bajo `--output-dir` | Agrupación |
|---|---|---|
| `by_ip` | `summary_by_ip.json` | Origen, fechas y tipos de eventos |
| `by_port` | `summary_by_port.json` | Puerto destino y clase GameServer/SourceTV/Other |
| `by_day` | `summary_by_day.json` | Día y distribución temporal |
| `by_week` | `summary_by_week.json` | Semana y distribución de eventos |
| `by_month` | `summary_by_month.json` | Mes y distribución de eventos |
| `by_attack_type` | `summary_by_attack_type.json` | Patrón registrado |
| `all` | Los seis anteriores | Generación de todos los informes |

El parser necesita timestamp, `SRC`, `DPT` y `LEN` legibles; las líneas que no puede
interpretar se omiten. Admite timestamps ISO y syslog sin año; `--year` permite
fijar este último, y sin override intenta reconocer el paso diciembre→enero.
No asumas que archivos mezclados/desordenados o zonas horarias distintas forman
una cronología normalizada: el parser descarta la zona del timestamp ISO.
Comprueba fechas, cantidad de eventos y archivos producidos; no solo el exit code.
Los nombres `attack` y las severidades son categorías del analizador, no una
confirmación de intención maliciosa ni motivo suficiente para conceder bypass.

Si faltan eventos, revisa primero lectura/rotación, timestamp y campos del mensaje,
ventana del resumen y flags de logging del servicio. Desactivar logs base o de
normalización no desactiva el descarte. El menú rsyslog vigente captura `FW_EVT`
con una regla estructurada; no copies las antiguas listas de prefijos. Antes de
usar esa mutación en el destino, identifica y respalda el archivo propio elegido
y prepara su restauración; puede reemplazar contenido y reiniciar rsyslog. No
debe apuntar a configuración ajena ni usarse para arreglar permisos de lectura.

`make logs-clear` trunca irreversiblemente el archivo elegido; `logs-backup-clear`
copia antes y también trunca. Ambos son mantenimiento explícito, no consulta.
No se recomiendan como procedimiento de diagnóstico. Los resúmenes no prueban
ataques confirmados ni efectividad de reglas. Código:
[fw_log_summary.py](../../log-summary/app/fw_log_summary.py),
[iptable.loggin.py](../../log-summary/app/iptable.loggin.py),
[Compose](../../log-summary/docker-compose.yml). No se ejecutó esta pila en el
host durante la reorganización documental.
