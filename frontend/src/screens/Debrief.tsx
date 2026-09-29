import type { Debrief as DebriefData } from "../types";
import { Button, Card, SectionTitle, STATUS_LABELS, MODE_LABELS, Tag } from "../ui";
import { MoveChips } from "../components/Effects";
import { ZopaScale } from "../components/Zopa";

function CompetencyBars({ debrief }: { debrief: DebriefData }) {
  const weakest = Math.min(...debrief.competencies.map((c) => c.score));
  return (
    <div className="flex flex-col gap-4">
      {debrief.competencies.map((competency) => {
        const weak = competency.score === weakest && competency.score < 60;
        return (
          <div key={competency.id}>
            <div className="mb-1 flex items-baseline justify-between">
              <span className={`text-[13px] font-semibold ${weak ? "text-warntext" : ""}`}>
                {competency.name}
              </span>
              <span className="font-mono text-[13px] font-bold tabular-nums">
                {Math.round(competency.score / 5)}/20
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-[3px] bg-linein">
              <div
                className="bar-fill h-full rounded-[3px]"
                style={{
                  width: `${competency.score}%`,
                  background: weak ? "#d9a12b" : "#1f7a6f",
                }}
              />
            </div>
            <p className="mt-1 text-[11px] leading-snug text-ink-muted">
              {competency.comment}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function EffectRow({ meter, delta, reason }: {
  meter: string; delta: number; reason: string;
}) {
  const good = (meter === "trust" && delta > 0) || (meter === "tension" && delta < 0)
    || (meter === "aspiration" && delta < 0);
  const label = meter === "aspiration"
    ? (delta < 0 ? "позиция оппонента подвинулась" : "аппетит оппонента вырос")
    : meter === "trust" ? "доверие" : meter === "tension" ? "напряжение" : "терпение";
  return (
    <li className="flex items-start gap-2 text-xs leading-snug">
      <span
        aria-hidden
        className={`mt-px grid h-[18px] w-[18px] shrink-0 place-items-center rounded font-mono text-[10px] font-bold ${
          good ? "bg-accent-soft text-accent-deep" : "bg-[#f7dcd7] text-critical"
        }`}
      >
        {good ? "+" : "−"}
      </span>
      <span className="text-ink-secondary">
        <b>{label}</b>{meter !== "aspiration" && (
          <b className="font-mono tabular-nums">{" "}{delta > 0 ? "+" : ""}{Math.round(delta)}</b>
        )} — {reason}
      </span>
    </li>
  );
}

function exportTranscript(debrief: DebriefData) {
  const lines: string[] = [
    `${debrief.scenario.title} · ${MODE_LABELS[debrief.mode]?.name}`,
    `Итог: ${STATUS_LABELS[debrief.status]}${debrief.deal_text ? ` — ${debrief.deal_text}` : ""}`,
    `Счёт: ${debrief.overall.score} · ${debrief.overall.grade}`,
    "",
    `${debrief.scenario.opponent_name}: ${debrief.opening}`,
  ];
  for (const turn of debrief.transcript) {
    if (turn.kind === "action") {
      lines.push(`— ${turn.narrative}`);
      if (turn.npc_text) lines.push(`${debrief.scenario.opponent_name}: ${turn.npc_text}`);
      continue;
    }
    lines.push(`Вы: ${turn.player_text}`);
    if (turn.npc_text) lines.push(`${debrief.scenario.opponent_name}: ${turn.npc_text}`);
  }
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `переговоры-${debrief.scenario.id}.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

const fmtClock = (s: number | null | undefined) =>
  typeof s === "number"
    ? `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`
    : "—";

export function Debrief({ debrief, onReplay, onCatalog }: {
  debrief: DebriefData;
  onReplay: () => void;
  onCatalog: () => void;
}) {
  const economics = debrief.economics;
  const vsBatna = economics.vs_batna;
  const meters = debrief.transcript.filter((t) => t.kind !== "action").map((t) => t.meters);
  const lastMeters = meters.at(-1);
  const peakTension = Math.max(20, ...meters.map((m) => m.tension));

  return (
    <div className="mx-auto max-w-4xl px-6 py-8 font-sans">
      {/* Шапка (4i): назад + контекст партии */}
      <div className="mb-4 flex items-baseline justify-between">
        <button type="button" onClick={onCatalog}
                className="text-sm text-ink-muted hover:text-ink">
          ← Каталог
        </button>
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
          {debrief.scenario.title} · {MODE_LABELS[debrief.mode]?.name} ·{" "}
          {fmtClock(debrief.duration_seconds)}
          {debrief.finished_at
            ? ` · ${new Date(debrief.finished_at * 1000).toLocaleDateString("ru-RU",
                { day: "2-digit", month: "short" })}`
            : ""}
        </span>
      </div>

      {/* Герой-карта (4i) */}
      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-6">
          <div className="text-center">
            <div className="font-mono text-[58px] font-bold leading-none tracking-tight text-accent-deep">
              {debrief.overall.score}
            </div>
            <span className="mt-1.5 inline-block rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-semibold text-accent-deep">
              {debrief.overall.grade}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-lg font-bold">
              {STATUS_LABELS[debrief.status]}
              {debrief.deal_text ? `: ${debrief.deal_text}` : ""}
            </div>
            <div className="mt-1 text-sm text-ink-secondary">
              {debrief.scenario.title} · {MODE_LABELS[debrief.mode]?.name}
            </div>
            <div className="mt-2 flex flex-wrap gap-4 font-mono text-[11px] text-ink-secondary">
              <span>доверие · {lastMeters?.trust ?? "—"}</span>
              <span>пик напряж. · {Math.round(peakTension)}</span>
              <span>ходов · {debrief.transcript.filter((t) => t.kind !== "action").length}</span>
              <span>{fmtClock(debrief.duration_seconds)}</span>
            </div>
            <div className="mt-1 text-[11px] text-ink-muted">
              {debrief.llm_used
                ? "Часть реплик оппонента озвучена моделью"
                : "Реплики оппонента в этой партии — авторские (сценарий)"}
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={onReplay}>Сыграть ещё раз</Button>
            <Button kind="ghost" onClick={onCatalog}>В каталог</Button>
          </div>
        </div>
      </Card>

      <div className="mb-5 grid gap-5 md:grid-cols-[1.25fr_1fr]">
        <Card>
          <SectionTitle>Компетенции</SectionTitle>
          <CompetencyBars debrief={debrief} />
        </Card>

        <div className="flex flex-col gap-5">
          <Card>
            <SectionTitle>Экономика сделки</SectionTitle>
            {debrief.deal ? (
              <>
                <ZopaScale debrief={debrief} />
                {/* Якоря партии (4i): старт оппонента · итог · ваш якорь */}
                <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[9.5px] text-ink-muted">
                  {typeof economics.opponent_first_offer === "number" && (
                    <span>
                      {economics.opponent_first_offer} · старт{" "}
                      {debrief.scenario.opponent_name.split(" ")[0]}
                    </span>
                  )}
                  {(() => {
                    const dealMain = Object.values(debrief.deal ?? {})
                      .find((v) => typeof v === "number");
                    return typeof dealMain === "number"
                      ? <span className="text-accent-deep">{dealMain} · итог</span>
                      : null;
                  })()}
                  {typeof economics.player_anchor === "number" && (
                    <span>{economics.player_anchor} · ваш якорь</span>
                  )}
                </div>
                {typeof vsBatna === "number" && (
                  <p className="mt-3 text-sm">
                    Против вашей альтернативы:{" "}
                    <b className={`font-mono tabular-nums ${vsBatna >= 0 ? "text-goodtext" : "text-critical"}`}>
                      {vsBatna >= 0 ? "+" : ""}{vsBatna} б.
                    </b>
                  </p>
                )}
                {economics.left_on_table && economics.left_on_table.points > 0 && (
                  <p className="mt-2 text-sm text-ink-secondary">
                    Осталось на столе{" "}
                    <b className="font-mono tabular-nums">{economics.left_on_table.points} б.</b> —
                    достижимый пакет: {economics.left_on_table.package}
                  </p>
                )}
                {economics.left_on_table && economics.left_on_table.points === 0 && (
                  <p className="mt-2 text-sm text-goodtext">
                    Пакет на Парето-границе: улучшить его, не ухудшая оппоненту, нельзя.
                  </p>
                )}
              </>
            ) : (
              <div className="text-sm text-ink-secondary">
                <p>Сделки нет. Ценность исхода — ваша альтернатива:{" "}
                  <b className="font-mono tabular-nums">{economics.batna} б.</b></p>
                {economics.best_offer_seen && (
                  <p className="mt-2">
                    Лучшее, что лежало на столе: {economics.best_offer_seen}{" "}
                    (<span className="font-mono tabular-nums">{economics.best_offer_utility} б.</span>)
                  </p>
                )}
              </div>
            )}
          </Card>

          <Card>
            <SectionTitle>Ключевые моменты</SectionTitle>
            <ol className="flex flex-col gap-2.5">
              {debrief.moments.map((moment, index) => {
                const negative = /вырос|обострение|слаб/i.test(moment.title);
                return (
                  <li key={index} className="flex gap-2.5 text-sm">
                    <span className="mt-0.5 shrink-0 font-mono text-[10px] text-ink-muted">
                      {typeof moment.at_seconds === "number"
                        ? fmtClock(moment.at_seconds) : `х.${moment.turn}`}
                    </span>
                    <span aria-hidden
                          className={`mt-px grid h-[18px] w-[18px] shrink-0 place-items-center rounded font-mono text-[10px] font-bold ${
                            negative ? "bg-[#f7dcd7] text-critical" : "bg-accent-soft text-accent-deep"
                          }`}>
                      {negative ? "−" : "+"}
                    </span>
                    <span>
                      <b>{moment.title}.</b>{" "}
                      <span className="text-ink-secondary">{moment.text}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
          </Card>
        </div>
      </div>

      {debrief.recommendations.length > 0 && (
        <Card className="mb-5">
          <SectionTitle>Что сделать в следующий раз</SectionTitle>
          <ol className="flex flex-col gap-3">
            {debrief.recommendations.map((recommendation, index) => (
              <li key={index} className="text-sm font-light leading-relaxed text-ink-secondary">
                <Tag>{recommendation.tag}</Tag>
                <span className="ml-2">{recommendation.text}</span>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-baseline gap-2.5">
            <SectionTitle>Стенограмма с разбором</SectionTitle>
            <span className="font-mono text-[9.5px] text-ink-muted">
              {debrief.transcript.filter((t) => t.kind !== "action").length} ходов ·
              ремарки действий · время ответа
            </span>
          </div>
          <button type="button" onClick={() => exportTranscript(debrief)}
                  className="text-xs text-accent-deep underline hover:text-accent">
            экспорт .txt
          </button>
        </div>
        <div className="mb-4 flex items-start gap-2.5">
          <span aria-hidden
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-fill text-[12px] font-bold text-accent-deep">
            {debrief.scenario.opponent_name.trim().charAt(0).toUpperCase()}
          </span>
          <div className="rounded-card rounded-tl border border-line bg-page px-4 py-2 text-sm">
            {debrief.opening}
          </div>
        </div>
        <div className="flex flex-col gap-5">
          {debrief.transcript.map((turn, index) => turn.kind === "action" ? (
            <div key={`${turn.n}-a${index}`} className="border-l-2 border-linein pl-4">
              <p className="text-sm italic text-ink-muted">{turn.narrative}</p>
              {turn.npc_text && (
                <p className="mt-0.5 text-sm text-ink-secondary">— {turn.npc_text}</p>
              )}
              {turn.effects.length > 0 && (
                <ul className="mt-1.5 flex flex-col gap-1">
                  {turn.effects
                    .filter((effect) => effect.meter !== "patience")
                    .map((effect, effectIndex) => (
                      <EffectRow key={effectIndex} {...effect} />
                    ))}
                </ul>
              )}
            </div>
          ) : (
            <div key={`${turn.n}-t${index}`} className="border-l-2 border-linein pl-4">
              <div className="mb-1 flex items-baseline gap-2 font-mono text-[9.5px] uppercase tracking-[0.12em] text-ink-muted">
                {typeof turn.at_seconds === "number"
                  ? fmtClock(turn.at_seconds) : `ход ${turn.n}`}
                <span className="normal-case tracking-normal">· ход {turn.n}</span>
                {debrief.mode === "free" && typeof turn.thinking_seconds === "number" && (
                  <span className="normal-case tracking-normal">
                    · ответ за {turn.thinking_seconds} с
                  </span>
                )}
              </div>
              <div className="mb-1 rounded-card bg-fill px-3 py-2 text-sm">
                <b className="mr-1.5 text-accent-deep">Вы:</b>{turn.player_text}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <MoveChips moves={turn.moves} />
              </div>
              {turn.effects.length > 0 && (
                <ul className="mt-2 flex flex-col gap-1">
                  {turn.effects
                    .filter((effect) => effect.meter !== "patience")
                    .map((effect, effectIndex) => (
                      <EffectRow key={effectIndex} {...effect} />
                    ))}
                </ul>
              )}
              {turn.event && (
                <div className="mt-2 rounded-card border px-3 py-2 text-xs text-ink-secondary"
                     style={{ background: "rgba(253,244,222,.97)", borderColor: "rgba(217,161,43,.6)" }}>
                  <b className="text-warntext">{turn.event.title}.</b> {turn.event.text}
                </div>
              )}
              {turn.npc_text && (
                <div className="mt-2 rounded-card border border-line bg-surface px-3 py-2 text-sm">
                  <b className="mr-1.5">{debrief.scenario.opponent_name}:</b>{turn.npc_text}
                </div>
              )}
              {turn.npc_note && (
                <div className="mt-1 text-xs italic text-ink-muted">
                  Почему так: {turn.npc_note}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
