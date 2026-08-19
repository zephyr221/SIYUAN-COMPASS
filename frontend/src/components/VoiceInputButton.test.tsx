import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { transcribeAudio } from "../api/speech";
import { VoiceInputButton } from "./VoiceInputButton";

vi.mock("../api/speech", () => ({
  transcribeAudio: vi.fn()
}));

class FakeMediaRecorder {
  static isTypeSupported() {
    return true;
  }

  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["audio"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

describe("VoiceInputButton", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("录音结束后上传并回传转写文本", async () => {
    const trackStop = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] });
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia }
    });
    vi.mocked(transcribeAudio).mockResolvedValue({ text: "这是语音内容" });
    const onTranscript = vi.fn();

    render(<VoiceInputButton onTranscript={onTranscript} />);
    fireEvent.click(screen.getByRole("button", { name: /语音输入/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /停止录音/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /停止录音/ }));

    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("这是语音内容"));
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true });
    expect(trackStop).toHaveBeenCalledOnce();
  });

  it("录音取消后不上传音频", async () => {
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] });
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia }
    });
    const onTranscript = vi.fn();

    render(<VoiceInputButton onTranscript={onTranscript} />);
    fireEvent.click(screen.getByRole("button", { name: /语音输入/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /取消/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /取消/ }));

    expect(onTranscript).not.toHaveBeenCalled();
    expect(transcribeAudio).not.toHaveBeenCalled();
  });
});
