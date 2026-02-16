Módulo 12 — ip_chain_setup.sh

Descripción:
Este módulo prepara la base del backend `iptables`: limpieza/recuperación inicial, políticas por defecto, reglas tempranas (`ESTABLISHED,RELATED`) y creación de cadenas necesarias para módulos posteriores (UDP, A2S, TCP, etc.). También contempla compatibilidad Docker según `TYPECHAIN` y flags asociadas.

Contextos recomendados:
- Ejecutar siempre al inicio del backend `iptables`.
- Validar `TYPECHAIN`, `DOCKER_INPUT_COMPAT` y `DOCKER_CHAIN_AUTORECOVER` antes de aplicar en producción.
- Mantener este módulo como infraestructura base y mover lógica funcional específica a módulos dedicados.

Notas:
- Ruta actual del módulo: `modules/ip_chain_setup.sh` (módulo raíz).
- El loader le da prioridad de ejecución temprana por sufijo `_chain_setup.sh`.
