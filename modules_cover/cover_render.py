import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image
from reportlab.lib.utils import ImageReader

def wrap_text_to_lines(text, font_name, font_size, max_width):
    """Ritorna una lista di righe che stanno dentro max_width."""
    words = (text or "").split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def draw_wrapped(c, text, x, y_top, max_width, font_name, font_size, max_lines, line_gap=1.2, align="left"):
    """
    align: "left" o "center"
    """
    c.setFont(font_name, font_size)
    lines = wrap_text_to_lines(text, font_name, font_size, max_width)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and stringWidth(last + "…", font_name, font_size) > max_width:
            last = last[:-1]
        lines[-1] = (last + "…") if last else "…"

    y = y_top
    step = font_size * line_gap
    for ln in lines:
        if align == "center":
            line_width = stringWidth(ln, font_name, font_size)
            x_draw = x + (max_width - line_width) / 2
        else:
            x_draw = x
        c.drawString(x_draw, y, ln)
        y -= step

    return y


def crop_fill_image(img_path, target_w_px, target_h_px):
    """
    Ritorna un'immagine PIL croppata e ridimensionata per riempire target (crop center).
    """
    img = Image.open(img_path).convert("RGB")
    iw, ih = img.size
    target_ratio = target_w_px / target_h_px
    img_ratio = iw / ih

    if img_ratio > target_ratio:
        # taglia ai lati
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        img = img.crop((left, 0, left + new_w, ih))
    else:
        # taglia sopra/sotto
        new_h = int(iw / target_ratio)
        top = (ih - new_h) // 2
        img = img.crop((0, top, iw, top + new_h))

    img = img.resize((target_w_px, target_h_px), Image.Resampling.LANCZOS)
    return img





