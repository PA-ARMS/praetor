"""
Scenario Service - Predictive Analysis Database
Manages scenario corpus for outcome prediction and probability analysis
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Optional
from pathlib import Path
from server.config import settings
import json
from server.services.ollama_service import ollama_service
from server.services.learning_feedback_service import learning_feedback_service
from server.utils.logger import setup_logger


class ScenarioService:
    def __init__(self):
        self.client = None
        self.collection = None
        self._query_cache = {}
        self._cache_keys = []
        self.logger = setup_logger("scenario")
        self._cache_capacity = 256

    def _ensure_initialized(self):
        """Initialize ChromaDB client and collection"""
        if self.collection is not None:
            return
        if self.client is None:
            self.client = chromadb.PersistentClient(
                path=settings.SCENARIO_DB_PATH,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
        try:
            self.collection = self.client.get_or_create_collection(
                name="scenario_corpus",
                metadata={"description": "Legal case scenarios for predictive analysis"}
            )
        except Exception as e:
            # Create a fresh collection if schema mismatch occurs
            try:
                self.client.delete_collection("scenario_corpus")
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name="scenario_corpus",
                metadata={"description": "Legal case scenarios for predictive analysis"}
            )
    
    async def add_scenario(
        self, 
        facts: str, 
        outcome: str,
        metadata: Dict,
        scenario_id: Optional[str] = None
    ):
        """Add scenario to database"""
        self._ensure_initialized()
        
        # Combine facts and outcome for embedding
        full_text = f"Facts: {facts}\n\nOutcome: {outcome}"
        if metadata.get('key_factors'):
            factors = metadata.get('key_factors', [])
            if isinstance(factors, list):
                full_text += f"\n\nKey Factors: {', '.join(factors)}"
            else:
                full_text += f"\n\nKey Factors: {factors}"
        
        # Generate embedding
        embedding = await ollama_service.embed(full_text)
        
        # Add to collection
        self.collection.add(
            embeddings=[embedding],
            documents=[full_text],
            metadatas=[metadata],
            ids=[scenario_id] if scenario_id else [f"scenario_{len(self.collection.get()['ids'])}"]
        )
    
    async def find_similar_scenarios(
        self, 
        query_facts: str, 
        n_results: int = 10,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Find similar scenarios for predictive analysis"""
        self._ensure_initialized()
        
        # Check total available scenarios and adjust n_results if needed
        total_available = 0
        try:
            # Get all IDs to count (more reliable than count() method)
            collection_data = self.collection.get()
            all_ids = collection_data.get('ids', [])
            total_available = len(all_ids) if all_ids else 0
            
            # If filters are applied, we need to check filtered count
            if filters and total_available > 0:
                # Query with filters to see how many match
                try:
                    test_query = self.collection.query(
                        query_embeddings=[[0.0] * 768],  # Dummy embedding
                        n_results=100,  # Get all
                        where=filters
                    )
                    filtered_count = len(test_query.get('ids', [[]])[0])
                    total_available = min(total_available, filtered_count)
                except Exception:
                    # If filter query fails, use total available
                    pass
            
            # Ensure we don't request more than available
            if total_available > 0:
                n_results = min(n_results, max(1, total_available))
            if n_results == 0:
                n_results = 1  # At least request 1
        except Exception as e:
            # If count fails, use requested n_results (will error if too many)
            self.logger.warning(f"Could not get scenario count: {e}")
            # Try to be safe - reduce to 5 if we can't determine
            n_results = min(n_results, 5)
            total_available = n_results  # Set a safe default
        
        # Generate query embedding
        query_embedding = await ollama_service.embed(query_facts)
        
        # Search collection (ChromaDB where clause)
        # Ensure n_results is valid (at least 1, not more than available)
        if n_results < 1:
            n_results = 1
        if total_available > 0 and n_results > total_available:
            n_results = max(1, total_available)
        
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results
        }
        if filters:
            query_params["where"] = filters
        
        try:
            raw = self.collection.query(**query_params)
        except Exception as e:
            self.logger.error(f"ChromaDB query error: {e}", exc_info=True)
            # If query fails, try with n_results=1
            if n_results > 1:
                query_params["n_results"] = 1
                raw = self.collection.query(**query_params)
            else:
                raise
        
        # Format results with outcome data
        formatted_results = []
        ids = raw.get('ids', [[]])[0]
        docs = raw.get('documents', [[]])[0]
        metas = raw.get('metadatas', [[]])[0]
        dists = raw.get('distances', [[]])[0] if raw.get('distances') else []
        
        for i, (_id, text, meta, dist) in enumerate(zip(ids, docs, metas, dists)):
            # Handle key_factors - might be string or list
            key_factors = meta.get('key_factors', [])
            if isinstance(key_factors, str):
                # If it's a comma-separated string, split it
                key_factors = [f.strip() for f in key_factors.split(',') if f.strip()]
            
            # Extract case name from text if available
            case_name = meta.get('case_name', '')
            if not case_name and text:
                # Try to extract case name from text (look for "v." pattern)
                lines = text.split('\n')[:3]
                for line in lines:
                    if ' v. ' in line or ' vs. ' in line or ' versus ' in line.lower():
                        case_name = line.strip()[:100]
                        break
            
            # Improved similarity calculation with better normalization
            if dist is not None and dist >= 0:
                # Use improved formula: better discrimination for close matches
                scale = 1.5  # Tuning parameter
                similarity_score = min(1.0, max(0.0, 1.0 / (1.0 + float(dist) / scale)))
            else:
                similarity_score = 0.5  # Default if distance is invalid
            
            # Only include fields that have actual values (not "Unknown" or empty)
            scenario_data = {
                "id": _id,
                "text": text[:2000] if text else "",  # Include more context (increased from 500)
                "metadata": meta,
                "similarity_score": similarity_score,
            }
            
            # Add outcome only if it's not "Unknown"
            outcome = meta.get('outcome', '')
            if outcome and outcome != 'Unknown':
                scenario_data["outcome"] = outcome
            
            # Add case_type only if it's not "Unknown"
            case_type = meta.get('case_type', '')
            if case_type and case_type != 'Unknown':
                scenario_data["case_type"] = case_type
            
            # Add jurisdiction only if it's not "Unknown"
            jurisdiction = meta.get('jurisdiction', '')
            if jurisdiction and jurisdiction != 'Unknown':
                scenario_data["jurisdiction"] = jurisdiction
            
            # Add citation if available
            citation = meta.get('citation', '')
            if citation:
                scenario_data["citation"] = citation
            
            # Add case name if available
            if case_name:
                scenario_data["case_name"] = case_name
            
            # Add key factors if available
            if key_factors:
                scenario_data["key_factors"] = key_factors
            
            # Add court level if available
            court_level = meta.get('court_level', '')
            if court_level and court_level != 'Unknown':
                scenario_data["court_level"] = court_level
            
            formatted_results.append(scenario_data)
        
        return formatted_results
    
    async def predict_outcome(
        self, 
        query_facts: str,
        case_type: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        db_session: Optional[object] = None  # SQLAlchemy session for learning feedback
    ) -> Dict:
        """Predict outcome probability based on similar scenarios"""
        # Build filters (ChromaDB requires $and operator for multiple filters)
        filters = None
        if case_type and jurisdiction:
            filters = {"$and": [{"case_type": case_type}, {"jurisdiction": jurisdiction}]}
        elif case_type:
            filters = {"case_type": case_type}
        elif jurisdiction:
            filters = {"jurisdiction": jurisdiction}
        
        # Find similar scenarios
        # Get total scenarios to avoid requesting more than available
        try:
            stats = self.get_collection_stats()
            total_available = stats.get('total_scenarios', 0)
            # Use more scenarios if available (up to 30 for better accuracy)
            n_results = min(30, max(5, total_available))  # Request at least 5, up to 30
        except Exception as e:
            self.logger.warning(f"Could not get stats, using default: {e}")
            n_results = 15  # Increased default
        
        # If filters are applied, we might have even fewer results
        # So we'll let find_similar_scenarios handle the final adjustment
        similar = await self.find_similar_scenarios(query_facts, n_results=n_results, filters=filters)
        
        # If no results with filters, try without filters (but still prefer filtered if available)
        if not similar and filters:
            self.logger.debug("No results with filters, trying without filters...")
            similar = await self.find_similar_scenarios(query_facts, n_results=n_results, filters=None)
        
        if not similar:
            return {
                "prediction": "Insufficient data",
                "confidence": 0.0,
                "similar_scenarios": 0,
                "outcome_probabilities": {}
            }
        
        # Calculate outcome probabilities with improved weighting
        outcome_counts = {}
        total_weight = 0
        
        # Filter out "Unknown" outcomes - they don't help prediction
        valid_scenarios = [s for s in similar 
                          if (s.get('outcome') or s.get('metadata', {}).get('outcome', 'Unknown')) != 'Unknown']
        
        # If we filtered out too many, use all (but weight Unknown lower)
        if len(valid_scenarios) < len(similar) * 0.5:
            valid_scenarios = similar
        
        for scenario in valid_scenarios:
            # Handle missing outcome field gracefully
            outcome = scenario.get('outcome') or scenario.get('metadata', {}).get('outcome', 'Unknown')
            similarity = scenario.get('similarity_score') or 0.5
            # Ensure similarity is between 0 and 1
            similarity = max(0.0, min(1.0, float(similarity)))
            
            # Improved weighting: use exponential to emphasize very similar cases
            # Also weight by case type match if available
            base_weight = similarity ** 1.5  # Less aggressive than square, but still emphasizes close matches
            
            # Boost weight if case type matches
            scenario_case_type = scenario.get('case_type') or scenario.get('metadata', {}).get('case_type')
            if case_type and scenario_case_type == case_type:
                base_weight *= 1.3  # Increased boost for case type match
            
            # Boost weight if jurisdiction matches
            scenario_jurisdiction = scenario.get('jurisdiction') or scenario.get('metadata', {}).get('jurisdiction')
            if jurisdiction and scenario_jurisdiction == jurisdiction:
                base_weight *= 1.15
            
            # Reduce weight for "Unknown" outcomes significantly
            if outcome == 'Unknown':
                base_weight *= 0.2  # Even lower weight for unknown
            
            weight = base_weight
            
            if outcome not in outcome_counts:
                outcome_counts[outcome] = 0
            outcome_counts[outcome] += weight
            total_weight += weight
        
        # Normalize to probabilities
        outcome_probabilities = {
            outcome: (count / total_weight * 100) 
            for outcome, count in outcome_counts.items()
        } if total_weight > 0 else {}
        
        # Special handling: if "Dismissed" is close to top, consider it more carefully
        # Dismissed cases often have procedural issues that might not be in similar cases
        if "Dismissed" in outcome_probabilities:
            dismissed_prob = outcome_probabilities["Dismissed"]
            if dismissed_prob >= 20 and dismissed_prob < 50:  # Dismissed is a contender
                # Check if query mentions procedural issues
                query_lower = query_facts.lower()
                procedural_keywords = ["statute of limitations", "jurisdiction", "venue", "service", 
                                      "filing", "deadline", "procedural", "dismiss", "motion to dismiss",
                                      "failure to", "lack of", "improper"]
                if any(keyword in query_lower for keyword in procedural_keywords):
                    # Boost dismissed probability if procedural issues mentioned
                    outcome_probabilities["Dismissed"] = min(100, dismissed_prob + 10)
        
        # Get most likely outcome
        # Filter out "Unknown" if we have other outcomes
        filtered_probs = {k: v for k, v in outcome_probabilities.items() if k != "Unknown"}
        if filtered_probs:
            most_likely = max(filtered_probs.items(), key=lambda x: x[1])
        elif outcome_probabilities:
            most_likely = max(outcome_probabilities.items(), key=lambda x: x[1])
        else:
            most_likely = ("Unknown", 0)
        
        # Special case: if "Dismissed" is very close to top (within 5%), prefer it for procedural cases
        if most_likely[0] != "Dismissed" and "Dismissed" in outcome_probabilities:
            dismissed_prob = outcome_probabilities["Dismissed"]
            if dismissed_prob >= most_likely[1] - 5:  # Within 5% of top
                query_lower = query_facts.lower()
                procedural_keywords = ["statute of limitations", "jurisdiction", "venue", "service", 
                                      "filing", "deadline", "procedural", "dismiss", "motion to dismiss",
                                      "failure to", "lack of", "improper"]
                if any(keyword in query_lower for keyword in procedural_keywords):
                    # Prefer dismissed for procedural cases
                    most_likely = ("Dismissed", dismissed_prob)
        
        # Calculate confidence (improved formula considering similarity, sample size, and outcome agreement)
        if not similar:
            confidence = 0.0
        else:
            # Get similarity scores (ensure they're in 0-1 range)
            similarities = [max(0, min(1, s.get('similarity_score', 0.5) or 0.5)) for s in similar]
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0.5
            
            # Sample size factor (more cases = higher confidence, up to a point)
            # Improved: logarithmic scaling for better calibration
            sample_size_factor = min(1.0, (len(similar) / 15.0) ** 0.7)  # Logarithmic scaling
            
            # Outcome agreement factor (how much the top outcome dominates)
            top_outcome_prob = most_likely[1] / 100.0 if outcome_probabilities else 0.5
            # Improved: stronger emphasis on agreement
            agreement_factor = top_outcome_prob ** 0.8  # Slightly less aggressive
            
            # Similarity quality factor (how consistent are the similarities)
            if len(similarities) > 1:
                similarity_std = (sum((s - avg_similarity) ** 2 for s in similarities) / len(similarities)) ** 0.5
                consistency_factor = 1.0 - min(0.5, similarity_std)  # Lower std = higher consistency
            else:
                consistency_factor = 0.8
            
            # Combined confidence formula (MORE CONSERVATIVE)
            # Base: average similarity (0-1) - reduced weight for more conservative scoring
            # Boosted by: sample size, outcome agreement, and consistency
            base_confidence = avg_similarity * 50  # Reduced from 60% to 50% for more conservatism
            sample_boost = sample_size_factor * 18  # Reduced from 20% to 18%
            agreement_boost = agreement_factor * 12  # Reduced from 15% to 12%
            consistency_boost = consistency_factor * 5  # Keep at 5%
            
            confidence = min(base_confidence + sample_boost + agreement_boost + consistency_boost, 90.0)  # Cap at 90% instead of 95%
            
            # More conservative minimum confidence floor based on sample size
            if len(similar) >= 15:
                confidence = max(confidence, 40.0)  # Reduced from 45% to 40%
            elif len(similar) >= 10:
                confidence = max(confidence, 30.0)  # Reduced from 35% to 30%
            elif len(similar) >= 5:
                confidence = max(confidence, 20.0)  # Reduced from 25% to 20%
            else:
                confidence = max(confidence, 10.0)  # Reduced from 15% to 10%
            
            # More conservative boost if outcome probability is very high
            if most_likely[1] >= 70:  # Increased threshold from 60% to 70%
                confidence = min(90.0, confidence + 3.0)  # Reduced boost from 5% to 3%
            
            # Additional conservatism: reduce confidence if sample size is small
            if len(similar) < 10:
                confidence = confidence * 0.9  # 10% reduction for small sample sizes
        
        # Apply learning feedback if database session provided
        warnings = []
        factor_reminders = []
        if db_session:
            try:
                enhancements = learning_feedback_service.get_prediction_enhancements(
                    case_facts=query_facts,
                    case_type=case_type,
                    jurisdiction=jurisdiction,
                    db=db_session
                )
                
                # Adjust confidence based on learned patterns
                confidence = learning_feedback_service.apply_confidence_adjustment(
                    base_confidence=confidence,
                    enhancements=enhancements,
                    case_type=case_type
                )
                
                # Add warnings if patterns suggest issues
                warnings = enhancements.get("warnings", [])
                factor_reminders = enhancements.get("factor_reminders", [])
            except Exception as e:
                self.logger.warning(f"Could not apply learning feedback: {e}")
                warnings = []
                factor_reminders = []
        
        result = {
            "prediction": most_likely[0],
            "confidence": round(confidence, 1),
            "similar_scenarios": len(similar),
            "outcome_probabilities": {k: round(v, 1) for k, v in outcome_probabilities.items()},
            "top_similar_scenarios": similar[:5]
        }
        
        # Add warnings if any
        if warnings:
            result["learning_warnings"] = warnings
        if factor_reminders:
            result["reasoning_reminders"] = sorted(set(factor_reminders))
        
        return result
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the scenario corpus"""
        self._ensure_initialized()
        collection_data = self.collection.get()
        return {
            "total_scenarios": len(collection_data['ids']),
            "collection_name": "scenario_corpus"
        }


# Singleton instance
scenario_service = ScenarioService()

