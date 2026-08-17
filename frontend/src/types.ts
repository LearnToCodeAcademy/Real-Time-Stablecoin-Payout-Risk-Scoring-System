export type Decision = "ALLOW" | "REVIEW" | "BLOCK" | "OBSERVED" | "SKIP" | "ERROR";

export interface LiveStatus {
  state: string;
  source: string | null;
  last_event_at: string | null;
  last_block: number | null;
  events_seen: number;
  events_scored: number;
  error: string | null;
}

export interface AlertEvent {
  type?: string;
  event_id: string;
  timestamp: string;
  wallet: string;
  from_wallet?: string;
  token?: string;
  decision: Decision;
  score?: number | null;
  reason?: string;
  tx_hash?: string;
  block_number?: number;
  amount?: number;
  source?: string;
  verified_real?: boolean;
}

export interface AlertStatistics {
  decisions: Record<string, number>;
  open_cases: number;
  top_risky_wallets: Array<{
    wallet: string;
    token?: string | null;
    max_score?: number | null;
  }>;
}

export interface GraphPayload {
  nodes: Array<Record<string, string | number | boolean | null | undefined>>;
  edges: Array<Record<string, string | number | boolean | null | undefined>>;
}

export interface RiskCase {
  case_id: string;
  decision: Decision;
  token?: string | null;
  wallet: string;
  updated_at: string;
  score?: number | null;
}

export interface Health {
  status: string;
  version: string;
  database: string;
  cache: string;
  etherscan_keys_configured: number;
  live_stream: LiveStatus;
  active_models: Record<string, string>;
  local_training_enabled: boolean;
  api_auth_enabled: boolean;
}

export interface WalletScore {
  wallet: string;
  token?: string | null;
  score?: number | null;
  decision: Decision;
  reason: string;
  prob_normal?: number | null;
  prob_malicious?: number | null;
  prob_poisoned?: number | null;
  confidence?: number | null;
  features?: Record<string, number>;
  processing_time_ms?: number;
  cache_hit?: boolean;
  assessment_status?: "SCORED" | "UNSCORABLE" | "BLOCKED_BY_REPUTATION" | "SKIPPED";
  data_status?: string;
  threat_intelligence?: {
    status: "MATCH" | "CLEAR" | "UNAVAILABLE" | "NOT_APPLICABLE";
    findings: Array<{ source: string; nametag?: string; labels?: string[]; reason?: string }>;
    providers_checked?: string[];
    provider_errors?: string[];
  };
}

export interface ModelVersion {
  version: string;
  token: string;
  run_id: string;
  active: boolean;
  metrics: Record<string, number | null>;
}

export interface TrainingJob {
  run_id: string;
  status: string;
  token: string;
  model: string;
  progress: number;
  stage: string;
  metrics: Record<string, unknown>;
  versions: Record<string, string>;
  message: string;
  started_at: string;
  finished_at?: string | null;
}

export interface CollectionJob {
  job_id: string;
  status: string;
  discovered: number;
  processed: number;
  requests: number;
  settings: { target_wallets: number; tokens: string[] };
  message: string;
  started_at: string;
  output_path?: string;
}
