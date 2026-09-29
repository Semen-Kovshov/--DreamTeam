import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type {
  ActionStatus, EffectItem, Hint, Meters, Mood, MoveChip, StartPayload,
} from "../types";
import { Button, SectionTitle, STATUS_LABELS, Tag } from "../ui";
import { MetersPanel, type MeterDeltas } from "../components/Meters";
import { EffectChips, MoveChips } from "../components/Effects";

const fmtClock = (s: number) =>
  `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/* Монограмма вместо эмодзи-аватара — как в эталонах 4a/4c. */
const monogram = (name: string) => name.trim().charAt(0).toUpperCase();

/* Подложка сцены — фолбэк, пока нет /scenes/<id>.jpg (контракт §09).
   Тона приходят из данных сценария (palette), не из кода. */
const sceneTint = (palette: { from: string; to: string }) =>
  `linear-gradient(160deg, ${palette.from} 0%, ${palette.to} 100%)`;

/* Нейтральные формы: имя может быть любого рода (§04). */
const MOOD_LABEL: Record<Mood, string> = {
  calm: "спокойное", pleased: "доброе", tense: "напряжённое", angry: "на взводе",
};
const MOOD_COLOR: Record<Mood, string> = {
  calm: "#898781", pleased: "#5f9c53", tense: "#d97a3f", angry: "#c04b3c",
};

interface LogItem {
  kind: "npc" | "player" | "event" | "action";
  text: string;
  ts?: string;               // mm:ss от начала партии (эталон 4f)
  title?: string;
  source?: "llm" | "template";
  moves?: MoveChip[];
  effects?: EffectItem[];
  narrative?: string;
  thinking?: number | null;
}

function diffMeters(prev: Meters, next: Meters): MeterDeltas {
  const diff = (a: number | null, b: number | null) =>
    typeof a === "number" && typeof b === "number" ? b - a : undefined;
  return {
    trust: diff(prev.trust, next.trust),
    tension: diff(prev.tension, next.tension),
    patience: diff(prev.patience, next.patience),
  };
}

function useTypewriter(text: string) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    setCount(0);
    if (!text) return;
    const interval = setInterval(() => {
      setCount((current) => {
        if (current >= text.length) {
          clearInterval(interval);
          return current;
        }
        return current + 2;
      });
    }, 16);
    return () => clearInterval(interval);
  }, [text]);
  return {
    shown: text.slice(0, count),
    done: count >= text.length,
    skip: () => setCount(text.length),
  };
}

function Sprite({ scenarioId, name, mood }: {
  scenarioId: string; name: string; mood: Mood;
}) {
  const [imgOk, setImgOk] = useState(true);
  useEffect(() => setImgOk(true), [scenarioId]);
  return (
    <div key={mood} className={`sprite-in ${mood === "angry" ? "sprite-shake" : ""}`}>
      <div className="sprite-breathe flex flex-col items-center">
        {imgOk ? (
          <img
            src={`/sprites/${scenarioId}/${mood}.png`}
            onError={() => setImgOk(false)}
            alt=""
            className="pointer-events-none h-[30vh] max-h-[280px] object-contain md:h-[46vh] md:max-h-[440px]"
          />
        ) : (
          <span
            aria-hidden
            className="grid h-44 w-44 place-items-center rounded-full bg-surface/75 text-7xl font-bold text-accent-deep shadow-card ring-4 backdrop-blur"
            style={{ ["--tw-ring-color" as string]: MOOD_COLOR[mood] + "66" }}
          >
            {monogram(name)}
          </span>
        )}
      </div>
      <div className="sprite-shadow mx-auto -mt-2" aria-hidden />
    </div>
  );
}

export function Game({ start, onDebrief, onCatalog }: {
  start: StartPayload;
  onDebrief: (sessionId: string) => void;
  onCatalog: () => void;
}) {
  const [items, setItems] = useState<LogItem[]>([
    { kind: "npc", text: start.opening, ts: "0:00" },
  ]);
  const [npcLine, setNpcLine] = useState<{ text: string; source?: string }>(
    { text: start.opening });
  const [narrative, setNarrative] = useState("");
  const [lastEcho, setLastEcho] = useState<LogItem | null>(null);
  const [mood, setMood] = useState<Mood>(start.npc_mood);
  const [meters, setMeters] = useState<Meters>(start.meters);
  const [deltas, setDeltas] = useState<MeterDeltas>({});
  const [onTable, setOnTable] = useState<string | null>(null);
  const [onTableValue, setOnTableValue] = useState<number | null>(null);
  const [status, setStatus] = useState<string>("active");
  const [dealText, setDealText] = useState<string | null>(null);
  const [dealValue, setDealValue] = useState<number | null>(null);
  const [actions, setActions] = useState<ActionStatus[]>(start.actions);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [error, setError] = useState("");
  const [hints, setHints] = useState<Hint[]>([]);
  const [hintsOpen, setHintsOpen] = useState(start.mode !== "exam");
  const [panel, setPanel] = useState<"none" | "log" | "brief">("none");
  const [event, setEvent] = useState<{ title: string; text: string } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [clock, setClock] = useState(0);
  const [busySeconds, setBusySeconds] = useState(0);
  const [turnCount, setTurnCount] = useState(0);
  const replyAt = useRef(Date.now());
  const startAt = useRef(Date.now());
  const busyAt = useRef(Date.now());
  const prevMeters = useRef<Meters>(start.meters);
  const firstOffer = useRef<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const exam = start.mode === "exam";
  const writer = useTypewriter(npcLine.text);
  const now = () => fmtClock(Math.floor((Date.now() - startAt.current) / 1000));

  /* Обучение — готовые реплики, свободный — советы-направления (эталон 3a). */
  const refreshHints = useCallback(() => {
    if (exam) return;
    api.hints(start.session_id).then((r) => setHints(r.hints)).catch(() => {});
  }, [exam, start.session_id]);
  useEffect(refreshHints, [refreshHints]);

  /* Один секундный тик: часы партии, таймер хода, счётчик генерации. */
  useEffect(() => {
    if (status !== "active") return;
    const interval = setInterval(() => {
      setClock(Math.floor((Date.now() - startAt.current) / 1000));
      if (start.timed) {
        setElapsed(Math.floor((Date.now() - replyAt.current) / 1000));
      }
      setBusySeconds(Math.floor((Date.now() - busyAt.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [start.timed, status]);

  useEffect(() => {
    if (panel === "log") logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [panel, items]);

  const resetClock = () => {
    replyAt.current = Date.now();
    setElapsed(0);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy || status !== "active") return;
    setInput("");
    setError("");
    setBusy(true);
    setNarrative("");
    // Сервер сбрасывает лимит «жестов между репликами» сразу при приёме хода —
    // снимаем эту блокировку оптимистично, чтобы лоток жил во время ожидания
    // (§06: «действия-мелочи доступны»). Кулдауны по ходам не трогаем.
    setActions((prev) => prev.map((a) =>
      a.reason === "сначала скажите что-нибудь"
        ? { ...a, available: true, reason: "" } : a));
    busyAt.current = Date.now();
    setBusySeconds(0);
    const sentAt = now();
    setItems((prev) => [...prev, { kind: "player", text, ts: sentAt }]);
    try {
      const payload = await api.turn(start.session_id, text);
      const echo: LogItem = {
        kind: "player", text, ts: sentAt,
        moves: payload.moves, effects: payload.effects,
        thinking: payload.thinking_seconds,
      };
      setLastEcho(echo);
      setItems((prev) => {
        const next = [...prev];
        next[next.length - 1] = echo;
        if (payload.event) {
          next.push({ kind: "event", title: payload.event.title, text: payload.event.text });
        }
        next.push({ kind: "npc", text: payload.npc_text,
                    source: payload.npc_source, ts: now() });
        return next;
      });
      setNpcLine({ text: payload.npc_text, source: payload.npc_source });
      setMood(payload.npc_mood);
      setDeltas(diffMeters(prevMeters.current, payload.meters));
      prevMeters.current = payload.meters;
      setMeters(payload.meters);
      setOnTable(payload.on_table ?? null);
      if (typeof payload.on_table_value === "number") {
        setOnTableValue(payload.on_table_value);
        if (firstOffer.current === null) firstOffer.current = payload.on_table_value;
      }
      setActions(payload.actions);
      setStatus(payload.status);
      setDealText(payload.deal_text ?? null);
      if (typeof payload.deal_value === "number") setDealValue(payload.deal_value);
      setEvent(payload.event);
      setTurnCount(payload.turn);
      refreshHints();
      resetClock();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  /* Лоток активен и во время ожидания ответа (§06). */
  const doAction = async (actionId: string) => {
    if (actionBusy || status !== "active") return;
    setActionBusy(true);
    setError("");
    try {
      const payload = await api.action(start.session_id, actionId);
      setNarrative(payload.narrative);
      if (payload.npc_text && !busy) {
        setNpcLine({ text: payload.npc_text, source: "template" });
      }
      setItems((prev) => [...prev,
        { kind: "action", text: payload.npc_text, narrative: payload.narrative,
          effects: payload.effects, ts: now() },
      ]);
      setMood(payload.npc_mood);
      setDeltas(diffMeters(prevMeters.current, payload.meters));
      prevMeters.current = payload.meters;
      setMeters(payload.meters);
      setActions(payload.actions);
      resetClock();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setActionBusy(false);
    }
  };

  const finish = async (action: "accept" | "leave") => {
    if (busy) return;
    setBusy(true);
    try {
      await api.finish(start.session_id, action);
      onDebrief(start.session_id);
    } catch (e) {
      setError(String((e as Error).message ?? e));
      setBusy(false);
    }
  };

  const timerStage = elapsed >= start.think_hard ? "crit"
    : elapsed >= start.think_soft ? "hot" : "calm";
  const timerStyles = {
    calm: "border-line bg-white text-ink-secondary",
    hot: "border-serious/55 bg-serious/10 text-[#a8551f]",
    crit: "border-critical/60 bg-critical/10 text-[#8f2f24]",
  } as const;

  return (
    <div className="relative h-[calc(100vh-57px)] overflow-hidden font-sans">
      {/* Сцена */}
      <div
        className="absolute inset-0"
        style={{ background: sceneTint(start.scenario.palette) }}
      />
      <SceneImage scenarioId={start.scenario.id} />
      <div className="vignette pointer-events-none absolute inset-0" />

      {/* Персонаж: низ уходит за верхнюю кромку VN-окна (§05) */}
      <div className="absolute inset-x-0 bottom-[196px] flex justify-center">
        <Sprite scenarioId={start.scenario.id} name={start.scenario.opponent_name}
                mood={mood} />
      </div>

      {/* Мобильная шапка (ТЗ: мобильный сценарий приоритетен): позиция,
          настроение, стол и табы — компактной полосой вместо боковых HUD */}
      <div className="absolute inset-x-0 top-0 z-[5] border-b border-line bg-surface/95 px-3 py-2 backdrop-blur md:hidden">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <span aria-hidden
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-fill text-[12px] font-bold text-accent-deep ring-2 ring-accent-soft">
              {monogram(start.scenario.opponent_name)}
            </span>
            <span className="truncate text-[12.5px] font-bold">
              {start.scenario.opponent_name}
            </span>
            {!exam && (
              <span aria-hidden className="h-[7px] w-[7px] shrink-0 rounded-full"
                    style={{ background: MOOD_COLOR[mood] }} />
            )}
          </div>
          <div className="flex shrink-0 gap-1">
            <TabButton active={panel === "log"} onClick={() => setPanel(panel === "log" ? "none" : "log")}>
              Журнал
            </TabButton>
            <TabButton active={panel === "brief"} onClick={() => setPanel(panel === "brief" ? "none" : "brief")}>
              Бриф
            </TabButton>
            {!exam && (
              <TabButton active={hintsOpen} onClick={() => setHintsOpen(!hintsOpen)}>
                Советы
              </TabButton>
            )}
          </div>
        </div>
        <div className="mt-1.5 flex items-center gap-3">
          {exam ? (
            <span className="flex-1 text-[10.5px] italic text-ink-muted">
              экзамен · индикаторы скрыты до разбора
            </span>
          ) : (
            <div className="flex flex-1 gap-2.5">
              <MiniMeter label="Дов" value={meters.trust} max={100} tone="#1f7a6f" />
              <MiniMeter label="Напр" value={meters.tension} max={100} tone="#d9a12b" />
              <MiniMeter label="Терп" value={meters.patience} max={start.max_turns}
                         tone="#5f9c53" />
            </div>
          )}
          <div className="flex shrink-0 items-center gap-1.5">
            {onTable && (
              <span className="max-w-[110px] truncate text-[11px] font-bold">
                {onTable}
              </span>
            )}
            <Button size="sm" onClick={() => void finish("accept")}
                    disabled={!onTable || status !== "active" || busy}>
              Принять
            </Button>
            <Button size="sm" kind="danger" onClick={() => void finish("leave")}
                    disabled={status !== "active" || busy}>
              Выйти
            </Button>
          </div>
        </div>
      </div>

      {/* HUD слева 248 (§05): «Позиция» с часами партии и дельтами (3a) */}
      <div className="absolute left-[18px] top-[18px] hidden w-[248px] flex-col gap-2.5 md:flex">
        <div className="rounded-card border border-line bg-surface/95 p-3.5 shadow-card backdrop-blur">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-ink-muted">
              Позиция
            </span>
            <span className="font-mono text-[10px] text-ink-muted">
              {clock >= 60 ? `${Math.floor(clock / 60)} мин` : `${clock} с`}
            </span>
          </div>
          <MetersPanel meters={meters} maxTurns={start.max_turns} hidden={exam}
                       deltas={exam ? undefined : deltas} />
        </div>
        <div className="rounded-card border border-line bg-surface/95 p-3.5 shadow-card backdrop-blur">
          <SectionTitle>На столе</SectionTitle>
          {onTable ? (
            <>
              <p className="text-[19px] font-bold leading-snug">{onTable}</p>
              <p className="mb-1.5 font-mono text-[9.5px] text-ink-muted">
                оффер · {start.scenario.opponent_name}
              </p>
              {onTableValue !== null && firstOffer.current !== null &&
                firstOffer.current !== start.scenario.goal_value && (
                <div className="mb-2">
                  <div className="h-1.5 overflow-hidden rounded-[3px] bg-linein">
                    <div
                      className="bar-fill h-full rounded-[3px] bg-accent-soft"
                      style={{ width: `${Math.max(0, Math.min(1,
                        (onTableValue - firstOffer.current) /
                        (start.scenario.goal_value - firstOffer.current))) * 100}%` }}
                    />
                  </div>
                  <div className="mt-1 flex justify-between font-mono text-[9.5px] text-ink-muted">
                    <span>{onTableValue}</span>
                    <span>ваш запрос · {start.scenario.goal_value}</span>
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="mb-2.5 text-sm text-ink-muted">Предложения ещё нет.</p>
          )}
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" onClick={() => void finish("accept")}
                    disabled={!onTable || status !== "active" || busy}>
              Принять
            </Button>
            <Button size="sm" kind="danger" onClick={() => void finish("leave")}
                    disabled={status !== "active" || busy}>
              Выйти
            </Button>
          </div>
        </div>
      </div>

      {/* HUD справа 252 (§05) */}
      <div className="absolute right-[18px] top-[18px] hidden w-[252px] flex-col gap-2.5 md:flex">
        <div className="flex items-center gap-2.5 rounded-card border border-line bg-surface/95 p-3 shadow-card backdrop-blur">
          <span aria-hidden
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-fill text-[15px] font-bold text-accent-deep ring-2 ring-accent-soft">
            {monogram(start.scenario.opponent_name)}
          </span>
          <div className="min-w-0">
            <div className="truncate text-[13px] font-bold">
              {start.scenario.opponent_name}
            </div>
            <div className="truncate text-[11px] text-ink-secondary">
              {start.scenario.opponent_role}
            </div>
            <div className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-fill px-2 py-0.5">
              {exam ? (
                <>
                  <span aria-hidden className="h-[7px] w-[7px] rounded-full border-[1.5px] border-[#b9b7b0]" />
                  <span className="text-[11px] italic text-ink-muted">настроение скрыто</span>
                </>
              ) : (
                <>
                  <span aria-hidden className="h-[7px] w-[7px] rounded-full"
                        style={{ background: MOOD_COLOR[mood] }} />
                  <span className="text-[11px] text-ink-secondary">{MOOD_LABEL[mood]}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Сегмент-табы */}
        <div className="flex gap-1 rounded-btn border border-line bg-surface/95 p-1 shadow-card backdrop-blur">
          <TabButton active={panel === "log"} onClick={() => setPanel(panel === "log" ? "none" : "log")}>
            Журнал
          </TabButton>
          <TabButton active={panel === "brief"} onClick={() => setPanel(panel === "brief" ? "none" : "brief")}>
            Бриф
          </TabButton>
          {!exam && (
            <TabButton active={hintsOpen} onClick={() => setHintsOpen(!hintsOpen)}>
              Подсказки
            </TabButton>
          )}
        </div>

        {/* Карточка подсказок (§04): обучение — готовые реплики (клик
            подставляет), свободный — советы-направления (3a/4c) */}
        {!exam && hintsOpen && hints.length > 0 && status === "active" && (
          <HintsCard hints={hints} onPick={setInput} />
        )}
      </div>

      {/* Подсказки на мобиле — поверх сцены, над диалоговым окном */}
      {!exam && hintsOpen && hints.length > 0 && status === "active" && (
        <div className="absolute inset-x-3 bottom-[236px] z-20 md:hidden">
          <HintsCard hints={hints} onPick={(text) => { setInput(text); setHintsOpen(false); }} />
        </div>
      )}

      {/* Событие (§04/§06): 390px; на мобиле — под шапкой */}
      {event && (
        <div className="event-in absolute left-1/2 top-[104px] z-10 w-[390px] max-w-[92vw] -translate-x-1/2 rounded-card border p-3.5 backdrop-blur md:top-4"
             style={{ background: "rgba(253,244,222,.97)", borderColor: "rgba(217,161,43,.6)" }}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[9.5px] font-bold uppercase tracking-[0.12em] text-warntext">
                Событие · {event.title}
              </div>
              <p className="mt-1 text-xs leading-[1.5] text-ink-secondary">{event.text}</p>
            </div>
            <button type="button" className="text-ink-muted hover:text-ink"
                    onClick={() => setEvent(null)} aria-label="закрыть">✕</button>
          </div>
        </div>
      )}

      {/* VN-окно (§05): inset 20/20/16; на мобиле — вплотную к краям */}
      <div className="absolute inset-x-2 bottom-2 md:inset-x-5 md:bottom-4">
        <div
          className="relative mx-auto max-w-4xl rounded-window border border-line bg-surface/95 px-4 py-3 shadow-window backdrop-blur md:px-6 md:py-4"
          onClick={() => !writer.done && writer.skip()}
        >
          {/* Имя-ярлык на верхней кромке; при ожидании — счётчик генерации (4c) */}
          <div className="absolute -top-[15px] left-6 flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1 shadow-tab">
            <span className="text-[13px] font-bold">
              {busy ? "…" : start.scenario.opponent_name}
            </span>
            {npcLine.source === "llm" && (
              <span className="rounded border border-line px-1 font-mono text-[9px] font-bold uppercase text-ink-muted">
                ИИ
              </span>
            )}
            {busy && (
              <span className="font-mono text-[10px] tabular-nums text-ink-muted">
                {busySeconds}с
              </span>
            )}
          </div>

          {/* Лоток действий + таймер */}
          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 md:gap-3">
            <div className="flex max-w-full items-center gap-[6px] overflow-x-auto rounded-full border border-[#eae9e2] bg-ink/[.035] px-[7px] py-[5px]">
              {start.action_catalog.map((item) => {
                const state = actions.find((a) => a.id === item.id);
                const disabled = !state?.available || actionBusy || status !== "active";
                return (
                  <button
                    key={item.id}
                    type="button"
                    disabled={disabled}
                    onClick={(e) => { e.stopPropagation(); void doAction(item.id); }}
                    title={`${item.label} — ${item.hint}` +
                      (state && !state.available && state.reason ? ` (${state.reason})` : "")}
                    className={`relative h-7 rounded-full border bg-white px-2.5 text-[11px] font-semibold shadow-[0_1px_3px_rgba(10,12,18,.08)] transition-colors ${
                      disabled
                        ? "border-[#eae9e2] font-normal text-[#c9c7c0]"
                        : "border-line text-ink-secondary hover:border-accent hover:bg-accent-soft hover:text-accent-deep"
                    }`}
                  >
                    {item.word}
                    {state && !state.available && state.uses_left > 0 && (
                      <span className="absolute -right-1 -top-1 rounded-full border border-[#eae9e2] bg-white px-1 text-[8.5px] font-semibold tabular-nums text-ink-muted">
                        {state.uses_left}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            {exam ? (
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                режим · экзамен
              </span>
            ) : start.timed && status === "active" ? (
              <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-xs ${timerStyles[timerStage]}`}
                    title="Время на ответ учитывается: долгая пауза читается как колебание">
                <span className="text-[9px] uppercase tracking-[0.12em]">свободный</span>
                {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
                <span className="h-1 w-11 overflow-hidden rounded-full bg-linein">
                  <span className="block h-full rounded-full bg-current"
                        style={{ width: `${Math.min(100, (elapsed / start.think_hard) * 100)}%` }} />
                </span>
              </span>
            ) : null}
          </div>

          {narrative && (
            <p className="narrative-in mb-1.5 text-sm italic text-ink-muted">
              {narrative}
            </p>
          )}

          {/* Реплика 16/1.65 */}
          <div className="min-h-[58px] text-base leading-[1.65]">
            {busy ? (
              <span className="italic text-ink-muted">
                обдумывает ответ
                <span className="typing-dot">.</span>
                <span className="typing-dot">.</span>
                <span className="typing-dot">.</span>
              </span>
            ) : (
              <>
                {writer.shown}
                {!writer.done && <span className="vn-caret" aria-hidden />}
              </>
            )}
          </div>

          {/* «ваш ход»: чипы + счётчик ответа */}
          {!exam && (
            <div className="mt-1.5 flex min-h-[26px] flex-wrap items-center gap-1.5 border-t border-linein pt-1.5">
              {busy ? (
                <span className="text-[11px] text-ink-muted">
                  {start.scenario.opponent_name} отвечает — реплику не отправить,
                  действия-мелочи доступны.
                </span>
              ) : lastEcho ? (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                    ваш ход
                  </span>
                  <MoveChips moves={lastEcho.moves ?? []} />
                  <EffectChips effects={lastEcho.effects ?? []} />
                  {start.timed && typeof lastEcho.thinking === "number" && (
                    <span className="font-mono text-[11px] text-ink-muted">
                      ответ · {lastEcho.thinking} с
                    </span>
                  )}
                </>
              ) : (
                <span className="text-[11px] text-ink-muted">
                  Ход {turnCount} из {start.max_turns} · говорите словами или жестами
                </span>
              )}
            </div>
          )}

          {error && (
            <p className="mt-2 text-sm text-critical">
              {error}
              {error.includes("сессия не найдена") && (
                <button type="button" onClick={onCatalog} className="ml-2 underline">
                  в каталог
                </button>
              )}
            </p>
          )}

          <div className="mt-3 flex items-center gap-2">
            <input
              value={input}
              maxLength={1000}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder={busy ? "Дождитесь ответа…"
                : status === "active" ? "Ваша реплика…" : "Партия завершена"}
              disabled={status !== "active" || busy}
              className="h-11 flex-1 rounded-btn border border-line bg-white px-4 text-[13.5px] shadow-[inset_0_1px_3px_rgba(10,12,18,.05)] outline-none transition-colors focus:border-accent focus:ring-[3px] focus:ring-accent-soft disabled:bg-fill disabled:text-ink-muted"
            />
            <Button onClick={() => void send()}
                    disabled={busy || status !== "active" || !input.trim()}>
              Сказать
            </Button>
          </div>
        </div>
      </div>

      {/* Оверлеи 420 (§05: 4f, 4g) */}
      {panel !== "none" && (
        <>
          <div className="scrim absolute inset-0 z-10" onClick={() => setPanel("none")} />
          <div className="panel-in absolute inset-y-0 right-0 z-20 w-[min(420px,94vw)] border-l border-line bg-surface shadow-panel">
            <div className="flex items-center justify-between border-b border-linein px-5 py-4">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold">
                  {panel === "log" ? "Журнал партии" : "Карта подготовки"}
                </span>
                <Tag tone="muted">
                  {panel === "log"
                    ? `${items.filter((i) => i.kind === "npc" || i.kind === "player").length} реплик`
                    : start.scenario.id}
                </Tag>
              </div>
              <button type="button" onClick={() => setPanel("none")} aria-label="закрыть"
                      className="text-ink-muted hover:text-ink">✕</button>
            </div>
            <div ref={logRef} className="h-[calc(100%-56px)] overflow-y-auto p-5">
              {panel === "log"
                ? <LogBody items={items} name={start.scenario.opponent_name} timed={start.timed} />
                : <BriefBody start={start} />}
            </div>
          </div>
        </>
      )}

      {/* Финал (§06: 4e): итог, отношения, статы, выгода к первому офферу */}
      {status !== "active" && (
        <div className="scrim-final absolute inset-0 z-30 grid place-items-center">
          <div className="rise-in w-[470px] max-w-[92vw] rounded-2xl border border-line bg-surface p-6 text-center shadow-window">
            <div className="tag mb-2">партия завершена</div>
            <div className="text-[21px] font-bold">
              {STATUS_LABELS[status] ?? status}
              {dealText ? `: ${dealText}` : ""}
            </div>
            <p className="mt-1.5 text-sm font-light text-ink-secondary">
              {relationLine(status, meters)}
            </p>
            <div className="my-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 border-y border-linein py-2.5 font-mono text-[11px] text-ink-secondary">
              <span>{turnCount} ходов</span>
              <span>{fmtClock(clock)}</span>
              <span>доверие {meters.trust ?? "—"}</span>
              {(() => {
                if (dealValue === null || firstOffer.current === null) return null;
                const higher = start.scenario.goal_value > start.scenario.limit_value;
                const gain = higher ? dealValue - firstOffer.current
                  : firstOffer.current - dealValue;
                if (gain <= 0) return null;
                return (
                  <span className="text-goodtext">
                    +{gain} {start.scenario.unit} к офферу
                  </span>
                );
              })()}
            </div>
            <div className="flex justify-center gap-2">
              <Button onClick={() => onDebrief(start.session_id)}>
                Разбор партии →
              </Button>
              <Button kind="ghost" onClick={onCatalog}>В каталог</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function relationLine(status: string, meters: Meters): string {
  if (status === "deal") {
    if ((meters.tension ?? 0) >= 55) return "Сделка есть, но отношения на пределе.";
    if ((meters.trust ?? 0) >= 55) return "Отношения сохранены.";
    return "Договорённость зафиксирована.";
  }
  if (status === "walked_away") return "Отношения разорваны — оппонент вышел сам.";
  if (status === "expired") return "Время истекло без решения.";
  return "Вы сохранили свою альтернативу.";
}

function SceneImage({ scenarioId }: { scenarioId: string }) {
  const [ok, setOk] = useState(true);
  useEffect(() => setOk(true), [scenarioId]);
  if (!ok) return null;
  return (
    <img
      src={`/scenes/${scenarioId}.jpg`}
      onError={() => setOk(false)}
      alt=""
      className="absolute inset-0 h-full w-full object-cover"
    />
  );
}

function HintsCard({ hints, onPick }: {
  hints: Hint[]; onPick: (text: string) => void;
}) {
  return (
    <div className="rise-in rounded-card border border-line bg-surface/95 p-3.5 shadow-card backdrop-blur">
      <SectionTitle>Подсказки</SectionTitle>
      <div className="flex flex-col divide-y divide-linein">
        {hints.map((hint, index) => hint.insert ? (
          <button
            key={index}
            type="button"
            onClick={() => onPick(hint.text)}
            className="group py-2 text-left first:pt-0 last:pb-0"
            title={hint.why}
          >
            <Tag>{hint.tag}</Tag>
            <div className="mt-0.5 text-[11.5px] leading-[1.45] text-ink group-hover:text-accent-deep">
              {hint.text}
            </div>
          </button>
        ) : (
          <div key={index} className="py-2 first:pt-0 last:pb-0">
            <Tag>{hint.tag}</Tag>
            <div className="mt-0.5 text-[11.5px] leading-[1.45] text-ink-secondary">
              {hint.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* Мини-метр мобильной шапки: полоса 4px + значение. */
function MiniMeter({ label, value, max, tone }: {
  label: string; value: number | null; max: number; tone: string;
}) {
  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline justify-between">
        <span className="text-[9px] uppercase tracking-[0.08em] text-ink-muted">
          {label}
        </span>
        <span className="text-[10px] font-bold tabular-nums">
          {value ?? "—"}
        </span>
      </div>
      <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-linein">
        {value !== null && (
          <div className="h-full rounded-full"
               style={{ width: `${(value / max) * 100}%`, background: tone }} />
        )}
      </div>
    </div>
  );
}

function TabButton({ children, onClick, active }: {
  children: React.ReactNode; onClick: () => void; active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-[9px] px-2 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? "bg-accent-soft text-accent-deep"
          : "text-ink-secondary hover:bg-fill"
      }`}
    >
      {children}
    </button>
  );
}

function LogBody({ items, name, timed }: {
  items: LogItem[]; name: string; timed: boolean;
}) {
  return (
    <div className="flex flex-col gap-3.5">
      {items.map((item, index) => {
        if (item.kind === "event") {
          return (
            <div key={index} className="rounded-card border px-3 py-2 text-xs text-ink-secondary"
                 style={{ background: "rgba(253,244,222,.97)", borderColor: "rgba(217,161,43,.6)" }}>
              <b className="text-warntext">{item.title}.</b> {item.text}
            </div>
          );
        }
        if (item.kind === "action") {
          const delta = (item.effects ?? [])
            .filter((e) => e.meter !== "patience" && Math.abs(e.delta) >= 1)
            .map((e) => `${e.meter === "trust" ? "доверие" : "напряжение"} ${e.delta > 0 ? "+" : ""}${Math.round(e.delta)}`)
            .join(" · ");
          return (
            <p key={index} className="text-center text-xs italic text-ink-muted">
              — {item.narrative?.replace(/^Вы /, "вы ").replace(/\.$/, "")}
              {delta ? ` · ${delta}` : ""} —
            </p>
          );
        }
        if (item.kind === "npc") {
          return (
            <div key={index}>
              <div className="flex items-baseline gap-2">
                <span className="text-[13px] font-bold">{name}</span>
                {item.ts && (
                  <span className="font-mono text-[9.5px] text-ink-muted">{item.ts}</span>
                )}
              </div>
              <p className="mt-0.5 text-sm leading-relaxed text-ink-secondary">{item.text}</p>
            </div>
          );
        }
        return (
          <div key={index} className="rounded-card bg-fill p-3">
            <div className="flex items-baseline gap-2">
              <span className="text-[13px] font-bold text-accent-deep">Вы</span>
              {item.ts && (
                <span className="font-mono text-[9.5px] text-ink-muted">{item.ts}</span>
              )}
            </div>
            <p className="mt-0.5 text-sm leading-relaxed">{item.text}</p>
            {(item.moves?.length || item.effects?.length) ? (
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <MoveChips moves={item.moves ?? []} />
                <EffectChips effects={item.effects ?? []} />
                {timed && typeof item.thinking === "number" && (
                  <span className="font-mono text-[10px] text-ink-muted">
                    ответ · {item.thinking} с
                  </span>
                )}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function BriefBody({ start }: { start: StartPayload }) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <p className="font-light leading-relaxed text-ink-secondary">{start.setting}</p>
      <div className="border-t border-linein pt-3">
        <Tag>цель</Tag>
        <div className="mt-0.5 text-ink-secondary">{start.brief.goal}</div>
      </div>
      <div className="border-t border-linein pt-3">
        <Tag>альтернатива · batna</Tag>
        <div className="mt-0.5 text-ink-secondary">{start.brief.batna}</div>
      </div>
      <div className="border-t border-linein pt-3">
        <Tag tone="critical">красные линии</Tag>
        <ul className="mt-1 flex flex-col gap-1 text-ink-secondary">
          {start.brief.issues.map((issue) => (
            <li key={issue.id}>
              {issue.kind === "numeric" ? (
                <>
                  {issue.name}: цель{" "}
                  <b className="font-mono tabular-nums">{issue.player_target}</b>
                  {issue.unit ? ` ${issue.unit}` : ""}, предел{" "}
                  <b className="font-mono tabular-nums">{issue.player_limit}</b>
                </>
              ) : (
                <>
                  {issue.name}
                  {issue.good_for_player === false && (
                    <span className="text-ink-muted"> · разменная монета</span>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="border-t border-linein pt-3">
        <Tag>факты</Tag>
        <ul className="mt-1 list-inside list-disc text-ink-secondary">
          {start.brief.facts.map((fact) => <li key={fact}>{fact}</li>)}
        </ul>
      </div>
      {start.brief.criteria.length > 0 && (
        <div className="border-t border-linein pt-3">
          <Tag>объективные критерии</Tag>
          <ul className="mt-1 list-inside list-disc text-ink-secondary">
            {start.brief.criteria.map((c) => <li key={c}>{c}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
