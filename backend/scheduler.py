import asyncio
import random
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.admin_analytics_service import AdminAnalyticsService
from backend.database import SessionLocal
from backend.logger import logger
from backend.notifications import check_interview_reminders, check_offer_expirations
from backend.report_scheduler import check_scheduled_reports as _check_scheduled_reports
from backend.scripts.cleanup_storage import cleanup_interview_storage

scheduler = AsyncIOScheduler()

MAX_RETRIES = 3
RETRY_DELAYS = [30, 120, 300]


def _active_company_ids(db):
    """Return set of company IDs that have active recruiter members."""
    from backend.database import CompanyMember

    rows = (
        db.query(CompanyMember.company_id)
        .filter(
            CompanyMember.is_active,
        )
        .distinct()
        .all()
    )
    return {r.company_id for r in rows if r.company_id}


async def _run_with_retry(coro_factory, job_name: str):
    last_exception = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await coro_factory()
            return
        except Exception as e:
            last_exception = e
            logger.error(
                f"Scheduler job '{job_name}' attempt {attempt}/{MAX_RETRIES} failed: {e}"
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[attempt - 1] + random.uniform(0, 10)
                logger.warning(f"Retrying '{job_name}' in {delay:.1f}s...")
                await asyncio.sleep(delay)
    logger.critical(f"Scheduler job '{job_name}' FAILED after {MAX_RETRIES} retries.")
    try:
        from backend.dead_letter_queue import record_dead_letter

        db = SessionLocal()
        try:
            record_dead_letter(db, job_name, last_exception)
        finally:
            db.close()
    except Exception as dl_error:
        logger.error(f"Failed to record dead letter for '{job_name}': {dl_error}")


async def _check_interview_reminders():
    db = SessionLocal()
    try:
        check_interview_reminders(db)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"interview_reminders failed: {e}")
        raise
    finally:
        db.close()


async def _check_offer_expirations():
    db = SessionLocal()
    try:
        check_offer_expirations(db)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"offer_expirations failed: {e}")
        raise
    finally:
        db.close()


async def _cleanup_old_data():
    try:
        freed_mb = cleanup_interview_storage(dry_run=False)
        logger.info(f"Data cleanup: freed {freed_mb:.2f} MB")
    except Exception as e:
        logger.error(f"data_cleanup failed: {e}")
        raise
    try:
        _cleanup_old_notifications()
    except Exception as e:
        logger.error(f"notification_cleanup failed: {e}")


def _cleanup_old_notifications():
    """Delete notifications older than 90 days"""
    from datetime import timedelta

    from backend.database import Notification

    db = SessionLocal()
    try:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
        deleted = (
            db.query(Notification).filter(Notification.created_at < cutoff).delete()
        )
        db.commit()
        if deleted:
            logger.info(f"Cleaned up {deleted} old notifications")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clean up old notifications: {e}")
        raise
    finally:
        db.close()


async def _daily_platform_report():
    db = SessionLocal()
    try:
        await AdminAnalyticsService.generate_ai_daily_report(db)
        logger.info("Daily AI Strategic Report generated")
    except Exception as e:
        logger.error(f"daily_ai_report failed: {e}")
        raise
    finally:
        db.close()


async def _pending_followup():
    db = SessionLocal()
    try:
        from backend.database import Application, SystemConfig
        from backend.email_utils import send_email

        auto_enabled = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == "automations_enabled")
            .first()
        )
        if auto_enabled and auto_enabled.value.lower() == "false":
            logger.info("Automations disabled, skipping followup")
            return

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        days_ago = datetime.now(UTC) - timedelta(days=3)
        pending = (
            db.query(Application)
            .filter(
                Application.status == "pending",
                Application.created_at < days_ago,
                Application.email.isnot(None),
                Application.company_id.in_(company_ids),
            )
            .limit(100)
            .all()
        )

        for app in pending:
            try:
                job_title = (
                    app.job.title if app.job else app.declared_role or "the position"
                )
                send_email(
                    app.email,
                    f"Following up - Your application for {job_title}",
                    f"<p>Just checking in on your application for <strong>{job_title}</strong>.</p>",
                )
            except Exception as e:
                logger.error(f"Follow-up send failed for app {app.id}: {e}")
                continue

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"pending_followup failed: {e}")
        raise
    finally:
        db.close()


