"""Build the current proposal; old HTML supplies design language only."""
from pathlib import Path
import re,json,html
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, Flowable, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/pdf/KAYAN_TrustGate_Proposal.pdf'
NAVY=colors.HexColor('#0F2438'); TEAL=colors.HexColor('#1FB8C4'); GREEN=colors.HexColor('#237A72')
AMBER=colors.HexColor('#F5A623'); MINT=colors.HexColor('#E8F2EE'); INK=colors.HexColor('#1A2B38')
WIDTH=A4[0]-32*mm
for name,file in [('Georgia','georgia.ttf'),('GeorgiaBold','georgiab.ttf'),('GeorgiaItalic','georgiai.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Georgia',normal='Georgia',bold='GeorgiaBold',italic='GeorgiaItalic',boldItalic='GeorgiaBold')
BODY=ParagraphStyle('Body',fontName='Georgia',fontSize=10.1,leading=14.2,textColor=INK,spaceAfter=8)
SMALL=ParagraphStyle('Small',parent=BODY,fontSize=8.1,leading=11.2,spaceAfter=5)
H1=ParagraphStyle('Section',fontName='Helvetica-Bold',fontSize=20,leading=24,textColor=NAVY,spaceAfter=13)
H2=ParagraphStyle('Sub',fontName='Helvetica-Bold',fontSize=11.1,leading=15,textColor=GREEN,spaceAfter=7)
CELL=ParagraphStyle('Cell',parent=SMALL,fontSize=8.5,leading=11.3,spaceAfter=0)

def inline(text):
    text=text.replace('\u2014',' - ').replace('\u2013','-').replace('\u2011','-').replace('\u00a0',' ').replace('\u2192',' to ')
    text=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',text)
    text=html.escape(text)
    text=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`([^`]+)`',r'<font name="Helvetica">\1</font>',text)
    return text

def p(text,style=BODY): return Paragraph(inline(text),style)
def table(rows,widths):
    styled=[]
    for i,row in enumerate(rows):
        style=ParagraphStyle('th',parent=CELL,fontName='Helvetica-Bold',textColor=colors.white) if i==0 else CELL
        styled.append([p(str(cell),style) for cell in row])
    result=Table(styled,colWidths=widths,hAlign='LEFT',repeatRows=1)
    result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,MINT]),
        ('BOX',(0,0),(-1,-1),.5,colors.HexColor('#A6BFB9')),('INNERGRID',(0,0),(-1,-1),.35,colors.HexColor('#C4D4D0')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    return result

def callout(label,text,dark=False):
    fg=colors.white if dark else INK
    st=ParagraphStyle('Callout',parent=BODY,fontSize=9.4,leading=13,textColor=fg,spaceAfter=0)
    title=ParagraphStyle('CalloutTitle',parent=H2,fontSize=8.5,leading=11,textColor=AMBER if dark else GREEN,spaceAfter=4)
    t=Table([[p(label,title)],[p(text,st)]],colWidths=[WIDTH-18])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY if dark else MINT),('LINEBEFORE',(0,0),(0,-1),3,AMBER if dark else GREEN),
        ('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,0),9),('BOTTOMPADDING',(0,-1),(-1,-1),9)]))
    return t

class KMark(Flowable):
    def __init__(self): Flowable.__init__(self); self.width=52; self.height=52
    def draw(self):
        c=self.canv;c.setFillColor(NAVY);c.roundRect(0,0,52,52,3,fill=1,stroke=0)
        c.setFillColor(TEAL);c.rect(12,16,8,29,fill=1,stroke=0)
        c.setFillColor(AMBER);c.rect(12,7,8,7,fill=1,stroke=0)
        for angle,y,color in [(45,34,AMBER),(-45,20,TEAL)]:
            c.saveState();c.translate(31,y);c.rotate(angle);c.setFillColor(color);c.roundRect(-4,-12,8,24,1,fill=1,stroke=0);c.restoreState()

class Hero(Flowable):
    def __init__(self,path): Flowable.__init__(self); self.width=WIDTH; self.height=185; self.path=path
    def draw(self):
        c=self.canv;c.saveState();clip=c.beginPath();clip.roundRect(0,0,self.width,self.height,7);c.clipPath(clip,stroke=0)
        height=self.width*764/1159
        c.drawImage(str(self.path),0,(self.height-height)/2,width=self.width,height=height)
        c.restoreState()

class Architecture(Flowable):
    def __init__(self): Flowable.__init__(self); self.width=WIDTH; self.height=143
    def draw(self):
        c=self.canv;w=self.width;bw=(w-32)/3;bh=37
        boxes=[(0,96,'Signed ROE','Scope, roles and expiry'),(bw+16,96,'Rust / Cedar gate','ALLOW / DENY'),(2*(bw+16),96,'Audit trail','Hash chain + HMAC'),
               (0,33,'Shared Qwen','Planner + four specialists'),(bw+16,33,'Bounded tools','Independent reproduction'),(2*(bw+16),33,'Owned lab','127.0.0.1:8888')]
        for x,y,title,sub in boxes:
            c.setFillColor(MINT);c.setStrokeColor(GREEN);c.roundRect(x,y,bw,bh,5,fill=1,stroke=1)
            c.setFillColor(NAVY);c.setFont('Helvetica-Bold',9);c.drawCentredString(x+bw/2,y+22,title)
            c.setFont('Helvetica',7.7);c.drawCentredString(x+bw/2,y+9,sub)
        c.setStrokeColor(GREEN);c.setLineWidth(1)
        for x,y in [(bw,114),(2*bw+16,114),(2*bw+16,51)]:
            c.line(x,y,x+15,y);c.line(x+15,y,x+11,y+3);c.line(x+15,y,x+11,y-3)
        gate_x=bw+16+bw/2
        c.line(bw/2,70,bw/2,84);c.line(bw/2,84,gate_x-28,84);c.line(gate_x-28,84,gate_x-28,96)
        c.line(gate_x-28,96,gate_x-31,92);c.line(gate_x-28,96,gate_x-25,92)
        c.line(gate_x+28,96,gate_x+28,70);c.line(gate_x+28,70,gate_x+25,74);c.line(gate_x+28,70,gate_x+31,74)
        c.setFillColor(GREEN);c.setFont('Helvetica',7.5);c.drawString(bw/2+5,74,'Requests are authorized before execution')
        c.setFillColor(NAVY);c.roundRect(0,0,w,22,4,fill=1,stroke=0)
        c.setFillColor(colors.white);c.setFont('Helvetica-Bold',8.5);c.drawCentredString(w/2,8,'FastAPI sessions  /  HTTP + WebSocket  /  live 3D operations console')

def chrome(c,doc):
    c.saveState();c.setStrokeColor(colors.HexColor('#C4D4D0'));c.line(16*mm,A4[1]-13*mm,A4[0]-16*mm,A4[1]-13*mm)
    c.setFont('Helvetica-Bold',7.3);c.setFillColor(GREEN);c.drawString(16*mm,A4[1]-11*mm,'KAYAN TRUSTGATE  /  CYBERSECURITY PROJECT PROPOSAL')
    c.setFont('Georgia',7.4);c.setFillColor(colors.HexColor('#66757D'));c.drawString(16*mm,9*mm,'TA review  |  1 November 2026')
    c.drawRightString(A4[0]-16*mm,9*mm,f'KAYAN  |  {doc.page}');c.restoreState()

def build():
    students=json.loads((ROOT/'docs/proposal/students.json').read_text())
    text=(ROOT/'docs/TA_PROPOSAL_REPORT.md').read_text(encoding='utf-8')
    sections=re.split(r'^## (\d\. .+)$',text,flags=re.M)
    assert len(sections)==13
    story=[Spacer(1,5),KMark(),Spacer(1,12),p('KAYAN TRUSTGATE',ParagraphStyle('CoverTitle',parent=H1,fontSize=29,leading=34)),
        p('Governed Autonomous Pentesting',ParagraphStyle('Subtitle',parent=H2,fontSize=16,leading=21)),
        p('Project proposal and implementation report',BODY),Spacer(1,7)]
    image=ROOT/'eval/reports/checkpoints/ta_meeting_20261101_preflight/meeting-ready-office.jpg'
    story.extend([Hero(image),p('Actual 3D operations console; screenshot cropped for the cover.',SMALL),Spacer(1,7),p('SUBMITTED BY',H2),
        table([['Student name','Student ID','Program']]+[[s['name'],s['student_id'],s['program']] for s in students],[WIDTH*.58,WIDTH*.18,WIDTH*.24]),Spacer(1,11),
        callout('PROJECT FOCUS','Signed Rules of Engagement, deterministic policy enforcement, inspectable agent sessions and evidence-based reporting.'),
        Spacer(1,6),p('Six TA sections are followed by a deliverables coverage matrix. Evaluation results, methodology substitutions and open limitations are stated explicitly.',SMALL)])
    for index in range(1,len(sections),2):
        heading,body=sections[index],sections[index+1]
        number=int(heading[0]);story.extend([PageBreak(),p(heading,H1)])
        if number==1: story.extend([Architecture(),Spacer(1,12)])
        for paragraph in body.strip().split('\n\n'):
            if paragraph.startswith('**No grounding improvement'):
                first,rest=paragraph.split('**',2)[1:]
                story.extend([callout('RECORDED EVALUATION RESULT',first,dark=True),Spacer(1,9)])
                if rest.strip(): story.append(p(rest.strip()))
            else: story.append(p(paragraph))
    story.extend([PageBreak(),p('TA Deliverables - Coverage Summary',H1),
        p('This crosswalk records how the requested deliverables map to the current implementation. Substitutions are explicit and are not represented as completed training or a second model.',BODY)])
    rows=[['TA requirement','Current delivery','Status'],
        ['Red / Blue Team structure','Recon, Web-App, Network = Red; Reporting = Blue; Planner coordinates.','Implemented'],
        ['Base and distinct helper model','One shared Qwen model with role-specific contracts; no separate helper model.','Design substitution'],
        ['Six organization/context inputs','Six optional descriptive fields; zero policy weight. Signed scope remains separate.','Implemented'],
        ['Phase 1 Risk Plan','Offline TF-IDF hypotheses, up to three risks, uncertainty and references.','Implemented'],
        ['Option A - direct mitigation','Reporting consumes hypotheses; no target testing, zero verified findings.','Implemented'],
        ['Option B - pentest to mitigation','Governed live testing, independently reproduced findings, shared mitigation shape.','Implemented'],
        ['Strategic frameworks / dynamic cost','Defense in Depth / Zero Trust filters; additive illustrative points and selection export.','Bounded implementation'],
        ['LLM training-time comparison','No fine-tuning experiment. Pretrained-model retrieval grounding evaluated off/on. No time figure or winner invented.','Methodology substitution'],
        ['Combined ATT&CK + OWASP approach','Both are included in the pinned local retrieval index. No demonstrated grounding gain.','Implemented; negative/equal outcome'],
        ['Blue Team task allocation','Reporting owns mitigation synthesis in both Phase 2 paths.','Resolved']]
    story.extend([table(rows,[WIDTH*.24,WIDTH*.57,WIDTH*.19]),Spacer(1,12),
        callout('EVIDENCE BOUNDARY','Original v1 grounding regressed; v2 off/on outcomes were equal. Reproduction, legacy evidence precision and five-label lab coverage are separate metrics. No classification-accuracy or mitigation-effectiveness claim is made.'),Spacer(1,12),
        p('Evidence guide',H2),p('Canonical project documents: TA_PROPOSAL_REPORT.md; TA_DELIVERABLES_ALIGNMENT.md; CLOSURE_EVIDENCE_REVIEW_2026-11-01.md; TA_MEETING_READINESS_2026-11-01.md. Recorded experiments: live_grounding_comparison.md; live_grounding_comparison_v2_bounded_retry.md; pentagi_go_comparison_2026-11-01.md. These are dated evidence records, not newly rerun comparisons.',SMALL)])
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=22*mm,bottomMargin=18*mm,
        title='KAYAN TrustGate - Project Proposal',author='; '.join(s['name'] for s in students),subject='TA deliverables and verified implementation')
    doc.afterPage=lambda: chrome(doc.canv,doc)
    doc.build(story)
    print(OUT)

if __name__=='__main__':build()
