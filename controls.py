"""Persistent keyboard/gamepad bindings and the desktop control setup screen."""
import json, os, shutil, tempfile
from pathlib import Path
import pygame

ACTIONS=[('UP',4),('DOWN',5),('LEFT',6),('RIGHT',7),('A',8),('B',0),('X',9),('Y',1),('L',10),('R',11),('SELECT',2),('START',3)]
DEFAULT_KEYS={4:pygame.K_UP,5:pygame.K_DOWN,6:pygame.K_LEFT,7:pygame.K_RIGHT,8:pygame.K_x,0:pygame.K_z,9:pygame.K_s,1:pygame.K_a,10:pygame.K_q,11:pygame.K_w,2:pygame.K_RSHIFT,3:pygame.K_RETURN}
DEFAULT_BUTTONS={8:0,0:1,9:2,1:3,10:4,11:5,2:6,3:7}
RESERVED={pygame.K_ESCAPE,pygame.K_g,pygame.K_F5,pygame.K_F8}
BITS=set(DEFAULT_KEYS)

def data_dir():return Path.home()/'.retro-collection'
def empty_controls():return {'keyboard':{},'gamepads':{}}

def valid_binding(spec):
    if not isinstance(spec,dict):return False
    typ=spec.get('type');index=spec.get('index')
    if type(index) is not int or not 0<=index<=127:return False
    if typ=='button':return set(spec)=={'type','index'}
    if typ=='axis':return set(spec)=={'type','index','direction'} and spec['direction'] in (-1,1) and type(spec['direction']) is int
    if typ=='hat':return set(spec)=={'type','index','component','direction'} and spec['component'] in (0,1) and type(spec['component']) is int and spec['direction'] in (-1,1) and type(spec['direction']) is int
    return False

def sanitize_controls(raw):
    result=empty_controls()
    if not isinstance(raw,dict):return result
    keys=raw.get('keyboard',{})
    if isinstance(keys,dict):
        for bit in BITS:
            k=keys.get(str(bit))
            if type(k) is int and 0<=k<2**31 and k not in RESERVED:result['keyboard'][str(bit)]=k
    pads=raw.get('gamepads',{})
    if isinstance(pads,dict):
        for guid,m in list(pads.items())[:64]:
            if not isinstance(guid,str) or not 1<=len(guid)<=64 or not isinstance(m,dict):continue
            clean={str(bit):m[str(bit)] for bit in BITS if valid_binding(m.get(str(bit)))}
            if clean:result['gamepads'][guid]=clean
    return result

def read_controls(path=None):
    path=Path(path) if path is not None else data_dir()/'controls.json'
    try:
        if path.stat().st_size>262144:return empty_controls()
        return sanitize_controls(json.loads(path.read_text(encoding='utf8')))
    except (OSError,ValueError,UnicodeError):return empty_controls()

def write_controls(config,path=None):
    path=Path(path) if path is not None else data_dir()/'controls.json';path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.controls-',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            json.dump(sanitize_controls(config),f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(name,path)
    except BaseException:
        try:os.unlink(name)
        except OSError:pass
        raise

def reset_application(path=None):
    """Remove only this collection's private data after explicit user confirmation."""
    root=Path(path) if path is not None else data_dir()
    if root.is_symlink():raise OSError('Refusing to delete a linked data directory')
    if root.exists():
        if not root.is_dir():raise OSError('App data path is not a directory')
        shutil.rmtree(root)

def scan_gamepads():
    pads=[]
    for index in range(pygame.joystick.get_count()):
        try:
            j=pygame.joystick.Joystick(index);j.init();pads.append(j)
        except pygame.error:pass
    return pads

def binding_active(pad,spec):
    typ=spec['type'];n=spec['index']
    if typ=='button':return n<pad.get_numbuttons() and bool(pad.get_button(n))
    if typ=='axis':return n<pad.get_numaxes() and pad.get_axis(n)*spec['direction']>.35
    return n<pad.get_numhats() and pad.get_hat(n)[spec['component']]*spec['direction']>0

