# `whitelist` — bypass privilegiado al host

El módulo reconoce `BYPASS_SOURCE_IPS` y dominios resueltos, pero la lista no concede acceso por sí sola: la configuración exige seleccionar `whitelist` y declarar `PRIVILEGED_BYPASS=true`. El permiso resultante es un bypass de input al host; no es un grant de forwarding ni una autorización general de contenedores.

Para dominios también se requiere `DNS_ALLOWED_CIDRS`. La resolución falla cerrada si falla DNS, excede el límite de respuestas o produce una IP fuera de esos CIDR. Prefiera grants `host`/`forward` de `ACCESS_POLICY` cuando necesite acotar servicio, protocolo y puerto. Revise el bypass privilegiado en `plan` antes de aplicar.

No migre antiguas listas de confianza sin verificar su alcance. Detalle en [capacidades](../security/capabilities.md) y [migración](../security/migration.md).
