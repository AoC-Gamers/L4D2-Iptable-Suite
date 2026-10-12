# `l4d2_tcpfilter_chain` — alias de compatibilidad

Este identificador antiguo solo se acepta si se selecciona también `l4d2_tcp_protect`; el compilador actual no emite reglas propias para él en ninguno de los motores. El control actual se implementa en `l4d2_tcp_protect`. Migre las listas `TCP_DOCKER` rechazadas a grants `containers` y configure `L4D2_GAMESERVER_TCP_PORTS` explícitamente.

No confunda una cadena heredada llamada `TCPfilter` con un objeto que la suite haya creado o pueda adoptar. El módulo `l4d2_tcp_protect` aplica el control a los puertos TCP de juego configurados; el perfil `games` no lo activa por defecto.
