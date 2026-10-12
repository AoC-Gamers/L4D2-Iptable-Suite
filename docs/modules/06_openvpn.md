# OpenVPN — adaptación de firewall

`openvpn_server` y `openvpn_sitetosite` son modos excluyentes de configuración. El núcleo valida sus redes e interfaces y compone reglas de NAT/alias cuando se solicitan; abrir el puerto del listener no concede automáticamente acceso del túnel al host o a otras redes. Declare los permisos necesarios con grants `host` o `forward`. El tráfico de forwarding queda sujeto a `ROUTED_POLICY` (por defecto `drop`).

NAT exige una interfaz de salida explícita y no es permiso de filtrado. NAT requiere familias compatibles; alias de router solo IPv4. `OVPNSRV_DOCKER_INTERFACE` y opciones de logging VPN heredadas se rechazan. Un listener publicado en Docker se expresa con un grant `containers` de servicio `openvpn_server`; el túnel debe correr en el host.

Las opciones `OVPNSRV_*`/`OVPNS2S_*` se validan en `core/config.py`; no todas las variantes tienen evidencia de tráfico real. [Resultados](../security/results.md) distingue los flujos ensayados de SNAT/legacy aún no ensayados.
