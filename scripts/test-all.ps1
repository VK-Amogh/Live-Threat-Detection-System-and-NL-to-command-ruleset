# Run all tests and contract validations
Write-Output "Running contract tests..."
.venv\Scripts\pytest.exe tests/contracts -v
if ($LASTEXITCODE -ne 0) {
    Write-Error "Contract tests failed!"
    exit 1
}

Write-Output "Checking contract exports and drift..."
.venv\Scripts\python.exe scripts/export-contracts.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Contract export failed!"
    exit 1
}

Write-Output "[SUCCESS] All tests and contract checks passed."
