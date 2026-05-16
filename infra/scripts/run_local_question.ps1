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
  [ValidateSet("summary", "json", "markdown")]
  [string]$OutputFormat = "summary",
  [string]$OutputFile = "",
  [string]$ProvenanceFile = ""
)

$repoRoot = Resolve-Path "$PSScriptRoot\..\.."
$apiRoot = Resolve-Path "$repoRoot\apps\api"
$env:PYTHONPATH = "$($repoRoot.Path);$($apiRoot.Path)"
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
  if ($ProvenanceFile) {
    $resolvedProvenanceFile = $ProvenanceFile
    if (-not [System.IO.Path]::IsPathRooted($resolvedProvenanceFile)) {
      $resolvedProvenanceFile = Join-Path $repoRoot.Path $resolvedProvenanceFile
    }
    $args += @("--provenance-file", $resolvedProvenanceFile)
  }
  python -m app.services.local_runner @args
} finally {
  Pop-Location
}
