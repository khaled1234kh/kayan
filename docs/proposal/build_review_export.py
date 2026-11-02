"""Export the review page as a self-contained PDF plus portable HTML/video ZIP."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib,json,re,html
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from pypdf import PdfReader,PdfWriter
from pypdf import filters
from pypdf.generic import DictionaryObject,NameObject,ArrayObject,NumberObject,TextStringObject
import build_pdf as design

ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'console/office/public'
MEDIA=PUBLIC/'review'
TMP=ROOT/'tmp/pdfs/review-export'
OUT=ROOT/'output/pdf/KAYAN_Evidence_Presentation_With_Videos.pdf'
PACKAGE=ROOT/'output/packages/KAYAN_Offline_Presentation.zip'
LINKED=ROOT/'output/pdf/KAYAN_Evidence_Presentation.pdf'
WIDTH=design.WIDTH
P=design.p
BODY=design.BODY
SMALL=design.SMALL
HEADING=design.H1
SUB=design.H2

def header(c,doc):
    c.saveState();c.setFillColor(design.GREEN);c.setFont('Helvetica-Bold',7.5)
    c.drawString(16*mm,A4[1]-11*mm,'KAYAN TRUSTGATE / EVIDENCE PRESENTATION')
    c.setStrokeColor(colors.HexColor('#C4D4D0'));c.line(16*mm,A4[1]-13*mm,A4[0]-16*mm,A4[1]-13*mm)
    c.setFillColor(colors.HexColor('#66757D'));c.setFont('Georgia',7.3)
    c.drawString(16*mm,9*mm,'Export prepared 2 November 2026 / Recorded evidence, not a live assessment')
    c.drawRightString(A4[0]-16*mm,9*mm,str(doc.page));c.restoreState()

def document(path,story):
    doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=16*mm,rightMargin=16*mm,topMargin=22*mm,bottomMargin=19*mm)
    doc.afterPage=lambda:header(doc.canv,doc)
    doc.build(story)

def attachment_annotation(writer,page_number,embedded,label):
    annotation=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/FileAttachment'),
        NameObject('/Rect'):ArrayObject([NumberObject(v) for v in [A4[0]-65, A4[1]-115, A4[0]-45,A4[1]-95]]),
        NameObject('/FS'):embedded.pdf_object,NameObject('/Name'):NameObject('/Paperclip'),
        NameObject('/Contents'):TextStringObject(label)})
    page=writer.pages[page_number]
    if '/Annots' not in page: page[NameObject('/Annots')]=ArrayObject()
    page['/Annots'].append(writer._add_object(annotation))

def build():
    TMP.mkdir(parents=True,exist_ok=True);OUT.parent.mkdir(parents=True,exist_ok=True);PACKAGE.parent.mkdir(parents=True,exist_ok=True)
    video_links=json.loads((ROOT/'docs/proposal/video_links.json').read_text(encoding='utf-8'))
    def watch(key,label):
        url=html.escape(video_links[key]['url'],quote=True)
        return Paragraph(f'<link href="{url}" color="#237A72"><b>{label} (Google Drive)</b></link>',SUB)
    manifest=json.loads((MEDIA/'manifest.json').read_text())
    for artifact in manifest['artifacts']:
        assert hashlib.sha256((MEDIA/artifact['file']).read_bytes()).hexdigest()==artifact['sha256']
    prefix=[P('Evidence presentation',HEADING),P('Export of the KAYAN recorded-evidence review page',SUB),
        design.callout('RECORDED EVIDENCE','This PDF starts no assessment. Click the video links to watch in your browser. The complete eight-page proposal and twelve-step evidence table follow. The separate attachment edition also includes the original MP4 files.'),Spacer(1,12),
        P('1. Three-path product walkthrough',SUB),
        P('Hypothetical Risk Plan, direct mitigation (Option A), then mitigation from the saved completed assessment (Option B). No fresh engagement ran during this recording.'),
        Image(str(ROOT/'eval/reports/acceptance/2026-11-01_browser_v2/v2-review-03.jpg'),width=WIDTH,height=WIDTH*700/1244),
        P('Preview from the existing three-path video. Duration: 35.44 seconds.',SMALL),Spacer(1,9),
        watch('three_path','Watch the three-path demonstration'),
        P('The link above opens the publicly shared recording; it does not need the local KAYAN server. An internet connection is required. For offline browser playback, extract the companion presentation ZIP and open index.html.'),
        P('The recordings show the 1 November interface. A later UI redesign was verified on 2 November; these recordings are retained as historical execution evidence.',SMALL),PageBreak(),
        P('2. Recorded real-model rehearsal',HEADING),
        P('Engagement 7da73508-01e6-48e9-9093-be09c5fd734d',SUB),
        design.callout('ESTABLISHED RUN RESULT','2 findings / 29 allowed / 1 denied, including the deliberate tainted-input test. This is the earlier verified local-model run, not a live run today.'),Spacer(1,12),
        Image(str(ROOT/'eval/reports/checkpoints/functionality_20261101_v1/media/recorded_v2_040s.png'),width=WIDTH,height=WIDTH*1392/2560),
        P('Archived recording frame sampled at 40 seconds. Full clip: 69.966633 seconds.',SMALL),Spacer(1,8),
        watch('rehearsal','Watch the recorded live assessment'),
        P('Previously inspected sequence: about 24s the new run is active, 40s shows Web-App inference, 55s Reporting, and 65s the saved report. These are recorded observations, not fresh timing measurements.'),
        P('3. Proposal and verification record',SUB),
        P('The full proposal follows these two review pages and retains its original page numbering. It includes all five confirmed students, the six TA sections and the deliverables matrix. The twelve-step evidence appendix follows the proposal. Full evidence text, the saved report and artifact hashes are also attached.'),
        P('No grounding improvement was demonstrated. Preserve this failure.',ParagraphStyle('Negative',parent=BODY,fontName='GeorgiaBold',textColor=design.GREEN))]
    document(TMP/'review-pages.pdf',prefix)
    prefix_reader=PdfReader(TMP/'review-pages.pdf')
    assert len(prefix_reader.pages)==2,'Review pages overflowed'
    source=(ROOT/'docs/CLOSURE_EVIDENCE_REVIEW_2026-11-01.md').read_text(encoding='utf-8')
    rows=[]
    for line in source.splitlines():
        if line.startswith('| 3D ') or line.startswith('| Planning '):
            columns=[v.strip() for v in line.split('|')[1:-1]]
            assert len(columns)==4
            rows.append(columns)
    assert len(rows)==12
    appendix=[P('Twelve-step evidence appendix',HEADING),P('Original dated observations and limits',SUB),
        P('All observation times below are 1 November 2026, Africa/Cairo. Original screenshot observations remain separate from later timing rechecks. These are per-step records, not a claim that one continuous video covers every check.',SMALL)]
    compact=ParagraphStyle('Evidence',parent=BODY,fontSize=9,leading=12.2,spaceAfter=6)
    title=ParagraphStyle('EvidenceTitle',parent=SUB,fontSize=11,leading=14,spaceBefore=9,spaceAfter=4)
    for label,status,observation,artifact in rows:
        appendix.append(KeepTogether([P(label,title),P('**Status:** '+status,compact),P(observation,compact),P('**Engagement / artifact:** '+artifact,compact)]))
    appendix.extend([Spacer(1,12),design.callout('LATER TASK-START TIMING RECHECK','The original ALLOW screenshots did not measure the roughly-two-second start criterion. A later real deterministic fixture, 31a60c71-26bb-459e-bae4-2a99c0644c7b, was visibly captured within 916.031 ms of publication. Result pixels were observed later; no universal latency bound is claimed. Full provenance and source timestamps are in the attached evidence-table.txt.')])
    document(TMP/'evidence-pages.pdf',appendix)
    writer=PdfWriter()
    for reader in [prefix_reader,PdfReader(MEDIA/'proposal.pdf'),PdfReader(TMP/'evidence-pages.pdf')]:
        for page in reader.pages: writer.add_page(page)
    students=json.loads((ROOT/'docs/proposal/students.json').read_text())
    writer.add_metadata({'/Title':'KAYAN Evidence Presentation - With Video Attachments','/Author':'; '.join(s['name'] for s in students),'/Subject':'Recorded demonstrations, full proposal and evidence table'})
    # Sharing edition: same pages and clickable URIs, without duplicating MP4 payloads.
    sharing=PdfWriter()
    for page in writer.pages: sharing.add_page(page)
    sharing.add_metadata({'/Title':'KAYAN Evidence Presentation - Public Video Links','/Author':'; '.join(s['name'] for s in students)})
    sharing.add_attachment('evidence-table.txt',source.encode('utf-8'))
    sharing.add_attachment('recorded-report.json',(MEDIA/'recorded-report.json').read_bytes())
    sharing.add_attachment('manifest.json',(MEDIA/'manifest.json').read_bytes())
    with LINKED.open('wb') as stream: sharing.write(stream)
    for page_number,name in [(0,'three-path.mp4'),(1,'rehearsal-7da73508.mp4')]:
        attached=writer.add_attachment(name,(MEDIA/name).read_bytes())
        attached.description=TextStringObject('Original hash-verified recording. Save/open from PDF Attachments; no autoplay.')
        attachment_annotation(writer,page_number,attached,name)
    writer.add_attachment('evidence-table.txt',source.encode('utf-8'))
    writer.add_attachment('recorded-report.json',(MEDIA/'recorded-report.json').read_bytes())
    writer.add_attachment('manifest.json',(MEDIA/'manifest.json').read_bytes())
    writer.root_object[NameObject('/PageMode')]=NameObject('/UseAttachments')
    with OUT.open('wb') as stream:writer.write(stream)
    # A browser-playable copy requires ordinary neighboring MP4s, not PDF multimedia support.
    portable=(PUBLIC/'review.html').read_text(encoding='utf-8')
    portable=portable.replace('href="/"','href="http://127.0.0.1:5173/"').replace('Open saved 3D console','Open 3D console (local services required)')
    portable=portable.replace('/review/three-path.mp4','videos/three-path.mp4').replace('/review/rehearsal-7da73508.mp4','videos/rehearsal-7da73508.mp4').replace('/review/','')
    portable=portable.replace('<h1>Evidence presentation</h1>','<h1>Evidence presentation</h1><p>Offline bundle: videos and documents below work without a server. The optional 3D console link needs local services.</p>')
    with ZipFile(PACKAGE,'w',ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('index.html',portable)
        for name in ['three-path.mp4','rehearsal-7da73508.mp4']:z.write(MEDIA/name,'videos/'+name)
        for name in ['proposal.pdf','evidence.html','recorded-report.json','manifest.json']:z.write(MEDIA/name,name)
        z.write(LINKED,'presentation.pdf')
        z.writestr('README.txt','Extract this ZIP completely, then open index.html in a browser. Both videos, the proposal and evidence documents work offline. The optional 3D console link needs the running local project. This ZIP contains no live assessment or executable service.\n')
    # This known, hash-checked MP4 is slightly larger than pypdf's default
    # 75 MB stream limit. Bound the read limit to our own largest attachment.
    filters.MAX_DECLARED_STREAM_LENGTH=max(filters.MAX_DECLARED_STREAM_LENGTH,max((MEDIA/n).stat().st_size for n in ['three-path.mp4','rehearsal-7da73508.mp4']))
    reader=PdfReader(OUT)
    for name in ['three-path.mp4','rehearsal-7da73508.mp4']:
        extracted=reader.attachments[name]
        if isinstance(extracted,list):extracted=extracted[0]
        assert hashlib.sha256(extracted).hexdigest()==hashlib.sha256((MEDIA/name).read_bytes()).hexdigest()
    assert len(reader.pages)==2+8+len(PdfReader(TMP/'evidence-pages.pdf').pages)
    with ZipFile(PACKAGE) as z:
        assert z.testzip() is None
        for name in ['three-path.mp4','rehearsal-7da73508.mp4']:
            assert hashlib.sha256(z.read('videos/'+name)).hexdigest()==hashlib.sha256((MEDIA/name).read_bytes()).hexdigest()
        local_links=[v for v in re.findall(r'(?:src|href)="([^"]+)"',z.read('index.html').decode()) if not v.startswith(('http:','https:','#'))]
        assert all(v in z.namelist() for v in local_links),local_links
    report={'pdf':str(OUT),'pages':len(reader.pages),'bytes':OUT.stat().st_size,'attachments':list(reader.attachments),'video_attachment_hashes_match':True,
            'zip':str(PACKAGE),'zip_bytes':PACKAGE.stat().st_size,'zip_integrity_and_relative_links_verified':True,'inline_video_playback_claimed':False,
            'linked_pdf':str(LINKED),'linked_pdf_bytes':LINKED.stat().st_size,'linked_pdf_pages':len(PdfReader(LINKED).pages),
            'video_links':video_links, 'pdf_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
            'linked_pdf_sha256':hashlib.sha256(LINKED.read_bytes()).hexdigest(),'zip_sha256':hashlib.sha256(PACKAGE.read_bytes()).hexdigest()}
    uri_values=[str(a.get_object().get('/A',{}).get('/URI','')) for page in PdfReader(LINKED).pages for a in page.get('/Annots',[])]
    assert all(item['url'] in uri_values for item in video_links.values())
    assert not any('127.0.0.1' in uri for uri in uri_values)
    report['public_link_annotations_verified']=True
    (ROOT/'docs/proposal/review_export_verification.json').write_bytes(json.dumps(report,indent=2).encode())
    (MEDIA/'presentation.pdf').write_bytes(LINKED.read_bytes())
    print(json.dumps(report))

if __name__=='__main__':build()
