$ErrorActionPreference = "Stop"

$baseUrl = "http://127.0.0.1:8000"

$health = Invoke-RestMethod "$baseUrl/health"
Write-Host "API health:" $health.status

$objectiveBody = @{
  title = "Smoke test ACVR1/FOP run"
  objective = "Generate a smoke-test therapeutic hypothesis for ACVR1-driven FOP."
  constraints = @{
    require_critic = $true
    require_citations = $true
  }
} | ConvertTo-Json -Depth 5

$objective = Invoke-RestMethod -Method Post -Uri "$baseUrl/objectives" -ContentType "application/json" -Body $objectiveBody

$runBody = @{
  objective_id = $objective.id
  execute_demo = $true
  run_config = @{
    execution_mode = "inline"
    agent_count = 3
    max_runtime_minutes = 10
    tool_budget_usd = 1
    evidence_strictness = "balanced"
  }
} | ConvertTo-Json -Depth 5

$run = Invoke-RestMethod -Method Post -Uri "$baseUrl/runs" -ContentType "application/json" -Body $runBody
Write-Host "Run:" $run.id $run.status

$report = Invoke-RestMethod "$baseUrl/reports/$($run.id)"
Write-Host "Report:" $report.hypothesis.title
