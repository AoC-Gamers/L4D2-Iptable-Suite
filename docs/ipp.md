# ipp: persistencia y gestión selectiva

`ipp.sh` comparte el escritor, lock, journal y watchdog de ambos entrypoints. Ya no
hay menú que instale paquetes, reinicie servicios, cambie alternativas o borre firewalls.

```sh
./ipp.sh                         # ayuda
sudo ./ipp.sh status
sudo ./ipp.sh doctor
sudo ./ipp.sh save               # sólo política confirmada de la suite
sudo ./ipp.sh load               # comprobación + aplicación + confirmación remota
sudo ./ipp.sh apply --remove http_https_protect
sudo ./ipp.sh apply --partial --only tcp_ssh --set SSH_RATE=30/minute
sudo ./ipp.sh disable            # objetos/hook propios; conserva persistencia
sudo ./ipp.sh confirm --token TOKEN --admin-verified
sudo ./ipp.sh rollback
```

Añadir `--backend iptables` cuando corresponda. No se edita `/etc/nftables.conf` ni
`/etc/iptables/rules.v4`/`rules.v6`. No se adopta ni borra persistencia ajena. La unidad
`systemd/l4d2-firewall.service` es una integración explícita de arranque, pendiente de
ensayo real en VM y de ordenarse después de Docker cuando haya grants de contenedores.

Consultar [operación](security/operations.md) y [migración](security/migration.md) antes
 de usarlo en un servidor existente. El modo `--local` sólo es para consola/arranque;
una sesión SSH ya establecida no sustituye la prueba administrativa nueva.
