import logging
import os
import json
import google.generativeai as genai
import google.auth
from google.oauth2 import service_account

def process_with_gemini(json_data, continue_from=None, user_info=None):
    """
    Process JSON data with Gemini AI model.
    
    Args:
        json_data (str): JSON string to be inserted into the prompt
        continue_from (str, optional): Text to continue from if previous response was cut off
        user_info (str, optional): User information string containing name and DOB
        
    Returns:
        str: Generated document content or None if an error occurs
    """
    try:
        logging.debug("Initializing Gemini AI processing")
        
        # Check if we're in development mode
        is_development = os.environ.get("ENVIRONMENT") == "development"
        
        if is_development:
            # In development, prioritize API key authentication
            api_key = os.environ.get("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                logging.info("Development mode: Using API key authentication")
            else:
                logging.error("Development mode requires GOOGLE_API_KEY to be set")
                raise ValueError("No API key available for development mode")
        else:
            # Production mode: Try service account authentication first
            try:
                # Get auth credentials - this will use Application Default Credentials in GCP
                logging.info("Using service account authentication...")
                
                # Limited retries to avoid slow startup
                os.environ["GOOGLE_AUTH_COMPUTE_METADATA_TIMEOUT_SECONDS"] = "2"
                credentials, project_id = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                genai.configure(credentials=credentials)
                logging.info(f"Using service account authentication with project: {project_id}")
            except Exception as e:
                # Fallback to API key if service account fails
                logging.warning(f"Service account auth failed: {str(e)}, trying API key...")
                api_key = os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    logging.info("Using API key authentication as fallback")
                else:
                    logging.error("Authentication failed. No service account or API key available.")
                    raise ValueError("No authentication method available")
        
        # Select the model (use the pro model for best quality)
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Prepare prompt text
        if continue_from:
            logging.info("Continuing generation from previous truncated response")
            prompt = f"The previous response was cut off. Please continue from:\n\n{continue_from}"
            system_instruction = "Continue the document from where it was cut off. Maintain the same formatting, style, and tone."
        else:
            # Create message with JSON data inserted into the template
            user_info_section = f"\nUser Information: {user_info}\n" if user_info else ""
            
            prompt = f"""You'll receive a list of reflections in JSON format. Each object contains:
- \"section\": a topic category (e.g. "Childhood and Family Life")
- \"question\": a prompt
- \"answer\": the individual's response
{user_info_section}
Your task:
1. Generate a **Profile Summary** written in first person, using warm, emotionally rich language. This is a summary of the person's essence and life—do not copy long answers. Condense meaningfully.

2. Generate a **Knowledge Base Document**, organized by the "section" field.

- If a section includes at least one non-empty answer:
 - Write a few short paragraphs summarizing the key memories, insights, or feelings.
 - Never copy answers verbatim. Summarize in a conversational voice.
- If a section includes **no answers**:
 - Still include the section header.
 - Write this placeholder under it:
  > _No memories recorded in this area yet. More information is needed._

Now begin, using the JSON data below.

{json_data}"""

            system_instruction = """# Gemini Instructions for Memorial Voice Assistant (Strict Summarization & Output Format)

You are a Gemini AI assistant creating a warm, emotionally intelligent memorial profile and structured memory archive from a person's recorded reflections. This content powers a Vapi voice assistant that speaks as the individual to their loved ones after their passing.

You will receive a JSON array. Each object contains:
- `\"section\"`: A category like "Life Overview", "Love and Relationships"
- `\"question\"`: A reflection prompt
- `\"answer\"`: The individual's response

---

## Your job is to generate two labeled outputs:

### 1. Profile Summary

- Write a **first-person narrative** that captures the person's essence—their values, tone, memories, relationships, and view of life.
- Use a **warm, conversational tone**, as if they're speaking directly to someone who loves and misses them.
- **Do not introduce the response with meta text like 'Here is your profile summary:' or 'Based on the data provided...'**
- DO NOT copy long answers. Always summarize and rephrase.
- Combine insights across all sections. Do not reference the questions or sections explicitly.
- Do not fabricate facts. Do not mention birthdates.
- Include meaningful details—even for shorter answers—to preserve memory value.
- Keep this section under 600 words, written as 2–5 natural paragraphs.

### 2. Knowledge Base Document

- Organize by the `\"section\"` field. Each section becomes a heading like: `## Love and Relationships`
- For each section:
  - If there are **answered questions**, summarize and rephrase into **first-person paragraphs** with warm tone and reflection.
  - Do **not copy answers verbatim**. Rewrite into natural, heartfelt summaries.
  - Add detail even for short answers. Expand modest responses into reflective paragraphs that feel complete.
  - Use direct quotes only for brief emotional phrases (e.g. "Daddy, you're awesome."), and never more than one short quote per section.
  - If a section has **no answered questions**, include the header and insert this line:
    > _No memories recorded in this area yet. More information is needed._

---

## Output Format:

```
**Profile Summary:**

[First-person summary]

**Knowledge Base Document:**

## Life Overview  
[Condensed reflections or \"need more data\" placeholder]

## Childhood and Family Life  
...

## Love and Relationships  
...

## Success, Failure and Personal Growth  
...

## Work, Career and Business  
...

## Spirituality, Beliefs and Philosophy  
...

## Hobbies, Interests and Passions  
...

## Adversity, Resilience, and Lessons Learned  
...

## Life Legacy and Impact  
...

## Final Reflections  
...
```

---

## Output Requirements:

- Use **first person** for all writing.
- NEVER include explanation or preamble (e.g. "Here is your summary").
- NEVER include raw transcript content.
- ALWAYS rewrite even brief answers into complete emotional reflections.
- Acknowledge missing content per section with a placeholder when no valid answers are present.
- Total output should remain under ~2,500 words.
- Prioritize memory-rich, emotionally meaningful content over technical detail or long anecdotes."""

        # Configure generation settings
        generation_config = genai.GenerationConfig(
            temperature=0.2,
            top_p=0.8,
            top_k=40,
            max_output_tokens=8192,
        )
        
        # Configure safety settings to allow memorial content 
        # The most permissive settings for content generation
        safety_settings = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
        }
        
        # Generate content and collect all parts of the response
        complete_response = ""
        try:
            # Create content based on whether we're continuing or starting fresh
            if continue_from:
                # Simple prompt for continuation without system instruction
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    stream=True
                )
            else:
                # Combine system instructions with user prompt
                combined_prompt = f"{system_instruction}\n\n{prompt}"
                response = model.generate_content(
                    combined_prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                    stream=True
                )
            
            # Stream the response
            for chunk in response:
                if chunk.text:
                    complete_response += chunk.text
                    
            logging.info("Successfully generated document content")
            return complete_response
            
        except Exception as e:
            logging.error(f"Error during content generation: {str(e)}")
            # If there's an error but we have some content, return what we have
            if complete_response:
                logging.warning("Returning partial response due to generation error")
                return complete_response
            return None
            
    except Exception as e:
        logging.error(f"Error in process_with_gemini: {str(e)}", exc_info=True)
        return None

