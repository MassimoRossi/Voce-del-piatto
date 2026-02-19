import os
import pandas as pd
from datetime import datetime

ARCHIVE_FILE = "archivio_piatti.xlsx"
IMAGES_DIR = "archived_images"

def initialize_archive():
    """Crea il file Excel con gli header se non esiste."""
    if not os.path.exists(ARCHIVE_FILE):
        df = pd.DataFrame(columns=[
            "seriale", 
            "titolo", 
            "ricetta", 
            "frase_iconica", 
            "immagine_path", 
            "tags", 
            "data_archiviazione"
        ])
        df.to_excel(ARCHIVE_FILE, index=False)
    
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)

def get_next_serial():
    """Ritorna il prossimo seriale disponibile."""
    if not os.path.exists(ARCHIVE_FILE):
        return 1
    df = pd.read_excel(ARCHIVE_FILE)
    if df.empty:
        return 1
    return df["seriale"].max() + 1

def add_entry(titolo, ricetta, frase, immagine_bytes, tags):
    """Aggiunge una riga all'archivio Excel e salva l'immagine."""
    initialize_archive()
    
    serial = get_next_serial()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Salva immagine
    img_filename = f"piatto_{serial}_{timestamp}.png"
    img_path = os.path.join(IMAGES_DIR, img_filename)
    
    with open(img_path, "wb") as f:
        f.write(immagine_bytes)
    
    # Prepara dati
    new_data = {
        "seriale": serial,
        "titolo": titolo,
        "ricetta": ricetta,
        "frase_iconica": frase,
        "immagine_path": img_path,
        "tags": tags,
        "data_archiviazione": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Carica, appendi e salva
    df = pd.read_excel(ARCHIVE_FILE)
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_excel(ARCHIVE_FILE, index=False)
    
    return serial, img_path
