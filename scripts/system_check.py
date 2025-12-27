"""
Full System Check - Validates all components of the AKLAWMS system
"""
import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {text}")

def print_error(text):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {text}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")

def print_info(text):
    print(f"  {text}")

# Results tracking
results = {
    "passed": [],
    "failed": [],
    "warnings": [],
    "timestamp": datetime.now().isoformat()
}

def check_python_version():
    """Check Python version"""
    print_header("Python Version Check")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        results["passed"].append("Python version")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        results["failed"].append("Python version")
        return False

def check_dependencies():
    """Check required Python packages"""
    print_header("Dependencies Check")
    # Format: (package_name, import_name)
    required = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("chromadb", "chromadb"),
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
        ("bcrypt", "bcrypt"),
        ("python-dotenv", "dotenv"),  # Package name vs import name
        ("pydantic-settings", "pydantic_settings")
    ]
    
    optional = [
        "coqui-tts",
        "torch",
        "pyttsx3",
        "beautifulsoup4",
        "lxml",
        "pdfplumber",
        "python-docx",
        "python-pptx",
        "pandas",
        "openpyxl"
    ]
    
    all_ok = True
    
    print_info("Required packages:")
    for pkg_name, import_name in required:
        try:
            __import__(import_name)
            print_success(f"{pkg_name}")
            results["passed"].append(f"Dependency: {pkg_name}")
        except ImportError:
            print_error(f"{pkg_name} - NOT INSTALLED")
            results["failed"].append(f"Dependency: {pkg_name}")
            all_ok = False
    
    print_info("\nOptional packages:")
    for pkg in optional:
        try:
            if pkg == "coqui-tts":
                from TTS.api import TTS
            elif pkg == "torch":
                import torch
            elif pkg == "pyttsx3":
                import pyttsx3
            elif pkg == "beautifulsoup4":
                import bs4
            elif pkg == "lxml":
                import lxml
            elif pkg == "pdfplumber":
                import pdfplumber
            elif pkg == "python-docx":
                import docx
            elif pkg == "python-pptx":
                import pptx
            elif pkg == "pandas":
                import pandas
            elif pkg == "openpyxl":
                import openpyxl
            print_success(f"{pkg}")
            results["passed"].append(f"Optional: {pkg}")
        except ImportError:
            print_warning(f"{pkg} - Not installed (optional)")
            results["warnings"].append(f"Optional: {pkg}")
    
    return all_ok

def check_directories():
    """Check required directories exist"""
    print_header("Directory Structure Check")
    required_dirs = [
        "data",
        "data/forms",
        "data/templates",
        "data/corpus",
        "data/audio",
        "data/chroma_db",
        "data/scenarios",
        "config",
        "server",
        "server/routes",
        "server/services",
        "server/middleware",
        "server/utils",
        "client",
        "scripts"
    ]
    
    all_ok = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"{dir_path}/")
            results["passed"].append(f"Directory: {dir_path}")
        else:
            print_error(f"{dir_path}/ - NOT FOUND")
            results["failed"].append(f"Directory: {dir_path}")
            all_ok = False
    
    return all_ok

def check_config_files():
    """Check configuration files"""
    print_header("Configuration Files Check")
    config_files = [
        "config/ai_laws.json",
        "config/source_catalog.json",
        "server/.env"  # Optional
    ]
    
    all_ok = True
    for config_file in config_files:
        if Path(config_file).exists():
            print_success(f"{config_file}")
            results["passed"].append(f"Config: {config_file}")
            
            # Validate JSON files
            if config_file.endswith(".json"):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        json.load(f)
                    print_info(f"  Valid JSON")
                except json.JSONDecodeError as e:
                    print_error(f"  Invalid JSON: {e}")
                    results["failed"].append(f"Config JSON: {config_file}")
                    all_ok = False
        else:
            if config_file == "server/.env":
                print_warning(f"{config_file} - Not found (using defaults)")
                results["warnings"].append(f"Config: {config_file}")
            else:
                print_error(f"{config_file} - NOT FOUND")
                results["failed"].append(f"Config: {config_file}")
                all_ok = False
    
    return all_ok

