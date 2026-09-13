"""Original AI-composed score, rendered locally with additive synthesis.

Development only: numpy and lameenc. No samples, pretrained audio model or
external recordings. The explicit melody and arrangement were composed by Codex.
"""
from pathlib import Path
import json
import math
import wave
import numpy as np
import lameenc

RATE = 32000
BPM = 96
BEAT = 60 / BPM
BARS = 32
DURATION = BARS * 4 * BEAT
ROOT = Path(__file__).resolve().parents[1]
mix = np.zeros((round(DURATION * RATE), 2), dtype=np.float64)
rng = np.random.default_rng(20260913)

# D major, gently coloured sevenths and ninths. Four eight-bar phrases.
chords = [
    ([54, 61, 64, 69], 38), ([57, 61, 64, 68], 42),
    ([54, 57, 61, 66], 35), ([55, 59, 62, 66], 31),
    ([55, 59, 62, 66], 40), ([55, 61, 64, 66], 33),
    ([54, 57, 61, 64], 38), ([55, 59, 61, 66], 33),
]
# (beat within bar, MIDI note, duration in beats). Call, answer, then release.
melody = [
 [(0.5,66,.75),(1.5,69,.5),(2.5,73,.75),(3.5,71,.4)],
 [(0.5,69,1),(2,68,.5),(3,64,.75)],
 [(0.5,66,.5),(1.25,69,.5),(2,73,.75),(3.25,71,.5)],
 [(0.5,69,1),(2,66,1.5)],
 [(0.5,67,.75),(1.5,71,.5),(2.5,74,.75)],
 [(0.5,73,.5),(1.5,71,.5),(2.5,69,1)],
 [(0.5,66,.5),(1.5,64,.5),(2.5,62,1)],
 [(1,64,.75),(2.5,61,.75)],
]

def add(at, wave_data, level=1, pan=0):
    start = round(at * BEAT * RATE)
    left = math.sqrt((1-pan)/2)
    right = math.sqrt((1+pan)/2)
    indices = (np.arange(len(wave_data)) + start) % len(mix)
    mix[indices,0] += wave_data * level * left
    mix[indices,1] += wave_data * level * right

def tone(note, length, kind='keys'):
    duration = length * BEAT + (1.1 if kind == 'keys' else .2)
    t = np.arange(round(duration*RATE))/RATE
    f = 440 * 2 ** ((note-69)/12)
    attack = 1-np.exp(-t/0.009)
    if kind == 'bass':
        signal = np.sin(2*np.pi*f*t) + .19*np.sin(4*np.pi*f*t)
        env = attack * np.exp(-t/0.36)
    elif kind == 'lead':
        signal = np.sin(2*np.pi*f*t) + .28*np.sin(4*np.pi*f*t)*np.exp(-t/0.11)
        env = attack * np.exp(-t/0.5)
    else:
        signal = (np.sin(2*np.pi*f*t + .6*np.sin(2*np.pi*f*t)*np.exp(-t/.16))
                  + .13*np.sin(2*np.pi*f*3*t)*np.exp(-t/.2))
        env = attack * np.exp(-t/.68)
    release = np.minimum(1, np.maximum(0, (duration-t)/.15))
    return signal * env * release

for bar in range(BARS):
    chord, bass = chords[bar % 8]
    phrase = bar // 8
    for beat, strength in [(0,.105),(1.75,.063),(3,.073)]:
        for voice,note in enumerate(chord):
            add(bar*4+beat+voice*.015, tone(note,1.3), strength, (voice-1.5)*.24)
    for beat,note,level in [(0,bass,.17),(2,bass+12,.105),(3.5,bass+7,.075)]:
        add(bar*4+beat, tone(note,.7,'bass'),level)
    # Second phrase leaves breathing space; fourth resolves to the tonic.
    line = melody[bar % 8]
    if phrase == 1 and bar % 2: line = line[:2]
    if phrase == 2:
        line = [(b, n+12 if i==0 and bar%2==0 else n, d) for i,(b,n,d) in enumerate(line)]
    if bar == 31: line = [(0.5,64,.5),(1.5,61,.5),(2.5,62,1)]
    for beat,note,length in line:
        add(bar*4+beat,tone(note,length,'lead'),.10 if phrase!=1 else .075,.12)
    for eighth in range(8):
        t = np.arange(round(RATE*.11))/RATE
        noise = rng.standard_normal(len(t))
        high = np.concatenate(([0.],np.diff(noise)))
        shaker = high*np.exp(-t/.017)*(1-np.exp(-t/.001))
        add(bar*4+eighth*.5+(0.035 if eighth%2 else 0),shaker,.008 if eighth%2 else .005,-.25)
    for beat in [0,2]:
        t = np.arange(round(RATE*.3))/RATE
        kick = np.sin(2*np.pi*(48*t + 1.9*(1-np.exp(-t*35)))) * np.exp(-t*20)
        add(bar*4+beat,kick,.09)
    for beat in [1,3]:
        t=np.arange(round(RATE*.12))/RATE
        brush=rng.standard_normal(len(t))*np.exp(-t*38)*(1-np.exp(-t*180))
        add(bar*4+beat,brush,.013,.25)

# Circular room reflections make the tail continue naturally at the loop boundary.
dry=mix.copy()
for delay,level in [(0.083,.10),(.151,.07),(.237,.05)]:
    mix += np.roll(dry[:,::-1],round(delay*RATE),axis=0)*level
mix=np.tanh(mix*1.15)
mix *= .55 / max(np.max(np.abs(mix)), .0001)
pcm=(mix*32767).astype('<i2')
out=ROOT/'assets'/'music-theme.mp3'
encoder=lameenc.Encoder()
encoder.set_bit_rate(64)
encoder.set_in_sample_rate(RATE)
encoder.set_channels(2)
encoder.set_quality(2)
out.write_bytes(encoder.encode(pcm.tobytes())+encoder.flush())
preview=ROOT/'.publishing'/'music-preview.wav'
with wave.open(str(preview),'wb') as wav:
    wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(RATE);wav.writeframes(pcm.tobytes())
metadata={'title':'Спокойная смена','composer':'Codex (AI-assisted original composition)',
          'method':'Explicit AI-composed score; local additive synthesis, no external audio model or samples',
          'bpm':BPM,'duration_seconds':DURATION,'sample_rate':RATE,'channels':2,
          'mp3_bytes':out.stat().st_size,'peak':float(np.max(np.abs(mix))),
          'rms':float(np.sqrt(np.mean(mix**2)))}
(ROOT/'music'/'track.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(metadata,ensure_ascii=False))