async def _auto_interview_invite():
    db = SessionLocal()
    try:
        from backend.database import (
            Application,
            EvaluationResult,
            EvaluationSession,
            SystemConfig,
        )
        from backend.email_utils import send_email

        auto_enabled = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == "automations_enabled")
            .first()
        )
        if auto_enabled and auto_enabled.value.lower() == "false":
            return

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        high_score = (
            db.query(Application)
            .outerjoin(
                EvaluationSession, EvaluationSession.application_id == Application.id
            )
            .outerjoin(
                EvaluationResult,
                EvaluationResult.evaluation_session_id == EvaluationSession.id,
            )
            .filter(
                Application.status == "screening",
                EvaluationResult.final_score > 80,
                Application.email.isnot(None),
                Application.company_id.in_(company_ids),
            )
            .limit(50)
            .all()
        )

        for app in high_score:
            try:
                job_title = app.job.title if app.job else "the position"
                send_email(
                    app.email,
                    f"You're invited to interview - {job_title}",
                    "<p>Your application has been shortlisted.</p>",
                )
                app.status = "interviewing"
            except Exception as e:
                logger.error(f"Auto-invite failed for app {app.id}: {e}")
                continue

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"auto_interview_invite failed: {e}")
        raise
    finally:
        db.close()


async def _auto_reject_incomplete():
    db = SessionLocal()
    try:
        from backend.database import Application, Job, SystemConfig

        auto_enabled = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == "automations_enabled")
            .first()
        )
        if auto_enabled and auto_enabled.value.lower() == "false":
            return

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        jobs = (
            db.query(Job)
            .filter(
                Job.required_fields.isnot(None),
                Job.company_id.in_(company_ids),
            )
            .limit(500)
            .all()
        )
        job_map = {j.id: j for j in jobs if j.required_fields}
        if not job_map:
            return

        pending_apps = (
            db.query(Application)
            .filter(
                Application.job_id.in_(list(job_map.keys())),
                Application.status == "pending",
                Application.company_id.in_(company_ids),
            )
            .limit(500)
            .all()
        )

        for app in pending_apps:
            job = job_map.get(app.job_id)
            if not job:
                continue
            required = job.required_fields.split(",")
            missing = [f for f in required if f == "phone" and not app.phone]
            if len(missing) >= 2:
                try:
                    from backend.email_utils import send_email

                    send_email(
                        app.email,
                        f"Application Update - {job.title}",
                        "<p>Some required information was missing.</p>",
                    )
                    app.status = "rejected"
                except Exception as e:
                    logger.error(f"Auto-reject send failed for app {app.id}: {e}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"auto_reject_incomplete failed: {e}")
        raise
    finally:
        db.close()


async def _offer_escalation():
    db = SessionLocal()
    try:
        from backend.database import Application, SystemConfig
        from backend.email_utils import send_email

        auto_enabled = (
            db.query(SystemConfig)
            .filter(SystemConfig.key == "automations_enabled")
            .first()
        )
        if auto_enabled and auto_enabled.value.lower() == "false":
            return

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        five_days_ago = datetime.now(UTC) - timedelta(days=5)
        stale = (
            db.query(Application)
            .filter(
                Application.status == "offer",
                Application.updated_at < five_days_ago,
                Application.company_id.in_(company_ids),
            )
            .limit(500)
            .all()
        )

        for app in stale:
            recruiter = None
            if app.job and app.job.recruiter:
                recruiter = app.job.recruiter
            if recruiter and recruiter.email:
                try:
                    send_email(
                        recruiter.email,
                        "Action Required: Offer pending for 5+ days",
                        "<p>The offer is pending.</p>",
                    )
                except Exception as e:
                    logger.error(f"Escalation send failed for app {app.id}: {e}")
                    continue

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"offer_escalation failed: {e}")
        raise
    finally:
        db.close()


