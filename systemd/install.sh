#!/bin/bash
# =============================================================================
# Installazione Webpage Monitor come servizio systemd
# =============================================================================

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/webpage-monitor"
SERVICE_USER="${SUDO_USER:-$USER}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Webpage Monitor - Installazione${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Verifica root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Esegui come root: sudo ./install.sh${NC}"
    exit 1
fi

# Verifica config.yaml
if [ ! -f "${SCRIPT_DIR}/config.yaml" ]; then
    echo -e "${RED}❌ config.yaml non trovato!${NC}"
    echo "   Crea il file di configurazione prima di installare:"
    echo "   cp config.example.yaml config.yaml"
    echo "   nano config.yaml"
    exit 1
fi

echo -e "${YELLOW}📁 Directory installazione:${NC} ${INSTALL_DIR}"
echo -e "${YELLOW}👤 Utente:${NC} ${SERVICE_USER}"
echo ""

# 1. Installa dipendenze sistema
echo -e "${GREEN}[1/6]${NC} Installazione dipendenze sistema..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip ghostscript > /dev/null

# 2. Crea directory
echo -e "${GREEN}[2/6]${NC} Creazione directory..."
mkdir -p "${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/downloads"
mkdir -p /var/log/webpage-monitor

# 3. Copia file
echo -e "${GREEN}[3/6]${NC} Copia file..."
cp "${SCRIPT_DIR}/monitor.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

# 4. Installa dipendenze Python
echo -e "${GREEN}[4/6]${NC} Installazione dipendenze Python..."
pip3 install -q -r "${INSTALL_DIR}/requirements.txt"

# 5. Imposta permessi
echo -e "${GREEN}[5/6]${NC} Configurazione permessi..."
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" /var/log/webpage-monitor
chmod 750 "${INSTALL_DIR}"
chmod 640 "${INSTALL_DIR}/config.yaml"

# 6. Installa servizio systemd
echo -e "${GREEN}[6/6]${NC} Installazione servizio systemd..."

# Crea service file con utente corretto
cat > /etc/systemd/system/webpage-monitor.service << EOF
[Unit]
Description=Webpage Monitor - Controlla aggiornamenti One Piece e WTC
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/monitor.py
StandardOutput=append:/var/log/webpage-monitor/monitor.log
StandardError=append:/var/log/webpage-monitor/monitor.log
TimeoutStartSec=300
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}
ReadWritePaths=/var/log/webpage-monitor
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Copia timer
cp "${SCRIPT_DIR}/systemd/webpage-monitor.timer" /etc/systemd/system/

# Reload e abilita
systemctl daemon-reload
systemctl enable webpage-monitor.timer
systemctl start webpage-monitor.timer

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  ✅ Installazione completata!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "Il monitor verrà eseguito ${YELLOW}ogni ora${NC}."
echo ""
echo -e "${YELLOW}Comandi utili:${NC}"
echo "  sudo systemctl status webpage-monitor.timer  # Stato timer"
echo "  sudo systemctl list-timers                   # Lista timer"
echo "  sudo systemctl start webpage-monitor         # Esegui ora"
echo "  sudo journalctl -u webpage-monitor -f        # Log systemd"
echo "  tail -f /var/log/webpage-monitor/monitor.log # Log applicazione"
echo ""
echo -e "${YELLOW}Test notifiche:${NC}"
echo "  cd ${INSTALL_DIR} && python3 monitor.py --test"
echo ""
echo -e "${YELLOW}Modifica configurazione:${NC}"
echo "  sudo nano ${INSTALL_DIR}/config.yaml"
echo ""