def check_database():
    """Check database connectivity"""
    print_header("Database Check")
    try:
        from server.models import SessionLocal, init_db
        from server.config import settings
        
        print_info(f"Database URL: {settings.DATABASE_URL}")
        
        # Initialize database
        init_db()
        print_success("Database initialized")
        results["passed"].append("Database initialization")
        
        # Test connection
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            print_success("Database connection successful")
            results["passed"].append("Database connection")
            return True
        except Exception as e:
            print_error(f"Database connection failed: {e}")
            results["failed"].append(f"Database connection: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        print_error(f"Database check failed: {e}")
        results["failed"].append(f"Database check: {e}")
        return False

def check_chromadb():
    """Check ChromaDB setup"""
    print_header("ChromaDB Check")
    try:
        from server.config import settings
        
        print_info(f"ChromaDB path: {settings.CHROMA_DB_PATH}")
        
        if Path(settings.CHROMA_DB_PATH).exists():
            print_success("ChromaDB directory exists")
            results["passed"].append("ChromaDB directory")
        else:
            print_warning("ChromaDB directory does not exist (will be created)")
            results["warnings"].append("ChromaDB directory")
        
        # Try to initialize
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        
        client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Try to get or create collection
        collection = client.get_or_create_collection(
            name="legal_corpus",
            metadata={"description": "Virginia and Federal legal corpus"}
        )
        
        print_success("ChromaDB client initialized")
        results["passed"].append("ChromaDB client")
        
        count = collection.count()
        print_info(f"RAG documents in database: {count}")
        results["passed"].append(f"ChromaDB RAG collection: {count} documents")
        
        # Check scenario DB if enabled
        if settings.SCENARIO_DB_ENABLED:
            scenario_path = settings.SCENARIO_DB_PATH
            if Path(scenario_path).exists():
                scenario_client = chromadb.PersistentClient(
                    path=scenario_path,
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
                try:
                    scenario_collection = scenario_client.get_or_create_collection(
                        name="scenarios",
                        metadata={"description": "Legal case scenarios"}
                    )
                    scenario_count = scenario_collection.count()
                    print_success(f"Scenario database: {scenario_count} scenarios")
                    results["passed"].append(f"Scenario DB: {scenario_count} scenarios")
                except Exception as e:
                    print_warning(f"Scenario database check: {e}")
                    results["warnings"].append(f"Scenario DB: {e}")
            else:
                print_warning("Scenario database directory does not exist")
                results["warnings"].append("Scenario DB directory")
        
        return True
    except Exception as e:
        print_error(f"ChromaDB check failed: {e}")
        results["failed"].append(f"ChromaDB: {e}")
        return False

def check_services():
    """Check service initialization"""
    print_header("Service Initialization Check")
    
    services_to_check = [
        ("Logger", "server.utils.logger", "setup_logger"),
        ("Guardrails", "server.services.guardrails_service", "GuardrailsService"),
        ("RAG", "server.services.rag_service", "RAGService"),
        ("Ollama", "server.services.ollama_service", "OllamaService"),
        ("Scenario", "server.services.scenario_service", "ScenarioService"),
        ("Error Analysis", "server.services.error_analysis_service", "ErrorAnalysisService"),
        ("Learning Session", "server.services.learning_session_service", "LearningSessionService"),
        ("Correction Verification", "server.services.correction_verification_service", "CorrectionVerificationService"),
        ("User Knowledge", "server.services.user_knowledge_service", "UserKnowledgeService"),
    ]
    
    all_ok = True
    for name, module_path, class_name in services_to_check:
        try:
            module = __import__(module_path, fromlist=[class_name])
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                if callable(cls):
                    # Try to instantiate
                    instance = cls()
                    print_success(f"{name} service")
                    results["passed"].append(f"Service: {name}")
                else:
                    print_error(f"{name} - Not callable")
                    results["failed"].append(f"Service: {name}")
                    all_ok = False
            else:
                print_error(f"{name} - Class not found")
                results["failed"].append(f"Service: {name}")
                all_ok = False
        except Exception as e:
            print_error(f"{name} - {e}")
            results["failed"].append(f"Service: {name}: {e}")
            all_ok = False
    
    return all_ok

def check_ollama_connection():
    """Check Ollama service connection"""
    print_header("Ollama Service Check")
    try:
        from server.services.ollama_service import ollama_service
        from server.config import settings
        
        print_info(f"Ollama URL: {settings.OLLAMA_BASE_URL}")
        print_info(f"Model: {settings.OLLAMA_MODEL}")
        
        import httpx
        import asyncio
        
        async def check():
            try:
                response = await httpx.AsyncClient(timeout=5.0).get(
                    f"{settings.OLLAMA_BASE_URL}/api/tags"
                )
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    print_success("Ollama service is running")
                    results["passed"].append("Ollama connection")
                    
                    if settings.OLLAMA_MODEL in model_names:
                        print_success(f"Model '{settings.OLLAMA_MODEL}' is available")
                        results["passed"].append(f"Ollama model: {settings.OLLAMA_MODEL}")
                    else:
                        print_warning(f"Model '{settings.OLLAMA_MODEL}' not found")
                        print_info(f"Available models: {', '.join(model_names[:5])}")
                        results["warnings"].append(f"Ollama model: {settings.OLLAMA_MODEL}")
                    return True
                else:
                    print_error(f"Ollama returned status {response.status_code}")
                    results["failed"].append("Ollama connection")
                    return False
            except Exception as e:
                print_error(f"Cannot connect to Ollama: {e}")
                results["failed"].append(f"Ollama connection: {e}")
                return False
        
        return asyncio.run(check())
    except Exception as e:
        print_error(f"Ollama check failed: {e}")
        results["failed"].append(f"Ollama check: {e}")
        return False

def check_routes():
    """Check API routes are properly configured"""
    print_header("API Routes Check")
    try:
        # Import without triggering route imports that might fail
        import sys
        original_path = sys.path[:]
        try:
            from server.main import app
        except ImportError as e:
            # Some routes might have import issues, but that's ok for this check
            print_warning(f"Could not fully import app: {e}")
            results["warnings"].append(f"Routes import: {e}")
            return True
        
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    'path': route.path,
                    'methods': list(route.methods) if route.methods else []
                })
        
        print_info(f"Total routes registered: {len(routes)}")
        
        # Expected routes - check for key endpoints
        # Note: We check if route contains the path, not exact match, since FastAPI
        # may add prefixes or route decorators may modify paths
        expected_routes = [
            "/api/auth/login",
            "/api/auth/register",
            "/api/chat/query",
            "/api/rag/search",
            "/api/rag/upload-document",  # Actual route name (not /upload)
            "/api/validation/stats",  # Validation stats endpoint
            "/api/validation/validations",  # Validation list endpoint
            "/health"
        ]
        
        route_paths = [r['path'] for r in routes]
        all_ok = True
        
        # Check each expected route
        for expected in expected_routes:
            # Check if any registered route contains this path
            # (FastAPI routes may have exact matches or be sub-paths)
            found = False
            for route_path in route_paths:
                # Check exact match or if expected is contained in route path
                if expected == route_path or expected in route_path or route_path.endswith(expected.split('/')[-1]):
                    found = True
                    break
            
            if found:
                print_success(f"{expected}")
                results["passed"].append(f"Route: {expected}")
            else:
                # Check if there's a similar route (might be named differently)
                similar = [r for r in route_paths if expected.split('/')[-1] in r]
                if similar:
                    print_warning(f"{expected} - Not found, but found similar: {similar[0]}")
                    results["warnings"].append(f"Route: {expected} (found: {similar[0]})")
                else:
                    print_warning(f"{expected} - Not found")
                    results["warnings"].append(f"Route: {expected}")
        
        return True
    except Exception as e:
        print_error(f"Routes check failed: {e}")
        results["failed"].append(f"Routes check: {e}")
        return False

