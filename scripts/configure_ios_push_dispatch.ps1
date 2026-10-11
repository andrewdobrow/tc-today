# Add only the new function section to existing production Supabase config.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$config = Join-Path $root 'supabase\config.toml'
if (-not (Test-Path -LiteralPath $config)) { throw "Missing config at $config" }
$current = Get-Content -LiteralPath $config -Raw
$marker = '(?m)^\s*\[functions\.push-dispatch\]\s*$'
if ($current -match $marker) {
    $start = [regex]::Match($current, $marker).Index
    $after = [regex]::Match($current.Substring($start + 1), '(?m)^\s*\[')
    $end = if ($after.Success) { $start + 1 + $after.Index } else { $current.Length }
    $section = $current.Substring($start, $end - $start)
    if ($section -notmatch '(?m)^\s*verify_jwt\s*=\s*false\s*(?:#.*)?$') {
        throw 'push-dispatch section exists with incompatible JWT configuration; check it before deploying.'
    }
    Write-Host 'push-dispatch configuration already exists and is correct.'
} else {
    Add-Content -LiteralPath $config -Encoding UTF8 -Value "`r`n# Manual-only TCT alert sender; validates a separate 256-bit admin secret.`r`n[functions.push-dispatch]`r`nverify_jwt = false`r`n"
    Write-Host 'Appended push-dispatch section only. Review the diff.'
}
