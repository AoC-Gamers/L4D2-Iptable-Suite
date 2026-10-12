# `preload.sh` — compatibilidad retirada

`modules/preload.sh` conserva una función de compatibilidad para instalaciones antiguas. La función `run_preload` informa que el preload fue retirado y termina con error; no parsea argumentos ni carga la configuración actual.

Use `ipp.sh` como CLI (`--env-file`, `--set`, `--only`, `--skip`, `--profile`) y consulte [operaciones](../security/operations.md) y [migración](../security/migration.md). El CLI lee `.env` como asignaciones `KEY=VALUE`, nunca como shell. Las pruebas unitarias y `validate` no aplican reglas al kernel.
