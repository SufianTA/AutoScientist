CREATE TABLE scientific_entities (
  id VARCHAR PRIMARY KEY,
  entity_type VARCHAR(80) NOT NULL,
  name VARCHAR(255) NOT NULL,
  normalized_name VARCHAR(255) NOT NULL,
  aliases_json JSON NOT NULL,
  metadata_json JSON NOT NULL,
  first_seen_run_id VARCHAR REFERENCES runs(id),
  last_seen_run_id VARCHAR REFERENCES runs(id),
  mention_count INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  CONSTRAINT uq_scientific_entity UNIQUE (entity_type, normalized_name)
);

CREATE TABLE scientific_hypothesis_memory (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  hypothesis_id VARCHAR REFERENCES hypotheses(id),
  title VARCHAR(255) NOT NULL,
  hypothesis_text TEXT NOT NULL,
  confidence FLOAT,
  status VARCHAR(80) NOT NULL,
  entity_ids_json JSON NOT NULL,
  evidence_summary_json JSON NOT NULL,
  failure_modes_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE scientific_causal_links (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  source_entity_id VARCHAR REFERENCES scientific_entities(id),
  target_entity_id VARCHAR REFERENCES scientific_entities(id),
  relation VARCHAR(120) NOT NULL,
  confidence FLOAT,
  evidence_ids_json JSON NOT NULL,
  metadata_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE experiment_memory (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  hypothesis_memory_id VARCHAR REFERENCES scientific_hypothesis_memory(id),
  name VARCHAR(255) NOT NULL,
  experiment_type VARCHAR(120) NOT NULL,
  expected_information_gain VARCHAR(120),
  feasibility VARCHAR(120),
  status VARCHAR(80) NOT NULL,
  protocol_json JSON NOT NULL,
  result_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE run_replays (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL UNIQUE REFERENCES runs(id),
  replay_hash VARCHAR(80) NOT NULL,
  bundle_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE tool_benchmarks (
  id VARCHAR PRIMARY KEY,
  tool_name VARCHAR(160) NOT NULL,
  tool_source VARCHAR(80) NOT NULL,
  call_count INTEGER NOT NULL,
  success_count INTEGER NOT NULL,
  failure_count INTEGER NOT NULL,
  avg_latency_ms FLOAT NOT NULL,
  avg_usefulness FLOAT,
  last_error TEXT,
  last_run_id VARCHAR REFERENCES runs(id),
  updated_at TIMESTAMP NOT NULL,
  CONSTRAINT uq_tool_benchmark UNIQUE (tool_name, tool_source)
);

CREATE TABLE agent_role_memory (
  id VARCHAR PRIMARY KEY,
  agent_name VARCHAR(120) NOT NULL UNIQUE,
  role_summary TEXT NOT NULL,
  run_count INTEGER NOT NULL,
  last_run_id VARCHAR REFERENCES runs(id),
  memory_json JSON NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE workflow_policy_examples (
  id VARCHAR PRIMARY KEY,
  run_id VARCHAR NOT NULL REFERENCES runs(id),
  step_index INTEGER NOT NULL,
  state_name VARCHAR(120) NOT NULL,
  action_type VARCHAR(80) NOT NULL,
  action_name VARCHAR(160) NOT NULL,
  context_json JSON NOT NULL,
  outcome_json JSON NOT NULL,
  reward FLOAT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE workflow_policy_models (
  id VARCHAR PRIMARY KEY,
  name VARCHAR(160) NOT NULL,
  version VARCHAR(80) NOT NULL,
  model_type VARCHAR(120) NOT NULL,
  training_summary_json JSON NOT NULL,
  artifact_path VARCHAR(512) NOT NULL,
  metrics_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL
);
