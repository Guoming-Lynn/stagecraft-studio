import { useState } from "react";
import {
  errorText,
  loadAssistantProvider,
  removeAssistantProvider,
  saveAssistantProvider,
  type AssistantProvider,
} from "../api/client";
import { chrome } from "../text/chrome";

export function AssistantConnection({
  provider,
  busy,
  onBusy,
  onChange,
  onError,
}: {
  provider: AssistantProvider | null;
  busy: boolean;
  onBusy: (value: boolean) => void;
  onChange: (value: AssistantProvider) => void;
  onError: (value: string) => void;
}) {
  const [kind, setKind] = useState<"openai" | "anthropic">(
    provider?.config?.provider ?? "openai",
  );
  const [url, setUrl] = useState(
    provider?.config?.base_url ?? "https://api.openai.com/v1",
  );
  const [model, setModel] = useState(provider?.config?.model ?? "");
  const [key, setKey] = useState("");
  const [remember, setRemember] = useState(
    provider?.key_storage === "credential_store",
  );
  const [timeout, setTimeout] = useState(
    provider?.config?.timeout_seconds ?? 30,
  );
  const [limit, setLimit] = useState(provider?.config?.call_limit ?? 20);
  const save = async () => {
    onBusy(true);
    onError("");
    try {
      const next = await saveAssistantProvider({
        config: {
          provider: kind,
          base_url: url,
          model,
          timeout_seconds: timeout,
          call_limit: limit,
          context_chars: 16000,
          max_output_tokens: 1024,
        },
        api_key: key,
        remember_key: remember,
      });
      onChange(next);
      setKey("");
    } catch (reason) {
      onError(errorText(reason));
      setKey("");
    } finally {
      onBusy(false);
    }
  };
  const remove = async () => {
    onBusy(true);
    try {
      await removeAssistantProvider();
      onChange(await loadAssistantProvider());
      setKey("");
    } catch (reason) {
      onError(errorText(reason));
    } finally {
      onBusy(false);
    }
  };
  return (
    <section className="assistant-settings">
      <label>
        {chrome.serviceType}
        <select
          disabled={busy}
          value={kind}
          onChange={(event) =>
            setKind(event.target.value as "openai" | "anthropic")
          }
        >
          <option value="openai">OpenAI 兼容</option>
          <option value="anthropic">Anthropic Messages</option>
        </select>
      </label>
      <label>
        {chrome.baseUrl}
        <input
          disabled={busy}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          autoComplete="off"
        />
      </label>
      <label>
        {chrome.modelId}
        <input
          disabled={busy}
          value={model}
          onChange={(event) => setModel(event.target.value)}
          autoComplete="off"
        />
      </label>
      <label>
        API key
        <input
          disabled={busy}
          type="password"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          autoComplete="off"
        />
      </label>
      <label>
        {chrome.timeout}
        <input
          type="number"
          min={1}
          max={60}
          disabled={busy}
          value={timeout}
          onChange={(event) => setTimeout(Number(event.target.value))}
        />
      </label>
      <label>
        {chrome.callLimit}
        <input
          type="number"
          min={1}
          max={100}
          disabled={busy}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value))}
        />
      </label>
      <label className="assistant-consent">
        <input
          type="checkbox"
          checked={remember}
          disabled={busy}
          onChange={(event) => setRemember(event.target.checked)}
        />
        {chrome.rememberCredential}
      </label>
      <div className="assistant-actions">
        <button
          type="button"
          disabled={busy || !model || !key}
          onClick={() => void save()}
        >
          {chrome.saveProbe}
        </button>
        <button type="button" disabled={busy} onClick={() => void remove()}>
          {chrome.removeCredential}
        </button>
      </div>
      <p className="assistant-subhint">
        {chrome.capability}：
        {provider?.capabilities.text ? chrome.supported : chrome.unavailable} ·{" "}
        {chrome.structuredTools}{" "}
        {provider?.capabilities.tool_calling
          ? chrome.supported
          : chrome.unavailable}{" "}
        · {chrome.structuredOutput}{" "}
        {provider?.capabilities.structured_output
          ? chrome.supported
          : chrome.unavailable}{" "}
        · {chrome.streaming}{" "}
        {provider?.capabilities.streaming
          ? chrome.supported
          : chrome.unavailable}
      </p>
      <p className="assistant-subhint">
        {chrome.credential}：
        {provider?.key_storage === "credential_store"
          ? chrome.credentialStore
          : provider?.key_storage === "session"
            ? chrome.sessionMemory
            : chrome.notSaved}{" "}
        · {chrome.callsUsed} {provider?.calls_used ?? 0} 次。
        {chrome.fullResponse}
      </p>
    </section>
  );
}
