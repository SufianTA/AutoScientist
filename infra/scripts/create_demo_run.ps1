$body = @{
  title = "ACVR1/FOP therapeutic hypothesis generation"
  objective = "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and identify candidate small molecules or intervention strategies. Use ToolUniverse tools where available, collect evidence, critique the hypothesis, and propose validation experiments."
  constraints = @{
    use_tooluniverse = $true
    allow_custom_tools = $true
    require_citations = $true
    require_critic = $true
  }
} | ConvertTo-Json -Depth 5

$objective = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/objectives" -ContentType "application/json" -Body $body
$runBody = @{ objective_id = $objective.id; execute_demo = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/runs" -ContentType "application/json" -Body $runBody

