"""Experimental desktop collection menu and Linux game selection."""
import argparse, json, math, os, random
from pathlib import Path
import pygame
from library import load_catalog, filter_catalog
from preferences import read_preferences, write_preferences

ROOT=Path(__file__).resolve().parent
CATEGORIES=['ALL','FAVORITES']
THUMB_CACHE={}
BACKGROUND_CACHE={}

def scroll_selection(chosen, wheel_y, count):
    """Scroll one row at a time without leaving the filtered game list."""
    return max(0,min(max(0,count-1),chosen-int(wheel_y)*3))

def background(size):
    if size not in BACKGROUND_CACHE:
        try:BACKGROUND_CACHE[size]=pygame.transform.smoothscale(pygame.image.load(str(ROOT/'assets/menu-background.png')).convert(),size)
        except (pygame.error,FileNotFoundError):BACKGROUND_CACHE[size]=None
    return BACKGROUND_CACHE[size]


def thumbnail(source_id):
    if source_id not in THUMB_CACHE:
        path=ROOT/'thumbnails'/(source_id+'.png')
        try: THUMB_CACHE[source_id]=pygame.image.load(str(path)).convert()
        except (FileNotFoundError,pygame.error): THUMB_CACHE[source_id]=None
    return THUMB_CACHE[source_id]


def textfit(font,text,maxwidth):
    while text and font.size(text)[0]>maxwidth:
        text=text[:-1]
    return text

