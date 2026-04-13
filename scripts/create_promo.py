"""Create a promo code from the command line.

Usage:
    python -m scripts.create_promo --code FRIENDS2026 --days 90 --expires 7 --note "Friends & family"

    --code      The promo code (will be uppercased)
    --days      Trial days granted (default 90)
    --expires   Days until code expires (default 7)
    --max-uses  Max redemptions (default unlimited)
    --note      Optional description
"""
import argparse
from datetime import datetime, timezone, timedelta


def main():
    parser = argparse.ArgumentParser(description="Create a promo code")
    parser.add_argument("--code", required=True)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--expires", type=int, default=7, help="Days until expiry")
    parser.add_argument("--max-uses", type=int, default=None)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    from app import create_app
    app = create_app()
    with app.app_context():
        from app.extensions import db
        from app.models.user import PromoCode

        code = args.code.strip().upper()
        existing = PromoCode.query.filter_by(code=code).first()
        if existing:
            print(f"Code '{code}' already exists (id={existing.id}, used {existing.times_used}x)")
            return

        promo = PromoCode(
            code=code,
            trial_days=args.days,
            max_uses=args.max_uses,
            expires_at=datetime.now(timezone.utc) + timedelta(days=args.expires),
            note=args.note or f"{args.days}-day trial promo",
        )
        db.session.add(promo)
        db.session.commit()
        print(f"Created promo code: {promo.code}")
        print(f"  Trial days: {promo.trial_days}")
        print(f"  Expires: {promo.expires_at.isoformat()}")
        print(f"  Max uses: {promo.max_uses or 'unlimited'}")
        print(f"  Share link: https://nickelanddime.io/register?promo={promo.code}")


if __name__ == "__main__":
    main()
