"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Clipboard, RefreshCw, Loader2, Sparkles } from "lucide-react";
import { toast } from "@/hooks/useToast";
import type { ChatDraftResult, ChatMessage } from "@/features/agent/services/recruitmentApi";
import { generateChatDraft } from "@/features/agent/services/recruitmentApi";

const SCENE_LABELS: Record<string, string> = {
  greeting: "初次打招呼",
  follow_up: "跟进",
  interview_invite: "邀约面试",
  info_request: "索要信息",
  objection_handling: "异议处理",
  closing: "收尾/加微信",
};

const SCENES = Object.keys(SCENE_LABELS);

interface AIDraftPanelProps {
  requirementId: number;
  candidateId: number;
  candidateName: string;
  lastMessage?: string;
  currentRole?: string;
  /** 已有的草稿结果，null 表示还没生成 */
  draft: ChatDraftResult | null;
  /** 生成中的 loading 状态 */
  generating: boolean;
  /** 开始生成时回调 — 父组件设置 loading 状态 */
  onGenerateStart: () => void;
  /** 当新的 draft 生成时回调 */
  onDraftGenerated: (result: ChatDraftResult) => void;
}

export function AIDraftPanel({
  requirementId,
  candidateId,
  candidateName,
  lastMessage,
  currentRole,
  draft,
  generating,
  onGenerateStart,
  onDraftGenerated,
}: AIDraftPanelProps) {
  const [selectedScene, setSelectedScene] = useState<string>(draft?.scene || "greeting");

  const handleGenerate = async (scene?: string) => {
    onGenerateStart();
    const messages: ChatMessage[] = lastMessage
      ? [{ role: "candidate" as const, content: lastMessage }]
      : [];
    try {
      const result = await generateChatDraft({
        requirement_id: requirementId,
        candidate_id: candidateId,
        messages,
      });
      onDraftGenerated(result);
      setSelectedScene(result.scene);
    } catch (error) {
      toast.error((error as Error).message || "生成话术失败");
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => toast.success("已复制到剪贴板"),
      () => toast.error("复制失败，请手动复制")
    );
  };

  const handleRegenerate = () => {
    void handleGenerate();
  };

  const handleSceneChange = (scene: string) => {
    setSelectedScene(scene);
    void handleGenerate(scene);
  };

  // 没有草稿且不在生成中：显示生成入口
  if (!draft && !generating) {
    return (
      <div className="rounded-md border border-dashed p-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <Sparkles className="h-5 w-5 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">生成 AI 话术草稿</p>
          <Button size="sm" variant="outline" onClick={() => void handleGenerate()}>
            <Sparkles className="mr-2 h-4 w-4" />
            生成话术
          </Button>
        </div>
      </div>
    );
  }

  // 生成中
  if (generating) {
    return (
      <div className="rounded-md border bg-muted/30 p-4">
        <div className="flex items-center justify-center gap-3 py-6">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <span className="text-sm text-muted-foreground">AI 正在生成话术...</span>
        </div>
      </div>
    );
  }

  // 有草稿结果
  const sceneLabel = SCENE_LABELS[selectedScene] || selectedScene;

  return (
    <div className="rounded-md border bg-muted/30 p-3">
      {/* 顶部：场景标签 + 操作按钮 */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">
            {sceneLabel}
          </Badge>
          <select
            value={selectedScene}
            onChange={(e) => handleSceneChange(e.target.value)}
            className="h-7 rounded border bg-transparent px-1 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
          >
            {SCENES.map((s) => (
              <option key={s} value={s}>
                {SCENE_LABELS[s]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={handleRegenerate}
            disabled={generating}
          >
            <RefreshCw className="mr-1 h-3 w-3" />
            重新生成
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => handleCopy(draft!.draft)}
          >
            <Clipboard className="mr-1 h-3 w-3" />
            采用草稿
          </Button>
        </div>
      </div>

      {/* 话术草稿 */}
      <div className="whitespace-pre-wrap text-sm leading-6 text-foreground">
        {draft!.draft}
      </div>

      {/* 追问建议 */}
      {draft!.follow_up_questions && draft!.follow_up_questions.length > 0 && (
        <div className="mt-3 border-t pt-2">
          <div className="text-xs font-medium text-muted-foreground mb-1">
            追问建议
          </div>
          <ul className="space-y-1">
            {draft!.follow_up_questions.map((q, i) => (
              <li key={i} className="text-xs text-muted-foreground flex items-start gap-1">
                <span className="text-blue-500 mt-0.5">&bull;</span>
                <span
                  className="cursor-pointer hover:text-foreground transition-colors"
                  onClick={() => handleCopy(q)}
                >
                  {q}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default AIDraftPanel;
