"""Generate three labeled synthetic bills; charges are invented TEST INPUTS.

These are not pricing references. No names, accounts, or addresses are copied
from any real patient. Layout sources are documented in samples/README.md.
"""
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parents[1]
SAMPLES=[
    {'id':'01_clean','title':'SYNTHETIC OUTPATIENT CLINIC','layout':'standard','rows':[
        ['07/15/2026','99213','Office visit - established patient','1','250.00'],
        ['07/15/2026','71046','Chest X-ray - two views','1','180.00'],
        ['07/15/2026','93000','Electrocardiogram complete','1','135.00'],
        ['07/15/2026','80053','Comprehensive metabolic panel','1','95.00']]},
    {'id':'02_skewed','title':'SYNTHETIC REHABILITATION CLINIC','layout':'unit_price','rows':[
        ['07/20/2026','97110','Therapeutic exercises','2','180.00'],
        ['07/20/2026','71046-26','Chest X-ray interpretation','1','75.00'],
        ['07/20/2026','93000','Electrocardiogram complete','1','135.00'],
        ['07/20/2026','G0008','Influenza vaccine administration','1','40.00']]},
    {'id':'03_degraded','title':'SYNTHETIC COMMUNITY CLINIC','layout':'standard','rows':[
        ['08/04/2026','99214','Office visit - established patient','1','320.00'],
        ['08/04/2026','J1885','Injection ketorolac per 15 mg','2','60.00'],
        ['08/04/2026','?????','Unclear procedure code','1','88.00'],
        ['08/04/2026','80053','Comprehensive metabolic panel','-','95.00'],
        ['08/04/2026','99213','Office visit - amount obscured','1','????']]}
]


def bill_pdf(sample):
    buffer=io.BytesIO()
    c=canvas.Canvas(buffer,pagesize=(612,792),invariant=1)
    c.setTitle(sample['id']+' - SYNTHETIC TEST BILL - NOT FOR PAYMENT')
    c.setAuthor('MedBill Decoder synthetic fixture generator')
    c.setFillColor(HexColor('#e8eff4')); c.rect(32,670,548,90,fill=1,stroke=0)
    c.setFillColor(HexColor('#173c4b')); c.setFont('Helvetica-Bold',16)
    c.drawString(44,733,sample['title'])
    c.setFont('Helvetica-Bold',11); c.drawString(44,707,'SYNTHETIC TEST BILL - NOT FOR PAYMENT')
    c.setFont('Helvetica',10); c.drawString(44,689,'All identities and charges are fabricated for software testing.')
    c.setFillColor(HexColor('#222222')); c.setFont('Helvetica-Bold',13)
    c.drawString(42,640,'ITEMIZED STATEMENT')
    c.setFont('Helvetica',10)
    c.drawString(42,616,'Patient: TEST PERSON '+sample['id'][:2])
    c.drawString(350,616,'Account: SAMPLE-'+sample['id'][:2])
    c.drawString(42,598,'Statement date: 08/15/2026')
    c.drawString(350,598,'Currency: USD')
    c.setFont('Helvetica-Bold',9)
    if sample['layout']=='unit_price':
        labels=[(42,'Date'),(108,'Description'),(315,'Code'),(395,'Qty'),(432,'Price'),(511,'Charge')]
    else:
        labels=[(42,'Date'),(111,'Code'),(184,'Description'),(455,'Qty'),(511,'Charge')]
    c.setFillColor(HexColor('#e8eff4')); c.rect(36,558,540,22,fill=1,stroke=0)
    c.setFillColor(HexColor('#222222'))
    for x,label in labels: c.drawString(x,565,label)
    y=535
    for row in sample['rows']:
        date,code,desc,qty,charge=row
        c.setFont('Helvetica',9)
        c.drawString(42,y,date)
        if sample['layout']=='unit_price':
            c.drawString(108,y,desc); c.drawString(315,y,code); c.drawString(395,y,qty)
            c.drawString(432,y,f'${float(charge)/float(qty):.2f}')
        else:
            c.drawString(111,y,code); c.drawString(184,y,desc); c.drawString(455,y,qty)
        c.drawString(511,y,('$'+charge) if charge!='????' else '????')
        c.setStrokeColor(HexColor('#cccccc')); c.setLineWidth(0.4); c.line(36,y-12,576,y-12)
        y-=42
    y-=22
    c.setFont('Helvetica-Bold',11)
    if sample['id']!='03_degraded':
        total=sum(float(row[4]) for row in sample['rows'])
        c.drawString(350,y,'Total charges:'); c.drawString(511,y,f'${total:.2f}')
        c.setFont('Helvetica',10)
        c.drawString(350,y-24,'Insurance payments:'); c.drawString(511,y-24,'$0.00')
        c.drawString(350,y-48,'Patient balance:'); c.drawString(511,y-48,f'${total:.2f}')
    else:
        c.drawString(42,y,'Total charges: unreadable in this synthetic test')
    c.setStrokeColor(HexColor('#173c4b')); c.line(36,110,576,110)
    c.setFont('Helvetica',9)
    c.drawString(42,91,'TEST FIXTURE ONLY. Do not use these amounts as reference prices.')
    c.drawString(42,75,'Contact: no real provider. Payment instructions intentionally omitted.')
    c.drawRightString(570,48,'Page 1 of 1')
    c.save()
    return buffer.getvalue()


