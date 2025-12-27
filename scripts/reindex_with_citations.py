"""
Re-index existing documents to extract and store citations in metadata

This script updates all existing documents in the vector database to include
citation metadata, which enables exact citation matching in searches.

Run this after implementing citation extraction to update your existing corpus.
"""
import asyncio
from pathlib import Path
import sys

# Ensure server modules are importable when running from repo root
sys.path.append(str(Path(__file__).resolve().parents[1]))

from server.services.rag_service import rag_service
from server.utils.logger import setup_logger

logger = setup_logger("reindex_citations")


async def reindex_with_citations():
    """Re-index all documents to extract and store citations in metadata"""
    print("Starting citation re-indexing...")
    logger.info("Starting citation re-indexing...")
    
    try:
        rag_service._ensure_initialized()
        collection = rag_service.collection
        
        # Get collection stats first
        stats = rag_service.get_collection_stats()
        print(f"Database contains {stats.get('total_documents', 0)} documents")
        logger.info(f"Database contains {stats.get('total_documents', 0)} documents")
        
        # Get all documents
        all_docs = collection.get()
        ids = all_docs.get('ids', [])
        documents = all_docs.get('documents', [])
        metadatas = all_docs.get('metadatas', [])
        
        total_docs = len(ids)
        print(f"Found {total_docs} documents to process")
        logger.info(f"Found {total_docs} documents to process")
        
        if total_docs == 0:
            print("⚠ No documents found in database")
            print("You may need to ingest documents first using scripts/ingest_sources.py")
            logger.warning("No documents found in database")
            return
        
        updated_count = 0
        already_had_citation = 0
        no_citation_found = 0
        
        for i, (doc_id, text, metadata) in enumerate(zip(ids, documents, metadatas)):
            # Skip if citation already exists
            if metadata.get('citation'):
                already_had_citation += 1
                continue
            
            # Extract citation from text
            citation = rag_service._extract_citation_from_text(text)
            
            if citation:
                # Update metadata with citation
                metadata['citation'] = citation
                
                # Update document in collection
                try:
                    collection.update(
                        ids=[doc_id],
                        metadatas=[metadata]
                    )
                    updated_count += 1
                    
                    # Progress logging
                    if updated_count % 100 == 0:
                        progress_msg = f"Progress: {i+1}/{total_docs} processed, {updated_count} updated with citations..."
                        print(progress_msg)
                        logger.info(progress_msg)
                except Exception as e:
                    error_msg = f"Failed to update document {doc_id}: {e}"
                    print(f"  ⚠ {error_msg}")
                    logger.warning(error_msg)
            else:
                no_citation_found += 1
                
                # Sample a few documents without citations for debugging
                if no_citation_found <= 5:
                    sample_text = text[:500] if len(text) > 500 else text
                    source = metadata.get('source', 'Unknown')
                    print(f"  Sample document without citation (source: {source}):")
                    print(f"    Text preview: {sample_text[:200]}...")
                
                # Log progress for documents without citations too
                if (i + 1) % 500 == 0:
                    progress_msg = f"Progress: {i+1}/{total_docs} processed..."
                    print(progress_msg)
                    logger.info(progress_msg)
        
        print("\n" + "=" * 60)
        print("Re-indexing complete!")
        print("=" * 60)
        print(f"Total documents processed: {total_docs}")
        print(f"Documents updated with citations: {updated_count}")
        print(f"Documents that already had citations: {already_had_citation}")
        print(f"Documents without citations found: {no_citation_found}")
        print("=" * 60)
        
        logger.info("=" * 60)
        logger.info("Re-indexing complete!")
        logger.info(f"Total documents processed: {total_docs}")
        logger.info(f"Documents updated with citations: {updated_count}")
        logger.info(f"Documents that already had citations: {already_had_citation}")
        logger.info(f"Documents without citations found: {no_citation_found}")
        logger.info("=" * 60)
        
        if updated_count > 0:
            success_msg = f"✓ Successfully added citations to {updated_count} documents"
            print(f"\n{success_msg}")
            print("Exact citation matching should now work for these documents.")
            logger.info(success_msg)
            logger.info("Exact citation matching should now work for these documents.")
        else:
            print("\n⚠ No documents were updated. This could mean:")
            print("  - All documents already have citations")
            print("  - No citations were found in document text")
            print("  - Documents may need to be re-ingested with citation extraction")
        
    except Exception as e:
        error_msg = f"Error during re-indexing: {e}"
        print(f"\n✗ {error_msg}")
        logger.error(error_msg)
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(traceback_str)
        print("\nFull error details:")
        print(traceback_str)
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("Citation Re-indexing Script")
    print("=" * 60)
    print("This will update all documents in your vector database")
    print("to include citation metadata for exact matching.")
    print("=" * 60)
    print()
    
    try:
        import sys
        sys.stdout.flush()
        asyncio.run(reindex_with_citations())
        print("\n✓ Re-indexing completed successfully!")
        sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n⚠ Re-indexing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error during re-indexing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

