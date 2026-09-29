import { useState } from "react";
import type { Brief, Mode, ScenarioCard, StartPayload } from "../types";
import { api } from "../api";
import { Button, MODE_LABELS, PERSONA_LABELS, Tag } from "../ui";

/* Фича-теги режим-карт (эталон 4b): у выбранной — «выбран». */
const MODE_TAGS: Record<Mode, string> = {
  training: "подсказки", free: "таймер", exam: "без подсказок",
};

/* Портрет-карта (4b): кроп calm-спрайта, фолбэк — палитра сцены + монограмма. */
function PortraitCard({ card }: { card: ScenarioCard }) {
  const [ok, setOk] = useState(true);
  return (
    <div className="w-[330px] shrink-0 overflow-hidden rounded-card border border-line bg-surface shadow-card">
      <div className="relative grid h-[412px] place-items-center overflow-hidden"
           style={{ background: `linear-gradient(160deg, ${card.palette.from}, ${card.palette.to})` }}>
        {ok ? (
          <img src={`/sprites/${card.id}/calm.png`} onError={() => setOk(false)}
               alt="" className="h-full w-full object-cover object-top" />
        ) : (
          <span aria-hidden
                className="grid h-40 w-40 place-items-center rounded-full bg-surface/80 text-7xl font-bold text-accent-deep shadow-card">
            {card.opponent_name.trim().charAt(0).toUpperCase()}
          </span>
        )}
      </div>
      <div className="px-4 py-3">
        <div className="text-[13px] font-bold">{card.opponent_name}</div>
        <div className="text-[11.5px] text-ink-secondary">
          {card.opponent_role} · {PERSONA_LABELS[card.persona]}
        </div>
      </div>
    </div>
  );
}

export function Briefing({ card, llmEnabled, onStart, onBack }: {
  card: ScenarioCard;
  llmEnabled: boolean;
  onStart: (payload: StartPayload) => void;
  onBack: () => void;
}) {
  const [mode, setMode] = useState<Mode>("training");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [prep, setPrep] = useState<(Brief & { setting: string }) | null>(null);
  const [prepOpen, setPrepOpen] = useState(false);

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      onStart(await api.start(card.id, mode, true));
    } catch (e) {
      setError(String((e as Error).message ?? e));
      setBusy(false);
    }
  };

  const togglePrep = async () => {
    if (prepOpen) {
      setPrepOpen(false);
      return;
    }
    if (!prep) {
      try {
        setPrep(await api.scenarioBrief(card.id));
      } catch (e) {
        setError(String((e as Error).message ?? e));
        return;
      }
    }
    setPrepOpen(true);
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <button
        type="button"
        onClick={onBack}
        className="mb-5 text-sm text-ink-muted hover:text-ink"
      >
        ← к каталогу
      </button>

      <div className="flex flex-col gap-6 md:flex-row">
        <PortraitCard card={card} />

        <div className="min-w-0 max-w-[660px] flex-1">
          <div className="flex items-center gap-3">
            <Tag>{card.category}</Tag>
            <Tag tone="muted">сложность {card.difficulty} из 4</Tag>
          </div>
          <h1 className="mt-1 text-[27px] font-bold leading-tight">{card.title}</h1>
          <p className="mt-2 text-[13px] font-light leading-[1.65] text-ink-secondary">
            {card.summary}
          </p>

          {/* Мини-карты ЦЕЛЬ / МИНИМУМ / ВРЕМЯ (эталон 4b) */}
          <div className="mt-4 grid grid-cols-3 gap-2.5">
            <MiniCard label="цель">
              <span className="font-mono text-[15px] font-bold">
                {card.goal_value}
              </span>{" "}{card.unit}
            </MiniCard>
            <MiniCard label="минимум">
              <span className="font-mono text-[15px] font-bold">
                {card.limit_value}
              </span>{" "}{card.unit}
            </MiniCard>
            <MiniCard label="время">
              <span className="font-mono text-[15px] font-bold">
                ≈ {card.est_minutes}
              </span>{" "}мин · до {card.max_turns} ходов
            </MiniCard>
          </div>

          <div className="mt-5">
            <Tag tone="muted">режим</Tag>
            <div className="mt-1.5 grid gap-2.5 sm:grid-cols-3">
              {(Object.keys(MODE_LABELS) as Mode[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setMode(key)}
                  className={`rounded-btn border p-3 text-left transition-colors ${
                    mode === key
                      ? "border-[1.5px] border-accent bg-accent-tint"
                      : "border-line bg-surface hover:border-ink-muted"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-bold">{MODE_LABELS[key].name}</span>
                    <Tag tone={mode === key ? "accent" : "muted"}>
                      {mode === key ? "выбран" : MODE_TAGS[key]}
                    </Tag>
                  </div>
                  <div className="mt-0.5 text-[11px] leading-snug text-ink-secondary">
                    {MODE_LABELS[key].hint}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {!llmEnabled && (
            <p className="mt-4 text-sm text-ink-muted">
              LLM не подключена — оппонент говорит репликами сценария,
              распознавание приёмов возьмут эвристики. Механика та же.
            </p>
          )}
          {error && <p className="mt-4 text-sm text-critical">{error}</p>}

          <div className="mt-5 flex gap-2.5">
            <Button size="lg" onClick={start} disabled={busy}>
              {busy ? "Готовим встречу…" : "Начать переговоры"}
            </Button>
            <Button size="lg" kind="ghost" onClick={() => void togglePrep()}>
              Карта подготовки
            </Button>
          </div>

          {prepOpen && prep && (
            <div className="rise-in mt-4 flex flex-col gap-3 rounded-card border border-line bg-surface p-4 text-sm">
              <div>
                <Tag>цель</Tag>
                <div className="mt-0.5 text-ink-secondary">{prep.goal}</div>
              </div>
              <div className="border-t border-linein pt-3">
                <Tag>альтернатива · batna</Tag>
                <div className="mt-0.5 text-ink-secondary">{prep.batna}</div>
              </div>
              <div className="border-t border-linein pt-3">
                <Tag>ваши козыри</Tag>
                <ul className="mt-1 list-inside list-disc text-ink-secondary">
                  {prep.facts.map((fact) => <li key={fact}>{fact}</li>)}
                </ul>
              </div>
              {prep.criteria.length > 0 && (
                <div className="border-t border-linein pt-3">
                  <Tag>объективные критерии</Tag>
                  <ul className="mt-1 list-inside list-disc text-ink-secondary">
                    {prep.criteria.map((c) => <li key={c}>{c}</li>)}
                  </ul>
                </div>
              )}
              <div className="border-t border-linein pt-3">
                <Tag tone="critical">красные линии</Tag>
                <ul className="mt-1 flex flex-col gap-1 text-ink-secondary">
                  {prep.issues.map((issue) => (
                    <li key={issue.id}>
                      {issue.kind === "numeric" ? (
                        <>
                          {issue.name}: цель{" "}
                          <b className="font-mono tabular-nums">{issue.player_target}</b>
                          {issue.unit ? ` ${issue.unit}` : ""}, предел{" "}
                          <b className="font-mono tabular-nums">{issue.player_limit}</b>
                        </>
                      ) : issue.name}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MiniCard({ label, children }: {
  label: string; children: React.ReactNode;
}) {
  return (
    <div className="rounded-btn border border-line bg-surface p-2.5">
      <Tag tone="muted">{label}</Tag>
      <div className="mt-0.5 text-[11.5px] leading-snug text-ink">{children}</div>
    </div>
  );
}
