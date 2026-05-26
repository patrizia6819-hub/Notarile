# ocr_worker.py - OTTIMIZZATO CON ROBUSTEZZA MIGLIORATA
import os
import sqlite3
import shutil
import re
try:
    import pypdf
except ImportError:
    pypdf = None

from config import DB_FILE, CARTELLA_PDF, inizializza_db, formatta_singola_data, formatta_singolo_importo

# REGEX PATTERNS COMPILATE (Performance)
REP_PATTERN = re.compile(r'Rep\.\s*n\s*[.\s]*(\d+)', re.IGNORECASE)
PARCELLA_PATTERN = re.compile(r'Parcella\s*\n\s*([A-Z0-9\/]+)', re.IGNORECASE)
DATA_PATTERN = re.compile(r'Parcella\s*\n\s*[A-Z0-9\/]+\s*\n\s*(\d{4}-\d{2}-\d{2})', re.IGNORECASE)
DATA_FALLBACK = re.compile(r'(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})', re.IGNORECASE)
IMPORTO_PATTERN = re.compile(r'Importo\s+Totale\s*\n\s*Parcella[\s\S]*?EUR\s*\n\s*([\d\.,]+)', re.IGNORECASE)
IMPORTO_FALLBACK = re.compile(r'EUR\s*\n\s*([\d\.,]+)', re.IGNORECASE)
CLIENTE_PATTERN = re.compile(r'Regime\s+fiscale:[\s\S]*?\n([A-ZÀ-ÿ\s]+)\n', re.IGNORECASE)

def inizializza_ocr_on_demand(log_callback, status_callback):
    """Inizializza il motore OCR e verifica dipendenze"""
    try:
        status_callback("Inizializzazione...", "orange")
        log_callback("⏳ Configurazione motore di estrazione testo digitale...\n")
        
        if pypdf is None:
            log_callback("⚠️ Libreria 'pypdf' non trovata. Installala con: pip install pypdf\n")
            status_callback("Errore", "red")
        else:
            status_callback("Pronto", "#10b981")
            log_callback("🏁 Motore Digitale per Fatture Elettroniche attivo ed ottimizzato.\n")
    except Exception as e:
        status_callback("Errore", "red")
        log_callback(f"❌ Errore: {e}\n")

def estrai_testo_da_pdf(percorso_pdf, log_callback):
    """Estrae testo da PDF con gestione errori migliorata"""
    try:
        testo_completo = []
        with open(percorso_pdf, 'rb') as f:
            reader = pypdf.PdfReader(f)
            num_pagine = len(reader.pages)
            
            for idx, pagina in enumerate(reader.pages):
                try:
                    testo_pag = pagina.extract_text()
                    if testo_pag:
                        testo_completo.append(testo_pag)
                except Exception as e:
                    log_callback(f"   ⚠️ Errore estrazione pagina {idx+1}/{num_pagine}: {e}\n")
                    continue
        
        if not testo_completo:
            log_callback(f"   ⚠️ Nessun testo estratto dal PDF\n")
            return ""
            
        return "\n".join(testo_completo)
    except Exception as e:
        log_callback(f"   ❌ Errore lettura digitale sul file: {e}\n")
        return ""

def analizza_campi_con_regex(testo):
    """Estrae campi dal testo con fallback robusti
    
    Ritorna: (repertorio, cliente, oggetto, numero_fattura, data_fattura, importo)
    """
    # 1. REPERTORIO
    rep_match = REP_PATTERN.search(testo)
    repertorio = rep_match.group(1) if rep_match else "000"
    
    # 2. NUMERO FATTURA
    numero_fattura = "NON_RILEVATO"
    parcella_match = PARCELLA_PATTERN.search(testo)
    if parcella_match:
        numero_fattura = parcella_match.group(1).strip()
    
    # 3. DATA FATTURA - Con fallback multipli
    data_fattura = "01/01/2026"  # Default più realistico
    
    # Prova prima il formato AAAA-MM-GG
    data_match = DATA_PATTERN.search(testo)
    if data_match:
        parti = data_match.group(1).split('-')
        data_fattura = f"{parti[2]}/{parti[1]}/{parti[0]}"
    else:
        # Fallback: cerca qualsiasi data
        fallback_match = DATA_FALLBACK.search(testo)
        if fallback_match:
            gg, mm, aa = fallback_match.groups()
            # Normalizza anno a 4 cifre
            if len(aa) == 2:
                aa = "20" + aa
            data_fattura = f"{gg.zfill(2)}/{mm.zfill(2)}/{aa}"
    
    # 4. IMPORTO TOTALE - Con fallback
    importo_fattura = 0.0
    
    # Prova prima il pattern completo
    imp_match = IMPORTO_PATTERN.search(testo)
    if not imp_match:
        imp_match = IMPORTO_FALLBACK.search(testo)
    
    if imp_match:
        valore_str = imp_match.group(1).strip().rstrip('.')
        try:
            importo_fattura = formatta_singolo_importo(valore_str)
        except Exception:
            importo_fattura = 0.0
    
    # 5. ANAGRAFICA CLIENTE
    cliente_estratto = f"CLIENTE_REP_{repertorio}"
    cli_match = CLIENTE_PATTERN.search(testo)
    if cli_match:
        cliente_pulito = cli_match.group(1).strip()
        cliente_pulito = " ".join(cliente_pulito.split())  # Normalizza spazi
        if len(cliente_pulito) > 3:
            cliente_estratto = cliente_pulito
    
    # 6. OGGETTO
    oggetto_estratto = f"Fattura Studio per Atto Rep. {repertorio}"
    
    return repertorio, cliente_estratto, oggetto_estratto, numero_fattura, data_fattura, importo_fattura

