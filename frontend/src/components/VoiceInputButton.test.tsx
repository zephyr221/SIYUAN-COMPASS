import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { transcribeAudio } from "../api/speech";
import { isSpeechConfigured } from "../api/speechAvailability";
import { VoiceInputButton } from "./VoiceInputButton";

vi.mock("../api/speech", () => ({
  transcribeAudio: vi.fn()
}));

vi.mock("../api/speechAvailability", () => ({
  isSpeechConfigured: vi.fn()
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
  beforeEach(() => {
    // 默认按「已配置」渲染，语音关闭的分支由单独一条用例覆盖。
    vi.mocked(isSpeechConfigured).mockResolvedValue(true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("语音未配置时不渲染任何控件", async () => {
    vi.mocked(isSpeechConfigured).mockResolvedValue(false);

    render(<VoiceInputButton onTranscript={vi.fn()} />);

    await waitFor(() => expect(isSpeechConfigured).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /语音输入/ })).not.toBeInTheDocument();
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
    // 按钮要等 isSpeechConfigured 解析后才出现。
    fireEvent.click(await screen.findByRole("button", { name: /语音输入/ }));
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
    // 按钮要等 isSpeechConfigured 解析后才出现。
    fireEvent.click(await screen.findByRole("button", { name: /语音输入/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /取消/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /取消/ }));

    expect(onTranscript).not.toHaveBeenCalled();
    expect(transcribeAudio).not.toHaveBeenCalled();
  });
});
