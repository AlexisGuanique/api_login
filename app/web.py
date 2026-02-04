from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import db
from app.models.account import Account
from app.models.email import Email
from app.models.user import User
from app.models.bot import Bot
from app.models.proxy import Proxy, ProxyKind
from app.services.encrypt import encrypt_service
from app.services.proxy_providers import DataimpulseProvider


web_bp = Blueprint("web", __name__)

@web_bp.app_template_filter("fmt_dt")
def fmt_dt(value) -> str:
    """
    Formatea datetime/ISO-string a 'dd-mm-aaaa hh:mm' para UI.
    Acepta: datetime | str (isoformat) | None
    """
    if not value:
        return ""
    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        # Soportar '2026-02-20 03:23:38' y '2026-02-20T03:23:38...'
        s = value.strip().replace("Z", "").replace("T", " ")
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            dt = None
    if not dt:
        return str(value)
    return dt.strftime("%d-%m-%Y %H:%M")


def _require_login():
    if not session.get("user_id") or not session.get("access_token"):
        return redirect(url_for("web.login"))
    return None


def _current_user() -> User | None:
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.filter_by(id=int(uid)).first()


@web_bp.get("/login")
def login():
    if session.get("user_id") and session.get("access_token"):
        return redirect(url_for("web.dashboard"))
    return render_template("login.html")


@web_bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username or not password:
        return render_template("login.html", error="Usuario y contraseña son requeridos"), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return render_template("login.html", error="Credenciales incorrectas"), 401

    # Soporta password hasheado o plano (tu API hace lo mismo)
    if not (check_password_hash(user.password, password) or user.password == password):
        return render_template("login.html", error="Credenciales incorrectas"), 401

    # Asegurar token no expirado; si no existe o es inválido, crearlo para habilitar UI + API.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not user.token_expiration or user.token_expiration <= now:
        user.token_expiration = now + timedelta(days=30)

    # Verificar si el token existe y es válido
    token_valid = False
    if user.access_token:
        try:
            jwt.decode(
                user.access_token,
                str(current_app.config["SECRET_KEY"]),
                algorithms=["HS256"],
                options={"verify_exp": False}
            )
            token_valid = True
        except jwt.InvalidTokenError:
            token_valid = False

    # Regenerar token si no existe o es inválido
    if not user.access_token or not token_valid:
        user.token_expiration = now + timedelta(days=30)
        user.access_token = jwt.encode(
            {"username": user.username, "exp": user.token_expiration},
            str(current_app.config["SECRET_KEY"]),
            algorithm="HS256",
        )

    db.session.commit()

    access_token = user.access_token
    user_id = user.id

    session["user_id"] = int(user_id)
    session["access_token"] = access_token
    session["name"] = user.name
    session["lastname"] = user.lastname
    return redirect(url_for("web.dashboard"))


@web_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))


@web_bp.get("/")
def dashboard():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    user_id = user.id
    accounts_count = Account.query.filter_by(user_id=user_id).count()
    emails_count = Email.query.filter_by(user_id=user_id).count()
    proxies_count = Proxy.query.filter_by(user_id=user_id).count()

    # Try to get stats from first active Dataimpulse proxy (ordered by created_at, limit 1)
    proxy_stats = None
    dataimpulse_proxy = Proxy.query.filter_by(
        user_id=user_id, kind=ProxyKind.DATAIMPULSE, is_active=True
    ).order_by(Proxy.created_at.asc()).limit(1).first()
    
    if dataimpulse_proxy and dataimpulse_proxy.username and dataimpulse_proxy.password:
        try:
            decrypted_password = encrypt_service.decrypt(dataimpulse_proxy.password)
            if decrypted_password:
                provider = DataimpulseProvider()
                stats = provider.get_status(dataimpulse_proxy.username, decrypted_password)
                proxy_stats = {
                    "proxy_name": dataimpulse_proxy.name,
                    "total_traffic": stats.total_traffic,
                    "traffic_used": stats.traffic_used,
                    "traffic_left": stats.traffic_left,
                    "used_threads": stats.used_threads,
                }
        except Exception:
            pass  # Silently fail if stats can't be fetched

    return render_template(
        "dashboard.html",
        user=user,
        accounts_count=accounts_count,
        emails_count=emails_count,
        proxies_count=proxies_count,
        proxy_stats=proxy_stats,
    )


