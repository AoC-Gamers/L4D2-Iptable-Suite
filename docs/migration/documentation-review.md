# Revisión de la reorganización documental

Fecha: 12 de octubre de 2026. Partida y base aprobada:
`93096dea2d7854a4d580a0b4922d5d1426c8149e`, `main` sin diferencia de commits.
Rama de trabajo `docs/feature-based-documentation`. Los dos workflows tenían
cambios locales de Node 24; se conservan sin incluirlos en commits ni publicarlos.
No se leyó/modificó `.env` ni configuraciones privadas. Los tests pueden generar
cachés Python y temporales de validación ignorados.

Esta entrega es documental. No constituye una nueva auditoría de seguridad ni
una nueva aceptación funcional de las reglas. [Aprobación](../security/approval.md)
registra por separado la evidencia del commit exacto anterior.

## Organización y compatibilidad

El [inventario previo](documentation-map.md) clasifica 54 Markdown originales,
52 rutas mapeadas, documentación externa a docs y referencias de scripts/unidades.
Se mantienen avisos en las rutas anteriores; los índices vigentes enlazan al
canónico directamente. La arquitectura sugerida se consolidó para evitar fichas
vacías: VPN server/S2S en una guía y SourceTV en la guía L4D2.

```text
docs/
  README.md, AGENTS.md
  getting-started/       inicio e instalación
  configuration/         formato, referencia, perfiles y ACL
  architecture/          contrato y catálogo consolidado
  firewall/              motores, transacciones, persistencia e iptables
  administration/        SSH
  docker/                integración/publicaciones/egreso
  vpn/                   servidor y site-to-site
  l4d2/                  juego, SourceTV y consultas
  web/                   TCP web y distinción QUIC
  boot/                  preparación y recuperación
  automation/            watcher y GeoIP
  observability/         resúmenes, informes y venv
  testing/               capas, diagnóstico, VM y diseños
  security/              aprobación y límites actuales
  migration/             migración funcional, mapa y este informe
  archive/audits/        evidencia fechada/hitos y manuales anteriores
```

Guías vigentes trasladadas: operaciones→instalación, configuración→configuration,
loader→architecture, operaciones/capacidades/ipp/iptables→firewall, boot→boot,
watcher/GeoIP→automation, validación y diseños VM→testing, firmas Source→l4d2.
Dieciocho fichas numeradas se consolidan en architecture/modules y enlazan a las
guías de cada servicio. Archivo contiene informes de resultados/auditorías/cierres
y dos manuales anteriores de logging/venv; el analizador sigue disponible.
Los README de GeoIP/log-summary quedan como entradas breves. Créditos conservados.

Se crean AGENTS raíz y docs, más instrucciones particulares en tests/systemd;
no se añadieron adaptadores de otras herramientas ni symlinks. CONTRIBUTING y
SECURITY explican colaboración, pruebas y la ausencia de canal privado confirmado.
El checker estándar Python no ejecuta comandos Markdown ni usa red/Netfilter.

Se repararon también enlaces que ya estaban rotos en los manuales anteriores:
anclas de configuración/multiplataforma, enlaces a secciones iptables retiradas,
`log-summary/docs/ipp.md` y `log-summary/example.env` inexistentes. Ahora apuntan a
secciones/páginas canónicas y `.env.example`; no se reescribieron sus afirmaciones
históricas. Se normalizaron espacios finales de esos dos manuales para pasar
`git diff --check`; el texto y los datos permanecen iguales. La advertencia de
archivo dirige a la guía vigente corregida.

## Referencias fuera de Markdown y alcance

- Cuatro `Documentation=` de unidades: solo ruta al Markdown nuevo; comandos,
  orden, dependencias y condiciones permanecen idénticos.
- `example.env`: solo comentarios; las asignaciones efectivas permanecen idénticas.
- `ipp.sh`: solo la ruta documental dentro de la ayuda. CLI/ejecución sin cambios.
- Dos docstrings de arneses VM: solo ruta de diseño; AST funcional sin cambios.
- `tests/check_docs.py` y `tests/test_docs.py`: comprobación documental y cinco
  regresiones de sus enlaces/anclas/navegación/avisos/unidades, sin cambios
  en las aserciones de pruebas funcionales ni workflows.

Código de core/modules, perfiles/config JSON, scripts de automatización y resto de
archivos se comparan con la base. Los workflows locales se excluyen de esta revisión
documental y conservan sus bytes iniciales. No se alteraron reglas, permisos,
configuración efectiva, transacciones, lock, rollback, schema o política de CI.

## Incidencias funcionales fuera del cambio

**F-DOC-01 — inconsistencia reproducida en generación lógica, pendiente.**
[config.py](../../core/config.py) valida `OVPNS2S_ROUTER_ALIAS` reemplazando `;`
por `|`, mientras [compiler.py](../../core/compiler.py) separa pares por coma
y campos por `;`. Con IP ficticias `192.0.2.1|198.51.100.1`, `Configuration`
acepta el dato pero `generate` lanza `ValueError: not enough values to unpack
(expected 2, got 1)` en ambos motores. Con `192.0.2.1;198.51.100.1` ambos generan.
Se reprodujo importando los dos constructores como usuario sin root con
`tests/empty.conf`, solo `openvpn_sitetosite`, `tun0`, redes `192.0.2.0/24` y
`198.51.100.0/24`. No se consultó ni cambió Netfilter. La CLI pública validate
también genera: el fallo ocurre antes de aplicación, no demuestra bypass.
Riesgo residual: entrada admitida por el validador interno falla al componer;
requiere unificar gramática/error y regresión en cambio funcional separado.
La guía usa el formato actualmente consumido `real;alias` separado por coma,
y enlaza esta limitación. No se corrigió producto ni se creó issue público.

