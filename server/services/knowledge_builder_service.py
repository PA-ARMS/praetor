
"""
Background Knowledge Graph Builder
This service runs in the background to systematically expand the legal knowledge graph.
"""
import asyncio
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from server.services.rag_service import rag_service
from server.services.ollama_service import ollama_service
from server.utils.logger import setup_logger

logger = setup_logger("knowledge_builder")

class KnowledgeGraphBuilder:
    def __init__(self):
        self.is_running = False
        self.synonyms_path = Path("config/legal_synonyms.json")
        self.relationships_path = Path("config/statute_relationships.json")
        self._catalog = None # Will load on start

    async def start(self):
        """Start the background builder process"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Starting Background Knowledge Graph Builder...")
        
        # Run in background loop
        asyncio.create_task(self._build_loop())

    async def _build_loop(self):
        """Main building loop"""
        while self.is_running:
            try:
                # 1. Load current state
                if not self.synonyms_path.exists() or not self.relationships_path.exists():
                    logger.warning("Config files not found. Waiting...")
                    await asyncio.sleep(60)
                    continue

                synonyms = json.loads(self.synonyms_path.read_text(encoding='utf-8'))
                relationships = json.loads(self.relationships_path.read_text(encoding='utf-8'))
                
                # 2. Identify next target
                target_citation = None
                target_term = None
                
                for term, values in synonyms.items():
                    for v in values:
                        # Find citation format
                        if re.match(r'\d+\.\d+-\d+', v):
                            if v not in relationships:
                                target_citation = v
                                target_term = term
                                break
                    if target_citation:
                        break
                
                if not target_citation:
                    logger.info("Knowledge Graph is up to date! No gaps found.")
                    await asyncio.sleep(3600) # Sleep for an hour
                    continue

                # 3. Process Target
                logger.info(f"Building relationship map for {target_citation} ({target_term})...")
                
                # Fetch text
                results = await rag_service.search(target_citation, n_results=1)
                if not results:
                    logger.warning(f"Text for {target_citation} not found in RAG. Skipping.")
                    # Mark as processed/skipped to avoid loop? 
                    # For now, just sleep and maybe we'll find it later or user adds it.
                    await asyncio.sleep(60) 
                    continue
                
                text = results[0]['text']
                
                # Generate Map
                analysis = await self._analyze_statute(target_citation, text)
                
                if analysis:
                    # Save
                    relationships[target_citation] = analysis
                    self.relationships_path.write_text(json.dumps(relationships, indent=4), encoding='utf-8')
                    
                    # Update live service
                    rag_service.STATUTE_RELATIONSHIPS = relationships
                    
                    logger.info(f"Successfully built and saved map for {target_citation}")
                else:
                    logger.error(f"Failed to generate analysis for {target_citation}")

                # Sleep to be polite to CPU
                await asyncio.sleep(10) 

            except Exception as e:
                logger.error(f"Knowledge Builder error: {e}")
                await asyncio.sleep(60)

    async def _analyze_statute(self, citation: str, text: str):
        """Ask LLM to analyze statute text"""
        prompt = f"""
        You are a Senior Virginia Legal Analyst. 
        Analyze the following Virginia Statute: {citation}
        
        STATUTE TEXT:
        {text[:3000]}
        
        Identify related Virginia Code sections. Return a JSON object with this EXACT structure:
        {{
            "title": "Short Title",
            "criminal_procedure": {{ "Citation": "Description" }},
            "collateral_consequences": {{ "Citation": "Description" }},
            "related_offenses": {{ "Citation": "Description" }}
        }}
        
        Return ONLY the JSON.
        """
        
        try:
            # Removed temperature argument as it's not supported by OllamaService.generate()
            response = await ollama_service.generate(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.error(f"LLM Analysis failed: {e}")
        return None

# Singleton
knowledge_builder = KnowledgeGraphBuilder()


