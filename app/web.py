from __future__ import annotations

import json
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
from app.models.vps import VPS
from app.models.contabo_config import ContaboConfig
from app.models.bot_global_config import BotGlobalConfig
from app.models.bot_browser_presence import BotBrowserPresence
from app.models.bot_browser_user_agent import BotBrowserUserAgent
from app.models.bot_domain_global_config import BotDomainGlobalConfig
from app.models.bot_domain_entry import BotDomainEntry
from app.models.bot_random_tld_entry import BotRandomTldEntry
from app.utils.bot_preferences import get_preferred_browsers_list
from app.services.encrypt import encrypt_service
from app.services.proxy_providers import DataimpulseProvider
from app.services.contabo import ContaboService, sync_instances_to_db
from app.services.contabo_encrypt import contabo_encrypt_service


web_bp = Blueprint("web", __name__)


def _get_browser_options_for_user(user_id: int) -> list[str]:
    """
    Devuelve opciones de navegador para configuración global.
    Regla: usar la intersección de navegadores entre bots conectados.
    Si no hay bots conectados, usar la unión histórica del usuario.
    """
    connected_bots = (
        Bot.query
        .filter_by(user_id=user_id)
        .filter_by(bot_type='creador')
        .filter((Bot.socket_id.isnot(None)) & (Bot.socket_id != ''))
        .all()
    )
    connected_bot_ids = [b.id for b in connected_bots]

    if connected_bot_ids:
        rows = BotBrowserPresence.query.filter(BotBrowserPresence.bot_id.in_(connected_bot_ids)).all()
        by_bot = {bot_id: set() for bot_id in connected_bot_ids}
        for row in rows:
            by_bot.setdefault(row.bot_id, set()).add(row.browser_name)

        sets = list(by_bot.values())
        common = set.intersection(*sets) if sets else set()
        return sorted(common, key=lambda x: x.lower())

    # Fallback cuando no hay bots conectados: unión histórica
    rows = BotBrowserPresence.query.filter_by(user_id=user_id).all()
    union_names = {row.browser_name for row in rows}
    return sorted(union_names, key=lambda x: x.lower())


def _build_bot_compatibility_matrix(user_id: int, selected_browsers: list[str]):
    """
    Construye datos de compatibilidad por bot (bot x navegador).
    """
    bots = (
        Bot.query
        .filter_by(user_id=user_id, bot_type='creador')
        .order_by(Bot.last_seen.desc())
        .all()
    )
    presence_rows = BotBrowserPresence.query.filter_by(user_id=user_id).all()

    by_bot_names: dict[int, set[str]] = {}
    by_bot_last_sync: dict[int, datetime] = {}
    all_names: set[str] = set()

    for row in presence_rows:
        by_bot_names.setdefault(row.bot_id, set()).add(row.browser_name)
        all_names.add(row.browser_name)
        current_last_sync = by_bot_last_sync.get(row.bot_id)
        if current_last_sync is None or row.last_seen > current_last_sync:
            by_bot_last_sync[row.bot_id] = row.last_seen

    browser_headers = sorted(all_names, key=lambda x: x.lower())
    sel_set = {s for s in selected_browsers if s}
    selected_exists_in_any_bot = bool(sel_set) and all(s in all_names for s in sel_set)
    rows = []
    for bot in bots:
        bot_names = by_bot_names.get(bot.id, set())
        missing_any = bool(sel_set) and any(s not in bot_names for s in sel_set)
        rows.append({
            "bot": bot,
            "browser_names": bot_names,
            "last_sync": by_bot_last_sync.get(bot.id),
            "missing_selected": missing_any,
        })

    return browser_headers, rows, selected_exists_in_any_bot


def _get_user_agent_map(user_id: int, browser_names: list[str]) -> dict[str, str]:
    if not browser_names:
        return {}
    rows = (
        BotBrowserUserAgent.query
        .filter_by(user_id=user_id)
        .filter(BotBrowserUserAgent.browser_name.in_(browser_names))
        .all()
    )
    return {row.browser_name: row.user_agent for row in rows}


