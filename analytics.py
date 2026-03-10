# analytics.py — TapTap Analytics Chatbot v3
# ALL SQL is hardcoded here. No dynamic SQL generation.
# Single source of truth: public.combined_leaderboard (cl)
# Verified column names from actual DB schema:
#   combined_leaderboard: userId(varchar), name, email, regNo, collegeName,
#                         employabilityScore, employabilityBand, branch,
#                         overallRank, collegeRank, aptitudePercentage,
#                         englishPercentage, codingPercentage
#   user_hackathon_participation: hackathon_id, user_id, current_score
#   hackathon: id, title
#   pod.pod_submission: user_id, status

from typing import Optional
from database import get_connection
from logger import logger


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── 1. Top N students by employability score ──────────────────────────────────

async def get_top_students(
    limit: int = 10,
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    band: Optional[str] = None,
) -> list[dict]:
    logger.debug(f"get_top_students limit={limit} college={college_name} dept={department} band={band}")
    async with get_connection() as conn:
        if college_name and department and band:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name, cl.branch AS department
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl."employabilityBand" ILIKE $3
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" DESC
                LIMIT $4
            """, college_name, department, band, limit)

        elif college_name and department:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name, cl.branch AS department
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" DESC
                LIMIT $3
            """, college_name, department, limit)

        elif college_name and band:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl."employabilityBand" ILIKE $2
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" DESC
                LIMIT $3
            """, college_name, band, limit)

        elif college_name:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" DESC
                LIMIT $2
            """, college_name, limit)

        else:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name
                FROM public.combined_leaderboard cl
                WHERE cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" DESC
                LIMIT $1
            """, limit)

    return _rows_to_dicts(rows)


# ── 2. Bottom N students ──────────────────────────────────────────────────────

async def get_bottom_students(
    limit: int = 10,
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    logger.debug(f"get_bottom_students limit={limit} college={college_name} dept={department}")
    async with get_connection() as conn:
        if college_name and department:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name, cl.branch AS department
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" ASC
                LIMIT $3
            """, college_name, department, limit)

        elif college_name:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" ASC
                LIMIT $2
            """, college_name, limit)

        else:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name
                FROM public.combined_leaderboard cl
                WHERE cl."employabilityScore" IS NOT NULL
                ORDER BY cl."employabilityScore" ASC
                LIMIT $1
            """, limit)

    return _rows_to_dicts(rows)


# ── 3. Band distribution ──────────────────────────────────────────────────────

