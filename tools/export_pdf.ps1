# Exports a .docx to PDF with Word (same folder, same name).
# Usage (PowerShell): .\tools\export_pdf.ps1 docs\design_brief.docx
param([Parameter(Mandatory = $true)][string]$Docx)

$full = (Resolve-Path $Docx).Path
$pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
# Word gets stuck on files inside some folders, so work on a temp copy
$tmp = Join-Path $env:TEMP ("export_" + [guid]::NewGuid().ToString() + ".docx")
Copy-Item $full $tmp

$word = New-Object -ComObject Word.Application
$word.Visible = $true
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($tmp, $false, $true)
    "pages: " + $doc.ComputeStatistics(2)
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close(0)
} finally {
    $word.Quit()
    Remove-Item $tmp
}
"saved: $pdf"