def _get_missing_user_agent_browsers(browser_names: list[str], user_agent_map: dict[str, str]) -> list[str]:
    missing = []
    for name in browser_names:
        if not (user_agent_map.get(name) or "").strip():
            missing.append(name)
    return missing


def _normalize_domain_text(value: str) -> str:
    domain = (value or "").strip()
    if not domain:
        return ""
    return domain if domain.startswith("@") else f"@{domain}"


def _normalize_tld_text(value: str) -> str:
    return (value or "").strip().lstrip(".").lower()


def _apply_domain_global_from_form(user: User) -> None:
    """Actualiza BotDomainGlobalConfig desde request.form (sin commit)."""
    domain_mode = (request.form.get("domain_mode") or "33mail").strip()
    random_fill_domain = request.form.get("random_fill_domain") == "on"
    default_domain = _normalize_domain_text(request.form.get("default_domain") or "")

    domain_cfg = BotDomainGlobalConfig.query.filter_by(user_id=user.id).first()
    if not domain_cfg:
        domain_cfg = BotDomainGlobalConfig(user_id=user.id)
        db.session.add(domain_cfg)

    if domain_mode == "random":
        domain_cfg.is33mail = False
        domain_cfg.random_domains = True
    elif domain_mode == "custom":
        domain_cfg.is33mail = False
        domain_cfg.random_domains = False
    else:
        domain_cfg.is33mail = True
        domain_cfg.random_domains = False
    domain_cfg.fill_domain = random_fill_domain
    domain_cfg.domain = default_domain or None


def _get_domain_config_bundle(user_id: int):
    global_cfg = BotDomainGlobalConfig.query.filter_by(user_id=user_id).first()
    domain_entries = (
        BotDomainEntry.query
        .filter_by(user_id=user_id)
        .order_by(BotDomainEntry.id.asc())
        .all()
    )
    random_tld_entries = (
        BotRandomTldEntry.query
        .filter_by(user_id=user_id)
        .order_by(BotRandomTldEntry.sort_order.asc(), BotRandomTldEntry.id.asc())
        .all()
    )
    if not global_cfg:
        global_cfg = BotDomainGlobalConfig(
            user_id=user_id,
            is33mail=True,
            random_domains=False,
            fill_domain=False,
            domain=None,
        )
    return global_cfg, domain_entries, random_tld_entries


