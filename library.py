"""Catalog index helpers. No game data is downloaded or executed here."""
import json
from pathlib import Path

def load_catalog(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    excluded=set(data.get('excluded_ids', [])); seen=set(); result=[]
    for f in data['files']:
        identifier=f['id']; name=f['name']
        if identifier in seen:
            raise ValueError('duplicate source identifier')
        seen.add(identifier)
        if identifier in excluded:
            continue
        ext=Path(name).suffix.lower()
        if ext not in ('.nes','.sfc','.smc'):
            continue
        result.append({'id':identifier,'name':name,'title':Path(name).stem,'system':'NES' if ext=='.nes' else 'SNES'})
    return result

def filter_catalog(games, category='ALL', query='', favorites=()):
    query=query.strip().casefold(); favorites=set(favorites)
    return [g for g in games if (category=='ALL' or category==g['system'] or (category=='FAVORITES' and g['id'] in favorites)) and query in g['title'].casefold()]
