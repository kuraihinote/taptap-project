import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as db:

    print("=== ALL POD TABLES ===")
    result = db.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'pod'
        ORDER BY table_name
    """)).fetchall()
    for r in result:
        print(r[0])

    print("\n=== ALL POD COLUMNS ===")
    result = db.execute(text("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'pod'
        ORDER BY table_name, ordinal_position
    """)).fetchall()
    for r in result:
        print(f"{r[0]}.{r[1]} — {r[2]}")

    print("\n=== SAMPLE pod_submission (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.pod_submission LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE pod_attempt (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.pod_attempt LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE pod_streak (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.pod_streak LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE pod_badge (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.pod_badge LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE user_pod_badge (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.user_pod_badge LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE user_coins (5 rows) ===")
    result = db.execute(text("""
        SELECT * FROM pod.user_coins LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== DISTINCT status values in pod_submission ===")
    result = db.execute(text("""
        SELECT DISTINCT status FROM pod.pod_submission
    """)).fetchall()
    for r in result:
        print(r[0])

    print("\n=== DISTINCT status values in pod_attempt ===")
    result = db.execute(text("""
        SELECT DISTINCT status FROM pod.pod_attempt
    """)).fetchall()
    for r in result:
        print(r[0])

    print("\n=== DISTINCT difficulty values in pod_submission ===")
    result = db.execute(text("""
        SELECT DISTINCT difficulty FROM pod.pod_submission
    """)).fetchall()
    for r in result:
        print(r[0])

    print("\n=== DISTINCT language values in pod_submission ===")
    result = db.execute(text("""
        SELECT DISTINCT language FROM pod.pod_submission ORDER BY 1
    """)).fetchall()
    for r in result:
        print(r[0])

    print("\n=== POD TYPE vs SUBMISSION COUNT ===")
    result = db.execute(text("""
        SELECT potd.type, COUNT(ps.id) AS submission_count
        FROM pod.pod_submission ps
        JOIN pod.problem_of_the_day potd ON potd.id = ps.problem_of_the_day_id
        GROUP BY potd.type
        ORDER BY potd.type
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))

    print("\n=== SAMPLE aptitude/verbal submissions (if any) ===")
    result = db.execute(text("""
        SELECT ps.id, ps.title, ps.language, ps.mcq, potd.type
        FROM pod.pod_submission ps
        JOIN pod.problem_of_the_day potd ON potd.id = ps.problem_of_the_day_id
        WHERE potd.type IN ('aptitude', 'verbal')
        LIMIT 5
    """)).fetchall()
    for r in result:
        print(dict(r._mapping))