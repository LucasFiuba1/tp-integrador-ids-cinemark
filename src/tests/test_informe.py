"""Pruebas de la estructura académica del informe y su exportación a PDF (SCRUM-86)."""
import re
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RUTA_MD = RAIZ / "docs" / "informe.md"
RUTA_PDF = RAIZ / "docs" / "informe.pdf"

REEMPLAZOS_TIPOGRAFICOS = {
    "—": "-",
    "–": "-",
    "·": "-",
    "•": "-",
    "“": '"',
    "”": '"',
    "’": "'",
    "→": "->",
}

ESTILOS_PDF = {
    "h1": ("F2", 16, 22, 76),
    "h2": ("F2", 13, 18, 86),
    "h3": ("F2", 11, 16, 92),
    "tabla": ("F1", 9.5, 13, 98),
    "item": ("F1", 10, 14, 90),
    "p": ("F1", 10, 14, 94),
}


def _limpiar_markdown(texto):
    for original, reemplazo in REEMPLAZOS_TIPOGRAFICOS.items():
        texto = texto.replace(original, reemplazo)
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"\*(.+?)\*", r"\1", texto)
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    return texto.strip()


def _parsear_bloques(markdown):
    bloques = []
    for cruda in markdown.splitlines():
        linea = cruda.strip()
        if not linea or linea == "---" or set(linea) <= {"|", "-", ":", " "}:
            bloques.append(("espacio", ""))
        elif linea.startswith("# "):
            bloques.append(("h1", _limpiar_markdown(linea[2:])))
        elif linea.startswith("## "):
            bloques.append(("h2", _limpiar_markdown(linea[3:])))
        elif linea.startswith("### "):
            bloques.append(("h3", _limpiar_markdown(linea[4:])))
        elif linea.startswith("|") and linea.endswith("|"):
            celdas = [_limpiar_markdown(celda) for celda in linea.strip("|").split("|")]
            bloques.append(("tabla", "  |  ".join(celdas)))
        elif linea.startswith("- "):
            bloques.append(("item", "- " + _limpiar_markdown(linea[2:])))
        else:
            bloques.append(("p", _limpiar_markdown(linea)))
    return bloques


def _escapar_pdf(texto):
    datos = texto.encode("cp1252", errors="replace")
    partes = []
    for byte in datos:
        if byte in (40, 41, 92):
            partes.append(f"\\{chr(byte)}")
        elif 32 <= byte <= 126:
            partes.append(chr(byte))
        else:
            partes.append(f"\\{byte:03o}")
    return "".join(partes)


def generar_pdf_informe(markdown):
    """Genera los bytes de un documento PDF 1.4 A4 con paginado automático a partir del Markdown del informe."""
    paginas = []
    comandos = []
    y = 790

    for tipo, texto in _parsear_bloques(markdown):
        if tipo == "espacio":
            y -= 6
            if y < 60 and comandos:
                paginas.append("\n".join(comandos))
                comandos = []
                y = 790
            continue
        fuente, tamano, interlineado, ancho = ESTILOS_PDF[tipo]
        if tipo in ("h1", "h2", "h3"):
            y -= 6
        for linea in textwrap.wrap(texto, width=ancho) or [""]:
            if y < 60:
                paginas.append("\n".join(comandos))
                comandos = []
                y = 790
            comandos.append(f"BT /{fuente} {tamano} Tf 50 {y} Td ({_escapar_pdf(linea)}) Tj ET")
            y -= interlineado

    if comandos:
        paginas.append("\n".join(comandos))

    objetos = [
        "",
        "",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    ids_pagina = []
    for contenido in paginas:
        datos = contenido.encode("latin1")
        objetos.append(f"<< /Length {len(datos)} >>\nstream\n{contenido}\nendstream")
        id_stream = len(objetos)
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {id_stream} 0 R >>"
        )
        ids_pagina.append(len(objetos))

    kids = " ".join(f"{i} 0 R" for i in ids_pagina)
    objetos[0] = "<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(ids_pagina)} >>"

    salida = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for indice, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida.extend(f"{indice} 0 obj\n{cuerpo}\nendobj\n".encode("latin1"))

    pos_xref = len(salida)
    salida.extend(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("latin1"))
    for offset in offsets[1:]:
        salida.extend(f"{offset:010d} 00000 n \n".encode("latin1"))
    salida.extend(
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{pos_xref}\n%%EOF\n".encode("latin1")
    )
    return bytes(salida)


def test_informe_markdown_contiene_todas_las_secciones_exigidas_por_la_catedra():
    contenido = RUTA_MD.read_text(encoding="utf-8")
    for seccion in (
        "# Informe del Proyecto Integrador — Cine Paradiso",
        "Facultad de Ingeniería (FIUBA)",
        "Cátedra Lanzillotta",
        "## Integrantes",
        "Lucas Cirillo Berardi",
        "Joaquín Nicolás Zavala Eguez",
        "## Resumen",
        "## 1. Introducción",
        "## 2. Solución Propuesta",
        "## 3. Tecnología Utilizada",
        "## 4. Conclusión",
    ):
        assert seccion in contenido


def test_informe_pdf_existe_es_valido_y_esta_sincronizado_con_el_markdown():
    esperado = generar_pdf_informe(RUTA_MD.read_text(encoding="utf-8"))
    assert RUTA_PDF.is_file(), "Falta el archivo docs/informe.pdf."
    actual = RUTA_PDF.read_bytes().replace(b"\r\n", b"\n")
    assert actual.startswith(b"%PDF-1.4\n")
    assert actual.endswith(b"%%EOF\n")
    assert b"/Count 4" in actual
    assert actual == esperado
