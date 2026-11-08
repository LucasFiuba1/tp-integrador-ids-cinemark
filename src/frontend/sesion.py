"""Protección de las páginas del frontend por sesión y rol (SCRUM-48).

El login (routes/publico.py) guarda en la sesión el token, el rol y el nombre. Estos decoradores la revisan antes
de mostrar una página; api_client.llamar usa ir_al_login cuando el backend rechaza el token (401).
Si la página pedida era un GET, ir_al_login guarda su URL (con la query, por ejemplo el ?token= del QR de ingreso)
para que el login vuelva ahí (SCRUM-74).
"""
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for


def ir_al_login(mensaje):
    session.clear()
    # Solo GET: volver a un POST después del login lo convertiría en un GET con otro significado. "//" o "/\\" al
    # principio el navegador los toma como otro sitio, así que esas rutas no se guardan.
    siguiente = request.full_path.rstrip("?")
    if request.method == "GET" and not siguiente.startswith(("//", "/\\")):
        session["siguiente"] = siguiente
    flash(mensaje, "error")
    return redirect(url_for("publico.ingresar"))


def requiere_sesion(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not session.get("token"):
            return ir_al_login("Ingresá para continuar.")
        return vista(*args, **kwargs)
    return envoltura


def requiere_admin(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "admin":
            abort(403)
        return vista(*args, **kwargs)
    return requiere_sesion(envoltura)
