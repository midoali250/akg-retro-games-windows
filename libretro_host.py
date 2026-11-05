"""Small libretro software-video host. Experimental; not a complete frontend."""
import ctypes as c
import hashlib
import os
from pathlib import Path
import struct
import tempfile
from collections import deque

ENV = c.CFUNCTYPE(c.c_bool, c.c_uint, c.c_void_p)
VIDEO = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_uint, c.c_size_t)
SAMPLE = c.CFUNCTYPE(None, c.c_int16, c.c_int16)
BATCH = c.CFUNCTYPE(c.c_size_t, c.POINTER(c.c_int16), c.c_size_t)
POLL = c.CFUNCTYPE(None)
INPUT = c.CFUNCTYPE(c.c_int16, c.c_uint, c.c_uint, c.c_uint, c.c_uint)
class SystemInfo(c.Structure):
    _fields_=[('library_name',c.c_char_p),('library_version',c.c_char_p),('valid_extensions',c.c_char_p),('need_fullpath',c.c_bool),('block_extract',c.c_bool)]
class GameGeometry(c.Structure):
    _fields_=[("base_width",c.c_uint),("base_height",c.c_uint),("max_width",c.c_uint),("max_height",c.c_uint),("aspect_ratio",c.c_float)]
class SystemTiming(c.Structure):
    _fields_=[("fps",c.c_double),("sample_rate",c.c_double)]
class AVInfo(c.Structure):
    _fields_=[("geometry",GameGeometry),("timing",SystemTiming)]
class GameInfo(c.Structure):
    _fields_=[('path',c.c_char_p),('data',c.c_void_p),('size',c.c_size_t),('meta',c.c_char_p)]
