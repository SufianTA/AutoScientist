param(
  [Parameter(Mandatory = $false)]
  [string]$Question,
  [switch]$Interactive,
  [int]$Agents = 6,
  [int]$Runtime = 30,
  [ValidateSet("exploratory", "balanced", "strict")]
  [string]$Strictness = "balanced",
  [string]$LlmProvider = "mock",
  [string]$LlmModel = "mock-scientist",
  [string[]]$ModelTools = @(),
  [switch]$RealData,
  [string]$LlmApiKeyEnvVar = "",
  [string]$LlmBaseUrl = "",
  [switch]$RequireRealLlm,
  [switch]$StreamProgress,
  [switch]$NoColor,
  [ValidateSet("summary", "json", "markdown")]
  [string]$OutputFormat = "summary",
  [string]$OutputFile = "",
  [string]$ProvenanceFile = ""
)

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$apiRoot = Resolve-Path "$repoRoot\apps\api"
$env:PYTHONPATH = "$($repoRoot.Path);$($apiRoot.Path)"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Push-Location $repoRoot.Path
try {
  $args = @()
  if ($Interactive) {
    $args += "--interactive"
  } elseif ($Question) {
    $args += $Question
  } else {
    throw "Provide -Question or use -Interactive."
  }
  $args += @(
    "--agents", $Agents,
    "--runtime", $Runtime,
    "--strictness", $Strictness,
    "--llm-provider", $LlmProvider,
    "--llm-model", $LlmModel,
    "--output-format", $OutputFormat
  )
  if ($LlmApiKeyEnvVar) {
    $args += @("--llm-api-key-env-var", $LlmApiKeyEnvVar)
  }
  if ($LlmBaseUrl) {
    $args += @("--llm-base-url", $LlmBaseUrl)
  }
  if ($RequireRealLlm) {
    $args += "--require-real-llm"
  }
  if ($StreamProgress) {
    $args += "--stream-progress"
  }
  if ($NoColor) {
    $args += "--no-color"
  }
  foreach ($modelTool in $ModelTools) {
    $args += @("--model-tool", $modelTool)
  }
  if ($RealData) {
    $args += "--real-data"
  }
  if ($OutputFile) {
    $resolvedOutputFile = $OutputFile
    if (-not [System.IO.Path]::IsPathRooted($resolvedOutputFile)) {
      $resolvedOutputFile = Join-Path $repoRoot.Path $resolvedOutputFile
    }
    $args += @("--output-file", $resolvedOutputFile)
  }
  if ($ProvenanceFile) {
    $resolvedProvenanceFile = $ProvenanceFile
    if (-not [System.IO.Path]::IsPathRooted($resolvedProvenanceFile)) {
      $resolvedProvenanceFile = Join-Path $repoRoot.Path $resolvedProvenanceFile
    }
    $args += @("--provenance-file", $resolvedProvenanceFile)
  }
  python -m app.services.local_runner @args
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
} finally {
  Pop-Location
}
