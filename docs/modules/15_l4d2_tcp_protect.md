# `l4d2_tcp_protect` — TCP de juego/RCON

Aplica limitación de conexiones TCP NEW por origen a `L4D2_GAMESERVER_TCP_PORTS`. La lista vacía no abre ni controla puertos. El módulo es opt-in y no forma parte del perfil `games` por defecto; `l4d2_tcpfilter_chain` es solo compatibilidad y depende de este módulo.

El módulo no ofrece una variante de control TCP de juego para contenedores. Los valores no vacíos de `TCP_DOCKER` se rechazan. Si solo necesita permitir una publicación TCP, un grant `containers` con `service=allowlist_ports` y el módulo seleccionado expresa ese permiso acotado, pero no aplica el limitador TCP de juego. Use `service=tcp_ssh` solo para una publicación SSH real; no es sustituto del control de juego. Evite superponer puertos host con SSH/web/allowlist: el validador rechaza ambigüedades.

La tasa/límite específico y evidencia de backend están en [capacidades](../security/capabilities.md) y [resultados](../security/results.md).
