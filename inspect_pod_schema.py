import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def dump():
    dsn = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME')}?sslmode={os.getenv('DB_SSL','require')}"
    conn = await asyncpg.connect(dsn)

    # Check distinct status values in pod_attempt
    print("\n=== DISTINCT STATUS VALUES IN pod.pod_attempt ===")
    rows = await conn.fetch("SELECT DISTINCT status, COUNT(*) as cnt FROM pod.pod_attempt GROUP BY status")
    for r in rows:
        print(f"  status='{r['status']}' count={r['cnt']}")

    # Sample a few pod_attempt rows with time_taken populated
    print("\n=== SAMPLE pod_attempt ROWS WITH time_taken ===")
    rows = await conn.fetch("SELECT status, time_taken, pod_started_at, end_date FROM pod.pod_attempt WHERE time_taken IS NOT NULL LIMIT 5")
    for r in rows:
        print(dict(r))

    # Check today's attempts
    print("\n=== TODAY'S pod_attempt ROWS (UTC date) ===")
    rows = await conn.fetch("SELECT status, time_taken, user_id FROM pod.pod_attempt WHERE create_at::date = CURRENT_DATE LIMIT 5")
    for r in rows:
        print(dict(r))

    await conn.close()

asyncio.run(dump())