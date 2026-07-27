import os
import io
import json
import shutil
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import qrcode
from fpdf import FPDF

# ==========================================
# 1. CONFIGURATION & JSON DB ENGINE
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
BACKUP_DIR = os.path.join(DB_DIR, "backups")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

DB_FILES = {
    "clients": os.path.join(DB_DIR, "clients.json"),
    "devis": os.path.join(DB_DIR, "devis.json"),
    "factures": os.path.join(DB_DIR, "factures.json"),
    "paiements": os.path.join(DB_DIR, "paiements.json"),
    "atelier": os.path.join(DB_DIR, "atelier.json"),
    "tarifs": os.path.join(DB_DIR, "tarifs.json"),
    "parametres": os.path.join(DB_DIR, "parametres.json"),
    "counters": os.path.join(DB_DIR, "counters.json")
}

class JSONDB:
    """Moteur de base de données JSON sécurisé avec backups automatiques."""
    
    @staticmethod
    def read(db_name):
        filepath = DB_FILES.get(db_name)
        if not os.path.exists(filepath):
            return [] if db_name != "parametres" else {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def write(db_name, data):
        filepath = DB_FILES.get(db_name)
        if os.path.exists(filepath):
            backup_name = f"{db_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(filepath, os.path.join(BACKUP_DIR, backup_name))
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def get_next_id(db_name):
        counters = JSONDB.read("counters")
        if db_name not in counters:
            counters[db_name] = 1
        else:
            counters[db_name] += 1
        JSONDB.write("counters", counters)
        return counters[db_name]

# ==========================================
# 2. INITIALISATION DES DONNÉES
# ==========================================

def init_db():
    if not os.path.exists(DB_FILES["parametres"]):
        JSONDB.write("parametres", {
            "nom_entreprise": "DJEFF ALUMINIUM PRO",
            "telephone": "0555000000", "email": "contact@djeff.dz",
            "adresse": "Alger, Algérie", "rc": "16/00-1234567 B 23",
            "nif": "000916123456789", "nis": "098765432109876", "tva_taux": 19.0
        })

    for db_name in ["clients", "devis", "factures", "paiements", "atelier"]:
        if not os.path.exists(DB_FILES[db_name]):
            JSONDB.write(db_name, [])

    if not os.path.exists(DB_FILES["tarifs"]):
        JSONDB.write("tarifs", {
            "produit_types": ["Fenêtre", "Imposte", "Porte", "Porte-fenêtre", "Baie vitrée", "Portail"],
            "ouvertures": ["Fixe", "1 vantail", "2 vantaux", "3 vantaux", "Coulissante", "Oscillo-battante"],
            "aluminium": [
                {"serie": "Série 40", "prix_ml": 1500.0},
                {"serie": "Série 45", "prix_ml": 1500.0},
                {"serie": "Série 50", "prix_ml": 1500.0}
            ],
            "vitrage": [
                {"type": "Simple vitrage", "prix_m2": 3500.0},
                {"type": "Double vitrage", "prix_m2": 4500.0}
            ],
            "couleurs": [
                {"nom": "Blanc", "supplement_fixe": 0, "supplement_pourcentage": 0},
                {"nom": "Gris Anthracite", "supplement_fixe": 0, "supplement_pourcentage": 15}
            ]
        })

    if not os.path.exists(DB_FILES["counters"]):
        JSONDB.write("counters", {"clients": 0, "devis": 0, "factures": 0, "paiements": 0, "atelier": 0})

# ==========================================
# 3. SERVICES MÉTIER (CRUD)
# ==========================================

# --- Client Service ---
def create_client(data):
    clients = JSONDB.read("clients")
    data["id"] = JSONDB.get_next_id("clients")
    data["date_creation"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clients.append(data)
    JSONDB.write("clients", clients)

def get_all_clients():
    return JSONDB.read("clients")

def update_client(client_id, updated_data):
    clients = JSONDB.read("clients")
    for c in clients:
        if c["id"] == client_id:
            c.update(updated_data)
            JSONDB.write("clients", clients)
            return True
    return False

def delete_client(client_id):
    clients = JSONDB.read("clients")
    clients = [c for c in clients if c["id"] != client_id]
    JSONDB.write("clients", clients)

# --- Paramètres & Tarifs ---
def get_parametres():
    return JSONDB.read("parametres")

def update_parametres(data):
    JSONDB.write("parametres", data)

def get_tarifs():
    return JSONDB.read("tarifs")

def update_tarifs(data):
    JSONDB.write("tarifs", data)

# --- Devis Service ---
def create_devis(data):
    devis_list = JSONDB.read("devis")
    data["id"] = JSONDB.get_next_id("devis")
    devis_list.append(data)
    JSONDB.write("devis", devis_list)

def get_all_devis():
    return JSONDB.read("devis")

def update_devis_statut(devis_id, statut):
    devis_list = JSONDB.read("devis")
    for d in devis_list:
        if d["id"] == devis_id:
            d["statut"] = statut
            JSONDB.write("devis", devis_list)
            return True
    return False

# --- Facture Service ---
def create_facture_from_devis(devis_id):
    devis_list = JSONDB.read("devis")
    devis = next((d for d in devis_list if d["id"] == devis_id), None)
    if not devis: return None
        
    factures = JSONDB.read("factures")
    year = datetime.now().year
    prefix = f"FAC-{year}-"
    seq = len([f for f in factures if f["numero"].startswith(prefix)]) + 1
    num_facture = f"{prefix}{seq:04d}"
    
    new_facture = {
        "id": JSONDB.get_next_id("factures"),
        "numero": num_facture,
        "devis_id": devis_id,
        "client_id": devis["client_id"],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_ttc": devis["total_ttc"],
        "statut": "Impayé",
        "items": devis["items"]
    }
    factures.append(new_facture)
    JSONDB.write("factures", factures)
    update_devis_statut(devis_id, "Facturé")
    return num_facture

def get_all_factures():
    return JSONDB.read("factures")

# --- Paiement Service ---
def create_paiement(data):
    paiements = JSONDB.read("paiements")
    data["id"] = JSONDB.get_next_id("paiements")
    paiements.append(data)
    JSONDB.write("paiements", paiements)
    
    factures = JSONDB.read("factures")
    for f in factures:
        if f["id"] == data["facture_id"]:
            total_paye = sum([p["montant"] for p in paiements if p["facture_id"] == f["id"]])
            if total_paye >= f["total_ttc"]:
                f["statut"] = "Payé"
            elif total_paye > 0:
                f["statut"] = "Partiel"
            break
    JSONDB.write("factures", factures)

def get_paiements_for_facture(facture_id):
    return [p for p in JSONDB.read("paiements") if p["facture_id"] == facture_id]

# --- Atelier Service (Ordres de Fabrication) ---
def create_of_from_facture(facture_id):
    factures = JSONDB.read("factures")
    facture = next((f for f in factures if f["id"] == facture_id), None)
    if not facture: return None
    
    atelier = JSONDB.read("atelier")
    year = datetime.now().year
    prefix = f"OF-{year}-"
    seq = len([o for o in atelier if o["numero"].startswith(prefix)]) + 1
    num_of = f"{prefix}{seq:04d}"
    
    new_of = {
        "id": JSONDB.get_next_id("atelier"),
        "numero": num_of,
        "facture_id": facture_id,
        "client_id": facture["client_id"],
        "date_creation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "statut": "En attente",
        "items": facture["items"]
    }
    atelier.append(new_of)
    JSONDB.write("atelier", atelier)
    return num_of

def get_all_ofs():
    return JSONDB.read("atelier")

def update_of_statut(of_id, statut):
    atelier = JSONDB.read("atelier")
    for o in atelier:
        if o["id"] == of_id:
            o["statut"] = statut
            JSONDB.write("atelier", atelier)
            return True
    return False

# ==========================================
# 4. MOTEUR DE CALCUL & PDF
# ==========================================

def calculer_prix_item(largeur, hauteur, qt, materiau, serie, vitrage, couleur_nom, marge):
    tarifs = get_tarifs()
    largeur_m, hauteur_m = largeur / 1000, hauteur / 1000
    surface, perimeter = largeur_m * hauteur_m, (largeur_m + hauteur_m) * 2
    
    cout_profil = 0
    if materiau == "Aluminium":
        profil = next((p for p in tarifs["aluminium"] if p["serie"] == serie), None)
        cout_profil = profil["prix_ml"] * perimeter if profil else 0
        
    vitrage_obj = next((v for v in tarifs["vitrage"] if v["type"] == vitrage), None)
    cout_vitrage = vitrage_obj["prix_m2"] * surface if vitrage_obj else 0
    
    couleur_obj = next((c for c in tarifs["couleurs"] if c["nom"] == couleur_nom), None)
    cout_couleur = 0
    if couleur_obj:
        cout_couleur = couleur_obj.get("supplement_fixe", 0) * perimeter
        if couleur_obj.get("supplement_pourcentage", 0) > 0:
            cout_couleur += (cout_profil * couleur_obj["supplement_pourcentage"] / 100)
            
    cout_mo = (cout_profil + cout_vitrage + cout_couleur) * 0.20
    cout_revient = cout_profil + cout_vitrage + cout_couleur + cout_mo
    prix_vente_ht = cout_revient * (1 + marge / 100)
    
    return {
        'surface': surface, 'perimeter': perimeter,
        'prix_unitaire': round(prix_vente_ht, 2),
        'total_ligne': round(prix_vente_ht * qt, 2)
    }

class DevisPDF(FPDF):
    def header(self):
        params = get_parametres()
        logo_path = os.path.join("assets", "logo.png")
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, params.get("nom_entreprise", ""), 0, 1, 'R')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, f"Tel: {params.get('telephone', '')} | Email: {params.get('email', '')}", 0, 1, 'R')
        self.cell(0, 5, f"RC: {params.get('rc', '')} | NIF: {params.get('nif', '')}", 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Conditions: 50% à la commande, 50% à la livraison. Validité: 30 jours.', 0, 0, 'C')

def generate_pdf(doc_data, doc_type="Devis"):
    params = get_parametres()
    clients = get_all_clients()
    client = next((c for c in clients if c["id"] == doc_data["client_id"]), {})
    
    pdf = DevisPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"{doc_type.upper()} N°: {doc_data['numero']}", 0, 1, 'L')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Date: {doc_data['date']}", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(95, 8, "Client:", 1, 0, 'L', 1)
    pdf.cell(95, 8, "Informations:", 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 8, f"{client.get('prenom', '')} {client.get('nom', '')}", 1, 0)
    statut_info = doc_data.get('statut', '')
    if doc_type == "Facture":
        total_paye = sum([p["montant"] for p in get_paiements_for_facture(doc_data["id"])])
        statut_info = f"{doc_data['statut']} ({total_paye:,.2f} / {doc_data['total_ttc']:,.2f} DA)"
    pdf.cell(95, 8, f"Statut: {statut_info}", 1, 1)
    pdf.cell(95, 8, f"Tel: {client.get('telephone1', '')}", 1, 1)
    pdf.multi_cell(190, 8, f"Adresse: {client.get('adresse', '')}, {client.get('wilaya', '')}", 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 9)
    headers = ["Désignation", "Ouverture", "Dim (LxH)", "Qté", "P.U HT", "Total HT"]
    widths = [50, 30, 35, 15, 30, 30]
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    for item in doc_data["items"]:
        designation = f"{item['produit_type']} {item['couleur']} ({item['serie_profil']})"
        pdf.cell(widths[0], 8, designation[:35], 1, 0)
        pdf.cell(widths[1], 8, item["ouverture"][:15], 1, 0)
        pdf.cell(widths[2], 8, f"{int(item['largeur'])}x{int(item['hauteur'])}", 1, 0, 'C')
        pdf.cell(widths[3], 8, str(item["quantite"]), 1, 0, 'C')
        pdf.cell(widths[4], 8, f"{item['prix_unitaire']:,.2f} DA", 1, 0, 'R')
        pdf.cell(widths[5], 8, f"{item['total_ligne']:,.2f} DA", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(50, 10, "TOTAL TTC:", 1, 0, 'R', True)
    pdf.cell(30, 10, f"{doc_data['total_ttc']:,.2f} DA", 1, 1, 'R', True)
    
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(f"{doc_type}: {doc_data['numero']}|Total: {doc_data['total_ttc']}")
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    pdf.image(img_byte_arr, x=10, y=pdf.get_y()+10, w=25)
        
    return bytes(pdf.output(dest='S'))

# ==========================================
# 5. INTERFACE STREAMLIT (MODULES)
# ==========================================

def show_dashboard():
    st.header("🏠 Tableau de bord")
    clients = get_all_clients()
    devis_list = get_all_devis()
    factures = get_all_factures()
    paiements = JSONDB.read("paiements")
    ofs = get_all_ofs()
    
    total_ca = sum([d["total_ttc"] for d in devis_list if d["statut"] in ["Accepté", "Facturé"]])
    total_paye = sum([p["montant"] for p in paiements])
    impayes = sum([f["total_ttc"] for f in factures if f["statut"] != "Payé"]) - total_paye
    ofs_en_cours = len([o for o in ofs if o["statut"] in ["En attente", "En production"]])
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Clients", len(clients))
    col2.metric("Devis", len(devis_list))
    col3.metric("Factures", len(factures))
    col4.metric("CA Validé", f"{total_ca:,.0f} DA")
    col5.metric("Impayés", f"{impayes:,.0f} DA")
    col6.metric("OFs en cours", ofs_en_cours)
    
    st.markdown("---")
    st.subheader("Évolution des Devis")
    if devis_list:
        df = pd.DataFrame([{'Date': pd.to_datetime(d["date"]), 'Total TTC': d["total_ttc"]} for d in devis_list])
        df['Mois'] = df['Date'].dt.to_period('M').astype(str)
        ca_mensuel = df.groupby('Mois')['Total TTC'].sum().reset_index()
        fig = px.bar(ca_mensuel, x='Mois', y='Total TTC', title="Chiffre d'Affaires Mensuel (DA)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun devis pour afficher les statistiques.")

def show_clients():
    st.header("👤 Gestion des Clients")
    with st.expander("➕ Ajouter un nouveau client"):
        with st.form("client_form"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom*")
                prenom = st.text_input("Prénom")
                tel1 = st.text_input("Téléphone 1*")
                tel2 = st.text_input("Téléphone 2")
            with c2:
                societe = st.text_input("Société")
                wilaya = st.text_input("Wilaya")
                commune = st.text_input("Commune")
                adresse = st.text_area("Adresse")
            
            if st.form_submit_button("Enregistrer"):
                if nom and tel1:
                    create_client({
                        "nom": nom, "prenom": prenom, "societe": societe, 
                        "telephone1": tel1, "telephone2": tel2, "wilaya": wilaya, 
                        "commune": commune, "adresse": adresse, "notes": ""
                    })
                    st.success("Client ajouté avec succès !")
                    st.rerun()
                else:
                    st.error("Le nom et le téléphone 1 sont obligatoires.")
    
    st.subheader("Liste des Clients")
    clients = get_all_clients()
    if clients:
        for client in clients:
            with st.expander(f"#{client['id']} - {client['prenom']} {client['nom']} ({client['telephone1']})"):
                with st.form(f"edit_client_{client['id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nom", client['nom'], key=f"nom_{client['id']}")
                        e_prenom = st.text_input("Prénom", client['prenom'], key=f"prenom_{client['id']}")
                        e_tel1 = st.text_input("Téléphone 1", client['telephone1'], key=f"tel1_{client['id']}")
                    with c2:
                        e_societe = st.text_input("Société", client.get('societe', ''), key=f"soc_{client['id']}")
                        e_wilaya = st.text_input("Wilaya", client.get('wilaya', ''), key=f"wil_{client['id']}")
                    
                    col_btn1, col_btn2 = st.columns([1, 4])
                    if col_btn1.form_submit_button("🗑️ Supprimer"):
                        delete_client(client['id'])
                        st.rerun()
                    if col_btn2.form_submit_button("💾 Mettre à jour"):
                        update_client(client['id'], {
                            "nom": e_nom, "prenom": e_prenom, "societe": e_societe, 
                            "telephone1": e_tel1, "wilaya": e_wilaya
                        })
                        st.success("Client mis à jour !")
                        st.rerun()
    else:
        st.info("Aucun client enregistré.")

def show_tarifs():
    st.header("💰 Gestion des Tarifs")
    tarifs = get_tarifs()
    
    st.subheader("Tarifs Aluminium (Prix au ML)")
    for alu in tarifs["aluminium"]:
        c1, c2 = st.columns([3, 1])
        c1.text(alu["serie"])
        new_price = c2.number_input(f"Prix {alu['serie']}", 0.0, 100000.0, float(alu["prix_ml"]), key=f"alu_{alu['serie']}")
        if new_price != alu["prix_ml"]:
            alu["prix_ml"] = new_price
            update_tarifs(tarifs)
            st.success(f"Prix {alu['serie']} mis à jour !")
            st.rerun()

    st.subheader("Tarifs Vitrage (Prix au m²)")
    for vit in tarifs["vitrage"]:
        c1, c2 = st.columns([3, 1])
        c1.text(vit["type"])
        new_price = c2.number_input(f"Prix {vit['type']}", 0.0, 100000.0, float(vit["prix_m2"]), key=f"vit_{vit['type']}")
        if new_price != vit["prix_m2"]:
            vit["prix_m2"] = new_price
            update_tarifs(tarifs)
            st.success(f"Prix {vit['type']} mis à jour !")
            st.rerun()

    st.subheader("Suppléments Couleurs")
    for coul in tarifs["couleurs"]:
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.text(coul["nom"])
        new_fixe = c2.number_input(f"Fixe {coul['nom']}", 0.0, 100000.0, float(coul.get("supplement_fixe", 0)), key=f"coul_f_{coul['nom']}")
        new_pct = c3.number_input(f"% {coul['nom']}", 0.0, 100.0, float(coul.get("supplement_pourcentage", 0)), key=f"coul_p_{coul['nom']}")
        if new_fixe != coul.get("supplement_fixe", 0) or new_pct != coul.get("supplement_pourcentage", 0):
            coul["supplement_fixe"] = new_fixe
            coul["supplement_pourcentage"] = new_pct
            update_tarifs(tarifs)
            st.success(f"Couleur {coul['nom']} mise à jour !")
            st.rerun()

def show_devis():
    st.header("📄 Création de Devis")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    clients = get_all_clients()
    if not clients:
        st.warning("Veuillez d'abord créer un client avant de faire un devis.")
        return

    st.subheader("Informations du Devis")
    c1, c2, c3 = st.columns(3)
    with c1:
        client_opts = {f"{c['prenom']} {c['nom']} ({c['telephone1']})": c["id"] for c in clients}
        client_sel = st.selectbox("Client", list(client_opts.keys()))
        commercial = st.text_input("Commercial", "DJEFF")
    with c2:
        marge = st.number_input("Marge (%)", 0, 100, 30)
        remise = st.number_input("Remise (%)", 0.0, 100.0, 0.0)
    with c3:
        tva = st.checkbox("Appliquer TVA (19%)")
        statut = st.selectbox("Statut", ["Brouillon", "Envoyé", "Accepté", "Refusé"])

    st.markdown("---")
    tarifs = get_tarifs()
    st.subheader("Ajouter un produit au panier")
    with st.form("item_form"):
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            p_type = st.selectbox("Type", tarifs["produit_types"])
            p_ouv = st.selectbox("Ouverture", tarifs["ouvertures"])
        with pc2:
            p_larg = st.number_input("Largeur (mm)", 100, 5000, 1200)
            p_haut = st.number_input("Hauteur (mm)", 100, 5000, 1000)
            p_qte = st.number_input("Quantité", 1, 100, 1)
        with pc3:
            p_mat = st.selectbox("Matériau", ["Aluminium", "PVC"])
            p_serie = st.selectbox("Série", [a["serie"] for a in tarifs["aluminium"]])
            p_vitr = st.selectbox("Vitrage", [v["type"] for v in tarifs["vitrage"]])
        with pc4:
            p_coul = st.selectbox("Couleur", [c["nom"] for c in tarifs["couleurs"]])
            
        if st.form_submit_button("➕ Calculer et Ajouter"):
            calc = calculer_prix_item(p_larg, p_haut, p_qte, p_mat, p_serie, p_vitr, p_coul, marge)
            st.session_state.cart.append({
                "produit_type": p_type, "ouverture": p_ouv, "largeur": p_larg, "hauteur": p_haut, 
                "quantite": p_qte, "materiau": p_mat, "serie_profil": p_serie, "type_vitrage": p_vitr, 
                "couleur": p_coul, "prix_unitaire": calc['prix_unitaire'], "total_ligne": calc['total_ligne'],
                "surface": calc['surface'], "perimeter": calc['perimeter']
            })
            st.success(f"Produit ajouté (Total: {calc['total_ligne']} DA)")
            st.rerun()

    if st.session_state.cart:
        st.subheader("Articles du Devis")
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart[['produit_type', 'ouverture', 'largeur', 'hauteur', 'quantite', 'materiau', 'serie_profil', 'type_vitrage', 'couleur', 'prix_unitaire', 'total_ligne']], use_container_width=True)
        
        col_total1, col_total2 = st.columns([3, 1])
        with col_total2:
            if st.button("🗑️ Vider le panier"):
                st.session_state.cart = []
                st.rerun()
                
            total_ht = sum([i['total_ligne'] for i in st.session_state.cart])
            total_remise = total_ht * (remise / 100)
            total_ht_net = total_ht - total_remise
            total_tva = total_ht_net * 0.19 if tva else 0
            total_ttc = total_ht_net + total_tva
            
            st.markdown(f"**Sous-total HT :** {total_ht:,.2f} DA")
            st.markdown(f"**Remise ({remise}%) :** -{total_remise:,.2f} DA")
            st.markdown(f"**Total HT Net :** {total_ht_net:,.2f} DA")
            if tva: st.markdown(f"**TVA (19%) :** {total_tva:,.2f} DA")
            st.markdown(f"### TOTAL TTC : {total_ttc:,.2f} DA")
            
            if st.button("💾 Valider et Enregistrer le Devis", type="primary"):
                year = datetime.now().year
                prefix = f"DEV-{year}-"
                existing_devis = get_all_devis()
                last = [d for d in existing_devis if d["numero"].startswith(prefix)]
                seq = len(last) + 1
                num_devis = f"{prefix}{seq:04d}"
                
                create_devis({
                    "numero": num_devis, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "client_id": client_opts[client_sel], "commercial": commercial, "statut": statut,
                    "marge": marge, "remise": remise, "tva": tva, "total_ht": total_ht_net, 
                    "total_ttc": total_ttc, "items": st.session_state.cart
                })
                st.session_state.cart = []
                st.success(f"Devis {num_devis} enregistré avec succès !")
                st.balloons()
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Devis Enregistrés")
    devis_list = get_all_devis()
    if devis_list:
        for d in reversed(devis_list):
            client = next((c for c in clients if c["id"] == d["client_id"]), {"nom": "Inconnu", "prenom": ""})
            with st.expander(f"{d['numero']} - {client['prenom']} {client['nom']} - {d['total_ttc']:,.2f} DA [{d['statut']}]"):
                st.write(f"**Date:** {d['date']} | **Commercial:** {d['commercial']}")
                st.dataframe(pd.DataFrame(d["items"]), use_container_width=True)
                
                col_pdf, col_fac = st.columns(2)
                if col_pdf.button("📄 Générer PDF Devis", key=f"pdf_{d['id']}"):
                    pdf_bytes = generate_pdf(d, "Devis")
                    col_pdf.download_button("⬇️ Télécharger", pdf_bytes, f"{d['numero']}.pdf", "application/pdf")
                
                if d["statut"] == "Accepté":
                    if col_fac.button("➡️ Convertir en Facture", key=f"fac_{d['id']}"):
                        num_fac = create_facture_from_devis(d["id"])
                        st.success(f"Facture {num_fac} créée avec succès !")
                        st.rerun()
    else:
        st.info("Aucun devis enregistré.")

def show_factures():
    st.header("🧾 Factures & Paiements")
    factures = get_all_factures()
    clients = get_all_clients()
    
    if not factures:
        st.info("Aucune facture émise. Convertissez un devis accepté en facture.")
        return
        
    for f in reversed(factures):
        client = next((c for c in clients if c["id"] == f["client_id"]), {"nom": "Inconnu", "prenom": ""})
        paiements = get_paiements_for_facture(f["id"])
        total_paye = sum([p["montant"] for p in paiements])
        reste = f["total_ttc"] - total_paye
        
        with st.expander(f"{f['numero']} - {client['prenom']} {client['nom']} - {f['total_ttc']:,.2f} DA [{f['statut']}]"):
            st.write(f"**Date:** {f['date']} | **Total Payé:** {total_paye:,.2f} DA | **Reste à payer:** {reste:,.2f} DA")
            
            col_pdf, col_pay, col_of = st.columns(3)
            if col_pdf.button("📄 Générer PDF Facture", key=f"pdf_fac_{f['id']}"):
                pdf_bytes = generate_pdf(f, "Facture")
                col_pdf.download_button("⬇️ Télécharger", pdf_bytes, f"{f['numero']}.pdf", "application/pdf")
            
            if col_of.button("🛠️ Envoyer en Atelier (OF)", key=f"of_{f['id']}"):
                num_of = create_of_from_facture(f["id"])
                st.success(f"Ordre de Fabrication {num_of} créé !")
                st.rerun()
            
            with col_pay.form(f"pay_form_{f['id']}"):
                st.write("**Enregistrer un paiement:**")
                montant = st.number_input("Montant (DA)", 0.0, float(reste) if reste > 0 else 0.0, 0.0, key=f"mnt_{f['id']}")
                methode = st.selectbox("Méthode", ["Espèces", "Virement", "Chèque", "CCP"], key=f"meth_{f['id']}")
                if st.form_submit_button("Valider le paiement"):
                    create_paiement({
                        "facture_id": f["id"],
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "montant": montant,
                        "methode": methode
                    })
                    st.success("Paiement enregistré !")
                    st.rerun()

def show_atelier():
    st.header("🛠️ Gestion de l'Atelier (Ordres de Fabrication)")
    ofs = get_all_ofs()
    clients = get_all_clients()
    
    if not ofs:
        st.info("Aucun ordre de fabrication. Convertissez une facture en OF.")
        return
        
    for o in reversed(ofs):
        client = next((c for c in clients if c["id"] == o["client_id"]), {"nom": "Inconnu", "prenom": ""})
        
        # Couleurs selon le statut
        if o["statut"] == "Terminé":
            icon = "✅"
        elif o["statut"] == "En production":
            icon = "⏳"
        else:
            icon = "⏸️"
            
        with st.expander(f"{icon} {o['numero']} - {client['prenom']} {client['nom']} [{o['statut']}]"):
            col_info, col_statut = st.columns([3, 1])
            with col_info:
                st.write(f"**Date de création:** {o['date_creation']}")
                st.write("**Liste des pièces à fabriquer :**")
                
                # Préparation du tableau de coupe
                df_items = pd.DataFrame(o["items"])
                df_coupe = df_items[['produit_type', 'ouverture', 'couleur', 'largeur', 'hauteur', 'quantite']].copy()
                df_coupe.columns = ['Type', 'Ouverture', 'Couleur', 'Largeur (mm)', 'Hauteur (mm)', 'Qté']
                st.table(df_coupe)
                
            with col_statut:
                new_statut = st.selectbox("Statut de l'OF", ["En attente", "En production", "Terminé"], 
                                          index=["En attente", "En production", "Terminé"].index(o["statut"]),
                                          key=f"statut_of_{o['id']}")
                if st.button("💾 Mettre à jour le statut", key=f"upd_of_{o['id']}"):
                    update_of_statut(o["id"], new_statut)
                    st.success(f"Statut de l'OF {o['numero']} mis à jour !")
                    st.rerun()

def show_parametres():
    st.header("⚙️ Paramètres de l'entreprise")
    params = get_parametres()
    
    with st.form("param_form"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom Entreprise", params.get("nom_entreprise", ""))
            tel = st.text_input("Téléphone", params.get("telephone", ""))
            email = st.text_input("Email", params.get("email", ""))
            adresse = st.text_area("Adresse", params.get("adresse", ""))
        with c2:
            rc = st.text_input("RC", params.get("rc", ""))
            nif = st.text_input("NIF", params.get("nif", ""))
            nis = st.text_input("NIS", params.get("nis", ""))
            tva = st.number_input("Taux TVA (%)", 0.0, 100.0, float(params.get("tva_taux", 19.0)))
        
        if st.form_submit_button("Mettre à jour les paramètres"):
            update_parametres({
                "nom_entreprise": nom, "telephone": tel, "email": email, "adresse": adresse,
                "rc": rc, "nif": nif, "nis": nis, "tva_taux": tva
            })
            st.success("Paramètres enregistrés avec succès !")

# ==========================================
# 6. POINT D'ENTRÉE PRINCIPAL
# ==========================================

def main():
    st.set_page_config(page_title="DJEFF ALUMINIUM PRO", page_icon="🏭", layout="wide")
    init_db()
    
    st.sidebar.title("🏭 DJEFF ALUMINIUM PRO")
    menu = st.sidebar.radio("Navigation", [
        "🏠 Tableau de bord", 
        "👤 Clients", 
        "📄 Devis", 
        "🧾 Factures", 
        "🛠️ Atelier",
        "💰 Tarifs", 
        "⚙️ Paramètres"
    ])
    
    if menu == "🏠 Tableau de bord":
        show_dashboard()
    elif menu == "👤 Clients":
        show_clients()
    elif menu == "📄 Devis":
        show_devis()
    elif menu == "🧾 Factures":
        show_factures()
    elif menu == "🛠️ Atelier":
        show_atelier()
    elif menu == "💰 Tarifs":
        show_tarifs()
    elif menu == "⚙️ Paramètres":
        show_parametres()

if __name__ == "__main__":
    main()
