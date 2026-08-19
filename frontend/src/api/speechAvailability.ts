import { fetchSpeechStatus } from "./speech";

// 本文件属于 sjtu-production 部署分支，不在学生上游仓库中。
//
// 上游把语音输入按钮无条件渲染，但后端默认 SPEECH_PROVIDER=disabled，
// 学生录完音只会拿到 503。生产环境在完成学校侧隐私审核和讯飞授权之前保持关闭，
// 因此这里先问一次 /speech/status，未配置就不渲染按钮。
//
// 问卷中有多个可语音输入的字段，每个字段一个按钮实例，
// 所以缓存在模块级而不是组件级，整页只发一次请求。

let cached: Promise<boolean> | null = null;

export function isSpeechConfigured(): Promise<boolean> {
  if (!cached) {
    cached = fetchSpeechStatus()
      .then((status) => status.configured)
      // 状态查不到就按未配置处理：宁可不显示按钮，也不要显示一个点了就失败的按钮。
      .catch(() => false);
  }
  return cached;
}

export function resetSpeechAvailabilityCache() {
  cached = null;
}