def render_cover_pdf(output_path, layout_key, header_title, header_subtitle,
                     items, piatto_by_seriale,
                     background_image_path=None):

    """
    items: lista confermata:
      [{"seriale": int, "img": bool, "frase": bool}, ...]
    """
    


    W, H = A4
    c = canvas.Canvas(output_path, pagesize=A4)

    # --- BACKGROUND A4 ---
    if background_image_path and os.path.exists(background_image_path):
        c.drawImage(
            ImageReader(background_image_path),
            0, 0,
            width=W,
            height=H
        )

    # --- AREA DINAMICA (zona piatti sopra il background) ---

    margin = 10 * mm   # margine di sicurezza interno (regolabile)

    x0 = margin
    y0 = margin
    x1 = W - margin
    y1 = H - margin

    dyn_left = x0
    dyn_right = x1
    dyn_bottom = y0
    header_space =30 * mm
    dyn_top = y1 - header_space


    dyn_w = dyn_right - dyn_left
    dyn_h = dyn_top - dyn_bottom


    # Layout rows x cols (Righe x Colonne)
    layout_rc = {
        "LO1 (1x1)": (1, 1),
        "LO2 (2x1)": (2, 1),
        "LO3 (3x1)": (3, 1),
        "LO4 (2x2)": (2, 2),
        "LO5 (3x2 hero)": (3, 2),
        "LO6 (3x2)": (3, 2),
    }
    rows, cols = layout_rc[layout_key]

    cell_w = dyn_w / cols
    cell_h = dyn_h / rows

    # Genera lista celle (con merge per LO5)
    cells = []
    for r in range(rows):
        for col in range(cols):
            # coordinate cella (riga 0 in alto)
            x = dyn_left + col * cell_w
            y = dyn_top - (r + 1) * cell_h
            w = cell_w
            h = cell_h

            # Merge LO5: riga 2 (index 1) unita su 2 colonne
            if layout_key == "LO5 (3x2 hero)" and r == 1:
                if col == 0:
                    w = cell_w * 2
                    cells.append((x, y, w, h, True))  # hero
                # col==1 saltata
                continue

            cells.append((x, y, w, h, False))

    # Assegna items in ordine di lettura alle celle
    n = min(len(items), len(cells))
    items = items[:n]

    for i in range(n):
        x, y, w, h, is_hero = cells[i]
        it = items[i]
        p = piatto_by_seriale[it["seriale"]]

        # bordo cella (wireframe)
        # c.setLineWidth(0.7 if is_hero else 0.4)
        # c.rect(x, y, w, h)

        titolo = p["titolo"]
        frase = p.get("frase", "")

        # testo centrato (per wireframe)
        pad = 6 * mm
        text_x = x + pad
        text_w = w - 2 * pad

        # Area immagine dentro la cella
        img_h = h * (0.75 if is_hero else 0.65)
        img_x = x + pad
        img_y = y + h - img_h - pad
        img_w = w - 2 * pad

        img_path = p.get("img_path")
        if it.get("img") and img_path:
            # Disegna immagine
            dpi = 150
            target_w_px = max(200, int((img_w / 72.0) * dpi))
            target_h_px = max(200, int((img_h / 72.0) * dpi))

            pil_img = crop_fill_image(img_path, target_w_px, target_h_px)
            c.drawImage(ImageReader(pil_img), img_x, img_y, width=img_w, height=img_h)

            # Testo parte sotto immagine
            y_text_top = img_y - 6*mm
        else:
            # Niente immagine: testo parte più in alto (centreremo meglio nello step successivo)
            # --- NO IMMAGINE: centra verticalmente titolo + (eventuale) frase ---
            pad = 6 * mm
            text_w = w - 2 * pad

            title_font = "Helvetica-Bold"
            title_size = 13 if is_hero else 11
            phrase_font = "Helvetica"
            phrase_size = 8

            # Stima righe effettive (wrap) per calcolare altezza blocco testo
            title_lines = wrap_text_to_lines(titolo, title_font, title_size, text_w)
            title_lines = title_lines[:2]
            title_h = len(title_lines) * (title_size * 1.2)

            phrase_h = 0
            phrase_lines = []
            if is_hero:
                max_phrase_lines = 5
            else:
                if layout_key in ("LO5 (3x2 hero)", "LO6 (3x2)"):
                    max_phrase_lines = 5
                else:
                    max_phrase_lines = 4 if h >= 70 * mm else 3


            if it.get("frase") and frase:
                phrase_lines = wrap_text_to_lines(frase, phrase_font, phrase_size, text_w)
                phrase_lines = phrase_lines[:max_phrase_lines]
                phrase_h = len(phrase_lines) * (phrase_size * 1.2) + (2 * mm)  # include gap

            block_h = title_h + phrase_h

            # y_top del blocco centrato
            y_text_top = y + (h + block_h) / 2 - title_size  # leggero aggiustamento ottico




        # Titolo: max 2 righe
        title_font = "Helvetica-Bold"
        title_size = 13 if is_hero else 11
        y_cursor = y_text_top

        # Titolo
        title_font = "Helvetica-Bold"
        title_size = 13 if is_hero else 11
        y_cursor = draw_wrapped(
            c, titolo, text_x, y_cursor, text_w,
            title_font, title_size,
            max_lines=2,
            align="center"
        )


       # Frase
        if it.get("frase") and frase:
            phrase_font = "Helvetica"
            phrase_size = 8
            y_cursor -= 2 * mm

            if is_hero:
                max_phrase_lines = 5
            else:
                if layout_key in ("LO5 (3x2 hero)", "LO6 (3x2)"):
                    max_phrase_lines = 5
                else:
                    max_phrase_lines = 4 if h >= 70 * mm else 3

        draw_wrapped(
            c, frase, text_x, y_cursor, text_w,
            phrase_font, phrase_size,
            max_lines=max_phrase_lines
        )




            


        # mostra anche i flag
        # c.setFont("Helvetica", 7)
        # c.drawString(x + 6*mm, y + 6*mm, f"#{it['seriale']}  img={it['img']}  frase={it['frase']}")

    c.showPage()
    c.save()
