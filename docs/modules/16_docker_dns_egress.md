# `docker_dns_egress` — retirado, requiere migración

La configuración rechaza seleccionar `docker_dns_egress`: la antigua regla por subred y puerto 53 no identifica interfaz ni destino DNS y concedía un ámbito de forwarding demasiado amplio.

Declare un grant `forward` con grupo, origen, destino DNS exacto, protocolo UDP/TCP y puerto 53, interfaces de entrada/salida. Los grants forward requieren `ROUTED_POLICY=drop`; si otra política administra rutas, el modo `unmanaged` delega esas rutas y la suite no las protege. No agregue reglas manualmente a `DOCKER-USER` ni dé por sentado que Docker consulta su DNS en un destino concreto. [Capacidades](../security/capabilities.md).
