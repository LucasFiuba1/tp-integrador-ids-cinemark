"""Protección de las páginas del frontend por sesión y rol (SCRUM-48).

El login (routes/publico.py) guarda en la sesión el token, el rol y el nombre. Estos decoradores la revisan antes
de mostrar una página; api_client.llamar usa ir_al_login cuando el backend rechaza el token (401).
"""
from functools import wraps

from flask import abort, flash, redirect, session, url_for


def ir_al_login(mensaje):
    session.clear()
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
