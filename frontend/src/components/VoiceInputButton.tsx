import { useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../api/speech";

type VoiceInputButtonProps = {
  disabled?: boolean;
  onTranscript: (text: string) => void;
};

type RecorderState = "idle" | "recording" | "transcribing";

const MAX_RECORDING_SECONDS = 60;
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"];
const TRANSCRIPTION_SAMPLE_RATE = 16_000;

type AudioWindow = Window & {
  webkitAudioContext?: typeof AudioContext;
  webkitOfflineAudioContext?: typeof OfflineAudioContext;
};

function formatSeconds(seconds: number) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}

function supportedMediaType() {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_TYPES.find((type) => !MediaRecorder.isTypeSupported || MediaRecorder.isTypeSupported(type)) || "";
}

function fallbackFilename(blob: Blob) {
  const type = blob.type.toLowerCase();
  if (type.includes("mp4") || type.includes("m4a")) return "recording.mp4";
  if (type.includes("ogg") || type.includes("opus")) return "recording.ogg";
  if (type.includes("wav")) return "recording.wav";
  return "recording.webm";
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodeWav(audioBuffer: AudioBuffer) {
  const samples = audioBuffer.getChannelData(0);
  const dataLength = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, audioBuffer.sampleRate, true);
  view.setUint32(28, audioBuffer.sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, dataLength, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return buffer;
}

async function normalizeRecording(blob: Blob) {
  const audioWindow = window as AudioWindow;
  const AudioContextConstructor = window.AudioContext || audioWindow.webkitAudioContext;
  const OfflineAudioContextConstructor = window.OfflineAudioContext || audioWindow.webkitOfflineAudioContext;
  if (!AudioContextConstructor || !OfflineAudioContextConstructor || blob.type.includes("wav")) {
    return { blob, filename: fallbackFilename(blob) };
  }

  const audioContext = new AudioContextConstructor();
  try {
    const decoded = await audioContext.decodeAudioData(await blob.arrayBuffer());
    const frameCount = Math.max(1, Math.ceil(decoded.duration * TRANSCRIPTION_SAMPLE_RATE));
    const offlineContext = new OfflineAudioContextConstructor(
      1,
      frameCount,
      TRANSCRIPTION_SAMPLE_RATE
    );
    const source = offlineContext.createBufferSource();
    source.buffer = decoded;
    source.connect(offlineContext.destination);
    source.start();
    const rendered = await offlineContext.startRendering();
    return {
      blob: new Blob([encodeWav(rendered)], { type: "audio/wav" }),
      filename: "recording.wav"
    };
  } catch {
    // Some embedded browsers expose MediaRecorder but cannot decode its
    // container. Keep the original file as a fallback so the server can
    // decide whether the provider accepts that format.
    return { blob, filename: fallbackFilename(blob) };
  } finally {
    await audioContext.close().catch(() => undefined);
  }
}

export function VoiceInputButton({ disabled = false, onTranscript }: VoiceInputButtonProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const mountedRef = useRef(true);

  const stopTracks = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const clearTimer = () => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
  };

  const reset = () => {
    clearTimer();
    stopTracks();
    recorderRef.current = null;
    chunksRef.current = [];
    setElapsed(0);
    setState("idle");
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cancelledRef.current = true;
      clearTimer();
      if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop();
      stopTracks();
    };
  }, []);

  async function startRecording() {
    if (disabled || state !== "idle") return;
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("当前浏览器不支持录音，请改用支持麦克风的浏览器。 ");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = supportedMediaType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      cancelledRef.current = false;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setError("录音失败，请检查麦克风权限后重试。 ");
        reset();
      };
      recorder.onstop = async () => {
        clearTimer();
        stopTracks();
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || "audio/webm" });
        recorderRef.current = null;
        chunksRef.current = [];
        if (cancelledRef.current || blob.size === 0) {
          if (mountedRef.current) reset();
          return;
        }
        if (mountedRef.current) setState("transcribing");
        try {
          const normalized = await normalizeRecording(blob);
          const result = await transcribeAudio(normalized.blob, normalized.filename);
          if (mountedRef.current) {
            onTranscript(result.text);
            reset();
          }
        } catch (caught) {
          if (mountedRef.current) {
            setError(caught instanceof Error ? caught.message : "语音转写失败，请稍后重试。 ");
            reset();
          }
        }
      };
      recorder.start();
      setElapsed(0);
      setState("recording");
      timerRef.current = window.setInterval(() => {
        setElapsed((current) => {
          if (current + 1 >= MAX_RECORDING_SECONDS) {
            recorder.stop();
          }
          return current + 1;
        });
      }, 1000);
    } catch (caught) {
      stopTracks();
      setError(caught instanceof DOMException && caught.name === "NotAllowedError"
        ? "麦克风权限未开启，请允许浏览器使用麦克风。"
        : "无法开始录音，请检查设备和浏览器权限。 ");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  function cancelRecording() {
    cancelledRef.current = true;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    else reset();
  }

  return (
    <div className="voice-input-control">
      <div className="voice-input-actions">
        {state === "idle" && (
          <button className="voice-button" disabled={disabled} onClick={startRecording} type="button">
            <span aria-hidden="true">🎙</span> 语音输入
          </button>
        )}
        {state === "recording" && (
          <>
            <button className="voice-button voice-button-recording" onClick={stopRecording} type="button">
              <span aria-hidden="true">●</span> 停止录音 {formatSeconds(elapsed)}
            </button>
            <button className="voice-button voice-button-secondary" onClick={cancelRecording} type="button">取消</button>
          </>
        )}
        {state === "transcribing" && <span className="voice-input-status" role="status">正在上传并转写，请稍候…</span>}
      </div>
      {state === "idle" && <span className="voice-input-hint">最长录音 1 分钟，文本会追加到当前内容末尾。</span>}
      {error && <div className="field-error" role="alert">{error}</div>}
    </div>
  );
}
