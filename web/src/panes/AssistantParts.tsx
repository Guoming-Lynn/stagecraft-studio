import type {
  AssistantCall,
  AssistantPreview,
  StageRunItem,
} from "../api/client";
import { chrome } from "../text/chrome";
export type Topic = "stage" | "rule" | "field" | "proposal" | "annotation";
export type ProtocolValues = Extract<
  NonNullable<AssistantCall["proposal"]>["values"],
  { target_gene: string }
>;
const rules = [
  "DESIGN_ESTIMABLE",
  "RESOLUTION_REVIEW_REQUIRED",
  "REVIEW_CLUSTER_COMPLETE",
  "CLAIM_SCOPE_ALLOWED",
  "CALIBRATION_STATUS_PRESERVED",
];
const fields = [
  "target_gene",
  "species",
  "harmony_keys",
  "loose_min_genes",
  "libraries",
];
export function topicLabel(topic: Topic): string {
  return {
    stage: chrome.stageSummary,
    rule: chrome.ruleExplanation,
    field: chrome.fieldExplanation,
    proposal: chrome.proposalDraft,
    annotation: chrome.clusterCandidate,
  }[topic];
}
export function ProposalCard({
  proposal,
  onApply,
}: {
  proposal: AssistantCall;
  onApply?: (values: ProtocolValues) => void;
}) {
  const draft = proposal.proposal;
  if (!draft) return null;
  const values = draft.values;
  if (draft.kind === "cluster_annotation" && "cluster_id" in values) {
    return (
      <section className="assistant-proposal">
        <strong>{chrome.assistantDraftReadOnly}</strong>
        <dl>
          <div>
            <dt>cluster</dt>
            <dd>{values.cluster_id}</dd>
          </div>
          <div>
            <dt>{chrome.candidateName}</dt>
            <dd>{values.candidate_name}</dd>
          </div>
          <div>
            <dt>{chrome.markerGenes}</dt>
            <dd>{values.marker_genes.join(", ")}</dd>
          </div>
        </dl>
        <p>{values.rationale}</p>
        <p className="assistant-subhint">{chrome.candidateHumanReview}</p>
      </section>
    );
  }
  if (!onApply || !("target_gene" in values)) return null;
  return (
    <section className="assistant-proposal">
      <strong>Proposal · DRAFT</strong>
      <dl>
        {Object.entries(values).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{Array.isArray(value) ? value.join(", ") : value}</dd>
          </div>
        ))}
      </dl>
      <p>{draft.rationale}</p>
      <p className="assistant-subhint">{draft.note}</p>
      <button type="button" onClick={() => onApply(values)}>
        {chrome.applyToProtocol}
      </button>
    </section>
  );
}
export function SendPreview({
  preview,
  approved,
  onApprove,
}: {
  preview: AssistantPreview;
  approved: boolean;
  onApprove: (value: boolean) => void;
}) {
  return (
    <section className="assistant-preview">
      <div className="assistant-preview-head">
        <strong>{chrome.sendPreview}</strong>
        <span>
          {preview.mode === "tools"
            ? chrome.structuredTools
            : preview.mode === "explanation"
              ? chrome.explanationMode
              : chrome.localOnly}
        </span>
      </div>
      <p className="assistant-subhint">
        {chrome.summaryHash}: {preview.input_hash}
      </p>
      <p className="assistant-detail">{preview.local_text}</p>
      <details>
        <summary>{chrome.inspectPayload}</summary>
        <pre>{JSON.stringify(preview.payload, null, 2)}</pre>
      </details>
      {preview.mode !== "local" ? (
        <label className="assistant-consent">
          <input
            type="checkbox"
            checked={approved}
            onChange={(event) => onApprove(event.target.checked)}
          />
          {chrome.sendConsent}
        </label>
      ) : null}
    </section>
  );
}
export function AssistantComposer(props: {
  runs: StageRunItem[];
  runId: string;
  topic: Topic;
  ruleId: string;
  fieldName: string;
  question: string;
  disabled: boolean;
  onRun: (value: string) => void;
  onTopic: (value: Topic) => void;
  onRule: (value: string) => void;
  onField: (value: string) => void;
  onQuestion: (value: string) => void;
}) {
  return (
    <div className="assistant-compose">
      <label>
        {chrome.content}
        <select
          value={props.topic}
          disabled={props.disabled}
          onChange={(event) => props.onTopic(event.target.value as Topic)}
        >
          {(
            ["stage", "rule", "field", "proposal", "annotation"] as Topic[]
          ).map((topic) => (
            <option value={topic} key={topic}>
              {topicLabel(topic)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {chrome.formalStage}
        <select
          value={props.runId}
          disabled={props.disabled}
          onChange={(event) => props.onRun(event.target.value)}
        >
          <option value="">{chrome.unspecified}</option>
          {props.runs.map((run) => (
            <option value={run.id} key={run.id}>
              #{run.id} · {run.stage_status}
            </option>
          ))}
        </select>
      </label>
      {props.topic === "rule" ? (
        <label>
          {chrome.rule}
          <select
            value={props.ruleId}
            disabled={props.disabled}
            onChange={(event) => props.onRule(event.target.value)}
          >
            {rules.map((rule) => (
              <option key={rule}>{rule}</option>
            ))}
          </select>
        </label>
      ) : null}
      {props.topic === "field" ? (
        <label>
          {chrome.parameter}
          <select
            value={props.fieldName}
            disabled={props.disabled}
            onChange={(event) => props.onField(event.target.value)}
          >
            {fields.map((field) => (
              <option key={field}>{field}</option>
            ))}
          </select>
        </label>
      ) : null}
      <label>
        {chrome.question}
        <textarea
          value={props.question}
          disabled={props.disabled}
          maxLength={1000}
          rows={3}
          placeholder={chrome.questionPlaceholder}
          onChange={(event) => props.onQuestion(event.target.value)}
        />
      </label>
    </div>
  );
}
