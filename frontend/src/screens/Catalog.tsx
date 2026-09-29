import { useEffect, useState } from "react";
import { api } from "../api";
import type { HistoryRecord, ScenarioCard } from "../types";
import { Card, Dots, PERSONA_LABELS, MODE_LABELS, STATUS_LABELS, SectionTitle, Tag } from "../ui";

/* Кроп сцены для арт-подложки карточки (4a); фолбэк — градиент из палитры
   сценария (данные, не код). */
function CardArt({ card }: { card: ScenarioCard }) {
  const [ok, setOk] = useState(true);
  return (
    <div className="relative h-[104px] w-full overflow-hidden rounded-t-btn"
         style={{ background: `linear-gradient(120deg, ${card.palette.from}, ${card.palette.to})` }}>
      {ok && (
        <img src={`/scenes/${card.id}.jpg`} onError={() => setOk(false)} alt=""
             className="h-full w-full object-cover" />
      )}
      <div className="absolute inset-0"
           style={{ background: "radial-gradient(120% 90% at 30% 10%, rgba(255,255,255,.35), transparent 60%)" }} />
    </div>
  );
}

function scoreTone(score: number): string {
  if (score >= 70) return "bg-accent-soft text-accent-deep";
  return "bg-[#f3e2c8] text-[#7a5408]";
}

export function Catalog({ onPick }: { onPick: (card: ScenarioCard) => void }) {
  const [cards, setCards] = useState<ScenarioCard[]>([]);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.scenarios().then(setCards).catch((e) => setError(String(e.message ?? e)));
    api.history().then(setHistory).catch(() => setHistory([]));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-7 max-w-3xl">
        {/* Шапка-бренд со счётчиками (эталон 4a) */}
        <div className="mb-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
          Тренажёр переговоров · {cards.length || "…"} сценария
          {history.length > 0 ? ` · ${history.length} парт. сыграно` : ""}
        </div>
        <h1 className="mb-2 text-[27px] font-bold leading-tight">Выберите сценарий</h1>
        <p className="text-sm font-light leading-relaxed text-ink-secondary">
          Разговор свободный — пишете, как сказали бы в жизни. Оппонент реагирует
          на приёмы, а не на ключевые слова: вопросы вскрывают скрытые интересы,
          аргументы двигают позицию, давление копит напряжение. После партии —
          разбор, где каждый балл объяснён конкретной репликой.
        </p>
      </div>

      {error && (
        <Card className="mb-6 border-critical/40">
          <p className="text-sm text-critical">Бэкенд недоступен: {error}</p>
          <p className="mt-1 text-sm text-ink-muted">
            Запустите: uvicorn app.main:app --port 8030 --app-dir backend
          </p>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <button
            key={card.id}
            type="button"
            onClick={() => onPick(card)}
            className="group overflow-hidden rounded-btn border border-line bg-surface text-left transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-card"
          >
            <CardArt card={card} />
            <div className="relative px-4 pb-4">
              <span aria-hidden
                    className="absolute -top-4 left-4 grid h-11 w-11 place-items-center rounded-full border-2 border-surface bg-fill text-base font-bold text-accent-deep shadow-tab">
                {card.opponent_name.trim().charAt(0).toUpperCase()}
              </span>
              <div className="pt-8">
                <Tag>{card.category}</Tag>
                <h2 className="mt-0.5 text-[14.5px] font-bold leading-snug group-hover:text-accent-deep">
                  {card.title}
                </h2>
                <p className="mt-1.5 min-h-[50px] text-[11.5px] leading-snug text-ink-secondary">
                  {card.summary}
                </p>
                <div className="mt-1 text-[11px] text-ink-secondary">
                  <b className="text-ink">{card.opponent_name}</b>{" "}
                  · {PERSONA_LABELS[card.persona]}
                </div>
                <div className="mt-2.5 flex items-center justify-between gap-2">
                  <Dots level={card.difficulty} />
                  <div className="flex flex-wrap justify-end gap-1">
                    {card.skills.slice(0, 2).map((skill) => (
                      <span key={skill}
                            className="rounded-full bg-fill px-2 py-0.5 text-[9.5px] text-ink-secondary">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      {history.length > 0 && (
        <div className="mt-10">
          <div className="mb-3 flex items-baseline justify-between">
            <SectionTitle>Прошлые партии</SectionTitle>
            {history.length > 6 && (
              <button type="button" onClick={() => setShowAll(!showAll)}
                      className="text-xs text-accent-deep underline hover:text-accent">
                {showAll ? "свернуть" : `все партии · ${history.length}`}
              </button>
            )}
          </div>
          <Card className="divide-y divide-linein p-0">
            {history.slice(0, showAll ? history.length : 6).map((record) => (
              <div
                key={record.session_id + record.finished_at}
                className="flex items-center justify-between gap-4 px-5 py-3"
              >
                <div className="flex min-w-0 items-baseline gap-3">
                  <span className="shrink-0 font-mono text-[10px] text-ink-muted">
                    {new Date(record.finished_at * 1000).toLocaleDateString("ru-RU",
                      { day: "2-digit", month: "2-digit" })}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] font-semibold">
                      {record.scenario_title}
                      <span className="ml-2 rounded-full bg-fill px-2 py-0.5 text-[9.5px] font-normal text-ink-secondary">
                        {MODE_LABELS[record.mode]?.name}
                      </span>
                    </div>
                    <div className="truncate text-[11.5px] text-ink-muted">
                      {STATUS_LABELS[record.status] ?? record.status}
                      {record.deal_text ? ` · ${record.deal_text}` : ""} · {record.turns} ходов
                    </div>
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <span className={`inline-block rounded-full px-2.5 py-1 font-mono text-[11px] font-bold ${scoreTone(record.overall.score)}`}>
                    {record.overall.score}
                  </span>
                  <div className="mt-0.5 text-[10px] text-ink-muted">{record.overall.grade}</div>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}