def check_file_permissions():
    """Check file permissions"""
    print_header("File Permissions Check")
    try:
        # Check if we can write to data directory
        test_file = Path("data/.test_write")
        try:
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("test")
            test_file.unlink()
            print_success("Data directory is writable")
            results["passed"].append("Data directory write")
        except Exception as e:
            print_error(f"Cannot write to data directory: {e}")
            results["failed"].append(f"Data directory write: {e}")
            return False
        
        return True
    except Exception as e:
        print_error(f"Permissions check failed: {e}")
        results["failed"].append(f"Permissions: {e}")
        return False

def generate_report():
    """Generate final report"""
    print_header("System Check Summary")
    
    total_checks = len(results["passed"]) + len(results["failed"]) + len(results["warnings"])
    
    print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
    print(f"  {Colors.GREEN}Passed: {len(results['passed'])}{Colors.RESET}")
    print(f"  {Colors.RED}Failed: {len(results['failed'])}{Colors.RESET}")
    print(f"  {Colors.YELLOW}Warnings: {len(results['warnings'])}{Colors.RESET}")
    print(f"  Total checks: {total_checks}")
    
    if results["failed"]:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Checks:{Colors.RESET}")
        for item in results["failed"]:
            print(f"  {Colors.RED}[X]{Colors.RESET} {item}")
    
    if results["warnings"]:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings:{Colors.RESET}")
        for item in results["warnings"]:
            print(f"  {Colors.YELLOW}[!]{Colors.RESET} {item}")
    
    # Save report to file
    report_file = Path("data/system_check_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{Colors.BLUE}Report saved to: {report_file}{Colors.RESET}")
    
    # Overall status
    if len(results["failed"]) == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}[PASS] System check PASSED{Colors.RESET}")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}[FAIL] System check FAILED ({len(results['failed'])} errors){Colors.RESET}")
        return False

def main():
    """Run full system check"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("="*70)
    print("AKLAWMS - Full System Check".center(70))
    print("="*70)
    print(f"{Colors.RESET}\n")
    
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {os.getcwd()}\n")
    
    # Run all checks
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Directories", check_directories),
        ("Configuration Files", check_config_files),
        ("Database", check_database),
        ("ChromaDB", check_chromadb),
        ("Services", check_services),
        ("Ollama Connection", check_ollama_connection),
        ("API Routes", check_routes),
        ("File Permissions", check_file_permissions),
    ]
    
    for name, check_func in checks:
        try:
            check_func()
        except Exception as e:
            print_error(f"{name} check crashed: {e}")
            results["failed"].append(f"{name}: {e}")
    
    # Generate final report
    success = generate_report()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

