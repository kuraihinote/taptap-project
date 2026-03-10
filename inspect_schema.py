import asyncio, asyncpg, os
from dotenv import load_dotenv

load_dotenv()

async def dump_schema():
    dsn = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}?sslmode={os.getenv('DB_SSL', 'require')}"
    conn = await asyncpg.connect(dsn)
    with open("schema_dump.txt", "w", encoding="utf-8") as f:
        tables = ["user", "combined_leaderboard"]
        for t in tables:
            f.write(f"--- {t} ---\n")
            rows = await conn.fetch(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='{t}'")
            for r in rows:
                f.write(f"{r['column_name']}: {r['data_type']}\n")
    await conn.close()

asyncio.run(dump_schema())
