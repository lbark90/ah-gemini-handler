import logging
import os
import json
from google import genai
from google.genai import types

def process_with_gemini(json_data, continue_from=None, user_info=None):
    """
    Process JSON data with Gemini AI model using Google Vertex AI.
    
    Args:
        json_data (str): JSON string to be inserted into the prompt
        continue_from (str, optional): Text to continue from if previous response was cut off
        user_info (str, optional): User information string containing name and DOB
        
    Returns:
        str: Generated document content or None if an error occurs
    """
    try:
        logging.debug("Initializing Gemini AI processing")
        
        # Load service account credentials
        logging.info("Using service account authentication...")
        
        # Set up the environment variable for authentication
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "google-credentials.json"
        )
        
        # Create client with Vertex AI
        client = genai.Client(
            vertexai=True,
            project="psyched-bee-455519-d7",
            location="us-central1",
        )
        
        # User information section to include in prompt if provided
        user_info_section = f"\nUser Information: {user_info}\n" if user_info else ""
        
        # Prepare main prompt content
        if continue_from:
            # For continuation requests
            prompt_text = f"The previous response was cut off. Please continue from:\n\n{continue_from}"
        else:
            # For new generation requests
            prompt_text = f"""You'll receive a list of reflections in JSON format. Each object contains:
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
Profile Summary:

[First-person summary]

Knowledge Base Document:

Life Overview
[Condensed reflections or "need more data" placeholder]

Childhood and Family Life
...

Love and Relationships
...

Success, Failure and Personal Growth
...

Work, Career and Business
...

Spirituality, Beliefs and Philosophy
...

Hobbies, Interests and Passions
...

Adversity, Resilience, and Lessons Learned
...

Life Legacy and Impact
...

Final Reflections
...

None
Update Requirements File
You'll also need to update your requirements.txt to make sure you have the correct Google Generative AI library for Vertex AI:

Note on Authentication
This implementation assumes that your service account has the necessary permissions for Vertex AI. The error you were seeing earlier indicates authentication issues. With this implementation, you should:

Make sure your service account has the Vertex AI User role
Ensure the Vertex AI and Generative AI APIs are enabled in your GCP project
The google-credentials.json file should be properly set as an environment variable:
The implementation I've provided follows the Vertex AI approach that has stronger authentication and typically more reliable performance for production use.

---

## Output Requirements:

- Use **first person** for all writing.
- NEVER include explanation or preamble (e.g. "Here is your summary").
- NEVER include raw transcript content.
- ALWAYS rewrite even brief answers into complete emotional reflections.
- Acknowledge missing content per section with a placeholder when no valid answers are present.
- Total output should remain under ~2,500 words.
- Prioritize memory-rich, emotionally meaningful content over technical detail or long anecdotes."""

                # Create prompt part from text
        msg_part = types.Part.from_text(text=prompt_text)
        system_part = types.Part.from_text(text=system_instruction)
        
        # Set up content structure 
        contents = [
            types.Content(
                role="user",
                parts=[msg_part]
            ),
        ]
        
        # Configure generation settings with correct safety settings format
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=8192,
            response_modalities=["TEXT"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="OFF"
                )
            ],
            system_instruction=[system_part],
        )
        
        # Model to use
        model = "gemini-2.0-flash-001"
        
        # Generate and collect response
        complete_response = ""
        try:
            response_stream = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            )
            
            for chunk in response_stream:
                if hasattr(chunk, 'text'):
                    complete_response += chunk.text
            
            logging.info("Successfully generated document content")
            return complete_response
            
        except Exception as e:
            logging.error(f"Error during content generation: {str(e)}")
            if complete_response:
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