@web_bp.get("/accounts")
def accounts():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    # Paginación + ordenamiento (server-side)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)  # Máximo 100 por página
    page = max(page, 1)

    sort = (request.args.get("sort") or "created_at").strip()
    direction = (request.args.get("dir") or "desc").strip().lower()
    direction = direction if direction in ("asc", "desc") else "desc"

    sort_map = {
        "id": Account.id,
        "email": Account.email,
        "password": Account.password,
        "cookie": Account.cookie,
        "user_agent": Account.user_agent,
        "created_at": Account.created_at,
        "updated_at": Account.updated_at,
        "user_id": Account.user_id,
    }
    sort_col = sort_map.get(sort, Account.created_at)

    order_expr = sort_col.asc() if direction == "asc" else sort_col.desc()
    query = Account.query.filter_by(user_id=user.id).order_by(order_expr)
    total = query.count()
    
    # Calcular offset y limit
    offset = (page - 1) * per_page
    accounts = query.offset(offset).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    return render_template(
        "accounts.html",
        user=user,
        accounts=[a.to_dict() if hasattr(a, "to_dict") else a for a in accounts],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        sort=sort if sort in sort_map else "created_at",
        dir=direction,
    )


@web_bp.get("/emails")
def emails():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    # Paginación + ordenamiento (server-side)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)  # Máximo 100 por página
    page = max(page, 1)

    sort = (request.args.get("sort") or "created_at").strip()
    direction = (request.args.get("dir") or "desc").strip().lower()
    direction = direction if direction in ("asc", "desc") else "desc"

    sort_map = {
        "id": Email.id,
        "email": Email.email,
        "status": Email.status,
        "usage_count": Email.usage_count,
        "created_at": Email.created_at,
        "user_id": Email.user_id,
    }
    sort_col = sort_map.get(sort, Email.created_at)

    order_expr = sort_col.asc() if direction == "asc" else sort_col.desc()
    query = Email.query.filter_by(user_id=user.id).order_by(order_expr)
    total = query.count()
    
    # Calcular offset y limit
    offset = (page - 1) * per_page
    emails = query.offset(offset).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    return render_template(
        "emails.html",
        user=user,
        emails=[e.to_dict() if hasattr(e, "to_dict") else e for e in emails],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        sort=sort if sort in sort_map else "created_at",
        dir=direction,
    )


@web_bp.get("/user")
def user_profile():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    return render_template("user.html", user=user)


@web_bp.post("/user")
def user_profile_post():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    name = (request.form.get("name") or "").strip()
    lastname = (request.form.get("lastname") or "").strip()
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if new_password or confirm_password:
        if new_password != confirm_password:
            return render_template("user.html", user=user, error="Las contraseñas no coinciden"), 400
        if len(new_password) < 6:
            return render_template("user.html", user=user, error="La contraseña debe tener al menos 6 caracteres"), 400
        user.password = generate_password_hash(new_password)

    user.name = name if name else None
    user.lastname = lastname if lastname else None
    db.session.commit()

    session["name"] = user.name
    session["lastname"] = user.lastname
    return render_template("user.html", user=user, success="Datos actualizados")


@web_bp.get("/bots")
def bots():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    # Limpiar bots que tienen socket_id = None pero estado != 'offline'
    # Esto corrige cualquier inconsistencia en la base de datos
    from app.database import db
    from datetime import datetime
    bots_to_fix = Bot.query.filter_by(user_id=user.id).filter(
        (Bot.socket_id.is_(None)) | (Bot.socket_id == ''),
        Bot.status != 'offline'
    ).all()
    
    if bots_to_fix:
        for bot in bots_to_fix:
            bot.status = 'offline'
        db.session.commit()
    
    bots_list = Bot.query.filter_by(user_id=user.id).order_by(Bot.last_seen.desc()).all()
    
    return render_template(
        "bots.html",
        user=user,
        bots=[b.to_dict() for b in bots_list],
    )


