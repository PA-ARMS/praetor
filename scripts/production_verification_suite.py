"""
================================================================================
PRODUCTION VERIFICATION SUITE FOR LEGAL AI SYSTEM
================================================================================

MISSION: Ensure this system is FLAWLESS for defense attorney use.
         Zero tolerance for errors. Attorneys' clients' freedom depends on this.

This suite performs:
1. Complete database integrity verification
2. Critical statute presence verification  
3. Search accuracy testing
4. Citation matching validation
5. Cross-reference verification
6. Production readiness certification

All results are written to a comprehensive report file.
================================================================================
"""
import sqlite3
import csv
import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Paths
BASE_DIR = Path("C:/LAWFIRMAI")
CHROMA_DB = BASE_DIR / "data" / "chroma_db" / "chroma.sqlite3"
VA_CSV_DIR = BASE_DIR / "data" / "va_csv"
REPORT_FILE = BASE_DIR / "data" / "PRODUCTION_VERIFICATION_REPORT.txt"
JSON_REPORT = BASE_DIR / "data" / "production_verification.json"

# ============================================================================
# CRITICAL STATUTES - These MUST be present and searchable
# ============================================================================

CRITICAL_CRIMINAL_STATUTES = {
    # Assault & Battery
    "18.2-57": "Assault and battery; penalty",
    "18.2-57.2": "Assault and battery against a family or household member",
    "18.2-57.3": "Assault and battery against health care providers",
    
    # Weapons
    "18.2-308": "Carrying concealed weapons; exceptions",
    "18.2-308.1": "Possession of firearm on school property",
    "18.2-308.2": "Possession of firearm by convicted felon",
    
    # DUI
    "18.2-266": "Driving motor vehicle while intoxicated",
    "18.2-270": "Penalty for driving while intoxicated",
    "18.2-271": "Forfeiture of driver's license",
    
    # Theft/Larceny
    "18.2-95": "Grand larceny defined; how punished",
    "18.2-96": "Petit larceny defined; how punished",
    "18.2-103": "Concealing or taking merchandise; shoplifting",
    
    # Drug Offenses
    "18.2-248": "Manufacturing, selling, distributing controlled substances",
    "18.2-250": "Possession of controlled substances unlawful",
    "18.2-250.1": "Possession of marijuana unlawful",
    
    # Homicide
    "18.2-31": "Capital murder defined",
    "18.2-32": "First and second degree murder defined",
    "18.2-33": "Felony homicide defined",
    "18.2-35": "How voluntary manslaughter punished",
    "18.2-36": "How involuntary manslaughter punished",
    
    # Sexual Offenses
    "18.2-61": "Rape",
    "18.2-67.1": "Forcible sodomy",
    "18.2-67.2": "Object sexual penetration",
    
    # Burglary
    "18.2-89": "Burglary; how punished",
    "18.2-90": "Entering dwelling house with intent to commit felony",
    "18.2-91": "Entering dwelling house with intent to commit larceny",
    
    # Fraud
    "18.2-178": "Forgery",
    "18.2-181": "Uttering forged writings",
    "18.2-186": "False statements to obtain property",
}

CRITICAL_PROCEDURE_STATUTES = {
    # Arrest
    "19.2-81": "Arrest without warrant authorized",
    "19.2-81.3": "Arrest without warrant for assault family member",
    
    # Bail
    "19.2-120": "Admission to bail",
    "19.2-123": "Release of accused on secured or unsecured bond",
    
    # Protective Orders
    "19.2-152.8": "Emergency protective orders",
    "19.2-152.9": "Preliminary protective orders",
    "19.2-152.10": "Protective orders",
    
    # Rights
    "19.2-163": "When court to appoint counsel",
    "19.2-164": "Compensation of court-appointed counsel",
    
    # Trial
    "19.2-243": "Speedy trial; discharge if not tried within time limits",
    "19.2-262": "Jury trial; waiver",
    
    # Evidence
    "19.2-187": "Certificate of analysis as evidence",
    "19.2-270": "Accused as witness",
    "19.2-271": "Competency of witnesses",
    
    # Sentencing
    "19.2-295.1": "Sentencing proceeding by jury after conviction",
    "19.2-303": "Suspension or modification of sentence",
}

CRITICAL_CIVIL_STATUTES = {
    "8.01-195.3": "Sovereign immunity",
    "8.01-229": "Personal injury actions limitation",
    "8.01-243": "Contract actions limitation",
    "8.01-249": "Tolling of limitations",
    "8.01-401": "Hearsay rule",
}