def _render_bot_config_page(
    user: User,
    *,
    error: str | None = None,
    success: str | None = None,
    selected_browsers_override: list[str] | None = None,
    user_agent_map_override: dict[str, str] | None = None,
    status_code: int = 200,
):
    browser_config = BotGlobalConfig.query.filter_by(user_id=user.id).first()
    selected_browsers = (
        list(selected_browsers_override)
        if selected_browsers_override is not None
        else get_preferred_browsers_list(browser_config)
    )
    browser_options = _get_browser_options_for_user(user.id)
    matrix_headers, matrix_rows, selected_exists_in_any_bot = _build_bot_compatibility_matrix(
        user.id, selected_browsers
    )
    user_agent_map = _get_user_agent_map(user.id, matrix_headers)
    if user_agent_map_override:
        user_agent_map.update(user_agent_map_override)
    missing_ua_browsers = _get_missing_user_agent_browsers(selected_browsers, user_agent_map)

    domain_cfg, domain_entries, random_tld_entries = _get_domain_config_bundle(user.id)

    return render_template(
        "bot_config.html",
        user=user,
        browser_config=browser_config,
        selected_browsers=selected_browsers,
        browser_options=browser_options,
        matrix_headers=matrix_headers,
        matrix_rows=matrix_rows,
        selected_exists_in_any_bot=selected_exists_in_any_bot,
        user_agent_map=user_agent_map,
        missing_ua_browsers=missing_ua_browsers,
        domain_cfg=domain_cfg,
        domain_entries=domain_entries,
        random_tld_entries=random_tld_entries,
        error=error,
        success=success,
    ), status_code

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
    bots_count = Bot.query.filter_by(user_id=user_id).count()
    
    # Contar bots por tipo
    logueadores_count = Bot.query.filter_by(user_id=user_id, bot_type='logueador').count()
    creadores_count = Bot.query.filter_by(user_id=user_id, bot_type='creador').count()
    proxies_count = Proxy.query.filter_by(user_id=user_id).count()
    
    # Contar VPS por CPU
    from sqlalchemy import func
    vps_by_cpu = db.session.query(
        VPS.cpu_cores,
        func.count(VPS.id).label('count')
    ).filter_by(user_id=user_id).group_by(VPS.cpu_cores).order_by(VPS.cpu_cores).all()
    
    vps_total = VPS.query.filter_by(user_id=user_id).count()
    vps_by_cpu_dict = {str(cpu): count for cpu, count in vps_by_cpu} if vps_by_cpu else {}
    
    # Obtener cuentas por hora (últimas 24 horas)
    from datetime import datetime, timedelta
    from sqlalchemy import text
    now = datetime.utcnow()
    hours_ago_24 = now - timedelta(hours=24)
    
    # Agrupar cuentas por hora usando SQLite date functions
    # SQLite almacena fechas como strings, necesitamos usar strftime
    try:
        accounts_by_hour_raw = db.session.execute(
            text("""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', created_at) as hour,
                    COUNT(*) as count
                FROM account
                WHERE user_id = :user_id 
                AND datetime(created_at) >= datetime(:hours_ago)
                GROUP BY strftime('%Y-%m-%d %H:00:00', created_at)
                ORDER BY hour
            """),
            {"user_id": user_id, "hours_ago": hours_ago_24.strftime('%Y-%m-%d %H:%M:%S')}
        ).fetchall()
        
        accounts_by_hour = [(row[0], row[1]) for row in accounts_by_hour_raw]
    except Exception as e:
        # Fallback: obtener todas las cuentas y agrupar en Python
        accounts = Account.query.filter(
            Account.user_id == user_id,
            Account.created_at >= hours_ago_24
        ).all()
        
        accounts_dict_temp = {}
        for account in accounts:
            hour_key = account.created_at.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:00:00')
            accounts_dict_temp[hour_key] = accounts_dict_temp.get(hour_key, 0) + 1
        
        accounts_by_hour = list(accounts_dict_temp.items())
    
    # Preparar datos para el gráfico (últimas 24 horas)
    chart_labels = []
    chart_data = []
    current_hour = hours_ago_24.replace(minute=0, second=0, microsecond=0)
    
    # Crear un diccionario con los datos existentes
    accounts_dict = {hour: count for hour, count in accounts_by_hour}
    
    # Llenar todas las horas (incluso las que no tienen cuentas)
    for i in range(24):
        hour_key = current_hour.strftime('%Y-%m-%d %H:00:00')
        chart_labels.append(current_hour.strftime('%H:00'))
        chart_data.append(accounts_dict.get(hour_key, 0))
        current_hour += timedelta(hours=1)

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
        bots_count=bots_count,
        logueadores_count=logueadores_count,
        creadores_count=creadores_count,
        proxies_count=proxies_count,
        proxy_stats=proxy_stats,
        vps_total=vps_total,
        vps_by_cpu=vps_by_cpu_dict,
        accounts_chart_labels=chart_labels,
        accounts_chart_data=chart_data,
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


@web_bp.get("/bot-config")
def bot_config():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    return _render_bot_config_page(user)