def check_for_truncation(content):
    """
    Check if the generated content appears to be truncated.
    
    Args:
        content (str): The generated document content
        
    Returns:
        tuple: (is_truncated, last_complete_section) or (False, None)
    """
    # Check if document ends with proper formatting (expected sections)
    expected_sections = [
        "## Final Reflections",
        "## Life Legacy and Impact",
        "## Adversity, Resilience, and Lessons Learned"
    ]
    
    # Check if document has Profile Summary and Knowledge Base sections
    has_profile_summary = "**Profile Summary:**" in content
    has_knowledge_base = "**Knowledge Base Document:**" in content
    
    if not (has_profile_summary and has_knowledge_base):
        # Find the last complete section or paragraph to continue from
        lines = content.split('\n')
        last_complete_line = ""
        
        for i in range(len(lines) - 1, 0, -1):
            # Find the last non-empty line to continue from
            if lines[i].strip():
                last_complete_line = lines[i]
                break
                
        return True, last_complete_line
    
    # Check if document ends with any of the expected final sections
    for section in expected_sections:
        if section in content:
            # Check if there's content after this section
            section_index = content.find(section)
            remaining_content = content[section_index + len(section):].strip()
            
            if not remaining_content or len(remaining_content) < 50:
                # Section exists but has little or no content - likely truncated
                return True, section
    
    # Document appears complete
    return False, None

