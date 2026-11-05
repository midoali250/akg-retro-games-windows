"""Bounded, atomic frontend preferences; never saves game state automatically."""
import json,os,tempfile
from pathlib import Path

def sanitize(value):
    if not isinstance(value,dict):value={}
    mode=value.get('display_mode','FIT');mode=mode if mode in ('FIT','STRETCH') else 'FIT'
    scaling=value.get('scaling','SHARP');scaling=scaling if scaling in ('SHARP','SMOOTH') else 'SHARP'
    favorites=value.get('favorites',[])
    if not isinstance(favorites,list):favorites=[]
    favorites=sorted(set(x for x in favorites[:1000] if isinstance(x,str) and 0<len(x)<=200))
    return {'display_mode':mode,'scaling':scaling,'favorites':favorites}

def read_preferences(path=None):
    path=Path(path) if path is not None else Path.home()/'.retro-collection'/'preferences.json'
    try:
        if path.stat().st_size>262144:return sanitize({})
        return sanitize(json.loads(path.read_text(encoding='utf8')))
    except (OSError,ValueError,UnicodeError):return sanitize({})

def write_preferences(value,path=None):
    path=Path(path) if path is not None else Path.home()/'.retro-collection'/'preferences.json'
    payload=json.dumps(sanitize(value),ensure_ascii=False,indent=2)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.preferences-',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    except BaseException:
        try:os.unlink(name)
        except OSError:pass
        raise
