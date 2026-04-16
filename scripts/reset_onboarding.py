"""Reset the onboarding flag for every user so they see the wizard again.

One user email is preserved (default: crb1898@gmail.com) so the admin
keeps their live setup intact.

Usage:
    python -m scripts.reset_onboarding                          # dry-run
    python -m scripts.reset_onboarding --apply                  # actually write
    python -m scripts.reset_onboarding --apply --keep other@x   # preserve a different email

Runs against whichever database `create_app()` resolves, so set
FLASK_ENV=production + DATABASE_URL before invoking for the prod DB.
"""
from __future__ import annotations

import argparse


def main():
    parser = argparse.ArgumentParser(description="Reset onboarding flag for all users")
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually commit the change. Without this flag, only prints what would change.",
    )
    parser.add_argument(
        "--keep", default="crb1898@gmail.com",
        help="Email address to preserve (case-insensitive). Default: crb1898@gmail.com",
    )
    parser.add_argument(
        "--clear-answers", action="store_true",
        help="Also wipe the saved onboarding_answers JSON blob.",
    )
    args = parser.parse_args()

    from app import create_app
    from app.extensions import db
    from app.models.user import User
    from app.models.settings import UserSettings

    keep_email = (args.keep or "").strip().lower()

    app = create_app()
    with app.app_context():
        preserved_user = None
        if keep_email:
            preserved_user = (
                User.query
                .filter(db.func.lower(User.email) == keep_email)
                .first()
            )

        preserved_id = preserved_user.id if preserved_user else None

        q = UserSettings.query.filter(UserSettings.onboarding_completed.is_(True))
        if preserved_id is not None:
            q = q.filter(UserSettings.user_id != preserved_id)

        rows = q.all()

        print(f"Database: {app.config.get('SQLALCHEMY_DATABASE_URI', '<unset>')}")
        if preserved_user:
            print(f"Preserving: {preserved_user.email} (user_id={preserved_id})")
        else:
            print(f"WARNING: no user found matching --keep '{args.keep}'. Nothing will be preserved.")
        print(f"Rows to reset: {len(rows)}")

        if not rows:
            print("Nothing to do.")
            return

        if not args.apply:
            preview = ", ".join(str(r.user_id) for r in rows[:20])
            more = "" if len(rows) <= 20 else f", ... (+{len(rows) - 20} more)"
            print(f"user_ids affected: {preview}{more}")
            print("Dry-run only. Re-run with --apply to commit.")
            return

        for s in rows:
            s.onboarding_completed = False
            if args.clear_answers:
                s.onboarding_answers = None
        db.session.commit()
        print(f"Reset {len(rows)} users.")


if __name__ == "__main__":
    main()
