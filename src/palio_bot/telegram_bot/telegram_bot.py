#!/usr/bin/env python3
"""
Telegram bot per la gestione del Palio con event system
"""
import asyncio
import logging
from typing import Dict, Optional, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from palio_bot.config import Config
from palio_bot.container import Container
from palio_bot.agent.models import Session

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PalioTelegramBot:
    def __init__(self, token: str, allowed_user_id: Optional[int] = None, config: Optional[Config] = None):
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.container: Optional[Container] = None
        self.user_sessions: Dict[int, Session] = {}
        self.chat_consumers: Dict[int, Any] = {}  # chat_id -> TelegramConsumer
        self.running_tasks: Dict[int, asyncio.Task] = {}  # chat_id -> Task
        self.config = config if config is not None else Config()
        
    async def initialize(self):
        """Initialize the container and system"""
        self.container = Container()
        await self.container.init_container()
        logger.info("Container initialized with event system")
        
    def check_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        if self.allowed_user_id is None:
            return True
        return user_id == self.allowed_user_id
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        
        # Log user ID for admin to see
        logger.info(f"User {user.full_name} (ID: {user.id}) started the bot")
        
        # If no allowed_user_id is set, show the user their ID
        if self.allowed_user_id is None:
            await update.message.reply_text(
                f"⚠️ *Bot non configurato*\n\n"
                f"Il tuo User ID è: `{user.id}`\n\n"
                f"Aggiungi questo ID alla variabile d'ambiente:\n"
                f"`ALLOWED_USER_ID={user.id}`\n\n"
                f"per limitare l'accesso solo a te.",
                parse_mode='Markdown'
            )
            return
            
        # Check if user is authorized
        if not self.check_user_authorized(user.id):
            await update.message.reply_text(
                "❌ Non sei autorizzato ad utilizzare questo bot."
            )
            return
            
        await update.message.reply_text(
            f"Ciao {user.mention_html()}! 👋\n\n"
            "Sono l'assistente del Palio. Posso aiutarti a gestire:\n"
            "• Risultati delle partite\n"
            "• Classifiche\n"
            "• Eventi\n"
            "• Statistiche\n\n"
            "Scrivimi un messaggio per iniziare!\n\n"
            "🆕 *Novità*: Ora vedrai gli aggiornamenti in tempo reale!\n\n"
            "Comandi disponibili:\n"
            "/status - Mostra lo stato del sistema\n"
            "/games_status - Mostra lo stato dei giochi\n"
            "/leaderboard - Aggiorna la classifica\n"
            "/save - Salva modifiche senza chiudere sessione\n"
            "/cancel - Annulla le modifiche della sessione corrente\n"
            "/close - Chiudi la sessione salvando le modifiche\n"
            "/stop - Interrompi l'elaborazione in corso",
            parse_mode='HTML'
        )
        
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        if not self.check_user_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot.")
            return
            
        if not self.container:
            await update.message.reply_text("❌ Sistema non inizializzato")
            return
            
        system = self.container.system()

        try:
            # Check if user has active session
            if system.active_session:
                await update.message.reply_text(
                    f"📊 *Stato Sistema*\n\n"
                    f"✅ Sistema attivo\n"
                    f"📝 Sessione: `{system.active_session.id[:8]}...`\n"
                    f"💬 Messaggi: {len(system.active_session.messages)}\n"
                    f"🔄 Event streaming: ✅ Attivo",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "📊 *Stato Sistema*\n\n"
                    "✅ Sistema attivo\n"
                    "❌ Nessuna sessione attiva\n"
                    "🔄 Event streaming: ✅ Attivo",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error in status: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")
            
    async def save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /save command"""
        if not self.validate(update):
            return
            
        system = self.container.system()
        
        try:
            system.save_session()
            await update.message.reply_text(
                "💾 Modifiche salvate\n"
                "La sessione rimane attiva per ulteriori modifiche."
            )
        except Exception as e:
            logger.error(f"Error in save: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /cancel command"""
        if not self.check_user_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot.")
            return
            
        if not self.container:
            await update.message.reply_text("❌ Sistema non inizializzato")
            return
            
        system = self.container.system()
        
        try:
            system.cancel_session()
            await update.message.reply_text(
                "🔙 Sessione annullata\n"
                "Le modifiche sono state annullate e il file è stato ripristinato."
            )
        except Exception as e:
            logger.error(f"Error in cancel: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")
            
    async def close(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /close command"""
        if not self.validate(update):
            return
            
        system = self.container.system()
        
        try:
            system.close_session()
            await update.message.reply_text(
                "✅ Sessione chiusa\n"
                "Le modifiche sono state salvate."
            )
        except Exception as e:
            logger.error(f"Error in close: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")
            
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop command to cancel ongoing computation."""
        if not self.check_user_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot.")
            return
            
        if not self.container:
            await update.message.reply_text("❌ Sistema non inizializzato")
            return
            
        chat_id = update.effective_chat.id
        
        try:
            # Check if there's a running task for this chat
            if chat_id not in self.running_tasks:
                await update.message.reply_text(
                    "⚠️ Nessuna elaborazione in corso da interrompere."
                )
                return
            
            # Cancel the running task
            task = self.running_tasks[chat_id]
            task.cancel()
            
            await update.message.reply_text(
                "🛑 Elaborazione interrotta immediatamente."
            )
            
            # Also request cancellation in the system for cleanup
            system = self.container.system()
            system.request_cancellation()
            
        except Exception as e:
            logger.error(f"Error in stop: {e}")
            await update.message.reply_text(f"❌ Errore: {str(e)}")
            
    async def games_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /games_status command"""
        if not self.validate(update):
            return
            
        try:
            import json
            from pathlib import Path
            
            # Read games status file
            file = Path(self.config.palio_games_status_temp_path)
            if not file.exists():
                file = Path(self.config.palio_games_status_path)
                if not file.exists():
                    await update.message.reply_text("❌ File palio_games_status_temp.json e palio_games_status.json non trovati.")
                    return
                
            with open(file, 'r', encoding='utf-8') as f:
                games_data = json.load(f)
                
            # Format as pretty JSON
            json_text = json.dumps(games_data, indent=2, ensure_ascii=False)
            
            # Split into chunks if too long (Telegram has message length limits)
            max_length = 4000
            if len(json_text) <= max_length:
                await update.message.reply_text(
                    f"📄 *palio_games_status.json*\n\n```json\n{json_text}\n```",
                    parse_mode='Markdown'
                )
            else:
                # Split into multiple messages
                chunks = []
                lines = json_text.split('\n')
                current_chunk = []
                current_length = 0
                
                for line in lines:
                    if current_length + len(line) + 1 > max_length:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = [line]
                        current_length = len(line)
                    else:
                        current_chunk.append(line)
                        current_length += len(line) + 1
                        
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    
                # Send chunks
                for i, chunk in enumerate(chunks):
                    header = f"📄 *palio_games_status.json* (parte {i+1}/{len(chunks)})\n\n" if i == 0 else ""
                    await update.message.reply_text(
                        f"{header}```json\n{chunk}\n```",
                        parse_mode='Markdown'
                    )
            
        except Exception as e:
            logger.error(f"Error in games_status: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Errore: {str(e)}")
            
    async def leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /leaderboard command"""
        if not self.validate(update):
            return
            
        # Send processing message
        processing_message = await update.message.reply_text("📊 Aggiornamento classifica in corso...")
        
        try:
            from palio_bot.leaderboard_updater import LeaderboardUpdater
            from palio_bot.config import Config
            
            config = Config()
            leaderboard_updater = LeaderboardUpdater(
                config.palio_file_path,
                config.palio_games_status_path,
                config.leaderboard_file_path
            )
            
            leaderboard_updater.update_leaderboard()
            
            await processing_message.edit_text(
                "✅ Classifica aggiornata con successo!\n"
                "📈 Tutti i giochi completati sono stati processati."
            )
            
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}", exc_info=True)
            await processing_message.edit_text(
                f"❌ Errore nell'aggiornamento della classifica:\n`{str(e)}`",
                parse_mode='Markdown'
            )
            
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages with event streaming"""

        if not self.validate(update):
            return
            
        system = self.container.system()
        user_message = update.message.text
        chat_id = update.effective_chat.id
        
        # Cancel any existing task for this chat
        if chat_id in self.running_tasks:
            self.running_tasks[chat_id].cancel()
            try:
                await self.running_tasks[chat_id]
            except asyncio.CancelledError:
                pass
            del self.running_tasks[chat_id]
        
        # Create or get Telegram consumer for this chat
        if chat_id not in self.chat_consumers:
            consumer = self.container.create_telegram_consumer(
                bot=context.bot,
                chat_id=chat_id
            )
            self.chat_consumers[chat_id] = consumer
            logger.info(f"Created Telegram consumer for chat {chat_id}")
        
        # Create background task for message processing
        async def process_message():
            try:
                # Process message through the system
                # Events will be sent to Telegram consumer automatically
                await system.send_message(user_message)
                
                # The final response is already sent by the TelegramConsumer
                # through the AgentCompleteEvent
                
            except asyncio.CancelledError:
                # Task was cancelled by /stop command
                await update.message.reply_text(
                    "⏹️ Elaborazione interrotta dall'utente"
                )
                raise
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                err = str(e)
                if len(err) > 3500:
                    err = err[:3500] + "…"
                await update.message.reply_text(
                    f"❌ Errore durante l'elaborazione:\n`{err}`",
                    parse_mode='Markdown'
                )
            finally:
                # Clean up task from running_tasks
                if chat_id in self.running_tasks:
                    del self.running_tasks[chat_id]
        
        # Start background task
        task = asyncio.create_task(process_message())
        self.running_tasks[chat_id] = task
    
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages with transcription"""
        if not self.validate(update):
            return
            
        # Get audio transcription service
        audio_service = self.container.audio_transcription_service()
        
        if not audio_service.is_available():
            await update.message.reply_text(
                "❌ Servizio di trascrizione audio non disponibile.\n"
                "Assicurati che GROQ_API_KEY sia configurata correttamente."
            )
            return
            
        # Send processing message
        processing_message = await update.message.reply_text("🎤 Trascrizione audio in corso...")
        
        try:
            # Get voice file
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            
            # Transcribe audio
            transcription = await audio_service.download_and_transcribe(
                voice_file.file_id, 
                context.bot
            )
            
            if transcription:
                # Delete processing message
                await processing_message.delete()
                
                # Send transcription and process as text message
                await update.message.reply_text(
                    f"📝 *Trascrizione:*\n_{transcription}_",
                    parse_mode='Markdown'
                )
                
                # Process transcription as regular text message
                system = self.container.system()
                chat_id = update.effective_chat.id
                
                # Create or get Telegram consumer for this chat
                if chat_id not in self.chat_consumers:
                    consumer = self.container.create_telegram_consumer(
                        bot=context.bot,
                        chat_id=chat_id
                    )
                    self.chat_consumers[chat_id] = consumer
                    logger.info(f"Created Telegram consumer for chat {chat_id}")
                
                # Process transcribed message through the system using background task
                async def process_voice_message():
                    try:
                        await system.send_message(transcription)
                    except asyncio.CancelledError:
                        await update.message.reply_text(
                            "⏹️ Elaborazione audio interrotta dall'utente"
                        )
                        raise
                    except Exception as e:
                        logger.error(f"Error processing voice transcription: {e}", exc_info=True)
                        await update.message.reply_text(
                            f"❌ Errore durante l'elaborazione audio:\n`{str(e)}`",
                            parse_mode='Markdown'
                        )
                    finally:
                        # Clean up task from running_tasks
                        if chat_id in self.running_tasks:
                            del self.running_tasks[chat_id]
                
                # Cancel any existing task for this chat
                if chat_id in self.running_tasks:
                    self.running_tasks[chat_id].cancel()
                    try:
                        await self.running_tasks[chat_id]
                    except asyncio.CancelledError:
                        pass
                    del self.running_tasks[chat_id]
                
                # Start background task for voice message processing
                task = asyncio.create_task(process_voice_message())
                self.running_tasks[chat_id] = task
                
            else:
                await processing_message.edit_text("❌ Errore nella trascrizione audio")
                
        except Exception as e:
            logger.error(f"Error processing voice message: {e}", exc_info=True)
            await processing_message.edit_text(
                f"❌ Errore durante la trascrizione:\n`{str(e)}`",
                parse_mode='Markdown'
            )
            
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by updates"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Si è verificato un errore imprevisto. Riprova più tardi."
            )

    def validate(self, update: Update) -> bool:
        """Validate the update to ensure user is authorized and system is initialized"""

        if not self.check_user_authorized(update.effective_user.id):
            asyncio.create_task(update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot."))
            return False

        if not self.container:
            asyncio.create_task(update.message.reply_text("❌ Sistema non inizializzato"))
            return False

        return True

def main():
    """Start the bot"""
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Get bot token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please create a .env file with:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        return
        
    # Get allowed user ID
    allowed_user_id = os.getenv("ALLOWED_USER_ID")
    if allowed_user_id:
        try:
            allowed_user_id = int(allowed_user_id)
            print(f"✅ Bot configured for user ID: {allowed_user_id}")
        except ValueError:
            print("⚠️ ALLOWED_USER_ID must be a number")
            allowed_user_id = None
    else:
        print("⚠️ ALLOWED_USER_ID not set - bot will show user IDs to help you configure it")
        
    # Create bot instance
    bot = PalioTelegramBot(token, allowed_user_id)
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("games_status", bot.games_status))
    application.add_handler(CommandHandler("leaderboard", bot.leaderboard))
    application.add_handler(CommandHandler("save", bot.save))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(CommandHandler("close", bot.close))
    application.add_handler(CommandHandler("stop", bot.stop_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(MessageHandler(filters.VOICE, bot.handle_voice_message))
    
    # Add error handler
    application.add_error_handler(bot.error_handler)
    
    # Initialize bot before starting
    async def post_init(application) -> None:
        await bot.initialize()
        logger.info("Bot initialized successfully with event system")
    
    application.post_init = post_init
    
    # Run the bot
    logger.info("Starting bot with event system...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()