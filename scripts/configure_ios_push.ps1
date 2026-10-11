# Run from the TCT website repository. Does not replace config.toml.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$config = Join-Path $root 'supabase\config.toml'
if (-not (Test-Path -LiteralPath $config)) {
    throw "Cannot find the existing supabase/config.toml at $config. Run from the correct website repo."
}
$current = Get-Content -LiteralPath $config -Raw
$marker = '(?m)^\s*\[functions\.push-device\]\s*$'
if ($current -match $marker) {
    # Validate the exact section, not a similarly named setting elsewhere.
    $sectionStart = [regex]::Match($current, $marker).Index
    $nextSection = [regex]::Match($current.Substring($sectionStart + 1), '(?m)^\s*\[')
    $sectionEnd = if ($nextSection.Success) { $sectionStart + 1 + $nextSection.Index } else { $current.Length }
    $section = $current.Substring($sectionStart, $sectionEnd - $sectionStart)
    if ($section -notmatch '(?m)^\s*verify_jwt\s*=\s*false\s*(?:#.*)?$') {
        throw 'push-device exists but verify_jwt is not false. Review this section manually before deploying.'
    }
    Write-Host 'push-device configuration is already present and correct; no file changes.'
} else {
    Add-Content -LiteralPath $config -Encoding UTF8 -Value "`r`n# Public enrollment handler validates a private per-installation secret.`r`n[functions.push-device]`r`nverify_jwt = false`r`n"
    Write-Host 'Appended only the push-device section to the existing Supabase config.'
    Write-Host 'Review with: git diff -- supabase/config.toml'
}
