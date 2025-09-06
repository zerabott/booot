#!/usr/bin/env python3

import sqlite3

def check_tables():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print('Tables in database:')
        for table in sorted(tables):
            print(f'  - {table[0]}')
        
        # Check if ranking tables exist
        ranking_tables = ['user_rankings', 'point_transactions', 'rank_definitions', 'rank_history', 'user_achievements']
        print('\nRanking system tables:')
        for table in ranking_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            exists = cursor.fetchone()
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f'  - {table}: {status}')
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_tables()
