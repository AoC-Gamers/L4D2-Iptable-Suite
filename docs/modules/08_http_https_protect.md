# `http_https_protect` — HTTP/HTTPS

Controla conexiones TCP nuevas a `HTTP_HTTPS_PORTS` (por defecto `80,443`) con tasa y ráfaga por origen y puerto. En nftables el medidor tiene expiración; el núcleo deriva timeout suficiente para el refill cuando no se fija uno, y rechaza un timeout explícito insuficiente.

Para una publicación Docker, un grant `containers` `service=http_https_protect` vincula la dirección/puerto público con destino/puerto interno y protocolo. El filtro usa el puerto público original tras DNAT. La protección no abre UDP/443: QUIC necesita un grant UDP independiente, normalmente `service=allowlist_ports` y módulo seleccionado.

La salida de `plan` muestra la composición; el tráfico real por versiones probadas y las limitaciones se separan en [capacidades](../security/capabilities.md) y [resultados](../security/results.md).
