# Oracle1 S2S - Notas de diseño y checklist

## Contexto actual
- Suite activa en Valpo con módulo `openvpn_sitetosite`.
- Variables activas en `.env`:
  - `OVPNS2S_INTERFACE=tun0`
  - `OVPNS2S_LOCAL_SUBNETS=192.168.1.0/24`
  - `OVPNS2S_REMOTE_SUBNETS=10.8.0.0/24` (inicial)
- En Oracle1 se observó:
  - `tun0 = 10.8.0.1/24`
  - NIC principal `ens3 = 10.0.0.188/24`
  - VCN en panel OCI: `10.0.0.0/16`

## Interpretación de redes
- `10.8.0.0/24`: red del túnel OpenVPN (overlay).
- `10.0.0.0/16`: red VCN de Oracle (underlay cloud, incluye otras instancias como oracle2).

## Objetivo
Permitir tráfico controlado entre:
- Valpo LAN: `192.168.1.0/24`
- Oracle VPN tunnel + VCN: `10.8.0.0/24` y `10.0.0.0/16`

## Configuración recomendada en Valpo (.env)
- `OVPNS2S_REMOTE_SUBNETS="10.8.0.0/24,10.0.0.0/16"`

## Qué habilita eso
- Tráfico desde peer OpenVPN (`10.8.0.0/24`) hacia LAN Valpo.
- Tráfico desde recursos de la VCN (`10.0.0.0/16`, por ejemplo oracle2) hacia LAN Valpo, sujeto a rutas/ACL.

## Requisitos en Oracle/OCI para full S2S
1. OpenVPN en Oracle1 debe rutear hacia `192.168.1.0/24`.
2. OCI route table/subred donde vive oracle2 debe conocer ruta a `192.168.1.0/24` via Oracle1 (o gateway correspondiente).
3. NSG/Security List deben permitir tráfico entre `10.0.0.0/16` y `192.168.1.0/24`.
4. Firewall local en Oracle1 debe permitir forwarding (si aplica).

## Verificación rápida
- Desde Oracle1: ping/traceroute a host de `192.168.1.0/24`.
- Desde oracle2: prueba a `192.168.1.1` o host valpo.
- En Valpo: `sudo ./nftables.rules.sh` y revisar contadores/registros.

## Nota operativa
Si se desea fase de prueba más restrictiva, usar solo `10.8.0.0/24` y luego ampliar a `10.0.0.0/16` al validar rutas OCI.
