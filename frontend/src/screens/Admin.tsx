import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AdminScenarioRow, GenerationForm } from "../types";
import { Button, Card, PERSONA_LABELS, SectionTitle, Tag } from "../ui";

const EMPTY_FORM: GenerationForm = {
  sphere: "", topic: "", player_role: "", opponent_role: "", opponent_name: "",
  persona: "positional", difficulty: 2, unit: "",
  player_target: null, player_limit: null, opponent_start: null,
  opponent_limit: null, wishes: "",
};

const EXAMPLE_FORM: GenerationForm = {
  sphere: "Логистика",
  topic: "Продление аренды склада 2000 м² под маркетплейс: владелец поднимает ставку, а нам нужны стабильные условия на год вперёд",
  player_role: "Операционный директор маркетплейса",
  opponent_role: "Владелец логистического парка",
  opponent_name: "Виктор Степанович",
  persona: "positional", difficulty: 2, unit: "₽/м²",
  player_target: 480, player_limit: 560, opponent_start: 620,
  opponent_limit: 520,
  wishes: "Пусть у владельца будет незанятый соседний блок и кредит под залог парка",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="tag">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

const inputCls = "h-10 w-full rounded-btn border border-line bg-white px-3 " +
  "text-[13px] outline-none transition-colors focus:border-accent " +
  "focus:ring-[3px] focus:ring-accent-soft";

export function Admin({ onCatalog, llmEnabled }: {
  onCatalog: () => void; llmEnabled: boolean;
}) {
  const [rows, setRows] = useState<AdminScenarioRow[]>([]);
  const [form, setForm] = useState<GenerationForm>(EMPTY_FORM);
  const [draft, setDraft] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [checkResult, setCheckResult] = useState<string>("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [genSeconds, setGenSeconds] = useState(0);
  const [overwrite, setOverwrite] = useState(false);
  const timer = useRef<number | null>(null);

  const refresh = () => {
    api.adminScenarios().then(setRows).catch((e) => setError(String(e.message)));
  };
  useEffect(refresh, []);

  const set = (patch: Partial<GenerationForm>) =>
    setForm((prev) => ({ ...prev, ...patch }));

  const numberOrNull = (value: string) =>
    value.trim() === "" ? null : Number(value.replace(",", "."));

  const generate = async () => {
    setBusy(true);
    setError("");
    setWarnings([]);
    setCheckResult("");
    setGenSeconds(0);
    timer.current = window.setInterval(() => setGenSeconds((s) => s + 1), 1000);
    try {
      const result = await api.adminGenerate(form);
      setDraft(JSON.stringify(result.draft, null, 2));
      setWarnings(result.warnings);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      setBusy(false);
    }
  };

  const parseDraft = (): unknown | null => {
    try {
      return JSON.parse(draft);
    } catch {
      setCheckResult("JSON не разбирается — проверьте синтаксис");
      return null;
    }
  };

  const check = async () => {
    const scenario = parseDraft();
    if (scenario === null) return;
    const result = await api.adminValidate(scenario);
    setCheckResult(result.ok
      ? `Схема в порядке: «${result.card?.title}» готов к сохранению`
      : "Ошибки схемы:\n– " + result.errors.join("\n– "));
  };

  const save = async () => {
    const scenario = parseDraft();
    if (scenario === null) return;
    setError("");
    try {
      const result = await api.adminSave(scenario, overwrite);
      setCheckResult(`Сохранено: «${result.id}» появился в каталоге игрока`);
      refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  };

  const remove = async (id: string) => {
    setError("");
    try {
      await api.adminDelete(id);
      refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-5 flex items-baseline justify-between">
        <div>
          <div className="tag mb-1">контур администратора</div>
          <h1 className="text-[27px] font-bold leading-tight">
            Настройка контекста симуляции
          </h1>
          <p className="mt-1 max-w-2xl text-sm font-light text-ink-secondary">
            Задайте сферу, тему, роли, тон собеседника и сложность — сценарий
            соберётся автоматически и сразу появится в каталоге игрока.
            Черновик можно править руками до сохранения.
          </p>
        </div>
        <button type="button" onClick={onCatalog}
                className="text-sm text-ink-muted hover:text-ink">
          ← Каталог
        </button>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <SectionTitle>Контекст переговоров</SectionTitle>
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="сфера">
                <input className={inputCls} value={form.sphere}
                       onChange={(e) => set({ sphere: e.target.value })}
                       placeholder="Продажи, закупки, HR…" />
              </Field>
              <Field label="имя оппонента · опционально">
                <input className={inputCls} value={form.opponent_name}
                       onChange={(e) => set({ opponent_name: e.target.value })}
                       placeholder="придумает модель" />
              </Field>
            </div>
            <Field label="тема переговоров">
              <textarea
                className={`${inputCls} h-16 resize-none py-2`}
                value={form.topic}
                onChange={(e) => set({ topic: e.target.value })}
                placeholder="О чём торг, что на кону, какая предыстория"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="роль игрока">
                <input className={inputCls} value={form.player_role}
                       onChange={(e) => set({ player_role: e.target.value })} />
              </Field>
              <Field label="роль оппонента">
                <input className={inputCls} value={form.opponent_role}
                       onChange={(e) => set({ opponent_role: e.target.value })} />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="тон собеседника">
                <div className="flex gap-1.5">
                  {(["soft", "positional", "hard"] as const).map((p) => (
                    <button key={p} type="button" onClick={() => set({ persona: p })}
                            className={`flex-1 rounded-btn border px-2 py-2 text-[11.5px] font-semibold transition-colors ${
                              form.persona === p
                                ? "border-accent bg-accent-tint text-accent-deep"
                                : "border-line bg-surface text-ink-secondary hover:border-ink-muted"
                            }`}>
                      {PERSONA_LABELS[p]}
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="сложность">
                <div className="flex gap-1.5">
                  {[1, 2, 3, 4].map((d) => (
                    <button key={d} type="button" onClick={() => set({ difficulty: d })}
                            className={`h-10 flex-1 rounded-btn border text-sm font-bold tabular-nums transition-colors ${
                              form.difficulty === d
                                ? "border-accent bg-accent-tint text-accent-deep"
                                : "border-line bg-surface text-ink-secondary hover:border-ink-muted"
                            }`}>
                      {d}
                    </button>
                  ))}
                </div>
              </Field>
            </div>

            <details className="rounded-btn border border-linein bg-page/60 p-3">
              <summary className="cursor-pointer text-[12px] font-semibold text-ink-secondary">
                Числа главного вопроса · опционально (иначе придумает модель)
              </summary>
              <div className="mt-3 grid grid-cols-5 gap-2">
                <Field label="единица">
                  <input className={inputCls} value={form.unit}
                         onChange={(e) => set({ unit: e.target.value })}
                         placeholder="тыс. ₽" />
                </Field>
                {([
                  ["цель игрока", "player_target"],
                  ["предел игрока", "player_limit"],
                  ["старт оппон.", "opponent_start"],
                  ["предел оппон.", "opponent_limit"],
                ] as const).map(([label, key]) => (
                  <Field key={key} label={label}>
                    <input className={inputCls} inputMode="decimal"
                           value={form[key] ?? ""}
                           onChange={(e) => set({ [key]: numberOrNull(e.target.value) } as Partial<GenerationForm>)} />
                  </Field>
                ))}
              </div>
            </details>

            <Field label="пожелания · опционально">
              <textarea
                className={`${inputCls} h-14 resize-none py-2`}
                value={form.wishes}
                onChange={(e) => set({ wishes: e.target.value })}
                placeholder="Особые обстоятельства, скрытые боли оппонента, события"
              />
            </Field>

            <div className="flex flex-wrap items-center gap-2.5">
              <Button onClick={() => void generate()}
                      disabled={busy || !llmEnabled || form.topic.length < 5
                        || form.sphere.length < 2 || form.player_role.length < 3
                        || form.opponent_role.length < 3}
                      title={llmEnabled ? "" : "LLM не подключена"}>
                {busy ? `Собираем сценарий… ${Math.floor(genSeconds / 60)}:${String(genSeconds % 60).padStart(2, "0")}` : "Сгенерировать сценарий"}
              </Button>
              <Button kind="ghost" onClick={() => setForm(EXAMPLE_FORM)}>
                Заполнить пример
              </Button>
            </div>
            {busy && (
              <p className="text-[11.5px] font-light text-ink-muted">
                Локальная модель собирает ядро и реплики персонажа — обычно
                3–6 минут. Можно не ждать на этой странице: запрос доработает.
              </p>
            )}
            {!llmEnabled && (
              <p className="text-[11.5px] font-light text-ink-muted">
                LLM не подключена — генерация недоступна, но сценарий можно
                вставить или написать в редакторе справа и сохранить.
              </p>
            )}
          </div>
        </Card>

        <div className="flex flex-col gap-5">
          <Card>
            <SectionTitle>Сценарии в каталоге</SectionTitle>
            <div className="flex flex-col divide-y divide-linein">
              {rows.map((row) => (
                <div key={row.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] font-semibold">{row.title}</div>
                    <div className="text-[10.5px] text-ink-muted">
                      {row.id} · {PERSONA_LABELS[row.persona] ?? row.persona} ·
                      сложность {row.difficulty}
                    </div>
                  </div>
                  {row.builtin
                    ? <Tag tone="muted">встроенный</Tag>
                    : (
                      <button type="button" onClick={() => void remove(row.id)}
                              className="text-[11.5px] text-critical underline hover:no-underline">
                        удалить
                      </button>
                    )}
                </div>
              ))}
            </div>
          </Card>

          {warnings.length > 0 && (
            <Card>
              <SectionTitle>Автоправки генератора</SectionTitle>
              <ul className="flex flex-col gap-1 text-[11.5px] font-light text-ink-secondary">
                {warnings.map((w, i) => <li key={i}>– {w}</li>)}
              </ul>
            </Card>
          )}
        </div>
      </div>

      <Card className="mt-5">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Черновик сценария · JSON</SectionTitle>
          <div className="flex items-center gap-2.5">
            <label className="flex items-center gap-1.5 text-[11.5px] text-ink-secondary">
              <input type="checkbox" checked={overwrite}
                     onChange={(e) => setOverwrite(e.target.checked)} />
              перезаписать существующий
            </label>
            <Button size="sm" kind="ghost" onClick={() => void check()}
                    disabled={!draft.trim()}>
              Проверить
            </Button>
            <Button size="sm" onClick={() => void save()} disabled={!draft.trim()}>
              Сохранить в каталог
            </Button>
          </div>
        </div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          placeholder='Сгенерируйте сценарий или вставьте JSON по схеме (см. docs/04-scenario-format.md)'
          className="h-72 w-full resize-y rounded-btn border border-line bg-white p-3 text-[11.5px] leading-relaxed tabular-nums outline-none transition-colors focus:border-accent"
        />
        {checkResult && (
          <p className="mt-2 whitespace-pre-wrap text-[12px] text-ink-secondary">
            {checkResult}
          </p>
        )}
        {error && <p className="mt-2 text-sm text-critical">{error}</p>}
      </Card>
    </div>
  );
}
