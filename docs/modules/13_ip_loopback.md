> **Referencia histórica anterior al núcleo transaccional.** Las instrucciones de aplicación, configuración y persistencia de esta página fueron reemplazadas por [operación actual](../security/operations.md), [capacidades](../security/capabilities.md) y [migración](../security/migration.md). No ejecutar las recetas antiguas.

# Módulo específico ip — loopback

## Módulo
- `modules/ip/ip_05_loopback.sh` (`ID=ip_loopback`)

## Objetivo
Permitir tráfico local `lo` en backend `iptables`.

## Nota operativa
En `nft`, este comportamiento se integra en `nf_chain_setup`.