def render(screen, games, category, query, chosen, favorites, status, about=False, settings=False, display_mode='FIT'):
    w,h=screen.get_size();sx=w/1280;sy=h/720
    def pos(x,y):return (round(x*sx),round(y*sy))
    def rect(x,y,ww,hh):return pygame.Rect(round(x*sx),round(y*sy),max(1,round(ww*sx)),max(1,round(hh*sy)))
    backdrop=background((w,h))
    if backdrop:screen.blit(backdrop,(0,0))
    else:screen.fill((10,17,43))
    shade=pygame.Surface((w,h),pygame.SRCALPHA);shade.fill((4,8,25,90));screen.blit(shade,(0,0))
    font=lambda n:pygame.font.SysFont('dejavusans',max(11,int(n*min(sx,sy))))
    big=font(30);small=font(13);body=font(17);tiny=font(11)
    def label(txt,x,y,color=(200,220,240),f=body):screen.blit(f.render(txt,True,color),pos(x,y))
    icon=pygame.image.load(str(ROOT/'assets/app-icon.png')).convert_alpha();icon=pygame.transform.smoothscale(icon,(int(52*sx),int(52*sy)));screen.blit(icon,pos(48,28))
    label('AKG RETRO GAMES',116,34,(225,235,255),big);label('ONE COLLECTION. ENDLESS ADVENTURES.',118,73,(122,152,193),small)
    label('BROWSE',50,178,(117,140,178),small)
    for i,cat in enumerate(CATEGORIES):
        y=218+i*47
        if cat==category:pygame.draw.rect(screen,(28,54,84),rect(38,y-8,178,37),border_radius=6)
        label({'ALL':'ALL GAMES','FAVORITES':'FAVORITES'}[cat],52,y,(101,225,238) if cat==category else (150,169,199),body)
    label('SEARCH: '+(query or 'type / to search'),250,152,(151,177,208),small)
    label(str(len(games))+' GAMES',1018,152,(151,177,208),small)
    selected=games[chosen] if games else None;page=chosen//6 if games else 0
    for index,g in enumerate(games[page*6:page*6+6],start=page*6):
        n=index-page*6;x=250+(n%3)*240;y=200+(n//3)*194;box=rect(x,y,218,172)
        pygame.draw.rect(screen,(16,29,52),box,border_radius=12)
        if index==chosen:
            # Bounded glow surface avoids allocating a full 4K overlay per card.
            spread=max(3,int(14*min(sx,sy)))
            glow=pygame.Surface((box.width+spread*2,box.height+spread*2),pygame.SRCALPHA)
            basebox=pygame.Rect(spread,spread,box.width,box.height)
            for pad,alpha in [(12,18),(8,28),(4,50)]:
                margin=max(1,int(pad*min(sx,sy)))
                pygame.draw.rect(glow,(25,195,255,alpha),basebox.inflate(margin*2,margin*2),width=max(2,int(3*min(sx,sy))),border_radius=max(5,int(15*min(sx,sy))))
            screen.blit(glow,(box.x-spread,box.y-spread))
        pygame.draw.rect(screen,(86,230,255) if index==chosen else (80,108,145),box,width=max(1,int(3*min(sx,sy))),border_radius=max(5,int(12*min(sx,sy))))
        banner=rect(x+8,y+8,202,95);colors=[(35,80,101),(42,60,110),(65,51,106),(35,76,80),(56,57,99),(48,63,92)];pygame.draw.rect(screen,colors[index%len(colors)],banner,border_radius=8)
        img=thumbnail(g['id'])
        if img:
            # Keep the complete game screenshot rather than cropping artwork.
            fitted=img.get_rect().fit(banner)
            screen.blit(pygame.transform.smoothscale(img,fitted.size),fitted)
        else:
            label('PREVIEW UNAVAILABLE',x+14,y+45,(190,205,224),tiny)
        label('★' if g['id'] in favorites else '',x+184,y+20,(238,195,94),small)
        title=textfit(body,g['title'],int(190*sx));label(title,x+14,y+114,(225,234,250),body)
        label('SELECTED' if index==chosen else 'GAME',x+14,y+145,(117,158,194),tiny)
    if not games:label('No matching games',310,300,(190,205,224),body)
    label('SELECTED GAME',1005,210,(131,152,186),small)
    if selected:
        lines=selected['title'];
        for i in range(0,min(len(lines),75),25):label(textfit(body,lines[i:i+25],int(220*sx)),1005,243+i//25*24,(220,235,250),body)
        label('Press Enter to play',1005,326,(105,220,230),body)
    pygame.draw.rect(screen,(30,62,91),rect(997,448,210,44),border_radius=8)
    label('SETTINGS  [G]',1010,459,(210,230,245),body)
    pygame.draw.line(screen,(50,65,95),pos(42,637),pos(1238,637),1)
    label('ARROWS / MOUSE    / SEARCH    F FAVORITE    TAB FAVORITES    G SETTINGS    I ABOUT    ESC EXIT',50,657,(151,170,199),small)
    if status:label(status,250,603,(247,190,104),small)
    if settings:
        shade=pygame.Surface((w,h),pygame.SRCALPHA);shade.fill((2,6,18,220));screen.blit(shade,(0,0))
        pygame.draw.rect(screen,(18,29,52),rect(250,150,780,420),border_radius=14)
        label('SETTINGS',285,180,(120,225,238),big)
        label('Display mode: '+display_mode,285,260,(225,235,245),body)
        label('Press D to switch: FIT 4:3 / FULL STRETCH',285,305,(200,220,235),body)
        label('G or ESC closes settings. Changes apply to the next game.',285,365,(200,220,235),body)
    if about:
        shade=pygame.Surface((w,h),pygame.SRCALPHA);shade.fill((2,6,18,218));screen.blit(shade,(0,0))
        panel=rect(170,95,940,520);pygame.draw.rect(screen,(18,29,52),panel,border_radius=14);pygame.draw.rect(screen,(83,167,195),panel,width=2,border_radius=14)
        label('DEVELOPER AND DISCLAIMER',205,122,(120,225,238),big)
        import textwrap
        lines=[]
        for paragraph in (ROOT/'NOTICE.md').read_text(encoding='utf-8').splitlines():
            lines.extend(textwrap.wrap(paragraph,width=84) or [''])
        y=180
        for line in lines:
            if y>555:break
            label(line,205,y,(211,222,240),small);y+=23
        label('Press I or ESC to return',205,575,(113,206,224),small)

def main():
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');p.add_argument('--screenshot');p.add_argument('--rom-dir',default=str(ROOT/'roms'));p.add_argument('--cores-dir',default=str(ROOT/'cores'));p.add_argument('--ci-game-id',help=argparse.SUPPRESS);args=p.parse_args()
    pygame.init();pygame.joystick.init();screen=pygame.display.set_mode((1280,720),0 if args.smoke else pygame.FULLSCREEN);pygame.display.set_caption('AKG Retro Games — preview')
    pygame.display.set_icon(pygame.image.load(str(ROOT/'assets/app-icon.png')))
    preferences=read_preferences();saved_preferences=preferences.copy()
    all_games=load_catalog(ROOT/'drive-index.json');favorites=set(preferences['favorites']);cat=0;query='';chosen=0;search=False;about=False;settings=False;display_mode=preferences['display_mode']; joysticks=[]; status='Experimental build — game support is being tested';running=True;clock=pygame.time.Clock()
    if args.ci_game_id:
        if not args.smoke:raise ValueError('CI game test requires smoke mode')
        from launch_game import launch_game
        games=[game for game in all_games if game['id']==args.ci_game_id]
        if len(games)!=1:raise ValueError('CI game ID not found')
        result=launch_game(games[0],screen,args.cores_dir,args.rom_dir,Path.home()/'.retro-collection'/'manual-saves',max_frames=24,test_manual=True)
        pygame.quit()
        if result!='test-complete':raise RuntimeError('CI game session failed')
        return
    for n in range(pygame.joystick.get_count()):
        try:
            j=pygame.joystick.Joystick(n);j.init();joysticks.append(j)
        except pygame.error:pass
    while running:
        games=filter_catalog(all_games,CATEGORIES[cat],query,favorites);chosen=min(chosen,max(0,len(games)-1))
        for event in pygame.event.get():
            if event.type==pygame.QUIT:running=False
            if event.type==pygame.JOYDEVICEADDED:
                try:
                    j=pygame.joystick.Joystick(event.device_index);j.init();joysticks.append(j)
                except pygame.error:pass
            if not about and not settings and not search and event.type==pygame.MOUSEWHEEL:
                chosen=scroll_selection(chosen,event.y,len(games))
            if not about and not settings and not search and event.type==pygame.MOUSEBUTTONDOWN and event.button in (4,5):
                chosen=scroll_selection(chosen,1 if event.button==4 else -1,len(games))
            if not about and not settings and event.type==pygame.JOYHATMOTION:
                dx,dy=event.value
                chosen=max(0,min(max(0,len(games)-1),chosen+dx-3*dy))
            if not about and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                sw,sh=screen.get_size();mx=event.pos[0]*1280/sw;my=event.pos[1]*720/sh
                if settings:
                    if 250<=mx<=1030 and 250<=my<=340:display_mode='STRETCH' if display_mode=='FIT' else 'FIT'
                    continue
                if 997<=mx<=1207 and 448<=my<=492:
                    settings=True;continue
                if 38<=mx<=216:
                    for i in range(len(CATEGORIES)):
                        if 210+i*47<=my<=247+i*47:cat=i;chosen=0
                page=chosen//6
                for n in range(6):
                    x=250+(n%3)*240;y=200+(n//3)*194
                    idx=page*6+n
                    if x<=mx<=x+218 and y<=my<=y+172 and idx<len(games):chosen=idx
            if event.type==pygame.KEYDOWN:
                if settings:
                    if event.key in (pygame.K_ESCAPE,pygame.K_g):settings=False
                    elif event.key==pygame.K_d:display_mode='STRETCH' if display_mode=='FIT' else 'FIT'
                elif about:
                    if event.key in (pygame.K_ESCAPE,pygame.K_i):about=False
                elif search:
                    if event.key==pygame.K_ESCAPE:search=False;query='';chosen=0
                    elif event.key==pygame.K_RETURN:search=False
                    elif event.key==pygame.K_BACKSPACE:query=query[:-1];chosen=0
                    elif event.unicode and event.unicode.isprintable() and len(query)<60:query+=event.unicode;chosen=0
                elif event.key==pygame.K_ESCAPE:running=False
                elif event.key==pygame.K_i:about=True
                elif event.key==pygame.K_g:settings=True
                elif event.key==pygame.K_SLASH:search=True;query='';chosen=0
                elif event.key==pygame.K_TAB:cat=(cat+1)%len(CATEGORIES);chosen=0
                elif event.key==pygame.K_RIGHT:chosen=min(chosen+1,max(0,len(games)-1))
                elif event.key==pygame.K_LEFT:chosen=max(0,chosen-1)
                elif event.key==pygame.K_DOWN:chosen=min(chosen+3,max(0,len(games)-1))
                elif event.key==pygame.K_UP:chosen=max(0,chosen-3)
                elif event.key==pygame.K_f and games:
                    ident=games[chosen]['id'];favorites.symmetric_difference_update({ident})
                elif event.key==pygame.K_RETURN and games:
                    try:
                        from launch_game import launch_game
                        result=launch_game(games[chosen],screen,args.cores_dir,args.rom_dir,Path.home()/'.retro-collection'/'manual-saves',display_mode=display_mode)
                        if result=='quit':running=False
                        preferences=read_preferences();display_mode=preferences['display_mode'];saved_preferences=preferences.copy()
                        status='Returned from game'
                    except (OSError,RuntimeError,ValueError) as err:status=str(err)[:110]
        preferences.update({'display_mode':display_mode,'favorites':sorted(favorites)})
        if preferences!=saved_preferences and not args.smoke:
            try:write_preferences(preferences);saved_preferences=preferences.copy()
            except OSError:status='Could not save settings on this device';saved_preferences=preferences.copy()
        render(screen,games,CATEGORIES[cat],query,chosen,favorites,status,about,settings,display_mode);pygame.display.flip()
        if args.screenshot:pygame.image.save(screen,args.screenshot)
        if args.smoke:running=False
        clock.tick(60)
    pygame.quit()
if __name__=='__main__':main()
