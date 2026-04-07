import asyncio
import os
from database.pool import DatabasePool
from dotenv import load_dotenv

async def main():
    load_dotenv()
    pool = await DatabasePool.get_pool()
    if not pool:
        print("No pool")
        return
        
    async with pool.acquire() as conn:
        with open('sql/12_WelcomeSystem.sql', 'r') as f:
            await conn.execute(f.read())
            print("Postgres Migrated!")

if __name__ == "__main__":
    asyncio.run(main())
