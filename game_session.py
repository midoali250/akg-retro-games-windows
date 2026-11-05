"""Experimental software-video/PCM game loop for the desktop prototype."""
import os,time,math
from pathlib import Path
import pygame
from libretro_host import LibretroHost
from preferences import read_preferences, write_preferences

KEYS={pygame.K_z:0,pygame.K_a:1,pygame.K_RSHIFT:2,pygame.K_RETURN:3,
      pygame.K_UP:4,pygame.K_DOWN:5,pygame.K_LEFT:6,pygame.K_RIGHT:7,
      pygame.K_x:8,pygame.K_s:9,pygame.K_q:10,pygame.K_w:11}

def frame_surface(host):
    if not host.last_frame or not host.width or not host.height:return None
    bpp=4 if host.pixel_format==1 else 2;stride=host.width*bpp
    if host.pitch<stride:raise ValueError('invalid video pitch')
    data=host.last_frame if host.pitch==stride else b''.join(host.last_frame[y*host.pitch:y*host.pitch+stride] for y in range(host.height))
    masks=(0x00ff0000,0x0000ff00,0x000000ff,0) if bpp==4 else ((0xf800,0x07e0,0x001f,0) if host.pixel_format==2 else (0x7c00,0x03e0,0x001f,0))
    frame=pygame.Surface((host.width,host.height),0,bpp*8,masks);frame.get_buffer().write(data);return frame

