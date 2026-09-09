"""Measure Python file writes, network connects and scratch artifacts during real HTTP decoding.

Run in a fresh process. The audit hook is observational, not a mock or a sandbox.
It does not instrument native child-process system calls or operating-system paging.
"""
import hashlib
import json
import os
import shlex
import stat
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
from fastapi.testclient import TestClient
from medbill.app import app, ROOT, SAMPLES
from medbill.edge_samples import fixtures
from medbill.reference import DEFAULT_DB


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def main():
    cases = {name: path.read_bytes() for name,path in SAMPLES.items()} | fixtures() | {'corrupt':b'not an image'}
    events = {'file_mutations': [], 'pipe_write_opens': 0, 'network_connects': [], 'child_processes': []}
    active = False

    def audit(event, args):
        if not active:
            return
        if event == 'open':
            path, mode, flags = args
            if (isinstance(mode,str) and any(m in mode for m in 'wax+')) or (
                    isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                if isinstance(path,int) and stat.S_ISFIFO(os.fstat(path).st_mode):
                    events['pipe_write_opens'] += 1
                else:
                    events['file_mutations'].append({'event': event, 'path':str(path)})
        elif event in ('os.remove','os.rename','os.mkdir','os.rmdir'):
            events['file_mutations'].append({'event':event,'path':str(args[0])})
        elif event == 'socket.connect':
            events['network_connects'].append(str(args[1]))
        elif event == 'subprocess.Popen':
            command = args[1]
            if isinstance(command,str):
                command = shlex.split(command,posix=False)
            executable = args[0] or command[0]
            events['child_processes'].append({'executable':Path(executable.strip('"')).name,
                                              'arguments':list(command[1:])})

    sys.addaudithook(audit)
    before = digest(DEFAULT_DB)
    original_dir = Path.cwd()
    old_env = {key:os.environ.get(key) for key in ('TMP','TEMP','TMPDIR')}
    results = {}
    with tempfile.TemporaryDirectory(prefix='medbill-audit-') as scratch:
        work = Path(scratch)/'working'; work.mkdir()
        temp = Path(scratch)/'temp'; temp.mkdir()
        for key in old_env:
            os.environ[key]=str(temp)
        try:
            os.chdir(work)
            with TestClient(app) as client:
                for name,data in cases.items():
                    active = True
                    try:
                        response = client.post('/api/decode',content=data,
                            headers={'content-type':'application/octet-stream'},params={
                                'synthetic':'true','carrier':'01112','locality':'05',
                                'setting':'nonfacility','category':'nonQP'})
                    finally:
                        active = False
                    body=response.json()
                    results[name]={'status':response.status_code,'outcome':body.get('outcome'),
                                   'cache_control':response.headers.get('cache-control')}
            artifacts=[p.relative_to(scratch).as_posix() for p in Path(scratch).rglob('*') if p.is_file()]
        finally:
            active=False
            os.chdir(original_dir)
            for key,value in old_env.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value
    after=digest(DEFAULT_DB)
    evidence={'cases':results,**events,'scratch_files_after_processing':artifacts,
              'reference_sha256_before':before,'reference_sha256_after':after,
              'reference_unchanged':before==after,
              'scope':'Python audit events during in-process HTTP handling, child command arguments, scratch working/temp files, reference hash. Native child syscalls and OS paging are not traced.'}
    evidence['passed']=(not events['file_mutations'] and not events['network_connects'] and not artifacts
                        and before==after and all(r['status']==(422 if n=='corrupt' else 200) for n,r in results.items())
                        and all(r['cache_control']=='no-store' for r in results.values())
                        and len(events['child_processes'])==7
                        and all(p['arguments'][:2]==['stdin','stdout'] for p in events['child_processes']))
    print(json.dumps(evidence,indent=2))
    if not evidence['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
