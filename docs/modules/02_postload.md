Módulo 02 — postload.sh

Descripción:
El módulo `postload.sh` se ejecuta después de aplicar todos los módulos específicos de backend. Se utiliza para tareas de limpieza y verificación final: eliminar reglas temporales, consolidar logs, forzar persistencia (si procede) y emitir resúmenes o eventos de auditoría.

Contextos recomendados:
- Útil para operaciones de post-provisión donde hay que revertir cambios temporales o validar el estado final del firewall.
- Evitar colocar lógica que bloquee el arranque del sistema; preferir acciones de no-bloqueo y reintentos controlados.
- En entornos con orquestadores (Docker, Kubernetes), limitar las acciones que toquen la configuración global salvo que estén explícitamente permitidas.