async def _automation_no_activity():
    db = SessionLocal()
    try:
        from backend.automation_worker import evaluate_application_rules
        from backend.database import Application

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        cutoff = datetime.now(UTC) - timedelta(days=7)
        stale_apps = (
            db.query(Application)
            .filter(
                Application.updated_at < cutoff,
                Application.status.in_(["pending", "screening", "invited"]),
                Application.company_id.in_(company_ids),
            )
            .limit(200)
            .all()
        )

        for app in stale_apps:
            try:
                evaluate_application_rules(app.id, app.company_id)
            except Exception as e:
                logger.error(f"Auto no-activity eval failed for app {app.id}: {e}")
                continue

        db.commit()
        logger.info(f"No-activity automation checked {len(stale_apps)} applications")
    except Exception as e:
        db.rollback()
        logger.error(f"automation_no_activity failed: {e}")
        raise
    finally:
        db.close()


async def _email_sequences():
    db = SessionLocal()
    try:
        from backend.email_sequence_worker import process_email_sequences

        process_email_sequences(db)
    except Exception as e:
        db.rollback()
        logger.error(f"email_sequences failed: {e}")
        raise
    finally:
        db.close()


async def _drift_check():
    from backend.jobs.scoring import run_drift_check

    db = SessionLocal()
    try:
        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        for cid in company_ids:
            await run_drift_check(company_id=cid)
    finally:
        db.close()


async def _calibration_collection():
    from backend.jobs.scoring import collect_calibration_samples

    db = SessionLocal()
    try:
        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        for cid in company_ids:
            await collect_calibration_samples(company_id=cid)
    finally:
        db.close()


async def _score_recalibration():
    from backend.jobs.scoring import run_score_recalibration

    db = SessionLocal()
    try:
        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        for cid in company_ids:
            await run_score_recalibration(company_id=cid)
    finally:
        db.close()


async def _drift_snapshot_recording():
    from backend.drift_monitor import check_alert_threshold, record_drift_snapshot

    db = SessionLocal()
    try:
        company_ids = _active_company_ids(db)
        if not company_ids:
            logger.info("[DRIFT] No active companies to process")
            return

        for company_id in company_ids:
            result = record_drift_snapshot(company_id=company_id)
            alert = check_alert_threshold(company_id=company_id)

            logger.info(
                f"[SCHEDULER] Drift snapshot recorded for company "
                f"{company_id}: {result.get('overall_score', {})}"
            )

            if alert:
                logger.warning(
                    f"[SCHEDULER] Company {company_id}: {alert}"
                )
    finally:
        db.close()


async def _ab_experiment_conclusion():
    from backend.ab_experiment import get_experiment_summary
    from backend.database import ABExperiment, SessionLocal

    try:
        with SessionLocal() as db:
            company_ids = _active_company_ids(db)
            if not company_ids:
                return
            active_exps = (
                db.query(ABExperiment)
                .filter(
                    ABExperiment.is_active,
                    ABExperiment.company_id.in_(company_ids),
                )
                .all()
            )
        for exp in active_exps:
            from backend.ab_experiment import conclude_experiment

            if conclude_experiment(exp, min_sample=50):
                summary = get_experiment_summary(exp.id)
                logger.info(f"[SCHEDULER] Experiment {exp.id} concluded: {summary}")
    except Exception as e:
        logger.error(f"[SCHEDULER] AB experiment conclusion failed: {e}")
        raise


