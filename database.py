import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_file: str = 'kronekort.db'):
        self.db_file = db_file
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table: stores Telegram user info and card numbers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                card_number TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Balance history table: stores balance checks
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                balance REAL,
                transactions TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str, card_number: str):
        """Add or update user with card number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, card_number)
            VALUES (?, ?, ?)
        ''', (user_id, username, card_number))
        
        conn.commit()
        conn.close()
    
    def get_user_card(self, user_id: int) -> Optional[str]:
        """Get user's card number"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT card_number FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def get_last_balance(self, user_id: int) -> Optional[Dict]:
        """Get last balance check for user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT balance, transactions, checked_at
            FROM balance_history
            WHERE user_id = ?
            ORDER BY checked_at DESC
            LIMIT 1
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'balance': row[0],
                'transactions': json.loads(row[1]) if row[1] else [],
                'checked_at': row[2]
            }
        return None
    
    def save_balance_check(self, user_id: int, balance: float, transactions: List[Dict]):
        """Save balance check result"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO balance_history (user_id, balance, transactions)
            VALUES (?, ?, ?)
        ''', (user_id, balance, json.dumps(transactions)))
        
        conn.commit()
        conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Get all users for periodic checking"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, card_number FROM users')
        rows = cursor.fetchall()
        conn.close()
        
        return [{'user_id': row[0], 'card_number': row[1]} for row in rows]

