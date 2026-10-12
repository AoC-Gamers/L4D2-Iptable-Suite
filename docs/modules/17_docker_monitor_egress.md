# `docker_monitor_egress` — retirado, requiere migración

La antigua autorización por subred/targets/puerto se rechaza como módulo. Migre cada flujo de monitoreo a un grant `forward` que fije origen, destino exacto, protocolo, puertos e interfaces; `ROUTED_POLICY` debe ser `drop` para que el grant opere en el modelo administrado.

No use la subred Docker amplia como sustituto del destino. Si deja `ROUTED_POLICY=unmanaged`, otras rutas se delegan y no debe presentarse como filtrado de forwarding por la suite. [Capacidades](../security/capabilities.md) detalla integración y límites con Docker.
