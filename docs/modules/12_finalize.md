> **Referencia histórica anterior al núcleo transaccional.** Las instrucciones de aplicación, configuración y persistencia de esta página fueron reemplazadas por [operación actual](../security/operations.md), [capacidades](../security/capabilities.md) y [migración](../security/migration.md). No ejecutar las recetas antiguas.

# Módulo unificado — finalize (ip/nf)

## Objetivo
Emitir cierre operativo y resumen de estado al final del pipeline.

## Backends
- iptables: `modules/ip_finalize.sh` (`ID=ip_finalize`)
- nftables: `modules/nf_finalize.sh` (`ID=nf_finalize`)

## Variables
- Requeridas: `TYPECHAIN` (y en `ip`, además `DOCKER_INPUT_COMPAT`, `DOCKER_CHAIN_AUTORECOVER`).
- `finalize` no requiere variables L4D2 para validación/ejecución.
- Si existen variables L4D2 en el entorno, solo se muestran en el resumen final como información opcional.

## Diferencias por backend
- `ip` aplica además políticas finales explícitas (`INPUT/FORWARD DROP` según contexto).
- `nf` reporta estado/flags finales del backend.

## Nota operativa
- Debe ejecutarse al final del pipeline para mantener el cierre consistente.
