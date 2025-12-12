from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# Try to import webdriver-manager as optional fallback
try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WEBDRIVER_MANAGER = True
except ImportError:
    HAS_WEBDRIVER_MANAGER = False

class DNBScraper:
    def __init__(self):
        self.url = 'https://www.dnb.no/kort/kronekort/saldo/'
        self.driver = None
    
    def _get_driver(self):
        """Initialize Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Use Selenium 4.6+ built-in driver management (Selenium Manager)
        # This automatically downloads and manages the ChromeDriver
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.warning(f"Selenium built-in driver management failed: {e}")
            # Fallback to webdriver-manager if available
            if HAS_WEBDRIVER_MANAGER:
                try:
                    logger.info("Trying webdriver-manager as fallback...")
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e2:
                    logger.error(f"Both driver management methods failed. Last error: {e2}")
                    raise
            else:
                logger.error(f"Failed to initialize Chrome driver: {e}")
                raise
        
        return driver
    
    def check_balance(self, card_number: str) -> Optional[Dict]:
        """
        Check balance for a card number
        Returns dict with 'balance' and 'transactions' or None if error
        """
        driver = None
        try:
            logger.info(f"Starting balance check for card number: {card_number[:4]}****")
            driver = self._get_driver()
            logger.info("Chrome driver initialized, loading page...")
            driver.get(self.url)
            
            # Wait for the page to load
            logger.info("Waiting for page to load...")
            time.sleep(3)
            
            # Find the card number input field (Kortnummer)
            logger.info("Looking for card number input field...")
            wait = WebDriverWait(driver, 15)
            
            # Try multiple selectors to find the input field
            card_input = None
            selectors = [
                (By.CSS_SELECTOR, "input.dnb-input__input[maxlength='12']"),  # Specific DNB input with maxlength 12
                (By.CSS_SELECTOR, "input.dnb-input__input"),  # DNB input class
                (By.CSS_SELECTOR, "input[type='text'][maxlength='12']"),  # Any text input with maxlength 12
                (By.CSS_SELECTOR, "input[type='text']"),  # Fallback to any text input
            ]
            
            for by, value in selectors:
                try:
                    card_input = wait.until(EC.presence_of_element_located((by, value)))
                    if card_input:
                        logger.info(f"Found input field using selector: {by}={value}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {by}={value} failed: {e}")
                    continue
            
            if not card_input:
                # Save page source for debugging
                page_source = driver.page_source[:1000]  # First 1000 chars
                logger.error(f"Could not find card number input field. Page title: {driver.title}")
                logger.debug(f"Page source snippet: {page_source}")
                raise Exception("Could not find card number input field on the page")
            
            # Enter card number
            logger.info("Entering card number...")
            card_input.clear()
            card_input.send_keys(card_number)
            
            # Find and click submit button ("Se saldo")
            logger.info("Looking for submit button...")
            submit_button = None
            submit_selectors = [
                (By.XPATH, "//button[.//span[contains(text(), 'Se saldo')]]"),  # Button containing "Se saldo" span
                (By.XPATH, "//span[contains(text(), 'Se saldo')]"),  # The span itself (clickable)
                (By.CSS_SELECTOR, "button.dnb-button"),  # DNB button class
                (By.CSS_SELECTOR, "button[type='submit']"),  # Standard submit button
                (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'saldo')]"),  # Button with "saldo" text
            ]
            
            for by, value in submit_selectors:
                try:
                    submit_button = wait.until(EC.element_to_be_clickable((by, value)))
                    if submit_button:
                        logger.info(f"Found submit button using selector: {by}={value}")
                        break
                except Exception as e:
                    logger.debug(f"Submit selector {by}={value} failed: {e}")
                    continue
            
            if not submit_button:
                raise Exception("Could not find submit button on the page")
            
            # Scroll into view and click
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            logger.info("Submit button clicked, waiting for results...")
            
            # Wait for results to load
            time.sleep(5)
            
            # Parse the page
            logger.info("Parsing page for balance information...")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract balance - must be from the "Saldo" section, NOT from transactions
            import re
            balance = None
            
            logger.info("Extracting balance...")
            
            # Strategy 1: Find "Saldo" paragraph and get balance from h2 in same parent
            saldo_p = soup.find('p', string=re.compile('^Saldo$', re.IGNORECASE))
            if saldo_p:
                logger.debug("Found 'Saldo' paragraph")
                # Walk up the parent tree to find the div containing both Saldo and balance
                current = saldo_p.parent
                max_depth = 10
                depth = 0
                while current and depth < max_depth:
                    # Check if this parent has an h2 with balance
                    h2_balance = current.find('h2', class_='dnb-h--large')
                    if h2_balance:
                        balance_elem = h2_balance.find('span', class_='dnb-number-format__visible')
                        if balance_elem:
                            text = balance_elem.get_text().strip()
                            logger.debug(f"Found balance element with text: {text}")
                            match = re.search(r'([\d\s,]+)\s*kr', text, re.IGNORECASE)
                            if match:
                                try:
                                    balance_str = match.group(1).replace(' ', '').replace(',', '.')
                                    balance = float(balance_str)
                                    logger.info(f"Found balance by parent traversal: {balance} kr")
                                    break
                                except Exception as e:
                                    logger.debug(f"Error parsing balance '{balance_str}': {e}")
                    current = current.parent
                    depth += 1
            
            # Strategy 2: Find all divs with dnb-space classes and check for Saldo
            if balance is None:
                logger.debug("Trying strategy 2: searching divs with dnb-space classes")
                # Try different ways to match the class
                all_divs = soup.find_all('div', class_=lambda x: x and ('dnb-space' in str(x) or (isinstance(x, list) and 'dnb-space' in x)))
                for div in all_divs:
                    # Check if this div contains "Saldo" text
                    saldo_text = div.find('p', string=re.compile('^Saldo$', re.IGNORECASE))
                    if saldo_text:
                        h2_balance = div.find('h2', class_='dnb-h--large')
                        if h2_balance:
                            balance_elem = h2_balance.find('span', class_='dnb-number-format__visible')
                            if balance_elem:
                                text = balance_elem.get_text().strip()
                                match = re.search(r'([\d\s,]+)\s*kr', text, re.IGNORECASE)
                                if match:
                                    try:
                                        balance_str = match.group(1).replace(' ', '').replace(',', '.')
                                        balance = float(balance_str)
                                        logger.info(f"Found balance from div search: {balance} kr")
                                        break
                                    except Exception as e:
                                        logger.debug(f"Error parsing balance: {e}")
            
            # Strategy 3: Find balance by position - before transaction section
            if balance is None:
                logger.debug("Trying strategy 3: finding balance by position")
                transaksjoner_text = soup.find(string=re.compile('Viser.*siste transaksjoner', re.IGNORECASE))
                if transaksjoner_text:
                    trans_parent = transaksjoner_text.find_parent()
                    # Get page HTML to check positions
                    page_html = driver.page_source
                    trans_pos = page_html.find('Viser')
                    
                    # Find all h2 elements with balance format
                    all_h2 = soup.find_all('h2', class_='dnb-h--large')
                    logger.debug(f"Found {len(all_h2)} h2 elements with dnb-h--large class")
                    
                    for h2 in all_h2:
                        h2_html = str(h2)
                        h2_pos = page_html.find(h2_html)
                        # Check if this h2 appears before the transaction section
                        if h2_pos != -1 and h2_pos < trans_pos:
                            balance_elem = h2.find('span', class_='dnb-number-format__visible')
                            if balance_elem:
                                text = balance_elem.get_text().strip()
                                logger.debug(f"Found potential balance h2 with text: {text}")
                                match = re.search(r'([\d\s,]+)\s*kr', text, re.IGNORECASE)
                                if match:
                                    try:
                                        balance_str = match.group(1).replace(' ', '').replace(',', '.')
                                        balance = float(balance_str)
                                        logger.info(f"Found balance by position: {balance} kr")
                                        break
                                    except Exception as e:
                                        logger.debug(f"Error parsing balance: {e}")
            
            if balance is None:
                logger.error("Could not extract balance from page. Page structure may have changed.")
                # Save a snippet of the page for debugging
                page_snippet = driver.page_source[:2000]
                logger.debug(f"Page snippet: {page_snippet}")
            
            # Extract transactions from the DNB table structure
            transactions = []
            logger.info("Extracting transactions...")
            
            # Find the transaction table
            transaction_table = soup.find('table', class_=lambda x: x and 'dnb-table' in x)
            if transaction_table:
                rows = transaction_table.find_all('tr', class_=lambda x: x and 'dnb-table__tr' in x)
                
                for row in rows:
                    # Skip month header rows (they have <td> with month name like "Desember 2025")
                    if row.find('td', class_='dnb-table__td'):
                        continue
                    
                    # Extract transaction data
                    # Date: Look for span with day name and p with day number
                    date_parts = []
                    date_span = row.find('span', class_=lambda x: x and 'dnb-span' in x)
                    if date_span:
                        date_parts.append(date_span.get_text().strip())
                    date_num = row.find('p', class_=lambda x: x and 'dnb-p--bold' in x)
                    if date_num:
                        date_parts.append(date_num.get_text().strip())
                    date = ' '.join(date_parts) if date_parts else ''
                    
                    # Description: Look for p with class dnb-p (but not bold)
                    desc_elems = row.find_all('p', class_='dnb-p')
                    description = ''
                    for desc_elem in desc_elems:
                        if 'dnb-p--bold' not in desc_elem.get('class', []):
                            text = desc_elem.get_text().strip()
                            if text and text not in date_parts:  # Don't include date parts
                                description = text
                                break
                    
                    # Amount: Look for span with dnb-number-format__visible
                    amount_elem = row.find('span', class_='dnb-number-format__visible')
                    amount = ''
                    if amount_elem:
                        amount = amount_elem.get_text().strip()
                    
                    # Only add if we have at least description or amount (and it's not a month header)
                    if (description or amount) and not any(month in date for month in ['Januar', 'Februar', 'Mars', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Desember']):
                        transaction = {
                            'date': date,
                            'description': description,
                            'amount': amount
                        }
                        transactions.append(transaction)
                        logger.debug(f"Found transaction: {transaction}")
            
            # Get the last (most recent) transaction if available
            last_transaction = transactions[0] if transactions else None
            if last_transaction:
                logger.info(f"Last transaction: {last_transaction}")
            
            return {
                'balance': balance,
                'transactions': transactions,
                'last_transaction': last_transaction
            }
            
        except Exception as e:
            logger.error(f"Error checking balance: {e}", exc_info=True)
            return None
        finally:
            if driver:
                driver.quit()
    
    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()

