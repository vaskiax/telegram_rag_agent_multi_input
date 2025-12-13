
import logging
import io
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self):
        # DeepSeek API (for standard text operations if needed, currently unused here)
        self.deepseek_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        
        # OpenAI Client (Specifically for Vision - GPT-4o)
        # We check if OPENAI_API_KEY is set to avoid errors if user hasn't provided it yet
        self.vision_client = None
        if os.environ.get("OPENAI_API_KEY"):
             self.vision_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    def transcribe_audio(self, file_path: str) -> str:
        """
        Transcribes audio using OpenAI Whisper API.
        """
        if not self.vision_client:
             return "Error: No tengo configurada una API Key de OpenAI para audio. Por favor configura OPENAI_API_KEY."
             
        try:
            with open(file_path, "rb") as audio_file:
                transcript = self.vision_client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    language="es" # Hint for Spanish
                )
            return transcript.text
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return "Lo siento, hubo un error al transcribir el audio."

    def describe_image_from_bytes(self, image_bytes: bytes) -> str:
        """
        Uses GPT-4o to describe an image (equations, diagrams, etc).
        """
        if not self.vision_client:
             return "Error: No tengo configurada una API Key de OpenAI para ver imágenes. Por favor configura OPENAI_API_KEY."

        import base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        try:
            response = self.vision_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe detalladamente esta imagen. Si hay texto o ecuaciones matemáticas, transcríbelas en formato LaTeX y explica su significado. Sé preciso."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error describing image with GPT-4o: {e}")
            return "Hubo un error al analizar la imagen."

    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extracts text from a PDF file using pypdf.
        """
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    async def scrape_url(self, url: str) -> str:
        """
        Scrapes text content from a URL using httpx and BeautifulSoup.
        """
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove scripts and styles
            for script in soup(["script", "style"]):
                script.extract()
                
            text = soup.get_text()
            
            # Clean text (remove extra properties)
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
            return ""

import os
media_processor = MediaProcessor()
