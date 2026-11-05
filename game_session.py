"""Experimental software-video/PCM game loop for the desktop prototype."""
import os,time
from pathlib import Path
import pygame
from libretro_host import LibretroHost

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

def run_session(screen, core_path, rom_path, state_dir, max_frames=None, test_manual=False):
    """Run one game; ESC returns; F5/F8 explicit save/load. No automatic saves."""
    joysticks=[]
    for i in range(pygame.joystick.get_count()):
        try:j=pygame.joystick.Joystick(i);j.init();joysticks.append(j)
        except pygame.error:pass
    count=0;notice='';until=0;clock=pygame.time.Clock();sound=None
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
                if e.type==pygame.KEYDOWN:
                    if e.key==pygame.K_ESCAPE:return 'menu'
                    if e.key in (pygame.K_F5,pygame.K_F8):
                        try:
                            if e.key==pygame.K_F5:core.save_state(state);notice='Saved manually'
                            else:core.load_state(state);notice='Loaded manual save'
                        except (OSError,RuntimeError,ValueError) as err:notice='Save/load failed: '+str(err)[:70]
                        until=time.monotonic()+3
            core.buttons=input_bits(joysticks);core.run_frame();count+=1
            if test_manual and count==10:core.save_state(state)
            if test_manual and count==20:core.load_state(state)
            frame=frame_surface(core)
            if frame:
                # Fit the full frame without cropping or stretching; add letterboxing.
                # This is upscaling, not native 4K.
                target=fit_frame(frame.get_size(),screen.get_size())
                screen.fill((0,0,0))
                screen.blit(pygame.transform.scale(frame,target.size),target.topleft)
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
                if test_manual and not state.exists():raise AssertionError('manual save not produced')
                return 'test-complete'
            fps=core.fps if 20<=core.fps<=120 else 60
            clock.tick(fps)
