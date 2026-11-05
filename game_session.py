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

def run_session(screen, core_path, rom_path, state_dir, max_frames=None, test_manual=False, display_mode='FIT'):
    """Run one game; ESC returns; F5/F8 explicit save/load. No automatic saves."""
    joysticks=[]
    for i in range(pygame.joystick.get_count()):
        try:j=pygame.joystick.Joystick(i);j.init();joysticks.append(j)
        except pygame.error:pass
    preferences=read_preferences();scaling=preferences['scaling'];persisted_display=display_mode;persisted_scaling=scaling
    count=0;notice='';until=0;clock=pygame.time.Clock();sound=None;menu=False;overlay_tested=False;overlay_changed=False;slot=0
    with LibretroHost(core_path,rom_path) as core:
        try:
            pygame.mixer.quit();pygame.mixer.init(frequency=int(core.sample_rate) if 8000<=core.sample_rate<=192000 else 44100,size=-16,channels=2,buffer=512);sound=pygame.mixer.Channel(0)
        except pygame.error:notice='Audio unavailable on this device';until=time.monotonic()+4
        state=Path(state_dir)/(core.game_hash+'.state')
        while True:
            for e in pygame.event.get():
                if e.type==pygame.QUIT:return 'quit'
                if e.type==pygame.JOYDEVICEADDED:
                    try:j=pygame.joystick.Joystick(e.device_index);j.init();joysticks.append(j)
                    except pygame.error:pass
                if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    gear_size=max(42,int(screen.get_height()*.065))
                    gear_hit=pygame.Rect(screen.get_width()-gear_size-10,10,gear_size,gear_size)
                    if gear_hit.collidepoint(e.pos):menu=not menu
                    elif menu:
                        sw,sh=screen.get_size();x,y=e.pos[0]*1280/sw,e.pos[1]*720/sh
                        if 360<=x<=920 and 220<=y<=260:display_mode='STRETCH' if display_mode=='FIT' else 'FIT'
                        elif 360<=x<=920 and 265<=y<=310:scaling='SMOOTH' if scaling=='SHARP' else 'SHARP'
                        elif 360<=x<=920 and 350<=y<=395:
                            try:core.save_state(state);notice='Saved manually'
                            except (OSError,RuntimeError,ValueError) as err:notice='Save failed: '+str(err)[:70]
                            until=time.monotonic()+3
                        elif 360<=x<=920 and 400<=y<=445:
                            try:core.load_state(state);notice='Loaded manual save'
                            except (OSError,RuntimeError,ValueError) as err:notice='Load failed: '+str(err)[:70]
                            until=time.monotonic()+3
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_g:menu=not menu;continue
                    if menu and e.key==pygame.K_d:display_mode='STRETCH' if display_mode=='FIT' else 'FIT';overlay_changed=True;continue
                    if menu and e.key==pygame.K_s:scaling='SMOOTH' if scaling=='SHARP' else 'SHARP';continue
                    if menu and e.key in (pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4):
                        slot=e.key-pygame.K_1
                        state=Path(state_dir)/(core.game_hash+('.state' if slot==0 else '.slot'+str(slot+1)+'.state'))
                        notice='Manual slot '+str(slot+1);until=time.monotonic()+3;continue
                    if e.key==pygame.K_ESCAPE:
                        if menu:menu=False;continue
                        return 'menu'
                    if e.key in (pygame.K_F5,pygame.K_F8):
                        try:
                            if e.key==pygame.K_F5:core.save_state(state);notice='Saved manually'
                            else:core.load_state(state);notice='Loaded manual save'
                        except (OSError,RuntimeError,ValueError) as err:notice='Save/load failed: '+str(err)[:70]
                        until=time.monotonic()+3
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
            if test_manual and not menu and count==10:core.save_state(state)
            if test_manual and not menu and count==20:core.load_state(state)
            frame=frame_surface(core)
            if frame:
                # Fit the full frame without cropping or stretching; add letterboxing.
                # This is upscaling, not native 4K.
                # 4:3 console display framing or explicit full-screen stretch; neither crops.
                target=screen.get_rect() if display_mode=='STRETCH' else fit_frame((4,3),screen.get_size())
                screen.fill((0,0,0))
                screen.blit((pygame.transform.smoothscale if scaling=='SMOOTH' else pygame.transform.scale)(frame,target.size),target.topleft)
            # In-game gear is clickable; G opens the same menu.
            size=max(42,int(screen.get_height()*.065));gear=pygame.Rect(screen.get_width()-size-10,10,size,size)
            pygame.draw.rect(screen,(22,44,70),gear,border_radius=8)
            cx,cy=gear.center;radius=max(8,size//4)
            for k in range(8):
                a=k*math.pi/4
                pygame.draw.line(screen,(230,245,255),(round(cx+math.cos(a)*radius*.7),round(cy+math.sin(a)*radius*.7)),(round(cx+math.cos(a)*radius*1.3),round(cy+math.sin(a)*radius*1.3)),max(2,size//12))
            pygame.draw.circle(screen,(230,245,255),(cx,cy),radius,max(2,size//12))
            if menu:
                sw,sh=screen.get_size();scale=min(sw/1280,sh/720)
                shade=pygame.Surface((sw,sh),pygame.SRCALPHA);shade.fill((0,0,0,190));screen.blit(shade,(0,0))
                panel=pygame.Rect(round(330*sw/1280),round(130*sh/720),round(620*sw/1280),round(420*sh/720))
                pygame.draw.rect(screen,(20,37,60),panel,border_radius=12)
                font=pygame.font.SysFont('dejavusans',max(17,int(22*scale)))
                lines=[(165,'GAME SETTINGS'),(230,'DISPLAY: '+display_mode+'  [D]'),(275,'FILTER: '+scaling+'  [S]'),(320,'MANUAL SLOT '+str(slot+1)+'  [1-4]'),(365,'SAVE STATE  [F5]'),(410,'LOAD STATE  [F8]'),(455,'CHEATS: no verified codes for this game'),(505,'G: RESUME   ESC: CLOSE')]
                for yy,txt in lines:screen.blit(font.render(txt,True,(225,235,245)),(round(360*sw/1280),round(yy*sh/720)))
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
                if test_manual and (not state.exists() or not overlay_changed):raise AssertionError('manual save or settings interaction failed')
                return 'test-complete'
            fps=core.fps if 20<=core.fps<=120 else 60
            clock.tick(fps)