def default_pad_active(pad,bit):
    if bit in DEFAULT_BUTTONS:
        b=DEFAULT_BUTTONS[bit];return b<pad.get_numbuttons() and bool(pad.get_button(b))
    if bit not in (4,5,6,7):return False
    axis,sign,component={4:(1,-1,1),5:(1,1,1),6:(0,-1,0),7:(0,1,0)}[bit]
    if pad.get_numaxes()>axis and pad.get_axis(axis)*sign>.35:return True
    hat_sign=-sign if component==1 else sign
    return pad.get_numhats()>0 and pad.get_hat(0)[component]*hat_sign>0

def input_bits(pads,config,pressed=None):
    if pressed is None:pressed=pygame.key.get_pressed()
    keys=config.get('keyboard',{});bits=set()
    for bit,key in DEFAULT_KEYS.items():
        try:
            if pressed[keys.get(str(bit),key)]:bits.add(bit)
        except (IndexError,KeyError,TypeError):pass
    for pad in pads:
        try:
            if not pad.get_init():continue
            custom=config.get('gamepads',{}).get(pad.get_guid(),{})
            for bit in BITS:
                spec=custom.get(str(bit))
                if binding_active(pad,spec) if spec else default_pad_active(pad,bit):bits.add(bit)
        except (pygame.error,AttributeError,IndexError,KeyError,TypeError):continue
    return bits

def captured_binding(event,controller_instance):
    if getattr(event,'instance_id',None)!=controller_instance:return None
    if event.type==pygame.JOYBUTTONDOWN and 0<=event.button<=127:return {'type':'button','index':event.button}
    if event.type==pygame.JOYAXISMOTION and 0<=event.axis<=127 and abs(event.value)>=.65:return {'type':'axis','index':event.axis,'direction':1 if event.value>0 else -1}
    if event.type==pygame.JOYHATMOTION and 0<=event.hat<=127:
        for component in (0,1):
            if event.value[component] in (-1,1):return {'type':'hat','index':event.hat,'component':component,'direction':event.value[component]}
    return None

def describe_binding(spec):
    if not spec:return 'default'
    if spec['type']=='button':return 'Button '+str(spec['index']+1)
    if spec['type']=='axis':return 'Axis '+str(spec['index']+1)+(' +' if spec['direction']>0 else ' -')
    return 'D-pad '+('X' if spec['component']==0 else 'Y')+(' +' if spec['direction']>0 else ' -')

