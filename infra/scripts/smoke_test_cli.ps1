$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$reportPath = Join-Path $repoRoot.Path "outputs\smoke_cli_report.md"
$provenancePath = Join-Path $repoRoot.Path "outputs\smoke_cli_provenance.json"

& "$PSScriptRoot\run_local_question.ps1" `
  -Question "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and propose validation experiments." `
  -Agents 3 `
  -Runtime 10 `
  -Strictness balanced `
  -OutputFormat markdown `
  -OutputFile $reportPath `
  -ProvenanceFile $provenancePath

if (-not (Test-Path $reportPath)) {
  throw "CLI smoke report was not written: $reportPath"
}
if (-not (Test-Path $provenancePath)) {
  throw "CLI smoke provenance was not written: $provenancePath"
}

$reportText = Get-Content $reportPath -Raw
if ($reportText -notmatch "ACVR1" -or $reportText -notmatch "FOP" -or $reportText -notmatch "Guardrails") {
  throw "CLI smoke report is missing expected ACVR1/FOP guardrail content."
}

$provenance = Get-Content $provenancePath -Raw | ConvertFrom-Json
if ($provenance.trace_summary.agent_steps -lt 8) {
  throw "CLI smoke provenance has too few agent steps."
}
if ($provenance.trace_summary.tool_calls -lt 2) {
  throw "CLI smoke provenance has too few tool calls."
}

Write-Host "CLI smoke test passed"
Write-Host "Report:" $reportPath
Write-Host "Provenance:" $provenancePath
