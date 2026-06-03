import asyncio
from pyrogram import Client
from config import API_ID, API_HASH

async def generate():
    print("=========================================")
    print("  Pyrogram String Session Generator      ")
    print("=========================================")
    print(f"Using API_ID: {API_ID}")
    print(f"Using API_HASH: {API_HASH}")
    print("\nStarting Pyrogram Client...\n")
    
    # Prompt the user for login through standard console
    async with Client("session_generator", api_id=API_ID, api_hash=API_HASH, in_memory=True) as app:
        session = await app.export_session_string()
        print("\n=========================================")
        print("  SUCCESS! Copy your STRING_SESSION below:")
        print("=========================================\n")
        print(session)
        print("\n=========================================")
        print("Paste this string into your .env or config.py")
        print("=========================================")

if __name__ == "__main__":
    asyncio.run(generate())