async def get_band_distribution(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    logger.debug(f"get_band_distribution college={college_name} dept={department}")
    async with get_connection() as conn:
        if college_name and department:
            rows = await conn.fetch("""
                SELECT cl."employabilityBand",
                       COUNT(*) AS count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl."employabilityBand" IS NOT NULL
                GROUP BY cl."employabilityBand"
                ORDER BY count DESC
            """, college_name, department)

        elif college_name:
            rows = await conn.fetch("""
                SELECT cl."employabilityBand",
                       COUNT(*) AS count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl."employabilityBand" IS NOT NULL
                GROUP BY cl."employabilityBand"
                ORDER BY count DESC
            """, college_name)

        else:
            rows = await conn.fetch("""
                SELECT cl."employabilityBand",
                       COUNT(*) AS count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
                FROM public.combined_leaderboard cl
                WHERE cl."employabilityBand" IS NOT NULL
                GROUP BY cl."employabilityBand"
                ORDER BY count DESC
            """)

    return _rows_to_dicts(rows)


# ── 4. College summary ────────────────────────────────────────────────────────

async def get_college_summary(college_name: Optional[str] = None) -> list[dict]:
    logger.debug(f"get_college_summary college={college_name}")
    async with get_connection() as conn:
        if college_name:
            rows = await conn.fetch("""
                SELECT cl."collegeName",
                       COUNT(*) AS total_students,
                       ROUND(AVG(cl."employabilityScore")::numeric, 2) AS avg_score,
                       SUM(CASE WHEN cl."employabilityBand" = 'High' THEN 1 ELSE 0 END) AS high_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Medium' THEN 1 ELSE 0 END) AS medium_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Low' THEN 1 ELSE 0 END) AS low_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Very Low' THEN 1 ELSE 0 END) AS very_low_band_count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                GROUP BY cl."collegeName"
            """, college_name)

        else:
            rows = await conn.fetch("""
                SELECT cl."collegeName",
                       COUNT(*) AS total_students,
                       ROUND(AVG(cl."employabilityScore")::numeric, 2) AS avg_score,
                       SUM(CASE WHEN cl."employabilityBand" = 'High' THEN 1 ELSE 0 END) AS high_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Medium' THEN 1 ELSE 0 END) AS medium_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Low' THEN 1 ELSE 0 END) AS low_band_count,
                       SUM(CASE WHEN cl."employabilityBand" = 'Very Low' THEN 1 ELSE 0 END) AS very_low_band_count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" IS NOT NULL
                GROUP BY cl."collegeName"
                ORDER BY avg_score DESC
            """)

    return _rows_to_dicts(rows)


# ── 5. Department summary ─────────────────────────────────────────────────────

async def get_department_summary(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
) -> list[dict]:
    logger.debug(f"get_department_summary college={college_name} dept={department}")
    async with get_connection() as conn:
        if college_name and department:
            rows = await conn.fetch("""
                SELECT cl.branch AS department,
                       COUNT(*) AS total_students,
                       ROUND(AVG(cl."employabilityScore")::numeric, 2) AS avg_score,
                       SUM(CASE WHEN cl."employabilityBand" = 'High' THEN 1 ELSE 0 END) AS high_band_count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl.branch IS NOT NULL
                GROUP BY cl.branch
                ORDER BY avg_score DESC
            """, college_name, department)

        elif college_name:
            rows = await conn.fetch("""
                SELECT cl.branch AS department,
                       COUNT(*) AS total_students,
                       ROUND(AVG(cl."employabilityScore")::numeric, 2) AS avg_score,
                       SUM(CASE WHEN cl."employabilityBand" = 'High' THEN 1 ELSE 0 END) AS high_band_count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch IS NOT NULL
                GROUP BY cl.branch
                ORDER BY avg_score DESC
            """, college_name)

        else:
            rows = await conn.fetch("""
                SELECT cl.branch AS department,
                       COUNT(*) AS total_students,
                       ROUND(AVG(cl."employabilityScore")::numeric, 2) AS avg_score,
                       SUM(CASE WHEN cl."employabilityBand" = 'High' THEN 1 ELSE 0 END) AS high_band_count
                FROM public.combined_leaderboard cl
                WHERE cl.branch IS NOT NULL
                GROUP BY cl.branch
                ORDER BY avg_score DESC
            """)

    return _rows_to_dicts(rows)


# ── 6. Hackathon performance ──────────────────────────────────────────────────
# Verified columns: user_hackathon_participation(hackathon_id, user_id, current_score)
# Uses DISTINCT ON subquery to prevent duplicate leaderboard rows inflating scores.

async def get_hackathon_performance(
    college_name: Optional[str] = None,
    hackathon_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    logger.debug(f"get_hackathon_performance college={college_name} hackathon={hackathon_name} limit={limit}")

    cte = """
        WITH cl_unique AS (
            SELECT DISTINCT ON ("userId")
                "userId", name, "regNo", "collegeName", branch
            FROM public.combined_leaderboard
            ORDER BY "userId"
        )
    """

    async with get_connection() as conn:
        if college_name and hackathon_name:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo", h.title AS hackathon_name,
                       uhp.current_score AS score,
                       RANK() OVER (PARTITION BY h.id ORDER BY uhp.current_score DESC) AS rank
                FROM public.user_hackathon_participation uhp
                JOIN public.hackathon h ON h.id = uhp.hackathon_id
                JOIN cl_unique cl ON cl."userId" = uhp.user_id
                WHERE cl."collegeName" ILIKE $1
                  AND h.title ILIKE $2
                ORDER BY uhp.current_score DESC
                LIMIT $3
            """, college_name, hackathon_name, limit)

        elif college_name:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo", h.title AS hackathon_name,
                       uhp.current_score AS score,
                       RANK() OVER (PARTITION BY h.id ORDER BY uhp.current_score DESC) AS rank
                FROM public.user_hackathon_participation uhp
                JOIN public.hackathon h ON h.id = uhp.hackathon_id
                JOIN cl_unique cl ON cl."userId" = uhp.user_id
                WHERE cl."collegeName" ILIKE $1
                ORDER BY uhp.current_score DESC
                LIMIT $2
            """, college_name, limit)

        else:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo", h.title AS hackathon_name,
                       uhp.current_score AS score,
                       RANK() OVER (PARTITION BY h.id ORDER BY uhp.current_score DESC) AS rank
                FROM public.user_hackathon_participation uhp
                JOIN public.hackathon h ON h.id = uhp.hackathon_id
                JOIN cl_unique cl ON cl."userId" = uhp.user_id
                ORDER BY uhp.current_score DESC
                LIMIT $1
            """, limit)

    return _rows_to_dicts(rows)


# ── 7. Pod performance ────────────────────────────────────────────────────────
# Verified columns: pod.pod_submission(user_id, status, create_at)
# Uses DISTINCT ON subquery to deduplicate combined_leaderboard before joining
# so counts are not inflated when leaderboard has multiple rows per userId.

async def get_pod_performance(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 20,
    date_filter: Optional[str] = None,   # "today" | "YYYY-MM-DD" | None
) -> list[dict]:
    logger.debug(f"get_pod_performance college={college_name} dept={department} limit={limit} date={date_filter}")

    # Build date clause
    if date_filter == "today":
        date_clause = "AND ps.create_at::date = CURRENT_DATE"
    elif date_filter:
        date_clause = f"AND ps.create_at::date = '{date_filter}'"
    else:
        date_clause = ""

    # Deduplicated leaderboard CTE — one row per userId
    cte = """
        WITH cl_unique AS (
            SELECT DISTINCT ON ("userId")
                "userId", name, "regNo", "collegeName", branch
            FROM public.combined_leaderboard
            ORDER BY "userId"
        )
    """

    async with get_connection() as conn:
        if college_name and department:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo",
                       SUM(CASE WHEN ps.status = 'pass' THEN 1 ELSE 0 END) AS pass_count,
                       SUM(CASE WHEN ps.status = 'fail' THEN 1 ELSE 0 END) AS fail_count,
                       COUNT(*) AS total
                FROM pod.pod_submission ps
                JOIN cl_unique cl ON cl."userId" = ps.user_id
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  {date_clause}
                GROUP BY cl.name, cl."regNo"
                ORDER BY pass_count DESC
                LIMIT $3
            """, college_name, department, limit)

        elif college_name:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo",
                       SUM(CASE WHEN ps.status = 'pass' THEN 1 ELSE 0 END) AS pass_count,
                       SUM(CASE WHEN ps.status = 'fail' THEN 1 ELSE 0 END) AS fail_count,
                       COUNT(*) AS total
                FROM pod.pod_submission ps
                JOIN cl_unique cl ON cl."userId" = ps.user_id
                WHERE cl."collegeName" ILIKE $1
                  {date_clause}
                GROUP BY cl.name, cl."regNo"
                ORDER BY pass_count DESC
                LIMIT $2
            """, college_name, limit)

        else:
            rows = await conn.fetch(f"""
                {cte}
                SELECT cl.name, cl."regNo",
                       SUM(CASE WHEN ps.status = 'pass' THEN 1 ELSE 0 END) AS pass_count,
                       SUM(CASE WHEN ps.status = 'fail' THEN 1 ELSE 0 END) AS fail_count,
                       COUNT(*) AS total
                FROM pod.pod_submission ps
                JOIN cl_unique cl ON cl."userId" = ps.user_id
                WHERE 1=1 {date_clause}
                GROUP BY cl.name, cl."regNo"
                ORDER BY pass_count DESC
                LIMIT $1
            """, limit)

    return _rows_to_dicts(rows)


# ── 8. Student profile ────────────────────────────────────────────────────────

async def get_student_profile(
    reg_no: Optional[str] = None,
    college_name: Optional[str] = None,
) -> list[dict]:
    logger.debug(f"get_student_profile reg_no={reg_no} college={college_name}")
    if not reg_no:
        return []
    async with get_connection() as conn:
        if college_name:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name, cl.email, cl.branch AS department,
                       cl."overallRank", cl."collegeRank",
                       cl."aptitudePercentage", cl."englishPercentage", cl."codingPercentage"
                FROM public.combined_leaderboard cl
                WHERE cl."regNo" ILIKE $1
                  AND cl."collegeName" ILIKE $2
            """, reg_no, college_name)

        else:
            rows = await conn.fetch("""
                SELECT cl."regNo", cl."userId", cl."employabilityScore", cl."employabilityBand",
                       cl."collegeName", cl.name, cl.email, cl.branch AS department,
                       cl."overallRank", cl."collegeRank",
                       cl."aptitudePercentage", cl."englishPercentage", cl."codingPercentage"
                FROM public.combined_leaderboard cl
                WHERE cl."regNo" ILIKE $1
            """, reg_no)

    return _rows_to_dicts(rows)