**F-DOC-02 — alcance de datos de Compose, observado; requiere decisión separada.**
[log-summary/docker-compose.yml](../../log-summary/docker-compose.yml) declara
`.env` propio y `../.env` del firewall en ambos servicios, exponiendo esas variables
al contenedor. No se inspeccionó su contenido ni se acredita filtración efectiva.
La guía advierte el alcance y la necesidad de archivo raíz; desacoplar esos inputs
requiere cambio funcional fuera de esta tarea. No se modificó Compose.

Los targets `make firewall-*`, `logs-clear` y `status` GeoIP tienen efectos que
requieren cuidado (aplicar, truncar e imprimir configuración, respectivamente).
Se documentaron; no se cambiaron ni se presentaron como diagnóstico pasivo.

## Comprobaciones de esta entrega

Entorno de esta revisión: usuario sin root en Linux, Python 3.12.3, Bash 5.2.21,
ShellCheck 0.9.0 extraído localmente (no estaba en PATH). No se instalaron paquetes
ni se cambiaron servicios del anfitrión. Comandos desde raíz del checkout salvo
herramientas de comparación que solo leen archivos/Git y fuentes originales.

| Comprobación | Resultado |
|---|---|
| `git diff --check`, staged y diff completo desde `93096de` | PASS tras normalizar espacios finales heredados al incorporar archivos nuevos |
| `python3 -I tests/check_docs.py` | PASS: 115 páginas Markdown, 575 enlaces/anclas locales; imágenes/referencias/avisos, navegación y cuatro `Documentation=`; no ejecuta bloques ni red |
| `python3 -I tests/test_docs.py` | 5 PASS: referencias/imágenes/anclas Unicode/duplicadas/explícitas, fallos de destino/referencia, navegación actual no exenta por mapa, avisos y referencias de unidad |
| Smoke lógico | `bash tests/smoke-modules.sh`: 21 core + 3 GeoIP Python PASS, HTTP lógico y validación de ambos motores PASS |
| Generación | `bash tests/generate.sh`: 8 candidatas PASS, cuatro perfiles por motor, sin kernel |
| Documentación de CLI | Ayuda pública de ambos wrappers y runner contrastada; 9 ejemplos enumerados deliberadamente de validate/generate/plan/diff PASS, incluidos web+games, VPN y ACL contenedor; no ejecución automática desde Markdown |
| Unitarios de referencias afectadas | `python3 -I tests/test_boot.py`: 18 PASS; `python3 -I tests/vm/test_transactions_harness.py`: 2 PASS. Mocks/lógica/proceso, no Netfilter |
| Sintaxis y ShellCheck | `bash -n` para scripts versionados; ShellCheck 0.9.0 sobre selección CI con exclusión preexistente de venv: PASS; `py_compile` del checker y dos arneses con docstrings corregidos: PASS |
| Sustancia histórica | Comparación con copia previa: 14 informes/manuales conservan prosa, fechas, resultados, fallos y datos; solo avisos, destinos de enlaces y espacios finales cambian |
| Alcance de producto | Hash de archivos versionados y comparación con base: solo ocho referencias documentales existentes fuera de Markdown; AST Python sin docstring, asignaciones de example.env y directivas de unidades sin Documentation idénticas; core/modules/perfiles restantes intactos |
| Cambios locales previos | SHA-256 de los dos workflows idénticos al inicio; excluidos de commits documentales |
| Rutas antiguas | Cero literales de rutas anteriores en guías de uso fuera del inventario/informe/avisos/archivo clasificado; rutas operativas conservan aviso directo |
| AGENTS | Revisión raíz/docs/tests/systemd: invariantes coincidentes; comandos ordinarios no privilegiados, casos especiales con aislamiento; sin adaptadores/symlinks |
| Externos | 25 destinos consultados: 23 HTTP 200, dos timeout (`iptables-restore` e `iptables-extensions` de man7); segundo intento de consulta también timeout. No se marcaron rotos ni aprobados. HTTP 200 acredita respuesta, no conservación semántica de todo el contenido externo |
| Fuentes importantes | Lectura oficial Docker iptables/nftables y manual nftables; API GitHub confirmó HEAD/conclusión de ambos runs, artifact no expirado y reporte privado desactivado. Capturas/docs Valve se conservaron con sus límites, sin nueva certificación de protocolos |

En total se ejecutaron **49 casos Python unitarios/documentales/harness** en esta
revisión (24 smoke, 18 boot, 2 TX harness, 5 checker), más generación y controles
estáticos. Son independientes de los 118 casos históricos de la aprobación.

**No ejecutado en esta rama:** checks privilegiados del motor, tráfico real,
Docker/OpenVPN, arranque/reboots y CI remoto. El cambio es documental y no requiere
alterar reglas/servicios del host; no se atribuye nueva evidencia kernel/tráfico.
Los dos enlaces man7 quedan no comprobados por timeout. La validación operativa de
cada destino y los pendientes de [limitaciones](../security/limitations.md) siguen
vigentes. No se agregó ni modificó política de CI documental o funcional.

Primer commit de reorganización: `2d85a05` (guías/instrucciones, avisos, archivo y
checker). Este registro completa la evidencia de revisión en un commit documental
posterior. Ninguno de los dos se mezcla automáticamente en main ni se publica.
