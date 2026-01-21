from datetime import datetime, timedelta, timezone
import argparse

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import db
from app.models.user import User
from app.models.email import Email
from app.models.account import Account


def _tables_exist() -> bool:
    # SQLite: verificar tablas mínimas para poder insertar
    try:
        inspector = db.inspect(db.engine)
        tables = set(inspector.get_table_names())
        return {"user", "email", "account"}.issubset(tables)
    except Exception:
        return False


DEMO_USERNAMES = {"demo_admin", "demo_user", "trueno"}
DEMO_ACCOUNT_EMAILS = {"demo_admin@example.com", "demo_user@example.com"}
DEMO_EMAILS = {
    "@demo_admin.example.com",
    "@demo_admin.mail.test",
    "@demo_user.example.com",
    "@demo_user.mail.test",
    "@trueno.example.com",
    "@trueno.mail.test",
    "@completed.demo.example",
    "@completed.demo2.example",
}

def delete_seed_for_users(user_ids: list[int]) -> None:
    """
    Elimina SOLO el seed generado por este script para user_ids dados.
    No borra usuarios.

    Patrones:
    - Emails: @u{uid}.seed{n}.example.com
    - Accounts: user{uid}.acc{n}@example.com
    """
    # Borrar accounts por patrón
    deleted_accounts_total = 0
    deleted_emails_total = 0
    for uid in user_ids:
        deleted_accounts_total += (
            Account.query.filter(
                Account.user_id == uid,
                Account.email.like(f"user{uid}.acc%@example.com"),
            ).delete(synchronize_session=False)
        )
        deleted_emails_total += (
            Email.query.filter(
                Email.user_id == uid,
                Email.email.like(f"@u{uid}.seed%.example.com"),
            ).delete(synchronize_session=False)
        )
    db.session.commit()
    print("OK: Seed eliminado para users:", user_ids)
    print("Deleted accounts:", deleted_accounts_total)
    print("Deleted emails:", deleted_emails_total)


def upsert_email(user_id: int, email_value: str, usage_count: int = 0, status: str = "active") -> Email:
    existing = Email.query.filter_by(user_id=user_id, email=email_value).first()
    if existing:
        existing.usage_count = usage_count
        existing.status = status
        return existing
    e = Email(user_id=user_id, email=email_value, usage_count=usage_count, status=status)
    db.session.add(e)
    return e


def upsert_account(user_id: int, email_value: str, password: str, user_agent: str = "seed/1.0") -> Account:
    existing = Account.query.filter_by(user_id=user_id, email=email_value).first()
    if existing:
        existing.user_agent = user_agent
        existing.password = password
        if not existing.cookie:
            existing.cookie = "{}"
        return existing
    a = Account(
        user_id=user_id,
        user_agent=user_agent,
        email=email_value,
        password=password,
        cookie="{}",
    )
    db.session.add(a)
    return a


def delete_demo_data() -> None:
    """
    Elimina SOLO los datos demo que este script insertó previamente:
    - Accounts con emails conocidos
    - Emails con dominios conocidos
    - Users con usernames conocidos (después de borrar sus FK dependientes)
    """
    # Borrar primero dependientes para evitar problemas FK
    deleted_accounts = Account.query.filter(Account.email.in_(DEMO_ACCOUNT_EMAILS)).delete(synchronize_session=False)
    deleted_emails = Email.query.filter(Email.email.in_(DEMO_EMAILS)).delete(synchronize_session=False)
    deleted_users = User.query.filter(User.username.in_(DEMO_USERNAMES)).delete(synchronize_session=False)
    db.session.commit()
    print("OK: Demo data eliminado")
    print("Deleted accounts:", deleted_accounts)
    print("Deleted emails:", deleted_emails)
    print("Deleted users:", deleted_users)


def seed_for_users(user_ids: list[int], email_count: int, account_count: int) -> None:
    # Validar usuarios existentes
    existing = {u.id for u in User.query.filter(User.id.in_(user_ids)).all()}
    missing = [uid for uid in user_ids if uid not in existing]
    if missing:
        raise RuntimeError(f"ERROR: No existen estos user_id en la DB: {missing}")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for uid in user_ids:
        # Emails (dominios estilo @dominio)
        for i in range(1, email_count + 1):
            domain = f"@u{uid}.seed{i}.example.com"
            usage = 0 if i % 3 else 1
            status = "active" if i % 7 else "completed"
            upsert_email(uid, domain, usage_count=usage, status=status)

        # Accounts
        for i in range(1, account_count + 1):
            acc_email = f"user{uid}.acc{i}@example.com"
            upsert_account(uid, acc_email, f"pass{uid}_{i}", user_agent="seed/2.0")

        # Refresh token_expiration para que login no “muera” por expiración en demos
        user = User.query.filter_by(id=uid).first()
        if user:
            user.token_expiration = now + timedelta(days=30)

    db.session.commit()
    print("OK: Seed para users completado")
    print("Users:", User.query.count())
    print("Emails:", Email.query.count())
    print("Accounts:", Account.query.count())


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed/cleanup de datos demo para api_login")
    parser.add_argument("--delete-demo", action="store_true", help="Elimina los datos demo que este script insertó")
    parser.add_argument(
        "--delete-seed",
        action="store_true",
        help="Elimina el seed generado por este script para los user_id indicados (no borra usuarios)",
    )
    parser.add_argument("--seed-users", action="store_true", help="Agrega datos de prueba para los user_id indicados (no crea usuarios)")
    parser.add_argument(
        "--user-ids",
        type=str,
        default="1,2",
        help="Lista de user_id separados por coma (default: 1,2). Ej: --user-ids 1,2,5",
    )
    parser.add_argument("--email-count", type=int, default=50, help="Cantidad de emails por usuario (default: 50)")
    parser.add_argument("--account-count", type=int, default=50, help="Cantidad de accounts por usuario (default: 50)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        print(f"DB: {db_uri}")

        if not _tables_exist():
            print("ERROR: No encuentro las tablas (user/email/account). Corre primero las migraciones: flask --app app db upgrade")
            return 2

        user_ids = [int(x.strip()) for x in args.user_ids.split(",") if x.strip()]

        if args.delete_demo:
            delete_demo_data()

        if args.delete_seed:
            delete_seed_for_users(user_ids)

        if args.seed_users:
            seed_for_users(user_ids, email_count=args.email_count, account_count=args.account_count)

        if not args.delete_demo and not args.delete_seed and not args.seed_users:
            print("Nada que hacer. Usa --delete-demo y/o --delete-seed y/o --seed-users")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())


