import type { RetrievalProfile, SearchType } from "../types";

type RetrievalSettingsProps = {
  disabled: boolean;
  profile: RetrievalProfile | null;
  onChange: (profile: RetrievalProfile) => void;
};

const searchTypes: SearchType[] = ["similarity", "mmr", "hybrid"];

function RetrievalSettings({ disabled, profile, onChange }: RetrievalSettingsProps) {
  if (!profile) {
    return (
      <section className="panel">
        <div className="panel-head">
          <h2>检索设置</h2>
        </div>
        <p className="panel-note">加载中</p>
      </section>
    );
  }

  const fetchTooSmall = profile.fetch_k < profile.top_k;

  function patchProfile(patch: Partial<RetrievalProfile>) {
    if (!profile) return;
    const next = { ...profile, ...patch };
    if (patch.top_k !== undefined && next.fetch_k < patch.top_k) {
      next.fetch_k = patch.top_k;
    }
    onChange(next);
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>检索设置</h2>
      </div>

      <div className="field-stack">
        <label className="field">
          <span>Search</span>
          <select
            value={profile.search_type}
            disabled={disabled}
            onChange={(event) => patchProfile({ search_type: event.target.value as SearchType })}
          >
            {searchTypes.map((searchType) => (
              <option key={searchType} value={searchType}>
                {searchType}
              </option>
            ))}
          </select>
        </label>

        <div className="field-grid">
          <NumberField
            disabled={disabled}
            label="Top K"
            min={1}
            value={profile.top_k}
            onChange={(value) => patchProfile({ top_k: value })}
          />
          <NumberField
            disabled={disabled}
            label="Fetch K"
            min={1}
            value={profile.fetch_k}
            onChange={(value) => patchProfile({ fetch_k: value })}
          />
        </div>

        <NumberField
          disabled={disabled}
          label="Context chars"
          min={1}
          value={profile.max_context_chars}
          onChange={(value) => patchProfile({ max_context_chars: value })}
        />

        <label className="toggle-field">
          <input
            type="checkbox"
            checked={profile.reranker_enabled}
            disabled={disabled}
            onChange={(event) => patchProfile({ reranker_enabled: event.target.checked })}
          />
          <span>Reranker</span>
        </label>

        {fetchTooSmall && <p className="field-error">Fetch K 需要大于等于 Top K</p>}
      </div>
    </section>
  );
}

function NumberField({
  disabled,
  label,
  min,
  value,
  onChange,
}: {
  disabled: boolean;
  label: string;
  min: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Math.max(min, Number(event.target.value) || min))}
      />
    </label>
  );
}

export default RetrievalSettings;
