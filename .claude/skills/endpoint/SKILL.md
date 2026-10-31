---
name: endpoint
description: Implementa uno o más endpoints de la API del backend siguiendo el patrón ruta → service → SQL → pruebas → docs. Usar al crear o modificar endpoints de src/backend.
argument-hint: "<MÉTODO /api/ruta> o descripción"
---

# Implementar endpoint: $ARGUMENTS

Referencia del patrón: `src/backend/routes/admin.py`, `src/backend/services/peliculas.py`, `src/tests/test_peliculas.py`.

1. **Contrato**: buscar el endpoint en `docs/endpoints.md` (método, ruta, rol, cuerpo, respuesta, códigos de error).
   Si no está o difiere, proponer el contrato y actualizar el doc primero.
2. **SQL**: verificar en `src/backend/db/schema.sql` las columnas y restricciones. Si hace falta cambiar el esquema,
   hacerlo ahí y en `docs/base_de_datos.md`.
3. **Service** en `src/backend/services/<funcionalidad>.py`: validaciones, reglas de negocio, `ErrorApi`,
   SQL parametrizado, `transaccion()` si hay más de una sentencia, fechas a ISO.
4. **Ruta** en el blueprint del módulo: decorador de verbo + `@requiere_rol(...)`, sin lógica.
5. **Pruebas** en `src/tests/test_<funcionalidad>.py`: feliz, 401, 403, 400 (subTest), 404, cada 409.
6. **Verificar**: `python -m unittest discover -s src/tests -v` en verde.
7. Si hay MySQL levantado, probar a mano con `curl` (login para obtener el token) y mostrar request/response.

Checklist final: sin ORM · SQL con `%s` · verbo correcto · endpoint protegido · sin código repetido ·
`docs/endpoints.md` actualizado.
