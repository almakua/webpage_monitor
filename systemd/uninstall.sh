#!/bin/bash
# =============================================================================
# Disinstallazione Webpage Monitor
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="/opt/webpage-monitor"

echo -e "${YELLOW}=========================================${NC}"
echo -e "${YELLOW}  Webpage Monitor - Disinstallazione${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Esegui come root: sudo ./uninstall.sh${NC}"
    exit 1
fi

read -p "Sei sicuro di voler disinstallare? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Annullato."
    exit 0
fi

echo -e "${GREEN}[1/3]${NC} Stop e rimozione servizio..."
systemctl stop webpage-monitor.timer 2>/dev/null || true
systemctl disable webpage-monitor.timer 2>/dev/null || true
rm -f /etc/systemd/system/webpage-monitor.service
rm -f /etc/systemd/system/webpage-monitor.timer
systemctl daemon-reload

echo -e "${GREEN}[2/3]${NC} Rimozione file..."
rm -rf "${INSTALL_DIR}"

read -p "Rimuovere anche i log? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}[3/3]${NC} Rimozione log..."
    rm -rf /var/log/webpage-monitor
fi

echo ""
echo -e "${GREEN}✅ Disinstallazione completata${NC}"

