# Pruebas y evidencia

Complementa [AGENTS raíz](../AGENTS.md). Lee [testing](../docs/testing/README.md)
y [runner VM](../docs/testing/vm.md). Los tests privilegiados nunca se ejecutan
directamente contra la red/servicios del host. Conserva attestación QEMU, root-owned
markers, ownership de fixtures, namespaces distintos y `/run` privado.

Separa unitarios/mocks, generación, check del motor, tráfico, VM y reboots. CI
obligatorio falla por herramientas/privilegios ausentes y por código 77: no convertir
SKIP en PASS. No reduzcas controles ni assertions de política para conseguir verde.
Preserva positivos/negativos y comprueba que el paquete alcanzó el control esperado.

H3 tiene una combinación de arranque; la matriz Docker normal tiene cinco. No las
confundas. Sondas muestreadas no excluyen ventanas arbitrariamente breves.
Limpieza solo de recursos acreditados: fixture modificada se conserva y reporta.
Informa commit, herramientas/versiones, aislamiento, resultado, capas y no ejecutados.
No guardes claves/tokens ni uses `.env` privado. El checker documental solo lee
Markdown/referencias y no ejecuta sus bloques ni invoca Netfilter.