@web_bp.post("/bot-config")
def bot_config_post():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    browser_config = BotGlobalConfig.query.filter_by(user_id=user.id).first()
    if not browser_config:
        browser_config = BotGlobalConfig(user_id=user.id)
        db.session.add(browser_config)

    # Formulario unificado: modo de dominio va en el mismo POST que navegadores/UA
    if request.form.get("domain_mode") is not None:
        _apply_domain_global_from_form(user)

    browser_options = _get_browser_options_for_user(user.id)
    raw_selected = request.form.getlist("preferred_browsers")
    seen_lower: set[str] = set()
    selected_browsers: list[str] = []
    for s in raw_selected:
        t = (s or "").strip()
        if not t:
            continue
        k = t.lower()
        if k in seen_lower:
            continue
        seen_lower.add(k)
        selected_browsers.append(t)

    for b in selected_browsers:
        if b not in browser_options:
            return _render_bot_config_page(
                user,
                error="Uno o más navegadores marcados no existen en el catálogo sincronizado de tus bots.",
                selected_browsers_override=selected_browsers,
                status_code=400,
            )

    # UA por fila del catálogo (índice alineado con browser_options en la plantilla)
    missing_ua: list[str] = []
    for i, b in enumerate(browser_options):
        ua = (request.form.get(f"ua_{i}") or "").strip()
        if b not in selected_browsers:
            continue
        if ua:
            continue
        existing = BotBrowserUserAgent.query.filter_by(
            user_id=user.id,
            browser_name=b,
        ).first()
        if not (existing and (existing.user_agent or "").strip()):
            missing_ua.append(b)

    if missing_ua:
        return _render_bot_config_page(
            user,
            error=(
                "Debes configurar User-Agent en el servidor para cada navegador global marcado. "
                f"Falta: {', '.join(missing_ua)}"
            ),
            selected_browsers_override=selected_browsers,
            status_code=400,
        )

    if selected_browsers:
        browser_config.preferred_browsers_json = json.dumps(selected_browsers)
        browser_config.preferred_browser = selected_browsers[0]
    else:
        browser_config.preferred_browsers_json = None
        browser_config.preferred_browser = None

    # Creator: ciclo / hora (se envía al bot con execute_creator)
    ct = (request.form.get("creator_time_config_type") or "cycle").strip().lower()
    if ct not in ("manual", "scheduled", "cycle", "both"):
        ct = "cycle"
    browser_config.creator_time_config_type = ct
    try:
        cm_raw = request.form.get("creator_cycle_minutes")
        browser_config.creator_cycle_time_minutes = (
            int(cm_raw) if cm_raw not in (None, "") else None
        )
    except ValueError:
        browser_config.creator_cycle_time_minutes = None
    try:
        apc_raw = request.form.get("creator_accounts_per_cycle")
        browser_config.creator_accounts_per_cycle = (
            int(apc_raw) if apc_raw not in (None, "") else None
        )
    except ValueError:
        browser_config.creator_accounts_per_cycle = None
    st = (request.form.get("creator_scheduled_time") or "").strip()
    browser_config.creator_scheduled_time = st or None
    tz = (request.form.get("creator_timezone") or "").strip()
    browser_config.creator_timezone = tz or None

    for i, b in enumerate(browser_options):
        ua = (request.form.get(f"ua_{i}") or "").strip()
        existing = BotBrowserUserAgent.query.filter_by(
            user_id=user.id,
            browser_name=b,
        ).first()
        if ua:
            if existing:
                existing.user_agent = ua
            else:
                db.session.add(
                    BotBrowserUserAgent(
                        user_id=user.id,
                        browser_name=b,
                        user_agent=ua,
                    )
                )
        else:
            if existing and b not in selected_browsers:
                db.session.delete(existing)

    db.session.commit()
    success_msg = (
        "Configuración global guardada (navegadores, User-Agent y modo de dominios)."
        if request.form.get("domain_mode") is not None
        else "Configuración de navegador(es) y User-Agent guardada."
    )
    return _render_bot_config_page(
        user,
        selected_browsers_override=get_preferred_browsers_list(browser_config),
        success=success_msg,
    )


@web_bp.post("/bot-config/domain-settings")
def bot_config_domain_settings_post():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    _apply_domain_global_from_form(user)

    db.session.commit()
    return _render_bot_config_page(user, success="Configuración global de dominios guardada.")


@web_bp.post("/bot-config/domain/create")
def bot_config_domain_create():
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    domain_text = _normalize_domain_text(request.form.get("domain_new") or request.form.get("domain") or "")
    if not domain_text:
        return _render_bot_config_page(user, error="Debes indicar un dominio válido.", status_code=400)

    exists = BotDomainEntry.query.filter_by(user_id=user.id, domain=domain_text).first()
    if exists:
        return _render_bot_config_page(user, error="Ese dominio ya existe en servidor.", status_code=400)

    db.session.add(BotDomainEntry(
        user_id=user.id,
        domain=domain_text,
        fill_domain=request.form.get("fill_domain_new") == "on" or request.form.get("fill_domain") == "on",
        is_active=request.form.get("is_active_new") == "on" or request.form.get("is_active") == "on",
    ))
    db.session.commit()
    return _render_bot_config_page(user, success="Dominio agregado en servidor.")


