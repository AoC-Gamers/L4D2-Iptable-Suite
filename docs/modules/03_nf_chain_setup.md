Módulo 03 — nf_chain_setup.sh

Descripción:
Este módulo inicializa la base de `nftables` para la suite: recrea la tabla `inet l4d2_filter`, define cadenas `input/forward/output`, fija políticas según `TYPECHAIN` y agrega reglas base seguras (`loopback`, `established,related`, salida permitida).

Contextos recomendados:
- Ejecutar siempre al inicio del backend `nftables`, antes de módulos de whitelist, VPN, TCP/UDP y validaciones.
- Usar `TYPECHAIN` para ajustar el alcance: `0=input`, `1=forward`, `2=ambos`.
- Mantener este módulo enfocado en estructura y política base; reglas específicas deben vivir en módulos funcionales.

Notas:
- Ruta actual del módulo: `modules/nf_chain_setup.sh` (módulo raíz, no dentro de `modules/nf/`).
- El loader le da prioridad de ejecución temprana por sufijo `_chain_setup.sh`.
