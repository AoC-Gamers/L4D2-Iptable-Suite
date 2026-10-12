# `finalize` — núcleo obligatorio

`finalize` es parte de la composición obligatoria del núcleo, no un cierre shell posterior. El motor genera una candidata, comprueba límites/propiedad y aplica por las transacciones descritas en [operaciones](../security/operations.md). No expone una opción para omitir el cierre del pipeline.

La salida de `validate` solo prueba validación lógica/generación; no hace kernel check ni instala reglas. Para saber el estado activo use `status` y consulte el historial de aceptación en [resultados](../security/results.md).
