from pathlib import Path
import sys, os, tempfile, threading, time, struct, fcntl, termios, subprocess, select, signal
import numpy as np
import math
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pulse_tui.audio import CavaInput, RawFrames
from pulse_tui.rasterizer import depth_mask
from pulse_tui.renderer import Renderer
from pulse_tui.scene import Scene
from pulse_tui.settings import BARS, BG, Options
from pulse_tui.terminal import Terminal, handle_keys

# Exercise the same package entry point as the launcher and installed CLI.
CLI = [sys.executable, '-m', 'pulse_tui']
os.environ['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + os.environ.get('PYTHONPATH', '')

# Deterministic spectra are test fixtures only, not an application mode.
def synthetic_spectrum(now):
    bins = np.linspace(0, 1, BARS)
    values = np.zeros(BARS)
    pattern = (0, 2, 1, 2, 0, 1, 2, 1, 0, 2, 2, 1)
    beat = .31
    index = int(now / beat)
    for k in range(max(0, index - 6), index + 1):
        age = now - k * beat
        band = pattern[k % len(pattern)]
        center = (.12, .47, .86)[band] + .05 * math.sin(k * 2.1)
        width = (.12, .16, .08)[band]
        values += np.exp(-((bins - center) / width) ** 2) * math.exp(-age * (6 if band == 2 else 4)) * .8
    return np.clip(values, 0, 1)


# Actual framing: incomplete reads, multiple frames, leftovers.
r=RawFrames(4)
assert r.feed(bytes([1,2,3])) is None
assert np.allclose(r.feed(bytes([4,5,6,7,8,9])),np.array([5,6,7,8])/255)
assert r.pending==bytearray([9])
assert np.allclose(r.feed(bytes([10,11,12])),np.array([9,10,11,12])/255)
print('PASS raw frame boundaries')

renderer=Renderer();scene=Scene()
for t in np.arange(0,3.2,1/60):scene.update(synthetic_spectrum(t),t,1/60)
assert scene.pulses
occupancy = []
for density in (.5, 1, 2, 4):
 opt=Options(density=density, camera='overhead')
 begin=time.perf_counter()
 lines=renderer.frame(scene,3.2,opt,120,40,'TEST INPUT',24)
 assert len(lines)==40
 assert renderer.mesh_n==round(38*density)+1
 dots=renderer.dots(scene,3.2,opt,120,36)
 occupancy.append(np.count_nonzero(dots>=0))
 assert sum(0x2800 <= ord(c) <= 0x28ff for line in lines for c in line)>100
 print(f'PASS mesh {density}x ({renderer.mesh_n}x{renderer.mesh_n}); frame plus dot check {(time.perf_counter()-begin)*1000:.1f} ms')
assert occupancy[-1]>occupancy[1], occupancy
# A flat triangle must have continuous, exact surface depth in its interior.
depth=depth_mask(np.array([1.,8.,1.]),np.array([1.,1.,8.]),np.array([2.,2.,2.]),np.array([[0,1,2]]),10,10).reshape(10,10)
assert np.allclose(depth[2:4,2:4],2)
assert np.isinf(depth[9,9])
opt=Options()
handle_keys(']',opt,scene,3.2);assert opt.density==2.25
handle_keys('[',opt,scene,3.2);assert opt.density==2
print('PASS finer/coarser controls, denser screen coverage, and surface depth')

# The native hot loops must preserve the portable renderer's visible geometry.
if renderer.native:
 portable=Renderer(use_native=False)
 for cols,rows,camera,density in [(120,40,'flight',1),(240,65,'overhead',2),(360,90,'flight',2),(120,40,'fixed',4)]:
  opt=Options(camera=camera,density=density)
  native_dots=renderer.dots(scene,3.2,opt,cols,rows-4)
  python_dots=portable.dots(scene,3.2,opt,cols,rows-4)
  disagreements=np.count_nonzero((native_dots>=0)!=(python_dots>=0))
  assert disagreements<=max(4,int(python_dots.size*.0002)), (camera,density,disagreements)
  shared=(native_dots>=0)&(python_dots>=0)
  assert np.allclose(native_dots[shared],python_dots[shared],atol=1e-10)
  print(f'PASS native/Python parity {cols}x{rows} {camera} {density}x: {disagreements} boundary dots differ')
else:
 print('Native library unavailable; portable renderer tests remain active.')
# Repeated frames must not be resent, and row colors must be self-contained.
import io
terminal=Terminal();terminal.previous_lines=[]
original_stdout=sys.stdout
capture=io.StringIO()
try:
 sys.stdout=capture
 terminal.draw(['a','b'])
 first=capture.getvalue();terminal.draw(['a','b'])
 assert capture.getvalue()==first
 terminal.draw(['a','c'])
 assert capture.getvalue()[len(first):]==BG+'\x1b[2;1Hc\x1b[K'
finally:
 sys.stdout=original_stdout
print('PASS unchanged-row output suppression')

# Live integration through the real CAVA binary and a synthetic stereo PCM FIFO.
with tempfile.TemporaryDirectory() as tmp:
 fifo=Path(tmp)/'pcm';os.mkfifo(fifo)
 conf=Path(tmp)/'input.conf';conf.write_text('[input]\nmethod = fifo\nsource = '+str(fifo)+'\n')
 before=conf.read_bytes()
 audio=CavaInput(conf)
 stop=threading.Event()
 def write_pcm():
  deadline=time.monotonic()+4
  fd=None
  while fd is None and time.monotonic()<deadline:
   try:fd=os.open(fifo,os.O_WRONLY|os.O_NONBLOCK)
   except OSError:time.sleep(.01)
  if fd is None:return
  try:
   phase=0
   while not stop.is_set():
    samples=np.arange(2048)+phase
    tone=(np.sin(samples*2*np.pi*180/44100)*22000).astype('<i2')
    right=(np.sin(samples*2*np.pi*2200/44100)*22000).astype('<i2')
    data=np.column_stack((tone,right)).tobytes();pos=0
    while pos<len(data) and not stop.is_set():
     try:pos+=os.write(fd,data[pos:])
     except BlockingIOError:time.sleep(.003)
    phase+=2048;time.sleep(.015)
  except BrokenPipeError:pass
  finally:os.close(fd)
 writer=threading.Thread(target=write_pcm,daemon=True);writer.start()
 try:
  deadline=time.monotonic()+4;nonzero=False
  while time.monotonic()<deadline:
   spectrum,seq=audio.poll()
   if seq and spectrum.max()>.03:nonzero=True;break
   time.sleep(.02)
  assert nonzero, 'CAVA failed to deliver nonzero spectrum'
  assert spectrum.shape==(2,64)
  assert spectrum[0].argmax() < spectrum[1].argmax(), 'Stereo frequency order is incorrect'
  assert np.all(np.max(spectrum,axis=1)>.03), 'Missing a stereo channel'
  assert conf.read_bytes()==before
  print(f'PASS live CAVA/FIFO integration: {seq} frames; peak {spectrum.max():.2f}; source config unchanged')
 finally:
  stop.set();audio.close();writer.join(timeout=2)
 assert audio.process.poll() is not None and not audio.path.exists()
 print('PASS CAVA shutdown and temporary-config cleanup')

# Real interactive terminal, mesh control, resize, quit, termios restoration.
import pty
master,slave=pty.openpty()
fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',35,100,0,0))
original=termios.tcgetattr(slave)
p=subprocess.Popen([*CLI,'--scene','ribbons','--palette','blue','--input-method','fifo','--source','/dev/zero','--fps','18','--duration','8'],stdin=slave,stdout=slave,stderr=slave)
output=bytearray()
def pump(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if select.select([master],[],[],.05)[0]:
   try:output.extend(os.read(master,262144))
   except OSError:break
deadline=time.monotonic()+5
while b'LIVE / CAVA' not in output and p.poll() is None and time.monotonic()<deadline:pump(.1)
assert p.poll() is None, output.decode(errors='replace')[-2000:]
os.write(master,b'c+]p');pump(.6)
assert b'WIREFRAME' in output and b'LIVE / CAVA' in output
assert b'blue' in output and b'neon' in output
assert b'Endless Ribbons' in output
for label in (b'Orbital Fragments',b'Filament Current',b'Terrain',b'Endless Ribbons'):
 os.write(master,b's');pump(.18)
 assert label in output, label
os.write(master,b'S');pump(.18)
assert b'Filament Current' in output
os.write(master,b'v');pump(.3)
assert b'classic' in output
fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0));p.send_signal(signal.SIGWINCH)
pump(.4);os.write(master,b'[ h');pump(.3);os.write(master,b'q');pump(.3)
p.wait(timeout=3)
assert p.returncode==0 and b'\x1b[?1049l' in output
after=termios.tcgetattr(slave)
# macOS may set the housekeeping PENDIN flag when canonical mode resumes.
after[3] &= ~getattr(termios, 'PENDIN', 0)
original[3] &= ~getattr(termios, 'PENDIN', 0)
assert after==original, [(i,a,b) for i,(a,b) in enumerate(zip(original,after)) if a!=b]
os.close(master);os.close(slave)
print('PASS scene switching, mesh/camera/energy controls, resize, quit, terminal restoration')

