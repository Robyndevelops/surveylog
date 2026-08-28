from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from pypdf import PdfReader, PdfWriter
import io, os, requests, tempfile

app = Flask(__name__)
CORS(app)

BLUE       = colors.HexColor('#1a3a6b')
LIGHT_BLUE = colors.HexColor('#e8eef8')
BORDER     = colors.HexColor('#c5d0e8')
MUTED      = colors.HexColor('#5a6a8a')
TEXT       = colors.HexColor('#1a2340')
WHITE      = colors.white
GREEN      = colors.HexColor('#16a34a')
GREEN_LIGHT= colors.HexColor('#f0fdf4')
LIGHT_GREY = colors.HexColor('#f8faff')

SUPABASE_URL = 'https://ufzrapdyybsbcuprwyid.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVmenJhcGR5eWJzYmN1cHJ3eWlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Nzk0ODksImV4cCI6MjA4OTM1NTQ4OX0.nzfA8paQ6rddGXe0E-5v-Df8jFGFHr8qaPbfC-JP1lk'

def S(name, **kw):
    return ParagraphStyle(name, **kw)

def fmt_date(d):
    if not d: return '—'
    try:
        parts = d.split('-')
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        return f"{int(parts[2])} {months[int(parts[1])-1]} {parts[0]}"
    except:
        return d

def get_period_label(date_str):
    try:
        parts = date_str.split('-')
        year, month = int(parts[0]), int(parts[1])
        return f"January – June {year}" if month <= 6 else f"July – December {year}"
    except:
        return None

def is_image(path):
    return path.lower().split('?')[0].endswith(('.jpg','.jpeg','.png','.gif','.webp'))

