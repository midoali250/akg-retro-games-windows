"""Experimental desktop game selection with exact ROM identity checks."""
import hashlib,json,sys
from pathlib import Path
from game_session import run_session

def launch_game(game,screen,core_dir,rom_dir,state_dir,max_frames=None,test_manual=False,display_mode='FIT'):
    manifest=json.loads((Path(__file__).parent/'cheats/index.json').read_text(encoding='utf8'))
    matches=[x for x in manifest['games'] if x['source_id']==game['id']]
    if len(matches)!=1:raise ValueError('game missing or ambiguous in identity catalog')
    record=matches[0];system=record['system']
    ext='.nes' if system=='NES' else '.smc' if system=='SNES' else None
    if not ext:raise ValueError('unsupported game system')
    rom=Path(rom_dir)/(record['source_id']+ext)
    suffix='.dll' if sys.platform=='win32' else '.dylib' if sys.platform=='darwin' else '.so'
    core=Path(core_dir)/(('fceumm_libretro' if system=='NES' else 'snes9x_libretro')+suffix)
    if not rom.is_file():raise FileNotFoundError('ROM is not bundled in this preview')
    if not core.is_file():raise FileNotFoundError('emulator core is not bundled in this preview')
    if hashlib.sha256(rom.read_bytes()).hexdigest()!=record['rom_sha256']:raise ValueError('ROM SHA-256 does not match this game')
    return run_session(screen,core,rom,state_dir,max_frames=max_frames,test_manual=test_manual,display_mode=display_mode)
