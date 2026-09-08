"""Run OCR against three synthetic fixtures and record actual results.

Expected values are loaded only AFTER extract() returns. They are never passed
to OCR or parsing and never used to fix a recognition error.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

from medbill.ocr import extract, tesseract_path

ROOT=Path(__file__).resolve().parents[1]


def main():
    manifest=json.loads((ROOT/'samples/manifest.json').read_text())
    destination=ROOT/'docs/phase2'; destination.mkdir(exist_ok=True)
    version=subprocess.run([tesseract_path(),'--version'],capture_output=True,text=True).stdout.splitlines()[0]
    reports=[]
    for sample in manifest:
        if sample['synthetic'] is not True:
            raise ValueError('Evaluator accepts synthetic fixtures only.')
        data=(ROOT/sample['input']).read_bytes()
        result=extract(data)
        result['input_sha256']=hashlib.sha256(data).hexdigest()
        result['engine_version']=version
        (destination/(sample['id']+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        (destination/(sample['id']+'.txt')).write_text('\n\n'.join(p['text'] for p in result['pages']),encoding='utf-8')
        discrepancies=[]
        expected_rows=sample['expected_rows']
        if len(result['items'])!=len(expected_rows):
            discrepancies.append({'field':'row_count','expected':len(expected_rows),'actual':len(result['items'])})
        for index,(expected,actual) in enumerate(zip(expected_rows,result['items'])):
            code,*modifier=expected['code'].split('-')
            known=code!='?????'
            normalized={'service_date':dt.datetime.strptime(expected['service_date'],'%m/%d/%Y').date().isoformat(),
                        'code':code if known else None,'modifier':(modifier[0] if modifier else '') if known else None,
                        'description':expected['description'],'quantity':None if expected['quantity']=='-' else expected['quantity'],
                        'charged_usd':None if expected['charged_usd']=='????' else expected['charged_usd']}
            for field,value in normalized.items():
                if actual[field]!=value:
                    discrepancies.append({'row':index+1,'field':field,'expected':value,'actual':actual[field]})
        report={'sample':sample['id'],'input':sample['input'],'engine_version':version,
                **result['summary'],'expected_rows':len(expected_rows),'discrepancies':discrepancies,
                'deskew_degrees':[p['deskew_correction_degrees'] for p in result['pages']],
                'review_reasons':[{'row':i+1,'issues':item['issues']} for i,item in enumerate(result['items']) if item['issues']]}
        reports.append(report)
        print(json.dumps(report,indent=2),flush=True)
        for item in result['items']:
            print(f"  {item['code']} {item['modifier']} | qty={item['quantity']} | ${item['charged_usd']} | {item['status']}",flush=True)
    (destination/'evaluation.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')


if __name__=='__main__': main()
