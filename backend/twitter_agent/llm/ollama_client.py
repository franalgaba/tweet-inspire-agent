"""Ollama client for local LLM integration."""

import os
from typing import Optional

import httpx
from loguru import logger


class OllamaError(Exception):
    """Custom exception for Ollama errors."""

    pass


class OllamaClient:
    """Client for interacting with Ollama local LLM."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434)
            model: Default model to use (default: llama3.2 or from env)
        """
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")

        # Setup headers for Ollama Cloud authentication
        headers = {}
        api_key = os.getenv("OLLAMA_API_KEY")
        if api_key and (
            "https://ollama.com" in self.base_url
            or self.base_url == "https://ollama.com"
        ):
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.Client(
            base_url=self.base_url, timeout=300.0, headers=headers
        )

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        stream: bool = False,
        system: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """
        Generate text using Ollama.

        Args:
            prompt: The prompt to send to the model
            model: Model name (overrides default)
            stream: Whether to stream the response
            system: System prompt/instructions
            temperature: Sampling temperature (0-1)
            top_p: Top-p sampling parameter

        Returns:
            Generated text

        Raises:
            OllamaError: If generation fails
        """
        model_name = model or self.model
        logger.debug(f"Generating text with model: {model_name}, stream: {stream}")
        try:
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                },
            }
            if system:
                payload["system"] = system

            if stream:
                # Handle streaming response
                logger.debug("Using streaming mode for generation")
                response = self.client.post("/api/generate", json=payload, stream=True)
                response.raise_for_status()
                full_text = ""
                for line in response.iter_lines():
                    if line:
                        import json

                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                full_text += chunk["response"]
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
                logger.debug(f"Generated {len(full_text)} characters via streaming")
                return full_text
            else:
                response = self.client.post("/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                result = data.get("response", "")
                logger.debug(f"Generated {len(result)} characters")
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API HTTP error: {e.response.status_code}")
            raise OllamaError(f"Ollama API error: {e.response.text}") from e
        except Exception as e:
            logger.exception("Unexpected error during Ollama generation")
            raise OllamaError(f"Unexpected error during generation: {str(e)}") from e

    def analyze_voice(self, tweets: list[str], username: str) -> str:
        """
        Analyze Twitter user's voice/persona from their tweets.

        Args:
            tweets: List of tweet texts to analyze
            username: Twitter username

        Returns:
            Analysis text describing the voice/persona
        """
        logger.info(
            f"Analyzing voice for @{username} using {len(tweets)} tweets with model: {self.model}"
        )
        # Use all tweets provided, but limit to reasonable number for LLM context (max 200)
        max_tweets_for_analysis = min(len(tweets), 200)
        tweets_text = "\n".join(
            [f"- {tweet}" for tweet in tweets[:max_tweets_for_analysis]]
        )
        if len(tweets) > max_tweets_for_analysis:
            logger.debug(
                f"Using {max_tweets_for_analysis} tweets for analysis (out of {len(tweets)} fetched)"
            )

        system_prompt = """You are an expert at analyzing natural speech patterns and conversational styles. 
Analyze the given Twitter tweets and provide a comprehensive analysis of how the user naturally expresses themselves, 
including their conversational style, natural speech patterns, sentence flow, and authentic voice."""
        user_prompt = f"""Analyze how user @{username} naturally writes and speaks based on these tweets:

{tweets_text}

Provide a detailed analysis covering:
1. Natural speech patterns - how they express thoughts (casual, direct, thoughtful, etc.)
2. Sentence structure and flow - how they naturally construct sentences
3. Conversational style - do they write like they're talking? How do they phrase things?
4. Punctuation and formatting - how they use periods, line breaks, commas, etc.
5. Vocabulary and phrasing - their natural word choices and how they phrase ideas
6. Tone and energy - how they sound (witty, serious, playful, thoughtful, etc.)
7. Unique characteristics - what makes their voice authentic and human

Focus on capturing their NATURAL way of communicating - like how they actually think and speak, not formal writing.

Format your response as a structured analysis."""

        result = self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent analysis
        )
        logger.debug(f"Voice analysis completed for @{username}")
        return result

    @staticmethod
    def _format_context_for_generation(
        context_text: str,
        original_tweet_context: Optional[str],
        vibe: Optional[str] = None,
    ) -> str:
        """
        Format context for generation with emphasis on unique value addition.

        Args:
            context_text: Full context text with research and other info
            original_tweet_context: Optional original tweet context
            vibe: Optional vibe/mood description for the generated content

        Returns:
            Formatted context string for the prompt
        """
        parts = []

        if original_tweet_context:
            parts.append(
                f"ORIGINAL TWEET (respond to this topic naturally, don't rephrase):\n{original_tweet_context}\n"
            )

        if context_text and context_text != "No additional context provided.":
            # Emphasize using research naturally - like sharing knowledge, not citing sources
            if original_tweet_context:
                parts.append(
                    f"RESEARCHED CONTEXT (use this naturally - like you know this info and are sharing a thought about it):\n{context_text}"
                )
            else:
                parts.append(f"RESEARCHED CONTEXT:\n{context_text}")

        if vibe:
            parts.append(
                f"VIBE/MOOD TO MATCH: {vibe}\n\nWrite in this specific vibe/mood while maintaining the user's natural voice and style."
            )

        return "\n".join(parts) if parts else "No additional context provided."

    def extract_topic(self, tweet_text: str) -> str:
        """
        Extract and summarize the main topic or subject from input content.

        Generates a comprehensive 5-sentence summary that captures the key topic,
        context, implications, and research angles to provide rich context for
        subsequent research and content generation.

        Args:
            tweet_text: The tweet text, thread content, or article content to analyze

        Returns:
            A 5-sentence summary capturing the topic, context, and research angles
        """
        logger.info(f"Extracting topic summary from content: {tweet_text[:100]}...")

        system_prompt = """You are an expert at analyzing social media content and extracting comprehensive topic summaries.
Your task is to generate a 5-sentence summary that:
1. Identifies the main topic or subject clearly
2. Captures the key context and background
3. Highlights important implications or angles
4. Identifies discussion points or controversies
5. Suggests research directions or related aspects

Write in clear, concise sentences. Each sentence should add distinct value.
Return ONLY the 5-sentence summary, no explanations or labels."""

        user_prompt = f"""Analyze this content and generate a comprehensive 5-sentence summary:

{tweet_text}

Provide a 5-sentence summary that:
- Clearly identifies the main topic or subject
- Explains the context and background
- Highlights key implications or angles
- Identifies discussion points or areas of interest
- Suggests what aspects might need deeper research

Write exactly 5 sentences. Each sentence should be substantial and informative:"""

        result = self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.4,  # Slightly higher for more nuanced summary
        )

        # Clean up the result - remove quotes, extra whitespace, labels, etc.
        summary = result.strip().strip('"').strip("'").strip()

        # Remove common prefixes/labels that LLMs might add
        prefixes_to_remove = [
            "Summary:",
            "Topic Summary:",
            "Here's the summary:",
            "The summary is:",
            "Summary:",
        ]
        for prefix in prefixes_to_remove:
            if summary.lower().startswith(prefix.lower()):
                summary = summary[len(prefix) :].strip()

        # Ensure we have proper sentence structure
        sentences = [s.strip() for s in summary.split(".") if s.strip()]
        if len(sentences) < 3:
            logger.warning(
                f"Generated summary has fewer than 3 sentences, may need refinement"
            )

        logger.info(
            f"Extracted topic summary ({len(sentences)} sentences): {summary[:150]}..."
        )
        return summary

    def generate_content(
        self,
        voice_analysis: str,
        content_context: Optional[str] = None,
        content_type: str = "tweet",
        analytics_insights: Optional[str] = None,
        calendar_hints: Optional[str] = None,
        topic: Optional[str] = None,
        original_tweet_context: Optional[str] = None,
        thread_count: Optional[int] = None,
        vibe: Optional[str] = None,
    ) -> str:
        """
        Generate Twitter content based on voice analysis and context.

        Args:
            voice_analysis: Analyzed voice/persona description
            content_context: Context from user-provided content files
            content_type: Type of content (tweet, thread, reply)
            analytics_insights: Insights from engagement analytics
            calendar_hints: Calendar/scheduling hints
            topic: Optional topic or text to generate tweet about
            original_tweet_context: Optional context of original tweet (for replies/quotes)
            thread_count: Number of tweets in thread (only used when content_type is "thread")
            vibe: Optional vibe/mood description for the generated content (e.g., "positive and excited", "skeptical")

        Returns:
            Generated content (single tweet or thread)
        """
        # Enhanced system prompt for replies/quotes vs standalone tweets
        if original_tweet_context:
            system_prompt = """You are replicating a Twitter user's authentic voice and natural way of speaking.
Your task is to craft responses that sound EXACTLY like they wrote them - natural, conversational, like their actual thoughts.

CRITICAL VOICE REPLICATION RULES:
- Match their capitalization style EXACTLY (lowercase, sentence case, etc.)
- Use their natural vocabulary, sentence structure, and phrasing patterns from their actual tweets
- Match their conversational tone - how they naturally express thoughts (casual, thoughtful, witty, etc.)
- Use their punctuation style - observe if they use periods, line breaks, question marks, etc.
- NO hashtags unless they frequently use them
- NO @mentions unless essential
- Sound NATURAL and HUMAN - like a real person thinking out loud, not polished writing
- Capture their natural speech patterns, rhythm, and flow

ABSOLUTE PROHIBITIONS:
- NEVER rephrase, restate, or paraphrase the original tweet
- NEVER use similar analogies or examples from the original tweet
- NEVER sound formal, academic, or overly polished
- NEVER sound like a parrot repeating or rephrasing
- NEVER write like an essay or article - write like a natural tweet/thought

REQUIREMENTS FOR NATURAL, VALUE-ADDED CONTENT:
- Stay on the SAME topic but explore different facets with your unique perspective
- Use researched context naturally - weave it in like you're sharing knowledge, not citing sources
- Sound like natural conversation or spontaneous thought - authentic, not crafted
- Match their way of expressing ideas - observe how they structure thoughts in their tweets
- Be genuine and authentic - like you're responding naturally to what you read
- Add value through your unique take or insight, but express it naturally"""
        else:
            system_prompt = """You are an expert at replicating a Twitter user's authentic voice and writing style.
Your task is to generate tweets that match the user's established tone, style, vocabulary, and communication patterns EXACTLY.
CRITICAL RULES:
- Write ONLY the tweet text itself - no explanations, no introductions, no meta-commentary
- Match the user's capitalization style (observe if they use lowercase, sentence case, etc.)
- Do NOT include hashtags (#) unless the user frequently uses them
- Do NOT include @mentions unless they are essential to the tweet content
- The tweet should sound like the user wrote it themselves
- Stay true to their voice, tone, and writing patterns"""

        context_parts = []
        if original_tweet_context:
            context_parts.append(f"ORIGINAL TWEET:\n{original_tweet_context}")
        if topic:
            # Check if topic contains researched information (from Perplexity)
            if "Topic:" in topic or len(topic) > 200:
                # This is researched information from Perplexity
                context_parts.append(
                    f"TOPIC INFORMATION:\n{topic}\n\nGenerate a tweet about this topic in the user's voice."
                )
            else:
                # This is just a topic string - include as instruction
                context_parts.append(
                    f"TOPIC TO WRITE ABOUT:\n{topic}\n\nGenerate a tweet about this topic in the user's voice."
                )
        if content_context:
            context_parts.append(f"User-provided content context:\n{content_context}")
        if analytics_insights:
            context_parts.append(
                f"Engagement analytics insights:\n{analytics_insights}"
            )
        if calendar_hints:
            context_parts.append(f"Calendar/scheduling hints:\n{calendar_hints}")

        context_text = (
            "\n\n".join(context_parts)
            if context_parts
            else "No additional context provided."
        )

        # Enhanced instructions based on content type
        if original_tweet_context:
            # For replies and quote tweets
            if content_type == "reply":
                instruction = """Generate a natural, conversational reply that:
- Stays on the SAME topic, but shares your unique perspective or thought about it
- Uses researched context naturally - like you're sharing something interesting you know, not citing a source
- Expresses your take as a STATEMENT or OPINION: make a bold claim, share your view, state what you think, make a connection, or assert an insight
- Be opinionated and direct - state your position clearly, don't hedge or ask questions
- Matches how they naturally write - their vocabulary, sentence flow, and way of expressing thoughts
- Sounds like a genuine human response - natural conversation, not polished writing
- Is concise and authentic (280 characters or less)
- CRITICAL: Stay on the same topic - don't branch into unrelated areas
- ABSOLUTE PROHIBITION: Do NOT rephrase or echo the original tweet
- AVOID opening questions - prefer statements and opinions
- Sound like them - natural, authentic, like their actual tweets"""
            elif content_type == "quote":
                instruction = """Generate a quote tweet (QT) with your natural commentary that:
- Stays on the SAME topic, but shares your unique thought or angle about it
- Uses researched context naturally - weave it in like you're naturally sharing knowledge or making a connection
- Expresses your view as a STATEMENT or OPINION: make a bold claim, state your position, assert what you think, or share a strong insight
- Be opinionated and direct - state your view clearly, don't hedge or ask questions
- Matches how they naturally write - their vocabulary, flow, and way of expressing ideas
- Sounds like a genuine human thought - natural and authentic, not crafted or formal
- Is concise and real (280 characters or less for your comment)
- CRITICAL: Stay on the same topic - don't go off into unrelated areas
- ABSOLUTE PROHIBITION: Do NOT summarize or echo the original tweet
- AVOID opening questions - prefer statements and opinions
- Sound like them - natural, authentic, like their actual tweets
- Format: Write ONLY your comment/commentary that would accompany the quote (the quote itself is separate)"""
            else:
                instruction = "Generate a standalone tweet about the topic in the user's voice (280 characters or less)."
        else:
            # Default thread count if not specified
            default_thread_count = thread_count if thread_count else 5
            content_type_instructions = {
                "tweet": "Generate a single tweet (280 characters or less).",
                "thread": f"""Generate a Twitter thread with EXACTLY {default_thread_count} separate tweets.

CRITICAL FORMATTING REQUIREMENTS:
- Each tweet MUST be on its own line starting with the number: "1/{default_thread_count} ", "2/{default_thread_count} ", etc.
- FIRST TWEET MUST BE A STRONG HOOK - start with a bold statement or opinionated claim that grabs attention:
  * Open with a surprising statement, bold claim, or counterintuitive insight (NOT a question)
  * Make a strong assertion or share a controversial opinion
  * Start with statements like "here's something wild...", "nobody's talking about...", "[controversial statement]—here's why", "[unexpected observation] changed how I think about...", etc.
  * Make people curious through statements, not questions - they should think "wait, tell me more"
- Each tweet should be SUBSTANTIAL (aim for 200-280 characters) - packed with ideas, not short snippets
- Each tweet must flow naturally from the previous one - create a narrative thread with connections
- Use transitional phrases or references to create continuity between tweets (prefer statements over questions)
- Each tweet should build on the previous one - like chapters in a story
- Format like this (one tweet per line):

1/{default_thread_count} [HOOK - bold statement or opinionated claim that makes people want to read more]
2/{default_thread_count} [second tweet - connects to first, continues the thought]
3/{default_thread_count} [third tweet - builds on previous, creates flow]
...

Do NOT write one long paragraph. Write {default_thread_count} separate, numbered tweets that feel connected and substantial. The first tweet MUST hook the reader with a statement, not a question.""",
                "reply": "Generate a reply tweet that is conversational and engaging (280 characters or less).",
                "quote": "Generate a quote tweet with a comment (280 characters or less for the comment).",
            }
            instruction = content_type_instructions.get(
                content_type, content_type_instructions["tweet"]
            )

        # Format context with emphasis on using research for unique value
        formatted_context = self._format_context_for_generation(
            context_text, original_tweet_context, vibe
        )

        # Different prompt structure for threads vs single tweets
        if content_type == "thread":
            user_prompt = f"""Write a Twitter thread that sounds EXACTLY like this user wrote it - natural, conversational, like their actual thoughts.

HOW THEY WRITE (analyze their REAL tweets - match their EXACT style):
{voice_analysis}

{formatted_context}

TASK: {instruction}

CRITICAL - MATCH THEIR VOICE EXACTLY:
1. Match their capitalization EXACTLY (lowercase, sentence case, etc.) - look at their actual tweets
2. Use their natural vocabulary - the exact words and phrases they use
3. Match their sentence structure - short/long sentences, how they build thoughts
4. Match their punctuation style - periods, commas, line breaks - exactly as they do
5. Sound like natural speech - exactly how they talk, not formulaic or AI-like
6. Match their rhythm - how their thoughts flow, their natural cadence

WHAT TO WRITE:
- Write EXACTLY {default_thread_count} separate tweets, each numbered 1/{default_thread_count}, 2/{default_thread_count}, etc.
- FIRST TWEET MUST BE A STRONG HOOK:
  * Start with a bold STATEMENT or opinionated claim that grabs attention - NOT a question
  * Make it intriguing enough that people will read the entire thread
  * Examples: "nobody's talking about [hidden truth]", "here's something wild about [topic]", "[controversial statement]—but here's why", "[unexpected observation] changed how I think about...", "[bold claim] and here's the data that proves it", etc.
  * The hook should hint at deeper insights in the following tweets, creating curiosity through statements
- Each tweet should be SUBSTANTIAL (aim for 200-280 characters) - rich with ideas, not brief
- Create FLOW between tweets - each one should connect to the previous:
  * Use "but", "and", "here's the thing", "meanwhile", "the kicker is", etc. to link thoughts
  * Make statements that build on the previous tweet
  * Reference ideas from previous tweets ("that's why...", "this means...", "the bigger picture...")
  * Build a narrative - like telling a story across tweets
- Be opinionated and direct - state your position clearly throughout the thread
- Each tweet should build on the previous one - don't jump topics abruptly
- Sound like their actual tweets - natural, authentic, conversational
- Use their exact writing style - match their voice perfectly
- Pack each tweet with value - don't be too brief
{f"- CRITICAL: Match the requested vibe/mood: {vibe} - express this emotional tone and attitude while staying true to their voice" if vibe else ""}

WHAT NOT TO DO:
❌ NEVER sound formal, academic, or polished - match their casual/conversational style
❌ NEVER use vocabulary they wouldn't use - match their word choices
❌ NEVER write like an essay or article - write like natural tweets
❌ NEVER write tweets that are too short or disconnected - aim for substantial content
❌ NEVER exceed 280 characters per tweet
❌ NO explanatory text - just the numbered tweets
❌ DON'T make tweets feel isolated - create clear connections between them

Format output exactly like this (one numbered tweet per line):
1/{default_thread_count} [HOOK - bold statement or opinionated claim that makes people want to read the whole thread]
2/{default_thread_count} [second tweet - connects to hook, continues the thought]
3/{default_thread_count} [third tweet - builds narrative]
...

Write the thread now:"""
        else:
            user_prompt = f"""Write a tweet that sounds EXACTLY like this user wrote it - natural, conversational, like their actual thoughts.

HOW THEY WRITE (analyze their REAL tweets):
{voice_analysis}

{formatted_context}

TASK: {instruction}

HOW TO WRITE LIKE THEM:
1. Match their capitalization EXACTLY (lowercase, sentence case, etc.)
2. Use their natural vocabulary and how they phrase things - match their actual tweets
3. Match their conversational style - how they naturally express thoughts
4. Use their punctuation and formatting - periods, line breaks, etc.
5. Sound like natural speech - authentic, spontaneous, not polished or formal
6. Match their rhythm and flow - how their sentences and thoughts flow together

WHAT TO WRITE:
1. Output ONLY the tweet text - nothing else
2. Stay within 280 characters
3. {"Stay on the SAME topic, but share your unique thought about it - use research naturally to add depth" if original_tweet_context else "Use researched context naturally to add depth"}
4. Sound natural and conversational - like you're sharing a thought, not writing an essay
5. Add value through your unique perspective, but express it naturally - like them
6. Be opinionated and direct - make statements and express your view clearly, avoid opening questions
{f"7. CRITICAL: Match the requested vibe/mood: {vibe} - express this emotional tone and attitude while staying true to their voice" if vibe else ""}

WHAT NOT TO DO:
❌ NEVER rephrase or echo the original tweet
❌ NEVER use similar analogies or examples from the original
❌ NEVER sound formal, academic, or overly polished
❌ NEVER sound like an AI or robot - sound human and natural
❌ NO explanatory prefixes
❌ AVOID opening questions - prefer statements and opinionated claims
❌ DON'T hedge or be wishy-washy - be direct and state your position

{"EXAMPLES:" if original_tweet_context else ""}
{"❌ BAD (rephrasing): 'calling privacy a meta is like saying wearing clothes is a trend'" if original_tweet_context else ""}
{"❌ BAD (too formal): 'autonomous agents are reshaping privacy frameworks, but without guardrails, they risk entrenching inequalities'" if original_tweet_context else ""}
{"✅ GOOD (natural, on-topic): Think about the actual topic naturally, share a genuine thought about it in their voice - like they would actually tweet" if original_tweet_context else ""}

Write the tweet now (ONLY the tweet text, nothing else):"""

        logger.info(f"Generating {content_type} content using model: {self.model}")
        # Use higher temperature for more natural, conversational, human-like responses
        # Especially for replies/quotes where we want spontaneous, authentic-sounding thoughts
        temperature = 0.9 if original_tweet_context else 0.85
        result = self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=temperature,  # Higher temperature for more natural, human-like generation
        )

        # Clean up the result - remove explanatory text and refusal patterns
        result = result.strip()

        # For threads, preserve the structure but clean each line
        if content_type == "thread":
            lines = result.split("\n")
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Remove common prefixes from each line
                for prefix in ["Here's a", "Tweet", "Generated", "Here is"]:
                    if line.lower().startswith(prefix.lower()):
                        line = line[len(prefix) :].strip()
                        if line.startswith(":") or line.startswith("-"):
                            line = line[1:].strip()
                cleaned_lines.append(line)
            result = "\n".join(cleaned_lines)
        else:
            # For single tweets, clean as before
            # Remove common prefixes and explanatory text
            prefixes_to_remove = [
                "Here's a generated tweet in the style of",
                "Here's a tweet",
                "Based on the analysis",
                "Here's a suggested tweet",
                "A tweet in their style:",
                "Tweet:",
                "Generated tweet:",
                "Suggested tweet:",
                "Here's",
            ]

            for prefix in prefixes_to_remove:
                if result.lower().startswith(prefix.lower()):
                    # Find the colon or newline and take everything after
                    colon_idx = result.find(":")
                    if colon_idx != -1:
                        result = result[colon_idx + 1 :].strip()
                    break

            # Remove quotes if the entire result is quoted
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1].strip()
            if result.startswith("'") and result.endswith("'"):
                result = result[1:-1].strip()

            # Remove leading/trailing explanatory phrases
            lines = result.split("\n")
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Skip lines that are clearly explanatory (short lines with explanatory phrases)
                if (
                    any(
                        phrase in line.lower()
                        for phrase in [
                            "here's",
                            "here is",
                            "based on",
                            "suggested",
                            "generated",
                            "in the style",
                            "following the",
                            "matching the",
                            "style of",
                        ]
                    )
                    and len(line) < 100
                ):
                    continue
                cleaned_lines.append(line)

            if cleaned_lines:
                result = " ".join(cleaned_lines)

        # Check for refusal patterns and try to extract actual content
        refusal_indicators = [
            "I can't assist",
            "I cannot assist",
            "I'm not able",
            "I cannot help",
            "I'm not designed",
            "as an AI",
            "I apologize, but",
            "I'm unable to",
        ]

        if any(indicator.lower() in result.lower() for indicator in refusal_indicators):
            logger.warning(
                "LLM refused to generate content - response appears to be a refusal"
            )
            logger.debug(f"Refused response: {result[:200]}")
            # Try to extract any actual content if present
            lines = result.split("\n")
            content_lines = [
                line
                for line in lines
                if not any(ind.lower() in line.lower() for ind in refusal_indicators)
                and line.strip()
                and len(line.strip()) > 10
            ]
            if content_lines:
                result = " ".join(content_lines)
            else:
                result = "Unable to generate content - LLM safety filters triggered. Try adjusting the prompt or using a different model."

        # Final cleanup - remove any remaining explanatory text
        result = result.strip()

        logger.debug(f"Content generation completed: {len(result)} characters")
        return result

    def check_available(self) -> bool:
        """
        Check if Ollama is available and the model exists.

        Returns:
            True if Ollama is accessible, False otherwise
        """
        try:
            logger.debug(f"Checking Ollama availability at {self.base_url}")
            response = self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = [model.get("name", "") for model in data.get("models", [])]
            # Check if default model is available (with or without tag)
            model_available = any(
                self.model in model or model.startswith(self.model.split(":")[0])
                for model in models
            )
            if model_available:
                logger.debug(f"Model {self.model} is available")
            else:
                logger.warning(
                    f"Model {self.model} not found in available models: {models}"
                )
            return model_available
        except Exception as e:
            logger.error(f"Failed to check Ollama availability: {str(e)}")
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
