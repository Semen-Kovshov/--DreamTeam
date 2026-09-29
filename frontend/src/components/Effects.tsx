import type { EffectItem, MoveChip } from "../types";
import { Chip } from "../ui";

const METER_NAMES: Record<string, string> = {
  trust: "доверие",
  tension: "напряжение",
  patience: "терпение",
};

/* Дельты знаком (§02): рост доверия — тёмная хвоя, снижение напряжения —
   зелёный статус, риск — красный. Здесь: good/bad решают цвет бейджа. */
function effectTone(effect: EffectItem): "good" | "bad" | "neutral" {
  if (effect.meter === "trust") return effect.delta > 0 ? "good" : "bad";
  if (effect.meter === "tension") return effect.delta > 0 ? "bad" : "good";
  return "neutral";
}

export function MoveChips({ moves }: { moves: MoveChip[] }) {
  if (!moves.length) return null;
  return (
    <>
      {moves.map((move, index) => (
        <Chip key={index} tone="accent">
          {move.label}
          {move.spin && <b className="font-semibold">· {move.spin}</b>}
          {move.conditional && <span>· условное</span>}
        </Chip>
      ))}
    </>
  );
}

export function EffectChips({ effects }: { effects: EffectItem[] }) {
  const visible = effects.filter(
    (effect) => effect.meter in METER_NAMES && Math.abs(effect.delta) >= 1,
  );
  if (!visible.length) return null;
  return (
    <>
      {visible.map((effect, index) => (
        <Chip
          key={index}
          delta={`${effect.delta > 0 ? "+" : ""}${Math.round(effect.delta)}`}
          deltaTone={effectTone(effect)}
        >
          {METER_NAMES[effect.meter]}
        </Chip>
      ))}
    </>
  );
}
