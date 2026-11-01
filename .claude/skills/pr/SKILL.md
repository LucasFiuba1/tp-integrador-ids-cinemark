---
name: pr
description: Revisa la rama contra las reglas de la cátedra, corre las pruebas, commitea con formato SCRUM-XXX: descripcion y abre el Pull Request a develop.
disable-model-invocation: true
---

# Preparar el Pull Request

1. **Contexto**: `git status`, `git branch --show-current` (debe ser `SCRUM-XXX/descripcion`; si no, frenar) y
   `git diff develop...HEAD` más lo no commiteado.
2. **Chequeos automáticos** (todos deben dar vacío o OK):
   - `grep -rnE "fetch\(|axios|XMLHttpRequest|new Promise|\$\.ajax" src/frontend`
   - `grep -rniE "sqlalchemy|sqlmodel|peewee|declarative_base" src requirements.txt`
   - `grep -rnE "execute\(f\"|execute\(\".*\" *%|\.format\(" src/backend` (SQL armado con datos)
   - `grep -rnE "^[a-z_]+ *= *(\[|\{)" src` y revisar que no sean estado global mutable
   - `grep -rn "while True" src`
   - `python -m unittest discover -s src/tests -v`
3. **Revisión manual** del diff: verbos HTTP, `@requiere_rol`, validaciones, `transaccion()` donde corresponde,
   fechas en un solo `DATETIME`, código repetido, `docs/endpoints.md` y `docs/base_de_datos.md` al día,
   dependencias nuevas en `requirements.txt`. Listar los problemas y corregirlos con OK del usuario.
4. **Commit**: mensaje `SCRUM-XXX: descripcion` (tomar la clave del prefijo de la rama). Varios commits chicos
   mejor que uno gigante. No commitear `.env`.
5. **PR** con `gh pr create --base develop`: título `SCRUM-XXX: descripcion`; cuerpo con qué cambia, cómo probarlo
   (comandos/curl) y link al ticket `https://tp-ids-final.atlassian.net/browse/SCRUM-XXX`. Pedir confirmación antes
   de pushear y crear el PR. Recordar que lo apruebe otra persona del equipo.
