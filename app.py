import os
import base64
import tempfile
import streamlit as st
from openai import OpenAI
import yaml
import io
from docx import Document

import hmac

def require_password():
    if st.session_state.get("auth_ok"):
        return

    st.title("Voce del Piatto")
    st.caption("Accesso riservato")

    pwd = st.text_input("Password", type="password")
    if st.button("Entra", use_container_width=True):
        secret = st.secrets.get("APP_PASSWORD", "")
        if secret and hmac.compare_digest(pwd, secret):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Password non corretta.")

    st.stop()

require_password()

# =====================
# Config
# =====================
st.set_page_config(page_title="Voce del Piatto", layout="wide")  # wide per 3 colonne

client = OpenAI()  # OPENAI_API_KEY da env / Streamlit Secrets

VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini")
GEN_MODEL = os.getenv("GEN_MODEL", "gpt-4o-mini")
TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-transcribe")

# =====================
# Load rules + prompt
# =====================
def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

RULES = load_yaml("rules/registri.yaml")
REGISTRI = RULES["registri"]          # dict: nome -> guida
HARD_RULES = RULES["hard_rules"]      # list[str]

with open("prompts/system.txt", "r", encoding="utf-8") as f:
    SYSTEM_TXT = f.read()

# =====================
# Session state
# =====================
if "ricetta" not in st.session_state:
    st.session_state.ricetta = ""
if "outputs" not in st.session_state:
    st.session_state.outputs = {}  # dict: registro -> testo generato
if "last_params" not in st.session_state:
    st.session_state.last_params = {}

if "draft_text" not in st.session_state:
    st.session_state.draft_text = ""
if "confirmed" not in st.session_state:
    st.session_state.confirmed = False
if "recipe_confirmed" not in st.session_state:
    st.session_state.recipe_confirmed = False

def reset_confirmation():
    st.session_state.recipe_confirmed = False

# =====================
# Helpers
# =====================
def _to_data_url(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def extract_text_from_image(image_bytes: bytes, mime: str) -> str:
    data_url = _to_data_url(image_bytes, mime)
    prompt = (
        "Estrai e trascrivi fedelmente il testo della ricetta dall'immagine.\n"
        "Regole:\n"
        "- Non inventare nulla.\n"
        "- Mantieni numeri, unità (g, ml), virgole, simboli e 'q.b.'\n"
        "- Mantieni struttura a righe.\n"
        "- Se c'è una tabella, rendila in testo con colonne separate da ' | '.\n"
        "Output: SOLO il testo estratto."
    )

    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        }]
    )
    return (resp.choices[0].message.content or "").strip()

