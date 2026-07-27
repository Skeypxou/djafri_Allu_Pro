from pathlib import Path
import re

src = Path("/mnt/data/app.py.py")
text = src.read_text(encoding="utf-8", errors="ignore")

insert_block = '''
# ==========================================
# DEVIS SERVICE
# ==========================================

def create_devis(data):
    devis = JSONDB.read("devis")
    data["id"] = JSONDB.get_next_id("devis")
    devis.append(data)
    JSONDB.write("devis", devis)
    return data["id"]

def get_all_devis():
    return JSONDB.read("devis")

def update_devis_statut(devis_id, nouveau_statut):
    devis = JSONDB.read("devis")
    for d in devis:
        if str(d.get("id")) == str(devis_id):
            d["statut"] = nouveau_statut
            JSONDB.write("devis", devis)
            return True
    return False

'''

marker = "def show_devis():"
if insert_block not in text:
    text = text.replace(marker, insert_block + marker, 1)

pattern = r"def create_facture_from_devis\(devis_id\):.*?def get_all_factures\(\):"
replacement = '''def create_facture_from_devis(devis_id):

    try:
        devis_list = JSONDB.read("devis") or []

        devis = next(
            (d for d in devis_list if str(d.get("id")) == str(devis_id)),
            None
        )

        if devis is None:
            st.error(f"Devis introuvable : {devis_id}")
            return None

        factures = JSONDB.read("factures") or []

        facture_existante = next(
            (f for f in factures if str(f.get("devis_id")) == str(devis_id)),
            None
        )

        if facture_existante:
            return facture_existante["numero"]

        year = datetime.now().year
        prefix = f"FAC-{year}-"
        seq = len([f for f in factures if f["numero"].startswith(prefix)]) + 1
        num_facture = f"{prefix}{seq:04d}"

        new_facture = {
            "id": JSONDB.get_next_id("factures"),
            "numero": num_facture,
            "devis_id": devis["id"],
            "client_id": devis["client_id"],
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_ttc": devis["total_ttc"],
            "statut": "Impayé",
            "items": devis["items"]
        }

        factures.append(new_facture)
        JSONDB.write("factures", factures)

        update_devis_statut(devis["id"], "Facturé")

        return num_facture

    except Exception as e:
        st.error(f"Erreur création facture : {e}")
        return None

def get_all_factures():'''

text = re.sub(pattern, replacement, text, flags=re.S)

out = "/mnt/data/app_corrige.py"
Path(out).write_text(text, encoding="utf-8")

print(out)