def fetch_attachment(path):
    try:
        url = f"{SUPABASE_URL}/storage/v1/object/public/{path}"
        r = requests.get(url, timeout=15,
            headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'})
        if r.status_code == 200:
            return r.content
        return None
    except:
        return None

def make_cover(student_name, principal_name, office, period, num_entries, total_hours):
    story = []
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=4, color=BLUE))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph("STUDENT SURVEYOR'S",
        S('t1', fontSize=34, fontName='Helvetica-Bold', textColor=BLUE, alignment=TA_CENTER, spaceAfter=4, leading=42)))
    story.append(Paragraph("DIARY AND LOG BOOK",
        S('t2', fontSize=34, fontName='Helvetica-Bold', textColor=BLUE, alignment=TA_CENTER, spaceAfter=8, leading=42)))
    story.append(Paragraph("Attachment (Practical)",
        S('ey', fontSize=12, fontName='Helvetica-Bold', textColor=TEXT, alignment=TA_CENTER, spaceAfter=0)))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="35%", thickness=1.5, color=BLUE, hAlign='CENTER'))
    story.append(Spacer(1, 10*mm))
    rows = [
        ("Student Surveyor's Name:", student_name),
        ("Principal's Name:",        principal_name),
        ("Principal's Office:",      office),
        ("Period:",                  period),
        ("Total Entries:",           str(num_entries)),
        ("Total Hours:",             str(total_hours)),
    ]
    tdata = [[
        Paragraph(r[0], S('lbl', fontSize=10, fontName='Helvetica-Bold', textColor=MUTED, alignment=TA_RIGHT, leading=14)),
        Paragraph(r[1], S('val', fontSize=10, fontName='Helvetica-Bold', textColor=TEXT, alignment=TA_LEFT, leading=14))
    ] for r in rows]
    info = Table(tdata, colWidths=[76*mm, 92*mm])
    info.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),9),
        ('BOTTOMPADDING',(0,0),(-1,-1),9),('LEFTPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),0.5,BORDER),
    ]))
    story.append(Table([[info]], colWidths=[168*mm], style=TableStyle([
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
    ])))
    story.append(Spacer(1, 10*mm))
    decl_rows = [
        [Paragraph("Principal's Declaration", S('dh', fontSize=11, fontName='Helvetica-Bold', textColor=BLUE)), '', ''],
        [Paragraph("I confirm that the entries in this Diary and Logbook are an accurate record of the candidate's work.",
            S('db', fontSize=10, fontName='Helvetica', textColor=TEXT, leading=15)), '', ''],
        [Spacer(1,6*mm), '', ''],
        [Paragraph("Interim Assessment", S('sl1', fontSize=9, fontName='Helvetica-Bold', textColor=MUTED)), '', ''],
        [Paragraph("Signature: ___________________________________", S('sv1', fontSize=9, fontName='Helvetica', textColor=TEXT)),
         '', Paragraph("Date: _______________", S('sd1', fontSize=9, fontName='Helvetica', textColor=TEXT, alignment=TA_RIGHT))],
        [Spacer(1,5*mm), '', ''],
        [Paragraph("Final Assessment", S('sl2', fontSize=9, fontName='Helvetica-Bold', textColor=MUTED)), '', ''],
        [Paragraph("Signature: ___________________________________", S('sv2', fontSize=9, fontName='Helvetica', textColor=TEXT)),
         '', Paragraph("Date: _______________", S('sd2', fontSize=9, fontName='Helvetica', textColor=TEXT, alignment=TA_RIGHT))],
        [Spacer(1,4*mm), '', ''],
    ]
    decl = Table(decl_rows, colWidths=[90*mm, 28*mm, 46*mm])
    decl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),LIGHT_BLUE),('BOX',(0,0),(-1,-1),1.5,BLUE),
        ('SPAN',(0,0),(-1,0)),('SPAN',(0,1),(-1,1)),('SPAN',(0,2),(-1,2)),
        ('SPAN',(0,3),(-1,3)),('SPAN',(0,5),(-1,5)),('SPAN',(0,6),(-1,6)),('SPAN',(0,8),(-1,8)),
        ('LINEBELOW',(0,4),(-1,4),0.5,BORDER),('LINEBELOW',(0,7),(-1,7),0.5,BORDER),
        ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
        ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),
        ('TOPPADDING',(0,0),(-1,0),12),('BOTTOMPADDING',(0,8),(-1,8),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(Table([[decl]], colWidths=[168*mm], style=TableStyle([
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
    ])))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=4, color=BLUE))
    story.append(PageBreak())
    return story

def make_tally_table(entries_subset, label=None):
    cat_map = {
        "Cadastral Survey (Boundary Reopening)":"Cadastral",
        "Cadastral Survey (Boundary Survey)":"Cadastral",
        "Cadastral Survey (Surveyor's Identification Report)":"Cadastral",
        "Engineering Survey":"Engineering","Topographical Survey":"Topographic",
        "Subdivision":"Subdivision","Strata (Plan Preparation)":"Strata","Plan Preparation":"Cadastral",
    }
    cat_totals = {}
    for e in entries_subset:
        cat = cat_map.get(e.get('job_type',''), e.get('job_type',''))
        hrs = float(e.get('total_hours',0) or 0)
        cat_totals[cat] = cat_totals.get(cat,0) + hrs
    grand = sum(float(e.get('total_hours',0) or 0) for e in entries_subset)
    def fh(n): return int(n) if n==int(n) else round(n,1)
    items = []
    if label:
        items.append(Paragraph(label, S('tlbl', fontSize=10, fontName='Helvetica-Bold', textColor=BLUE, spaceBefore=8, spaceAfter=4)))
    data = [['Nature of Work','Total Hours']]
    for cat,hrs in cat_totals.items():
        data.append([cat, str(fh(hrs))])
    data.append(['TOTAL', str(fh(grand))])
    t = Table(data, colWidths=[120*mm, 46*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),('TEXTCOLOR',(0,0),(-1,0),WHITE),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
        ('FONTNAME',(0,1),(-1,-2),'Helvetica'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),
        ('BACKGROUND',(0,-1),(-1,-1),LIGHT_BLUE),('TEXTCOLOR',(0,-1),(-1,-1),BLUE),
        ('ALIGN',(1,0),(1,-1),'CENTER'),('GRID',(0,0),(-1,-1),0.5,BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-2),[WHITE,LIGHT_GREY]),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),10),
    ]))
    items.append(t)
    items.append(Spacer(1, 6*mm))
    return items

