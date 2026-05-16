param(
  [Parameter(Mandatory = $true)]
  [string]$Question,
  [int]$Agents = 6,
  [int]$Runtime = 30,
  [ValidateSet("exploratory", "balanced", "strict")]
  [string]$Strictness = "balanced",
  [string]$LlmProvider = "mock",
  [string]$LlmModel = "mock-scientist"
)

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$env:PYTHONPATH = $repoRoot.Path
Push-Location "$repoRoot\apps\api"
try {
  python -m app.services.local_runner $Question --agents $Agents --runtime $Runtime --strictness $Strictness --llm-provider $LlmProvider --llm-model $LlmModel
} finally {
  Pop-Location
}

