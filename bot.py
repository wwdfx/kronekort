import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from database import Database
from scraper import DNBScraper
from config import TELEGRAM_BOT_TOKEN, CHECK_INTERVAL
import re

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_CARD = 1

class KronekortBot:
    def __init__(self):
        self.db = Database()
        self._scraper = None
        self._executor = None
        self.checking_users = set()  # Track users currently being checked
    
    @property
    def scraper(self):
        """Lazy initialization of scraper"""
        if self._scraper is None:
            self._scraper = DNBScraper()
        return self._scraper
    
    @property
    def executor(self):
        """Lazy initialization of thread pool executor"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=2)
        return self._executor
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        # Check if user already has a card number
        card_number = self.db.get_user_card(user_id)
        
        if card_number:
            await update.message.reply_text(
                f"Hei {username}! Du har allerede registrert kortnummeret ditt.\n\n"
                f"Bruk /balance for å sjekke saldoen manuelt.\n"
                f"Bruk /updatecard for å oppdatere kortnummeret ditt."
            )
        else:
            await update.message.reply_text(
                f"Hei {username}! Velkommen til Kronekort Bot.\n\n"
                f"Jeg vil hjelpe deg med å overvåke saldoen på ditt Kronekort.\n\n"
                f"Vennligst send meg ditt kortnummer (12 siffer)."
            )
            return WAITING_FOR_CARD
    
    async def handle_card_number(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle card number input"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        card_input = update.message.text.strip()
        
        # Validate card number (should be 12 digits, possibly with spaces)
        card_number = re.sub(r'\s+', '', card_input)
        
        if not re.match(r'^\d{12}$', card_number):
            await update.message.reply_text(
                "Ugyldig kortnummer. Vennligst send et gyldig 12-sifret kortnummer."
            )
            return WAITING_FOR_CARD
        
        # Save card number
        self.db.add_user(user_id, username, card_number)
        
        await update.message.reply_text(
            f"Takk! Kortnummeret ditt er registrert.\n\n"
            f"Jeg vil nå sjekke saldoen hvert 5. minutt og varsle deg hvis den endres.\n\n"
            f"Bruk /balance for å sjekke saldoen manuelt."
        )
        
        return ConversationHandler.END
    
    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        user_id = update.effective_user.id
        
        # Check if user has registered a card
        card_number = self.db.get_user_card(user_id)
        if not card_number:
            await update.message.reply_text(
                "Du har ikke registrert et kortnummer ennå. Bruk /start for å begynne."
            )
            return
        
        # Check if already checking
        if user_id in self.checking_users:
            await update.message.reply_text("Sjekker saldo... vennligst vent.")
            return
        
        self.checking_users.add(user_id)
        
        try:
            await update.message.reply_text("Sjekker saldo...")
            
            # Check balance using thread pool executor with timeout (60 seconds)
            try:
                result = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        self.executor, self.scraper.check_balance, card_number
                    ),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                logger.error("Balance check timed out after 60 seconds")
                await update.message.reply_text(
                    "Tidsavbrudd ved sjekking av saldo. Vennligst prøv igjen senere."
                )
                return
            
            if result and result.get('balance') is not None:
                balance = result['balance']
                last_transaction = result.get('last_transaction')
                
                message = f"📊 **Saldo:** {balance:,.2f} kr"
                
                if last_transaction:
                    message += f"\n\n📝 **Siste transaksjon:**"
                    if last_transaction.get('date'):
                        message += f"\nDato: {last_transaction['date']}"
                    if last_transaction.get('description'):
                        message += f"\nBeskrivelse: {last_transaction['description']}"
                    if last_transaction.get('amount'):
                        message += f"\nBeløp: {last_transaction['amount']}"
                
                # Save this check
                self.db.save_balance_check(user_id, balance, result.get('transactions', []))
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "Kunne ikke hente saldo. Vennligst prøv igjen senere."
                )
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            await update.message.reply_text(
                "En feil oppstod ved sjekking av saldo. Vennligst prøv igjen senere."
            )
        finally:
            self.checking_users.discard(user_id)
    
    async def update_card(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /updatecard command"""
        await update.message.reply_text(
            "Vennligst send meg ditt nye kortnummer (12 siffer)."
        )
        return WAITING_FOR_CARD
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text("Operasjonen er avbrutt.")
        return ConversationHandler.END
    
    async def check_all_users(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodically check balance for all users"""
        users = self.db.get_all_users()
        
        for user in users:
            user_id = user['user_id']
            card_number = user['card_number']
            
            # Skip if already checking
            if user_id in self.checking_users:
                continue
            
            self.checking_users.add(user_id)
            
            try:
                # Check balance using thread pool executor with timeout (60 seconds)
                try:
                    result = await asyncio.wait_for(
                        asyncio.get_running_loop().run_in_executor(
                            self.executor, self.scraper.check_balance, card_number
                        ),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Balance check timed out for user {user_id}")
                    continue
                
                if result and result.get('balance') is not None:
                    current_balance = result['balance']
                    last_balance_data = self.db.get_last_balance(user_id)
                    
                    # Check if balance changed
                    if last_balance_data:
                        previous_balance = last_balance_data['balance']
                        
                        if abs(current_balance - previous_balance) > 0.01:  # Balance changed
                            # Get last transaction
                            last_transaction = result.get('last_transaction')
                            
                            message = f"🔔 **Saldoendring oppdaget!**\n\n"
                            message += f"📊 **Ny saldo:** {current_balance:,.2f} kr\n"
                            message += f"📊 **Forrige saldo:** {previous_balance:,.2f} kr\n"
                            message += f"📈 **Endring:** {current_balance - previous_balance:+,.2f} kr"
                            
                            if last_transaction:
                                message += f"\n\n📝 **Siste transaksjon:**"
                                if last_transaction.get('date'):
                                    message += f"\nDato: {last_transaction['date']}"
                                if last_transaction.get('description'):
                                    message += f"\nBeskrivelse: {last_transaction['description']}"
                                if last_transaction.get('amount'):
                                    message += f"\nBeløp: {last_transaction['amount']}"
                            
                            # Send notification
                            try:
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=message,
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"Error sending message to user {user_id}: {e}")
                    
                    # Save this check
                    self.db.save_balance_check(user_id, current_balance, result.get('transactions', []))
                else:
                    logger.warning(f"Could not get balance for user {user_id}")
                    
            except Exception as e:
                logger.error(f"Error checking balance for user {user_id}: {e}")
            finally:
                self.checking_users.discard(user_id)
            
            # Small delay between users
            await asyncio.sleep(2)
    
    def shutdown(self):
        """Cleanup resources"""
        if self._executor:
            self._executor.shutdown(wait=True)

def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in environment variables or .env file")
        print("Please create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    bot_instance = KronekortBot()
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler for card number input
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', bot_instance.start),
            CommandHandler('updatecard', bot_instance.update_card)
        ],
        states={
            WAITING_FOR_CARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_card_number)
            ],
        },
        fallbacks=[CommandHandler('cancel', bot_instance.cancel)]
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('balance', bot_instance.balance))
    
    # Schedule periodic balance checks
    job_queue = application.job_queue
    job_queue.run_repeating(
        bot_instance.check_all_users,
        interval=CHECK_INTERVAL,
        first=10  # Start checking after 10 seconds
    )
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

