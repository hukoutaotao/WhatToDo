"""Synthetic Git objects in a fresh owned scratch repository, never main Git."""
from pathlib import Path
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]


class GitDefinitionFixture:
    def __init__(self,path):
        self.root=Path(path).resolve()
        owned=(ROOT/'.local-state/postgres-tests').resolve()
        if not self.root.is_relative_to(owned) or self.root.name!='git-fixture' or self.root.exists():raise ValueError('FIXTURE_GIT_SCOPE')
        self.root.mkdir(parents=True)
        self.run('init','-q',str(self.root))

    def run(self,*args,raw=None):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_AUTHOR_NAME='Synthetic Fixture',GIT_AUTHOR_EMAIL='fixture@example.invalid',GIT_COMMITTER_NAME='Synthetic Fixture',GIT_COMMITTER_EMAIL='fixture@example.invalid',GIT_TERMINAL_PROMPT='0')
        result=subprocess.run(['git','-C',str(self.root),*args],input=raw,env=env,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise ValueError('FIXTURE_GIT_COMMAND')
        return result.stdout.decode('ascii').strip()

    def commit_objects(self,files):
        rows=[]
        for name,raw in sorted(files.items()):
            if '/' in name or not name.endswith('.json'):raise ValueError('FIXTURE_GIT_PATH')
            oid=self.run('hash-object','-w','--stdin',raw=raw)
            rows.append(f'100644 blob {oid}\t{name}\n')
        tree=self.run('mktree',raw=''.join(rows).encode())
        # Creates an unreferenced synthetic commit object, with no branch/index
        # update, checkout, remote or actual project history modification.
        return self.run('-c','commit.gpgsign=false','commit-tree',tree,'-m','synthetic definition fixtures')
