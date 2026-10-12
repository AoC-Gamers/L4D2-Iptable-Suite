# Servicios web

`http_https_protect` limita conexiones TCP nuevas por origen y puerto a
`HTTP_HTTPS_PORTS` (default `80,443`). `HTTP_HTTPS_RATE=180/minute` y
`HTTP_HTTPS_BURST=360`; el timeout nft declarado es `NFT_HTTP_HTTPS_METER_TIMEOUT=5m`.
El núcleo amplía el timeout omitido si hace falta y rechaza uno explícito que no
cubra recarga. Capacidad, logging y familias: [referencia](../configuration/reference.md).

El perfil [web.conf](../../config/profiles/web.conf) selecciona SSH+web, sin VPN
ni L4D2. No abre UDP/443. QUIC necesita grant UDP independiente y módulo
`allowlist_ports` seleccionado. En contenedores, grants `http_https_protect`
relacionan IP/puerto público original con destino/puerto interno después de DNAT,
con origen e interfaces; consulta [Docker](../docker/README.md).

Desde la raíz, sin root, validar y planificar solo genera/describe reglas:

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh plan --env-file config/profiles/web.conf
```

Verifica puertos, selección y familia; después ensaya cliente autorizado/denegado,
retorno y TCP/UDP independiente en VM. Aplicación y recuperación siguen
[transacciones](../firewall/transactions.md). Si no responde, distingue listener,
DNAT, reglas ajenas y filtro de la suite mediante [diagnóstico](../testing/diagnostics.md).

Este control es de red/conexiones. No cuenta peticiones HTTP ni sustituye límites
del proxy/aplicación; tampoco mitiga la saturación del enlace de entrada.
Código: [compilador](../../core/compiler.py), [módulo](../../modules/nf/nf_45_http_https_protect.sh).
Pruebas: [HTTP lógico](../../tests/http-https-protect.sh), [tráfico](../../tests/policy-flows.py),
[matriz Docker](../testing/docker.md); alcance probado: [aprobación](../security/approval.md).
