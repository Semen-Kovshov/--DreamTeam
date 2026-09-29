import type { Meters } from "../types";

/* Метрика «хвоя» (§04): бар 6px на #edece6, заливка градиентом 90°. */
const GRADIENTS = {
  trust: "linear-gradient(90deg,#4da296,#1f7a6f)",
  tension: "linear-gradient(90deg,#e0b45c,#d9a12b)",
  patience: "linear-gradient(90deg,#8bbb7d,#5f9c53)",
} as const;

export function tensionTone(value: number): string {
  if (value >= 65) return "#c04b3c";
  if (value >= 45) return "#d97a3f";
  return "#d9a12b";
}

/* Знак «полезно/вредно» зависит от шкалы: −напряжение — хорошо. */
function deltaTone(meter: string, delta: number): string {
  const good = meter === "tension" ? delta < 0 : delta > 0;
  return good ? "text-goodtext" : "text-critical";
}

function Meter({ meterId, label, value, max = 100, gradient, display, delta }: {
  meterId: string; label: string; value: number | null; max?: number;
  gradient: string; display?: string; delta?: number;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[11px] text-ink-secondary">{label}</span>
        <span className="flex items-baseline gap-1.5">
          {typeof delta === "number" && delta !== 0 && (
            <span className={`font-mono text-[9.5px] tabular-nums ${deltaTone(meterId, delta)}`}>
              {delta > 0 ? "+" : ""}{delta}
            </span>
          )}
          <span className="font-mono text-[11.5px] font-bold tabular-nums">
            {value === null ? "—" : display ?? value}
          </span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-[3px] bg-linein">
        {value !== null && (
          <div
            className="bar-fill h-full rounded-[3px]"
            style={{ width: `${(value / max) * 100}%`, background: gradient }}
          />
        )}
      </div>
    </div>
  );
}

export interface MeterDeltas {
  trust?: number;
  tension?: number;
  patience?: number;
}

export function MetersPanel({ meters, maxTurns, hidden, deltas }: {
  meters: Meters; maxTurns: number; hidden: boolean; deltas?: MeterDeltas;
}) {
  if (hidden) {
    /* Экзамен (§06): заглушка с пунктирной рамкой. */
    return (
      <div className="rounded-card border border-dashed border-[#cfccc2] p-3 text-center">
        <div className="tag mb-1">режим экзамена</div>
        <p className="text-[11px] leading-snug text-ink-muted">
          Доверие, напряжение и терпение скрыты до разбора.
        </p>
      </div>
    );
  }
  return (
    <div>
      <Meter meterId="trust" label="Доверие" value={meters.trust}
             gradient={GRADIENTS.trust} delta={deltas?.trust} />
      <Meter meterId="tension" label="Напряжение" value={meters.tension}
             gradient={GRADIENTS.tension} delta={deltas?.tension} />
      <Meter meterId="patience" label="Терпение" value={meters.patience}
             max={maxTurns} gradient={GRADIENTS.patience}
             display={`${meters.patience} из ${maxTurns}`}
             delta={deltas?.patience} />
    </div>
  );
}