# Ctrl-C must restore terminal settings and the alternate screen as well.
master,slave=pty.openpty()
fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
original=termios.tcgetattr(slave)
p=subprocess.Popen([*CLI,'--input-method','fifo','--source','/dev/zero','--duration','5'],stdin=slave,stdout=slave,stderr=slave)
output=bytearray()
deadline=time.monotonic()+3
while b'LIVE / CAVA' not in output and p.poll() is None and time.monotonic()<deadline:pump(.1)
p.send_signal(signal.SIGINT);pump(.3);p.wait(timeout=3)
assert p.returncode==0 and b'\x1b[?1049l' in output
after=termios.tcgetattr(slave)
assert after[3]&~getattr(termios,'PENDIN',0)==original[3]&~getattr(termios,'PENDIN',0)
os.close(master);os.close(slave)
print('PASS Ctrl-C restoration')

# Removed modes must be rejected by argument parsing rather than starting audio.
result=subprocess.run([*CLI,'--demo'],capture_output=True,text=True)
assert result.returncode==2 and 'unrecognized arguments: --demo' in result.stderr
help_result=subprocess.run([*CLI,'--help'],capture_output=True,text=True,check=True)
assert '--demo' not in help_result.stdout and '--snapshot' not in help_result.stdout
print('PASS removed mode rejection and live-only CLI help')
