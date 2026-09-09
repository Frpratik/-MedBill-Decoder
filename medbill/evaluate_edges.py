"""Save explicitly synthetic edge fixtures and their actual live HTTP results."""
import json
from pathlib import Path
import httpx
from medbill.edge_samples import fixtures


def main():
    target=Path('docs/phase6'); target.mkdir(parents=True,exist_ok=True)
    results={}
    for name,data in fixtures().items():
        (target/f'{name}.png').write_bytes(data)
        response=httpx.post('http://127.0.0.1:8000/api/decode',content=data,
            headers={'content-type':'application/octet-stream'},params={
                'synthetic':'true','carrier':'01112','locality':'05',
                'setting':'nonfacility','category':'nonQP'},timeout=120)
        response.raise_for_status()
        report=response.json()
        (target/f'{name}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        results[name]={'http':response.status_code,'outcome':report['outcome'],'summary':report['summary']}
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    main()
