# 📡 Webpage Monitor

Monitora pagine web per aggiornamenti e invia push notification via [ntfy.sh](https://ntfy.sh).

## Monitoraggi Attivi

| Sito | Cosa monitora |
|------|---------------|
| [TCB Scans](https://tcbonepiecechapters.com/) | Nuovi capitoli di One Piece |
| [WTC Rules](https://worldteamchampionship.com/wtc-rules/) | Aggiornamenti WTC Terrain Map Pack |

## 🚀 Setup

### 1. Installa dipendenze

```bash
pip install -r requirements.txt

# Per compressione PDF (Ubuntu/Debian)
sudo apt install ghostscript
```

### 2. Setup notifiche (ntfy.sh)

1. Installa l'app **ntfy** sul telefono:
   - [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - [iOS](https://apps.apple.com/app/ntfy/id1625396347)

2. Scegli i topic per ogni monitor (es. `marco-onepiece`, `marco-wtc`)

3. Nell'app, sottoscrivi i topic che vuoi ricevere

### 3. Configura

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Ogni monitor ha il suo topic ntfy:

```yaml
notifications:
  ntfy:
    enabled: true
    server: "https://ntfy.sh"
    default_topic: "marco-monitor"  # fallback

monitors:
  one_piece:
    ntfy_topic: "marco-onepiece"    # topic dedicato
  wtc_terrain:
    ntfy_topic: "marco-wtc"         # topic dedicato
```

💡 **Tip**: Puoi sottoscrivere solo i topic che ti interessano!

### 4. Testa

```bash
python3 monitor.py --test
```

Dovresti ricevere una notifica sul telefono! 📱

### 5. Attiva esecuzione automatica (ogni ora)

**Opzione A: Systemd (consigliato per server)**

```bash
# Crea config.yaml prima!
cp config.example.yaml config.yaml
nano config.yaml

# Installa
sudo ./systemd/install.sh
```

**Opzione B: Cron**

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## 🛠️ Comandi

```bash
python3 monitor.py           # Esegui controllo (una volta)
python3 monitor.py --daemon  # Esegui in loop continuo
python3 monitor.py --test    # Testa notifiche
python3 monitor.py --reset   # Resetta stato
```

## 🐳 Docker

### Build e push dell'immagine

```bash
# Build
docker build -t webpage-monitor .

# Tag per il registry (Docker Hub)
docker tag webpage-monitor alm4kua/webpage-monitor:latest

# Push
docker login
docker push alm4kua/webpage-monitor:latest
```

### Esecuzione sul server

```bash
# 1. Crea directory config
mkdir -p ~/webpage-monitor
cd ~/webpage-monitor

# 2. Crea config.yaml
cat > config.yaml << 'EOF'
notifications:
  ntfy:
    enabled: true
    server: "https://ntfy.sh"
    default_topic: "tuo-topic-default"

scheduler:
  interval_minutes: 60          # Controlla ogni ora
  randomize_delay: true         # Delay casuale 0-5 min
  max_random_delay_minutes: 5

monitors:
  one_piece:
    enabled: true
    name: "One Piece (TCB Scans)"
    url: "https://tcbonepiecechapters.com/"
    type: "one_piece"
    ntfy_topic: "tuo-topic-onepiece"

  wtc_terrain:
    enabled: true
    name: "WTC Terrain Map Pack"
    url: "https://worldteamchampionship.com/wtc-rules/"
    type: "wtc_terrain"
    download_pdf: true
    compress_pdf: true
    ntfy_topic: "tuo-topic-wtc"

settings:
  download_dir: "/config/downloads"
  state_file: "/config/state.json"
EOF

# 3. Pull immagine
docker pull alm4kua/webpage-monitor:latest

# 4. Test notifiche
docker run --rm -v $(pwd):/config alm4kua/webpage-monitor:latest --test

# 5. Avvia in background (daemon mode)
docker run -d \
  --name webpage-monitor \
  --restart unless-stopped \
  -v $(pwd):/config \
  alm4kua/webpage-monitor:latest
```

### Comandi Docker

```bash
# Vedi log
docker logs -f webpage-monitor

# Esecuzione singola (senza daemon)
docker run --rm -v $(pwd):/config alm4kua/webpage-monitor:latest --config /config/config.yaml

# Stop / Riavvia
docker stop webpage-monitor
docker restart webpage-monitor

# Rimuovi container
docker rm -f webpage-monitor
```

### Docker Compose (consigliato)

Crea `docker-compose.yaml`:

```yaml
services:
  monitor:
    image: alm4kua/webpage-monitor:latest
    container_name: webpage-monitor
    restart: unless-stopped
    volumes:
      - ./:/config
```

Comandi:

```bash
docker compose up -d                      # Avvia daemon
docker compose logs -f                    # Vedi log
docker compose down                       # Stop
docker compose restart                    # Riavvia
docker compose run --rm monitor --test    # Test notifiche
```

### Modifica configurazione a caldo

Il config viene ricaricato ad ogni ciclo! Modifica `config.yaml` e le modifiche saranno applicate al prossimo controllo.

## 🖥️ Systemd (Server Linux)

**Installazione:**
```bash
sudo ./systemd/install.sh
```

**Comandi utili:**
```bash
sudo systemctl status webpage-monitor.timer   # Stato timer
sudo systemctl list-timers                    # Prossima esecuzione
sudo systemctl start webpage-monitor          # Esegui subito
sudo journalctl -u webpage-monitor -f         # Log systemd
tail -f /var/log/webpage-monitor/monitor.log  # Log applicazione
```

**Disinstallazione:**
```bash
sudo ./systemd/uninstall.sh
```

## ➕ Aggiungere Nuovi Monitor

Aggiungi in `config.yaml`:

```yaml
monitors:
  mio_monitor:
    enabled: true
    name: "Nome Monitor"
    url: "https://example.com"
    type: "one_piece"  # o "wtc_terrain"
```

## 📁 File

```
├── monitor.py           # Script principale
├── config.yaml          # Configurazione
├── state.json           # Stato (auto)
├── downloads/           # PDF scaricati (auto)
├── monitor.log          # Log cron
├── Dockerfile           # Container image
├── .dockerignore
└── systemd/
    ├── install.sh       # Script installazione
    ├── uninstall.sh     # Script disinstallazione
    ├── webpage-monitor.service
    └── webpage-monitor.timer
```

## 🐛 Troubleshooting

**Non ricevo notifiche**: Verifica che il topic nel config corrisponda a quello sottoscritto nell'app.

**Ghostscript non trovato**: `sudo apt install ghostscript`

**Vedere i log**: `tail -f monitor.log`
