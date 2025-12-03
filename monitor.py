#!/usr/bin/env python3
"""
Webpage Monitor
===============
Monitora pagine web per aggiornamenti e invia notifiche.

Uso:
    python monitor.py              # Esegue tutti i monitor
    python monitor.py --test       # Testa le notifiche
    python monitor.py --reset      # Resetta lo stato (forza nuovo controllo)
"""

import argparse
import json
import os
import re
import smtplib
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup


# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CONFIG_FILE = SCRIPT_DIR / "config.yaml"
DEFAULT_STATE_FILE = SCRIPT_DIR / "state.json"


def load_config(config_path: Path = DEFAULT_CONFIG_FILE) -> dict:
    """Carica la configurazione da file YAML."""
    if not config_path.exists():
        print(f"❌ File di configurazione non trovato: {config_path}")
        print(f"   Copia config.example.yaml in config.yaml e configuralo")
        sys.exit(1)
    
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# =============================================================================
# NOTIFICHE
# =============================================================================

class Notifier:
    """Gestisce l'invio di notifiche su più canali."""
    
    def __init__(self, config: dict):
        self.config = config.get("notifications", {})
    
    def send(self, title: str, message: str, url: str | None = None, ntfy_topic: str | None = None) -> None:
        """Invia notifica su tutti i canali abilitati."""
        print(f"\n🔔 {title}: {message}")
        
        if self.config.get("email", {}).get("enabled"):
            self._send_email(title, message, url)
        
        if self.config.get("telegram", {}).get("enabled"):
            self._send_telegram(title, message, url)
        
        if self.config.get("ntfy", {}).get("enabled"):
            self._send_ntfy(title, message, url, ntfy_topic)
    
    def _send_email(self, title: str, message: str, url: str | None) -> None:
        """Invia notifica via email."""
        cfg = self.config["email"]
        try:
            msg = MIMEMultipart()
            msg["From"] = cfg["from_address"]
            msg["To"] = ", ".join(cfg["to_addresses"])
            msg["Subject"] = f"[Monitor] {title}"
            
            body = f"{message}\n"
            if url:
                body += f"\nLink: {url}"
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
                if cfg.get("use_tls", True):
                    server.starttls()
                server.login(cfg["username"], cfg["password"])
                server.send_message(msg)
            
            print("   ✉️  Email inviata")
        except Exception as e:
            print(f"   ❌ Errore email: {e}")
    
    def _send_telegram(self, title: str, message: str, url: str | None) -> None:
        """Invia notifica via Telegram."""
        cfg = self.config["telegram"]
        try:
            text = f"*{title}*\n{message}"
            if url:
                text += f"\n\n[Apri link]({url})"
            
            for chat_id in cfg["chat_ids"]:
                response = requests.post(
                    f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": False
                    },
                    timeout=10
                )
                response.raise_for_status()
            
            print("   📱 Telegram inviato")
        except Exception as e:
            print(f"   ❌ Errore Telegram: {e}")
    
    def _send_ntfy(self, title: str, message: str, url: str | None, topic: str | None = None) -> None:
        """Invia push notification via ntfy.sh."""
        cfg = self.config["ntfy"]
        # Usa topic specifico del monitor, oppure default
        topic = topic or cfg.get("default_topic") or cfg.get("topic")
        
        if not topic:
            print("   ⚠️  Nessun topic ntfy configurato")
            return
        
        try:
            headers = {
                "Title": title,
                "Priority": "high",
                "Tags": "bell"
            }
            if url:
                headers["Click"] = url
                headers["Actions"] = f"view, Apri, {url}"
            
            response = requests.post(
                f"{cfg['server']}/{topic}",
                data=message.encode("utf-8"),
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            print(f"   📲 Push notification inviata (topic: {topic})")
        except Exception as e:
            print(f"   ❌ Errore ntfy: {e}")


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class StateManager:
    """Gestisce lo stato persistente dei monitor."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load()
    
    def _load(self) -> dict:
        """Carica lo stato dal file."""
        if self.state_file.exists():
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {}
    
    def save(self) -> None:
        """Salva lo stato su file."""
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def get(self, monitor_id: str) -> dict:
        """Ottiene lo stato di un monitor."""
        return self.state.get(monitor_id, {})
    
    def set(self, monitor_id: str, data: dict) -> None:
        """Imposta lo stato di un monitor."""
        self.state[monitor_id] = data
    
    def get_error_count(self, monitor_id: str) -> int:
        """Ottiene il contatore errori di un monitor."""
        return self.state.get(f"{monitor_id}_errors", 0)
    
    def increment_error(self, monitor_id: str) -> int:
        """Incrementa il contatore errori e ritorna il nuovo valore."""
        key = f"{monitor_id}_errors"
        self.state[key] = self.state.get(key, 0) + 1
        return self.state[key]
    
    def reset_errors(self, monitor_id: str) -> None:
        """Resetta il contatore errori."""
        self.state[f"{monitor_id}_errors"] = 0
    
    def reset_all(self) -> None:
        """Resetta tutto lo stato."""
        self.state = {}
        self.save()


# =============================================================================
# MONITORS
# =============================================================================

def fetch_page(url: str, user_agent: str, max_retries: int = 3, retry_delay: int = 30) -> BeautifulSoup | None:
    """Scarica e parsa una pagina web con retry."""
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": user_agent},
                timeout=30
            )
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                print(f"   ⚠️  Tentativo {attempt + 1}/{max_retries} fallito, riprovo tra {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise e
    return None


def check_one_piece(soup: BeautifulSoup, state: dict) -> tuple[bool, dict, str | None]:
    """
    Controlla nuovi capitoli di One Piece.
    
    Returns:
        (has_update, new_state, url)
    """
    one_piece_links = []
    
    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True)
        # Cerca specificamente "One Piece" + "Chapter" ma esclude spin-off
        if "One Piece" in text and "Chapter" in text:
            # Esclude varianti come "Nami vs Kalifa"
            if "by Boichi" in text or "Spin" in text.lower():
                continue
            
            match = re.search(r"Chapter\s*(\d+)", text)
            if match:
                chapter_num = int(match.group(1))
                href = link["href"]
                if not href.startswith("http"):
                    href = urllib.parse.urljoin("https://tcbonepiecechapters.com/", href)
                one_piece_links.append({
                    "chapter": chapter_num,
                    "title": text,
                    "url": href
                })
    
    if not one_piece_links:
        raise ValueError("Nessun capitolo One Piece trovato nella pagina")
    
    latest = max(one_piece_links, key=lambda x: x["chapter"])
    previous_chapter = state.get("chapter")
    
    new_state = {
        "chapter": latest["chapter"],
        "title": latest["title"],
        "url": latest["url"],
        "last_check": datetime.now().isoformat()
    }
    
    has_update = previous_chapter is not None and latest["chapter"] > previous_chapter
    
    return has_update, new_state, latest["url"] if has_update else None


def check_wtc_terrain(soup: BeautifulSoup, state: dict, config: dict, settings: dict) -> tuple[bool, dict, str | None]:
    """
    Controlla aggiornamenti del WTC Terrain Map Pack.
    
    Returns:
        (has_update, new_state, url)
    """
    page_text = soup.get_text()
    
    # Cerca info sul Terrain Map Pack
    terrain_match = re.search(
        r"Terrain Map Pack[^\n]*?\((\d+\.?\d*)\)[^\n]*?Last update[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
        page_text,
        re.I | re.DOTALL
    )
    
    if not terrain_match:
        # Prova pattern alternativo
        version_match = re.search(r"Terrain Map Pack[^\n]*?\((\d+\.?\d*)\)", page_text, re.I)
        date_match = re.search(r"Terrain Map Pack[\s\S]*?Last update[:\s]*(\d{1,2}/\d{1,2}/\d{4})", page_text, re.I)
        
        if not date_match:
            raise ValueError("Info WTC Terrain Map Pack non trovate nella pagina")
        
        version = version_match.group(1) if version_match else None
        last_update = date_match.group(1)
    else:
        version = terrain_match.group(1)
        last_update = terrain_match.group(2)
    
    # Cerca il link al PDF
    pdf_url = None
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True)
        # Cerca link che contengono "terrain" e sono PDF
        if "terrain" in href.lower() or "terrain" in text.lower():
            if href.endswith(".pdf") or "pdf" in href.lower():
                pdf_url = href
                if not pdf_url.startswith("http"):
                    pdf_url = urllib.parse.urljoin("https://worldteamchampionship.com/", pdf_url)
                break
    
    previous_update = state.get("last_update")
    previous_version = state.get("version")
    
    new_state = {
        "version": version,
        "last_update": last_update,
        "pdf_url": pdf_url,
        "last_check": datetime.now().isoformat()
    }
    
    has_update = (
        previous_update is not None and 
        (last_update != previous_update or version != previous_version)
    )
    
    # Se c'è un aggiornamento e il download è abilitato
    if has_update and config.get("download_pdf") and pdf_url:
        download_and_compress_pdf(pdf_url, version, settings)
    
    return has_update, new_state, "https://worldteamchampionship.com/wtc-rules/"


def download_and_compress_pdf(url: str, version: str | None, settings: dict) -> None:
    """Scarica e comprime il PDF del Terrain Map Pack."""
    download_dir = Path(settings.get("download_dir", "./downloads"))
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Nome file
    version_str = f"-v{version}" if version else ""
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"WTC_Terrain_Map_Pack{version_str}_{timestamp}.pdf"
    filepath = download_dir / filename
    compressed_path = download_dir / f"WTC_Terrain_Map_Pack{version_str}_{timestamp}-compressed.pdf"
    
    print(f"\n   📥 Download PDF: {url}")
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        print(f"   ✅ Salvato: {filepath}")
        
        # Comprimi con ghostscript
        print(f"   🗜️  Compressione in corso...")
        result = subprocess.run(
            [
                "gs",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/screen",
                "-dNOPAUSE",
                "-dBATCH",
                f"-sOutputFile={compressed_path}",
                str(filepath)
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            original_size = filepath.stat().st_size / 1024 / 1024
            compressed_size = compressed_path.stat().st_size / 1024 / 1024
            print(f"   ✅ Compresso: {compressed_path}")
            print(f"      {original_size:.1f}MB → {compressed_size:.1f}MB ({(1 - compressed_size/original_size)*100:.0f}% riduzione)")
        else:
            print(f"   ⚠️  Errore compressione: {result.stderr}")
            
    except Exception as e:
        print(f"   ❌ Errore download/compressione: {e}")


# =============================================================================
# MAIN
# =============================================================================

def run_monitor(
    monitor_id: str,
    monitor_config: dict,
    settings: dict,
    state_manager: StateManager,
    notifier: Notifier
) -> None:
    """Esegue un singolo monitor."""
    name = monitor_config.get("name", monitor_id)
    url = monitor_config["url"]
    monitor_type = monitor_config["type"]
    ntfy_topic = monitor_config.get("ntfy_topic")  # Topic specifico del monitor
    
    print(f"\n📡 {name}...")
    
    try:
        soup = fetch_page(
            url,
            settings.get("user_agent", "Mozilla/5.0"),
            settings.get("max_retries", 3),
            settings.get("retry_delay", 30)
        )
        
        current_state = state_manager.get(monitor_id)
        
        if monitor_type == "one_piece":
            has_update, new_state, link = check_one_piece(soup, current_state)
            if has_update:
                notifier.send(
                    "🏴‍☠️ Nuovo Capitolo One Piece!",
                    f"Capitolo {new_state['chapter']} disponibile!",
                    link,
                    ntfy_topic=ntfy_topic
                )
            else:
                status = f"Cap. {new_state['chapter']}" if new_state.get('chapter') else "N/A"
                print(f"   ✓ Nessun aggiornamento (ultimo: {status})")
        
        elif monitor_type == "wtc_terrain":
            has_update, new_state, link = check_wtc_terrain(
                soup, current_state, monitor_config, settings
            )
            if has_update:
                version_str = f"v{new_state['version']}" if new_state.get('version') else ""
                notifier.send(
                    "🗺️ WTC Terrain Map Pack Aggiornato!",
                    f"Nuova versione {version_str} del {new_state['last_update']}",
                    link,
                    ntfy_topic=ntfy_topic
                )
            else:
                version_str = f"v{new_state['version']}" if new_state.get('version') else ""
                print(f"   ✓ Nessun aggiornamento ({version_str}, {new_state.get('last_update', 'N/A')})")
        
        else:
            print(f"   ⚠️  Tipo monitor sconosciuto: {monitor_type}")
            return
        
        # Salva nuovo stato e resetta errori
        state_manager.set(monitor_id, new_state)
        state_manager.reset_errors(monitor_id)
        
    except Exception as e:
        error_count = state_manager.increment_error(monitor_id)
        max_retries = settings.get("max_retries", 3)
        
        if error_count > max_retries:
            notifier.send(
                f"❌ Errore Monitor: {name}",
                f"Errore dopo {error_count} tentativi: {str(e)[:100]}",
                url,
                ntfy_topic=ntfy_topic
            )
        else:
            print(f"   ⚠️  Errore ({error_count}/{max_retries + 1}): {e}")


def main():
    parser = argparse.ArgumentParser(description="Webpage Monitor")
    parser.add_argument("--config", "-c", type=Path, default=DEFAULT_CONFIG_FILE,
                        help="Path al file di configurazione")
    parser.add_argument("--test", action="store_true",
                        help="Invia notifica di test")
    parser.add_argument("--reset", action="store_true",
                        help="Resetta lo stato di tutti i monitor")
    args = parser.parse_args()
    
    # Carica configurazione
    config = load_config(args.config)
    settings = config.get("settings", {})
    
    # Inizializza componenti
    state_file = Path(settings.get("state_file", DEFAULT_STATE_FILE))
    if not state_file.is_absolute():
        state_file = SCRIPT_DIR / state_file
    
    state_manager = StateManager(state_file)
    notifier = Notifier(config)
    
    # Modalità test
    if args.test:
        print("🧪 Test notifiche...")
        
        # Testa ogni topic configurato nei monitor
        monitors = config.get("monitors", {})
        tested_topics = set()
        
        for monitor_id, monitor_cfg in monitors.items():
            if not monitor_cfg.get("enabled", True):
                continue
            topic = monitor_cfg.get("ntfy_topic")
            if topic and topic not in tested_topics:
                notifier.send(
                    f"🧪 Test: {monitor_cfg.get('name', monitor_id)}",
                    "Se ricevi questo messaggio, le notifiche funzionano!",
                    "https://example.com",
                    ntfy_topic=topic
                )
                tested_topics.add(topic)
        
        # Testa anche il topic di default se esiste e non è già testato
        default_topic = config.get("notifications", {}).get("ntfy", {}).get("default_topic")
        if default_topic and default_topic not in tested_topics:
            notifier.send(
                "🧪 Test: Default",
                "Se ricevi questo messaggio, le notifiche funzionano!",
                "https://example.com",
                ntfy_topic=default_topic
            )
        
        return
    
    # Reset stato
    if args.reset:
        state_manager.reset_all()
        print("🔄 Stato resettato")
        return
    
    # Esegui monitors
    print("=" * 60)
    print(f"🔍 Webpage Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    monitors = config.get("monitors", {})
    
    for monitor_id, monitor_config in monitors.items():
        if not monitor_config.get("enabled", True):
            continue
        
        run_monitor(monitor_id, monitor_config, settings, state_manager, notifier)
    
    # Salva stato
    state_manager.save()
    
    print("\n" + "=" * 60)
    print("✅ Controllo completato")


if __name__ == "__main__":
    main()
