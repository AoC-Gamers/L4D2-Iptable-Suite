# `postload.sh` — helper heredado

`modules/postload.sh` es un helper de salida histórica, no el cierre del flujo actual. El núcleo genera y valida la candidata antes de entregarla al motor transaccional; los módulos no controlan servicios.

No use este script para inferir que una política quedó aplicada o confirmada. Consulte `ipp.sh status` y [operaciones](../security/operations.md). La evidencia de integración y sus límites está en [resultados](../security/results.md).
