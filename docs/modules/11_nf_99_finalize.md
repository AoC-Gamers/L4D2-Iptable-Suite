Módulo 11 — nf_99_finalize.sh

Descripción:
Este módulo realiza las tareas finales tras aplicar las reglas de `nftables`: comprueba el estado de las tablas, aplica políticas por defecto, persiste la configuración si procede y realiza tareas de limpieza (eliminar reglas temporales, cerrar sets temporales). También ajusta compatibilidades y emite un resumen o log final.

Contextos recomendados:
- Ejecutar siempre al final del conjunto de módulos para consolidar el estado.
- Mantener idempotencia y evitar operaciones destructivas a menos que se haga explícitamente (por ejemplo, una opción de reconfiguración completa).
- En sistemas gestionados, validar que la persistencia (si se usa) no interfiera con mecanismos del orquestador o herramientas de gestión de configuración.
