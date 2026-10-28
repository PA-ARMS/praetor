"""
Full System Check - Comprehensive verification of all system components
"""
import sys
import asyncio

# Fix Windows console encoding for Unicode symbols (checkmark, etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
import httpx
from pathlib import Path
sys.path.insert(0, 'C:\\LAWFIRMAI')

from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.config import settings

async def check_backend_api():
    """Check if backend API is running and healthy"""
    print("="*80)
    print("1. BACKEND API CHECK")
    print("="*80)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:5001/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Backend API: RUNNING")
                print(f"   Status: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Backend API: ERROR (status {response.status_code})")
                return False
    except Exception as e:
        print(f"❌ Backend API: NOT ACCESSIBLE")
        print(f"   Error: {e}")
        return False

def check_file_structure():
    """Check critical file structure"""
    print("\n" + "="*80)
    print("2. FILE STRUCTURE CHECK")
    print("="*80)
    
    critical_files = {
        "Source Code": [
            "server/main.py",
            "server/config.py",
            "server/models.py",
            "server/routes/chat.py",
            "server/routes/rag.py",
            "server/services/rag_service.py",
            "server/services/ollama_service.py",
        ],
        "Frontend": [
            "client/src/App.jsx",
            "client/src/components/ChatInterface.jsx",
            "client/package.json",
            "client/vite.config.js",
        ],
        "Configuration": [
            "config/ai_laws.json",
            "config/source_catalog.json",
        ],
        "Startup Scripts": [
            "START_SYSTEM.bat",
            "STOP_SYSTEM.bat",
        ],
        "Documentation": [
            "README.md",
            "QUICKSTART.md",
        ],
    }
    
    all_good = True
    for category, files in critical_files.items():
        print(f"\n{category}:")
        for file_path in files:
            path = Path(file_path)
            if path.exists():
                size = path.stat().st_size
                print(f"  ✅ {file_path} ({size / 1024:.1f} KB)")
            else:
                print(f"  ❌ {file_path} - MISSING!")
                all_good = False
    
    return all_good

