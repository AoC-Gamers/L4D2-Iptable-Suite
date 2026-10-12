# Convenciones documentales

Complementa [AGENTS raíz](../AGENTS.md); no es un registro de tareas.

- Organiza guías actuales por funcionalidad `docs/<feature>/*.md`, rutas en inglés
  kebab-case y prosa española. Identificadores, variables y comandos conservan su forma real.
- Mantén una fuente canónica por tema. Los README orientan y enlazan; no duplican
  procedimientos completos. El [índice](README.md) debe alcanzar todas las páginas actuales.
- Conserva la decisión, commit, entorno, referencias y límites de evidencia en
  `security/approval.md`; los ensayos reproducibles pertenecen a `testing/`.
  No mantengas copias de auditorías ni informes de tareas terminadas en el árbol.
  El historial Git conserva los originales; no conviertas resultados de otro
  commit en PASS del HEAD actual ni borres pendientes al consolidar contenido.
- Contrasta ejemplos con CLI, código y `config/` versionado. Indica cwd, privilegios,
  efecto (leer/generar/comprobar/mutar), valores ficticios y resultado esperado. Una
  mutación de conectividad necesita confirmación/recuperación. Nunca ejecutes bloques
  Markdown automáticamente. No copies configuraciones privadas ni salidas sensibles.
- Usa enlaces relativos internos, incluidas imágenes/anclas. Corrige referencias
  entrantes al mover y apunta directamente al canónico, sin wrappers documentales
  ni avisos de traslado. Registra cambios de rutas e integración de contenido en
  [mapa documental](migration/documentation-map.md).
- No amplíes garantías ni ocultes pendientes. Separa estática, mocks, generación,
  motor, tráfico, VM/reboots y destino. Pruebas omitidas no acreditan aceptación.
- Antes de entregar: `git diff --check`, `python3 -I tests/check_docs.py` desde raíz,
  revisar rutas antiguas, referencias externas importantes, comandos/opciones contra
  CLI, alcance del diff y coherencia de AGENTS. Registra red restringida/errores
  temporales y checks no realizados. No cambies política/CI para validar documentos.
