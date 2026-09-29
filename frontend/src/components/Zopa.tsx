import type { Debrief } from "../types";

/** Доля [0..1] точки на шкале ZOPA от края игрока к краю оппонента. */
export function zopaPosition(playerEdge: number, opponentEdge: number,
                             value: number): number {
  if (playerEdge === opponentEdge) return 0;
  const share = (value - playerEdge) / (opponentEdge - playerEdge);
  return Math.max(0, Math.min(1, share));
}

export function ZopaScale({ debrief }: { debrief: Debrief }) {
  const economics = debrief.economics;
  const zopa = economics.zopa;
  const deal = debrief.deal;
  if (!zopa || !deal) return null;

  const mainIssueId = Object.keys(deal).find(
    (key) => typeof deal[key] === "number",
  );
  if (!mainIssueId) return null;
  const dealValue = deal[mainIssueId] as number;
  const position = zopaPosition(zopa.player_edge, zopa.opponent_edge, dealValue);

  return (
    <div>
      <div className="mb-1.5 flex justify-between font-mono text-[9.5px] text-ink-muted">
        <span>ваш предел · {zopa.player_edge}</span>
        <span>предел оппонента · {zopa.opponent_edge}</span>
      </div>
      <div className="relative h-2 rounded-[3px] bg-linein">
        <div
          className="bar-fill absolute inset-y-0 left-0 rounded-[3px] bg-accent-soft"
          style={{ width: `${position * 100}%` }}
        />
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent-deep ring-2 ring-surface"
          style={{ left: `${position * 100}%` }}
          title={`сделка: ${dealValue}`}
        />
      </div>
      <div className="mt-1.5 text-sm text-ink-secondary">
        Сделка <b className="font-mono tabular-nums">{dealValue}</b> — взято{" "}
        <b className="font-mono tabular-nums">{Math.round((zopa.capture ?? 0) * 100)}%</b>{" "}
        зоны возможного соглашения
      </div>
    </div>
  );
}
