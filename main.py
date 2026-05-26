import os
import sys
import sqlite3
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess

from config import (
    DB_FILE, CARTELLA_PDF, OPZIONI_PAGAMENTO, formatta_singola_data, 
    formatta_singolo_importo, mostra_euro, inizializza_db
)
from pdf_generator import genera_pdf_pratica
import ocr_worker

class AppNotarile(tk.Tk):
    """Applicazione GUI per la gestione della Prima Nota Notarile con OCR"""
    
    def __init__(self):
        super().__init__()
        self.title("Prima Nota Notarile v16.3 - Automazione Totale OCR")
        self.geometry("1550x920")
        
        inizializza_db()
        
        self.path_in, self.path_out = tk.StringVar(), tk.StringVar()
        self.sezioni = {"CLIENTI": [], "INCASSO": [], "VERSAMENTO": [], "GIROCONTO": [], "IMPOSTA": [], "FATTURA": []}
        self.f_rows_containers = {}
        self.id_movimento_selezionato_registro = None 

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)
        
        self.tab_inserimento = ttk.Frame(self.notebook)
        self.tab_visualizzazione = ttk.Frame(self.notebook)
        self.tab_elenco_movimenti = ttk.Frame(self.notebook)
        self.tab_smistatore = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_inserimento, text="➕ Maschera Pratica")
        self.notebook.add(self.tab_visualizzazione, text="🔍 Ricerca Pratiche")
        self.notebook.add(self.tab_elenco_movimenti, text="📊 Elenco Movimenti (Autonomo)")
        self.notebook.add(self.tab_smistatore, text="📁 Smistatore Allegati OCR")
        
        self.crea_tab_inserimento()
        self.crea_tab_visualizzazione()
        self.crea_tab_elenco_movimenti()
        self.crea_tab_smistatore()
        
    def crea_tab_inserimento(self):
        """Crea la tab per l'inserimento pratica"""
        canvas = tk.Canvas(self.tab_inserimento, borderwidth=0, bg="#f1f5f9")
        scrollbar = ttk.Scrollbar(self.tab_inserimento, orient="vertical", command=canvas.yview)
        self.scroll_content = tk.Frame(canvas, bg="#f1f5f9", padx=10, pady=5)
        
        self.scroll_content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        f_gen = tk.Frame(self.scroll_content, bd=1, relief="solid", bg="#f8fafc", padx=6, pady=6)
        f_gen.pack(fill="x", pady=(0, 4))
        
        tk.Label(f_gen, text="Repertorio *:", bg="#f8fafc", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.ent_rep = tk.Entry(f_gen, width=12, font=("Arial", 9))
        self.ent_rep.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        
        tk.Label(f_gen, text="Data Atto:", bg="#f8fafc", font=("Arial", 9)).grid(row=0, column=2, sticky="w", padx=10, pady=2)
        self.ent_data_atto = tk.Entry(f_gen, width=12, font=("Arial", 9))
        self.ent_data_atto.grid(row=0, column=3, sticky="w", padx=2, pady=2)
        self.ent_data_atto.bind("<FocusOut>", self.on_date_field_leave)
        
        tk.Label(f_gen, text="Fascicolo / Rif:", bg="#f8fafc", font=("Arial", 9)).grid(row=0, column=4, sticky="w", padx=10, pady=2)
        self.ent_fascicolo = tk.Entry(f_gen, width=15, font=("Arial", 9))
        self.ent_fascicolo.grid(row=0, column=5, sticky="w", padx=2, pady=2)
        
        tk.Label(f_gen, text="Oggetto / Adempimento:", bg="#f8fafc", font=("Arial", 9)).grid(row=1, column=0, sticky="w", padx=2, pady=4)
        self.ent_oggetto = tk.Entry(f_gen, font=("Arial", 9))
        self.ent_oggetto.grid(row=1, column=1, columnspan=5, sticky="ew", padx=2, pady=4)
        f_gen.columnconfigure(1, weight=1)
        
        self.costruisci_struttura_interfaccia()
        
        f_all = tk.LabelFrame(self.scroll_content, text=" 📄 ALLEGATI PDF ASSOCIATI ALLA PRATICA (Doppio Click per Aprire) ", font=("Arial", 9, "bold"), fg="#1e3a8a", bg="#ffffff", padx=5, pady=4)
        f_all.pack(fill="x", pady=4)
        self.list_allegati = tk.Listbox(f_all, height=4, font=("Arial", 9), bg="#f8fafc")
        self.list_allegati.pack(fill="x", padx=2, pady=2)
        self.list_allegati.bind("<Double-1>", self.apri_pdf_selezionato)

        f_bottoni = tk.Frame(self.scroll_content, bg="#f1f5f9")
        f_bottoni.pack(fill="x", pady=5)
        
        btn_salva = tk.Button(f_bottoni, text="💾 SALVA PRATICA", bg="#1e3a8a", fg="white", font=("Arial", 10, "bold"), bd=0, padx=12, pady=6, command=self.salva_dati)
        btn_salva.pack(side="left", padx=4)
        
        btn_svuota = tk.Button(f_bottoni, text="🧹 SVUOTA MASCHERA", bg="#64748b", fg="white", font=("Arial", 9), bd=0, padx=10, pady=6, command=self.svuota_maschera)
        btn_svuota.pack(side="left", padx=4)
        
        btn_elimina = tk.Button(f_bottoni, text="❌ ELIMINA INTERA PRATICA", bg="#b91c1c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=6, command=self.elimina_pratica_corrente)
        btn_elimina.pack(side="right", padx=4)

        self.svuota_maschera()

    def on_date_field_leave(self, event):
        """Formatta automaticamente il campo data quando l'utente lo lascia"""
        widget = event.widget
        valore = widget.get().strip()
        if valore:
            formattato = formatta_singola_data(valore)
            widget.delete(0, tk.END)
            widget.insert(0, formattato)

    def ottieni_lista_clienti_inseriti(self):
        """Ritorna lista clienti unici inseriti"""
        lista = []
        for ent_n, _, _ in self.sezioni["CLIENTI"]:
            val = ent_n.get().strip()
            if val and val not in lista:
                lista.append(val)
        return lista if lista else [""]

    def aggiorna_dropdown_clienti(self, event=None):
        """Aggiorna i dropdown clienti in base a quelli inseriti"""
        clienti_attuali = self.ottieni_lista_clienti_inseriti()
        for _, _, _, cmb_cli, _ in self.sezioni["FATTURA"]:
            current_selection = cmb_cli.get()
            cmb_cli['values'] = clienti_attuali
            if current_selection in clienti_attuali:
                cmb_cli.set(current_selection)
            elif clienti_attuali:
                cmb_cli.set(clienti_attuali[0])

    def costruisci_struttura_interfaccia(self):
        """Costruisce la struttura principale dell'interfaccia con sezioni"""
        f_master_cl = tk.LabelFrame(self.scroll_content, text=" ANAGRAFICA CLIENTI / PARTI COINVOLTE ", font=("Arial", 9, "bold"), fg="#475569", bg="#ffffff", padx=4, pady=2)
        f_master_cl.pack(fill="x", pady=2)
        self.f_rows_containers["CLIENTI"] = tk.Frame(f_master_cl, bg="#ffffff")
        self.f_rows_containers["CLIENTI"].pack(fill="x")
        tk.Button(f_master_cl, text="➕ Aggiungi Cliente", bg="#475569", fg="white", font=("Arial", 8), bd=0, padx=4, pady=1, 
                  command=lambda: [self.aggiungi_riga_cliente(self.f_rows_containers["CLIENTI"]), self.aggiorna_dropdown_clienti()]).pack(anchor="e", pady=1)

        blocchi_movimento = [
            ("INCASSO", "📥 SEZIONE INCASSI (CONTANTI / BONIFICI / ASSEGNI)", True),
            ("VERSAMENTO", "🏦 VERSAMENTI SU CONTO CORRENTE DEDICATO (LEGGE 147/2013)", False),
            ("GIROCONTO", "🔄 GIROCONTI EFFETTUATI SU CONTO COMPETENZE DELLO STUDIO", False),
            ("IMPOSTA", "⚖️ IMPOSTE REGISTRATE / ANTICIPATE (F24 Autoliquidazione)", True)
        ]
        for tipo, titolo, ha_mod in blocchi_movimento:
            colore = "#0f766e" if "INCASS" in titolo or "VERSAM" in titolo else "#b45309"
            f_master_m = tk.LabelFrame(self.scroll_content, text=f" {titolo} ", font=("Arial", 9, "bold"), fg=colore, bg="#ffffff", padx=4, pady=2)
            f_master_m.pack(fill="x", pady=2)
            self.f_rows_containers[tipo] = tk.Frame(f_master_m, bg="#ffffff")
            self.f_rows_containers[tipo].pack(fill="x")
            tk.Button(f_master_m, text="➕ Aggiungi Riga", bg=colore, fg="white", font=("Arial", 8), bd=0, padx=4, pady=1, 
                      command=lambda t=tipo, hm=ha_mod: self.aggiungi_riga_movimento(self.f_rows_containers[t], t, hm)).pack(anchor="e", pady=1)

        f_master_fa = tk.LabelFrame(self.scroll_content, text=" 🧾 ESTREMI FATTURAZIONE ELETTRONICA STUDIO ", font=("Arial", 9, "bold"), fg="#1e3a8a", bg="#ffffff", padx=4, pady=2)
        f_master_fa.pack(fill="x", pady=2)
        self.f_rows_containers["FATTURA"] = tk.Frame(f_master_fa, bg="#ffffff")
        self.f_rows_containers["FATTURA"].pack(fill="x")
        tk.Button(f_master_fa, text="➕ Aggiungi Fattura", bg="#1e3a8a", fg="white", font=("Arial", 8), bd=0, padx=4, pady=1, 
                  command=lambda: self.aggiungi_riga_fattura(self.f_rows_containers["FATTURA"])).pack(anchor="e", pady=1)

    def aggiungi_riga_cliente(self, container):
        """Aggiunge una nuova riga cliente"""
        riga = tk.Frame(container, bg="#ffffff")
        riga.pack(fill="x", pady=1)
        tk.Label(riga, text=f"Cliente {len(self.sezioni['CLIENTI'])+1}:", bg="#ffffff", width=9, anchor="w", font=("Arial", 9)).pack(side="left", padx=2)
        ent_nome = tk.Entry(riga, font=("Arial", 9))
        ent_nome.pack(side="left", fill="x", expand=True, padx=2)
        ent_nome.bind("<KeyRelease>", lambda e: self.aggiorna_dropdown_clienti())
        
        tk.Label(riga, text="Fattura N° Collegata:", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=2)
        ent_fat = tk.Entry(riga, width=12, font=("Arial", 9))
        ent_fat.pack(side="left", padx=2)
        self.sezioni["CLIENTI"].append((ent_nome, ent_fat, riga))

    def aggiungi_riga_movimento(self, container, tipo, ha_modalita):
        """Aggiunge una nuova riga movimento (incasso, versamento, etc.)"""
        riga = tk.Frame(container, bg="#ffffff")
        riga.pack(fill="x", pady=1)
        tk.Label(riga, text="Data (GG/MM/AAAA):", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=2)
        ent_data = tk.Entry(riga, width=12, font=("Arial", 9))
        ent_data.pack(side="left", padx=2)
        ent_data.bind("<FocusOut>", self.on_date_field_leave)
        
        tk.Label(riga, text="Importo (€):", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=10)
        ent_imp = tk.Entry(riga, width=12, font=("Arial", 9))
        ent_imp.pack(side="left", padx=2)
        cmb_mod = None
        if ha_modalita:
            tk.Label(riga, text="Modalità / Note:", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=10)
            if tipo == "IMPOSTA":
                cmb_mod = ttk.Combobox(riga, values=["F24", "F24 APPROVATO", "ESENTE", "ALTRO"], width=15, font=("Arial", 9))
                cmb_mod.set("F24")
            else:
                cmb_mod = ttk.Combobox(riga, values=OPZIONI_PAGAMENTO, width=12, font=("Arial", 9))
            cmb_mod.pack(side="left", padx=2)
        self.sezioni[tipo].append((ent_data, ent_imp, cmb_mod, riga))

    def aggiungi_riga_fattura(self, container):
        """Aggiunge una nuova riga fattura"""
        riga = tk.Frame(container, bg="#ffffff")
        riga.pack(fill="x", pady=1)
        tk.Label(riga, text="Fattura N°:", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=2)
        ent_num = tk.Entry(riga, width=10, font=("Arial", 9))
        ent_num.pack(side="left", padx=2)
        
        tk.Label(riga, text="Data Emi:", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=10)
        ent_data = tk.Entry(riga, width=12, font=("Arial", 9))
        ent_data.pack(side="left", padx=2)
        ent_data.bind("<FocusOut>", self.on_date_field_leave)
        
        tk.Label(riga, text="Importo (€):", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=10)
        ent_imp = tk.Entry(riga, width=12, font=("Arial", 9))
        ent_imp.pack(side="left", padx=2)
        
        tk.Label(riga, text="Seleziona Cliente:", bg="#ffffff", font=("Arial", 9)).pack(side="left", padx=10)
        cmb_cli = ttk.Combobox(riga, values=self.ottieni_lista_clienti_inseriti(), font=("Arial", 9))
        cmb_cli.pack(side="left", fill="x", expand=True, padx=2)
        
        self.sezioni["FATTURA"].append((ent_num, ent_data, ent_imp, cmb_cli, riga))

    def apri_pdf_selezionato(self, event):
        """Apre il PDF selezionato dal doppio click"""
        sel = self.list_allegati.curselection()
        if not sel: return
        nome_f = self.list_allegati.get(sel[0])
        percorso = os.path.join(CARTELLA_PDF, nome_f)
        if os.path.exists(percorso):
            if sys.platform.startswith('win'): os.startfile(percorso)
            else: subprocess.run(['open', percorso])

    def crea_tab_visualizzazione(self):
        """Crea la tab per visualizzare e ricercare pratiche"""
        f_top = tk.Frame(self.tab_visualizzazione, padx=10, pady=10)
        f_top.pack(fill="x")
        tk.Label(f_top, text="Filtra Pratiche:", font=("Arial", 10)).pack(side="left", padx=5)
        self.ent_cerca = tk.Entry(f_top, width=35, font=("Arial", 10))
        self.ent_cerca.pack(side="left", padx=5)
        self.ent_cerca.bind("<KeyRelease>", lambda e: self.aggiorna_tabella_ricerca())
        
        self.tree = ttk.Treeview(self.tab_visualizzazione, columns=("rep", "data", "fascicolo", "clienti", "oggetto"), show="headings")
        self.tree.heading("rep", text="REPERTORIO")
        self.tree.heading("data", text="DATA ATTO")
        self.tree.heading("fascicolo", text="FASCICOLO")
        self.tree.heading("clienti", text="CLIENTI / PARTI")
        self.tree.heading("oggetto", text="OGGETTO / ADEMPIMENTO")
        
        self.tree.column("rep", width=100, anchor="center")
        self.tree.column("data", width=100, anchor="center")
        self.tree.column("fascicolo", width=120)
        self.tree.column("clienti", width=300)
        self.tree.column("oggetto", width=450)
        
        scroll_y = tk.Scrollbar(self.tab_visualizzazione, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scroll_y.pack(side="right", fill="y", pady=10, padx=(0,10))
        
        self.tree.bind("<Double-1>", lambda e: self.carica_pratica_da_tabella())
        self.aggiorna_tabella_ricerca()

    def popola_suggerimenti_registro(self):
        """Popola i suggerimenti nei campi del registro movimenti"""
        clienti = set()
        causali = {"INCASSO", "VERSAMENTO", "GIROCONTO", "IMPOSTA"}
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT nome_cliente FROM clienti WHERE nome_cliente IS NOT NULL AND nome_cliente != ''")
                for r in cursor.fetchall(): clienti.add(r[0])
                cursor.execute("SELECT DISTINCT cliente_libero FROM movimenti WHERE cliente_libero IS NOT NULL AND cliente_libero != ''")
                for r in cursor.fetchall(): clienti.add(r[0])
                cursor.execute("SELECT DISTINCT tipo_movimento FROM movimenti WHERE tipo_movimento IS NOT NULL AND tipo_movimento != ''")
                for r in cursor.fetchall(): causali.add(r[0].upper())
        except Exception:
            pass
        
        self.reg_cliente_libero['values'] = sorted(list(clienti))
        self.reg_causale['values'] = sorted(list(causali))

    def crea_tab_elenco_movimenti(self):
        """Crea la tab per gestire il registro movimenti autonomo"""
        f_editor = tk.LabelFrame(self.tab_elenco_movimenti, text=" 📝 REGISTRO CONTABILE COMPLETAMENTE EDITABILE ", font=("Arial", 9, "bold"), fg="#0f766e", bg="#f8fafc", padx=8, pady=6)
        f_editor.pack(fill="x", padx=10, pady=5)
        
        tk.Label(f_editor, text="Data Mov. *:", bg="#f8fafc").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.reg_data = tk.Entry(f_editor, width=12)
        self.reg_data.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self.reg_data.bind("<FocusOut>", self.on_date_field_leave)
        
        tk.Label(f_editor, text="Causale *:", bg="#f8fafc").grid(row=0, column=2, sticky="w", padx=10, pady=2)
        self.reg_causale = ttk.Combobox(f_editor, values=["INCASSO", "VERSAMENTO", "GIROCONTO", "IMPOSTA"], width=15)
        self.reg_causale.grid(row=0, column=3, sticky="w", padx=2, pady=2)
        self.reg_causale.set("INCASSO")

        tk.Label(f_editor, text="Repertorio (Opz):", bg="#f8fafc").grid(row=0, column=4, sticky="w", padx=10, pady=2)
        self.reg_rep = tk.Entry(f_editor, width=10)
        self.reg_rep.grid(row=0, column=5, sticky="w", padx=2, pady=2)

        tk.Label(f_editor, text="Cliente / Fornitore:", bg="#f8fafc").grid(row=0, column=6, sticky="w", padx=10, pady=2)
        self.reg_cliente_libero = ttk.Combobox(f_editor, width=28)
        self.reg_cliente_libero.grid(row=0, column=7, sticky="w", padx=2, pady=2)

        f_importi = tk.Frame(f_editor, bg="#f8fafc", bd=1, relief="groove", padx=5, pady=5)
        f_importi.grid(row=1, column=0, columnspan=8, sticky="ew", pady=6)
        
        tk.Label(f_importi, text="Importo CASSA (€):", bg="#f8fafc", fg="#0f766e", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        self.reg_imp_cassa = tk.Entry(f_importi, width=12)
        self.reg_imp_cassa.pack(side="left", padx=5)

        tk.Label(f_importi, text="Importo BANCA ORD (€):", bg="#f8fafc", fg="#1e3a8a", font=("Arial", 9, "bold")).pack(side="left", padx=10)
        self.reg_imp_banca_ord = tk.Entry(f_importi, width=12)
        self.reg_imp_banca_ord.pack(side="left", padx=5)

        tk.Label(f_importi, text="Importo BANCA DED. (€):", bg="#f8fafc", fg="#b45309", font=("Arial", 9, "bold")).pack(side="left", padx=10)
        self.reg_imp_banca_ded = tk.Entry(f_importi, width=12)
        self.reg_imp_banca_ded.pack(side="left", padx=5)

        tk.Label(f_importi, text="Fattura N°:", bg="#f8fafc", font=("Arial", 9, "bold")).pack(side="left", padx=15)
        self.reg_num_fattura = tk.Entry(f_importi, width=12)
        self.reg_num_fattura.pack(side="left", padx=5)

        tk.Label(f_importi, text="Nota/Mod:", bg="#f8fafc").pack(side="left", padx=15)
        self.reg_modalita = ttk.Combobox(f_importi, values=OPZIONI_PAGAMENTO + ["F24", "F24 APPROVATO", "ESENTE"], width=12)
        self.reg_modalita.set("BONIFICO")
        self.reg_modalita.pack(side="left", padx=2)

        tk.Label(f_editor, text="Descrizione Riga:").grid(row=2, column=0, sticky="w", padx=2, pady=4)
        self.reg_desc_libera = tk.Entry(f_editor, width=60)
        self.reg_desc_libera.grid(row=2, column=1, columnspan=5, sticky="ew", padx=2, pady=4)
        
        f_btn_reg = tk.Frame(f_editor, bg="#f8fafc")
        f_btn_reg.grid(row=3, column=0, columnspan=8, sticky="ew", pady=5)
        
        btn_add_mov = tk.Button(f_btn_reg, text="➕ Inserisci Riga Autonoma", bg="#0f766e", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, command=self.registro_inserisci_nuovo)
        btn_add_mov.pack(side="left", padx=4)
        
        self.btn_mod_mov = tk.Button(f_btn_reg, text="💾 Salva Modifiche Campi", bg="#b45309", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, state="disabled", command=self.registro_salva_modifica)
        self.btn_mod_mov.pack(side="left", padx=4)
        
        self.btn_del_mov = tk.Button(f_btn_reg, text="❌ Elimina Riga", bg="#b91c1c", fg="white", font=("Arial", 9, "bold"), bd=0, padx=10, pady=4, state="disabled", command=self.registro_elimina_riga)
        self.btn_del_mov.pack(side="left", padx=4)
        
        btn_clear_reg = tk.Button(f_btn_reg, text="🧹 Pulisci Campi", bg="#64748b", fg="white", font=("Arial", 9), bd=0, padx=8, pady=4, command=self.registro_pulisci_campi)
        btn_clear_reg.pack(side="left", padx=4)

        colonne = ("db_id", "data", "cliente", "causale", "num_fattura", "descrizione", "repertorio", "cassa", "banca_ord", "banca_ded")
        self.tree_movimenti = ttk.Treeview(self.tab_elenco_movimenti, columns=colonne, show="headings")
        
        self.tree_movimenti.heading("db_id", text="ID")
        self.tree_movimenti.heading("data", text="DATA")
        self.tree_movimenti.heading("cliente", text="CLIENTE / FORNITORE")
        self.tree_movimenti.heading("causale", text="CAUSALE")
        self.tree_movimenti.heading("num_fattura", text="FATTURA N°")
        self.tree_movimenti.heading("descrizione", text="DESCRIZIONE / NOTE")
        self.tree_movimenti.heading("repertorio", text="REP.")
        self.tree_movimenti.heading("cassa", text="CASSA (€)")
        self.tree_movimenti.heading("banca_ord", text="BANCA ORD (€)")
        self.tree_movimenti.heading("banca_ded", text="BANCA DED. (€)")
        
        self.tree_movimenti.column("db_id", width=50, anchor="center")
        self.tree_movimenti.column("data", width=95, anchor="center")
        self.tree_movimenti.column("cliente", width=200)
        self.tree_movimenti.column("causale", width=110, anchor="center")
        self.tree_movimenti.column("num_fattura", width=100, anchor="center")
        self.tree_movimenti.column("descrizione", width=220)
        self.tree_movimenti.column("repertorio", width=80, anchor="center")
        self.tree_movimenti.column("cassa", width=110, anchor="e")
        self.tree_movimenti.column("banca_ord", width=110, anchor="e")
        self.tree_movimenti.column("banca_ded", width=110, anchor="e")
        
        scr_y = tk.Scrollbar(self.tab_elenco_movimenti, orient="vertical", command=self.tree_movimenti.yview)
        self.tree_movimenti.configure(yscrollcommand=scr_y.set)
        
        self.tree_movimenti.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
        scr_y.pack(side="right", fill="y", pady=10, padx=(0,10))
        
        self.tree_movimenti.bind("<<TreeviewSelect>>", self.on_registro_select_row)
        self.carica_registro_movimenti()

    def carica_registro_movimenti(self):
        """Carica i movimenti da database nella tabella"""
        for item in self.tree_movimenti.get_children():
            self.tree_movimenti.delete(item)
            
        self.popola_suggerimenti_registro()
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(\"\"\"\n                SELECT m.id, m.data_mov, m.tipo_movimento, m.repertorio, m.importo, m.modalita,\n                       m.cliente_libero, m.descrizione_libera, m.num_fattura,\n                       (SELECT group_concat(nome_cliente, ', ') FROM clienti WHERE repertorio=m.repertorio) as cl_rep,\n                       p.oggetto\n                FROM movimenti m\n                LEFT JOIN pratiche p ON m.repertorio = p.repertorio\n                ORDER BY m.id DESC\n            \"\"\")\n            \n            for row in cursor.fetchall():\n                mid, data, causale, rep, importo, modalita, cl_libero, desc_libera, fat_num, cl_rep, ogg_rep = row\n                \n                mostra_cliente = cl_libero if cl_libero else (cl_rep if cl_rep else \"-\")\n                mostra_desc = desc_libera if desc_libera else (f\"{ogg_rep} ({modalita})\" if ogg_rep else f\"Movimento ({modalita})\")\n                mostra_fattura = fat_num if fat_num else \"-\"\n                \n                cassa, banca_ord, banca_ded = \"\", \"\", \"\"\n                data_formattata = formatta_singola_data(data)\n                \n                if \"CASSA:\" in str(modalita):\n                    cassa = mostra_euro(importo)\n                elif \"B_DED:\" in str(modalita):\n                    banca_ded = mostra_euro(importo)\n                elif \"B_ORD:\" in str(modalita):\n                    banca_ord = mostra_euro(importo)\n                else:\n                    if str(modalita).upper() == \"CONTANTI\": cassa = mostra_euro(importo)\n                    elif str(causale).upper() == \"VERSAMENTO\": banca_ded = mostra_euro(importo)\n                    else: banca_ord = mostra_euro(importo)\n                    \n                self.tree_movimenti.insert(\"\", \"end\", values=(\n                    mid, data_formattata, mostra_cliente, causale, mostra_fattura, mostra_desc,\n                    rep if rep else \"-\", cassa, banca_ord, banca_ded\n                ))\n\n    def on_registro_select_row(self, event):\n        \"\"\"Gestisce la selezione di una riga nel registro\"\"\"\n        sel = self.tree_movimenti.selection()\n        if not sel: return\n        valori = self.tree_movimenti.item(sel[0])[\"values\"]\n        \n        self.id_movimento_selezionato_registro = valori[0]\n        \n        with sqlite3.connect(DB_FILE) as conn:\n            c = conn.cursor()\n            c.execute(\"SELECT data_mov, tipo_movimento, importo, repertorio, modalita, cliente_libero, descrizione_libera, num_fattura FROM movimenti WHERE id=?\", (self.id_movimento_selezionato_registro,))\n            res = c.fetchone()\n            if res:\n                self.reg_data.delete(0, tk.END)\n                self.reg_data.insert(0, formatta_singola_data(res[0]))\n                self.reg_causale.set(res[1])\n                \n                self.reg_rep.delete(0, tk.END)\n                self.reg_rep.insert(0, res[3] if res[3] else \"\")\n                \n                self.reg_cliente_libero.set(res[5] if res[5] else \"\")\n                \n                self.reg_desc_libera.delete(0, tk.END)\n                self.reg_desc_libera.insert(0, res[6] if res[6] else \"\")\n                \n                self.reg_num_fattura.delete(0, tk.END)\n                self.reg_num_fattura.insert(0, res[7] if res[7] else \"\")\n\n                self.reg_imp_cassa.delete(0, tk.END)\n                self.reg_imp_banca_ord.delete(0, tk.END)\n                self.reg_imp_banca_ded.delete(0, tk.END)\n                \n                mod_tag = str(res[4])\n                if \"CASSA:\" in mod_tag:\n                    self.reg_imp_cassa.insert(0, str(res[2]))\n                    self.reg_modalita.set(mod_tag.replace(\"CASSA:\", \"\"))\n                elif \"B_DED:\" in mod_tag:\n                    self.reg_imp_banca_ded.insert(0, str(res[2]))\n                    self.reg_modalita.set(mod_tag.replace(\"B_DED:\", \"\"))\n                elif \"B_ORD:\" in mod_tag:\n                    self.reg_imp_banca_ord.insert(0, str(res[2]))\n                    self.reg_modalita.set(mod_tag.replace(\"B_ORD:\", \"\"))\n                else:\n                    self.reg_imp_banca_ord.insert(0, str(res[2]))\n                    self.reg_modalita.set(mod_tag)\n\n        self.btn_mod_mov.config(state=\"normal\")\n        self.btn_del_mov.config(state=\"normal\")\n\n    def registro_pulisci_campi(self):\n        \"\"\"Pulisce i campi del registro movimento\"\"\"\n        self.id_movimento_selezionato_registro = None\n        self.reg_data.delete(0, tk.END)\n        self.reg_rep.delete(0, tk.END)\n        self.reg_imp_cassa.delete(0, tk.END)\n        self.reg_imp_banca_ord.delete(0, tk.END)\n        self.reg_imp_banca_ded.delete(0, tk.END)\n        self.reg_num_fattura.delete(0, tk.END)\n        self.reg_cliente_libero.set(\"\")\n        self.reg_desc_libera.delete(0, tk.END)\n        self.reg_causale.set(\"INCASSO\")\n        self.reg_modalita.set(\"BONIFICO\")\n        self.btn_mod_mov.config(state=\"disabled\")\n        self.btn_del_mov.config(state=\"disabled\")\n\n    def estrai_valore_e_tag_importo(self):\n        \"\"\"Estrae il valore importo e il tag corrispondente\"\"\"\n        v_cassa = formatta_singolo_importo(self.reg_imp_cassa.get().strip())\n        v_ord = formatta_singolo_importo(self.reg_imp_banca_ord.get().strip())\n        v_ded = formatta_singolo_importo(self.reg_imp_banca_ded.get().strip())\n        base_mod = self.reg_modalita.get().strip().upper()\n        \n        if v_cassa > 0: return v_cassa, f\"CASSA:{base_mod}\"\n        if v_ded > 0: return v_ded, f\"B_DED:{base_mod}\"\n        return v_ord, f\"B_ORD:{base_mod}\"\n\n    def registro_inserisci_nuovo(self):\n        \"\"\"Inserisce un nuovo movimento nel registro\"\"\"\n        data = formatta_singola_data(self.reg_data.get().strip())\n        rep = self.reg_rep.get().strip()\n        causale = self.reg_causale.get().strip().upper()\n        cli_libero = self.reg_cliente_libero.get().strip()\n        desc_libera = self.reg_desc_libera.get().strip()\n        fat_num = self.reg_num_fattura.get().strip()\n        \n        importo, tag_modalita = self.estrai_valore_e_tag_importo()\n        \n        if not data or importo <= 0:\n            messagebox.showerror(\"Errore\", \"Inserire la Data e almeno un Importo valido!\")\n            return\n            \n        with sqlite3.connect(DB_FILE) as conn:\n            cursor = conn.cursor()\n            cursor.execute(\"\"\"\n                INSERT INTO movimenti (repertorio, tipo_movimento, data_mov, importo, modalita, cliente_libero, descrizione_libera, num_fattura) \n                VALUES (?,?,?,?,?,?,?,?)\n            \"\"\", (rep if rep else None, causale, data, importo, tag_modalita, cli_libero, desc_libera, fat_num if fat_num else None))\n            conn.commit()\n            \n        self.registro_pulisci_campi()\n        self.aggiorna_tabelle_totali()\n        messagebox.showinfo(\"Inserito\", \"Riga inserita correttamente.\")\n\n    def registro_salva_modifica(self):\n        \"\"\"Salva le modifiche ad un movimento esistente\"\"\"\n        if not self.id_movimento_selezionato_registro: return\n        data = formatta_singola_data(self.reg_data.get().strip())\n        rep = self.reg_rep.get().strip()\n        causale = self.reg_causale.get().strip().upper()\n        cli_libero = self.reg_cliente_libero.get().strip()\n        desc_libera = self.reg_desc_libera.get().strip()\n        fat_num = self.reg_num_fattura.get().strip()\n        \n        importo, tag_modalita = self.estrai_valore_e_tag_importo()\n        \n        with sqlite3.connect(DB_FILE) as conn:\n            cursor = conn.cursor()\n            cursor.execute(\"\"\"\n                UPDATE movimenti \n                SET repertorio=?, tipo_movimento=?, data_mov=?, importo=?, modalita=?, cliente_libero=?, descrizione_libera=?, num_fattura=? \n                WHERE id=?\n            \"\"\", (rep if rep else None, causale, data, importo, tag_modalita, cli_libero, desc_libera, fat_num if fat_num else None, self.id_movimento_selezionato_registro))\n            conn.commit()\n            \n        self.registro_pulisci_campi()\n        self.aggiorna_tabelle_totali()\n        messagebox.showinfo(\"Successo\", \"Movimento aggiornato nel registro flussi.\")\n\n    def registro_elimina_riga(self):\n        \"\"\"Elimina una riga dal registro movimento\"\"\"\n        if not self.id_movimento_selezionato_registro: return\n        if messagebox.askyesno(\"Conferma\", \"Vuoi cancellare definitivamente questa riga?\"):\n            with sqlite3.connect(DB_FILE) as conn:\n                cursor = conn.cursor()\n                cursor.execute(\"DELETE FROM movimenti WHERE id=?\", (self.id_movimento_selezionato_registro,))\n                conn.commit()\n            self.registro_pulisci_campi()\n            self.aggiorna_tabelle_totali()\n\n    def crea_tab_smistatore(self):\n        \"\"\"Crea la tab per lo smistamento automatico OCR\"\"\"\n        container = tk.Frame(self.tab_smistatore, padx=20, pady=20)\n        container.pack(fill=\"both\", expand=True)\n        \n        tk.Label(container, text=\"📁 Cartella SORGENTE (Origine PDF):\").grid(row=1, column=0, sticky=\"w\", pady=5)\n        tk.Entry(container, textvariable=self.path_in).grid(row=1, column=1, sticky=\"ew\", padx=10, pady=5)\n        tk.Button(container, text=\"Sfoglia...\", command=lambda: self.path_in.set(filedialog.askdirectory())).grid(row=1, column=2, pady=5)\n        \n        tk.Label(container, text=\"📁 Cartella DESTINAZIONE (Smistati):\").grid(row=2, column=0, sticky=\"w\", pady=5)\n        tk.Entry(container, textvariable=self.path_out).grid(row=2, column=1, sticky=\"ew\", padx=10, pady=5)\n        tk.Button(container, text=\"Sfoglia...\", command=lambda: self.path_out.set(filedialog.askdirectory())).grid(row=2, column=2, pady=5)\n        \n        self.lbl_ocr_status = tk.Label(container, text=\"Stato OCR: Inizializzazione...\", font=("Arial", 10, "bold\"), fg=\"orange\")\n        self.lbl_ocr_status.grid(row=3, column=0, columnspan=3, pady=10)\n        \n        self.btn_ocr = tk.Button(container, text=\"🚀 AVVIA ANALISI E INTEGRAZIONE AUTOMATICA OCR\", bg=\"#10b981\", fg=\"white\", font=(\"Arial\", 10, \"bold\"), bd=0, pady=8, command=self.avvia_ocr)\n        self.btn_ocr.grid(row=4, column=0, columnspan=3, pady=5, sticky=\"ew\")\n        \n        self.log_textbox = tk.Text(container, height=12, font=(\"Consolas\", 9), bg=\"white\")\n        self.log_textbox.grid(row=5, column=0, columnspan=3, pady=10, sticky=\"nsew\")\n        \n        container.grid_rowconfigure(5, weight=1)\n        container.grid_columnconfigure(1, weight=1)\n        threading.Thread(target=lambda: ocr_worker.inizializza_ocr_on_demand(self.log_ocr, self.status_ocr), daemon=True).start()\n\n    def log_ocr(self, msg): \n        \"\"\"Scrive nel log OCR\"\"\"\n        self.log_textbox.insert(\"end\", msg)\n        self.log_textbox.see(\"end\")\n\n    def status_ocr(self, msg, col): \n        \"\"\"Aggiorna lo stato OCR\"\"\"\n        self.lbl_ocr_status.config(text=f\"Stato OCR Engine: {msg}\", fg=col)\n    \n    def avvia_ocr(self):\n        \"\"\"Avvia l'elaborazione OCR in background\"\"\"\n        if not self.path_in.get() or not self.path_out.get(): return\n        self.btn_ocr.config(state=\"disabled\", bg=\"#cbd5e1\")\n        threading.Thread(target=lambda: [\n            ocr_worker.elabora_smistamento(self.path_in.get(), self.path_out.get(), self.log_ocr, self.status_ocr, self.aggiorna_tabelle_totali),\n            self.btn_ocr.config(state=\"normal\", bg=\"#10b981\")\n        ], daemon=True).start()\n\n    def aggiorna_tabelle_totali(self):\n        \"\"\"Aggiorna tutte le tabelle\"\"\"\n        self.aggiorna_tabella_ricerca()\n        self.carica_registro_movimenti()\n\n    def aggiorna_tabella_ricerca(self):\n        \"\"\"Aggiorna la tabella di ricerca pratiche\"\"\"\n        for item in self.tree.get_children(): self.tree.delete(item)\n        chiave = self.ent_cerca.get().strip()\n        with sqlite3.connect(DB_FILE) as conn:\n            cursor = conn.cursor()\n            if chiave:\n                cursor.execute(\"\"\"\n                    SELECT p.repertorio, p.data_atto, p.fascicolo, p.oggetto,\n                           (SELECT group_concat(nome_cliente, ', ') FROM clienti WHERE repertorio=p.repertorio) as cl\n                    FROM pratiche p WHERE p.repertorio LIKE ? OR p.oggetto LIKE ? OR cl LIKE ?\n                \"\"\", (f\"%{chiave}%\", f\"%{chiave}%\", f\"%{chiave}%\"))\n            else:\n                cursor.execute(\"SELECT repertorio, data_atto, fascicolo, oggetto FROM pratiche\")\n            for row in cursor.fetchall():\n                cursor.execute(\"SELECT nome_cliente FROM clienti WHERE repertorio=?\", (row[0],))\n                clienti_list = [c[0] for c in cursor.fetchall() if c[0]]\n                self.tree.insert(\"\", \"end\", values=(row[0], formatta_singola_data(row[1]), row[2], \", \".join(clienti_list), row[3]))\n\n    def carica_pratica_da_tabella(self):\n        \"\"\"Carica una pratica selezionata dalla tabella\"\"\"\n        sel = self.tree.selection()\n        if not sel: return\n        rep = self.tree.item(sel[0])[\"values\"][0]\n        self.carica_pratica_specifica(rep)\n\n    def carica_pratica_specifica(self, rep):\n        \"\"\"Carica i dati di una pratica specifica dal database\"\"\"\n        self.svuota_maschera_per_ricarica()\n        \n        self.list_allegati.delete(0, tk.END)\n        if os.path.exists(CARTELLA_PDF):\n            for f in os.listdir(CARTELLA_PDF):\n                if f.lower().endswith(\".pdf\") and f\"rep_{rep}\" in f.lower():\n                    self.list_allegati.insert(tk.END, f)\n\n        with sqlite3.connect(DB_FILE) as conn:\n            cursor = conn.cursor()\n            cursor.execute(\"SELECT repertorio, data_atto, fascicolo, oggetto FROM pratiche WHERE repertorio=?\", (rep,))\n            p = cursor.fetchone()\n            if not p: return\n            \n            self.ent_rep.insert(0, p[0])\n            self.ent_data_atto.insert(0, formatta_singola_data(p[1]))\n            self.ent_fascicolo.insert(0, p[2])\n            self.ent_oggetto.insert(0, p[3])\n            \n            cursor.execute(\"SELECT nome_cliente, num_fattura FROM clienti WHERE repertorio=?\", (rep,))\n            for c in cursor.fetchall():\n                riga = tk.Frame(self.f_rows_containers[\"CLIENTI\"], bg=\"#ffffff\")\n                riga.pack(fill=\"x\", pady=1)\n                tk.Label(riga, text=f\"Cliente {len(self.sezioni['CLIENTI'])+1}:\", bg=\"#ffffff\", width=9, anchor=\"w\", font=(\"Arial\", 9)).pack(side=\"left\", padx=2)\n                ent_n = tk.Entry(riga, font=(\"Arial\", 9))\n                ent_n.insert(0, c[0])\n                ent_n.pack(side=\"left\", fill=\"x\", expand=True, padx=2)\n                ent_n.bind(\"<KeyRelease>\", lambda e: self.aggiorna_dropdown_clienti())\n                \n                tk.Label(riga, text=\"Fattura N° Collegata:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=2)\n                ent_f = tk.Entry(riga, width=12, font=(\"Arial\", 9))\n                ent_f.insert(0, c[1] if c[1] else \"\")\n                ent_f.pack(side=\"left\", padx=2)\n                self.sezioni[\"CLIENTI\"].append((ent_n, ent_f, riga))\n                \n            for tipo in [\"INCASSO\", \"VERSAMENTO\", \"GIROCONTO\", \"IMPOSTA\"]:\n                cursor.execute(\"SELECT data_mov, importo, modalita, num_fattura FROM movimenti WHERE repertorio=? AND tipo_movimento=? AND cliente_libero IS NULL\", (rep, tipo))\n                ha_mod = tipo in [\"INCASSO\", \"IMPOSTA\"]\n                for m in cursor.fetchall():\n                    riga = tk.Frame(self.f_rows_containers[tipo], bg=\"#ffffff\")\n                    riga.pack(fill=\"x\", pady=1)\n                    tk.Label(riga, text=\"Data:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=2)\n                    ent_d = tk.Entry(riga, width=12, font=(\"Arial\", 9))\n                    ent_d.insert(0, formatta_singola_data(m[0]))\n                    ent_d.pack(side=\"left\", padx=2)\n                    ent_d.bind(\"<FocusOut>\", self.on_date_field_leave)\n                    \n                    tk.Label(riga, text=\"Importo (€):\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=10)\n                    ent_i = tk.Entry(riga, width=12, font=(\"Arial\", 9))\n                    ent_i.insert(0, str(m[1]))\n                    ent_i.pack(side=\"left\", padx=2)\n                    cmb_m = None\n                    if ha_mod:\n                        tk.Label(riga, text=\"Modalità / Note:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=10)\n                        if tipo == \"IMPOSTA\":\n                            cmb_m = ttk.Combobox(riga, values=[\"F24\", \"F24 APPROVATO\", \"ESENTE\", \"ALTRO\"], width=15, font=(\"Arial\", 9))\n                        else:\n                            cmb_m = ttk.Combobox(riga, values=OPZIONI_PAGAMENTO, width=12, font=(\"Arial\", 9))\n                        cmb_m.set(m[2] if m[2] is not None else \"\")\n                        cmb_m.pack(side=\"left\", padx=2)\n                    self.sezioni[tipo].append((ent_d, ent_i, cmb_m, riga))\n            \n            clienti_attuali = self.ottieni_lista_clienti_inseriti()\n            cursor.execute(\"SELECT num_fattura, data_fattura, importo, nome_cliente FROM fatture_studio WHERE repertorio=?\", (rep,))\n            for f in cursor.fetchall():\n                riga = tk.Frame(self.f_rows_containers[\"FATTURA\"], bg=\"#ffffff\")\n                riga.pack(fill=\"x\", pady=1)\n                tk.Label(riga, text=\"Fattura N°:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=2)\n                ent_num = tk.Entry(riga, width=10, font=(\"Arial\", 9))\n                ent_num.insert(0, f[0])\n                ent_num.pack(side=\"left\", padx=2)\n                tk.Label(riga, text=\"Data Emi:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=10)\n                ent_dat = tk.Entry(riga, width=12, font=(\"Arial\", 9))\n                ent_dat.insert(0, formatta_singola_data(f[1]))\n                ent_dat.pack(side=\"left\", padx=2)\n                ent_dat.bind(\"<FocusOut>\", self.on_date_field_leave)\n                \n                tk.Label(riga, text=\"Importo (€):\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=10)\n                ent_imp = tk.Entry(riga, width=12, font=(\"Arial\", 9))\n                ent_imp.insert(0, str(f[2]))\n                ent_imp.pack(side=\"left\", padx=2)\n                \n                tk.Label(riga, text=\"Seleziona Cliente:\", bg=\"#ffffff\", font=(\"Arial\", 9)).pack(side=\"left\", padx=10)\n                cmb_cli = ttk.Combobox(riga, values=clienti_attuali, font=(\"Arial\", 9))\n                cmb_cli.set(f[3] if f[3] else \"\")\n                cmb_cli.pack(side=\"left\", fill=\"x\", expand=True, padx=2)\n                \n                self.sezioni[\"FATTURA\"].append((ent_num, ent_dat, ent_imp, cmb_cli, riga))\n\n        self.garantisci_righe_minime()\n        self.aggiorna_dropdown_clienti()\n        self.notebook.select(self.tab_inserimento)\n\n    def salva_dati(self):\n        \"\"\"Salva i dati della pratica nel database e genera PDF\"\"\"\n        rep = self.ent_rep.get().strip()\n        if not rep:\n            messagebox.showerror(\"Errore\", \"Il campo Repertorio è obbligatorio!\")\n            return\n            \n        data_atto = formatta_singola_data(self.ent_data_atto.get().strip())\n        fascicolo = self.ent_fascicolo.get().strip()\n        oggetto = self.ent_oggetto.get().strip()\n        \n        try:\n            with sqlite3.connect(DB_FILE) as conn:\n                cursor = conn.cursor()\n                cursor.execute(\"INSERT OR REPLACE INTO pratiche (repertorio, data_atto, fascicolo, oggetto) VALUES (?,?,?,?)\", (rep, data_atto, fascicolo, oggetto))\n                \n                cursor.execute(\"DELETE FROM clienti WHERE repertorio=?\", (rep,))\n                clienti_nomi = []\n                for ent_n, ent_f, _ in self.sezioni[\"CLIENTI\"]:\n                    n = ent_n.get().strip()\n                    f = ent_f.get().strip()\n                    if n:\n                        cursor.execute(\"INSERT INTO clienti (repertorio, nome_cliente, num_fattura) VALUES (?,?,?)\", (rep, n, f if f else None))\n                        clienti_nomi.append(n)\n                \n                cursor.execute(\"DELETE FROM movimenti WHERE repertorio=? AND cliente_libero IS NULL\", (rep,))\n                dati_campi = {}\n                for tipo in [\"INCASSO\", \"VERSAMENTO\", \"GIROCONTO\", \"IMPOSTA\"]:\n                    dates, imps, mods = [], [], []\n                    for ent_d, ent_i, cmb_m, _ in self.sezioni[tipo]:\n                        d = formatta_singola_data(ent_d.get().strip())\n                        i = formatta_singolo_importo(ent_i.get().strip())\n                        m = cmb_m.get().strip().upper() if cmb_m else \"\"\n                        if d or i > 0:\n                            cursor.execute(\"INSERT INTO movimenti (repertorio, tipo_movimento, data_mov, importo, modalita) VALUES (?,?,?,?,?)\", (rep, tipo, d, i, m))\n                            dates.append(d); imps.append(str(i)); mods.append(m)\n                    dati_campi[f\"{tipo}: Data\"] = \"|\".join(dates)\n                    dati_campi[f\"{tipo}: Importo\"] = \"|\".join(imps)\n                    dati_campi[f\"{tipo}: Modalità\"] = \"|\".join(mods)\n                    \n                cursor.execute(\"DELETE FROM fatture_studio WHERE repertorio=?\", (rep,))\n                f_nums, f_dates, f_imps, f_clis = [], [], [] , []\n                for ent_num, ent_dat, ent_imp, cmb_cli, _ in self.sezioni[\"FATTURA\"]:\n                    num = ent_num.get().strip()\n                    dat = formatta_singola_data(ent_dat.get().strip())\n                    imp = formatta_singolo_importo(ent_imp.get().strip())\n                    cli = cmb_cli.get().strip()\n                    \n                    if num or dat or imp > 0 or cli:\n                        cursor.execute(\"INSERT INTO fatture_studio (repertorio, num_fattura, data_fattura, importo, nome_cliente) VALUES (?,?,?,?,?)\", (rep, num, dat, imp, cli))\n                        f_nums.append(num); f_dates.append(dat); f_imps.append(str(imp)); f_clis.append(cli)\n                dati_campi[\"FATTURA: Numero\"] = \"|\".join(f_nums)\n                dati_campi[\"FATTURA: Data\"] = \"|\".join(f_dates)\n                dati_campi[\"FATTURA: Importo\"] = \"|\".join(f_imps)\n                dati_campi[\"FATTURA: Cliente\"] = \"|\".join(f_clis)\n                conn.commit()\n                \n            try:\n                genera_pdf_pratica(rep, data_atto, fascicolo, \", \".join(clienti_nomi), oggetto, dati_campi)\n                messagebox.showinfo(\"Successo\", f\"Pratica Rep. {rep} salvata.\")\n            except Exception as e:\n                messagebox.showerror(\"Errore PDF\", f\"Errore scrittura PDF: {e}\")\n                \n            self.aggiorna_tabelle_totali()\n            \n        except Exception as e:\n            messagebox.showerror(\"Errore Database\", f\"Impossibile salvare i dati: {e}\")\n\n    def elimina_pratica_corrente(self):\n        \"\"\"Elimina la pratica corrente e tutti i dati associati\"\"\"\n        rep = self.ent_rep.get().strip()\n        if not rep: return\n        if messagebox.askyesno(\"Conferma\", f\"Vuoi eliminare la pratica Rep. {rep}?\"):\n            try:\n                with sqlite3.connect(DB_FILE) as conn:\n                    cursor = conn.cursor()\n                    cursor.execute(\"DELETE FROM pratiche WHERE repertorio=?\", (rep,))\n                    cursor.execute(\"DELETE FROM clienti WHERE repertorio=?\", (rep,))\n                    cursor.execute(\"DELETE FROM movimenti WHERE repertorio=?\", (rep,))\n                    cursor.execute(\"DELETE FROM fatture_studio WHERE repertorio=?\", (rep,))\n                    conn.commit()\n                messagebox.showinfo(\"Eliminato\", f\"Pratica Rep. {rep} rimossa.\")\n                self.svuota_maschera()\n                self.aggiorna_tabelle_totali()\n            except Exception as e:\n                messagebox.showerror(\"Errore\", f\"Impossibile eliminare: {e}\")\n\n    def svuota_maschera_per_ricarica(self):\n        \"\"\"Svuota la maschera prima di ricaricare dati - CLEANUP MIGLIORATO\"\"\"\n        self.ent_rep.delete(0, tk.END)\n        self.ent_data_atto.delete(0, tk.END)\n        self.ent_fascicolo.delete(0, tk.END)\n        self.ent_oggetto.delete(0, tk.END)\n        self.list_allegati.delete(0, tk.END)\n        \n        # Cleanup approfondito dei widget\n        for key in self.sezioni.keys():\n            if key in self.f_rows_containers:\n                for widget in self.f_rows_containers[key].winfo_children():\n                    widget.destroy()\n            self.sezioni[key].clear()\n\n    def garantisci_righe_minime(self):\n        \"\"\"Garantisce che ci sia almeno una riga per ogni sezione\"\"\"\n        if not self.sezioni[\"CLIENTI\"]: self.aggiungi_riga_cliente(self.f_rows_containers[\"CLIENTI\"])\n        if not self.sezioni[\"INCASSO\"]: self.aggiungi_riga_movimento(self.f_rows_containers[\"INCASSO\"], \"INCASSO\", ha_modalita=True)\n        if not self.sezioni[\"VERSAMENTO\"]: self.aggiungi_riga_movimento(self.f_rows_containers[\"VERSAMENTO\"], \"VERSAMENTO\", ha_modalita=False)\n        if not self.sezioni[\"GIROCONTO\"]: self.aggiungi_riga_movimento(self.f_rows_containers[\"GIROCONTO\"], \"GIROCONTO\", ha_modalita=False)\n        if not self.sezioni[\"IMPOSTA\"]: self.aggiungi_riga_movimento(self.f_rows_containers[\"IMPOSTA\"], \"IMPOSTA\", ha_modalita=True)\n        if not self.sezioni[\"FATTURA\"]: self.aggiungi_riga_fattura(self.f_rows_containers[\"FATTURA\"])\n\n    def svuota_maschera(self):\n        \"\"\"Svuota e reinizializza la maschera\"\"\"\n        self.svuota_maschera_per_ricarica()\n        self.garantisci_righe_minime()\n        self.aggiorna_dropdown_clienti()\n\nif __name__ == \"__main__\":\n    app = AppNotarile()\n    app.mainloop()\n", "path": "main.py"}