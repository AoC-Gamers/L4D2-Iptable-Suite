# Cierre H2 — configuración canónica y migración de estado

La configuración distingue ahora la entrada del operador del bundle persistente. `TYPECHAIN` se acepta solo en una carga de entrada nueva; se valida contra cualquier `HOST_SERVICES`/`CONTAINER_POLICY` explícitos, se traduce una vez y se elimina de `Configuration.values`. El renderizador entrega su propio valor técnico a los módulos legacy según el destino. Los bundles nuevos usan `schema=2` y guardan las dimensiones efectivas.

`ACCESS_POLICY` es una ruta de entrada, no parte de la política normalizada. Al cargarla, el núcleo conserva la ACL parseada en el bundle y vacía esa ruta. Los dominios bypass también se resuelven antes de guardar y el estado conserva las IP efectivas. La revalidación de estado normalizado consume dimensiones y ACL ya parseadas; no vuelve a abrir el archivo de ACL ni a resolver DNS salvo que la operación parcial incluya explícitamente una nueva entrada de dominio.

## Migración

Los bundles sin número de esquema y los `schema=1` se interpretan como estado de la versión anterior. Si contienen las dos dimensiones modernas, estas son autoridad y se retira `TYPECHAIN` sin volver a traducirlo; esto preserva, entre otros, el estado válido `TYPECHAIN=0`, `HOST_SERVICES=false`, `CONTAINER_POLICY=restrict` que podía surgir del default inyectado. Si el estado solo conserva `TYPECHAIN=0|1|2`, se traduce una sola vez. La combinación incompleta/ambigua, dominios sin resolver o un esquema desconocido falla sin escritura.

`Store.get()` migra `current`, `persisted` y los bundles `previous`/`candidate` de `pending` en memoria. El snapshot del journal no se altera. La lectura por sí sola no reescribe archivos. El formato nuevo se escribe al confirmar una política (`current`), guardar la política confirmada (`persisted`) o restaurar una política previa confirmada. Una política pending conserva su journal y watchdog mientras esté pendiente.

En operaciones parciales y retirada de módulos, `configuration()` usa el constructor normalizado y la ACL ya confirmada. No reinterpreta `TYPECHAIN` proveniente del estado ni reabre rutas antiguas. `TYPECHAIN` no puede cambiarse mediante `--partial` o `--remove`; para cambiar el alcance host/contenedor se debe suministrar una configuración nueva con las opciones canónicas.

## Verificación

`tests/test_h2.py` cubre traducción input, precedencia de dimensiones modernas, versión desconocida, migración de solo-legacy, persistencia lógica de current/persisted/pending y conservación byte a byte del archivo pending en lectura. También ejecuta composición de `container-only` y `host + containers restrict`, partial/remove y save/load lógico para nftables e iptables. Son pruebas de configuración/estado sin acceso a Netfilter; no prueban tráfico ni ejecución real del journal.

La regresión real `tests/h2-flows.py` ejecuta la CLI pública completa, tráfico TCP
IPv4/IPv6 y cuatro combinaciones: nftables/iptables y host activo/desactivado
con contenedores restrict. Comprueba apply/save/load/partial/remove, rechazo de
referencias de grants al retirar módulos, migración schema 1 y rollback pending
conservando snapshot, ACL y reglas ajenas. Pasó con iptables-nft 1.8.10, nftables
1.0.9 y kernel 7.0.0-38 en namespaces desechables; la matriz legacy de VM se
registra en el informe de cierre conjunto.