def fit_frame(frame_size, screen_size):
    """Center an uncropped frame in the available display using square pixels."""
    fw,fh=frame_size;sw,sh=screen_size
    if min(fw,fh,sw,sh)<=0:raise ValueError('invalid frame or screen size')
    scale=min(sw/fw,sh/fh)
    w=max(1,min(sw,round(fw*scale)));h=max(1,min(sh,round(fh*scale)))
    return pygame.Rect((sw-w)//2,(sh-h)//2,w,h)

def input_bits(joysticks):
    pressed=pygame.key.get_pressed();bits={b for k,b in KEYS.items() if pressed[k]}
    for j in joysticks:
        try:
            if not j.get_init():continue
            for n,bit in [(0,8),(1,0),(2,9),(3,1),(4,10),(5,11),(6,2),(7,3)]:
                if n<j.get_numbuttons() and j.get_button(n):bits.add(bit)
            if j.get_numhats():
                x,y=j.get_hat(0)
                if x<0:bits.add(6)
                if x>0:bits.add(7)
                if y>0:bits.add(4)
                if y<0:bits.add(5)
            if j.get_numaxes()>=2:
                x,y=j.get_axis(0),j.get_axis(1)
                if x<-.35:bits.add(6)
                if x>.35:bits.add(7)
                if y<-.35:bits.add(4)
                if y>.35:bits.add(5)
        except pygame.error:continue
    return bits

def menu_next(index,delta,total):
    return (index+delta)%total if total else 0

def run_session(screen, core_path, rom_path, state_dir, max_frames=None, test_manual=False, display_mode='FIT', verified_cheats=None):
    """Run one game with selectable settings, explicit state slots and verified cheats."""
    joysticks=[]
    for i in range(pygame.joystick.get_count()):
        try:j=pygame.joystick.Joystick(i);j.init();joysticks.append(j)
        except pygame.error:pass
    preferences=read_preferences();scaling=preferences['scaling'];persisted_display=display_mode;persisted_scaling=scaling
    count=0;notice='';until=0;clock=pygame.time.Clock();sound=None;menu=False;selected=0;cheat_menu=False;cheat_selected=0;active=set();overlay_tested=False;overlay_changed=False;cheat_probe_started=False;cheat_toggles=0;slot=0
    entries=verified_cheats or []
    with LibretroHost(core_path,rom_path) as core:
        for entry in entries:
            if entry.get('rom_sha256')!=core.game_hash or entry.get('verified') is not True:raise ValueError('unverified or wrong-game cheat')
        try:
            pygame.mixer.quit();pygame.mixer.init(frequency=int(core.sample_rate) if 8000<=core.sample_rate<=192000 else 44100,size=-16,channels=2,buffer=512);sound=pygame.mixer.Channel(0)
        except pygame.error:notice='Audio unavailable on this device';until=time.monotonic()+4
        def state_path(number):return Path(state_dir)/(core.game_hash+('.state' if number==0 else '.slot'+str(number+1)+'.state'))
        def save_or_load(saving):
            nonlocal notice,until
            try:
                if saving:core.save_state(state_path(slot));notice='Saved slot '+str(slot+1)
                else:core.load_state(state_path(slot));notice='Loaded slot '+str(slot+1)
            except (OSError,RuntimeError,ValueError) as err:notice='Save/load failed: '+str(err)[:70]
            until=time.monotonic()+3
        def activate(row):
            nonlocal display_mode,scaling,slot,menu,cheat_menu,notice,until,cheat_selected
            if row==0:display_mode='STRETCH' if display_mode=='FIT' else 'FIT'
            elif row==1:scaling='SMOOTH' if scaling=='SHARP' else 'SHARP'
            elif row==2:slot=(slot+1)%4
            elif row==3:save_or_load(True)
            elif row==4:save_or_load(False)
            elif row==5:cheat_menu=True;cheat_selected=0
            elif row==6:menu=False
            elif row==7:return 'menu'
            elif row==8:return 'quit'
            return None
        def toggle_cheat(index):
            nonlocal notice,until,cheat_toggles
            if index>=len(entries):return
            candidate=set(active)
            if index in candidate:candidate.remove(index)
            else:candidate.add(index)
            try:
                core.set_verified_cheats([entries[i] for i in sorted(candidate)])
                active.clear();active.update(candidate);cheat_toggles+=1;notice='Cheat '+('enabled' if index in active else 'disabled')
            except (RuntimeError,ValueError) as err:notice='Cheat error: '+str(err)[:60]
            until=time.monotonic()+3
        while True:
            action=None
            for e in pygame.event.get():
                if e.type==pygame.QUIT:return 'quit'
                if e.type==pygame.JOYDEVICEADDED:
                    try:j=pygame.joystick.Joystick(e.device_index);j.init();joysticks.append(j)
                    except pygame.error:pass
                if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    gear_size=max(42,int(screen.get_height()*.065));gear_hit=pygame.Rect(screen.get_width()-gear_size-10,10,gear_size,gear_size)
                    if gear_hit.collidepoint(e.pos):menu=not menu;cheat_menu=False
                    elif menu:
                        sw,sh=screen.get_size();x,y=e.pos[0]*1280/sw,e.pos[1]*720/sh
                        if 340<=x<=940:
                            row=int((y-205)//36)
                            if cheat_menu and 0<=row<min(len(entries),7):cheat_selected=row;toggle_cheat(row)
                            elif not cheat_menu and 0<=row<9:selected=row;action=activate(selected)
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_g:menu=not menu;cheat_menu=False;continue
                    if e.key==pygame.K_ESCAPE:
                        if cheat_menu:cheat_menu=False;continue
                        if menu:menu=False;continue
                        return 'menu'
                    if menu:
                        if e.key in (pygame.K_DOWN,pygame.K_UP):
                            delta=1 if e.key==pygame.K_DOWN else -1
                            if cheat_menu:cheat_selected=menu_next(cheat_selected,delta,min(len(entries),7))
                            else:selected=menu_next(selected,delta,9)
                            continue
                        if e.key in (pygame.K_RETURN,pygame.K_SPACE):
                            if cheat_menu:toggle_cheat(cheat_selected)
                            else:action=activate(selected)
                            continue
                        if e.key==pygame.K_d:display_mode='STRETCH' if display_mode=='FIT' else 'FIT';overlay_changed=True;continue
                        if e.key==pygame.K_s:scaling='SMOOTH' if scaling=='SHARP' else 'SHARP';continue
                        if e.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):slot=e.key-pygame.K_1;notice='Manual slot '+str(slot+1);until=time.monotonic()+3;continue
                    if e.key==pygame.K_F5:save_or_load(True)
                    if e.key==pygame.K_F8:save_or_load(False)
                if menu and e.type==pygame.JOYHATMOTION and e.value[1]:
                    delta=-1 if e.value[1]>0 else 1
                    if cheat_menu:cheat_selected=menu_next(cheat_selected,delta,min(len(entries),7))
                    else:selected=menu_next(selected,delta,9)
                if menu and e.type==pygame.JOYBUTTONDOWN and e.button==0:
                    if cheat_menu:toggle_cheat(cheat_selected)
                    else:action=activate(selected)
                if action:return action
            if not test_manual and (display_mode!=persisted_display or scaling!=persisted_scaling):
                preferences.update({'display_mode':display_mode,'scaling':scaling})
                try:write_preferences(preferences);persisted_display=display_mode;persisted_scaling=scaling
                except OSError:notice='Could not save settings on this device';until=time.monotonic()+3;persisted_display=display_mode;persisted_scaling=scaling
            core.buttons=input_bits(joysticks) if not menu else set()
            if not menu:core.run_frame();count+=1
            if test_manual and count==3 and not overlay_tested:
                overlay_tested=True
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(screen.get_width()-20,20)))
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_d))
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_g))
            if test_manual and entries and count==5 and not cheat_probe_started:
                cheat_probe_started=True
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_g))
                for _ in range(5):pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_DOWN))
                for _ in range(3):pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN))
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE))
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_g))
            if test_manual and not menu and count==10:core.save_state(state_path(slot))
            if test_manual and not menu and count==20:core.load_state(state_path(slot))
            frame=frame_surface(core)
            if frame:
                target=screen.get_rect() if display_mode=='STRETCH' else fit_frame((4,3),screen.get_size())
                screen.fill((0,0,0));screen.blit((pygame.transform.smoothscale if scaling=='SMOOTH' else pygame.transform.scale)(frame,target.size),target.topleft)
            size=max(42,int(screen.get_height()*.065));gear=pygame.Rect(screen.get_width()-size-10,10,size,size)
            pygame.draw.rect(screen,(22,44,70),gear,border_radius=8);cx,cy=gear.center;radius=max(8,size//4)
            for k in range(8):
                a=k*math.pi/4;pygame.draw.line(screen,(230,245,255),(round(cx+math.cos(a)*radius*.7),round(cy+math.sin(a)*radius*.7)),(round(cx+math.cos(a)*radius*1.3),round(cy+math.sin(a)*radius*1.3)),max(2,size//12))
            pygame.draw.circle(screen,(230,245,255),(cx,cy),radius,max(2,size//12))
            if menu:
                sw,sh=screen.get_size();scale=min(sw/1280,sh/720);shade=pygame.Surface((sw,sh),pygame.SRCALPHA);shade.fill((0,0,0,190));screen.blit(shade,(0,0))
                def rect(x,y,w,h):return pygame.Rect(round(x*sw/1280),round(y*sh/720),round(w*sw/1280),round(h*sh/720))
                pygame.draw.rect(screen,(20,37,60),rect(310,125,660,495),border_radius=12)
                font=pygame.font.SysFont('dejavusans',max(16,int(21*scale)));title='CHEATS' if cheat_menu else 'GAME SETTINGS'
                screen.blit(font.render(title,True,(110,225,255)),rect(345,160,600,30).topleft)
                if cheat_menu:
                    lines=[('[ON] ' if i in active else '[OFF] ')+str(e.get('name','Verified cheat'))[:45] for i,e in enumerate(entries[:7])]
                    if not lines:lines=['No verified cheats for this exact game.']
                    choice=cheat_selected if entries else -1
                else:
                    lines=['Display: '+display_mode+' [D]','Filter: '+scaling+' [S]','Manual slot: '+str(slot+1)+' [1-4]','Save state [F5]','Load state [F8]','Cheats ('+str(len(entries))+')','Resume game','Back to game list','Exit application'];choice=selected
                for i,text in enumerate(lines):
                    r=rect(340,205+i*36,600,32)
                    if i==choice:
                        pygame.draw.rect(screen,(32,99,132),r,border_radius=6);pygame.draw.rect(screen,(85,230,255),r,width=max(1,int(2*scale)),border_radius=6)
                    screen.blit(font.render(text,True,(235,245,255)),(r.x+8,r.y+3))
                screen.blit(font.render('Arrows / Enter / Mouse   ESC: Back',True,(175,200,220)),rect(345,560,600,30).topleft)
            pcm=core.drain_audio()
            if sound and pcm and (not sound.get_busy() or sound.get_queue() is None):
                try:
                    chunk=pygame.mixer.Sound(buffer=pcm)
                    if sound.get_busy():sound.queue(chunk)
                    else:sound.play(chunk)
                except pygame.error:pass
            if time.monotonic()<until:
                f=pygame.font.SysFont('dejavusans',22);screen.blit(f.render(notice,True,(255,230,160)),(15,15))
            pygame.display.flip()
            if max_frames is not None and count>=max_frames:
                if test_manual and (not state_path(slot).exists() or not overlay_changed or (entries and cheat_toggles<2)):raise AssertionError('manual save, settings or cheat interaction failed')
                return 'test-complete'
            clock.tick(core.fps if 20<=core.fps<=120 else 60)