def transcribe_audio_bytes(audio_bytes: bytes, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            tr = client.audio.transcriptions.create(
                model=TRANSCRIBE_MODEL,
                file=f,
            )
        return getattr(tr, "text", "") or ""
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

def generate_output(ricetta: str, registro: str, out_type: str, length: str) -> str:
    reg_hint = REGISTRI[registro]

    user_prompt = f"""
Sei un copywriter gastronomico specializzato.
Il tuo compito è scrivere la descrizione di un piatto basandoti sulla ricetta fornita.

COMANDO: Devi generare SOLAMENTE la versione: {out_type} {length}.
NON generare altre varianti.
NON generare introduzioni o spiegazioni.
NON unire più versioni (es. se chiesto Menu, NON fare Cameriere).

REGISTRO RICHIESTO: {registro}
DESCRIZIONE REGISTRO: {reg_hint}
(Usa queste regole di stile SOLO per la versione {out_type} {length})

REGOLE HARD (da rispettare sempre):
- """ + "\n- ".join(HARD_RULES) + f"""

RICETTA (testo sorgente):
{ricetta}

OUTPUT ATTESO:
Scrivi SOLO il testo per {out_type} in formato {length}.
""".strip()

    resp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_TXT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()

def translate_text(text: str, language: str, register: str) -> str:
    prompt = f"""
Sei un traduttore esperto di menu gastronomici.
Traduci il seguente testo in {language}.
Mantieni rigorosamente il tono, lo stile e la formattazione del registro originale: "{register}".
Non aggiungere spiegazioni o commenti extra.

TESTO DA TRADURRE:
{text}
""".strip()
    
    resp = client.chat.completions.create(
        model=GEN_MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()

def export_docx(titolo: str, contenuto: str) -> bytes:
    doc = Document()
    doc.add_heading(titolo, level=1)

    for par in contenuto.split("\n"):
        doc.add_paragraph(par)

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.read()

# =====================
# UX Fine: mini-CSS (pulizia visiva)
# =====================
PRIMARY = "#C9A227"  # zafferano scuro

st.markdown("""
<style>
/* Centra il contenitore principale */
.block-container {
  max-width: 1600px;
  margin-left: auto;
  margin-right: auto;
  padding-top: 1.2rem;
  padding-bottom: 1rem;
}

/* Titolo principale */
h1 {
  color: #C9A227 !important;   /* zafferano */
  text-align: center;
  margin-bottom: 0.2rem;
}

/* Sottotitolo */
[data-testid="stCaptionContainer"] {
  text-align: center;
  margin-top: -0.5rem;
  margin-bottom: 1rem;
}

/* Titoli di sezione */
h2, h3 {
  color: #C9A227;
}

/* Bottoni primari */
button[kind="primary"] {
  background-color: #C9A227 !important;
  border-color: #C9A227 !important;
}
</style>
""", unsafe_allow_html=True)



# =====================
# Header
# =====================
st.markdown("""
<div style="text-align:center; margin-top:2.2rem; margin-bottom:1.2rem;">
  <div style="font-size:3rem; font-weight:800; color:#C9A227; line-height:1.05; letter-spacing:0.5px;">
    Voce<span style="opacity:.9;">•</span>del<span style="opacity:.9;">•</span>Piatto


  </div>
  <div style="font-size:1rem; color:#6b6b6b; margin-top:0.35rem;">
    Il piatto, raccontato bene.
  </div>
</div>
""", unsafe_allow_html=True)

# =====================
# Home / Tool switch
# =====================


page = st.radio(
        "",
        ["Home", "Tool"],
        horizontal=True,
        index=0,
        label_visibility="collapsed"
        )

st.divider()

if page == "Home":
    # --- LANDING ---
    st.markdown("""
    <div style="text-align:center; margin-top:0.5rem; margin-bottom:1.5rem;">
      <div style="font-size:1.6rem; font-weight:700; color:#1F1F1F;">
        Descrizioni per menu e sala, in 30 secondi.
      </div>
      <div style="font-size:1rem; color:#6b6b6b; margin-top:0.4rem;">
        Carica una ricetta (foto o voce), scegli lo stile, genera la tua “voce”.
      </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
        <div style="background:#F6F6F6; border:1px solid #E6E6E6; padding:14px 16px; border-radius:12px;">
          <div style="font-weight:700; color:#C9A227;">Input naturale</div>
          <div style="margin-top:6px;">Testo, foto o voce → testo editabile.</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background:#F6F6F6; border:1px solid #E6E6E6; padding:14px 16px; border-radius:12px;">
          <div style="font-weight:700; color:#C9A227;">5 registri</div>
          <div style="margin-top:6px;">Minimal, classico, territoriale, sensoriale, emozionale.</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background:#F6F6F6; border:1px solid #E6E6E6; padding:14px 16px; border-radius:12px;">
          <div style="font-weight:700; color:#C9A227;">Output pronto</div>
          <div style="margin-top:6px;">Menu o sala, supporto lingue, export DOCX incluso.</div>
        </div>
        """, unsafe_allow_html=True)

    
    st.stop()


reg_names = list(REGISTRI.keys())
default_regs = [r for r in ["Minimal contemporaneo", "Classico elegante"] if r in reg_names]
if not default_regs and reg_names:
    default_regs = [reg_names[0]]
default_idx = reg_names.index("Minimal contemporaneo") if "Minimal contemporaneo" in reg_names else 0

# =====================
# Layout 3 colonne
# =====================
left, center, right = st.columns([2.15, 2.15, 2.15], gap="large")

# =====================
# LEFT: controlli (in form) + azioni
# =====================
with left:
    st.subheader("Impostazioni")

    with st.form("controls", clear_on_submit=False):
        sperimentazione = st.toggle("Confronta stili", value=True, key="sp_sperimentazione")

        if sperimentazione:
            registri_sel = st.multiselect(
            "Registri",
            reg_names,
            default=[],
            key="sp_registri_multi"
    )
        else:
            registro = st.selectbox(
                "Registro",
                reg_names,
                index=default_idx,
                key="sp_registro_single"
            )
            registri_sel = [registro]


        out_type = st.radio("Tipo testo", ["Menu", "Cameriere"], key="sp_out_type")
        length = st.radio("Lunghezza", ["Corto", "Lungo"], key="sp_length")

        # Disable generate if not confirmed
        is_confirmed = st.session_state.get("recipe_confirmed", False)
        
        extra_langs = st.multiselect(
            "Lingue extra (appendi traduzione)",
            ["Inglese", "Tedesco", "Francese", "Spagnolo"],
            default=[],
            key="sp_extra_langs"
        )
        
        genera = st.form_submit_button("Genera", type="primary", disabled=not is_confirmed)


    colA, colB = st.columns(2)
    if colA.button("Pulisci output"):
        st.session_state.outputs = {}
    if colB.button("Pulisci tutto"):
        st.session_state.outputs = {}
        st.session_state.ricetta = ""
        st.session_state.recipe_confirmed = False

    st.divider()
    st.caption("Hard rules attive:")
    for r in HARD_RULES:
        st.write(f"• {r}")

# =====================
# CENTER: input (Foto/Voce/Testo) + revisione
# =====================
with center:
    st.subheader("Input")

    tab_foto, tab_voce, tab_testo = st.tabs(["📷 Foto", "🎙️ Voce", "✍️ Testo"])

    with tab_foto:
        img = st.file_uploader("Carica immagine (JPG/PNG)", type=["jpg", "jpeg", "png"])
        c1, c2 = st.columns([1, 1])
        do_ocr = c1.button("Estrai testo", type="primary")
        if img:
            st.image(img, caption="Anteprima", use_container_width=True)

        if do_ocr:
            if not img:
                st.warning("Carica prima un'immagine.")
            else:
                with st.spinner("Estrazione testo in corso..."):
                    text = extract_text_from_image(img.getvalue(), img.type or "image/jpeg")
                if text:
                    st.session_state.ricetta = text.strip()
                    reset_confirmation()
                    st.success("Testo estratto e copiato in Revisione!")
                    st.rerun()
                else:
                    st.warning("Niente testo utile. Prova foto più nitida/frontale.")


    with tab_voce:
        st.write("MVP: carica una registrazione (wav/mp3/m4a).")
        aud = st.file_uploader("Carica audio", type=["wav", "mp3", "m4a", "aac"])
        do_stt = st.button("Trascrivi audio", type="primary")
        if aud:
            st.audio(aud)

        if do_stt:
            if not aud:
                st.warning("Carica prima un file audio.")
            else:
                suffix = os.path.splitext(aud.name)[1] or ".wav"
                with st.spinner("Trascrizione in corso..."):
                    text = transcribe_audio_bytes(aud.getvalue(), suffix=suffix)
                if text:
                    st.session_state.ricetta = text.strip()
                    reset_confirmation()
                    st.success("Trascrizione completata e copiata in Revisione!")
                    st.rerun()
                else:
                    st.warning("Trascrizione vuota. Prova un audio più pulito.")

    with tab_testo:
        txt_in = st.text_area("Scrivi/Incolla", key="manual_input_text", height=200)

        if st.button("Copia in Revisione", type="primary"):
            if txt_in and txt_in.strip():
                st.session_state.ricetta = txt_in.strip()
                reset_confirmation()
                st.rerun()
            else:
                st.warning("Scrivi qualcosa prima di copiare.")


    st.divider()

    st.subheader("Revisione ricetta")
    val_ricetta = st.text_area(
            "Testo ufficiale (usato per generare)",
            key="ricetta",
            height=260,
            on_change=reset_confirmation
    )

    # Confirmation button
    if st.button("✅ Conferma Ricetta", type="primary", use_container_width=True):
        if val_ricetta.strip():
            st.session_state.recipe_confirmed = True
            st.rerun()
        else:
            st.warning("La ricetta è vuota.")
    
    if st.session_state.get("recipe_confirmed", False):
        st.success("Ricetta confermata. Puoi generare.")



# =====================
# RIGHT: output persistente
# =====================
with right:
    st.subheader("Output")

    ricetta = (st.session_state.ricetta or "").strip()

    if genera:
        if not ricetta:
             # Should be caught by disabled, but safety check
            st.error("Manca la ricetta.")
        elif not st.session_state.get("recipe_confirmed", False):
             st.error("Devi confermare la ricetta.")
        else:
            st.session_state.outputs = {}
            st.session_state.last_params = {
                "registri": registri_sel,
                "tipo": out_type,
                "lunghezza": length
            }
            for r in registri_sel:
                with st.spinner(f"Genero: {r}…"):
                    # 1. Italian generation
                    base_text = generate_output(ricetta, r, out_type, length)
                    final_output = base_text
                    
                    # 2. Translate if needed
                    for lang in extra_langs:
                         with st.spinner(f"Traduco in {lang}..."):
                             tr_text = translate_text(base_text, lang, r)
                             final_output += f"\n\n--- {lang.upper()} ---\n{tr_text}"
                    
                    st.session_state.outputs[r] = final_output

    # Mostra sempre ultimo output generato (persistente)
    if st.session_state.outputs:
        params = st.session_state.last_params or {}
        st.caption(f"Ultima generazione: {params.get('tipo','')} / {params.get('lunghezza','')}")

        for r, txt in st.session_state.outputs.items():
            with st.expander(r, expanded=True):
                st.write(txt)
                st.code(txt, language="markdown")

                filename = f"{r}_{params.get('tipo','')}_{params.get('lunghezza','')}.docx".replace(" ", "_")
                titolo = f"Voce del Piatto — {r} — {params.get('tipo','')} — {params.get('lunghezza','')}"
                docx_bytes = export_docx(titolo, txt)
                st.download_button(
                    "Scarica DOCX",
                    data=docx_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"btn_dl_{r.replace(' ', '_')}"
                )

    else:
        st.markdown("""
        <div style="
            background:#F6F6F6;
            border:1px solid #E6E6E6;
            padding:14px 16px;
            border-radius:10px;
            color:#1F1F1F;">
            <b>Nessun output ancora.</b> Inserisci ricetta e premi <b>Genera</b>.
        </div>
        """, unsafe_allow_html=True)


