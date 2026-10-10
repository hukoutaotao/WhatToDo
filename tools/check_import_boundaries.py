"""Static import/clock boundaries for the selected package; not dynamic sandboxing."""
import ast
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
DOMAIN_STDLIB=frozenset(('__future__','dataclasses','datetime','fractions','typing','hashlib','json','decimal','re','zoneinfo','math','unicodedata'))


def inspect_source(source, *, module):
    layer=module.split('.')[1] if module.startswith('src.') and len(module.split('.'))>1 else None
    errors=[];aliases={}
    tree=ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            names=[a.name for a in node.names]
            for a in node.names:aliases[a.asname or a.name.split('.')[0]]=a.name
        elif isinstance(node,ast.ImportFrom):
            base=node.module or ''
            if node.level:
                parts=module.split('.')[:-node.level]
                base='.'.join(parts+([base] if base else []))
            names=[base]
            for a in node.names:aliases[a.asname or a.name]=base+'.'+a.name
        else:continue
        for name in names:
            top=name.split('.')[0]
            if layer=='domain' and not (top in DOMAIN_STDLIB or name=='src.domain' or name.startswith('src.domain.')):
                errors.append((node.lineno,'DOMAIN_IMPORT',name))
            if layer=='application' and (name=='src.adapters' or name.startswith('src.adapters.') or top in ('tools','tests','psycopg','requests','httpx','openai','anthropic')):
                errors.append((node.lineno,'APPLICATION_BOUNDARY',name))
            if layer=='adapters' and top in ('tools','tests'):errors.append((node.lineno,'ADAPTER_TEST_DEPENDENCY',name))
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        if isinstance(node.func,ast.Name) and node.func.id in ('__import__','eval','exec'):
            errors.append((node.lineno,'DYNAMIC_IMPORT_OR_CODE',node.func.id))
        if layer=='domain' and isinstance(node.func,ast.Attribute) and node.func.attr in ('now','today','utcnow'):
            base=node.func.value
            if isinstance(base,ast.Name) and aliases.get(base.id,'').startswith('datetime'):
                errors.append((node.lineno,'DOMAIN_WALL_CLOCK',node.func.attr))
            elif isinstance(base,ast.Attribute) and isinstance(base.value,ast.Name) and aliases.get(base.value.id)=='datetime':
                errors.append((node.lineno,'DOMAIN_WALL_CLOCK',node.func.attr))
    return tuple(sorted(set(errors)))


def check_tree(root=ROOT):
    errors=[];count=0
    for layer in ('domain','application','adapters'):
        for path in sorted((root/'src'/layer).rglob('*.py')):
            module='.'.join(path.relative_to(root).with_suffix('').parts)
            errors.extend((path.relative_to(root).as_posix(),*e) for e in inspect_source(path.read_text(encoding='utf-8'),module=module));count+=1
    return count,tuple(errors)


def main():
    count,errors=check_tree()
    if errors:
        for e in errors:print(':'.join(map(str,e)),file=sys.stderr)
        return 1
    print(f'{count} package modules: static import/clock boundaries pass; runtime behavior is tested separately')
    return 0


if __name__=='__main__':raise SystemExit(main())
