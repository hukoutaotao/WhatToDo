"""Read exact local Git commit blobs; never fetch, checkout, stage or publish."""
import os
from pathlib import Path
import subprocess

from src.application.definitions import DefinitionArtifact,DefinitionError,GitDefinitionRequest,need


class GitDefinitionSource:
    def __init__(self,repository):
        self.repository=Path(repository).resolve()
        actual=self._git('rev-parse','--show-toplevel').decode('utf-8').strip()
        need(Path(actual).resolve()==self.repository,'DEFINITION_GIT_ROOT')

    def _git(self,*args):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_OPTIONAL_LOCKS='0',GIT_NO_REPLACE_OBJECTS='1',GIT_TERMINAL_PROMPT='0')
        try:result=subprocess.run(['git','-C',str(self.repository),*args],env=env,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except (OSError,subprocess.SubprocessError):raise DefinitionError('DEFINITION_GIT_UNAVAILABLE') from None
        need(result.returncode==0,'DEFINITION_GIT_OBJECT_UNAVAILABLE')
        return result.stdout

    def read(self,request):
        need(isinstance(request,GitDefinitionRequest),'DEFINITION_GIT_REQUEST')
        need(self._git('cat-file','-t',request.commit).strip()==b'commit','DEFINITION_GIT_COMMIT')
        expression=request.commit+':'+request.path
        need(self._git('cat-file','-t',expression).strip()==b'blob','DEFINITION_GIT_BLOB')
        size=int(self._git('cat-file','-s',expression));need(0<size<=1048576,'DEFINITION_SIZE')
        oid=self._git('rev-parse','--verify',expression).decode('ascii').strip()
        return DefinitionArtifact(request,oid,self._git('cat-file','blob',expression))
