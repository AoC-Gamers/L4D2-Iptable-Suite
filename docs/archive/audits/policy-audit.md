# Auditoría de política efectiva

> Archivo histórico. Se conserva el contenido del informe/manual anterior; no es
> la guía operativa vigente. Consulta el [índice actual](../../README.md) y
> [la aprobación por commit](../../security/approval.md).

## POL-01 — `STATE_CAPACITY` no limitaba las entradas hashlimit de iptables

**Prioridad: P1. Estado: corregido y verificado en namespace aislado.**

`core/compiler.py` añadía `--hashlimit-htable-max STATE_CAPACITY`, pero dejaba que
el kernel eligiera el número de buckets según la RAM. El kernel aumenta el máximo
de entradas hasta el número de buckets cuando el máximo pedido es menor. Así, con
`STATE_CAPACITY=16`, las protecciones web y L4D2 TCP aceptaban 24 orígenes nuevos
distintos en la prueba, sin llegar al corte que sí aplicaba nftables.

El compilador ahora fija `--hashlimit-htable-size` y `--hashlimit-htable-max` al
mismo `STATE_CAPACITY` en cada regla hashlimit. Conserva expiraciones específicas
de servicio o derivadas de tasa y sólo añade la expiración de 60 segundos cuando
la regla no trae una.

La regresión unitaria comprueba reglas con opciones preexistentes, reemplazo del
tamaño/máximo y expiraciones SSH/web calculadas. La prueba de tráfico aislado usa
24 orígenes: ambos motores y los dos servicios aceptan exactamente 16 y bloquean
los 8 restantes. También pasaron los escenarios de grants por origen, bypass de
protocolo opuesto con `HOST_SERVICES=false` y validación de timeouts.

Evidencia de ejecución: Linux 7.0.0-38-generic, nftables 1.0.9 e iptables 1.8.10
(backend nf_tables), dentro de `tests/isolated-run.sh` con namespaces de usuario,
red y montaje y `/run` privado. No cubre aún el tráfico de iptables-legacy.

La semántica se contrasta con el [código upstream de `xt_hashlimit`](https://github.com/torvalds/linux/blob/master/net/netfilter/xt_hashlimit.c)
y la [documentación de iptables-extensions](https://man7.org/linux/man-pages/man8/iptables-extensions.8.html).