def control_screen(screen):
    """Modal editor, entered from Settings; connect controllers in the OS first."""
    config=read_controls();pads=scan_gamepads();selected=0;row_selected=0;column_selected=0;capture=None;message='Connect USB/Bluetooth in your system, then click DETECT.';clock=pygame.time.Clock()
    def current():return pads[selected] if pads and selected<len(pads) else None
    while True:
        sw,sh=screen.get_size();sx=sw/1280;sy=sh/720;scale=min(sx,sy)
        def rect(x,y,w,h):return pygame.Rect(round(x*sx),round(y*sy),max(1,round(w*sx)),max(1,round(h*sy)))
        for e in pygame.event.get():
            if e.type==pygame.QUIT:return 'quit'
            if e.type in (pygame.JOYDEVICEADDED,pygame.JOYDEVICEREMOVED):pads=scan_gamepads();selected=0;capture=None;message='Controllers updated.'
            if capture:
                mode,bit=capture
                if e.type==pygame.KEYDOWN and e.key==pygame.K_ESCAPE:capture=None;message='Binding canceled.';continue
                try:
                    if mode=='key' and e.type==pygame.KEYDOWN:
                        if e.key in RESERVED:message='Reserved key: choose another key or ESC to cancel.';continue
                        config['keyboard'][str(bit)]=e.key;write_controls(config);capture=None;message='Keyboard assignment saved.'
                    elif mode=='pad' and current() is not None:
                        binding=captured_binding(e,current().get_instance_id())
                        if binding:config['gamepads'].setdefault(current().get_guid(),{})[str(bit)]=binding;write_controls(config);capture=None;message='Controller assignment saved.'
                except (OSError,pygame.error) as err:capture=None;message='Could not save controls: '+str(err)[:65]
                continue
            if e.type==pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE,pygame.K_g):return None
                if e.key==pygame.K_F5:pads=scan_gamepads();selected=0;message='Detection complete.'
                if e.key==pygame.K_TAB and pads:selected=(selected+1)%len(pads)
                if e.key==pygame.K_UP:row_selected=(row_selected-1)%len(ACTIONS)
                if e.key==pygame.K_DOWN:row_selected=(row_selected+1)%len(ACTIONS)
                if e.key in (pygame.K_LEFT,pygame.K_RIGHT):column_selected=1-column_selected
                if e.key in (pygame.K_RETURN,pygame.K_SPACE):
                    bit=ACTIONS[row_selected][1]
                    if column_selected==0:capture=('key',bit);message='Press a key for '+ACTIONS[row_selected][0]+'; ESC cancels.'
                    elif current() is None:message='Connect a controller in the OS and press DETECT.'
                    else:capture=('pad',bit);message='Press a controller button or move its stick; ESC cancels.'
            if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                x=e.pos[0]/sx;y=e.pos[1]/sy
                if 920<=x<=1120 and 82<=y<=125:pads=scan_gamepads();selected=0;message='Detection complete.';continue
                if 640<=x<=900 and 82<=y<=125 and pads:selected=(selected+1)%len(pads);continue
                if 960<=x<=1120 and 620<=y<=675:return None
                row=int((y-190)//31)
                if 0<=row<len(ACTIONS) and 190+row*31<=y<=218+row*31:
                    bit=ACTIONS[row][1];row_selected=row
                    if 400<=x<=690:column_selected=0;capture=('key',bit);message='Press a keyboard key for '+ACTIONS[row][0]+'; ESC cancels.'
                    elif 710<=x<=1110:
                        column_selected=1
                        if current() is None:message='No controller detected. Connect one in the OS and press DETECT.'
                        else:capture=('pad',bit);message='Press a controller button, D-pad or move a stick for '+ACTIONS[row][0]+'; ESC cancels.'
        screen.fill((9,17,39));font=pygame.font.SysFont('dejavusans',max(12,int(19*scale)));small=pygame.font.SysFont('dejavusans',max(10,int(15*scale)));title=pygame.font.SysFont('dejavusans',max(17,int(28*scale)))
        def label(text,x,y,color=(225,238,250),f=font):screen.blit(f.render(str(text),True,color),rect(x,y,1,1).topleft)
        def button(text,x,y,w,h):pygame.draw.rect(screen,(36,75,105),rect(x,y,w,h),border_radius=6);label(text,x+8,y+8,f=small)
        label('CONTROLLER & KEYBOARD SETTINGS',130,35,(103,225,245),title)
        name=current().get_name() if current() else 'No controller connected'
        button(('NEXT: '+name)[:30],640,82,260,43);button('ADD / DETECT [F5]',920,82,200,43)
        label('ACTION',150,155,(140,190,220),small);label('KEYBOARD — click to assign',400,155,(140,190,220),small);label('CONTROLLER — click to assign',710,155,(140,190,220),small)
        mapping=config['gamepads'].get(current().get_guid(),{}) if current() else {}
        for i,(name,bit) in enumerate(ACTIONS):
            y=190+i*31;label(name,150,y+3)
            button(pygame.key.name(config['keyboard'].get(str(bit),DEFAULT_KEYS[bit])),400,y,290,28)
            button(describe_binding(mapping.get(str(bit))),710,y,400,28)
            if i==row_selected:pygame.draw.rect(screen,(100,230,250),rect(400 if column_selected==0 else 710,y,290 if column_selected==0 else 400,28),width=max(1,int(2*scale)),border_radius=6)
        label(message[:105],130,580,(255,211,139),small);button('BACK / ESC',960,620,160,55)
        label('Arrows / Enter: assign  •  TAB: next controller  •  G, ESC, F5, F8 reserved',130,628,(155,185,210),small)
        pygame.display.flip();clock.tick(60)
