#!/usr/bin/env python3
"""
Telegram bot per la gestione del Palio con event system
"""

import logging
from typing import Dict, Optional, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from palio_bot.container import Container
from palio_bot.agent.models import Session

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PalioTelegramBot:
    def __init__(self, token: str, allowed_user_id: Optional[int] = None):
        self.token = token
        self.allowed_user_id = allowed_user_id
        self.container: Optional[Container] = None
        self.user_sessions: Dict[int, Session] = {}
        self.chat_consumers: Dict[int, Any] = {}  # chat_id -> TelegramConsumer
        
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
            "/cancel - Annulla le modifiche della sessione corrente\n"
            "/close - Chiudi la sessione salvando le modifiche",
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
        user_id = update.effective_user.id
        
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
        if not self.check_user_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot.")
            return
            
        if not self.container:
            await update.message.reply_text("❌ Sistema non inizializzato")
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
            
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages with event streaming"""
        if not self.check_user_authorized(update.effective_user.id):
            await update.message.reply_text("❌ Non sei autorizzato ad utilizzare questo bot.")
            return
            
        if not self.container:
            await update.message.reply_text("❌ Sistema non inizializzato")
            return
            
        system = self.container.system()
        user_message = update.message.text
        chat_id = update.effective_chat.id
        
        # Create or get Telegram consumer for this chat
        if chat_id not in self.chat_consumers:
            consumer = self.container.create_telegram_consumer(
                bot=context.bot,
                chat_id=chat_id
            )
            self.chat_consumers[chat_id] = consumer
            logger.info(f"Created Telegram consumer for chat {chat_id}")
        
        try:
            # Process message through the system
            # Events will be sent to Telegram consumer automatically
            response = await system.send_message(user_message)
            
            # The final response is already sent by the TelegramConsumer
            # through the AgentCompleteEvent
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Errore durante l'elaborazione:\n`{str(e)}`",
                parse_mode='Markdown'
            )
            
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by updates"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Si è verificato un errore imprevisto. Riprova più tardi."
            )

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
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(CommandHandler("close", bot.close))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Add error handler
    application.add_error_handler(bot.error_handler)
    
    # Initialize bot before starting
    async def post_init(application: Application) -> None:
        await bot.initialize()
        logger.info("Bot initialized successfully with event system")
    
    application.post_init = post_init
    
    # Run the bot
    logger.info("Starting bot with event system...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()