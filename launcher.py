"""Experimental desktop collection menu; game execution is not implemented."""
import argparse, json, math, os, random
from pathlib import Path
import pygame
from library import load_catalog, filter_catalog

ROOT=Path(__file__).resolve().parent
CATEGORIES=['ALL','NES','SNES','FAVORITES']

def textfit(font,text,maxwidth):
    while text and font.size(text)[0]>maxwidth:
        text=text[:-1]
    return text

def render(screen, games, category, query, chosen, favorites, status, about=False):
    w,h=screen.get_size();sx=w/1280;sy=h/720
    def pos(x,y):return (round(x*sx),round(y*sy))
    def rect(x,y,ww,hh):return pygame.Rect(round(x*sx),round(y*sy),max(1,round(ww*sx)),max(1,round(hh*sy)))
    base=pygame.Surface((1,h))
    for y in range(h):
        t=y/max(1,h-1);base.set_at((0,y),(int(10+5*t),int(17+3*t),int(43+13*t)))
    screen.blit(pygame.transform.scale(base,(w,h)),(0,0))
    halo=pygame.Surface((w,h),pygame.SRCALPHA)
    pygame.draw.ellipse(halo,(36,115,185,25),rect(270,-300,780,700));pygame.draw.ellipse(halo,(119,60,190,19),rect(700,-200,600,500));screen.blit(halo,(0,0))
    rng=random.Random(711)
    for _ in range(110):
        x,y=rng.randrange(w),rng.randrange(h);screen.set_at((x,y),(60,85,121))
    font=lambda n:pygame.font.SysFont('dejavusans',max(11,int(n*min(sx,sy))))
    big=font(30);small=font(13);body=font(17);tiny=font(11)
    def label(txt,x,y,color=(200,220,240),f=body):screen.blit(f.render(txt,True,color),pos(x,y))
    icon=pygame.image.load(str(ROOT/'assets/app-icon.png')).convert_alpha();icon=pygame.transform.smoothscale(icon,(int(52*sx),int(52*sy)));screen.blit(icon,pos(48,28))
    label('RETRO COLLECTION',116,34,(225,235,255),big);label('ONE COLLECTION. ENDLESS ADVENTURES.',118,73,(122,152,193),small)
    label('BROWSE',50,178,(117,140,178),small)
    for i,cat in enumerate(CATEGORIES):
        y=218+i*47
        if cat==category:pygame.draw.rect(screen,(28,54,84),rect(38,y-8,178,37),border_radius=6)
        label({'ALL':'ALL GAMES','NES':'NES','SNES':'SNES','FAVORITES':'FAVORITES'}[cat],52,y,(101,225,238) if cat==category else (150,169,199),body)
    label('SEARCH: '+(query or 'type / to search'),250,152,(151,177,208),small)
    label(str(len(games))+' GAMES',1018,152,(151,177,208),small)
    selected=games[chosen] if games else None;page=chosen//6 if games else 0
    for index,g in enumerate(games[page*6:page*6+6],start=page*6):
        n=index-page*6;x=250+(n%3)*240;y=200+(n//3)*194;box=rect(x,y,218,172)
        pygame.draw.rect(screen,(16,29,52),box,border_radius=12)
        pygame.draw.rect(screen,(67,220,234) if index==chosen else (48,66,99),box,width=max(1,int(2*min(sx,sy))),border_radius=12)
        banner=rect(x+8,y+8,202,95);colors=[(35,80,101),(42,60,110),(65,51,106),(35,76,80),(56,57,99),(48,63,92)];pygame.draw.rect(screen,colors[index%len(colors)],banner,border_radius=8)
        label(g['system'],x+14,y+20,(156,230,238),small);label('★' if g['id'] in favorites else '',x+184,y+20,(238,195,94),small)
        title=textfit(body,g['title'],int(190*sx));label(title,x+14,y+114,(225,234,250),body)
        label('SELECTED' if index==chosen else 'GAME',x+14,y+145,(117,158,194),tiny)
    if not games:label('No matching games',310,300,(190,205,224),body)
    label('SELECTED GAME',1005,210,(131,152,186),small)
    if selected:
        lines=selected['title'];
        for i in range(0,min(len(lines),75),25):label(textfit(body,lines[i:i+25],int(220*sx)),1005,243+i//25*24,(220,235,250),body)
        label(selected['system'],1005,326,(105,220,230),body)
    label('SETTINGS',1005,460,(143,165,200),body)
    pygame.draw.line(screen,(50,65,95),pos(42,637),pos(1238,637),1)
    label('ARROWS / MOUSE    / SEARCH    F FAVORITE    TAB FILTER    I ABOUT    ESC EXIT',50,657,(151,170,199),small)
    if status:label(status,250,603,(247,190,104),small)
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
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');p.add_argument('--screenshot');args=p.parse_args()
    pygame.init();pygame.joystick.init();screen=pygame.display.set_mode((1280,720),0 if args.smoke else pygame.FULLSCREEN);pygame.display.set_caption('Retro Collection — preview')
    pygame.display.set_icon(pygame.image.load(str(ROOT/'assets/app-icon.png')))
    all_games=load_catalog(ROOT/'drive-index.json');favorites=set();cat=0;query='';chosen=0;search=False;about=False; joysticks=[]; status='Preview only: game execution is not implemented';running=True;clock=pygame.time.Clock()
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
            if not about and event.type==pygame.JOYHATMOTION:
                dx,dy=event.value
                chosen=max(0,min(max(0,len(games)-1),chosen+dx-3*dy))
            if not about and event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                sw,sh=screen.get_size();mx=event.pos[0]*1280/sw;my=event.pos[1]*720/sh
                if 38<=mx<=216:
                    for i in range(4):
                        if 210+i*47<=my<=247+i*47:cat=i;chosen=0
                page=chosen//6
                for n in range(6):
                    x=250+(n%3)*240;y=200+(n//3)*194
                    idx=page*6+n
                    if x<=mx<=x+218 and y<=my<=y+172 and idx<len(games):chosen=idx
            if event.type==pygame.KEYDOWN:
                if about:
                    if event.key in (pygame.K_ESCAPE,pygame.K_i):about=False
                elif search:
                    if event.key==pygame.K_ESCAPE:search=False;query='';chosen=0
                    elif event.key==pygame.K_RETURN:search=False
                    elif event.key==pygame.K_BACKSPACE:query=query[:-1];chosen=0
                    elif event.unicode and event.unicode.isprintable() and len(query)<60:query+=event.unicode;chosen=0
                elif event.key==pygame.K_ESCAPE:running=False
                elif event.key==pygame.K_i:about=True
                elif event.key==pygame.K_SLASH:search=True;query='';chosen=0
                elif event.key==pygame.K_TAB:cat=(cat+1)%len(CATEGORIES);chosen=0
                elif event.key==pygame.K_RIGHT:chosen=min(chosen+1,max(0,len(games)-1))
                elif event.key==pygame.K_LEFT:chosen=max(0,chosen-1)
                elif event.key==pygame.K_DOWN:chosen=min(chosen+3,max(0,len(games)-1))
                elif event.key==pygame.K_UP:chosen=max(0,chosen-3)
                elif event.key==pygame.K_f and games:
                    ident=games[chosen]['id'];favorites.symmetric_difference_update({ident})
                elif event.key==pygame.K_RETURN:status='Preview only: game execution is not implemented'
        render(screen,games,CATEGORIES[cat],query,chosen,favorites,status,about);pygame.display.flip()
        if args.screenshot:pygame.image.save(screen,args.screenshot)
        if args.smoke:running=False
        clock.tick(60)
    pygame.quit()
if __name__=='__main__':main()
