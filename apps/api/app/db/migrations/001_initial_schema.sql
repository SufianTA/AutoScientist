CREATE TABLE objectives (
  id VARCHAR PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  objective_text TEXT NOT NULL,
  constraints_json JSON NOT NULL,
  created_by VARCHAR(120),
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE runs (
  id VARCHAR PRIMARY KEY,
  objective_id VARCHAR NOT NULL REFERENCES objectives(id),
  status VARCHAR(40) NOT NULL,
  current_state VARCHAR(80) NOT NULL,
  run_config_json JSON NOT NULL,
  agent_count INTEGER NOT NULL,
  max_runtime_minutes INTEGER NOT NULL,
  estimated_cost_usd FLOAT NOT NULL,
  account_id VARCHAR REFERENCES billing_accounts(id),
  payment_status VARCHAR(40) NOT NULL,
  queued_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  final_confidence FLOAT
);

CREATE TABLE billing_accounts (
  id VARCHAR PRIMARY KEY,
  owner_email VARCHAR(255) NOT NULL UNIQUE,
  display_name VARCHAR(255) NOT NULL,
  balance_usd FLOAT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE credit_ledger_entries (
  id VARCHAR PRIMARY KEY,
  account_id VARCHAR NOT NULL REFERENCES billing_accounts(id),
  run_id VARCHAR REFERENCES runs(id),
  entry_type VARCHAR(40) NOT NULL,
  amount_usd FLOAT NOT NULL,
  balance_after_usd FLOAT NOT NULL,
  description TEXT NOT NULL,
  external_reference VARCHAR(255),
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE checkout_sessions (
  id VARCHAR PRIMARY KEY,
  account_id VARCHAR NOT NULL REFERENCES billing_accounts(id),
  amount_usd FLOAT NOT NULL,
  provider VARCHAR(40) NOT NULL,
  status VARCHAR(40) NOT NULL,
  checkout_url VARCHAR(512) NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE model_tools (
  id VARCHAR PRIMARY KEY,
  name VARCHAR(160) NOT NULL UNIQUE,
  description TEXT NOT NULL,
  provider VARCHAR(80) NOT NULL,
  endpoint_url VARCHAR(512),
  api_key_env_var VARCHAR(160),
  input_schema_json JSON NOT NULL,
  output_schema_json JSON NOT NULL,
  tooluniverse_config_json JSON NOT NULL,
  status VARCHAR(40) NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE agent_steps (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  agent_name VARCHAR(120) NOT NULL,
  state_name VARCHAR(120) NOT NULL,
  input_json JSON NOT NULL,
  output_json JSON NOT NULL,
  started_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP,
  error TEXT
);

CREATE TABLE tool_calls (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR REFERENCES runs(id),
  step_id VARCHAR REFERENCES agent_steps(id),
  tool_name VARCHAR(160) NOT NULL,
  tool_source VARCHAR(80) NOT NULL,
  input_json JSON NOT NULL,
  output_json JSON NOT NULL,
  status VARCHAR(40) NOT NULL,
  latency_ms INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE evidence_items (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  source VARCHAR(160) NOT NULL,
  source_url_or_id VARCHAR(512),
  evidence_text TEXT NOT NULL,
  structured_json JSON NOT NULL,
  support_label VARCHAR(80),
  support_score FLOAT,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE hypotheses (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  title VARCHAR(255) NOT NULL,
  hypothesis_text TEXT NOT NULL,
  confidence FLOAT NOT NULL,
  status VARCHAR(80) NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE board_posts (
  id VARCHAR PRIMARY KEY,
  post_type VARCHAR(80) NOT NULL,
  run_id VARCHAR REFERENCES runs(id),
  hypothesis_id VARCHAR REFERENCES hypotheses(id),
  agent_author VARCHAR(120) NOT NULL,
  content_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE model_scores (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  evidence_id VARCHAR REFERENCES evidence_items(id),
  model_name VARCHAR(160) NOT NULL,
  label VARCHAR(80) NOT NULL,
  score FLOAT NOT NULL,
  rationale TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);
