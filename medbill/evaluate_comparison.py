"""Compare the saved actual Phase 2 OCR outputs, never their expected manifest."""
import json
from pathlib import Path
from medbill.compare import Comparator

ROOT=Path(__file__).resolve().parents[1]


def main():
    destination=ROOT/'docs/phase3'; destination.mkdir(exist_ok=True)
    comparator=Comparator(carrier='01112',locality='05',setting='nonfacility',category='nonQP')
    for name in ['01_clean','02_skewed','03_degraded']:
        extraction=json.loads((ROOT/'docs/phase2'/f'{name}.json').read_text())
        result=comparator.compare(extraction)
        result['input_ocr_sha256']=__import__('hashlib').sha256((ROOT/'docs/phase2'/f'{name}.json').read_bytes()).hexdigest()
        (destination/f'{name}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(name,json.dumps(result['summary']),flush=True)
        for item in result['items']:
            if item['availability']=='compared':
                s=item['statistics']
                print(f"  {item['code']} qty={item['quantity']} charge/unit=${item['unit_charge_usd']} local/unit=${item['unit_benchmark_usd']} p95=${s['p95_usd']} n={s['n']} flag={item['flag']} above=${item['amount_above_benchmark_usd']}",flush=True)
            else:
                print(f"  {item['code']}: {item['availability']}",flush=True)


if __name__=='__main__': main()
