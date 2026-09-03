import os
import shutil

from sqlalchemy.orm import Session

from backend.database import Application, SessionLocal
from backend.logger import logger


def cleanup_interview_storage(dry_run=True, max_days=None):
    """
    Enhanced Cleanup:
    1. Groups applications by Email (Identifies guest and registered candidates).
    2. Keeps media ONLY for the most recent application of each candidate.
    3. Option to also delete media older than `max_days` if provided.
    """
    db: Session = SessionLocal()
    try:
        total_freed_mb = 0
        logger.info(f"Starting Enhanced Storage Cleanup (Dry Run: {dry_run})")

        # 1. Get all unique emails from applications
        emails = (
            db.query(Application.email)
            .filter(Application.email is not None)
            .distinct()
            .all()
        )
        emails = [e[0] for e in emails]

        logger.info(f"Found {len(emails)} unique candidate identities (emails)")

        for email in emails:
            # Get all apps for this email
            apps = (
                db.query(Application)
                .filter(Application.email == email, Application.deleted_at.is_(None))
                .order_by(Application.created_at.desc())
                .all()
            )

            if not apps:
                continue

            # Identify the LATEST application
            apps[0]
            older_apps = apps[1:]

            # Logic: Keep media for latest_app, delete for all older_apps
            # (regardless of how many there are)

            # Delete older media
            for app in older_apps:
                app_folder = os.path.join("uploads", "interviews", str(app.id))
                if os.path.exists(app_folder):
                    size_bytes = sum(
                        os.path.getsize(os.path.join(dp, f))
                        for dp, dn, filenames in os.walk(app_folder)
                        for f in filenames
                    )
                    total_freed_mb += size_bytes / (1024 * 1024)
                    if not dry_run:
                        shutil.rmtree(app_folder)
                        logger.info(
                            f"Deleted OLD media: app {app.id} (Candidate: {email})"
                        )
                    else:
                        logger.info(
                            f"[DRY RUN] Would delete OLD media: app {app.id} (Candidate: {email}) - {size_bytes / 1024 / 1024:.2f} MB"
                        )

        # 2. Orphaned Folder Cleanup (folders with no matching app in DB)
        interviews_base = os.path.join("uploads", "interviews")
        if os.path.exists(interviews_base):
            app_ids = set(r[0] for r in db.query(Application.id).all())
            for folder_name in os.listdir(interviews_base):
                folder_path = os.path.join(interviews_base, folder_name)
                if not os.path.isdir(folder_path):
                    continue
                try:
                    fid = int(folder_name)
                    if fid not in app_ids:
                        size_bytes = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, dn, filenames in os.walk(folder_path)
                            for f in filenames
                        )
                        total_freed_mb += size_bytes / (1024 * 1024)
                        if not dry_run:
                            shutil.rmtree(folder_path)
                            logger.info(f"Deleted ORPHAN: {folder_path}")
                        else:
                            logger.info(
                                f"[DRY RUN] Would delete ORPHAN: {folder_path} - {size_bytes / 1024 / 1024:.2f} MB"
                            )
                except Exception:
                    pass

        logger.info(
            f"Enhanced Cleanup Complete. Total identified: {total_freed_mb:.2f} MB"
        )
        return total_freed_mb

    except Exception as e:
        logger.error(f"Enhanced Cleanup script failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import sys

    is_dry = "--commit" not in sys.argv
    cleanup_interview_storage(dry_run=is_dry)
