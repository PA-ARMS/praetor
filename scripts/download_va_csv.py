"""
Download Virginia Code CSV files from law.lis.virginia.gov
These are structured database exports - much better than HTML scraping!
"""
import asyncio
import httpx
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.services.rag_service import rag_service
from server.utils.logger import setup_logger

logger = setup_logger("va_csv_download")

BASE_URL = "https://law.lis.virginia.gov"

# All Code of Virginia titles
COV_TITLES = [
    ("Title 1", "CoVTitle_1.csv", "General Provisions"),
    ("Title 2.2", "CoVTitle_2.2.csv", "Administration of Government"),
    ("Title 3.2", "CoVTitle_3.2.csv", "Agriculture, Animal Care, and Food"),
    ("Title 4.1", "CoVTitle_4.1.csv", "Alcoholic Beverage and Cannabis Control"),
    ("Title 5.1", "CoVTitle_5.1.csv", "Aviation"),
    ("Title 6.2", "CoVTitle_6.2.csv", "Financial Institutions and Services"),
    ("Title 8.01", "CoVTitle_8.01.csv", "Civil Remedies and Procedure"),
    ("Title 8.1A", "CoVTitle_8.1A.csv", "Uniform Commercial Code"),
    ("Title 8.2", "CoVTitle_8.2.csv", "Commercial Code - Sales"),
    ("Title 8.2A", "CoVTitle_8.2A.csv", "Commercial Code - Leases"),
    ("Title 8.3A", "CoVTitle_8.3A.csv", "Commercial Code - Negotiable Instruments"),
    ("Title 8.4", "CoVTitle_8.4.csv", "Commercial Code - Bank Deposits"),
    ("Title 8.4A", "CoVTitle_8.4A.csv", "Commercial Code - Funds Transfers"),
    ("Title 8.5A", "CoVTitle_8.5A.csv", "Uniform Commercial Code - Letters of Credit"),
    ("Title 8.7", "CoVTitle_8.7.csv", "Commercial Code - Warehouse Receipts"),
    ("Title 8.8A", "CoVTitle_8.8A.csv", "Commercial Code - Investment Securities"),
    ("Title 8.9A", "CoVTitle_8.9A.csv", "Commercial Code - Secured Transactions"),
    ("Title 8.10", "CoVTitle_8.10.csv", "Commercial Code - Effective Date"),
    ("Title 8.11", "CoVTitle_8.11.csv", "Commercial Code - Effective Date and Transition"),
    ("Title 8.12", "CoVTitle_8.12.csv", "Commercial Code - Controllable Electronic Records"),
    ("Title 8.13", "CoVTitle_8.13.csv", "Commercial Code - Consumer Protection"),
    ("Title 9.1", "CoVTitle_9.1.csv", "Commonwealth Public Safety"),
    ("Title 10.1", "CoVTitle_10.1.csv", "Conservation"),
    ("Title 11", "CoVTitle_11.csv", "Contracts"),
    ("Title 12.1", "CoVTitle_12.1.csv", "Conveyances"),
    ("Title 13.1", "CoVTitle_13.1.csv", "Corporations"),
    ("Title 15.2", "CoVTitle_15.2.csv", "Counties, Cities and Towns"),
    ("Title 16.1", "CoVTitle_16.1.csv", "Courts Not of Record"),
    ("Title 17.1", "CoVTitle_17.1.csv", "Courts of Record"),
    ("Title 18.2", "CoVTitle_18.2.csv", "Crimes and Offenses Generally"),
    ("Title 19.2", "CoVTitle_19.2.csv", "Criminal Procedure"),
    ("Title 20", "CoVTitle_20.csv", "Domestic Relations"),
    ("Title 21", "CoVTitle_21.csv", "Drainage, Soil Conservation, Sanitation"),
    ("Title 22.1", "CoVTitle_22.1.csv", "Education"),
    ("Title 23.1", "CoVTitle_23.1.csv", "Institutions of Higher Education"),
    ("Title 24.2", "CoVTitle_24.2.csv", "Elections"),
    ("Title 25.1", "CoVTitle_25.1.csv", "Eminent Domain"),
    ("Title 27", "CoVTitle_27.csv", "Fire Protection"),
    ("Title 28.2", "CoVTitle_28.2.csv", "Fisheries and Habitat of the Tidal Waters"),
    ("Title 29.1", "CoVTitle_29.1.csv", "Wildlife, Inland Fisheries and Boating"),
    ("Title 30", "CoVTitle_30.csv", "General Assembly"),
    ("Title 32.1", "CoVTitle_32.1.csv", "Health"),
    ("Title 33.2", "CoVTitle_33.2.csv", "Highways and Other Surface Transportation Systems"),
    ("Title 34", "CoVTitle_34.csv", "Homestead and Other Exemptions"),
    ("Title 35.1", "CoVTitle_35.1.csv", "Hotels, Restaurants, Summer Camps and Campgrounds"),
    ("Title 36", "CoVTitle_36.csv", "Housing"),
    ("Title 37.2", "CoVTitle_37.2.csv", "Behavioral Health and Developmental Services"),
    ("Title 38.2", "CoVTitle_38.2.csv", "Insurance"),
    ("Title 40.1", "CoVTitle_40.1.csv", "Labor and Employment"),
    ("Title 41.1", "CoVTitle_41.1.csv", "Legislative and Administrative Services"),
    ("Title 42.1", "CoVTitle_42.1.csv", "Libraries"),
    ("Title 43", "CoVTitle_43.csv", "Mechanics' and Certain Other Liens"),
    ("Title 44", "CoVTitle_44.csv", "Military and Emergency Laws"),
    ("Title 45.2", "CoVTitle_45.2.csv", "Mines, Minerals, and Energy"),
    ("Title 46.2", "CoVTitle_46.2.csv", "Motor Vehicles"),
    ("Title 47.1", "CoVTitle_47.1.csv", "Notaries and Out-of-State Commissioners"),
    ("Title 48", "CoVTitle_48.csv", "Nuisances"),
    ("Title 49", "CoVTitle_49.csv", "Oaths, Affirmations and Bonds"),
    ("Title 50", "CoVTitle_50.csv", "Partnerships"),
    ("Title 51.1", "CoVTitle_51.1.csv", "Pensions, Benefits, and Retirement"),
    ("Title 51.5", "CoVTitle_51.5.csv", "Persons with Disabilities"),
    ("Title 52", "CoVTitle_52.csv", "Police (State)"),
    ("Title 53.1", "CoVTitle_53.1.csv", "Prisons and Other Methods of Correction"),
    ("Title 54.1", "CoVTitle_54.1.csv", "Professions and Occupations"),
    ("Title 55.1", "CoVTitle_55.1.csv", "Property and Conveyances"),
    ("Title 56", "CoVTitle_56.csv", "Public Service Companies"),
    ("Title 57", "CoVTitle_57.csv", "Religious and Charitable Matters; Cemeteries"),
    ("Title 58.1", "CoVTitle_58.1.csv", "Taxation"),
    ("Title 59.1", "CoVTitle_59.1.csv", "Trade and Commerce"),
    ("Title 60.2", "CoVTitle_60.2.csv", "Unemployment Compensation"),
    ("Title 61.1", "CoVTitle_61.1.csv", "Warehouses, Cold Storage"),
    ("Title 62.1", "CoVTitle_62.1.csv", "Waters of the State, Ports and Harbors"),
    ("Title 63.2", "CoVTitle_63.2.csv", "Welfare (Social Services)"),
    ("Title 64.2", "CoVTitle_64.2.csv", "Wills, Trusts, and Fiduciaries"),
    ("Title 65.2", "CoVTitle_65.2.csv", "Workers' Compensation"),
    ("Title 66", "CoVTitle_66.csv", "Juvenile Justice"),
]

