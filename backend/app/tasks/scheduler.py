import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import async_session

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def _collect_job():
    from app.services.collector import generate_demo_data, run_collection

    async def _run():
        async with async_session() as db:
            if settings.demo_mode:
                await generate_demo_data(db)
            else:
                await run_collection(db)

    try:
        _run_async(_run())
    except Exception:
        logger.exception("Collection job failed")


def _analysis_job():
    from app.services.analyzer import analyze_all_servers

    async def _run():
        async with async_session() as db:
            await analyze_all_servers(db)

    try:
        _run_async(_run())
    except Exception:
        logger.exception("Analysis job failed")


def _recommendation_job():
    from app.services.recommender import generate_recommendations

    async def _run():
        async with async_session() as db:
            await generate_recommendations(db)

    try:
        _run_async(_run())
    except Exception:
        logger.exception("Recommendation job failed")


def start_scheduler():
    # Run collection immediately on startup
    scheduler.add_job(_collect_job, "interval", seconds=settings.collect_interval, id="collect", next_run_time=None)
    scheduler.add_job(_analysis_job, "interval", seconds=settings.analysis_interval, id="analysis", next_run_time=None)
    scheduler.add_job(
        _recommendation_job, "interval", seconds=settings.recommendation_interval, id="recommend", next_run_time=None
    )
    scheduler.start()
    logger.info("Scheduler started (demo_mode=%s)", settings.demo_mode)

    # Trigger initial collection immediately in a thread
    scheduler.add_job(_collect_job, id="initial_collect")
    scheduler.add_job(_recommendation_job, id="initial_recommend")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