class LibretroHost:
    """One loaded core/game. Call close before creating another in the process."""
    def __init__(self, library, game, system_dir=None):
        library=Path(library).resolve()
        self._dll_dir=os.add_dll_directory(str(library.parent)) if os.name=='nt' else None
        self.lib=c.CDLL(str(library));self.game=Path(game).resolve()
        self.rom=self.game.read_bytes();self.game_hash=hashlib.sha256(self.rom).hexdigest()
        if not self.rom:raise ValueError('empty game')
        self.buffer=c.create_string_buffer(self.rom);self.path_bytes=os.fsencode(str(self.game))
        self.directory_bytes=os.fsencode(str(Path(system_dir or self.game.parent).resolve()))
        self.pixel_format=0;self.width=0;self.height=0;self.pitch=0;self.last_frame=None;self.frames=0;self.audio_samples=0;self.audio_queue=deque();self.audio_bytes=0;self.buttons=set();self.loaded=False;self.initialized=False
        self._callbacks=[ENV(self._environment),VIDEO(self._video),SAMPLE(self._sample),BATCH(self._batch),POLL(self._poll),INPUT(self._input)]
        L=self.lib
        for name,typ in [('retro_set_environment',ENV),('retro_set_video_refresh',VIDEO),('retro_set_audio_sample',SAMPLE),('retro_set_audio_sample_batch',BATCH),('retro_set_input_poll',POLL),('retro_set_input_state',INPUT)]:
            getattr(L,name).argtypes=[typ];getattr(L,name).restype=None
        L.retro_api_version.restype=c.c_uint
        if L.retro_api_version()!=1:raise RuntimeError('unsupported libretro API')
        L.retro_get_system_info.argtypes=[c.POINTER(SystemInfo)];L.retro_get_system_info.restype=None
        L.retro_get_system_av_info.argtypes=[c.POINTER(AVInfo)];L.retro_get_system_av_info.restype=None
        L.retro_init.argtypes=[];L.retro_init.restype=None;L.retro_deinit.argtypes=[];L.retro_deinit.restype=None
        L.retro_load_game.argtypes=[c.POINTER(GameInfo)];L.retro_load_game.restype=c.c_bool
        L.retro_unload_game.argtypes=[];L.retro_unload_game.restype=None;L.retro_run.argtypes=[];L.retro_run.restype=None
        L.retro_serialize_size.argtypes=[];L.retro_serialize_size.restype=c.c_size_t
        L.retro_serialize.argtypes=[c.c_void_p,c.c_size_t];L.retro_serialize.restype=c.c_bool
        L.retro_unserialize.argtypes=[c.c_void_p,c.c_size_t];L.retro_unserialize.restype=c.c_bool
        L.retro_cheat_reset.argtypes=[];L.retro_cheat_reset.restype=None
        L.retro_cheat_set.argtypes=[c.c_uint,c.c_bool,c.c_char_p];L.retro_cheat_set.restype=None
        for (name,_),cb in zip([('retro_set_environment',ENV),('retro_set_video_refresh',VIDEO),('retro_set_audio_sample',SAMPLE),('retro_set_audio_sample_batch',BATCH),('retro_set_input_poll',POLL),('retro_set_input_state',INPUT)],self._callbacks):getattr(L,name)(cb)
        try:
            L.retro_init();self.initialized=True
            info=SystemInfo();L.retro_get_system_info(c.byref(info));self.system_name=(info.library_name or b'').decode('utf8','replace')
            self.info=GameInfo(self.path_bytes,None if info.need_fullpath else c.cast(self.buffer,c.c_void_p),0 if info.need_fullpath else len(self.rom),None)
            if not L.retro_load_game(c.byref(self.info)):raise RuntimeError('core rejected game')
            self.loaded=True
            av=AVInfo();L.retro_get_system_av_info(c.byref(av));self.fps=av.timing.fps;self.sample_rate=av.timing.sample_rate
        except BaseException:
            self.close();raise
    def _environment(self,cmd,data):
        if cmd in (9,30,31) and data:
            c.cast(data,c.POINTER(c.c_char_p))[0]=self.directory_bytes;return True
        if cmd==3 and data:c.cast(data,c.POINTER(c.c_bool))[0]=True;return True
        if cmd==10 and data:
            v=c.cast(data,c.POINTER(c.c_uint))[0]
            if v not in (0,1,2):return False
            self.pixel_format=v;return True
        if cmd==17 and data:c.cast(data,c.POINTER(c.c_bool))[0]=False;return True
        if cmd==39 and data:c.cast(data,c.POINTER(c.c_uint))[0]=0;return True
        if cmd in (6,8,11,16,18,34,35):return True
        return False
    def _video(self,data,width,height,pitch):
        if data and data != c.c_void_p(-1).value and width and height and 0<pitch<=65536 and height<=4096:
            self.last_frame=c.string_at(data,pitch*height);self.width=width;self.height=height;self.pitch=pitch
        self.frames+=1
    def _enqueue_audio(self,data):
        if not data:return
        self.audio_queue.append(data);self.audio_bytes+=len(data)
        while self.audio_bytes>524288 and self.audio_queue:
            self.audio_bytes-=len(self.audio_queue.popleft())
    def _sample(self,left,right):
        self.audio_samples+=1;self._enqueue_audio(struct.pack('<hh',left,right))
    def _batch(self,data,frames):
        self.audio_samples+=frames
        if data and 0<frames<=65536:self._enqueue_audio(c.string_at(data,frames*4))
        return frames
    def drain_audio(self):
        data=b''.join(self.audio_queue);self.audio_queue.clear();self.audio_bytes=0;return data
    def _poll(self):pass
    def _input(self,port,device,index,ident):return int(port==0 and device==1 and index==0 and ident in self.buttons)
    def run_frame(self):
        if not self.loaded:raise RuntimeError('game not loaded')
        self.lib.retro_run()
    def save_state(self,path):
        """Explicit save only; bind the state to this exact ROM SHA-256."""
        n=self.lib.retro_serialize_size()
        if n<=0 or n>100_000_000:raise RuntimeError('serialization unavailable or too large')
        buf=c.create_string_buffer(n)
        if not self.lib.retro_serialize(buf,n):raise RuntimeError('serialization failed')
        payload=b'RCST1'+bytes.fromhex(self.game_hash)+struct.pack('<I',n)+buf.raw
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.retro-state-',dir=dest.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
            os.replace(tmp,dest)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def load_state(self,path):
        p=Path(path)
        if p.stat().st_size>100_000_041:raise ValueError('state too large')
        data=p.read_bytes()
        if len(data)<41 or data[:5]!=b'RCST1' or data[5:37]!=bytes.fromhex(self.game_hash):raise ValueError('state belongs to another game or is invalid')
        size=struct.unpack('<I',data[37:41])[0]
        if size!=len(data)-41 or size!=self.lib.retro_serialize_size():raise ValueError('invalid state size')
        buf=c.create_string_buffer(data[41:])
        if not self.lib.retro_unserialize(buf,size):raise RuntimeError('core rejected state')
    def set_verified_cheats(self,entries):
        """Apply only individually verified cheats for the exact loaded ROM hash."""
        selected=[]
        for entry in entries:
            if entry.get('rom_sha256')!=self.game_hash or entry.get('verified') is not True:raise ValueError('unverified or wrong-game cheat')
            code=entry.get('code')
            if not isinstance(code,str) or not code or len(code)>128 or not code.isascii():raise ValueError('invalid cheat code')
            selected.append(code.encode('ascii'))
        self.lib.retro_cheat_reset()
        for i,code in enumerate(selected):self.lib.retro_cheat_set(i,True,code)
    def close(self):
        if self.loaded:self.lib.retro_unload_game();self.loaded=False
        if self.initialized:self.lib.retro_deinit();self.initialized=False
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
