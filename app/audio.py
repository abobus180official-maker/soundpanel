from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
import soundfile as sf


AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".aiff", ".aif", ".opus")


def resample_linear(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or len(data) == 0:
        return data
    n_out = max(1, int(round(len(data) * dst_sr / float(src_sr))))
    idx = np.linspace(0.0, len(data) - 1.0, n_out, dtype=np.float64)
    lo = np.floor(idx).astype(np.int64)
    hi = np.minimum(lo + 1, len(data) - 1)
    frac = (idx - lo)[:, None].astype(np.float32)
    return (data[lo] * (1.0 - frac) + data[hi] * frac).astype(np.float32)


def compute_peaks(data: np.ndarray, buckets: int = 1400) -> np.ndarray:
    mono = data.mean(axis=1) if data.ndim > 1 else data
    if len(mono) == 0:
        return np.zeros(buckets, dtype=np.float32)
    n = min(buckets, len(mono))
    edges = np.linspace(0, len(mono), n + 1).astype(np.int64)
    peaks = np.zeros(n, dtype=np.float32)
    for i in range(n):
        start = edges[i]
        end = max(edges[i] + 1, edges[i + 1])
        peaks[i] = float(np.max(np.abs(mono[start:end])))
    return peaks


class Sound:
    def __init__(self, sound_id: int, path: str, name: str, data: np.ndarray,
                 samplerate: int, hotkey: str = "", volume: float = 1.0):
        self.id = sound_id
        self.path = path
        self.name = name
        self.data = data
        self.samplerate = samplerate
        self.hotkey = hotkey
        self.volume = volume
        self.peaks = compute_peaks(data)

    @property
    def duration(self) -> float:
        return len(self.data) / float(self.samplerate) if self.samplerate else 0.0


class Voice:
    def __init__(self, sound: Sound, volume: float, loop: bool = False):
        self.sound = sound
        self.pos = 0
        self.volume = volume
        self.loop = loop

    @property
    def progress(self) -> float:
        total = len(self.sound.data)
        return min(1.0, self.pos / float(total)) if total else 0.0

    @property
    def finished(self) -> bool:
        return self.pos >= len(self.sound.data)


class AudioEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.voices: list[Voice] = []
        self.samplerate = 48000
        self.out_device: int | None = None
        self.mic_device: int | None = None
        self.mic_enabled = True
        self.mic_gain = 1.0
        self.sfx_gain = 1.0
        self.out_level = 0.0
        self.mic_level = 0.0
        self.last_error: str | None = None
        self._out_stream: sd.OutputStream | None = None
        self._in_stream: sd.InputStream | None = None
        self._mic_buffer = np.zeros((0, 2), dtype=np.float32)
        self._mic_samplerate = 0
        self._pending: list[Voice] = []

    def load_sound(self, path: str, name: str, sound_id: int, hotkey: str = "",
                   volume: float = 1.0) -> Sound:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        if data.ndim == 1:
            data = data[:, None]
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        data = np.ascontiguousarray(data.astype(np.float32))
        if sr != self.samplerate:
            data = resample_linear(data, sr, self.samplerate)
            sr = self.samplerate
        return Sound(sound_id, path, name, data, sr, hotkey, volume)

    @staticmethod
    def output_devices() -> list[tuple[int, str]]:
        return AudioEngine._devices("output")

    @staticmethod
    def input_devices() -> list[tuple[int, str]]:
        return AudioEngine._devices("input")

    @staticmethod
    def _devices(kind: str) -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []
        try:
            for index, dev in enumerate(sd.query_devices()):
                channels = dev.get("max_output_channels" if kind == "output" else "max_input_channels", 0)
                if channels > 0:
                    result.append((index, dev["name"]))
        except Exception as exc:
            print("device query failed:", exc)
        return result

    def default_samplerate(self, out_device: int | None) -> int:
        try:
            info = sd.query_devices(out_device, "output")
            sr = int(round(float(info["default_samplerate"])))
            if sr >= 8000:
                return sr
        except Exception:
            pass
        return 48000

    def start(self, out_device: int | None, mic_device: int | None,
              samplerate: int | None = None) -> bool:
        self.stop()
        self.last_error = None
        self.out_device = out_device
        self.mic_device = mic_device
        self.samplerate = samplerate or self.default_samplerate(out_device)
        try:
            self._out_stream = sd.OutputStream(
                samplerate=self.samplerate,
                channels=2,
                device=out_device,
                dtype="float32",
                blocksize=1024,
                callback=self._out_callback,
            )
            self._out_stream.start()
        except Exception as exc:
            self.last_error = f"Не удалось открыть устройство вывода: {exc}"
            self._out_stream = None
            return False
        if mic_device is not None:
            self._open_mic(mic_device)
        return True

    def _open_mic(self, mic_device: int) -> None:
        try:
            info = sd.query_devices(mic_device, "input")
            self._mic_samplerate = int(round(float(info["default_samplerate"])))
            self._in_stream = sd.InputStream(
                samplerate=self._mic_samplerate,
                channels=1,
                device=mic_device,
                dtype="float32",
                blocksize=1024,
                callback=self._in_callback,
            )
            self._in_stream.start()
        except Exception as exc:
            self._in_stream = None
            self.last_error = f"Не удалось открыть микрофон: {exc}"

    def stop(self) -> None:
        for stream in (self._in_stream, self._out_stream):
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self._in_stream = None
        self._out_stream = None
        with self.lock:
            self.voices.clear()
            self._mic_buffer = np.zeros((0, 2), dtype=np.float32)
        self.out_level = 0.0
        self.mic_level = 0.0

    @property
    def running(self) -> bool:
        return self._out_stream is not None

    def _in_callback(self, indata, frames, time_info, status) -> None:
        mono = indata[:, 0].copy()
        if self._mic_samplerate and self._mic_samplerate != self.samplerate:
            mono = resample_linear(mono, self._mic_samplerate, self.samplerate)
        block = np.repeat(mono[:, None], 2, axis=1)
        with self.lock:
            self._mic_buffer = np.concatenate([self._mic_buffer, block], axis=0)
            limit = self.samplerate
            if len(self._mic_buffer) > limit:
                self._mic_buffer = self._mic_buffer[-limit:]
        self.mic_level = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0

    def _out_callback(self, outdata, frames, time_info, status) -> None:
        mix = np.zeros((frames, 2), dtype=np.float32)
        with self.lock:
            self.voices.extend(self._pending)
            self._pending.clear()
            alive: list[Voice] = []
            for voice in self.voices:
                data = voice.sound.data
                if voice.pos >= len(data):
                    if voice.loop and len(data):
                        voice.pos = 0
                    else:
                        continue
                chunk = data[voice.pos:voice.pos + frames]
                count = len(chunk)
                if count:
                    mix[:count] += chunk * (voice.volume * self.sfx_gain)
                    voice.pos += count
                if voice.pos < len(data) or voice.loop:
                    alive.append(voice)
            self.voices = alive
            if self.mic_enabled and self.mic_gain > 0.0 and len(self._mic_buffer):
                take = min(frames, len(self._mic_buffer))
                mix[:take] += self._mic_buffer[:take] * self.mic_gain
                self._mic_buffer = self._mic_buffer[take:]
        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix
        self.out_level = float(np.sqrt(np.mean(mix ** 2))) if frames else 0.0

    def play(self, sound: Sound, volume: float | None = None, loop: bool = False,
             exclusive: bool = False) -> None:
        voice = Voice(sound, sound.volume if volume is None else volume, loop)
        with self.lock:
            if exclusive:
                self.voices = [v for v in self.voices if v.sound.id != sound.id]
            self._pending.append(voice)

    def stop_sound(self, sound_id: int) -> None:
        with self.lock:
            self.voices = [v for v in self.voices if v.sound.id != sound_id]
            self._pending = [v for v in self._pending if v.sound.id != sound_id]

    def stop_all(self) -> None:
        with self.lock:
            self.voices.clear()
            self._pending.clear()

    def playing_ids(self) -> set[int]:
        with self.lock:
            return {v.sound.id for v in self.voices}

    def voice_progress(self, sound_id: int) -> float | None:
        with self.lock:
            for voice in self.voices:
                if voice.sound.id == sound_id:
                    return voice.progress
        return None

    def set_sfx_gain(self, value: float) -> None:
        self.sfx_gain = max(0.0, min(2.0, value))

    def set_mic_gain(self, value: float) -> None:
        self.mic_gain = max(0.0, min(2.0, value))
