# Módulo transversal — preload

## Objetivo
Preparar el entorno antes de cargar módulos de backend.

## Módulo
- `modules/preload.sh`

## Alcance
- Carga de variables globales y parámetros de ejecución.
- Parseo de opciones (`--env-file`, `--only`, `--skip`, `--dry-run`, `--verbose`, `--set`).
- Preparación de listas de módulos a ejecutar/saltar.

## Recomendaciones
- Mantener este módulo idempotente y sin lógica de filtrado específica.
- Usarlo solo para bootstrap y validaciones transversales al backend.
