# pdf_generator.py - OTTIMIZZATO E PULITO
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from config import CARTELLA_PDF, mostra_euro, formatta_singolo_importo, formatta_singola_data

def genera_pdf_pratica(repertorio, data_atto, fascicolo, clienti, oggetto, dati_campi):
    """Genera un PDF riepilogativo della pratica
    
    Args:
        repertorio: Numero repertorio
        data_atto: Data atto
        fascicolo: Numero fascicolo
        clienti: Nomi clienti separati da virgola
        oggetto: Oggetto della pratica
        dati_campi: Dict con dati movimenti e fatture
    """
    os.makedirs(CARTELLA_PDF, exist_ok=True)
    nome_file = os.path.join(CARTELLA_PDF, f"Riepilogo_Rep_{repertorio}.pdf")
    
    doc = SimpleDocTemplate(nome_file, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    # Stili predefiniti
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', 
        parent=styles['Heading1'], 
        fontName='Helvetica-Bold', 
        fontSize=17, 
        textColor=colors.HexColor('#1e3a8a'), 
        spaceAfter=4
    )
    section_style = ParagraphStyle(
        'SecTitle', 
        parent=styles['Heading2'], 
        fontName='Helvetica-Bold', 
        fontSize=11, 
        textColor=colors.HexColor('#0f766e'), 
        spaceBefore=10, 
        spaceAfter=5
    )
    cell_style = ParagraphStyle(
        'Cell', 
        parent=styles['Normal'], 
        fontName='Helvetica', 
        fontSize=9, 
        leading=11
    )
    cell_bold = ParagraphStyle(
        'CellB', 
        parent=styles['Normal'], 
        fontName='Helvetica-Bold', 
        fontSize=9, 
        leading=11
    )
    
    # Titolo
    story.append(Paragraph(f"SCHEDA RIEPILOGATIVA PRIMA NOTA - REP. {repertorio}", title_style))
    story.append(Spacer(1, 4))
    
    # Informazioni generali
    info_data = [
        [
            Paragraph("<b>REPERTORIO:</b>", cell_style), 
            Paragraph(repertorio, cell_bold), 
            Paragraph("<b>DATA ATTO:</b>", cell_style), 
            Paragraph(formatta_singola_data(data_atto), cell_style)
        ],
        [
            Paragraph("<b>FASCICOLO:</b>", cell_style), 
            Paragraph(fascicolo, cell_style), 
            Paragraph("<b>OGGETTO:</b>", cell_style), 
            Paragraph(oggetto, cell_style)
        ]
    ]
    t_info = Table(info_data, colWidths=[90, 180, 90, 180])
    t_info.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f1f5f9')),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 8))
    
    # Tabella movimenti
    story.append(Paragraph("MOVIMENTI E FLUSSI FINANZIARI REGISTRATI:", section_style))
    tab_mov_data = [[
        Paragraph("<b>CATEGORIA</b>", cell_style), 
        Paragraph("<b>DATA MOV.</b>", cell_style),
        Paragraph("<b>IMPORTO</b>", cell_style), 
        Paragraph("<b>DETTAGLIO / MODALITÀ</b>", cell_style)
    ]]
    
    # Categorie allineate
    categorie = [
        ("INCASSO", "INCASSO: Data", "INCASSO: Importo", "INCASSO: Modalità"),
        ("VERSAMENTO", "VERSAMENTO: Data", "VERSAMENTO: Importo", ""),
        ("GIROCONTO", "GIROCONTO: Data", "GIROCONTO: Importo", ""),
        ("IMPOSTA", "IMPOSTA: Data", "IMPOSTA: Importo", "IMPOSTA: Modalità")
    ]
    
    for cat_nome, col_d, col_i, col_m in categorie:
        r_dates = [d for d in dati_campi.get(col_d, "").split("|") if d.strip()]
        r_imps = [i for i in dati_campi.get(col_i, "").split("|") if i.strip()]
        r_mods = dati_campi.get(col_m, "").split("|") if col_m else []
        
        for idx in range(max(len(r_dates), len(r_imps))):
            d_v = formatta_singola_data(r_dates[idx].strip()) if idx < len(r_dates) else ""
            m_v = r_mods[idx].strip() if idx < len(r_mods) else "-"
            i_raw = r_imps[idx].strip() if idx < len(r_imps) else "0"
            i_float = formatta_singolo_importo(i_raw)
            
            if d_v or i_float > 0:
                tab_mov_data.append([
                    Paragraph(cat_nome, cell_style), 
                    Paragraph(d_v, cell_style),
                    Paragraph(mostra_euro(i_float), cell_bold), 
                    Paragraph(m_v if m_v else "-", cell_style)
                ])
    
    t_mov = Table(tab_mov_data, colWidths=[120, 100, 110, 210])
    t_mov.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(t_mov)
    story.append(Spacer(1, 8))
    
    # Tabella fatture
    story.append(Paragraph("ESTREMI DI FATTURAZIONE ELETTRONICA STUDIO ASSOCIATI:", section_style))
    tab_fat_data = [[
        Paragraph("<b>NUMERO FATTURA / DOC</b>", cell_style), 
        Paragraph("<b>SOGGETTO CLIENTE</b>", cell_style),
        Paragraph("<b>DATA EMISSIONE</b>", cell_style), 
        Paragraph("<b>IMPORTO FATTURATO</b>", cell_style)
    ]]
    
    f_nums = [n for n in dati_campi.get("FATTURA: Numero", "").split("|") if n.strip()]
    f_dates = [d for d in dati_campi.get("FATTURA: Data", "").split("|") if d.strip()]
    f_imps = [i for i in dati_campi.get("FATTURA: Importo", "").split("|") if i.strip()]
    f_clis = [c for c in dati_campi.get("FATTURA: Cliente", "").split("|")]
    
    for idx in range(max(len(f_nums), len(f_dates), len(f_imps), len(f_clis))):
        n_v = f_nums[idx].strip() if idx < len(f_nums) else ""
        d_v = formatta_singola_data(f_dates[idx].strip()) if idx < len(f_dates) else ""
        c_v = f_clis[idx].strip() if idx < len(f_clis) else "-"
        i_raw = f_imps[idx].strip() if idx < len(f_imps) else "0"
        i_float = formatta_singolo_importo(i_raw)
        
        if n_v or d_v or i_float > 0 or c_v != "-":
            tab_fat_data.append([
                Paragraph(n_v, cell_bold), 
                Paragraph(c_v if c_v else "-", cell_style),
                Paragraph(d_v, cell_style), 
                Paragraph(mostra_euro(i_float), cell_bold)
            ])
    
    if len(tab_fat_data) == 1:
        tab_fat_data.append([Paragraph("Nessuna fattura emessa", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style)])
    
    t_fat = Table(tab_fat_data, colWidths=[110, 200, 110, 120])
    t_fat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4b5563')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story.append(t_fat)
    
    doc.build(story)
