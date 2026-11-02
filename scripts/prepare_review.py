"""Prepare an offline presentation from existing, hash-verified evidence only."""
from pathlib import Path
from zipfile import ZipFile
import hashlib,json,shutil,html
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'console/office/public'
DEST=PUBLIC/'review'
DEST.mkdir(parents=True,exist_ok=True)
downloads=ROOT.parent
sources={
    'three-path.mp4':downloads/'KAYAN-final-three-path-2026-11-01_v2.mp4',
    'proposal.pdf':ROOT/'output/pdf/KAYAN_TrustGate_Proposal.pdf',
}
expected={
    'three-path.mp4':'884600dc39805af0b2ca3ed00f58f49107378353e9b24adbbf488839121d56f0',
    'proposal.pdf':json.loads((ROOT/'docs/proposal/pdf_verification.json').read_text())['pdf_sha256'],
    'rehearsal-7da73508.mp4':json.loads((ROOT/'eval/reports/checkpoints/functionality_20261101_v1/media/recorded_v2_metadata.json').read_text())['sha256'],
}
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for name,path in sources.items():
    if not path.exists() and (DEST/name).exists():
        assert digest(DEST/name)==expected[name],f'Packaged mismatch: {name}'
        continue
    assert digest(path)==expected[name],f'Source mismatch: {name}'
    shutil.copyfile(path,DEST/name)
original=Path(r'C:\Users\khale\Videos\Screen Recordings\Screen Recording 2026-11-01 155848.mp4')
previous_manifest=json.loads((DEST/'manifest.json').read_text()) if (DEST/'manifest.json').exists() else {}
if original.exists():
    shutil.copyfile(original,DEST/'rehearsal-7da73508.mp4')
    recovery='Original recording path'
elif (DEST/'rehearsal-7da73508.mp4').exists() and digest(DEST/'rehearsal-7da73508.mp4')==expected['rehearsal-7da73508.mp4']:
    recovery=previous_manifest.get('rehearsal_source','Existing hash-verified packaged recording')
else:
    archive=downloads/'KAYAN-final-delivery-2026-11-01_v2.zip'
    with ZipFile(archive) as z:
        (DEST/'rehearsal-7da73508.mp4').write_bytes(z.read('media/earlier_option_b_live_7da73508.mp4'))
    recovery=f'Recovered unchanged from {archive.name}; original Videos path missing'
for name,value in expected.items(): assert digest(DEST/name)==value,name
evidence=(ROOT/'docs/CLOSURE_EVIDENCE_REVIEW_2026-11-01.md').read_text(encoding='utf-8')
(DEST/'evidence.html').write_text('<!doctype html><meta charset="utf-8"><title>KAYAN evidence table</title><style>body{max-width:1100px;margin:40px auto;font:15px/1.6 system-ui;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Twelve-step evidence and provenance</h1><pre>'+html.escape(evidence)+'</pre>',encoding='utf-8')
report=json.loads((ROOT/'reports/report_7da73508.json').read_text())
(DEST/'recorded-report.json').write_bytes(json.dumps(report,indent=2).encode())
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>KAYAN - Evidence Presentation</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef3f5;color:#102638;font:16px/1.6 system-ui}main{max-width:1100px;margin:auto;padding:32px 22px}h1{font-size:34px;margin:0}h2{font-size:22px}header,section{background:white;border:1px solid #cedbdf;border-radius:12px;padding:24px;margin-bottom:20px}.label{color:#237a72;font-weight:700;letter-spacing:.08em;font-size:13px}.notice{border-left:4px solid #f5a623;background:#fff7e7;padding:14px}.links{display:flex;gap:12px;flex-wrap:wrap}a{color:#126d74}.button{background:#102638;color:white;padding:10px 16px;border-radius:6px;text-decoration:none}video{display:block;width:100%;max-height:600px;background:#102638;border-radius:8px}code{overflow-wrap:anywhere}.muted{color:#536976}details{margin-top:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}footer{font-size:14px;color:#536976}</style>
<main><header><div class="label">KAYAN TRUSTGATE / RECORDED EVIDENCE</div><h1>Evidence presentation</h1>
<p class="notice">Recorded demonstrations and saved results. This page starts no assessment and is not evidence that the live gate is currently running.</p>
<div class="links"><a class="button" href="/">Open saved 3D console</a><a class="button" href="/review/proposal.pdf" target="_blank">Open proposal PDF</a><a href="/review/evidence.html" target="_blank">Twelve-step evidence table</a><a href="/review/recorded-report.json" target="_blank">Recorded report JSON</a></div></header>
<section><h2>1. Three-path product walkthrough</h2><p>Hypothetical Risk Plan → direct mitigation (Option A) → mitigation from the saved completed assessment (Option B). No fresh engagement ran during this recording.</p><video controls preload="metadata" src="/review/three-path.mp4"></video></section>
<section><h2>2. Recorded real-model rehearsal</h2><p><code>7da73508-01e6-48e9-9093-be09c5fd734d</code><br>2 findings / 29 allowed / 1 denied, including the deliberate tainted-input test. This is the earlier recorded local-model run, not a live run today.</p><video controls preload="metadata" src="/review/rehearsal-7da73508.mp4"></video><p class="muted">69.97-second original clip. At about 24s the new run is active; about 40s shows Web-App inference, 55s Reporting, and 65s the saved report. These are previously inspected observations, not new timing measurements.</p></section>
<section><h2>3. Proposal and verification record</h2><p>The eight-page proposal includes all five confirmed students, the six TA sections and deliverables coverage. The grounding regression and equal v2 outcomes remain disclosed.</p><p><strong>No grounding improvement was demonstrated. Preserve this failure.</strong></p><div class="links"><a class="button" href="/review/proposal.pdf" target="_blank">Read proposal</a><a href="/review/manifest.json" target="_blank">Artifact hashes and provenance</a></div></section><footer>Offline review uses the original saved session. Gate execution remains subject to the current host controls; recordings do not override authorization.</footer></main></html>'''
sharing_pdf=ROOT/'output/pdf/KAYAN_Evidence_Presentation.pdf'
if sharing_pdf.is_file():
    shutil.copyfile(sharing_pdf,DEST/'presentation.pdf')
    page=page.replace('<a class="button" href="/review/proposal.pdf" target="_blank">Open proposal PDF</a>',
        '<a class="button" href="/review/presentation.pdf" target="_blank">Sharing PDF with video links</a><a href="/review/proposal.pdf" target="_blank">Original proposal</a>')
(PUBLIC/'review.html').write_bytes(page.encode('utf-8'))
manifest={'prepared_at_utc':datetime.now(timezone.utc).isoformat(),'new_engagement_started':False,'rehearsal_source':recovery,
    'artifacts':[{ 'file':name,'bytes':(DEST/name).stat().st_size,'sha256':value} for name,value in expected.items()]}
(DEST/'manifest.json').write_bytes(json.dumps(manifest,indent=2).encode())
print(json.dumps(manifest))
