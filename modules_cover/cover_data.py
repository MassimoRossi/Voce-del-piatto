import os
import pandas as pd


def load_piatti(base_dir):
    """
    Legge archivio_piatti.xlsx e restituisce lista di dict:
    [
        {
            "seriale": int,
            "titolo": str,
            "frase": str,
            "img_path": str | None
        }
    ]
    """

    excel_path = os.path.join(base_dir, "archivio_piatti.xlsx")
    img_dir = os.path.join(base_dir, "img")

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel non trovato: {excel_path}")

    df = pd.read_excel(excel_path, engine="openpyxl")

    piatti = []

    for _, row in df.iterrows():

        seriale = row.get("seriale")
        titolo = row.get("titolo")
        frase = row.get("frase_iconica")

        # Salta righe senza seriale o titolo
        if pd.isna(seriale) or pd.isna(titolo):
            continue

        seriale = int(seriale)
        titolo = str(titolo).strip()
        frase = "" if pd.isna(frase) else str(frase).strip()

        # Risoluzione immagine: seriale.png
        img_path = os.path.join(img_dir, f"{seriale}.png")
        if not os.path.exists(img_path):
            img_path = None

        piatti.append({
            "seriale": seriale,
            "titolo": titolo,
            "frase": frase,
            "img_path": img_path
        })

    return piatti
