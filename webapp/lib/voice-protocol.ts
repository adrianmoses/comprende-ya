// --- Metrics (existing) ---

export interface VoiceMetrics {
  stt_ms: number;
  llm_ms: number;
  tts_ms: number;
  total_ms: number;
}

export interface VoiceResponse {
  type: "metrics";
  data: VoiceMetrics;
  transcription: string;
  response: string;
}

// --- Session & Activity ---

export interface Activity {
  concept_ids: string[];
  concept_names: string[];
  activity_type: "drill" | "conversation" | "discrimination" | "review";
  context: string;
  instructions: string;
  duration_estimate_min: number;
  contrast_pair: string[] | null;
}

export interface SessionPlan {
  learner_id: string;
  session_id: string;
  duration_target_min: number;
  activities: Activity[];
  created_at: string;
}

export interface SessionPlanMessage {
  type: "session_plan";
  plan: SessionPlan;
}

export interface ActivityChangeMessage {
  type: "activity_change";
  activity_index: number;
  activity: Activity;
  replan_action: string;
  replan_reason: string;
  remaining_activities: number;
}

export interface SessionEndMessage {
  type: "session_end";
  session_id: string;
  reason: string;
}

export type ServerMessage =
  | VoiceResponse
  | SessionPlanMessage
  | ActivityChangeMessage
  | SessionEndMessage;

// --- Learner Data (for dashboard) ---

export interface LearnerProfile {
  learner_id: string;
  mastered: string[];
  progressing: string[];
  decaying: string[];
  unseen: string[];
  confusion_pairs: ConfusionPair[];
  total_evidence_count: number;
}

export interface StudiesState {
  concept_id: string;
  mastery: number;
  projected_mastery: number;
  confidence: number;
  half_life_days: number;
  practice_count: number;
  last_evidence_at: string | null;
  last_outcome: number | null;
  trend: "improving" | "declining" | "plateau";
  first_seen_at: string | null;
}

export interface ConfusionPair {
  concept_a: string;
  concept_b: string;
  evidence_count: number;
  last_seen_at: string | null;
}

export interface EffectiveContext {
  context_id: string;
  concept_id: string | null;
  effectiveness: number;
  sample_count: number;
}
