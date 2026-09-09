"""Send actual synthetic fixture bytes to the running local HTTP server."""
import json
from pathlib import Path
import httpx


def main():
    target=Path('docs/phase5')
    target.mkdir(parents=True,exist_ok=True)
    params=dict(synthetic='true',carrier='01112',locality='05',setting='nonfacility',category='nonQP')
    for name, path in [('clean','output/pdf/01_clean.pdf'),('skewed','samples/02_skewed.png'),
                       ('degraded','output/pdf/03_degraded.pdf')]:
        response=httpx.post('http://127.0.0.1:8000/api/decode',params=params,
            content=Path(path).read_bytes(),headers={'content-type':'application/octet-stream'},timeout=180)
        response.raise_for_status()
        data=response.json()
        # Save only synthetic evaluation output. The server itself never saves reports.
        (target/f'{name}.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(name,'HTTP',response.status_code,json.dumps(data['summary']),json.dumps(data['explanation_summary']))


if __name__=='__main__':
    main()