def make_tally(entries):
    story = []
    story.append(Paragraph("TALLY OF HOURS", S('th', fontSize=9, fontName='Helvetica-Bold', textColor=BLUE, spaceBefore=10, spaceAfter=5, letterSpacing=1.5)))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
    story.append(Spacer(1, 4*mm))
    from collections import OrderedDict
    period_entries = OrderedDict()
    for e in entries:
        lbl = get_period_label(e.get('date',''))
        if lbl:
            if lbl not in period_entries:
                period_entries[lbl] = []
            period_entries[lbl].append(e)
    if len(period_entries) > 1:
        for period_lbl, p_entries in period_entries.items():
            story += make_tally_table(p_entries, label=f"Period: {period_lbl}")
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
        story.append(Spacer(1, 4*mm))
        story += make_tally_table(entries, label="Combined Total")
    else:
        story += make_tally_table(entries)
    story.append(PageBreak())
    return story

def make_progress_report(report, period_label):
    obs  = report.get('principal_observations','') if report else ''
    cand = report.get('candidate_comments','') if report else ''
    psig = report.get('principal_signature_date','') if report else ''
    csig = report.get('candidate_signature_date','') if report else ''
    items = []
    head = Table([[
        Paragraph("PRINCIPAL'S PROGRESS REPORT", S('prht', fontSize=9, fontName='Helvetica-Bold', textColor=WHITE, letterSpacing=1)),
        Paragraph(period_label, S('prhs', fontSize=10, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_RIGHT))
    ]], colWidths=[90*mm, 76*mm])
    head.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BLUE),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    items.append(head)
    items.append(Spacer(1,2*mm))
    items.append(Paragraph("To be completed every six (6) months.", S('note', fontSize=8, fontName='Helvetica', textColor=MUTED, spaceAfter=5)))
    items.append(Paragraph("Observations on training to date, experience gained and ability of Trainee:", S('prl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=3)))
    obs_box = Table([[Paragraph(obs if obs else '[Pending]', S('prb', fontSize=10, fontName='Helvetica', textColor=TEXT, leading=15))]], colWidths=[166*mm])
    obs_box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT_BLUE if obs else LIGHT_GREY),('BOX',(0,0),(-1,-1),0.5,BORDER),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    items.append(obs_box)
    items.append(Table([[Paragraph("Signature:",S('sl1',fontSize=9,fontName='Helvetica-Bold',textColor=MUTED)),Paragraph("_______________________________",S('sv1',fontSize=9,fontName='Helvetica',textColor=TEXT)),Paragraph("Date:",S('sl2',fontSize=9,fontName='Helvetica-Bold',textColor=MUTED)),Paragraph(fmt_date(psig) if psig else '________________',S('sd1',fontSize=9,fontName='Helvetica',textColor=TEXT))]],colWidths=[22*mm,70*mm,16*mm,58*mm],style=TableStyle([('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),0)])))
    items.append(Spacer(1,4*mm))
    items.append(Paragraph("Candidate's Comments:", S('prl2', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=3)))
    cand_box = Table([[Paragraph(cand if cand else '[To be completed by candidate]', S('prb2', fontSize=10, fontName='Helvetica', textColor=TEXT, leading=15))]], colWidths=[166*mm])
    cand_box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GREEN_LIGHT if cand else LIGHT_GREY),('BOX',(0,0),(-1,-1),0.5,BORDER),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    items.append(cand_box)
    items.append(Table([[Paragraph("Signature:",S('csl1',fontSize=9,fontName='Helvetica-Bold',textColor=MUTED)),Paragraph("_______________________________",S('csv1',fontSize=9,fontName='Helvetica',textColor=TEXT)),Paragraph("Date:",S('csl2',fontSize=9,fontName='Helvetica-Bold',textColor=MUTED)),Paragraph(fmt_date(csig) if csig else '________________',S('csd1',fontSize=9,fontName='Helvetica',textColor=TEXT))]],colWidths=[22*mm,70*mm,16*mm,58*mm],style=TableStyle([('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),0)])))
    items.append(Spacer(1,6*mm))
    items.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    items.append(Spacer(1,6*mm))
    return KeepTogether(items)

def make_entry(entry, num, total):
    job_type  = entry.get('job_type','')
    date      = entry.get('date','')
    title_ref = entry.get('title_ref','—')
    parish    = entry.get('parish','')
    prop_desc = entry.get('property_desc','—')
    nature    = entry.get('selected_nature',[]) or []
    notes     = entry.get('student_notes','') or ''
    hour_rows = entry.get('hour_rows',[]) or []
    total_hrs = entry.get('total_hours','0')
    parcel    = entry.get('parcel_size','N/A') or 'N/A'
    degree    = entry.get('degree','—') or '—'
    principal = entry.get('principal_comments','') or '[Pending]'
    items = []
    header = Table([[
        Paragraph(job_type.upper(), S('et', fontSize=8, fontName='Helvetica-Bold', textColor=BLUE, letterSpacing=1)),
        Paragraph(f"Entry {num} of {total}", S('er', fontSize=8, fontName='Helvetica', textColor=MUTED, alignment=TA_RIGHT))
    ]], colWidths=[120*mm, 46*mm])
    header.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT_BLUE),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,-1),1.5,BLUE)]))
    items.append(header)
    items.append(Paragraph(prop_desc, S('etl', fontSize=13, fontName='Helvetica-Bold', textColor=TEXT, spaceAfter=3)))
    items.append(Paragraph(f"{parish}  \u00b7  {fmt_date(date)}  \u00b7  {title_ref}  \u00b7  Parcel: {parcel}", S('em', fontSize=9, fontName='Helvetica', textColor=MUTED, spaceAfter=5)))
    items.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    items.append(Spacer(1,3*mm))
    left = []
    left.append(Paragraph("NATURE OF PROFESSIONAL WORK", S('nl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=2)))
    for n in nature:
        left.append(Paragraph(f"\u2013 {n}", S('ni', fontSize=9, fontName='Helvetica', textColor=TEXT, leftIndent=8, spaceAfter=2, leading=13)))
    left.append(Spacer(1,3*mm))
    left.append(Paragraph("STUDENT SURVEYOR'S NOTES", S('snl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=2)))
    left.append(Paragraph(notes if notes else '\u2014', S('nb', fontSize=9, fontName='Helvetica', textColor=TEXT, spaceAfter=3, leading=13)))
    right = []
    right.append(Paragraph("WORK HOURS", S('whl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=2)))
    for row in hour_rows:
        if row.get('hours'):
            right.append(Paragraph(f"{row.get('type','')}: <b>{row.get('hours','')} hrs</b>", S('whr', fontSize=9, fontName='Helvetica', textColor=TEXT, spaceAfter=2, leading=13)))
    right.append(Paragraph(f"<b>Total: {total_hrs} hrs</b>", S('wht', fontSize=9, fontName='Helvetica-Bold', textColor=BLUE, spaceAfter=3)))
    right.append(Spacer(1,3*mm))
    right.append(Paragraph("STUDENT SURVEYOR DEGREE", S('dgl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=2)))
    right.append(Paragraph(degree, S('dgv', fontSize=9, fontName='Helvetica-Bold', textColor=BLUE, spaceAfter=3)))
    right.append(Spacer(1,3*mm))
    right.append(Paragraph("PRINCIPAL'S COMMENTS", S('pcl', fontSize=8, fontName='Helvetica-Bold', textColor=MUTED, spaceAfter=2)))
    right.append(Paragraph(principal, S('pcv', fontSize=9, fontName='Helvetica', textColor=TEXT, spaceAfter=3, leading=13)))
    lt = Table([[c] for c in left], colWidths=[100*mm])
    lt.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
    rt = Table([[c] for c in right], colWidths=[66*mm])
    rt.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1),('LINEBEFORE',(0,0),(0,-1),0.5,BORDER)]))
    two = Table([[lt,rt]], colWidths=[100*mm,68*mm])
    two.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    items.append(two)
    items.append(Spacer(1,4*mm))
    items.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    items.append(Spacer(1,5*mm))
    return KeepTogether(items)

def make_appendix_cover():
    items = []
    items.append(Spacer(1, 55*mm))
    items.append(HRFlowable(width="100%", thickness=4, color=BLUE))
    items.append(Spacer(1, 22*mm))
    items.append(Paragraph("APPENDIX", S('at', fontSize=42, fontName='Helvetica-Bold', textColor=BLUE, alignment=TA_CENTER, spaceAfter=0)))
    items.append(Spacer(1, 14*mm))
    items.append(Paragraph("Survey Plans and Supporting Documents", S('as', fontSize=14, fontName='Helvetica', textColor=MUTED, alignment=TA_CENTER, spaceAfter=0)))
    items.append(Spacer(1, 22*mm))
    items.append(HRFlowable(width="100%", thickness=4, color=BLUE))
    items.append(PageBreak())
    return items

def make_appendix_header(entry_num, entry):
    job_type  = entry.get('job_type', '')
    prop_desc = entry.get('property_desc', '—')
    title_ref = entry.get('title_ref', '—')
    items = []
    header = Table([[
        Paragraph(f"Entry No. {entry_num}", S('ahl', fontSize=11, fontName='Helvetica-Bold', textColor=WHITE)),
        Paragraph(prop_desc, S('ahr', fontSize=11, fontName='Helvetica-Bold', textColor=WHITE, alignment=TA_RIGHT))
    ]], colWidths=[85*mm, 85*mm])
    header.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),BLUE),
        ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),
        ('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
    ]))
    items.append(header)
    items.append(Spacer(1, 2*mm))
    items.append(Paragraph(
        f"{job_type}  ·  {title_ref}",
        S('ameta', fontSize=10, fontName='Helvetica', textColor=MUTED, spaceAfter=0)
    ))
    items.append(Spacer(1, 2*mm))
    items.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    items.append(Spacer(1, 6*mm))
    return items

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    try:
        data             = request.get_json()
        entries          = data.get('entries', [])
        student_name     = data.get('student_name', 'Student Surveyor')
        principal_name   = data.get('principal_name', 'Supervising Surveyor')
        office           = data.get('office', '')
        period           = data.get('period', '2025 – 2026')
        progress_reports = data.get('progress_reports', [])
        filter_period    = data.get('filter_period', None)

        if filter_period:
            entries = [e for e in entries if get_period_label(e.get('date','')) == filter_period]

        total_hours = sum(float(e.get('total_hours',0) or 0) for e in entries)
        def fh(n): return int(n) if n==int(n) else round(n,1)
        th_fmt = fh(total_hours)
        pr_by_label = {r.get('period_label',''): r for r in progress_reports}

        def add_page_number(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(20*mm, 12*mm, f"{student_name}  \u00b7  Surveyor's Logbook  \u00b7  {period}")
            canvas.drawRightString(190*mm, 12*mm, f"Page {doc.page}")
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.5)
            canvas.line(20*mm, 15*mm, 190*mm, 15*mm)
            canvas.restoreState()

        story = []
        story += make_cover(f"{student_name}, BSc.(Hons.)", principal_name, office,
                            filter_period if filter_period else period, len(entries), th_fmt)
        story += make_tally(entries)

        current_period = None
        entry_num = 0
        entries_with_attachments = []

        for e in entries:
            lbl = get_period_label(e.get('date',''))
            if lbl and lbl != current_period:
                if current_period is not None:
                    story.append(PageBreak())
                current_period = lbl
                pr = pr_by_label.get(lbl, {'period_label': lbl})
                story.append(make_progress_report(pr, lbl))
                story.append(Paragraph("LOGBOOK ENTRIES", S('leh', fontSize=9, fontName='Helvetica-Bold', textColor=BLUE, spaceBefore=4, spaceAfter=5, letterSpacing=1.5)))
                story.append(HRFlowable(width="100%", thickness=2, color=BLUE))
                story.append(Spacer(1,4*mm))
            entry_num += 1
            story.append(make_entry(e, entry_num, len(entries)))
            if e.get('attachments'):
                entries_with_attachments.append((entry_num, e))

        # APPENDIX
        has_attachments = bool(entries_with_attachments)
        if has_attachments:
            story.append(PageBreak())
            story += make_appendix_cover()

            page_w = A4[0] - 40*mm
            page_h = A4[1] - 60*mm
            header_h = 28*mm
            pdf_attachments = []

            for entry_num_a, entry in entries_with_attachments:
                raw_attachments = entry.get('attachments', []) or []
                attachments = [
                    (a if isinstance(a, str) else a.get('path', ''))
                    for a in raw_attachments
                    if (isinstance(a, str) or a.get('include', True))
                ]
                for path in attachments:
                    att_data = fetch_attachment(path)
                    if not att_data:
                        continue
                    filename = path.split('/')[-1]

                    if is_image(path):
                        img_avail_h = page_h - header_h
                        story += make_appendix_header(entry_num_a, entry)
                        try:
                            img_buf = io.BytesIO(att_data)
                            img = Image(img_buf)
                            ratio = min(page_w / img.drawWidth, img_avail_h / img.drawHeight)
                            img.drawWidth  *= ratio
                            img.drawHeight *= ratio
                            story.append(Table([[img]], colWidths=[page_w], style=TableStyle([
                                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                                ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                            ])))
                        except:
                            story.append(Paragraph(f"[Could not embed: {filename}]",
                                S('err', fontSize=9, fontName='Helvetica', textColor=MUTED)))
                        story.append(PageBreak())

                    elif path.lower().endswith('.pdf'):
                        pdf_attachments.append((entry_num_a, entry, att_data))

        # Build main PDF
        main_buf = io.BytesIO()
        doc = SimpleDocTemplate(main_buf, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=20*mm, bottomMargin=22*mm,
            title="Student Surveyor's Diary and Log Book",
            author=student_name)
        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
        main_buf.seek(0)

        # Merge PDF attachments
        if has_attachments and pdf_attachments:
            writer = PdfWriter()
            main_reader = PdfReader(main_buf)
            for page in main_reader.pages:
                writer.add_page(page)

            for entry_num_a, entry, pdf_data in pdf_attachments:
                try:
                    hdr_buf = io.BytesIO()
                    hdr_doc = SimpleDocTemplate(hdr_buf, pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=20*mm, bottomMargin=22*mm)
                    hdr_doc.build(make_appendix_header(entry_num_a, entry))
                    hdr_buf.seek(0)
                    hdr_reader = PdfReader(hdr_buf)
                    writer.add_page(hdr_reader.pages[0])
                    att_reader = PdfReader(io.BytesIO(pdf_data))
                    for att_page in att_reader.pages:
                        writer.add_page(att_page)
                except Exception as pe:
                    try:
                        att_reader = PdfReader(io.BytesIO(pdf_data))
                        for att_page in att_reader.pages:
                            writer.add_page(att_page)
                    except:
                        pass

            final_buf = io.BytesIO()
            writer.write(final_buf)
            final_buf.seek(0)
        else:
            final_buf = main_buf

        filename_out = f"Logbook_{student_name.replace(' ','_')}.pdf"
        return send_file(final_buf, mimetype='application/pdf',
                         as_attachment=True, download_name=filename_out)

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
