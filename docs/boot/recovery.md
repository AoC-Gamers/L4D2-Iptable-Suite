# Recuperación de la protección de arranque

Preparar consola fuera de banda antes de activar [guard/readiness](README.md).
Sin `--recovery-file`, el manifiesto solo ofrece recuperación por consola. El
[ejemplo SSH](../../config/boot-recovery.example.json) usa fuentes/destinos ficticios,
interfaz exacta y puertos incluidos en `SSH_PORT`; no es un bypass general de host.
El archivo operacional debe ser root-owned y confiable, incluidos sus ancestros.

## Restore fallido

Si falta persistencia, está corrupta, la versión no está aceptada o falla el motor,
la barrera debe permanecer y los consumidores dependientes no deben arrancar.
Desde consola o la nueva conexión de recuperación expresamente permitida, consulta
estado de unidades y journal (root para logs restringidos; cualquier directorio,
solo lectura):

```sh
systemctl --no-pager status l4d2-firewall-guard.service l4d2-firewall.service l4d2-firewall-ready.service
sudo journalctl -b -u l4d2-firewall-guard.service -u l4d2-firewall.service -u l4d2-firewall-ready.service --no-pager
```

No publiques logs sin sanear. Distingue unidad inactiva de restore exitoso; `Result=success`
con `inactive/dead` no prueba que se ejecutara la restauración. Repara únicamente la
causa identificada con el conjunto código/estado conocido válido. No edites un journal
pending a mano ni conviertas schema 2 para volver a código antiguo.

Tras restituir inputs/herramientas compatibles, desde cualquier directorio en el
host de destino en mantenimiento, **root**, con consumidores protegidos todavía
detenidos y manifiesto válido, estos comandos cambian solo protección propia:

```sh
sudo /opt/l4d2-firewall/ipp.sh boot-restore
sudo /opt/l4d2-firewall/ipp.sh ready
```

Para política iptables pasa `--backend iptables` consistentemente. `boot-restore`
arma/rearma guard, recupera journal, restaura persistencia, verifica kernel y solo
entonces libera barrera. `ready` consulta disponibilidad bajo lock y no recupera
journal. Si falla, conserva barrera/consumidores detenidos, vuelve al diagnóstico;
no desarmes para forzar arranque. Después prueba conexiones nuevas permitidas y
rechazadas y reactiva solo consumidores revisados.

## Cambio de alcance o retirada

Desde consola, detener primero los consumidores y su activación por sockets. Tras
revisar las unidades opt-in habilitadas, desarmar exige decisión explícita local:

```sh
sudo /opt/l4d2-firewall/ipp.sh boot-disarm --local
```

Es una mutación root de la barrera propia; no detiene servicios ni cambia por sí
misma la política normal. Sigue [retirada/persistencia](../firewall/persistence.md)
para `disable`, o aplica/confirmar/guardar/ready y prepara el nuevo manifiesto antes
de reactivar protección. No reinicies dejando unidades guard habilitadas sin manifiesto.

`--accept-version-change` solo se acepta en check/apply/load de mantenimiento;
un check no persiste aceptación. Aplicar/cargar, confirmar y guardar sí conserva
la decisión evaluada. Nunca autoriza cambio frontend o mezcla v4/v6; esa transición
necesita [migración](../migration/README.md). Límites: [seguridad](../security/limitations.md).
