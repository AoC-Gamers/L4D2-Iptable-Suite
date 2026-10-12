# Seguridad, aceptación y evidencia

La [aprobación con observaciones](approval.md) registra el commit y el alcance
cerrado de H1–H3. Las [limitaciones](limitations.md) delimitan operación y pruebas
pendientes por versión/topología. No es certificación externa ni una promesa para
todas las instalaciones o cambios futuros.

Para una decisión de despliegue, genera la configuración real, revisa permisos,
prueba motor/tráfico/arranque en una VM representativa y conserva recuperación.
Las [pruebas](../testing/README.md) separan lógica, kernel, tráfico y reboots;
una dependencia ausente o un SKIP no son PASS.

Los [informes históricos](../archive/audits/README.md) conservan evidencia fechada,
fallos y límites. No se actualizan sus resultados para hacerlos pasar por ensayos
del HEAD actual. Reporte de problemas: [SECURITY](../../SECURITY.md).