@web_bp.post("/bot-config/domain/<int:domain_id>/update")
def bot_config_domain_update(domain_id: int):
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    row = BotDomainEntry.query.filter_by(id=domain_id, user_id=user.id).first()
    if not row:
        return _render_bot_config_page(user, error="Dominio no encontrado.", status_code=404)

    domain_text = _normalize_domain_text(
        request.form.get(f"domain_update_{domain_id}") or request.form.get("domain") or ""
    )
    if not domain_text:
        return _render_bot_config_page(user, error="Debes indicar un dominio válido.", status_code=400)

    duplicate = (
        BotDomainEntry.query
        .filter(BotDomainEntry.user_id == user.id, BotDomainEntry.domain == domain_text, BotDomainEntry.id != row.id)
        .first()
    )
    if duplicate:
        return _render_bot_config_page(user, error="Ese dominio ya existe en otro registro.", status_code=400)

    row.domain = domain_text
    row.fill_domain = request.form.get(f"fill_domain_update_{domain_id}") == "on"
    row.is_active = request.form.get(f"is_active_update_{domain_id}") == "on"
    db.session.commit()
    return _render_bot_config_page(user, success="Dominio actualizado.")


@web_bp.post("/bot-config/domain/<int:domain_id>/delete")
def bot_config_domain_delete(domain_id: int):
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    row = BotDomainEntry.query.filter_by(id=domain_id, user_id=user.id).first()
    if not row:
        return _render_bot_config_page(user, error="Dominio no encontrado.", status_code=404)
    db.session.delete(row)
    db.session.commit()
    return _render_bot_config_page(user, success="Dominio eliminado.")


@web_bp.post("/bot-config/tld/create")
def bot_config_tld_create():
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    tld = _normalize_tld_text(request.form.get("tld") or "")
    if not tld:
        return _render_bot_config_page(user, error="Debes indicar una terminación válida.", status_code=400)

    exists = BotRandomTldEntry.query.filter_by(user_id=user.id, tld=tld).first()
    if exists:
        return _render_bot_config_page(user, error="Esa terminación ya existe.", status_code=400)

    max_order = db.session.query(db.func.max(BotRandomTldEntry.sort_order)).filter_by(user_id=user.id).scalar()
    next_order = int(max_order or -1) + 1
    db.session.add(BotRandomTldEntry(user_id=user.id, tld=tld, sort_order=next_order))
    db.session.commit()
    return _render_bot_config_page(user, success="Terminación añadida.")


@web_bp.post("/bot-config/tld/<int:tld_id>/update")
def bot_config_tld_update(tld_id: int):
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    row = BotRandomTldEntry.query.filter_by(id=tld_id, user_id=user.id).first()
    if not row:
        return _render_bot_config_page(user, error="Terminación no encontrada.", status_code=404)

    tld = _normalize_tld_text(request.form.get("tld") or "")
    if not tld:
        return _render_bot_config_page(user, error="Debes indicar una terminación válida.", status_code=400)

    duplicate = (
        BotRandomTldEntry.query
        .filter(BotRandomTldEntry.user_id == user.id, BotRandomTldEntry.tld == tld, BotRandomTldEntry.id != row.id)
        .first()
    )
    if duplicate:
        return _render_bot_config_page(user, error="Esa terminación ya existe en otro registro.", status_code=400)

    row.tld = tld
    db.session.commit()
    return _render_bot_config_page(user, success="Terminación actualizada.")


@web_bp.post("/bot-config/tld/<int:tld_id>/delete")
def bot_config_tld_delete(tld_id: int):
    guard = _require_login()
    if guard:
        return guard
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    row = BotRandomTldEntry.query.filter_by(id=tld_id, user_id=user.id).first()
    if not row:
        return _render_bot_config_page(user, error="Terminación no encontrada.", status_code=404)
    db.session.delete(row)
    db.session.commit()
    return _render_bot_config_page(user, success="Terminación eliminada.")


