Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🚀 HVAC Predictive Maintenance Demo Runner" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Start Backend in a new window
Write-Host "1. Starting FastAPI Backend in a new window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"cd backend; py main.py`""

# Wait for backend to initialize
Write-Host "   Waiting 4 seconds for server to start..."
Start-Sleep -Seconds 4

# 2. Seed Database
Write-Host "2. Seeding initial baseline data..." -ForegroundColor Yellow
py backend/scripts/seed_database.py

# 3. Start Frontend in a new window
Write-Host "3. Starting React Frontend in a new window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit -Command `"npm run dev`""

Write-Host ""
Write-Host "✅ All systems are running!" -ForegroundColor Green
Write-Host "=========================================="
Write-Host "👉 To INJECT A FAULT during your demo, run:" -ForegroundColor White
Write-Host "   py scripts\inject_fault.py" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "👉 To REVERT BACK to normal without restarting servers, run:" -ForegroundColor White
Write-Host "   py scripts\revert_db.py" -ForegroundColor DarkCyan
Write-Host "=========================================="
