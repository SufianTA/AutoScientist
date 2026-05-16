param(
  [Parameter(Mandatory = $true)]
  [string]$Question,
  [int]$Agents = 6,
  [int]$Runtime = 30,
  [ValidateSet("exploratory", "balanced", "strict")]
  [string]$Strictness = "balanced",
  [string]$LlmProvider = "mock",
  [string]$LlmModel = "mock-scientist",
  [string[]]$ModelTools = @(),
  [ValidateSet("summary", "json", "markdown")]
  [string]$OutputFormat = "summary",
  [string]$OutputFile = ""
)

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$env:PYTHONPATH = $repoRoot.Path
Push-Location "$repoRoot\apps\api"
try {
  $args = @(
    $Question,
    "--agents", $Agents,
    "--runtime", $Runtime,
    "--strictness", $Strictness,
    "--llm-provider", $LlmProvider,
    "--llm-model", $LlmModel,
    "--output-format", $OutputFormat
  )
  foreach ($modelTool in $ModelTools) {
    $args += @("--model-tool", $modelTool)
  }
  if ($OutputFile) {
    $resolvedOutputFile = $OutputFile
    if (-not [System.IO.Path]::IsPathRooted($resolvedOutputFile)) {
      $resolvedOutputFile = Join-Path $repoRoot.Path $resolvedOutputFile
    }
    $args += @("--output-file", $resolvedOutputFile)
  }
  python -m app.services.local_runner @args
} finally {
  Pop-Location
}
