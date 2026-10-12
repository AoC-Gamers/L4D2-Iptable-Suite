# `loopback` — núcleo obligatorio

Loopback se acepta en el input como regla de base en ambos backends. El ID legacy `loopback` puede resolverse por compatibilidad, pero no es un módulo funcional opcional ni se puede excluir: forma parte del núcleo junto con setup y finalize.

La política IPv6 `ipv4-block-ipv6` conserva las excepciones necesarias de ND/ICMPv6 además de loopback; no promete conectividad general IPv6. Detalle en [capacidades](../security/capabilities.md).
