import { useEffect, useState } from "react";
import { api } from "./api";
import type { Debrief as DebriefData, Health, ScenarioCard, StartPayload } from "./types";
import { Catalog } from "./screens/Catalog";
import { Briefing } from "./screens/Briefing";
import { Game } from "./screens/Game";
import { Debrief } from "./screens/Debrief";
import { Admin } from "./screens/Admin";

type View =
  | { name: "catalog" }
  | { name: "brief"; card: ScenarioCard }
  | { name: "game"; start: StartPayload }
  | { name: "debrief"; data: DebriefData }
  | { name: "admin" };

export default function App() {
  const [view, setView] = useState<View>({ name: "catalog" });
  const [health, setHealth] = useState<Health | null>(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const openDebrief = async (sessionId: string) => {
    try {
      setView({ name: "debrief", data: await api.debrief(sessionId) });
      window.scrollTo(0, 0);
    } catch (e) {
      setLoadError(String((e as Error).message ?? e));
    }
  };

  const replay = async (data: DebriefData) => {
    try {
      const start = await api.start(data.scenario.id, data.mode, true);
      setView({ name: "game", start });
    } catch (e) {
      setLoadError(String((e as Error).message ?? e));
    }
  };

  return (
    <div className="min-h-screen bg-page text-ink">
      <header className="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <button
            type="button"
            onClick={() => setView({ name: "catalog" })}
            className="flex items-baseline gap-2"
          >
            <span className="text-lg font-bold tracking-tight">Вторая сторона</span>
            <span className="hidden text-sm text-ink-muted sm:inline">
              тренажёр переговоров
            </span>
          </button>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setView(view.name === "admin" ? { name: "catalog" } : { name: "admin" })}
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                view.name === "admin"
                  ? "border-accent bg-accent-soft text-accent-deep"
                  : "border-line text-ink-secondary hover:border-ink-muted"
              }`}
            >
              Админ
            </button>
            <div className="flex items-center gap-2 text-xs text-ink-muted">
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${health?.llm.enabled ? "bg-good" : "bg-baseline"}`}
              />
              {health === null
                ? "нет связи с бэкендом"
                : health.llm.enabled
                  ? `LLM: ${health.llm.model}`
                  : "офлайн-режим (без LLM)"}
            </div>
          </div>
        </div>
      </header>

      {loadError && (
        <div className="mx-auto max-w-6xl px-6 pt-3">
          <p className="text-sm text-critical">{loadError}</p>
        </div>
      )}

      {view.name === "catalog" && (
        <Catalog onPick={(card) => setView({ name: "brief", card })} />
      )}
      {view.name === "brief" && (
        <Briefing
          card={view.card}
          llmEnabled={health?.llm.enabled ?? false}
          onStart={(start) => setView({ name: "game", start })}
          onBack={() => setView({ name: "catalog" })}
        />
      )}
      {view.name === "game" && (
        /* key: новая сессия обязана перемонтировать экран партии, иначе
           «Сыграть ещё раз» унаследует реплики и метры прошлой игры. */
        <Game key={view.start.session_id} start={view.start}
              onDebrief={(id) => void openDebrief(id)}
              onCatalog={() => setView({ name: "catalog" })} />
      )}
      {view.name === "admin" && (
        <Admin onCatalog={() => setView({ name: "catalog" })}
               llmEnabled={health?.llm.enabled ?? false} />
      )}
      {view.name === "debrief" && (
        <Debrief
          debrief={view.data}
          onReplay={() => void replay(view.data)}
          onCatalog={() => setView({ name: "catalog" })}
        />
      )}
    </div>
  );
}