# Other collections
OTHER_COLLECTIONS = [
    ("Constitution", "Constitution.csv", "Constitution of Virginia"),
    ("Charters", "Charters.csv", "Virginia Charters"),
    ("Authorities", "Authorities.csv", "Virginia Authorities"),
    ("Compacts", "Compacts.csv", "Virginia Compacts"),
    ("Uncodified Acts", "UnCodifiedActs.csv", "Virginia Uncodified Acts"),
]


async def download_csv(url: str, output_path: Path) -> bool:
    """Download a CSV file"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"Downloading: {url}")
            response = await client.get(url)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)
            
            size_kb = len(response.content) / 1024
            logger.info(f"Downloaded {output_path.name}: {size_kb:.1f} KB")
            return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False


async def parse_and_index_csv(csv_path: Path, collection_name: str, collection_desc: str) -> int:
    """Parse CSV and index into RAG database"""
    count = 0
    
    try:
        # Increase field size limit for large fields
        import csv
        csv.field_size_limit(10000000)
        
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            # CSV uses comma as delimiter
            reader = csv.DictReader(f, delimiter=',')
            
            # Detect CSV format by checking column names
            first_row = next(reader, None)
            if not first_row:
                return 0
            
            # Reset reader
            f.seek(0)
            reader = csv.DictReader(f, delimiter=',')
            
            for row in reader:
                # Try different CSV formats
                section_num = ''
                title = ''
                body = ''
                
                # Format 1: Code of Virginia (Section, Title, Body)
                if 'Section' in row and 'Body' in row:
                    section_num = row.get('Section', '')
                    title = row.get('Title', '')
                    body = row.get('Body', '')
                
                # Format 2: Constitution (SectionName, SectionTitle, SectionText)
                elif 'SectionText' in row:
                    section_num = row.get('SectionName', '')
                    title = row.get('SectionTitle', '')
                    body = row.get('SectionText', '')
                    # Also check ArticleName for Constitution
                    if not title and 'ArticleName' in row:
                        title = row.get('ArticleName', '')
                
                # Format 3: Charters/Authorities (may have different structure)
                elif 'SectionText' in row or 'Text' in row:
                    section_num = row.get('Section', '') or row.get('SectionName', '')
                    title = row.get('Title', '') or row.get('SectionTitle', '') or row.get('Name', '')
                    body = row.get('Text', '') or row.get('SectionText', '') or row.get('Body', '')
                
                # Try to find any text field
                if not body:
                    for key in row.keys():
                        if 'text' in key.lower() or 'body' in key.lower() or 'content' in key.lower():
                            body = row.get(key, '')
                            break
                
                if not body or len(body) < 50:
                    continue
                
                # Strip HTML tags from body
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(body, 'html.parser')
                text = soup.get_text('\n', strip=True)
                
                if not text or len(text) < 50:
                    continue
                
                # Build citation
                citation = f"§ {section_num}" if section_num else collection_name
                
                # Build full text
                full_text = f"{citation}"
                if title:
                    full_text += f". {title}\n\n"
                else:
                    full_text += "\n\n"
                full_text += text
                
                # Add to RAG database
                metadata = {
                    "source": f"Code of Virginia {citation}",
                    "jurisdiction": "Virginia",
                    "document_type": "Statute",
                    "citation": citation,
                    "title": collection_name,
                    "catchline": title,
                    "origin_url": f"https://law.lis.virginia.gov/vacode/{section_num}/"
                }
                
                try:
                    await rag_service.add_document(text=full_text, metadata=metadata)
                    count += 1
                    
                    if count % 100 == 0:
                        logger.info(f"Indexed {count} sections from {collection_name}")
                except Exception as e:
                    logger.warning(f"Error indexing {citation}: {e}")
                    continue
        
        logger.info(f"✓ Completed {collection_name}: {count} sections indexed")
        return count
        
    except Exception as e:
        logger.error(f"Error parsing {csv_path}: {e}")
        return count


async def main():
    """Main function"""
    logger.info("="*80)
    logger.info("VIRGINIA CODE CSV DOWNLOAD AND INDEXING")
    logger.info("="*80)
    
    # Create download directory
    download_dir = Path("data/va_csv")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize RAG service
    rag_service._ensure_initialized()
    
    total_downloaded = 0
    total_indexed = 0
    
    # Download and index Code of Virginia titles
    logger.info("\n📚 Downloading Code of Virginia Titles...")
    for title_name, filename, description in COV_TITLES:
        url = f"{BASE_URL}/CSV/{filename}"
        output_path = download_dir / filename
        
        # Download if not already present
        if not output_path.exists():
            success = await download_csv(url, output_path)
            if success:
                total_downloaded += 1
            else:
                logger.warning(f"Skipping {title_name} due to download error")
                continue
        else:
            logger.info(f"Using cached: {filename}")
        
        # Parse and index
        count = await parse_and_index_csv(output_path, title_name, description)
        total_indexed += count
    
    # Download and index other collections
    logger.info("\n📜 Downloading Other Collections...")
    for coll_name, filename, description in OTHER_COLLECTIONS:
        url = f"{BASE_URL}/CSV/{filename}"
        output_path = download_dir / filename
        
        if not output_path.exists():
            success = await download_csv(url, output_path)
            if success:
                total_downloaded += 1
        else:
            logger.info(f"Using cached: {filename}")
        
        if output_path.exists():
            count = await parse_and_index_csv(output_path, coll_name, description)
            total_indexed += count
    
    logger.info("\n" + "="*80)
    logger.info("DOWNLOAD AND INDEXING COMPLETE")
    logger.info("="*80)
    logger.info(f"Files downloaded: {total_downloaded}")
    logger.info(f"Sections indexed: {total_indexed}")
    logger.info(f"CSV files saved to: {download_dir}")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())

