# `tcp_ssh` — servicio SSH del host

El módulo agrega el puerto `SSH_PORT` (por defecto 22) al input del host y limita conexiones TCP nuevas por origen. La configuración exige un puerto válido cuando el módulo está activo. `SSH_DOCKER` dejó de ser una opción de apertura: su valor no vacío se rechaza.

Para SSH dentro de una publicación Docker, use un grant `containers` con `service=tcp_ssh` y direcciones/puertos público e interno explícitos. En host, un grant `host` permite la excepción acotada a origen/servicio; revise solapamientos de puerto con otros controles TCP.

El estado por origen tiene capacidad limitada y expiración; los valores y evidencia por backend se documentan en [capacidades](../security/capabilities.md). No interprete `validate`/`plan` como prueba de conectividad.