@web_bp.get("/accounts/hourly-stats")
def accounts_hourly_stats():
    """Endpoint para obtener estadísticas de cuentas por hora (accesible desde sesión web)"""
    guard = _require_login()
    if guard:
        return guard
    
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))
    
    try:
        from datetime import timedelta
        from flask import jsonify
        
        # Calcular la fecha de inicio (últimas 24 horas)
        now = datetime.utcnow()
        start_time = now - timedelta(hours=24)
        
        # Obtener todas las cuentas del usuario creadas en las últimas 24 horas
        accounts = Account.query.filter(
            Account.user_id == user.id,
            Account.created_at >= start_time
        ).all()
        
        print(f"📊 Cuentas encontradas en últimas 24h: {len(accounts)}")
        
        # Agrupar por hora
        hourly_counts = {}
        
        # Inicializar todas las horas de las últimas 24 horas con 0
        for i in range(24):
            hour_time = now - timedelta(hours=i)
            hour_key = hour_time.strftime('%Y-%m-%d %H:00')
            hourly_counts[hour_key] = 0
        
        # Contar cuentas por hora
        for account in accounts:
            # Redondear a la hora más cercana
            account_hour = account.created_at.replace(minute=0, second=0, microsecond=0)
            hour_key = account_hour.strftime('%Y-%m-%d %H:00')
            
            if hour_key in hourly_counts:
                hourly_counts[hour_key] += 1
        
        # Convertir a lista ordenada (más reciente primero)
        hourly_data = []
        for i in range(24):
            hour_time = now - timedelta(hours=i)
            hour_key = hour_time.strftime('%Y-%m-%d %H:00')
            hourly_data.append({
                'hour': hour_time.strftime('%H:00'),
                'date': hour_time.strftime('%Y-%m-%d'),
                'count': hourly_counts.get(hour_key, 0)
            })
        
        # Invertir para mostrar de más antiguo a más reciente
        hourly_data.reverse()
        
        # Calcular promedio de las últimas 6 horas
        last_6_hours_data = hourly_data[-6:] if len(hourly_data) >= 6 else hourly_data
        last_6_hours_total = sum(item['count'] for item in last_6_hours_data)
        last_6_hours_avg = last_6_hours_total / len(last_6_hours_data) if len(last_6_hours_data) > 0 else 0
        
        # Calcular total de cuentas creadas hoy (desde medianoche UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_accounts = Account.query.filter(
            Account.user_id == user.id,
            Account.created_at >= today_start
        ).count()
        
        print(f"📊 Datos por hora generados: {len(hourly_data)} horas")
        print(f"📊 Total de cuentas en período: {len(accounts)}")
        print(f"📊 Promedio últimas 6 horas: {last_6_hours_avg:.2f}")
        print(f"📊 Total hoy: {today_accounts}")
        
        return jsonify({
            "message": "Estadísticas por hora obtenidas exitosamente",
            "user_id": user.id,
            "data": hourly_data,
            "total_accounts": len(accounts),
            "last_6_hours_avg": round(last_6_hours_avg, 2),
            "today_total": today_accounts
        }), 200
        
    except Exception as e:
        from flask import jsonify
        return jsonify({"error": f"Error al obtener estadísticas por hora: {str(e)}"}), 500


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


# =============================================================================
# VPS ROUTES
# =============================================================================

