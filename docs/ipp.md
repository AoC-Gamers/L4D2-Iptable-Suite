# ipp.sh - IPTables Persistent Manager

## Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Instalación y Requisitos](#instalación-y-requisitos)
- [Uso del Script](#uso-del-script)
- [Funcionalidades del Menú](#funcionalidades-del-menú)
- [Casos de Uso](#casos-de-uso)
- [Integración con la Suite](#integración-con-la-suite)
- [Troubleshooting](#troubleshooting)

## Descripción General

`ipp.sh` (IPTables Persistent Manager) es una herramienta interactiva diseñada para simplificar la gestión de la persistencia de reglas iptables. Proporciona un menú intuitivo que elimina la necesidad de recordar comandos complejos de `iptables-persistent` y automatiza las tareas más comunes de administración.

### Características Principales

- **Menú interactivo** fácil de usar con opciones numeradas
- **Gestión automática** de iptables-persistent (instalación/desinstalación)
- **Visualización clara** de reglas activas y guardadas
- **Backup y restauración** de configuraciones
- **Diagnóstico del sistema** con información detallada del estado
- **Confirmaciones de seguridad** para operaciones destructivas
- **Soporte completo** para reglas IPv4 (IPv6 deshabilitado por defecto)

## Instalación y Requisitos

### Requisitos del Sistema

- **Sistema Operativo**: Linux con systemd (Ubuntu 16.04+, Debian 8+, CentOS 7+)
- **Permisos**: Acceso root/sudo
- **Dependencias**: iptables, bash 4.0+

### Instalación

```bash
# Descargar como parte de la suite completa
git clone https://github.com/AoC-Gamers/L4D2-Iptable-Suite.git
cd L4D2-Iptable-Suite

# O descargar solo el script
wget https://raw.githubusercontent.com/AoC-Gamers/L4D2-Iptable-Suite/main/ipp.sh
chmod +x ipp.sh
```

### Verificación de Instalación

```bash
# Verificar que el script es ejecutable
ls -la ipp.sh

# Verificar dependencias del sistema
which iptables
systemctl --version
```

## Uso del Script

### Ejecución Básica

```bash
# Ejecutar el gestor de persistencia
sudo ./ipp.sh
```

**⚠️ Importante**: El script debe ejecutarse con permisos de root/sudo ya que modifica configuraciones del sistema y reglas de iptables.

### Menú Principal

Al ejecutar el script, se presenta el siguiente menú interactivo:

```
=========================================
       IPTables Persistent Manager      
=========================================
1 - Install iptables-persistent
2 - Remove  iptables-persistent
3 - Show current iptables rules
4 - Clear all iptables rules
5 - Save current rules (persistent)
6 - Show saved rules file
7 - Clear saved rules file
8 - Reload saved rules
9 - Status of iptables service
0 - Exit
=========================================
```

## Funcionalidades del Menú

### 1. Install iptables-persistent

**Funcionalidad**: Instala y configura automáticamente el paquete `iptables-persistent`.

**Proceso realizado**:
- Pre-configura debconf para evitar prompts interactivos
- Actualiza la lista de paquetes (`apt-get update`)
- Instala `iptables-persistent`
- Elimina el archivo de reglas IPv6 (ya que solo usamos IPv4)
- Crea el directorio `/etc/iptables` si no existe

**Salida típica**:
```
🔄 Installing iptables-persistent...
✅ iptables-persistent installed successfully
📝 IPv6 support disabled (rules.v6 removed)
```

**Cuándo usarlo**: Primera vez que configuras persistencia de iptables en el sistema.

---

### 2. Remove iptables-persistent

**Funcionalidad**: Desinstala completamente `iptables-persistent` del sistema.

**Proceso realizado**:
- Ejecuta `apt-get purge -y iptables-persistent`
- Elimina configuraciones y archivos relacionados

**Salida típica**:
```
🔄 Removing iptables-persistent...
✅ iptables-persistent removed successfully
```

**Cuándo usarlo**: Cuando necesitas limpiar completamente la instalación o cambiar a un método diferente de persistencia.

---

### 3. Show current iptables rules

**Funcionalidad**: Muestra todas las reglas de iptables actualmente activas en el sistema.

**Información mostrada**:
- Reglas de la tabla filter (INPUT, FORWARD, OUTPUT)
- Reglas de la tabla NAT
- Números de línea para facilitar referencias
- Contadores de paquetes y bytes
- Información detallada de cada regla

**Formato de salida**:
```
📋 Current iptables rules:
==========================
Chain INPUT (policy DROP 0 packets, 0 bytes)
num  target     prot opt source               destination         
1    ACCEPT     all  --  0.0.0.0/0            0.0.0.0/0           
2    DROP       udp  --  0.0.0.0/0            0.0.0.0/0           

📋 NAT table rules:
==================
Chain PREROUTING (policy ACCEPT 0 packets, 0 bytes)
...
```

**Cuándo usarlo**: Para verificar qué reglas están activas antes de hacer cambios o guardar configuraciones.

---

### 4. Clear all iptables rules

**Funcionalidad**: Limpia completamente todas las reglas de iptables y restaura políticas por defecto.

**⚠️ Operación destructiva**: Requiere confirmación del usuario.

**Proceso realizado**:
1. Cambia políticas por defecto a ACCEPT (para evitar bloqueo del sistema)
2. Limpia todas las reglas (`iptables -F`)
3. Elimina cadenas personalizadas (`iptables -X`)
4. Limpia tablas NAT y mangle
5. Resetea contadores

**Prompt de confirmación**:
```
⚠️  This will clear ALL iptables rules. Continue? [y/N]
```

**Cuándo usarlo**: Para resetear completamente la configuración de iptables o resolver conflictos de reglas.

---

### 5. Save current rules (persistent)

**Funcionalidad**: Guarda las reglas actuales de iptables para que persistan después de reinicios.

**Proceso realizado**:
- Crea el directorio `/etc/iptables` si no existe
- Ejecuta `iptables-save` y guarda en `/etc/iptables/rules.v4`
- Establece permisos apropiados (644)
- Cuenta y reporta el número total de reglas guardadas

**Salida típica**:
```
💾 Saving current iptables rules...
✅ Rules saved to /etc/iptables/rules.v4
📊 Total rules saved: 25
```

**Cuándo usarlo**: Después de configurar reglas con `iptables.rules.sh` para hacer los cambios permanentes.

---

### 6. Show saved rules file

**Funcionalidad**: Muestra el contenido del archivo de reglas guardadas usando `less` para navegación.

**Características**:
- Navegación con teclas de `less` (espacio, flechas, q para salir)
- Muestra el formato raw de iptables-save
- Búsqueda dentro del archivo con `/`

**Salida típica**:
```
📋 Saved iptables rules from /etc/iptables/rules.v4:
=============================================
# Generated by iptables-save v1.8.4
*filter
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
:OUTPUT ACCEPT [0:0]
-A INPUT -i lo -j ACCEPT
...
```

**Cuándo usarlo**: Para revisar qué reglas están configuradas para cargar al inicio del sistema.

---

### 7. Clear saved rules file

**Funcionalidad**: Vacía el archivo de reglas guardadas sin eliminarlo.

**Proceso realizado**:
- Verifica que el archivo existe
- Vacía el contenido usando redirección (`> archivo`)
- Mantiene el archivo para futuras configuraciones

**Salida típica**:
```
🗑️  Clearing saved rules file...
✅ Saved rules file cleared
```

**Cuándo usarlo**: Para limpiar configuraciones guardadas sin afectar las reglas actualmente activas.

---

### 8. Reload saved rules

**Funcionalidad**: Recarga las reglas desde el archivo guardado, aplicándolas inmediatamente al sistema.

**Proceso realizado**:
- Verifica que el archivo de reglas existe
- Ejecuta `iptables-restore` con el archivo guardado
- Reemplaza completamente las reglas activas

**Salida típica**:
```
🔄 Reloading saved iptables rules...
✅ Rules reloaded successfully
```

**Cuándo usarlo**: Para restaurar una configuración guardada o aplicar cambios después de modificar manualmente el archivo de reglas.

---

### 9. Status of iptables service

**Funcionalidad**: Proporciona un diagnóstico completo del estado del sistema de iptables persistentes.

**Información mostrada**:
- Estado de instalación de iptables-persistent
- Existencia y ubicación del archivo de reglas
- Número total de reglas guardadas
- Número de reglas actualmente activas

**Salida típica**:
```
📊 IPTables service status:
==========================
✅ iptables-persistent: INSTALLED
✅ Rules file: EXISTS (/etc/iptables/rules.v4)
📊 Total saved rules: 25
📊 Current active rules: 27
```

**Cuándo usarlo**: Para verificar el estado general del sistema antes de hacer cambios o diagnosticar problemas.

---

### 0. Exit

**Funcionalidad**: Sale del script de manera segura.

**Salida**:
```
👋 Exiting...
```

## Casos de Uso

### Configuración Inicial de un Servidor L4D2

**Escenario**: Acabas de instalar `iptables.rules.sh` y quieres hacer las reglas persistentes.

```bash
# 1. Aplicar reglas L4D2
sudo ./iptables.rules.sh

# 2. Gestionar persistencia
sudo ./ipp.sh
# → Seleccionar: 1 (Install iptables-persistent)
# → Seleccionar: 5 (Save current rules)
# → Seleccionar: 9 (Status) para verificar
# → Seleccionar: 0 (Exit)
```

### Mantenimiento Rutinario

**Escenario**: Verificación semanal del estado de reglas.

```bash
sudo ./ipp.sh
# → Seleccionar: 9 (Status) para diagnóstico general
# → Seleccionar: 3 (Show current rules) para revisar reglas activas
# → Comparar con la salida esperada
# → Seleccionar: 0 (Exit)
```

### Actualización de Configuración

**Escenario**: Has modificado el archivo `.env` y necesitas aplicar nuevas reglas.

```bash
# 1. Aplicar nuevas reglas
sudo ./iptables.rules.sh

# 2. Guardar cambios
sudo ./ipp.sh
# → Seleccionar: 3 (Show current rules) para verificar
# → Seleccionar: 5 (Save current rules) para hacer persistente
# → Seleccionar: 0 (Exit)
```

### Recovery de Configuración

**Escenario**: Las reglas se han corrompido o eliminado accidentalmente.

```bash
sudo ./ipp.sh
# → Seleccionar: 8 (Reload saved rules) para restaurar
# → Seleccionar: 3 (Show current rules) para verificar
# → Si las reglas guardadas también están mal:
#   → Seleccionar: 4 (Clear all rules) para limpiar
#   → Salir y ejecutar ./iptables.rules.sh nuevamente
#   → Volver y seleccionar: 5 (Save current rules)
```

### Limpieza Completa del Sistema

**Escenario**: Necesitas desinstalar completamente la configuración de iptables.

```bash
sudo ./ipp.sh
# → Seleccionar: 4 (Clear all rules) para limpiar reglas activas
# → Seleccionar: 7 (Clear saved rules file) para limpiar archivo
# → Seleccionar: 2 (Remove iptables-persistent) para desinstalar
# → Seleccionar: 0 (Exit)
```

## Integración con la Suite

### Flujo de Trabajo con iptables.rules.sh

```bash
# 1. Configurar .env según tus necesidades
nano .env

# 2. Aplicar reglas específicas de L4D2
sudo ./iptables.rules.sh

# 3. Gestionar persistencia
sudo ./ipp.sh
# Usar opciones 1 y 5 para hacer reglas persistentes
```

### Coordinación con iptable.loggin.py

```bash
# Después de configurar logging
sudo python3 iptable.loggin.py  # Configurar rsyslog

# Verificar que las reglas están activas
sudo ./ipp.sh  # Opción 3: Show current rules
```

### Automatización con Scripts

```bash
#!/bin/bash
# Script de deployment automatizado

# Aplicar configuración
sudo ./iptables.rules.sh

# Hacer persistente automáticamente
sudo ./ipp.sh <<EOF
1
5
0
EOF
```

## Troubleshooting

### Problemas Comunes

#### iptables-persistent no se instala

**Síntomas**:
```
E: Unable to locate package iptables-persistent
```

**Causa**: Repositorios desactualizados o distribución no soportada.

**Solución**:
```bash
# Actualizar repositorios
sudo apt update

# Para distribuciones más antiguas, instalar netfilter-persistent
sudo apt install netfilter-persistent iptables-persistent

# Verificar instalación
dpkg -l | grep persistent
```

#### Archivo de reglas no se guarda

**Síntomas**:
```
❌ No saved rules file found at /etc/iptables/rules.v4
```

**Causa**: Permisos insuficientes o directorio no creado.

**Solución**:
```bash
# Verificar/crear directorio
sudo mkdir -p /etc/iptables

# Verificar permisos
sudo ls -la /etc/iptables/

# Intentar guardar manualmente
sudo iptables-save > /tmp/test-rules.v4
sudo mv /tmp/test-rules.v4 /etc/iptables/rules.v4
sudo chmod 644 /etc/iptables/rules.v4
```

#### Reglas no persisten después del reinicio

**Síntomas**: Después de reiniciar, las reglas de iptables vuelven a estar vacías.

**Diagnóstico**:
```bash
# Verificar estado del servicio
sudo systemctl status iptables-persistent
# o en sistemas más nuevos:
sudo systemctl status netfilter-persistent

# Verificar archivo de reglas
sudo cat /etc/iptables/rules.v4
```

**Solución**:
```bash
# Habilitar servicio si está deshabilitado
sudo systemctl enable netfilter-persistent

# Reiniciar servicio
sudo systemctl restart netfilter-persistent

# Verificar que las reglas se cargan
sudo ./ipp.sh  # Opción 9: Status
```

#### Script termina con error de permisos

**Síntomas**:
```
❌ This script must be run as root or with sudo.
```

**Solución**:
```bash
# Siempre ejecutar con sudo
sudo ./ipp.sh

# Verificar que tienes permisos sudo
sudo -l
```

#### Reglas se muestran vacías después de aplicar iptables.rules.sh

**Síntomas**: El script `iptables.rules.sh` ejecuta sin errores, pero `ipp.sh` muestra 0 reglas.

**Diagnóstico**:
```bash
# Verificar si hay errores en iptables.rules.sh
sudo ./iptables.rules.sh 2>&1 | tee /tmp/iptables-debug.log

# Verificar configuración .env
cat .env | grep -v "^#" | grep -v "^$"

# Verificar directamente con iptables
sudo iptables -L -n -v
```

**Solución**:
```bash
# Verificar que .env está en el directorio correcto
ls -la .env

# Regenerar .env si es necesario
cp example.env .env
nano .env  # Configurar según tus necesidades

# Reaplicar reglas
sudo ./iptables.rules.sh
```

### Verificación del Estado del Sistema

#### Script de Diagnóstico Completo

```bash
#!/bin/bash
echo "=== DIAGNÓSTICO IPP.SH ==="

echo "1. Verificando permisos..."
[ "$(id -u)" -eq 0 ] && echo "✅ Ejecutándose como root" || echo "❌ NO ejecutándose como root"

echo "2. Verificando iptables-persistent..."
dpkg -l | grep -q iptables-persistent && echo "✅ iptables-persistent instalado" || echo "❌ iptables-persistent NO instalado"

echo "3. Verificando servicio..."
systemctl is-active netfilter-persistent >/dev/null 2>&1 && echo "✅ Servicio activo" || echo "❌ Servicio NO activo"

echo "4. Verificando directorio de reglas..."
[ -d "/etc/iptables" ] && echo "✅ Directorio existe" || echo "❌ Directorio NO existe"

echo "5. Verificando archivo de reglas..."
[ -f "/etc/iptables/rules.v4" ] && echo "✅ Archivo de reglas existe" || echo "❌ Archivo de reglas NO existe"

echo "6. Contando reglas guardadas..."
if [ -f "/etc/iptables/rules.v4" ]; then
    count=$(grep -c '^-A' /etc/iptables/rules.v4 2>/dev/null || echo 0)
    echo "📊 Reglas guardadas: $count"
else
    echo "📊 Reglas guardadas: 0 (archivo no existe)"
fi

echo "7. Contando reglas activas..."
count=$(iptables -S | wc -l)
echo "📊 Reglas activas: $count"
```

#### Comandos de Verificación Manual

```bash
# Estado completo del sistema
sudo systemctl status netfilter-persistent

# Contenido del archivo de reglas
sudo cat /etc/iptables/rules.v4

# Reglas actualmente en memoria
sudo iptables -S

# Logs del sistema relacionados con iptables
sudo journalctl -u netfilter-persistent --no-pager

# Verificar que el servicio se inicia automáticamente
sudo systemctl is-enabled netfilter-persistent
```

### Integración con Otros Servicios

#### Conflictos con Docker

Si tienes Docker instalado, puede haber conflictos con las reglas de iptables:

```bash
# Ver reglas de Docker
sudo iptables -t nat -L DOCKER

# Reiniciar Docker después de cambios en iptables
sudo systemctl restart docker

# Verificar que Docker no ha sobrescrito tus reglas
sudo ./ipp.sh  # Opción 3: Show current rules
```

#### Conflictos con UFW

Si tienes UFW (Uncomplicated Firewall) habilitado:

```bash
# Deshabilitar UFW temporalmente
sudo ufw disable

# Aplicar reglas L4D2
sudo ./iptables.rules.sh
sudo ./ipp.sh  # Guardar reglas

# UFW puede interferir, considera mantenerlo deshabilitado
# o configurar exclusiones específicas
```

---

## Enlaces Relacionados

- [README Principal](../README.md)
- [Documentación iptables.rules.sh](iptables.rules.md)
- [Documentación iptable.loggin.py](iptable.loggin.md)
- [Archivo de Configuración example.env](../example.env)

---

*Documentación actualizada para L4D2 IPTables Suite v2.4*
