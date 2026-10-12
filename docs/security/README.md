# Seguridad, aceptación y evidencia

La [aprobación con observaciones](approval.md) registra el commit y el alcance
cerrado de H1–H3. Las [limitaciones](limitations.md) delimitan operación y pruebas
pendientes por versión/topología. No es certificación externa ni una promesa para
todas las instalaciones o cambios futuros.

Para una decisión de despliegue, genera la configuración real, revisa permisos,
prueba motor/tráfico/arranque en una VM representativa y conserva recuperación.
Las [pruebas](../testing/README.md) separan lógica, kernel, tráfico y reboots;
una dependencia ausente o un SKIP no son PASS.

El [registro de aprobación](approval.md) conserva evidencia fechada, fallos y
límites. Los informes sustituidos pueden recuperarse del historial Git; su
[integración](../migration/documentation-map.md) indica qué información sigue
vigente. No se presentan resultados históricos como ensayos del HEAD actual.
Reporte de problemas: [SECURITY](../../SECURITY.md).