@web_bp.get("/vps")
def vps_list():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    # Check if user has Contabo config
    has_config = ContaboConfig.query.filter_by(user_id=user.id).first() is not None

    # Pagination + sorting
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    # Permitir solo valores válidos: 5, 10, 20, 50, 100, 300, 1000
    valid_per_page = [5, 10, 20, 50, 100, 300, 1000]
    if per_page not in valid_per_page:
        per_page = 20
    page = max(page, 1)

    sort = (request.args.get("sort") or "created_at").strip()
    direction = (request.args.get("dir") or "desc").strip().lower()
    direction = direction if direction in ("asc", "desc") else "desc"

    sort_map = {
        "display_name": VPS.display_name,
        "ip_v4": VPS.ip_v4,
        "status": VPS.status,
        "data_center": VPS.data_center,
        "created_at": VPS.created_at,
        "cpu_cores": VPS.cpu_cores,
    }
    sort_col = sort_map.get(sort, VPS.created_at)

    order_expr = sort_col.asc() if direction == "asc" else sort_col.desc()
    query = VPS.query.filter_by(user_id=user.id).order_by(order_expr)
    total = query.count()

    offset = (page - 1) * per_page
    vps_instances = query.offset(offset).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    # Check for flash messages from session
    error = session.pop("vps_error", None)
    success = session.pop("vps_success", None)

    return render_template(
        "vps_list.html",
        user=user,
        vps_list=[v.to_dict() for v in vps_instances],
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        sort=sort if sort in sort_map else "created_at",
        dir=direction,
        has_config=has_config,
        error=error,
        success=success,
    )


@web_bp.post("/vps/sync")
def vps_sync():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    try:
        config = ContaboConfig.query.filter_by(user_id=user.id).first()
        if not config:
            session["vps_error"] = "Configura Contabo primero"
            return redirect(url_for("web.contabo_config"))

        # Decrypt credentials
        client_secret = contabo_encrypt_service.decrypt(config.client_secret)
        password = contabo_encrypt_service.decrypt(config.password)

        if not client_secret or not password:
            session["vps_error"] = "Error al descifrar credenciales"
            return redirect(url_for("web.vps_list"))

        # Create service and sync
        service = ContaboService(
            client_id=config.client_id,
            client_secret=client_secret,
            username=config.username,
            password=password
        )

        result = sync_instances_to_db(user.id, service)
        total_from_api = result.get('total_from_contabo', 0)
        
        message = f"Sincronización completada: {result['added']} agregados, {result['skipped']} existentes. Total desde API: {total_from_api}"
        if result.get('conflicts', 0) > 0:
            message += f". ⚠️ {result.get('warning', '')}"
        session["vps_success"] = message

    except ValueError as e:
        # Errores de validación o autenticación
        db.session.rollback()
        session["vps_error"] = str(e)
        return redirect(url_for("web.vps_list"))
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        # Detectar errores de restricción UNIQUE
        if "UNIQUE constraint failed" in error_msg or "IntegrityError" in error_msg:
            session["vps_error"] = "Error: Un VPS con ese instance_id ya existe en la base de datos. Intenta eliminar todos los VPS y sincronizar nuevamente."
        else:
            session["vps_error"] = f"Error en sincronización: {error_msg}"

    return redirect(url_for("web.vps_list"))


@web_bp.post("/vps/<int:vps_id>/restart")
def vps_restart(vps_id):
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    try:
        vps = VPS.query.filter_by(id=vps_id, user_id=user.id).first()
        if not vps:
            session["vps_error"] = "VPS no encontrado"
            return redirect(url_for("web.vps_list"))

        config = ContaboConfig.query.filter_by(user_id=user.id).first()
        if not config:
            session["vps_error"] = "Configura Contabo primero"
            return redirect(url_for("web.contabo_config"))

        # Decrypt credentials
        client_secret = contabo_encrypt_service.decrypt(config.client_secret)
        password = contabo_encrypt_service.decrypt(config.password)

        if not client_secret or not password:
            session["vps_error"] = "Error al descifrar credenciales"
            return redirect(url_for("web.vps_list"))

        # Create service and restart
        service = ContaboService(
            client_id=config.client_id,
            client_secret=client_secret,
            username=config.username,
            password=password
        )

        service.restart_instance(vps.instance_id)

        session["vps_success"] = f"Reinicio solicitado para {vps.display_name or vps.instance_id}"

    except Exception as e:
        session["vps_error"] = f"Error al reiniciar: {str(e.response.json()['error']['message'])}"

    return redirect(url_for("web.vps_list"))


