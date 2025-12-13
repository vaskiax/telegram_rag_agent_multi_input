
import logging
import os
import tempfile
import io
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from app.core.config import settings
from app.agent.graph import agent_app
from app.interface.utils import media_processor

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Hola {user_first_name}! Soy Telegram Brain Agent.\n"
        "Puedo responder preguntas basándome EXCLUSIVAMENTE en mi base de conocimientos.\n"
        "Envíame texto, audio o imágenes."
    )



# Import renderer
from app.utils.renderer import render_latex_to_image
import re

async def send_response_with_latex(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """
    Parses text for LaTeX blocks, renders them as images, and sends the message parts in order.
    Supports $$...$$ for display math. Inline math $...$ is kept as text or could be rendered too.
    For simplicity, we split by $$...$$.
    """
    # Regex to split by $$...$$, \[...\], or \(...\)
    # Group 1 captures the content including delimiters
    # We match:
    # 1. $$...$$ (Display)
    # 2. \[...\] (Display)
    # 3. \(...\) (Inline - we will render this too for visual clarity)
    parts = re.split(r'(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\(.*?\\\))', text)
    
    for part in parts:
        if not part.strip():
            continue
            
        # Check if it is a LaTeX block
        is_latex = False
        if part.startswith('$$') and part.endswith('$$'):
            is_latex = True
            content = part[2:-2].strip()
        elif part.startswith('\\[') and part.endswith('\\]'):
            is_latex = True
            content = part[2:-2].strip()
        elif part.startswith('\\(') and part.endswith('\\)'):
            is_latex = True
            content = part[2:-2].strip()
        else:
            content = part

        if not is_latex:
            # Text part
            await update.message.reply_text(part.strip())
        else:
            # LaTeX part - Apply "Smart Filter"
            # If the expression is too simple (just a variable "x" or "K"), rendering it as an image is spammy.
            # Criteria for Image:
            # 1. Contains LaTeX commands ('\')
            # 2. Contains math operators ('=', '^', '_')
            # 3. Is reasonably long (> 15 chars)
            
            # remove spaces for length check
            compact = content.replace(" ", "")
            is_complex = (
                "\\" in content or 
                "=" in content or 
                "^" in content or 
                "_" in content or
                "{" in content or
                len(compact) > 15
            )
            
            if not is_complex:
                # It's simple (e.g. "K" or "x"). Just send as text bolded or code to stand out slightly, or just plain.
                # Let's use Italic for math variables which is standard.
                await update.message.reply_text(f"_{content}_", parse_mode='Markdown')
            else:
                # Complex -> Render
                try:
                    msg = await update.message.reply_text("📐 Renderizando ecuación...")
                    image_buffer = render_latex_to_image(content)
                    await update.message.reply_photo(photo=image_buffer)
                    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
                except Exception as e:
                    logger.error(f"Error rendering LaTeX: {e}")
                    # Fallback: Send raw
                    await update.message.reply_text(f"Error renderizando ecuación:\n{part}")


# Import global task registry
from app.core.global_state import task_registry


# Import for messages
from langchain_core.messages import HumanMessage, AIMessage

# Global dictionary for chat history
# chat_id -> List[BaseMessage]
user_chat_history = {}  

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id
    
    # 1. Check for /save command
    if user_text.strip().lower().startswith("/save "):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        note_content = user_text[6:].strip()
        try:
            response = await agent_app.ainvoke({
                "question": note_content,
                "media_type": "text_note",
                "task_id": str(chat_id)
            })
            final_answer = response.get("final_answer", "Error al guardar nota.")
            await update.message.reply_text(final_answer)
        except Exception as e:
            logger.error(f"Error saving note: {e}", exc_info=True)
            await update.message.reply_text("Error al guardar la nota.")
        return

    # 2. Check for URL
    if user_text.strip().startswith("http"):
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            response = await agent_app.ainvoke({
                "question": "Ingest URL",
                "url": user_text.strip(),
                "media_type": "url",
                "task_id": str(chat_id)
            })
            final_answer = response.get("final_answer", "Error al procesar URL.")
            await update.message.reply_text(final_answer)
        except Exception as e:
            logger.error(f"Error processing URL: {e}", exc_info=True)
            await update.message.reply_text("Error al procesar el enlace.")
        return

    # 3. Regular RAG Query with Memory
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Get History
    if chat_id not in user_chat_history:
        user_chat_history[chat_id] = []
        
    history = user_chat_history[chat_id]
    
    # Check for active background task in Global Registry
    current_status = task_registry.get(str(chat_id))
    final_question = user_text
    
    if current_status:
        # Inject system status into the question for the Agent to see
        final_question = f"[SYSTEM_STATUS: Current Task = {current_status}] {user_text}"
        
    try:
        # Invoke Agent with History
        # We pass 'messages' which LangGraph will append to its state. 
        # Note: We manually manage the persistence here for simplicity.
        
        response = await agent_app.ainvoke({
            "question": final_question,
            "messages": history
        })
        final_answer = response.get("final_answer", "Error al generar respuesta.")
        
        # Update History
        history.append(HumanMessage(content=user_text))
        history.append(AIMessage(content=final_answer))
        
        # Keep last 10 messages (5 turns)
        if len(history) > 10:
            user_chat_history[chat_id] = history[-10:]
        
        # Use the new LaTeX aware sender
        await send_response_with_latex(update, context, final_answer)
        
    except Exception as e:
        logger.error(f"Error executing agent: {e}", exc_info=True)
        await update.message.reply_text("Hubo un error procesando tu solicitud.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    document = update.message.document
    
    # Check if PDF (Internal mime check mostly for logging, we accept ALL in filter)
    # But if it's clearly not a PDF/Text we might warn, but user wants generic ingestion.
    # For now, let's stick to PDF check for this specific logic path
    if document.mime_type != 'application/pdf':
        await update.message.reply_text("⚠️ Por el momento mi sistema de ingesta está optimizado para PDFs. Intentaré procesarlo, pero si falla, conviértelo a PDF.")
    
    # 1. Immediate Feedback (ACK)
    status_msg = await update.message.reply_text(f"⏳ Iniciando procesamiento de: {document.file_name} en segundo plano...")
    
    # 2. Launch Background Task
    # We pass 'context.bot' which is safe to use.
    import asyncio
    asyncio.create_task(
        process_document_background(
            chat_id=chat_id, 
            file_id=document.file_id, 
            file_name=document.file_name, 
            bot=context.bot, 
            message_id_to_edit=status_msg.message_id
        )
    )
    # 3. Return immediately to satisfy Webhook logic
    return 


async def process_document_background(chat_id: int, file_id: str, file_name: str, bot, message_id_to_edit: int):
    """
    Background task to process the document without blocking the webhook.
    """
    try:
        # Set status
        task_id = str(chat_id)
        task_registry[task_id] = f"Downloading {file_name}..."
        
        # 1. Download
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=f"⬇️ Descargando {file_name}...")
        new_file = await bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            await new_file.download_to_drive(custom_path=temp_pdf.name)
            temp_path = temp_pdf.name
            
        # 2. Ingest
        task_registry[task_id] = f"Extracting text from {file_name}..."
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=f"🧠 Ingiriendo contenido en la base de conocimientos...")
        
        response = await agent_app.ainvoke({
            "question": "Ingest PDF",
            "file_path": temp_path,
            "media_type": "pdf",
            "task_id": task_id # Pass ID down the graph
        })
        final_answer = response.get("final_answer")
        
        # 4. Final Result
        await bot.delete_message(chat_id=chat_id, message_id=message_id_to_edit)
        await bot.send_message(chat_id=chat_id, text=f"✅ {final_answer}")
        
    except Exception as e:
        logger.error(f"Error in background processing: {e}", exc_info=True)
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id_to_edit, text=f"❌ Error al procesar {file_name}: {str(e)}")
    finally:
        # Clear status
        task_id = str(chat_id)
        if task_id in task_registry:
            del task_registry[task_id]
            
        # Clean up temp file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        voice_file = await update.message.voice.get_file()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            await voice_file.download_to_drive(custom_path=temp_audio.name)
            temp_path = temp_audio.name
            
        transcript = media_processor.transcribe_audio(temp_path)
        
        # Clean up
        try:
             os.remove(temp_path)
        except:
             pass
        
        if "no está disponible" in transcript:
             await update.message.reply_text(transcript)
             return

        await update.message.reply_text(f"🎤 Oído: \"{transcript}\"")
        
        # Query the Agent with the transcript
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        response = await agent_app.ainvoke({"question": transcript})
        final_answer = response.get("final_answer", "Error al generar respuesta.")
        
        # Send formatted response
        await send_response_with_latex(update, context, final_answer)
        
    except Exception as e:
        logger.error(f"Error handling voice: {e}")
        await update.message.reply_text("Error al procesar el audio.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Same as before
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await update.message.reply_text("🖼️ Imagen recibida. Analizando...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        
        # Save to temp file for consistency
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
            await photo_file.download_to_drive(custom_path=temp_img.name)
            temp_path = temp_img.name
        
        response = await agent_app.ainvoke({
            "question": "Ingest Image",
            "file_path": temp_path,
            "media_type": "image"
        })
        final_answer = response.get("final_answer")
        await update.message.reply_text(final_answer)
    except Exception as e:
        logger.error(f"Error handling photo: {e}", exc_info=True)
        await update.message.reply_text("Error al procesar la imagen.")

def create_bot_application() -> ApplicationBuilder:
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document)) 
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return application

