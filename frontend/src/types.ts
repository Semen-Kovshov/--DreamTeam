// Типы зеркалят полезные нагрузки бэкенда (app/engine/session.py).

export interface ScenarioCard {
  id: string;
  title: string;
  category: string;
  difficulty: number;
  summary: string;
  opponent_name: string;
  opponent_role: string;
  portrait: string;
  persona: "soft" | "positional" | "hard";
  max_turns: number;
  skills: string[];
  goal_value: number;
  limit_value: number;
  unit: string;
  palette: { from: string; to: string };
  est_minutes: number;
}

export interface PublicIssue {
  id: string;
  kind: "numeric" | "boolean";
  name: string;
  unit?: string;
  direction?: "higher_better" | "lower_better";
  player_target?: number;
  player_limit?: number;
  ask_phrase?: string;
  good_for_player?: boolean;
}

export interface Brief {
  role: string;
  goal: string;
  batna: string;
  facts: string[];
  criteria: string[];
  issues: PublicIssue[];
}

export type Mode = "training" | "free" | "exam";

export interface Meters {
  trust: number | null;
  tension: number | null;
  patience: number;
}

export type Mood = "calm" | "pleased" | "tense" | "angry";

export interface ActionCatalogItem {
  id: string;
  label: string;
  word: string;
  hint: string;
  cooldown: number;
  max_uses: number;
}

export interface ActionStatus {
  id: string;
  available: boolean;
  reason: string;
  uses_left: number;
}

export interface StartPayload {
  session_id: string;
  mode: Mode;
  scenario: ScenarioCard;
  setting: string;
  brief: Brief;
  opening: string;
  meters: Meters;
  max_turns: number;
  npc_mood: Mood;
  action_catalog: ActionCatalogItem[];
  actions: ActionStatus[];
  timed: boolean;
  think_soft: number;
  think_hard: number;
}

export interface MoveChip {
  label: string;
  spin?: string;
  conditional?: boolean;
}

export interface EffectItem {
  meter: string;
  delta: number;
  reason: string;
}

export type GameStatus = "active" | "deal" | "no_deal" | "walked_away" | "expired";

export interface TurnPayload {
  session_id: string;
  kind: "turn";
  turn: number;
  status: GameStatus;
  npc_text: string;
  npc_source: "llm" | "template";
  npc_mood: Mood;
  voice_note?: string;
  event: { title: string; text: string } | null;
  meters: Meters;
  moves: MoveChip[];
  effects: EffectItem[];
  actions: ActionStatus[];
  thinking_seconds?: number | null;
  on_table?: string;
  on_table_value?: number | null;
  deal_text?: string | null;
  deal_value?: number | null;
}

export interface ActionPayload {
  session_id: string;
  kind: "action";
  narrative: string;
  npc_text: string;
  npc_mood: Mood;
  meters: Meters;
  effects: EffectItem[];
  actions: ActionStatus[];
}

export interface Hint {
  tag: string;
  text: string;
  insert: boolean;       // true — готовая реплика (клик подставляет в поле)
  technique?: string;
  why?: string;
}

export interface Competency {
  id: string;
  name: string;
  score: number;
  comment: string;
}

export interface TranscriptTurn {
  kind: "turn" | "action";
  at_seconds?: number | null;
  n: number;
  player_text: string;
  narrative: string;
  moves: MoveChip[];
  effects: EffectItem[];
  event: { title: string; text: string } | null;
  npc_text: string;
  npc_source: "llm" | "template";
  npc_note: string;
  thinking_seconds?: number | null;
  meters: { trust: number; tension: number; patience: number };
}

export interface Economics {
  utility_player: number;
  batna: number;
  vs_batna?: number;
  utility_opponent?: number;
  zopa?: { player_edge: number; opponent_edge: number; capture: number | null };
  left_on_table?: { points: number; package: string | null };
  best_offer_seen?: string | null;
  best_offer_utility?: number | null;
  opponent_first_offer?: number | null;
  player_anchor?: number | null;
  unit?: string;
}

export interface Debrief {
  status: GameStatus;
  deal: Record<string, number | boolean> | null;
  deal_text: string | null;
  competencies: Competency[];
  overall: { score: number; grade: string };
  moments: { turn: number; at_seconds?: number | null; title: string; text: string }[];
  recommendations: { tag: string; text: string }[];
  llm_used: boolean;
  duration_seconds: number;
  finished_at: number | null;
  economics: Economics;
  scenario: ScenarioCard;
  mode: Mode;
  transcript: TranscriptTurn[];
  opening: string;
}

export interface HistoryRecord {
  finished_at: number;
  session_id: string;
  scenario_id: string;
  scenario_title: string;
  mode: Mode;
  status: GameStatus;
  turns: number;
  overall: { score: number; grade: string };
  deal_text: string | null;
}

export interface AdminScenarioRow {
  id: string;
  title: string;
  category: string;
  persona: string;
  difficulty: number;
  builtin: boolean;
}

export interface GenerationForm {
  sphere: string;
  topic: string;
  player_role: string;
  opponent_role: string;
  opponent_name: string;
  persona: "soft" | "positional" | "hard";
  difficulty: number;
  unit: string;
  player_target: number | null;
  player_limit: number | null;
  opponent_start: number | null;
  opponent_limit: number | null;
  wishes: string;
}

export interface Health {
  ok: boolean;
  llm: { provider: string; model: string | null; enabled: boolean };
  scenarios: number;
}
