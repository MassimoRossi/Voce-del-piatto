import streamlit as st
import os
from modules_cover.cover_data import load_piatti
from modules_cover.cover_render import render_cover_pdf





def cover_ui(base_dir=r"c:\cover_menu"):
    BASE_DIR = base_dir



    st.title("Generatore Cover Menu")




    # Caricamento dati
    piatti = load_piatti(BASE_DIR)

    # Layout
    layout_map = {
        "LO1 (1x1)": 1,
        "LO2 (2x1)": 2,
        "LO3 (3x1)": 3,
        "LO4 (2x2)": 4,
        "LO5 (3x2 hero)": 5,
        "LO6 (3x2)": 6,
    }
    layout = st.selectbox("Seleziona Layout", list(layout_map.keys()))
    max_piatti = layout_map[layout]


    # -----------------------------
    # STATO: draft (bozza) vs confirmed (confermato)
    # -----------------------------
    if "draft_items" not in st.session_state:
        # lista di dict: {"seriale": int, "img": bool, "frase": bool}
        st.session_state.draft_items = []

    if "confirmed_items" not in st.session_state:
        st.session_state.confirmed_items = []

    if "confirmed_layout" not in st.session_state:
        st.session_state.confirmed_layout = layout

    # Se cambio layout, azzero la bozza (più pulito per MVP)
    if st.session_state.get("last_layout") != layout:
        st.session_state.last_layout = layout
        st.session_state.draft_items = []
        # non tocchiamo confirmed: resta valido finché non confermi nuovo

    # Mappa seriale -> piatto (per titolo/frase/img_path)
    piatto_by_seriale = {p["seriale"]: p for p in piatti}

    # -----------------------------
    # WIZARD: selezione in expander
    # -----------------------------
    with st.expander(f"1) Seleziona piatti (max {max_piatti})", expanded=True):

        # Scelte disponibili (non già selezionate)
        selected_seriali = [it["seriale"] for it in st.session_state.draft_items]
        available = [p for p in piatti if p["seriale"] not in selected_seriali]

        # Mostro un selectbox per aggiungere 1 alla volta (UX controllata)
        def label_piatto(p):
            badge = "🖼️" if p["img_path"] else "—"
            return f"{p['seriale']:>3} {badge}  {p['titolo']}"

        if len(st.session_state.draft_items) < max_piatti and available:
            pick = st.selectbox(
                "Aggiungi un piatto",
                options=[p["seriale"] for p in available],
                format_func=lambda s: label_piatto(piatto_by_seriale[s]),
                key="pick_seriale"
            )
            col_add, col_info = st.columns([1, 3])
            with col_add:
                add_disabled = len(st.session_state.draft_items) >= max_piatti
                if st.button("➕ Aggiungi", disabled=add_disabled, use_container_width=True):
                    p = piatto_by_seriale[pick]
                    st.session_state.draft_items.append({
                        "seriale": pick,
                        "img": bool(p["img_path"]),   # default: ON solo se esiste file
                        "frase": bool(p["frase"])     # default: ON solo se frase non vuota
                    })
                    st.rerun()
            with col_info:
                st.caption("Suggerimento: puoi disattivare immagine/frase per ogni riga nella lista sotto.")
        else:
            if len(st.session_state.draft_items) >= max_piatti:
                st.info("Hai raggiunto il numero massimo per questo layout.")
            elif not available:
                st.info("Nessun altro piatto disponibile da aggiungere.")

        st.write("---")
        st.subheader("Selezionati (bozza)")

        if not st.session_state.draft_items:
            st.caption("Nessun piatto selezionato.")
        else:
            # Tabella “righe” con toggle per riga
            for idx, it in enumerate(st.session_state.draft_items):
                s = it["seriale"]
                p = piatto_by_seriale.get(s, {})
                titolo = p.get("titolo", f"Seriale {s}")
                has_img = bool(p.get("img_path"))
                has_frase = bool(p.get("frase"))

                # funzione spostamento
                def move_item(i, direction):
                    j = i + direction
                    if 0 <= j < len(st.session_state.draft_items):
                        items = st.session_state.draft_items
                        items[i], items[j] = items[j], items[i]
                        st.session_state.draft_items = items
                        st.rerun()

                c1, c2, c3, c4, c5, c6 = st.columns([5, 1, 1, 1, 1, 1])

                with c1:
                    st.write(f"**{idx+1}. {titolo}**  _(#{s})_")

                with c2:
                    if st.button("↑", key=f"up_{s}_{idx}", disabled=(idx == 0)):
                        move_item(idx, -1)

                with c3:
                    if st.button("↓", key=f"down_{s}_{idx}", disabled=(idx == len(st.session_state.draft_items)-1)):
                        move_item(idx, 1)

                with c4:
                    it["img"] = st.checkbox(
                        "Img",
                        value=it["img"],
                        disabled=not has_img,
                        key=f"img_{s}_{idx}"
                    )

                with c5:
                    it["frase"] = st.checkbox(
                        "Frase",
                        value=it["frase"],
                        disabled=not has_frase,
                        key=f"fr_{s}_{idx}"
                    )

                with c6:
                    if st.button("🗑️", key=f"rm_{s}_{idx}", help="Rimuovi"):
                        st.session_state.draft_items.pop(idx)
                        st.rerun()

            st.write("---")
            col_ok, col_cancel = st.columns(2)

            with col_ok:
                if st.button("✅ Conferma", use_container_width=True):
                    st.session_state.confirmed_items = [dict(x) for x in st.session_state.draft_items]
                    st.session_state.confirmed_layout = layout
                    st.success("Selezione confermata.")
                    st.rerun()

            with col_cancel:
                if st.button("↩️ Annulla", use_container_width=True):
                    # ripristina la bozza all'ultima confermata (o vuota)
                    st.session_state.draft_items = [dict(x) for x in st.session_state.confirmed_items]
                    st.info("Modifiche annullate.")
                    st.rerun()

    # -----------------------------
    # RIEPILOGO (fuori expander)
    # -----------------------------
    st.write("### Riepilogo confermato")
    if not st.session_state.confirmed_items:
        st.caption("Nessuna selezione confermata.")
    else:
        st.write("Layout:", st.session_state.confirmed_layout)
        for idx, it in enumerate(st.session_state.confirmed_items):
            p = piatto_by_seriale[it["seriale"]]
            st.write(
                f"{idx+1}. {p['titolo']}  "
                f"(img={'✓' if it['img'] else '—'}, frase={'✓' if it['frase'] else '—'})"
            )

    st.write("----")

    if st.button("📄 Genera PDF", use_container_width=True):

        if not st.session_state.confirmed_items:
            st.warning("Nessuna selezione confermata.")
        else:
            out_dir = os.path.join(BASE_DIR, "output")
            os.makedirs(out_dir, exist_ok=True)

            out_path = os.path.join(out_dir, "cover_test.pdf")

            background_image_path = os.path.join(BASE_DIR, "assets", "background_a4.png")

            render_cover_pdf(
                output_path=out_path,
                layout_key=st.session_state.confirmed_layout,
                header_title=None,
                header_subtitle=None,
                items=st.session_state.confirmed_items,
                piatto_by_seriale=piatto_by_seriale,
                background_image_path=background_image_path
            )

            st.success("Cover Menu generato con successo.")

            with open(out_path, "rb") as f:
                st.download_button(
                    "⬇️ Scarica PDF",
                    data=f.read(),
                    file_name="cover_test.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )




    st.write("----")
    st.write("Layout scelto:", layout)
if __name__ == "__main__":
    cover_ui()
