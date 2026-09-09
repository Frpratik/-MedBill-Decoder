"""Export a clean committed checkout, excluding untracked runtime/setup data."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}',*args],cwd=ROOT)


def main():
    if git('status','--porcelain','--untracked-files=normal').strip():
        raise SystemExit('Commit or otherwise resolve workspace changes before packaging.')
    commit=git('rev-parse','HEAD').decode().strip()
    payload=git('archive','--format=zip','--prefix=MedBillDecoder/','HEAD')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ZIP integrity check failed')
        names=archive.namelist()
        forbidden=('MedBillDecoder/data/raw/','MedBillDecoder/data/processed/',
                   'MedBillDecoder/.venv/','MedBillDecoder/.tools/',
                   'MedBillDecoder/.git/','MedBillDecoder/tmp/','MedBillDecoder/dist/')
        if any(name.startswith(forbidden) or Path(name).name in ('.env','.env.local') for name in names):
            raise SystemExit('Excluded runtime/configuration content found in archive')
        for required in ['README.md','NOTICE.md','requirements.txt','medbill/app.py',
                         'docs/DEVPOST_DRAFT.md','docs/DEMO_VIDEO_SCRIPT.md']:
            if 'MedBillDecoder/'+required not in names:
                raise SystemExit(f'Missing package file: {required}')
    output=ROOT/'dist'; output.mkdir(exist_ok=True)
    package=output/'MedBillDecoder-source.zip'
    package.write_bytes(payload)
    manifest={'commit':commit,'archive':package.name,'bytes':len(payload),
              'sha256':hashlib.sha256(payload).hexdigest(),
              'entries':len(names),'zip_integrity':'passed','excluded_paths_check':'passed',
              'contents':'Committed source, documentation, small source excerpts and synthetic test evidence; no full reference dataset or installed dependencies.',
              'files':names}
    (output/'MedBillDecoder-source.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in manifest.items() if key!='files'},indent=2))


if __name__=='__main__':
    main()
