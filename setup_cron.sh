#!/bin/bash
# =============================================================================
# Setup script per cron job - Esegue il monitor ogni ora
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="${PYTHON_PATH:-python3}"
LOG_FILE="${SCRIPT_DIR}/monitor.log"

echo "🔧 Setup Webpage Monitor Cron Job"
echo "================================="
echo ""
echo "Directory script: ${SCRIPT_DIR}"
echo "Python: ${PYTHON_PATH}"
echo "Log file: ${LOG_FILE}"
echo ""

# Verifica che config.yaml esista
if [ ! -f "${SCRIPT_DIR}/config.yaml" ]; then
    echo "❌ config.yaml non trovato!"
    echo "   Copia config.example.yaml in config.yaml e configuralo."
    exit 1
fi

# Crea la riga cron
CRON_CMD="0 * * * * cd ${SCRIPT_DIR} && ${PYTHON_PATH} monitor.py >> ${LOG_FILE} 2>&1"

echo "Riga cron da aggiungere:"
echo ""
echo "  ${CRON_CMD}"
echo ""

read -p "Vuoi aggiungere automaticamente al crontab? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Rimuovi vecchie entry di questo monitor
    (crontab -l 2>/dev/null | grep -v "webpage_monitor/monitor.py") | crontab -
    
    # Aggiungi nuova entry
    (crontab -l 2>/dev/null; echo "${CRON_CMD}") | crontab -
    
    echo ""
    echo "✅ Cron job aggiunto! Il monitor verrà eseguito ogni ora."
    echo ""
    echo "Crontab attuale:"
    crontab -l | grep -A1 -B1 "monitor.py" || echo "(nessuna entry trovata)"
else
    echo ""
    echo "ℹ️  Per aggiungere manualmente, esegui:"
    echo "   crontab -e"
    echo ""
    echo "   E aggiungi la riga:"
    echo "   ${CRON_CMD}"
fi

echo ""
echo "📋 Comandi utili:"
echo "   - Vedere i log: tail -f ${LOG_FILE}"
echo "   - Test notifiche: python3 monitor.py --test"
echo "   - Reset stato: python3 monitor.py --reset"
echo "   - Eseguire manualmente: python3 monitor.py"