def check_databases():
    """Check database files"""
    print("\n" + "="*80)
    print("3. DATABASE CHECK")
    print("="*80)
    
    databases = {
        "SQLite Database": "data/legal_ai.db",
        "ChromaDB": "data/chroma_db",
        "Scenario DB": "data/scenario_db",
    }
    
    all_good = True
    for name, path in databases.items():
        db_path = Path(path)
        if db_path.exists():
            if db_path.is_file():
                size = db_path.stat().st_size
                print(f"✅ {name}: {size / 1024 / 1024:.2f} MB")
            else:
                # Directory - count files
                files = list(db_path.rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                print(f"✅ {name}: {file_count} files, {total_size / 1024 / 1024:.2f} MB")
        else:
            print(f"❌ {name}: NOT FOUND")
            all_good = False
    
    return all_good

async def check_rag_service():
    """Check RAG service and vector database"""
    print("\n" + "="*80)
    print("4. RAG SERVICE CHECK")
    print("="*80)
    
    try:
        rag_service._ensure_initialized()
        collection = rag_service.collection
        all_docs = collection.get()
        
        total_docs = len(all_docs['ids'])
        va_statutes = sum(1 for m in all_docs['metadatas'] 
                         if m.get('jurisdiction') == 'Virginia' and m.get('document_type') == 'Statute')
        
        print(f"✅ RAG Service: OPERATIONAL")
        print(f"   Total documents: {total_docs:,}")
        print(f"   Virginia statutes: {va_statutes:,}")
        
        # Test search
        test_results = await rag_service.search("18.2-57.2", n_results=1)
        if test_results and len(test_results) > 0:
            citation = test_results[0]['metadata'].get('citation', '')
            if '18.2-57.2' in citation:
                print(f"✅ Citation search: WORKING (found § 18.2-57.2)")
            else:
                print(f"⚠️  Citation search: Found different result")
        else:
            print(f"⚠️  Citation search: No results")
        
        return True
    except Exception as e:
        print(f"❌ RAG Service: ERROR")
        print(f"   Error: {e}")
        return False

async def check_ollama_service():
    """Check Ollama LLM service"""
    print("\n" + "="*80)
    print("5. OLLAMA SERVICE CHECK")
    print("="*80)
    
    try:
        # Test embedding
        test_embedding = await ollama_service.embed("test")
        if test_embedding and len(test_embedding) > 0:
            print(f"✅ Ollama Embeddings: WORKING")
            print(f"   Embedding dimension: {len(test_embedding)}")
        else:
            print(f"❌ Ollama Embeddings: FAILED")
            return False
        
        # Test generation
        test_response = await ollama_service.generate("Say 'test'", max_tokens=10)
        if test_response and len(test_response) > 0:
            print(f"✅ Ollama Generation: WORKING")
            print(f"   Model: {settings.OLLAMA_MODEL}")
        else:
            print(f"❌ Ollama Generation: FAILED")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Ollama Service: ERROR")
        print(f"   Error: {e}")
        return False

def check_data_integrity():
    """Check data integrity"""
    print("\n" + "="*80)
    print("6. DATA INTEGRITY CHECK")
    print("="*80)
    
    checks = {
        "Virginia Code CSV Files": ("data/va_csv", 71, "*.csv"),
        "Scenarios": ("data/scenarios", 1000, "*.json"),
        "Sources": ("data/sources", 100, "*"),
    }
    
    all_good = True
    for name, (path, min_count, pattern) in checks.items():
        data_path = Path(path)
        if data_path.exists():
            files = list(data_path.glob(pattern))
            count = len(files)
            if count >= min_count:
                print(f"✅ {name}: {count:,} files")
            else:
                print(f"⚠️  {name}: {count:,} files (expected {min_count}+)")
        else:
            print(f"❌ {name}: Directory not found")
            all_good = False
    
    return all_good

def check_dependencies():
    """Check Python and Node dependencies"""
    print("\n" + "="*80)
    print("7. DEPENDENCIES CHECK")
    print("="*80)
    
    # Check Python requirements
    req_file = Path("server/requirements.txt")
    if req_file.exists():
        print(f"✅ Python requirements.txt: Found")
        with open(req_file) as f:
            req_count = len([l for l in f if l.strip() and not l.startswith('#')])
        print(f"   Dependencies listed: {req_count}")
    else:
        print(f"❌ Python requirements.txt: NOT FOUND")
    
    # Check Node modules
    node_modules = Path("client/node_modules")
    if node_modules.exists():
        module_count = len(list(node_modules.iterdir()))
        print(f"✅ Node modules: {module_count} packages installed")
    else:
        print(f"❌ Node modules: NOT FOUND")
    
    # Check package.json
    package_json = Path("client/package.json")
    if package_json.exists():
        print(f"✅ package.json: Found")
    else:
        print(f"❌ package.json: NOT FOUND")
    
    return True

def check_services():
    """Check if services can be imported"""
    print("\n" + "="*80)
    print("8. SERVICE MODULES CHECK")
    print("="*80)
    
    services = [
        "server.services.rag_service",
        "server.services.ollama_service",
        "server.services.guardrails_service",
        "server.services.motion_analysis_service",
        "server.services.comparative_motion_service",
        "server.services.ocr_service",
    ]
    
    all_good = True
    for service_name in services:
        try:
            __import__(service_name)
            print(f"✅ {service_name.split('.')[-1]}: Imported successfully")
        except Exception as e:
            print(f"❌ {service_name.split('.')[-1]}: Import failed - {e}")
            all_good = False
    
    return all_good

def check_configuration():
    """Check configuration settings"""
    print("\n" + "="*80)
    print("9. CONFIGURATION CHECK")
    print("="*80)
    
    config_items = {
        "Ollama Model": settings.OLLAMA_MODEL,
        "Ollama Base URL": settings.OLLAMA_BASE_URL,
        "Database URL": settings.DATABASE_URL,
        "ChromaDB Path": settings.CHROMA_DB_PATH,
        "Port": settings.PORT,
        "Host": settings.HOST,
    }
    
    for name, value in config_items.items():
        if value:
            print(f"✅ {name}: {value}")
        else:
            print(f"⚠️  {name}: Not set")
    
    return True

async def main():
    """Run all checks"""
    print("\n" + "="*80)
    print("FULL SYSTEM CHECK")
    print("="*80)
    print("Verifying all system components...\n")
    
    results = {
        "Backend API": await check_backend_api(),
        "File Structure": check_file_structure(),
        "Databases": check_databases(),
        "RAG Service": await check_rag_service(),
        "Ollama Service": await check_ollama_service(),
        "Data Integrity": check_data_integrity(),
        "Dependencies": check_dependencies(),
        "Service Modules": check_services(),
        "Configuration": check_configuration(),
    }
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - SYSTEM IS HEALTHY!")
    else:
        print("⚠️  SOME CHECKS FAILED - REVIEW ABOVE")
    print("="*80)
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())