def elabora_smistamento(path_in, path_out, log_callback, status_callback, callback_aggiorna):
    """Elabora i PDF dalla cartella sorgente e integra nel DB"""
    inizializza_db()
    status_callback("Elaborazione...", "blue")
    
    if not os.path.exists(path_in):
        log_callback(f"❌ Cartella sorgente non trovata: {path_in}\n")
        status_callback("Pronto", "#10b981")
        return

    if not os.path.exists(path_out):
        os.makedirs(path_out)

    files = [f for f in os.listdir(path_in) if f.lower().endswith('.pdf')]
    if not files:
        log_callback("⚠️ Nessun file PDF trovato nella cartella sorgente.\n")
        status_callback("Pronto", "#10b981")
        return
    
    log_callback(f"⏳ AVVIA PARSING DOCUMENTI... Elaborazione accurata...\n")
    log_callback(f"Trovati {len(files)} file validi da elaborare.\n")
    
    elaborati_ok = 0
    elaborati_errore = 0

    for f_nome in files:
        percorso_completo = os.path.join(path_in, f_nome)
        log_callback(f"🔍 Lettura strutturale di: {f_nome}...\n")
        
        try:
            testo_estratto = estrai_testo_da_pdf(percorso_completo, log_callback)
            if not testo_estratto:
                log_callback(f"   ⚠️ PDF vuoto o non leggibile, skip\n")
                elaborati_errore += 1
                continue
            
            repertorio, cliente_estratto, oggetto_estratto, numero_fattura, data_fattura, importo_fattura = analizza_campi_con_regex(testo_estratto)
            data_pulita = formatta_singola_data(data_fattura)

            log_callback(f"   ↳ RILEVATO -> Rep: {repertorio} | Fattura N.: {numero_fattura} | Data: {data_pulita} | Importo: {importo_fattura}€ | Cliente: {cliente_estratto}\n")

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                
                # Inserimento tabelle incrociate
                cursor.execute("""
                    INSERT OR REPLACE INTO pratiche (repertorio, data_atto, fascicolo, oggetto)
                    VALUES (?, ?, ?, ?)
                """, (repertorio, data_pulita, f"FASC-{repertorio}", oggetto_estratto))
                
                cursor.execute("DELETE FROM clienti WHERE repertorio = ?", (repertorio,))
                cursor.execute("""
                    INSERT INTO clienti (repertorio, nome_cliente, num_fattura)
                    VALUES (?, ?, ?)
                """, (repertorio, cliente_estratto, numero_fattura))
                
                cursor.execute("DELETE FROM movimenti WHERE repertorio = ? AND cliente_libero IS NULL", (repertorio,))
                cursor.execute("""
                    INSERT INTO movimenti (repertorio, tipo_movimento, data_mov, importo, modalita, descrizione_libera, num_fattura)
                    VALUES (?, 'INCASSO', ?, ?, 'BONIFICO', ?, ?)
                """, (repertorio, data_pulita, importo_fattura, f"Incasso automatico fattura {numero_fattura}", numero_fattura))
                
                cursor.execute("DELETE FROM fatture_studio WHERE repertorio = ?", (repertorio,))
                cursor.execute("""
                    INSERT INTO fatture_studio (repertorio, num_fattura, data_fattura, importo, nome_cliente)
                    VALUES (?, ?, ?, ?, ?)
                """, (repertorio, numero_fattura, data_pulita, importo_fattura, cliente_estratto))
                
                conn.commit()

            # Archiviazione della copia rinominata
            nome_allegato_dest = f"Fattura_{numero_fattura.replace('/', '_')}_rep_{repertorio}.pdf"
            shutil.copy2(percorso_completo, os.path.join(CARTELLA_PDF, nome_allegato_dest))

            # Spostamento nella cartella di output
            cartella_dest = os.path.join(path_out, f"Fattura_{numero_fattura.replace('/', '_')}_Rep_{repertorio}")
            if not os.path.exists(cartella_dest):
                os.makedirs(cartella_dest)
            
            shutil.move(percorso_completo, os.path.join(cartella_dest, f_nome))
            log_callback(f"   ✅ REGISTRAZIONE INTEGRATA E ARCHIVIAZIONE COMPLETATA\n")
            elaborati_ok += 1

        except Exception as e:
            log_callback(f"   ❌ Errore durante elaborazione: {e}\n")
            elaborati_errore += 1

    log_callback(f"\n🏁 Fine elaborazione: {elaborati_ok} OK, {elaborati_errore} errori\n")
    status_callback("Pronto", "#10b981")
    
    if callback_aggiorna:
        callback_aggiorna()
