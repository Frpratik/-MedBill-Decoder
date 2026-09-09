"""Setup-only download of pinned CMS archives. Never called by the app runtime."""
import argparse
import hashlib
from pathlib import Path
import tempfile
import urllib.request
from medbill.ingest import ARCHIVES, ROOT


def verify(path, expected):
    with path.open('rb') as source:
        actual=hashlib.file_digest(source,'sha256').hexdigest().upper()
    if actual != expected.upper():
        raise ValueError(f'Checksum mismatch for {path.name}. Review the source; the existing file has not been replaced.')
    return actual


def ensure_archive(directory, filename, expected, *, check_only=False):
    target=Path(directory)/filename
    if target.exists():
        verify(target,expected)
        return 'verified existing'
    if check_only:
        raise FileNotFoundError(f'Missing archive: {filename}')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Unique partial files avoid publishing incomplete data and leave prior data intact.
    with tempfile.NamedTemporaryFile(dir=target.parent,suffix='.part',delete=False) as output:
        partial=Path(output.name)
        try:
            request=urllib.request.Request('https://www.cms.gov/files/zip/'+filename,
                                           headers={'User-Agent':'MedBillDecoder-source-setup/1.0'})
            with urllib.request.urlopen(request,timeout=120) as response:
                while chunk:=response.read(1024*1024):
                    output.write(chunk)
        except BaseException:
            output.close()
            partial.unlink(missing_ok=True)
            raise
    try:
        verify(partial,expected)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return 'downloaded and verified'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true',help='Verify local archives without network access.')
    args=parser.parse_args()
    try:
        for filename,digest in ARCHIVES.values():
            result=ensure_archive(ROOT/'data/raw',filename,digest,check_only=args.check_only)
            print(f'{filename}: {result}',flush=True)
    except (OSError,ValueError) as error:
        parser.exit(1,f'{error}\n')


if __name__=='__main__':
    main()
