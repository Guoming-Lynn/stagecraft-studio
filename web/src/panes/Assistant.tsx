import { useEffect, useState } from "react";
import {
  callAssistant,
  cancelAssistant,
  errorText,
  loadAssistantProvider,
  loadStageRuns,
  previewAssistant,
  type AssistantCall,
  type AssistantPreview,
  type AssistantProvider,
  type StageRunItem,
} from "../api/client";
import { queueProposal } from "../proposal_store";
import { chrome, getLanguage } from "../text/chrome";
import { AssistantConnection } from "./AssistantConnection";
import {
  AssistantComposer,
  SendPreview,
  ProposalCard,
  topicLabel,
  type Topic,
} from "./AssistantParts";

type Message = {
  role: "user" | "assistant";
  text: string;
  call?: AssistantCall;
};

export function Assistant({ ready = true }: { ready?: boolean }) {
  const [provider, setProvider] = useState<AssistantProvider | null>(null);
  const [runs, setRuns] = useState<StageRunItem[]>([]);
  const [runId, setRunId] = useState("");
  const [topic, setTopic] = useState<Topic>("stage");
  const [ruleId, setRuleId] = useState("DESIGN_ESTIMABLE");
  const [fieldName, setFieldName] = useState("harmony_keys");
  const [question, setQuestion] = useState("");
  const [preview, setPreview] = useState<AssistantPreview | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [callId, setCallId] = useState("");
  const [error, setError] = useState("");
  const [sendApproved, setSendApproved] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    if (!ready) return;
    let disposed = false;
    void Promise.all([loadAssistantProvider(), loadStageRuns()])
      .then(([nextProvider, nextRuns]) => {
        if (disposed) return;
        setProvider(nextProvider);
        setRuns(nextRuns);
        setRunId(nextRuns[0] ? String(nextRuns[0].id) : "");
      })
      .catch((reason: unknown) => {
        if (!disposed) setError(errorText(reason));
      });
    return () => {
      disposed = true;
    };
  }, [ready]);

  const invalidate = () => {
    setPreview(null);
    setSendApproved(false);
  };
  const prepare = async () => {
    setBusy(true);
    setError("");
    invalidate();
    try {
      setPreview(
        await previewAssistant({
          stage_run_id: runId ? Number(runId) : null,
          topic,
          rule_id: ruleId,
          field_name: fieldName,
          question,
        }),
      );
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  };
  const submit = async () => {
    if (!preview || (preview.mode !== "local" && !sendApproved)) return;
    setBusy(true);
    setError("");
    const id = crypto.randomUUID().replaceAll("-", "");
    setCallId(id);
    setMessages((current) => [
      ...current.slice(-10),
      { role: "user", text: question || topicLabel(topic) },
    ]);
    try {
      const result = await callAssistant(
        preview.preview_id,
        id,
        preview.input_hash,
        sendApproved,
      );
      setMessages((current) => [
        ...current,
        { role: "assistant", text: result.text, call: result },
      ]);
      setQuestion("");
      invalidate();
      setProvider(await loadAssistantProvider());
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
      setCallId("");
    }
  };

  return (
    <div className="assistant-shell">
      <header className="assistant-header">
        <div>
          <h3>{chrome.assistantTitle}</h3>
          <p className="assistant-subhint">
            {provider?.capabilities.tool_calling
              ? chrome.assistantConnected
              : provider?.capabilities.text
                ? chrome.assistantExplanation
                : chrome.assistantLocal}
            {provider?.config
              ? ` · ${provider.config.model}`
              : ` · ${chrome.assistantUnconfigured}`}
          </p>
        </div>
        <button
          type="button"
          aria-label={chrome.assistantSettings}
          title={chrome.assistantSettings}
          onClick={() => setSettingsOpen((open) => !open)}
        >
          ⚙
        </button>
      </header>
      {settingsOpen ? (
        <AssistantConnection
          provider={provider}
          busy={busy}
          onBusy={setBusy}
          onError={setError}
          onChange={(next) => {
            setProvider(next);
            invalidate();
          }}
        />
      ) : null}
      <div className="assistant-messages" aria-live="polite">
        {messages.map((message, index) => (
          <article
            className={`assistant-message assistant-message-${message.role}`}
            key={`${index}-${message.role}`}
          >
            <p>{message.text}</p>
            {message.call ? (
              <>
                <p className="assistant-subhint">
                  {chrome.assistantNote} · {message.call.model} ·{" "}
                  {message.call.status} ·{" "}
                  {message.call.usage
                    ? `${message.call.usage.input_tokens}+${message.call.usage.output_tokens} tokens`
                    : getLanguage() === "en-US"
                      ? "Usage unknown"
                      : "用量未知"}
                </p>
                <p className="assistant-subhint">
                  {getLanguage() === "en-US" ? "Input hash" : "输入 hash"}：
                  {message.call.input_hash}
                </p>
                <p className="assistant-subhint">
                  {getLanguage() === "en-US" ? "Sources" : "来源"}：
                  {message.call.sources
                    .map((source) => source.ref)
                    .join(", ") || (getLanguage() === "en-US" ? "None" : "无")}
                </p>
                {message.call.proposal ? (
                  <ProposalCard
                    proposal={message.call}
                    onApply={queueProposal}
                  />
                ) : null}
              </>
            ) : null}
          </article>
        ))}
      </div>
      <AssistantComposer
        runs={runs}
        runId={runId}
        topic={topic}
        ruleId={ruleId}
        fieldName={fieldName}
        question={question}
        disabled={busy}
        onRun={(value) => {
          setRunId(value);
          invalidate();
        }}
        onTopic={(value) => {
          setTopic(value);
          invalidate();
        }}
        onRule={(value) => {
          setRuleId(value);
          invalidate();
        }}
        onField={(value) => {
          setFieldName(value);
          invalidate();
        }}
        onQuestion={(value) => {
          setQuestion(value);
          invalidate();
        }}
      />
      <div className="assistant-actions">
        <button type="button" disabled={busy} onClick={() => void prepare()}>
          {busy ? chrome.assistantSending : chrome.assistantPreview}
        </button>
        <button
          type="button"
          disabled={
            busy || !preview || (preview.mode !== "local" && !sendApproved)
          }
          onClick={() => void submit()}
        >
          {preview?.mode === "local"
            ? chrome.assistantLocalExplain
            : chrome.assistantSend}
        </button>
        {callId ? (
          <button
            type="button"
            onClick={() =>
              void cancelAssistant(callId).catch((reason: unknown) =>
                setError(errorText(reason)),
              )
            }
          >
            {chrome.cancel}
          </button>
        ) : null}
      </div>
      {preview ? (
        <SendPreview
          preview={preview}
          approved={sendApproved}
          onApprove={setSendApproved}
        />
      ) : null}
      {error ? <p className="log-error">{error}</p> : null}
      <p className="assistant-subhint">
        {getLanguage() === "en-US"
          ? "Assistant output is advisory. It can read authorized summaries and create drafts only; human review, protocol freezing, and scientific status remain controlled by the formal workflow."
          : "助手内容属于辅助说明。只读授权摘要，配置建议仅保存为草案。人工审阅、冻结和科学状态仍由正式分析流程决定。"}
      </p>
    </div>
  );
}