@web_bp.get("/proxies")
def proxies():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    # Paginación + ordenamiento
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    page = max(page, 1)

    sort = (request.args.get("sort") or "created_at").strip()
    direction = (request.args.get("dir") or "desc").strip().lower()
    direction = direction if direction in ("asc", "desc") else "desc"

    sort_map = {
        "name": Proxy.name,
        "host": Proxy.host,
        "port": Proxy.port,
        "kind": Proxy.kind,
        "created_at": Proxy.created_at,
    }
    sort_col = sort_map.get(sort, Proxy.created_at)

    order_expr = sort_col.asc() if direction == "asc" else sort_col.desc()
    query = Proxy.query.filter_by(user_id=user.id).order_by(order_expr)
    total = query.count()

    offset = (page - 1) * per_page
    proxies_list = query.offset(offset).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return render_template(
        "proxies.html",
        user=user,
        proxies=[p.to_dict() for p in proxies_list],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        sort=sort if sort in sort_map else "created_at",
        dir=direction,
    )


@web_bp.route("/proxies/create", methods=["GET", "POST"])
def proxy_create():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    form_data = {}
    error = None
    success = None

    if request.method == "POST":
        form_data = {
            "name": (request.form.get("name") or "").strip(),
            "host": (request.form.get("host") or "").strip(),
            "port": request.form.get("port", ""),
            "kind": request.form.get("kind", "unknown"),
            "username": (request.form.get("username") or "").strip(),
            "password": request.form.get("password", ""),
            "is_active": request.form.get("is_active") == "on",
        }

        if not form_data["name"] or not form_data["host"] or not form_data["port"]:
            error = "Nombre, Host y Puerto son requeridos."
        else:
            try:
                port = int(form_data["port"])
                try:
                    kind = ProxyKind(form_data["kind"])
                except ValueError:
                    kind = ProxyKind.UNKNOWN

                encrypted_password = None
                if form_data["password"]:
                    encrypted_password = encrypt_service.encrypt(form_data["password"])

                new_proxy = Proxy(
                    user_id=user.id,
                    name=form_data["name"],
                    host=form_data["host"],
                    port=port,
                    kind=kind,
                    username=form_data["username"] or None,
                    password=encrypted_password,
                    is_active=form_data["is_active"],
                )
                db.session.add(new_proxy)
                db.session.commit()
                return redirect(url_for("web.proxies"))
            except ValueError:
                error = "Puerto debe ser un número válido."
            except Exception as e:
                db.session.rollback()
                error = f"Error al crear proxy: {str(e)}"

    return render_template(
        "proxy_create.html",
        user=user,
        form_data=form_data,
        error=error,
        success=success,
    )


@web_bp.route("/proxies/<int:proxy_id>/edit", methods=["GET", "POST"])
def proxy_edit(proxy_id):
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    proxy = Proxy.query.filter_by(id=proxy_id, user_id=user.id).first()
    if not proxy:
        return redirect(url_for("web.proxies"))

    error = None
    success = None

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        host = (request.form.get("host") or "").strip()
        port_str = request.form.get("port", "")
        kind_str = request.form.get("kind", "unknown")
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password", "")
        is_active = request.form.get("is_active") == "on"

        if not name or not host or not port_str:
            error = "Nombre, Host y Puerto son requeridos."
        else:
            try:
                port = int(port_str)
                try:
                    kind = ProxyKind(kind_str)
                except ValueError:
                    kind = ProxyKind.UNKNOWN

                proxy.name = name
                proxy.host = host
                proxy.port = port
                proxy.kind = kind
                proxy.username = username or None
                proxy.is_active = is_active

                # Solo actualizar password si se proporciona uno nuevo
                if password:
                    proxy.password = encrypt_service.encrypt(password)

                db.session.commit()
                success = "Proxy actualizado exitosamente."
            except ValueError:
                error = "Puerto debe ser un número válido."
            except Exception as e:
                db.session.rollback()
                error = f"Error al actualizar proxy: {str(e)}"

    return render_template(
        "proxy_edit.html",
        user=user,
        proxy=proxy.to_dict(),
        error=error,
        success=success,
    )
