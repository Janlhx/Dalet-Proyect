import asyncio
import os
from database.turso_client import TursoClient
from dotenv import load_dotenv

async def main():
    load_dotenv()
    client = TursoClient.get_client()
    if not client:
        print("No Turso client")
        return
    print("Turso client OK!")

if __name__ == "__main__":
    asyncio.run(main())
