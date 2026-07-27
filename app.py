import os
import json
import shutil
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

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
        # Sauvegarde automatique avant écriture
        if os.path.exists(filepath):
            backup_name = f"{db_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(filepath, os.path.join(BACKUP_DIR, backup_name))
        
        # Écriture sécurisée
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
# 2. INITIALISATION DES DONNÉES (CRUD Base)
# ==========================================

def init_db():
    """Initialise les fichiers JSON s'ils n'existent pas avec des données par défaut."""
    
    # Paramètres
    if not os.path.exists(DB_FILES["parametres"]):
        default_params = {
            "nom_entreprise": "DJEFF ALUMINIUM PRO",
            "telephone": "0555000000",
            "email": "contact@djeff.dz",
            "adresse": "Alger, Algérie",
            "rc": "16/00-1234567 B 23",
            "nif": "000916123456789",
            "nis": "098765432109876",
            "tva_taux": 19.0
        }
        JSONDB.write("parametres", default_params)

    # Clients
    if not os.path.exists(DB_FILES["clients"]):
        JSONDB.write("clients", [])

    # Devis
    if not os.path.exists(DB_FILES["devis"]):
        JSONDB.write("devis", [])

    # Tarifs (Structure regroupée pour simplifier)
    if not os.path.exists(DB_FILES["tarifs"]):
        default_tarifs = {
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
        }
        JSONDB.write("tarifs", default_tarifs)

    # Counters
    if not os.path.exists(DB_FILES["counters"]):
        JSONDB.write("counters", {"clients": 0, "devis": 0})

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
    return data["id"]

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

# --- Paramètres Service ---
def get_parametres():
    return JSONDB.read("parametres")

def update_parametres(data):
    JSONDB.write("parametres", data)

# ==========================================
# 4. INTERFACE STREAMLIT (MODULES)
# ==========================================

def show_dashboard():
    st.header("🏠 Tableau de bord")
    st.info("Le tableau de bord sera complété une fois le module Devis validé.")
    
    clients = get_all_clients()
    col1, col2 = st.columns(2)
    col1.metric("Total Clients", len(clients))

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
            
            submitted = st.form_submit_button("Enregistrer")
            if submitted:
                if nom and tel1:
                    new_client = {
                        "nom": nom, "prenom": prenom, "societe": societe, 
                        "telephone1": tel1, "telephone2": tel2, "wilaya": wilaya, 
                        "commune": commune, "adresse": adresse, "notes": ""
                    }
                    create_client(new_client)
                    st.success("Client ajouté avec succès !")
                    st.rerun()
                else:
                    st.error("Le nom et le téléphone 1 sont obligatoires.")
    
    st.subheader("Liste des Clients")
    clients = get_all_clients()
    
    if clients:
        df = pd.DataFrame(clients)
        # Affichage et gestion de la modification/suppression
        for index, client in enumerate(clients):
            with st.expander(f"#{client['id']} - {client['prenom']} {client['nom']} ({client['telephone1']})"):
                with st.form(f"edit_client_{client['id']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nom", client['nom'], key=f"nom_{client['id']}")
                        e_prenom = st.text_input("Prénom", client['prenom'], key=f"prenom_{client['id']}")
                        e_tel1 = st.text_input("Téléphone 1", client['telephone1'], key=f"tel1_{client['id']}")
                        e_tel2 = st.text_input("Téléphone 2", client.get('telephone2', ''), key=f"tel2_{client['id']}")
                    with c2:
                        e_societe = st.text_input("Société", client.get('societe', ''), key=f"soc_{client['id']}")
                        e_wilaya = st.text_input("Wilaya", client.get('wilaya', ''), key=f"wil_{client['id']}")
                        e_commune = st.text_input("Commune", client.get('commune', ''), key=f"com_{client['id']}")
                        e_adresse = st.text_area("Adresse", client.get('adresse', ''), key=f"adr_{client['id']}")
                    
                    col_btn1, col_btn2 = st.columns([1, 4])
                    with col_btn1:
                        if st.form_submit_button("🗑️ Supprimer"):
                            delete_client(client['id'])
                            st.rerun()
                        if st.form_submit_button("💾 Mettre à jour"):
                            update_data = {
                                "nom": e_nom, "prenom": e_prenom, "societe": e_societe, 
                                "telephone1": e_tel1, "telephone2": e_tel2, "wilaya": e_wilaya, 
                                "commune": e_commune, "adresse": e_adresse
                            }
                            update_client(client['id'], update_data)
                            st.success("Client mis à jour !")
                            st.rerun()
    else:
        st.info("Aucun client enregistré pour le moment.")

def show_devis():
    st.header("📄 Création de Devis")
    st.warning("Module en cours de développement... Disponible à l'étape suivante.")

def show_tarifs():
    st.header("💰 Gestion des Tarifs")
    st.warning("Module en cours de développement... Disponible à l'étape suivante.")

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
# 5. POINT D'ENTRÉE PRINCIPAL
# ==========================================

def main():
    st.set_page_config(page_title="DJEFF ALUMINIUM PRO", page_icon="🏭", layout="wide")
    init_db()
    
    st.sidebar.title("🏭 DJEFF ALUMINIUM PRO")
    menu = st.sidebar.radio("Navigation", [
        "🏠 Tableau de bord", 
        "👤 Clients", 
        "📄 Devis", 
        "💰 Tarifs", 
        "⚙️ Paramètres"
    ])
    
    if menu == "🏠 Tableau de bord":
        show_dashboard()
    elif menu == "👤 Clients":
        show_clients()
    elif menu == "📄 Devis":
        show_devis()
    elif menu == "💰 Tarifs":
        show_tarifs()
    elif menu == "⚙️ Paramètres":
        show_parametres()

if __name__ == "__main__":
    main()