async def _daily_reengagement_digest():
    db = SessionLocal()
    try:
        from backend.database import Job, ReEngagementCampaign
        from backend.email_utils import send_email
        from backend.reengagement_engine import ReEngagementEngine

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        cutoff = datetime.now(UTC) - timedelta(days=7)
        active_jobs = (
            db.query(Job)
            .filter(
                Job.is_active,
                Job.deleted_at.is_(None),
                Job.company_id.in_(company_ids),
            )
            .limit(500)
            .all()
        )

        recruiter_digests = {}
        for job in active_jobs:
            recent_campaign = (
                db.query(ReEngagementCampaign)
                .filter(ReEngagementCampaign.job_id == job.id)
                .order_by(ReEngagementCampaign.created_at.desc())
                .first()
            )
            if recent_campaign and recent_campaign.created_at > cutoff:
                continue
            try:
                campaign = await ReEngagementEngine.create_campaign(
                    job, job.recruiter_id, db
                )
                recruiter_id = job.recruiter_id
                if recruiter_id not in recruiter_digests:
                    recruiter_digests[recruiter_id] = {"count": 0, "jobs": []}
                recruiter_digests[recruiter_id]["count"] += campaign.matched_candidates
                recruiter_digests[recruiter_id]["jobs"].append(job.title)
            except Exception as e:
                logger.error(f"Daily re-engagement failed for job {job.id}: {e}")
                continue

        for recruiter_id, digest in recruiter_digests.items():
            if digest["count"] == 0:
                continue
            from backend.database import User
            from backend.models.evaluation.profile import RecruiterProfile

            recruiter = (
                db.query(User)
                .join(RecruiterProfile, RecruiterProfile.user_id == User.id)
                .filter(User.id == recruiter_id)
                .first()
            )
            if (
                not recruiter
                or not recruiter.recruiter_profile
                or not recruiter.recruiter_profile.email
            ):
                continue
            try:
                jobs_list = ", ".join(digest["jobs"][:5])
                send_email(
                    recruiter.recruiter_profile.email,
                    "Re-engagement Opportunities Available",
                    f"<p>You have {digest['count']} re-engagement opportunities across your jobs.</p><p>Jobs: {jobs_list}</p>",
                )
            except Exception as e:
                logger.error(f"Digest email failed for recruiter {recruiter_id}: {e}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"daily_reengagement_digest failed: {e}")
        raise
    finally:
        db.close()


async def _scheduled_reports():
    await _check_scheduled_reports()


async def _activity_digest():
    db = SessionLocal()
    try:
        from backend.database import Application, BatchJob, Job, User
        from backend.email_utils import send_email

        company_ids = _active_company_ids(db)
        if not company_ids:
            return
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0)

        today_apps = (
            db.query(Application)
            .filter(
                Application.created_at >= today_start,
                Application.company_id.in_(company_ids),
            )
            .limit(1000)
            .all()
        )

        recruiter_apps: dict[int, int] = {}
        for app in today_apps:
            if app.status not in ("pending", "imported"):
                continue
            recruiter_id = None
            if app.job_id:
                job = db.query(Job).filter(Job.id == app.job_id).first()
                if job:
                    recruiter_id = job.recruiter_id
            elif app.batch_id:
                batch = db.query(BatchJob).filter(BatchJob.id == app.batch_id).first()
                if batch:
                    recruiter_id = batch.recruiter_id
            if recruiter_id:
                recruiter_apps[recruiter_id] = recruiter_apps.get(recruiter_id, 0) + 1

        for recruiter_id, new_count in recruiter_apps.items():
            recruiter = db.query(User).filter(User.id == recruiter_id).first()
            if not recruiter or not recruiter.email:
                continue
            try:
                send_email(
                    recruiter.email,
                    "Daily Recruitment Update",
                    f"<p>{new_count} new candidate(s) today.</p>",
                )
            except Exception as e:
                logger.error(f"Digest send failed for {recruiter.email}: {e}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"activity_digest failed: {e}")
        raise
    finally:
        db.close()


async def _scheduled_job(coro_factory, job_name: str):
    await _run_with_retry(coro_factory, job_name)


async def _subscription_period_cron():
    """Daily billing maintenance (Monetization S6).

    - Grants each active/trialing subscription's ``credits_monthly`` at
      ``current_period_start`` (idempotent per subscription + period).
    - Sends renewal reminders at period_end - 3d and period_end - 1d
      (once per period via ``renewal_reminder_sent``).
    - At ``current_period_end``: ``trialing`` -> ``expired``;
      ``cancel_at_period_end=True`` -> ``canceled`` (profile -> free);
      ``active`` -> ``past_due`` with ``grace_end = end + 3 days``.
    - Past grace: ``past_due`` -> ``expired`` (profile -> free).
    """
    from backend.credit_service import grant_credits
    from backend.database import (
        AuditLog,
        Subscription,
        SubscriptionPlan,
        User,
    )
    from backend.email_service import email_service
    from backend.subscription_lifecycle_service import log_subscription_history

    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        subs = (
            db.query(Subscription)
            .filter(Subscription.status.in_(["active", "trialing", "past_due"]))
            .all()
        )
        for sub in subs:
            try:
                user = db.query(User).filter(User.id == sub.user_id).first()
                if user is None:
                    continue
                if sub.company_id:
                    from backend.credit_service import resolve_company_billing_user

                    billing_user = resolve_company_billing_user(db, sub.company_id)
                    user = billing_user or user
                period_start = sub.current_period_start
                period_end = sub.current_period_end

                # 1. Monthly credit grant at period start (idempotent).
                if (
                    sub.status in ("active", "trialing")
                    and period_start
                    and period_start <= now
                ):
                    plan = (
                        db.query(SubscriptionPlan)
                        .filter(SubscriptionPlan.id == sub.plan_id)
                        .first()
                    )
                    if plan and plan.credits_monthly and user:
                        try:
                            grant_credits(
                                db,
                                user,
                                plan.credits_monthly,
                                provider="system",
                                provider_ref=f"sub-{sub.id}-period-{period_start.isoformat()}",
                                note=f"Monthly credit allocation for {plan.slug}",
                                tx_type="grant",
                            )
                        except Exception as ge:
                            logger.error(
                                f"[SUB CRON] credit grant failed for sub {sub.id}: {ge}"
                            )

                # 2. Renewal reminder at period_end - 3d / -1d.
                if (
                    sub.status == "active"
                    and period_end
                    and not sub.renewal_reminder_sent
                    and user
                ):
                    remaining = (period_end - now).total_seconds() / 86400.0
                    if remaining <= 3.0:
                        try:
                            email_service.send_subscription_status_email(
                                user, "renewal_reminder"
                            )
                            sub.renewal_reminder_sent = True
                            db.add(
                                AuditLog(
                                    user_id=user.id,
                                    action="subscription_renewal_reminder",
                                    target_id=str(sub.id),
                                    details=f"Renewal reminder sent for sub #{sub.id}",
                                )
                            )
                        except Exception as re_e:
                            logger.error(
                                f"[SUB CRON] renewal reminder failed for sub {sub.id}: {re_e}"
                            )

                # 3. Period-end transitions.
                if period_end and now >= period_end:
                    if sub.status == "trialing":
                        sub.status = "expired"
                        log_subscription_history(
                            db,
                            sub,
                            "expired",
                            notes="Trial ended at current_period_end (system cron)",
                        )
                    elif sub.status == "active":
                        if sub.cancel_at_period_end:
                            sub.status = "canceled"
                            sub.canceled_at = now
                            log_subscription_history(
                                db,
                                sub,
                                "canceled",
                                notes="Canceled at period end (system cron)",
                            )
                        else:
                            sub.status = "past_due"
                            sub.grace_end = period_end + timedelta(days=3)
                            log_subscription_history(
                                db,
                                sub,
                                "payment_received",
                                notes="Period ended; awaiting manual renewal — 3-day grace (system cron)",
                            )
                    if user:
                        rp = getattr(user, "recruiter_profile", None)
                        if rp:
                            rp.tier = "free"
                            rp.subscription_status = sub.status
                        cp = getattr(user, "candidate_profile", None)
                        if cp and hasattr(cp, "subscription_status"):
                            cp.subscription_status = sub.status

                # 4. Past grace: expire.
                if sub.status == "past_due" and sub.grace_end and now >= sub.grace_end:
                    sub.status = "expired"
                    log_subscription_history(
                        db,
                        sub,
                        "expired",
                        notes="Grace period ended without renewal (system cron)",
                    )
                    if user:
                        rp = getattr(user, "recruiter_profile", None)
                        if rp:
                            rp.tier = "free"
                            rp.subscription_status = "expired"
                        cp = getattr(user, "candidate_profile", None)
                        if cp and hasattr(cp, "subscription_status"):
                            cp.subscription_status = "expired"

                db.commit()
            except Exception as sub_e:
                db.rollback()
                logger.error(
                    f"[SUB CRON] sub {sub.id} processing failed: {sub_e}", exc_info=True
                )
    except Exception as e:
        db.rollback()
        logger.error(f"subscription_period_cron failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def _pending_payment_reminder_cron():
    """Daily reminder for pending manual-payment transactions (S10).

    Any Transaction still in ``pending`` (i.e. the user uploaded a proof
    or submitted an upgrade but no admin has approved/rejected it yet)
    triggers a nudge email. A transaction is only emailed again if it has
    aged past a 3-day quiet window since its creation so we never spam.
    """
    from backend.database import Transaction, User
    from backend.email_service import email_service
    from backend.logger import logger

    db = SessionLocal()
    try:
        now = datetime.now(UTC).replace(tzinfo=None)
        cutoff = now - timedelta(days=1)  # only remind requests older than 24h
        quiet = now - timedelta(days=3)  # min age before re-emailing is allowed
        txs = (
            db.query(Transaction)
            .filter(
                Transaction.status == "pending",
                Transaction.created_at <= cutoff,
            )
            .all()
        )
        sent = 0
        for tx in txs:
            try:
                if tx.created_at and tx.created_at > quiet:
                    continue
                user = db.query(User).filter(User.id == tx.user_id).first()
                if not user or not user.email:
                    continue
                email_service.send_subscription_status_email(user, "pending_reminder")
                tx.created_at = now  # reset quiet window so we don't spam daily
                sent += 1
                logger.info(
                    f"[S10] pending-payment reminder sent for tx #{tx.id} "
                    f"({getattr(tx, 'description', '') or 'subscription'})"
                )
            except Exception as tx_e:
                logger.error(f"[S10] pending reminder failed for tx #{tx.id}: {tx_e}")
        db.commit()
        logger.info(f"[S10] pending-payment reminder cron finished ({sent} sent)")
    except Exception as e:
        db.rollback()
        logger.error(f"pending_payment_reminder_cron failed: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    jobs = [
        (
            "interview_reminders",
            _check_interview_reminders,
            IntervalTrigger(minutes=15),
        ),
        (
            "offer_expirations",
            _check_offer_expirations,
            CronTrigger(hour="8,20", minute=0),
        ),
        ("data_cleanup", _cleanup_old_data, CronTrigger(hour=3, minute=0)),
        ("daily_ai_report", _daily_platform_report, CronTrigger(hour=4, minute=0)),
        ("pending_followup", _pending_followup, CronTrigger(hour=10, minute=0)),
        (
            "auto_interview_invite",
            _auto_interview_invite,
            CronTrigger(hour=9, minute=0),
        ),
        (
            "auto_reject_incomplete",
            _auto_reject_incomplete,
            CronTrigger(hour=8, minute=0),
        ),
        ("offer_escalation", _offer_escalation, CronTrigger(hour=18, minute=0)),
        ("activity_digest", _activity_digest, CronTrigger(hour=7, minute=0)),
        (
            "automation_no_activity",
            _automation_no_activity,
            CronTrigger(hour="*/2", minute=30),
        ),
        ("email_sequences", _email_sequences, CronTrigger(hour=9, minute=0)),
        ("drift_check", _drift_check, CronTrigger(hour=2, minute=0)),
        (
            "calibration_collection",
            _calibration_collection,
            CronTrigger(hour="*/12", minute=30),
        ),
        (
            "score_recalibration",
            _score_recalibration,
            CronTrigger(day_of_week="sun", hour=3, minute=0),
        ),
        (
            "drift_snapshot",
            _drift_snapshot_recording,
            CronTrigger(hour="*/6", minute=15),
        ),
        (
            "ab_experiment",
            _ab_experiment_conclusion,
            CronTrigger(hour="*/12", minute=45),
        ),
        (
            "daily_reengagement",
            _daily_reengagement_digest,
            CronTrigger(hour=6, minute=0),
        ),
        ("scheduled_reports", _scheduled_reports, CronTrigger(hour="*", minute=5)),
        (
            "subscription_period",
            _subscription_period_cron,
            CronTrigger(hour=1, minute=0),
        ),
        (
            "pending_payment_reminder",
            _pending_payment_reminder_cron,
            CronTrigger(hour=9, minute=30),
        ),
    ]

    for job_id, coro, trigger in jobs:
        scheduler.add_job(
            func=_scheduled_job,
            trigger=trigger,
            id=job_id,
            args=[lambda c=coro: c(), job_id],
            max_instances=1,
            replace_existing=True,
        )

    scheduler.start()
    logger.info(f"Async scheduler started with {len(jobs)} jobs")


def stop_scheduler():
    # The scheduler may never have been started when
    # SCHEDULER_ENABLED=false. APScheduler requires a running
    # event loop for shutdown(), so skip cleanly in that case.
    if scheduler.state == 0:
        logger.info("Async scheduler was not started; nothing to stop")
        return

    scheduler.shutdown(wait=False)
    logger.info("Async scheduler stopped")