@web_bp.post("/vps/restart-batch")
def vps_restart_batch():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    try:
        # Obtener IDs de VPS seleccionados
        vps_ids = request.form.getlist("vps_ids")
        if not vps_ids:
            session["vps_error"] = "No se seleccionaron VPS"
            return redirect(url_for("web.vps_list"))

        # Convertir a enteros
        vps_ids = [int(vid) for vid in vps_ids]

        # Verificar que todos los VPS pertenezcan al usuario
        vps_list = VPS.query.filter(
            VPS.id.in_(vps_ids),
            VPS.user_id == user.id
        ).all()

        if len(vps_list) != len(vps_ids):
            session["vps_error"] = "Algunos VPS no fueron encontrados o no pertenecen a tu cuenta"
            return redirect(url_for("web.vps_list"))

        # Obtener configuración de Contabo
        config = ContaboConfig.query.filter_by(user_id=user.id).first()
        if not config:
            session["vps_error"] = "Configura Contabo primero"
            return redirect(url_for("web.contabo_config"))

        # Descifrar credenciales
        client_secret = contabo_encrypt_service.decrypt(config.client_secret)
        password = contabo_encrypt_service.decrypt(config.password)

        if not client_secret or not password:
            session["vps_error"] = "Error al descifrar credenciales"
            return redirect(url_for("web.vps_list"))

        # Crear servicio y reiniciar cada VPS
        service = ContaboService(
            client_id=config.client_id,
            client_secret=client_secret,
            username=config.username,
            password=password
        )

        restarted = []
        failed = []
        for vps in vps_list:
            try:
                service.restart_instance(vps.instance_id)
                restarted.append(vps.display_name or vps.instance_id)
            except Exception as e:
                failed.append(f"{vps.display_name or vps.instance_id}: {str(e)}")

        if failed:
            session["vps_error"] = f"Reiniciados: {len(restarted)}, Fallidos: {len(failed)}. {', '.join(failed[:3])}"
        else:
            session["vps_success"] = f"Reinicio solicitado para {len(restarted)} VPS: {', '.join(restarted[:5])}{'...' if len(restarted) > 5 else ''}"

    except Exception as e:
        session["vps_error"] = f"Error al reiniciar: {str(e)}"

    return redirect(url_for("web.vps_list"))


# =============================================================================
# CONTABO CONFIG ROUTES
# =============================================================================

@web_bp.route("/contabo-config", methods=["GET", "POST"])
def contabo_config():
    guard = _require_login()
    if guard:
        return guard

    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for("web.login"))

    config = ContaboConfig.query.filter_by(user_id=user.id).first()
    form_data = {}
    error = None
    success = None

    if request.method == "POST":
        form_data = {
            "client_id": (request.form.get("client_id") or "").strip(),
            "client_secret": request.form.get("client_secret", ""),
            "username": (request.form.get("username") or "").strip(),
            "password": request.form.get("password", ""),
        }

        if not form_data["client_id"] or not form_data["username"]:
            error = "Client ID y Username son requeridos."
        elif not config and (not form_data["client_secret"] or not form_data["password"]):
            error = "Client Secret y Password son requeridos para nueva configuración."
        else:
            try:
                if config:
                    # Update existing
                    config.client_id = form_data["client_id"]
                    config.username = form_data["username"]
                    if form_data["client_secret"]:
                        config.client_secret = contabo_encrypt_service.encrypt(form_data["client_secret"])
                    if form_data["password"]:
                        config.password = contabo_encrypt_service.encrypt(form_data["password"])
                else:
                    # Create new
                    config = ContaboConfig(
                        user_id=user.id,
                        client_id=form_data["client_id"],
                        client_secret=contabo_encrypt_service.encrypt(form_data["client_secret"]),
                        username=form_data["username"],
                        password=contabo_encrypt_service.encrypt(form_data["password"]),
                    )
                    db.session.add(config)

                db.session.commit()
                success = "Configuración guardada exitosamente."
                form_data = {}  # Clear form after success

            except Exception as e:
                db.session.rollback()
                error = f"Error al guardar: {str(e)}"

    return render_template(
        "contabo_config.html",
        user=user,
        config=config.to_dict() if config else None,
        form_data=form_data,
        error=error,
        success=success,
    )

