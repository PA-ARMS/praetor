# Prerequisites Check Script
Write-Host "Checking prerequisites for Virginia Legal AI..." -ForegroundColor Cyan
Write-Host ""

$missing = @()

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
    try {
        $pythonVersion = python --version 2>&1 | Out-String
        Write-Host "  ✓ Python found: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Python not working" -ForegroundColor Red
        $missing += "Python 3.10+"
    }
} else {
    Write-Host "  ✗ Python not found" -ForegroundColor Red
    $missing += "Python 3.10+"
}

# Check Node.js
Write-Host "Checking Node.js..." -ForegroundColor Yellow
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCmd) {
    try {
        $nodeVersion = node --version 2>&1 | Out-String
        Write-Host "  ✓ Node.js found: $nodeVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ Node.js not working" -ForegroundColor Red
        $missing += "Node.js 18+"
    }
} else {
    Write-Host "  ✗ Node.js not found" -ForegroundColor Red
    $missing += "Node.js 18+"
}

# Check npm
Write-Host "Checking npm..." -ForegroundColor Yellow
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($npmCmd) {
    try {
        $npmVersion = npm --version 2>&1 | Out-String
        Write-Host "  ✓ npm found: $npmVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ npm not working" -ForegroundColor Red
        $missing += "npm"
    }
} else {
    Write-Host "  ✗ npm not found" -ForegroundColor Red
    $missing += "npm"
}

# Check Ollama
Write-Host "Checking Ollama..." -ForegroundColor Yellow
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollamaCmd) {
    try {
        $ollamaVersion = ollama --version 2>&1 | Out-String
        Write-Host "  ✓ Ollama found: $ollamaVersion" -ForegroundColor Green
        
        $models = ollama list 2>&1 | Out-String
        if ($models -like "*llama3.1*") {
            Write-Host "  ✓ llama3.1 model available" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ llama3.1 model not found" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ✗ Ollama not working" -ForegroundColor Red
        $missing += "Ollama"
    }
} else {
    Write-Host "  ✗ Ollama not found" -ForegroundColor Red
    $missing += "Ollama"
}

Write-Host ""
if ($missing.Count -eq 0) {
    Write-Host "All prerequisites met! ✓" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Install Python dependencies: pip install -r server/requirements.txt"
    Write-Host "2. Install Node dependencies: cd client && npm install"
    Write-Host "3. Initialize data: python scripts/setup_data.py"
    Write-Host "4. Start backend: python server/main.py"
    Write-Host "5. Start frontend: cd client && npm run dev"
} else {
    Write-Host "Missing prerequisites:" -ForegroundColor Red
    foreach ($item in $missing) {
        Write-Host "  - $item" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Please install missing components. See INSTALL_REQUIREMENTS.md for instructions." -ForegroundColor Yellow
}