# ── 9. Score distribution (histogram buckets) ─────────────────────────────────

async def get_score_distribution(
    college_name: Optional[str] = None,
    department: Optional[str] = None,
    bucket_size: int = 10,
) -> list[dict]:
    logger.debug(f"get_score_distribution college={college_name} dept={department} bucket={bucket_size}")
    async with get_connection() as conn:
        if college_name and department:
            rows = await conn.fetch("""
                SELECT
                    (FLOOR(cl."employabilityScore" / $3) * $3)::int AS bucket_start,
                    (FLOOR(cl."employabilityScore" / $3) * $3 + $3 - 1)::int AS bucket_end,
                    COUNT(*) AS count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl.branch ILIKE $2
                  AND cl."employabilityScore" IS NOT NULL
                GROUP BY bucket_start, bucket_end
                ORDER BY bucket_start
            """, college_name, department, bucket_size)

        elif college_name:
            rows = await conn.fetch("""
                SELECT
                    (FLOOR(cl."employabilityScore" / $2) * $2)::int AS bucket_start,
                    (FLOOR(cl."employabilityScore" / $2) * $2 + $2 - 1)::int AS bucket_end,
                    COUNT(*) AS count
                FROM public.combined_leaderboard cl
                WHERE cl."collegeName" ILIKE $1
                  AND cl."employabilityScore" IS NOT NULL
                GROUP BY bucket_start, bucket_end
                ORDER BY bucket_start
            """, college_name, bucket_size)

        else:
            rows = await conn.fetch("""
                SELECT
                    (FLOOR(cl."employabilityScore" / $1) * $1)::int AS bucket_start,
                    (FLOOR(cl."employabilityScore" / $1) * $1 + $1 - 1)::int AS bucket_end,
                    COUNT(*) AS count
                FROM public.combined_leaderboard cl
                WHERE cl."employabilityScore" IS NOT NULL
                GROUP BY bucket_start, bucket_end
                ORDER BY bucket_start
            """, bucket_size)

    return _rows_to_dicts(rows)