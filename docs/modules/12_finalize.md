# Módulo unificado — finalize (ip/nf)

## Objetivo
Emitir cierre operativo y resumen de estado al final del pipeline.

## Backends
- iptables: `modules/ip_finalize.sh` (`ID=ip_finalize`)
- nftables: `modules/nf_finalize.sh` (`ID=nf_finalize`)

## Diferencias por backend
- `ip` aplica además políticas finales explícitas (`INPUT/FORWARD DROP` según contexto).
- `nf` reporta estado/flags finales del backend.

## Nota operativa
- Debe ejecutarse al final del pipeline para mantener el cierre consistente.