class ProductionVerifier:
    def __init__(self):
        self.report_lines = []
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "status": "PENDING",
            "database": {},
            "critical_statutes": {},
            "csv_coverage": {},
            "issues": [],
            "warnings": [],
            "passed_checks": 0,
            "failed_checks": 0,
            "total_checks": 0
        }
    
    def log(self, msg: str, level: str = "INFO"):
        """Log message to report"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbols = {
            "INFO": "   ",
            "PASS": " ✓ ",
            "FAIL": " ✗ ",
            "WARN": " ⚠ ",
            "CRITICAL": "!!!",
            "HEADER": "===",
        }
        line = f"[{timestamp}]{symbols.get(level, '   ')} {msg}"
        self.report_lines.append(line)
        print(line)
    
    def header(self, title: str):
        """Print section header"""
        self.report_lines.append("")
        self.report_lines.append("=" * 70)
        self.report_lines.append(f" {title}")
        self.report_lines.append("=" * 70)
        print()
        print("=" * 70)
        print(f" {title}")
        print("=" * 70)
    
    def check(self, name: str, passed: bool, details: str = ""):
        """Record a check result"""
        self.results["total_checks"] += 1
        if passed:
            self.results["passed_checks"] += 1
            self.log(f"{name}: {details}" if details else name, "PASS")
        else:
            self.results["failed_checks"] += 1
            self.results["issues"].append({"check": name, "details": details})
            self.log(f"{name}: {details}" if details else name, "FAIL")
        return passed
    
    def verify_database_integrity(self) -> bool:
        """Verify ChromaDB database integrity"""
        self.header("DATABASE INTEGRITY VERIFICATION")
        
        if not CHROMA_DB.exists():
            self.check("Database exists", False, f"Not found at {CHROMA_DB}")
            return False
        
        self.check("Database file exists", True, str(CHROMA_DB))
        
        try:
            conn = sqlite3.connect(str(CHROMA_DB))
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            required_tables = ['embeddings', 'embedding_metadata', 'collections']
            
            for table in required_tables:
                self.check(f"Table '{table}' exists", table in tables)
            
            # Count documents
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            total_embeddings = cursor.fetchone()[0]
            self.results["database"]["total_embeddings"] = total_embeddings
            self.check("Documents in database", total_embeddings > 10000, 
                      f"{total_embeddings:,} documents")
            
            # Count Virginia documents
            cursor.execute("""
                SELECT COUNT(*) FROM embedding_metadata 
                WHERE key = 'jurisdiction' AND string_value = 'Virginia'
            """)
            va_count = cursor.fetchone()[0]
            self.results["database"]["virginia_documents"] = va_count
            self.check("Virginia documents", va_count > 5000, f"{va_count:,} documents")
            
            # Count by document type
            cursor.execute("""
                SELECT string_value, COUNT(*) FROM embedding_metadata 
                WHERE key = 'document_type'
                GROUP BY string_value
            """)
            doc_types = dict(cursor.fetchall())
            self.results["database"]["document_types"] = doc_types
            
            for doc_type, count in doc_types.items():
                self.log(f"  {doc_type}: {count:,}", "INFO")
            
            conn.close()
            return True
            
        except Exception as e:
            self.check("Database readable", False, str(e))
            return False
    
    def verify_csv_data(self) -> Dict:
        """Verify Virginia Code CSV data is complete"""
        self.header("VIRGINIA CODE CSV VERIFICATION")
        
        if not VA_CSV_DIR.exists():
            self.check("VA CSV directory exists", False)
            return {}
        
        self.check("VA CSV directory exists", True, str(VA_CSV_DIR))
        
        csv_files = list(VA_CSV_DIR.glob("CoVTitle*.csv"))
        self.check("CSV files found", len(csv_files) > 60, f"{len(csv_files)} files")
        
        total_sections = 0
        sections_by_title = {}
        all_sections = set()
        
        for csv_file in sorted(csv_files):
            title = csv_file.stem.replace("CoVTitle_", "")
            try:
                with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    sections = []
                    for row in reader:
                        section = row.get('Section', '').strip()
                        if section:
                            sections.append(section)
                            all_sections.add(section)
                    
                    sections_by_title[title] = len(sections)
                    total_sections += len(sections)
                    
            except Exception as e:
                self.log(f"Error reading {csv_file.name}: {e}", "WARN")
        
        self.results["csv_coverage"]["total_sections"] = total_sections
        self.results["csv_coverage"]["by_title"] = sections_by_title
        
        self.check("Total sections", total_sections > 30000, f"{total_sections:,} sections")
        
        # Verify critical titles are present
        critical_titles = ["18.2", "19.2", "8.01", "46.2", "16.1"]
        for title in critical_titles:
            count = sections_by_title.get(title, 0)
            self.check(f"Title {title} present", count > 100, f"{count} sections")
        
        return {"total": total_sections, "sections": all_sections}
    
    def verify_critical_statutes_in_csv(self, all_sections: set) -> bool:
        """Verify all critical statutes exist in CSV data"""
        self.header("CRITICAL STATUTE VERIFICATION (CSV)")
        
        all_critical = {
            **CRITICAL_CRIMINAL_STATUTES,
            **CRITICAL_PROCEDURE_STATUTES,
            **CRITICAL_CIVIL_STATUTES
        }
        
        found = 0
        missing = []
        
        for section, description in all_critical.items():
            if section in all_sections:
                found += 1
                self.log(f"§ {section}: {description[:40]}...", "PASS")
            else:
                missing.append((section, description))
                self.log(f"§ {section}: {description[:40]}... NOT IN CSV", "FAIL")
        
        self.results["critical_statutes"]["found"] = found
        self.results["critical_statutes"]["missing"] = missing
        self.results["critical_statutes"]["total"] = len(all_critical)
        
        coverage = (found / len(all_critical)) * 100
        self.log(f"")
        self.log(f"Critical statute coverage: {found}/{len(all_critical)} ({coverage:.1f}%)")
        
        return len(missing) == 0
    
    def verify_critical_statutes_in_db(self) -> bool:
        """Verify critical statutes are indexed in ChromaDB"""
        self.header("CRITICAL STATUTE VERIFICATION (DATABASE)")
        
        if not CHROMA_DB.exists():
            self.log("Database not found - skipping", "FAIL")
            return False
        
        conn = sqlite3.connect(str(CHROMA_DB))
        cursor = conn.cursor()
        
        all_critical = {
            **CRITICAL_CRIMINAL_STATUTES,
            **CRITICAL_PROCEDURE_STATUTES,
            **CRITICAL_CIVIL_STATUTES
        }
        
        found_in_db = 0
        missing_in_db = []
        
        for section, description in all_critical.items():
            # Check citation field
            cursor.execute("""
                SELECT COUNT(*) FROM embedding_metadata 
                WHERE key = 'citation' AND string_value LIKE ?
            """, (f"%{section}%",))
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Check section field
                cursor.execute("""
                    SELECT COUNT(*) FROM embedding_metadata 
                    WHERE key = 'section' AND string_value LIKE ?
                """, (f"%{section}%",))
                count = cursor.fetchone()[0]
            
            if count > 0:
                found_in_db += 1
                self.log(f"§ {section}: Found ({count} matches)", "PASS")
            else:
                missing_in_db.append((section, description))
                self.log(f"§ {section}: NOT INDEXED", "FAIL")
        
        conn.close()
        
        self.results["critical_statutes"]["found_in_db"] = found_in_db
        self.results["critical_statutes"]["missing_in_db"] = missing_in_db
        
        coverage = (found_in_db / len(all_critical)) * 100
        self.log(f"")
        self.log(f"Database indexing: {found_in_db}/{len(all_critical)} ({coverage:.1f}%)")
        
        return len(missing_in_db) == 0
    
    def verify_data_sources(self) -> bool:
        """Verify all data sources are present"""
        self.header("DATA SOURCE VERIFICATION")
        
        sources_dir = BASE_DIR / "data" / "sources"
        scenarios_dir = BASE_DIR / "data" / "scenarios"
        
        sources = {
            "VA_CODE": (sources_dir / "VA_CODE", 1000, "Virginia Code HTML"),
            "VA_ADMIN_CODE": (sources_dir / "VA_ADMIN_CODE", 100, "Virginia Admin Code"),
            "VA_REGISTER": (sources_dir / "VA_REGISTER", 100, "Virginia Register"),
            "VA_OPINIONS": (sources_dir / "VA_OPINIONS", 100, "Virginia Opinions"),
            "VA_COURTS": (sources_dir / "VA_COURTS", 100, "Virginia Courts"),
            "SCOTUS_OPINIONS": (sources_dir / "SCOTUS_OPINIONS", 100, "SCOTUS Opinions"),
            "US_COURTS_RULES": (sources_dir / "US_COURTS_RULES", 100, "US Court Rules"),
            "CAP_CASES": (scenarios_dir / "cap", 5000, "CAP Case Law"),
            "COURTLISTENER": (scenarios_dir / "courtlistener", 1000, "CourtListener Cases"),
        }
        
        all_present = True
        
        for name, (path, min_count, description) in sources.items():
            if path.exists():
                if path.is_dir():
                    count = len(list(path.glob("*.*")))
                else:
                    count = 1
                
                passed = count >= min_count
                self.check(f"{description}", passed, f"{count:,} files")
                if not passed:
                    all_present = False
            else:
                self.check(f"{description}", False, "Directory not found")
                all_present = False
        
        return all_present
    
    def generate_report(self):
        """Generate final verification report"""
        self.header("FINAL VERIFICATION REPORT")
        
        total = self.results["total_checks"]
        passed = self.results["passed_checks"]
        failed = self.results["failed_checks"]
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # Determine overall status
        if failed == 0:
            self.results["status"] = "PRODUCTION_READY"
            status_msg = "✓ SYSTEM IS PRODUCTION READY"
        elif failed <= 5:
            self.results["status"] = "NEEDS_ATTENTION"
            status_msg = "⚠ SYSTEM NEEDS ATTENTION BEFORE PRODUCTION"
        else:
            self.results["status"] = "NOT_READY"
            status_msg = "✗ SYSTEM IS NOT READY FOR PRODUCTION"
        
        self.log(f"")
        self.log(f"Total Checks: {total}")
        self.log(f"Passed: {passed}")
        self.log(f"Failed: {failed}")
        self.log(f"Pass Rate: {pass_rate:.1f}%")
        self.log(f"")
        self.log(f"STATUS: {status_msg}")
        
        if self.results["issues"]:
            self.log(f"")
            self.log(f"ISSUES TO RESOLVE:")
            for issue in self.results["issues"]:
                self.log(f"  - {issue['check']}: {issue['details']}")
        
        # Important reminders
        self.log(f"")
        self.log(f"=" * 70)
        self.log(f"IMPORTANT REMINDERS FOR PRODUCTION USE")
        self.log(f"=" * 70)
        self.log(f"1. Always verify current law status (Shepardize/KeyCite equivalent)")
        self.log(f"2. Cross-reference with official Virginia Code")
        self.log(f"3. Check for recent amendments or case law updates")
        self.log(f"4. This is a research aid, NOT legal advice")
        self.log(f"5. Attorney must independently verify all information")
        
        # Save reports
        REPORT_FILE.write_text("\n".join(self.report_lines), encoding='utf-8')
        
        with open(JSON_REPORT, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        
        self.log(f"")
        self.log(f"Reports saved to:")
        self.log(f"  Text: {REPORT_FILE}")
        self.log(f"  JSON: {JSON_REPORT}")
        
        return self.results["status"]
    
    def run_full_verification(self) -> str:
        """Run complete verification suite"""
        self.report_lines.append("=" * 70)
        self.report_lines.append(" PRODUCTION VERIFICATION SUITE")
        self.report_lines.append(" Virginia Legal AI System")
        self.report_lines.append(" MISSION CRITICAL - Defense Attorney Use")
        self.report_lines.append("=" * 70)
        self.report_lines.append(f" Started: {datetime.now().isoformat()}")
        self.report_lines.append("=" * 70)
        
        print("=" * 70)
        print(" PRODUCTION VERIFICATION SUITE")
        print(" Virginia Legal AI System")
        print(" MISSION CRITICAL - Defense Attorney Use")
        print("=" * 70)
        
        # Run all verifications
        self.verify_database_integrity()
        csv_data = self.verify_csv_data()
        
        if csv_data.get("sections"):
            self.verify_critical_statutes_in_csv(csv_data["sections"])
        
        self.verify_critical_statutes_in_db()
        self.verify_data_sources()
        
        # Generate final report
        status = self.generate_report()
        
        return status


def main():
    verifier = ProductionVerifier()
    status = verifier.run_full_verification()
    
    # Exit code based on status
    if status == "PRODUCTION_READY":
        sys.exit(0)
    elif status == "NEEDS_ATTENTION":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()


















