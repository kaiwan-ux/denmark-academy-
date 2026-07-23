"""
AI-powered MCQ generator using RAG and Gemini/Grok APIs.
Generates new questions similar to existing ones based on learning material.
Uses multiple API keys with load balancing for better performance.
"""

import asyncio
import json
import random
import re
from hashlib import sha256
from typing import Literal
import httpx
from denmark_academy.config import get_settings
from denmark_academy.retrieval.qdrant import QdrantRepository
from denmark_academy.ai.api_key_manager import get_api_key_manager


DifficultyLevel = Literal["easy", "medium", "hard"]
TrackType = Literal["pr", "citizenship"]


class MCQGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.qdrant = QdrantRepository()
        self.timeout = self.settings.ai_request_timeout_seconds
        self.api_key_manager = get_api_key_manager()
        
        # Ensure Qdrant collections exist
        try:
            self.qdrant.ensure_collections()
        except Exception as e:
            print(f"Warning: Could not ensure Qdrant collections: {e}")

    async def generate_mcqs(
        self,
        *,
        track: TrackType,
        difficulty: DifficultyLevel,
        count: int,
        exclude_stems: list[str] | None = None,
    ) -> list[dict]:
        """Generate exactly ``count`` validated, RAG-grounded, non-repeating MCQs."""
        sample_questions = self._get_sample_questions(track, limit=5)
        learning_contexts = [context for context in self._get_diverse_learning_contexts(track, min(count, 5)) if context]
        if not learning_contexts:
            raise ValueError("RAG learning material is unavailable for the selected exam track")
        generated_questions: list[dict] = []
        existing_stems = [question.get("stem", "") for question in sample_questions if question.get("stem")]
        existing_stems.extend(stem for stem in (exclude_stems or []) if stem)
        existing_signatures = {self._question_signature(stem) for stem in existing_stems}
        learning_objectives: list[str] = []
        for attempt in range(3):
            missing = count - len(generated_questions)
            if missing <= 0:
                break
            batch_size = missing if attempt == 0 else min(20, max(missing * 2, 3))
            plan = self._provider_plan(batch_size)
            contexts = [learning_contexts[(len(generated_questions) + index + attempt) % len(learning_contexts)] for index in range(batch_size)]
            tasks = [
                self._generate_single_mcq(
                    track=track, difficulty=difficulty, learning_context=contexts[index],
                    sample_questions=sample_questions, question_number=len(generated_questions) + index + 1,
                    provider=plan[index],
                )
                for index in range(batch_size)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for index, result in enumerate(results):
                if isinstance(result, Exception) or result is None or not self._valid_question(result):
                    continue
                stem = result.get("stem", "")
                signature = self._question_signature(stem)
                objective = self._normalize_text(result.get("learning_objective", ""))
                if not signature or signature in existing_signatures:
                    continue
                if any(self._too_similar(stem, prior, threshold=0.82) for prior in existing_stems):
                    continue
                if objective and any(self._too_similar(objective, prior, threshold=0.78) for prior in learning_objectives):
                    continue
                result["question_number"] = len(generated_questions) + 1
                result["track"] = track
                result["content_sha256"] = self._content_hash(track, result)
                result["rag_grounded"] = True
                result["rag_sources"] = [
                    {"source_document_id": chunk.get("source_document_id"), "section_title": chunk.get("section_title") or chunk.get("title"), "page_start": chunk.get("page_start") or chunk.get("page")}
                    for chunk in contexts[index][:3]
                ]
                generated_questions.append(result)
                existing_signatures.add(signature)
                existing_stems.append(stem)
                if objective:
                    learning_objectives.append(objective)
                if len(generated_questions) == count:
                    break
        if len(generated_questions) != count:
            raise ValueError(f"Generated {len(generated_questions)} of {count} unique validated questions after retries")
        return generated_questions

    def _valid_question(self, question: dict) -> bool:
        choices = [self._normalize_text(question.get(key, "")) for key in ("choice_a", "choice_b", "choice_c")]
        if len(set(choices)) != 3 or any(len(choice) < 3 for choice in choices):
            return False
        lengths = [len(choice.split()) for choice in choices]
        return max(lengths) <= max(4, min(lengths) * 4) and question.get("correct_choice") in {"A", "B", "C"}
    def _provider_plan(self, count: int) -> list[Literal["gemini", "grok"]]:
        has_grok = bool(self.api_key_manager.get_grok_keys())
        has_gemini = bool(self.api_key_manager.get_gemini_keys())
        if has_grok and not has_gemini:
            return ["grok"] * count
        if has_gemini and not has_grok:
            return ["gemini"] * count
        if not has_grok and not has_gemini:
            return ["grok"] * count
        gemini_count = count // 2
        grok_count = count - gemini_count
        return (["grok"] * grok_count) + (["gemini"] * gemini_count)

    def _get_diverse_learning_contexts(self, track: TrackType, count: int) -> list[list[dict]]:
        """Get diverse learning contexts for variety in questions"""
        try:
            collection_name = "da_learning_chunks"
            
            # Check if collection exists
            if not self.qdrant.client.collection_exists(collection_name):
                print(f"Collection '{collection_name}' does not exist yet")
                return []
            
            # Get collection info
            try:
                info = self.qdrant.client.get_collection(collection_name)
                point_count = info.points_count if hasattr(info, 'points_count') else 0
                print(f"Collection '{collection_name}' has {point_count} points")
                
                if point_count == 0:
                    return []
            except Exception as e:
                print(f"Could not get collection info: {e}")
                return []
            
            # Generate diverse search queries for variety
            diverse_queries = (
                [
                    "arbejde uddannelse og hverdagsliv i Danmark",
                    "rettigheder pligter ophold og offentlige myndigheder",
                    "dansk demokrati velfærd og praktiske samfundsforhold",
                    "familieliv sundhed kommuner og integration",
                    "arbejdsmarked skat bolig og sociale regler",
                ]
                if track == "pr"
                else [
                    "Danmarks historie og historiske begivenheder",
                    "dansk kultur kunst litteratur og traditioner",
                    "Folketinget regeringen demokrati og valg",
                    "grundloven rettigheder ligestilling og danske værdier",
                    "Danmarks geografi rigsfællesskab og internationale samarbejde",
                ]
            )
            
            contexts = []
            queries_used = []
            
            # Get diverse contexts from different topics
            for i in range(count):
                # Rotate through queries with some randomization
                query = diverse_queries[i % len(diverse_queries)]
                
                # Add randomization to make results different each time
                import random
                if random.random() > 0.5 and len(diverse_queries) > 1:
                    query = random.choice(diverse_queries)
                
                queries_used.append(query)
                
                try:
                    results = self.qdrant.search(
                        query=query,
                        track_slug=track,
                        collections=["learning_chunks"],
                        limit=2  # Get 2 chunks per question for context
                    )
                    
                    chunks = [hit.payload for hit in results]
                    if chunks:
                        contexts.append(chunks)
                    else:
                        contexts.append([])
                except Exception as e:
                    print(f"Error searching with query '{query}': {e}")
                    contexts.append([])
            
            print(f"Used diverse queries: {set(queries_used)}")
            return contexts
                
        except Exception as e:
            print(f"Error getting diverse contexts: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_sample_questions(self, track: TrackType, limit: int = 5) -> list[dict]:
        """Retrieve sample questions for style reference"""
        try:
            collection_name = "da_official_questions"
            
            # Check if collection exists
            if not self.qdrant.client.collection_exists(collection_name):
                print(f"Collection '{collection_name}' does not exist yet - no data ingested")
                return []
            
            # Check collection info
            try:
                info = self.qdrant.client.get_collection(collection_name)
                point_count = info.points_count if hasattr(info, 'points_count') else 0
                print(f"Collection '{collection_name}' has {point_count} points")
                
                if point_count == 0:
                    print("Collection is empty - no questions available")
                    return []
            except Exception as e:
                print(f"Could not get collection info: {e}")
            
            # Try to search
            results = self.qdrant.search(
                query="dansk eksamen spÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¸rgsmÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¥l citizenship statsborgerskab",
                track_slug=track,
                collections=["official_questions"],
                limit=limit
            )
            
            questions = [hit.payload for hit in results]
            if questions:
                print(f"ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ Found {len(questions)} sample questions from database")
                return questions
            else:
                print("ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â No sample questions found for this track")
                return []
                
        except Exception as e:
            print(f"ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚ÂÃƒâ€¦Ã¢â‚¬â„¢ Error fetching sample questions: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_learning_context(self, track: TrackType, topic: str) -> list[dict]:
        """Retrieve relevant learning material"""
        try:
            collection_name = "da_learning_chunks"
            
            # Check if collection exists
            if not self.qdrant.client.collection_exists(collection_name):
                print(f"Collection '{collection_name}' does not exist yet - no learning material ingested")
                return []
            
            # Check collection info
            try:
                info = self.qdrant.client.get_collection(collection_name)
                point_count = info.points_count if hasattr(info, 'points_count') else 0
                print(f"Collection '{collection_name}' has {point_count} points")
                
                if point_count == 0:
                    print("Collection is empty - no learning material available")
                    return []
            except Exception as e:
                print(f"Could not get collection info: {e}")
            
            # Try to search
            results = self.qdrant.search(
                query=topic,
                track_slug=track,
                collections=["learning_chunks"],
                limit=3
            )
            
            chunks = [hit.payload for hit in results]
            if chunks:
                print(f"ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã¢â‚¬Å“ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ Found {len(chunks)} learning chunks from database")
                return chunks
            else:
                print("ÃƒÆ’Ã‚Â¢Ãƒâ€¦Ã‚Â¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â No learning material found for this topic")
                return []
                
        except Exception as e:
            print(f"ÃƒÆ’Ã‚Â¢Ãƒâ€šÃ‚ÂÃƒâ€¦Ã¢â‚¬â„¢ Error fetching learning material: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_topic_from_samples(self, samples: list[dict]) -> str:
        """Extract a common topic from sample questions"""
        if not samples:
            return "dansk samfund og kultur"
        
        # Use first question's stem as topic
        first_question = samples[0]
        return first_question.get("stem", "dansk samfund")[:100]

    async def _generate_single_mcq(
        self,
        *,
        track: TrackType,
        difficulty: DifficultyLevel,
        learning_context: list[dict],
        sample_questions: list[dict],
        question_number: int,
        provider: Literal["gemini", "grok"]
    ) -> dict | None:
        """Generate a single MCQ using AI with smart API key selection"""
        
        prompt = self._build_prompt(
            track=track,
            difficulty=difficulty,
            learning_context=learning_context,
            sample_questions=sample_questions
        )
        
        api_key = self.api_key_manager.get_next_gemini_key() if provider == "gemini" else self.api_key_manager.get_next_grok_key()
        result = None

        # Try assigned provider first. Fallback may use the other provider, but normal operation is exact half split.
        if provider == "gemini" and api_key:
            print(f"Question {question_number}: Using Gemini API")
            result = await self._call_gemini(prompt, api_key)
        elif provider == "grok" and api_key:
            print(f"Question {question_number}: Using Grok API")
            result = await self._call_grok(prompt, api_key)
        if result:
            return self._parse_ai_response(result)
        
        # Try fallback with different provider
        fallback_provider = "grok" if provider == "gemini" else "gemini"
        fallback_key = (self.api_key_manager.get_next_grok_key() 
                       if fallback_provider == "grok" 
                       else self.api_key_manager.get_next_gemini_key())
        
        if fallback_key:
            print(f"Question {question_number}: Fallback to {fallback_provider} API")
            if fallback_provider == "gemini":
                result = await self._call_gemini(prompt, fallback_key)
            else:
                result = await self._call_grok(prompt, fallback_key)
        
        if result:
            return self._parse_ai_response(result)
        
        print(f"Question {question_number}: All API attempts failed")
        return None

    def _build_prompt(
        self,
        *,
        track: TrackType,
        difficulty: DifficultyLevel,
        learning_context: list[dict],
        sample_questions: list[dict]
    ) -> str:
        """Build a strictly RAG-grounded, track-specific Danish exam prompt."""
        if not learning_context:
            raise ValueError("RAG context is required for AI MCQ generation")

        track_name = "Permanent Residence (PR)" if track == "pr" else "Citizenship"
        track_rules = (
            "PR-sporet skal følge mønstret for prøven i dansk samfund, hverdagsliv, "
            "rettigheder, pligter, arbejde og praktiske offentlige institutioner. "
            "Undgå spørgsmål, der er særlige for statsborgerskabsprøvens historiske detaljeniveau."
            if track == "pr"
            else
            "Statsborgerskabssporet skal følge indfødsretsprøvens mønster med dansk historie, "
            "kultur, demokrati, samfundsforhold og værdier. Bland ikke PR-sporets praktiske fokus ind."
        )
        difficulty_desc = {
            "easy": "et direkte faktaspørgsmål, hvis svar står tydeligt i kilden",
            "medium": "et forståelsesspørgsmål, der kræver at to oplysninger i kilden forbindes",
            "hard": "et præcist anvendelses- eller sammenligningsspørgsmål, stadig fuldt dokumenteret af kilden",
        }[difficulty]

        context_parts = []
        for index, chunk in enumerate(learning_context[:3], start=1):
            text = str(chunk.get("text") or chunk.get("content") or "").strip()
            if not text:
                continue
            title = chunk.get("section_title") or chunk.get("title") or "Officielt læremateriale"
            pages = chunk.get("page_start") or chunk.get("page") or "ukendt"
            context_parts.append(f"KILDE {index} — {title}, side {pages}:\n{text[:1400]}")
        if not context_parts:
            raise ValueError("Retrieved RAG chunks contained no usable text")
        context_text = "\n\n".join(context_parts)

        sample_parts = []
        for index, question in enumerate(sample_questions[:3], start=1):
            choices = question.get("choices") or {}
            sample_parts.append(
                f"STILEKSEMPEL {index}: {question.get('stem', '')}\n"
                f"A: {choices.get('A', question.get('choice_a', ''))}\n"
                f"B: {choices.get('B', question.get('choice_b', ''))}\n"
                f"C: {choices.get('C', question.get('choice_c', ''))}"
            )
        sample_text = "\n\n".join(sample_parts) or "Ingen stileksempler tilgængelige."

        return f"""Du udarbejder ét nyt dansk multiple-choice-spørgsmål til {track_name}-prøven.

SPORSPECIFIKT MØNSTER:
{track_rules}

AUTORITATIVE RAG-KILDER:
{context_text}

OFFICIELLE STILEKSEMPLER (kun form og sværhedsgrad — kopier aldrig indhold):
{sample_text}

KRAV:
1. Spørgsmålet og det korrekte svar skal kunne dokumenteres direkte fra RAG-kilderne ovenfor.
2. Opfind aldrig fakta, årstal, institutioner eller regler, som ikke findes i kilderne.
3. Skriv naturligt og korrekt dansk.
4. Lav præcis tre realistiske svarmuligheder og kun ét korrekt svar.
   De forkerte svar skal være troværdige, samme type og omtrent samme detaljeringsniveau som det korrekte.
5. Niveauet skal være {difficulty_desc}.
6. Spørgsmålet skal være nyt og må ikke teste samme formulering eller læringsmål som stileksemplerne.
   Angiv ét kort, præcist learning_objective, så systemet kan håndhæve konceptmæssig variation.
7. Hold PR og Citizenship strengt adskilt efter det valgte prøvemønster.
8. Forklar kort svaret og angiv hvilken KILDE der dokumenterer det.

Returnér kun gyldig JSON:
{{
  "stem": "Spørgsmålet",
  "choice_a": "Svar A",
  "choice_b": "Svar B",
  "choice_c": "Svar C",
  "correct_choice": "A",
  "explanation": "Forklaring med henvisning til KILDE 1",
  "grounding_source": "KILDE 1",
  "learning_objective": "Det præcise begreb som spørgsmålet tester"
}}"""

    async def _call_gemini(self, prompt: str, api_key=None) -> str | None:
        """Call Gemini API with specified or default key"""
        if not api_key:
            api_key = self.settings.gemini_api_key
        
        if not api_key:
            print("Gemini API key not configured")
            return None
        
        try:
            url = f"{self.settings.gemini_base_url}/models/{self.settings.gemini_model}:generateContent"
            headers = {"Content-Type": "application/json"}
            params = {"key": api_key.get_secret_value()}
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.9,  # Higher temperature for more variety
                    "maxOutputTokens": 800,
                    "topP": 0.95  # Add topP for diversity
                }
            }
            
            # Use a longer timeout for API calls
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, json=payload, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    print(f"Gemini API success, got {len(content)} chars")
                    return content
                else:
                    print(f"Gemini API error: {response.status_code} - {response.text[:200]}")
        except httpx.TimeoutException:
            print("Gemini API timeout - request took too long")
        except Exception as e:
            print(f"Gemini API exception: {e}")
        
        return None

    async def _call_grok(self, prompt: str, api_key=None) -> str | None:
        """Call Grok API (OpenAI-compatible) with specified or default key"""
        if not api_key:
            api_key = self.settings.grok_api_key
        
        if not api_key:
            print("Grok API key not configured")
            return None
        
        try:
            url = f"{self.settings.grok_base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.get_secret_value()}"
            }
            
            payload = {
                "model": self.settings.grok_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,  # Higher temperature for more variety
                "max_tokens": 800,
                "top_p": 0.95  # Add top_p for diversity
            }
            
            # Use a longer timeout for API calls
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"Grok API success, got {len(content)} chars")
                    return content
                else:
                    print(f"Grok API error: {response.status_code} - {response.text[:200]}")
        except httpx.TimeoutException:
            print("Grok API timeout - request took too long")
        except Exception as e:
            print(f"Grok API exception: {e}")
        
        return None

    def _parse_ai_response(self, response: str) -> dict | None:
        """Parse AI response and extract MCQ"""
        try:
            print(f"Parsing AI response: {response[:200]}...")
            
            # Extract JSON from response (might have markdown code blocks)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                print("No JSON found in response")
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate required fields
            required = ["stem", "choice_a", "choice_b", "choice_c", "correct_choice"]
            missing = [field for field in required if field not in data]
            if missing:
                print(f"Missing required fields: {missing}")
                return None
            
            # Normalize correct_choice
            correct = data["correct_choice"].upper()
            if correct not in ["A", "B", "C"]:
                print(f"Invalid correct_choice: {correct}, defaulting to A")
                correct = "A"
            
            result = {
                "question_number": 1,  # Will be set properly by the calling function
                "stem": str(data["stem"]).strip(),
                "choice_a": str(data["choice_a"]).strip(),
                "choice_b": str(data["choice_b"]).strip(),
                "choice_c": str(data["choice_c"]).strip(),
                "correct_choice": correct,
                "explanation": str(data.get("explanation", "")).strip(),
                "learning_objective": str(data.get("learning_objective", "")).strip(),
                "generated": True
            }
            
            print(f"Successfully parsed question: {result['stem'][:50]}...")
            return result
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    def _question_signature(self, text: str) -> str:
        normalized = self._normalize_text(text)
        return sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""

    def _content_hash(self, track: TrackType, question: dict) -> str:
        raw = "|".join([
            track,
            self._normalize_text(question.get("stem", "")),
            self._normalize_text(question.get("choice_a", "")),
            self._normalize_text(question.get("choice_b", "")),
            self._normalize_text(question.get("choice_c", "")),
        ])
        return sha256(raw.encode("utf-8")).hexdigest()

    def _too_similar(self, left: str, right: str, threshold: float = 0.72) -> bool:
        left_tokens = set(self._normalize_text(left).split())
        right_tokens = set(self._normalize_text(right).split())
        if not left_tokens or not right_tokens:
            return False
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        return overlap >= threshold

    def _normalize_text(self, value: str) -> str:
        cleaned = re.sub(r"[^\wÃ¦Ã¸Ã¥Ã†Ã˜Ã…]+", " ", value.lower(), flags=re.UNICODE)
        return re.sub(r"\s+", " ", cleaned).strip()