def raster(data,scale=300/72):
    with pdfium.PdfDocument(data) as doc:
        page=doc[0]
        try:
            bitmap=page.render(scale=scale)
            try: return bitmap.to_pil().convert('RGB').copy()
            finally: bitmap.close()
        finally: page.close()


def degrade(image,angle,blur,noise):
    array=np.asarray(image).copy()
    h,w=array.shape[:2]
    matrix=cv2.getRotationMatrix2D((w/2,h/2),angle,1)
    array=cv2.warpAffine(array,matrix,(w,h),borderValue=(255,255,255))
    array=cv2.GaussianBlur(array,(3,3),blur)
    rng=np.random.default_rng(2026)
    shadow=np.linspace(0,24,w)[None,:,None]
    array=np.clip(array.astype(float)-shadow+rng.normal(0,noise,array.shape),0,255).astype('uint8')
    return Image.fromarray(array)


def main():
    out=ROOT/'output/pdf'; out.mkdir(parents=True,exist_ok=True)
    inputs=ROOT/'samples'; inputs.mkdir(exist_ok=True)
    manifest=[]
    for sample in SAMPLES:
        original=bill_pdf(sample)
        if sample['id']=='01_clean':
            final=original; path=out/(sample['id']+'.pdf')
        elif sample['id']=='02_skewed':
            final=original
            image=degrade(raster(original,200/72),3.0,0.5,2.0)
            path=inputs/(sample['id']+'.png'); image.save(path)
        else:
            image=degrade(raster(original,180/72),-2.0,0.8,3.0)
            buffer=io.BytesIO(); c=canvas.Canvas(buffer,pagesize=(612,792),invariant=1)
            c.setTitle('SYNTHETIC DEGRADED TEST BILL - NOT FOR PAYMENT')
            c.drawImage(ImageReader(image),0,0,width=612,height=792); c.save()
            final=buffer.getvalue(); path=out/(sample['id']+'.pdf')
        (out/(sample['id']+'.pdf')).write_bytes(final)
        manifest.append({'id':sample['id'],'input':path.relative_to(ROOT).as_posix(),
                         'synthetic':True,'charges_are_fabricated':True,
                         'expected_rows':[{'service_date':r[0],'code':r[1],'description':r[2],
                            'quantity':r[3],'charged_usd':r[4]} for r in sample['rows']]})
    (inputs/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps([{'id':s['id'],'input':s['input'],'expected_rows':len(s['expected_rows'])} for s in manifest],indent=2))


if __name__=='__main__': main()
