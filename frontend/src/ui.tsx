import type { ReactNode } from "react";

export function Card({ children, className = "" }: {
  children: ReactNode; className?: string;
}) {
  return (
    <div className={`rounded-card border border-line bg-surface p-5 ${className}`}>
      {children}
    </div>
  );
}

/* Секция-хедер карточек: Sans 10/700 caps (§02) */
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 text-[10px] font-bold uppercase tracking-[0.1em] text-ink-muted">
      {children}
    </div>
  );
}

/* Метка-тег: mono 9 caps — единственная «нумерация» в системе (§02) */
export function Tag({ children, tone = "accent" }: {
  children: ReactNode; tone?: "accent" | "muted" | "warn" | "critical";
}) {
  const tones = {
    accent: "text-accent-deep",
    muted: "text-ink-muted",
    warn: "text-warntext",
    critical: "text-critical",
  } as const;
  return <span className={`tag ${tones[tone]}`}>{children}</span>;
}

/* Чип приёма: пилюля #f4f3ef, дельта — белая мини-пилюля mono внутри (§04) */
export function Chip({ children, delta, deltaTone = "neutral", tone = "neutral" }: {
  children: ReactNode;
  delta?: string;
  deltaTone?: "good" | "bad" | "neutral";
  tone?: "neutral" | "accent";
}) {
  const deltaTones = {
    good: "text-goodtext",
    bad: "text-critical",
    neutral: "text-ink-secondary",
  } as const;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-transparent px-3 py-1 text-xs font-medium ${
      tone === "accent" ? "bg-accent-tint text-accent-deep" : "bg-fill text-ink"
    }`}>
      {children}
      {delta && (
        <span className={`rounded-full bg-white px-1.5 py-px font-mono text-[10px] font-semibold ${deltaTones[deltaTone]}`}>
          {delta}
        </span>
      )}
    </span>
  );
}

export function Button({ children, onClick, kind = "primary", disabled, title, size = "md" }: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  title?: string;
  size?: "md" | "sm" | "lg";
}) {
  const kinds = {
    primary: "bg-accent text-white shadow-btn hover:bg-accent-deep",
    ghost: "border border-line bg-surface text-ink-secondary hover:border-ink-muted",
    danger: "border border-critical/40 bg-surface text-critical hover:bg-critical/5",
  } as const;
  const sizes = {
    lg: "h-[46px] px-6 text-[13.5px]",
    md: "h-11 px-6 text-[13.5px]",
    sm: "h-[33px] px-3.5 text-xs",
  } as const;
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-btn font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-55 ${kinds[kind]} ${sizes[size]}`}
    >
      {children}
    </button>
  );
}

/* Сложность: точки 7px, шкала из 4 (§05 каталог) */
export function Dots({ level, max = 4 }: { level: number; max?: number }) {
  return (
    <span className="inline-flex items-center gap-1" aria-label={`сложность ${level} из ${max}`}>
      {Array.from({ length: max }, (_, index) => (
        <span
          key={index}
          className={`h-[7px] w-[7px] rounded-full ${index < level ? "bg-accent" : "bg-line"}`}
        />
      ))}
    </span>
  );
}

export const PERSONA_LABELS: Record<string, string> = {
  soft: "мягкий стиль",
  positional: "позиционный торг",
  hard: "жёсткий стиль",
};

export const MODE_LABELS: Record<string, { name: string; hint: string }> = {
  training: { name: "Обучение", hint: "подсказки трёх техник и видимые индикаторы" },
  free: { name: "Свободный", hint: "индикаторы видны, время ответа на счету" },
  exam: { name: "Экзамен", hint: "все индикаторы скрыты до разбора" },
};

export const STATUS_LABELS: Record<string, string> = {
  deal: "Сделка",
  no_deal: "Без сделки",
  walked_away: "Оппонент прервал",
  expired: "Время вышло",
};
