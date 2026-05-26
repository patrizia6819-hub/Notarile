# config.py - OTTIMIZZATO E PULITO
import os
import sqlite3
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "prima_nota.db")
CARTELLA_PDF = os.path.join(BASE_DIR, "PDF_PRATICHE")

OPZIONI_PAGAMENTO = ["BONIFICO", "ASSEGNO", "CONTANTI", "CARTA", "POS"]

if not os.path.exists(CARTELLA_PDF):
    os.makedirs(CARTELLA_PDF)

def inizializza_db():
    """Crea le tabelle del database se non esistono"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pratiche (
                repertorio TEXT PRIMARY KEY,
                data_atto TEXT,
                fascicolo TEXT,
                oggetto TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clienti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repertorio TEXT,
                nome_cliente TEXT,
                num_fattura TEXT,
                FOREIGN KEY(repertorio) REFERENCES pratiche(repertorio) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repertorio TEXT,
                tipo_movimento TEXT,
                data_mov TEXT,
                importo REAL,
                modalita TEXT,
                cliente_libero TEXT,
                descrizione_libera TEXT,
                num_fattura TEXT,
                FOREIGN KEY(repertorio) REFERENCES pratiche(repertorio) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fatture_studio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repertorio TEXT,
                num_fattura TEXT,
                data_fattura TEXT,
                importo REAL,
                nome_cliente TEXT,
                FOREIGN KEY(repertorio) REFERENCES pratiche(repertorio) ON DELETE CASCADE
            )
        """)
        conn.commit()

def formatta_singola_data(valore):
    """Converte date da vari formati a GG/MM/AAAA
    
    Supporta:
    - 240526 -> 24/05/2026 (numerico 6 cifre)
    - 24052026 -> 24/05/2026 (numerico 8 cifre)
    - 24/05/26 -> 24/05/2026 (con separatori, anno 2 cifre)
    - 2026/05/24 -> 24/05/2026 (formato DB YYYY/MM/DD)
    """
    if not valore:
        return ""
    
    valore = str(valore).strip()
    
    # CASO 1: Numerico puro senza separatori
    if valore.isdigit():
        if len(valore) == 6:  # GGMMAA
            return f"{valore[0:2]}/{valore[2:4]}/20{valore[4:6]}"
        elif len(valore) == 8:  # GGMMAAAA
            return f"{valore[0:2]}/{valore[2:4]}/{valore[4:8]}"
    
    # Standardizza separatori
    valore = valore.replace("-", "/").replace(".", "/")
    
    parti = valore.split("/")
    if len(parti) == 3:
        # CASO 2: Formato DB YYYY/MM/DD -> GG/MM/AAAA
        if len(parti[0]) == 4:
            return f"{parti[2]}/{parti[1]}/{parti[0]}"
        # CASO 3: Inserimento manuale GG/MM/AA -> GG/MM/AAAA
        elif len(parti[2]) == 2:
            return f"{parti[0]}/{parti[1]}/20{parti[2]}"
    
    return valore

def formatta_singolo_importo(valore):
    """Converte importi da vari formati a float
    
    Supporta:
    - "1.234,50" -> 1234.50 (formato europeo)
    - "1,234.50" -> 1234.50 (formato US)
    - "€ 1234,50" -> 1234.50 (con simbolo)
    """
    if not valore:
        return 0.0
    try:
        valore = str(valore).replace("€", "").replace(" ", "").strip()
        
        # Se ha entrambi i separatori, è formato europeo
        if "," in valore and "." in valore:
            valore = valore.replace(".", "")
        
        valore = valore.replace(",", ".")
        return float(valore)
    except ValueError:
        return 0.0

def mostra_euro(valore):
    """Formatta un numero come valuta EUR in stile europeo
    
    Esempio: 1234.5 -> "€ 1.234,50"
    """
    try:
        valore_float = float(valore)
        # Formatta con separatore di migliaia e 2 decimali
        formattato = f"{valore_float:,.2f}"
        # Inverte separatori: , <-> .
        formattato = formattato.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€ {formattato}"
    except (ValueError, TypeError):
        return "€ 0,00"
