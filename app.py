import os
import io
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import qrcode
from fpdf import FPDF
import json

# Importation de notre moteur de base de données JSON
import json_database as db

# ==========================================
# 1. MOTEUR DE CALCUL (Adapté pour JSON)
# ==========================================

def calculer_prix_item(tarifs, largeur, hauteur, qt, materiau, serie, vitrage, couleur_nom, marge):
    largeur_m = largeur / 1000
    hauteur_m = hauteur / 1000
    surface = largeur_m * hauteur_m
    perimeter = (largeur_m + hauteur_m) * 2
    
    cout_profil = 0
    if materiau == "Aluminium":
        # On lit le prix directement depuis le dictionnaire JSON des tarifs
        prix_ml = tarifs['aluminium'].get(serie, 0)
        cout_profil = prix_ml * perimeter
        
    cout_vitrage = tarifs['vitrages'].get(vitrage, 0) * surface
    
    # Gestion des couleurs (gestion simplifiée pour JSON)
    cout_couleur = 0
    if couleur_nom == "Gris Anthracite":
        cout_couleur = cout_profil * 0.15
    elif couleur_nom == "Chêne Doré":
        cout_couleur = cout_profil * 0.20
            
    cout_mo = (cout_profil + cout_vitrage + cout_couleur) * 0.20
    cout_revient = cout_profil + cout_vitrage + cout_couleur + cout_mo
    prix_vente_ht = cout_revient * (1 + marge / 100)
    
    return {
        'surface': round(surface, 2),
        'ml': round(perimeter, 2),
        'prix_unitaire': round(prix_vente_ht, 2),
        'total_ligne': round(prix_vente_ht * qt, 2)
    }

# ==========================================
# 2. GÉNÉRATEUR PDF (Adapté pour Dictionnaires JSON)
# ==========================================

class DocumentPDF(FPDF):
    def header(self):
        params = self.params
        logo_path = os.path.join("assets", "logo.png")
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 33)
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, params.get('nom_entreprise', ''), 0, 1, 'R')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, f"Tel: {params.get('telephone', '')} | Email: {params.get('email', '')}", 0, 1, 'R')
        self.cell(0, 5, f"RC: {params.get('rc', '')} | NIF: {params.get('nif', '')} | NIS: {params.get('nis', '')}", 0, 1, 'R')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Conditions: 50% à la commande, 50% à la livraison. Validité: 30 jours.', 0, 0, 'C')

def generate_document_pdf(doc_data, client, params, doc_type="devis"):
    pdf = DocumentPDF()
    pdf.params = params
    pdf.add_page()
    
    # Titre du document
    title = "DEVIS N°" if doc_type == "devis" else "FACTURE N°"
    numero = doc_data.get('numero', '')
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"{title}: {numero}", 0, 1, 'L')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Date: {doc_data.get('date', '')}", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(95, 8, "Client:", 1, 0, 'L', 1)
    pdf.cell(95, 8, "Informations:", 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 8, f"{client.get('prenom', '')} {client.get('nom', '')}", 1, 0)
    pdf.cell(95, 8, f"Statut: {doc_data.get('statut', '')}", 1, 1)
    pdf.cell(95, 8, f"Tel: {client.get('telephone', '')}", 1, 0)
    pdf.multi_cell(190, 8, f"Adresse: {client.get('adresse', '')}, {client.get('wilaya', '')}", 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 9)
    headers = ["Désignation", "Ouverture", "Dim (LxH)", "Qté", "P.U HT", "Total HT"]
    widths = [50, 30, 35, 15, 30, 30]
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    for item in doc_data.get('lignes', []):
        designation = f"{item.get('produit', '')} {item.get('couleur', '')} ({item.get('serie', '')})"
        pdf.cell(widths[0], 8, designation[:35], 1, 0)
        pdf.cell(widths[1], 8, item.get('ouverture', '')[:15], 1, 0)
        pdf.cell(widths[2], 8, f"{int(item.get('largeur', 0))}x{int(item.get('hauteur', 0))}", 1, 0, 'C')
        pdf.cell(widths[3], 8, str(item.get('quantite', 1)), 1, 0, 'C')
        pdf.cell(widths[4], 8, f"{item.get('prix_unitaire', 0):,.2f} DA", 1, 0, 'R')
        pdf.cell(widths[5], 8, f"{item.get('total', 0):,.2f} DA", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 10)
    
    total_ht = doc_data.get('total_ht', 0)
    total_ttc = doc_data.get('total_ttc', 0)
    
    pdf.cell(50, 8, "Sous Total HT:", 1, 0)
    pdf.cell(30, 8, f"{total_ht:,.2f} DA", 1, 1, 'R')
    
    if doc_data.get('tva', False):
        tva_montant = total_ht * 0.19
        pdf.set_x(110)
        pdf.cell(50, 8, f"TVA (19%):", 1, 0)
        pdf.cell(30, 8, f"{tva_montant:,.2f} DA", 1, 1, 'R')
        
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(50, 10, "TOTAL TTC:", 1, 0, 'R', True)
    pdf.cell(30, 10, f"{total_ttc:,.2f} DA", 1, 1, 'R', True)
    
    # QR Code
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(f"{title} {numero}|Client: {client.get('nom', '')}|Total: {total_ttc}")
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    pdf.image(img_byte_arr, x=10, y=pdf.get_y()+10, w=25)
        
    return bytes(pdf.output(dest='S'))

# ==========================================
# 3. INTERFACE STREAMLIT
# ==========================================

def main():
    st.set_page_config(page_title="DJEFF ALUMINIUM PRO", page_icon="🏭", layout="wide")
    
    # Initialisation de la base de données JSON
    db.initialize_database()
    
    st.sidebar.title("🏭 DJEFF ALUMINIUM PRO")
    menu = st.sidebar.radio("Navigation", [
        "🏠 Tableau de bord", "👤 Clients", "📄 Devis", "🧾 Factures",
        "💰 Tarifs", "⚙️ Paramètres", "💾 Sauvegarde"
    ])
    
    if menu == "🏠 Tableau de bord":
        show_dashboard()
    elif menu == "👤 Clients":
        show_clients()
    elif menu == "📄 Devis":
        show_devis()
    elif menu == "🧾 Factures":
        show_factures()
    elif menu == "💰 Tarifs":
        show_tarifs()
    elif menu == "⚙️ Paramètres":
        show_parametres()
    elif menu == "💾 Sauvegarde":
        show_backup()

def show_dashboard():
    st.header("🏠 Tableau de bord")
    
    clients = db.get_all_clients()
    devis = db.get_all_quotes()
    factures = db.get_all_invoices()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Clients", len(clients))
    col2.metric("Total Devis", len(devis))
    col3.metric("Total Factures", len(factures))
    
    total_ca = sum([f.get('montant', 0) for f in factures])
    col4.metric("CA Facturé (DA)", f"{total_ca:,.0f}")
    
    st.markdown("---")
    st.subheader("Évolution des Devis")
    if devis:
        df = pd.DataFrame(devis)
        df['Date'] = pd.to_datetime(df['date'])
        df['Mois'] = df['Date'].dt.to_period('M').astype(str)
        ca_mensuel = df.groupby('Mois')['total_ttc'].sum().reset_index()
        fig = px.bar(ca_mensuel, x='Mois', y='total_ttc', title="Chiffre d'Affaires Mensuel (DA)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun devis pour afficher les statistiques.")

def show_clients():
    st.header("👤 Gestion des Clients")
    with st.expander("➕ Ajouter un client"):
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
                    # Sauvegarde dans JSON
                    db.add_client({
                        "nom": nom, "prenom": prenom, "societe": societe, "telephone1": tel1, 
                        "telephone2": tel2, "wilaya": wilaya, "commune": commune, 
                        "adresse": adresse, "notes": ""
                    })
                    st.success("Client ajouté avec succès !")
                    st.rerun()
                else:
                    st.error("Le nom et le téléphone sont obligatoires.")
    
    st.subheader("Liste des Clients")
    clients = db.get_all_clients()
    if clients:
        df = pd.DataFrame(clients)
        st.dataframe(df[['id', 'numero', 'nom', 'prenom', 'telephone1', 'societe', 'wilaya']], use_container_width=True)
    else:
        st.info("Aucun client enregistré.")

def show_devis():
    st.header("📄 Création de Devis")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    clients = db.get_all_clients()
    if not clients:
        st.warning("Veuillez d'abord créer un client avant de faire un devis.")
        return

    st.subheader("Informations du Devis")
    c1, c2, c3 = st.columns(3)
    with c1:
        client_opts = {f"{c.get('prenom', '')} {c['nom']} ({c.get('telephone1', '')})": c['id'] for c in clients}
        client_sel = st.selectbox("Client", list(client_opts.keys()))
        commercial = st.text_input("Commercial", "DJEFF")
    with c2:
        marge = st.number_input("Marge (%)", 0, 100, 30)
        remise = st.number_input("Remise (%)", 0.0, 100.0, 0.0)
    with c3:
        tva = st.checkbox("Appliquer TVA (19%)")
        statut = st.selectbox("Statut", ["Brouillon", "Envoyé", "Accepté", "Refusé"])

    st.markdown("---")
    st.subheader("Ajouter un produit au panier")
    tarifs = db.get_tarifs() # Récupère les tarifs depuis JSON
    
    with st.form("item_form"):
        types = ["Fenêtre", "Imposte", "Porte", "Porte-fenêtre", "Baie vitrée", "Portail"]
        ouv = ["Fixe", "1 vantail", "2 vantaux", "3 vantaux", "Coulissante", "Oscillo-battante"]
        series = list(tarifs['aluminium'].keys())
        vitrages = list(tarifs['vitrages'].keys())
        couleurs = ["Blanc", "Gris Anthracite", "Chêne Doré"]
        
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            p_type = st.selectbox("Type", types)
            p_ouv = st.selectbox("Ouverture", ouv)
        with pc2:
            p_larg = st.number_input("Largeur (mm)", 100, 5000, 1200)
            p_haut = st.number_input("Hauteur (mm)", 100, 5000, 1000)
            p_qte = st.number_input("Quantité", 1, 100, 1)
        with pc3:
            p_mat = st.selectbox("Matériau", ["Aluminium", "PVC"])
            p_serie = st.selectbox("Série", series)
            p_vitr = st.selectbox("Vitrage", vitrages)
        with pc4:
            p_coul = st.selectbox("Couleur", couleurs)
            
        add_btn = st.form_submit_button("➕ Calculer et Ajouter")
            
        if add_btn:
            calc = calculer_prix_item(tarifs, p_larg, p_haut, p_qte, p_mat, p_serie, p_vitr, p_coul, marge)
            item = {
                "produit": p_type, "ouverture": p_ouv, "materiau": p_mat, "couleur": p_coul,
                "largeur": p_larg, "hauteur": p_haut, "serie": p_serie, "vitrage": p_vitr,
                "surface": calc['surface'], "ml": calc['ml'], "quantite": p_qte,
                "prix_unitaire": calc['prix_unitaire'], "total": calc['total_ligne']
            }
            st.session_state.cart.append(item)
            st.success(f"Produit ajouté au panier (Total: {calc['total_ligne']} DA)")
            st.rerun()

    if st.session_state.cart:
        st.subheader("Articles du Devis")
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart[['produit', 'ouverture', 'largeur', 'hauteur', 'quantite', 'materiau', 'serie', 'vitrage', 'couleur', 'prix_unitaire', 'total']], use_container_width=True)
        
        col_total1, col_total2 = st.columns([3, 1])
        with col_total2:
            if st.button("🗑️ Vider le panier"):
                st.session_state.cart = []
                st.rerun()
                
            total_ht = sum([i['total'] for i in st.session_state.cart])
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
                quote_data = {
                    "client_id": client_opts[client_sel],
                    "commercial": commercial,
                    "statut": statut,
                    "marge": marge,
                    "remise": remise,
                    "tva": tva,
                    "total_ht": total_ht_net,
                    "total_ttc": total_ttc,
                    "lignes": st.session_state.cart
                }
                db.create_quote(quote_data)
                st.session_state.cart = []
                st.success("Devis enregistré avec succès !")
                st.balloons()
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Devis Enregistrés")
    devis_list = db.get_all_quotes()
    params = db.get_entreprise_params()
    
    if devis_list:
        for d in reversed(devis_list):
            client = db.get_client(d['client_id'])
            client_name = f"{client.get('prenom', '')} {client['nom']}" if client else "Client inconnu"
            
            with st.expander(f"{d['numero']} - {client_name} - {d['total_ttc']:,.2f} DA [{d['statut']}]"):
                st.write(f"**Date:** {d['date']} | **Commercial:** {d['commercial']}")
                if st.button("📄 Générer PDF Devis", key=f"pdf_{d['id']}"):
                    pdf_bytes = generate_document_pdf(d, client, params, "devis")
                    st.download_button(
                        label="⬇️ Télécharger le PDF",
                        data=pdf_bytes,
                        file_name=f"{d['numero']}.pdf",
                        mime="application/pdf"
                    )

def show_factures():
    st.header("🧾 Gestion des Factures")
    
    st.subheader("Transformer un Devis en Facture")
    devis_list = db.get_all_quotes()
    factures_list = db.get_all_invoices()
    
    # Liste des IDs de devis qui ont DÉJÀ une facture
    devis_deja_factures = [f['devis_id'] for f in factures_list]
    
    # On ne garde que les devis qui n'ont pas encore été facturés
    devis_a_facturer = [d for d in devis_list if d['id'] not in devis_deja_factures]
    
    if not devis_a_facturer:
        st.info("Tous les devis ont déjà été facturés ou aucun devis n'existe.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            devis_opts = {f"{d['numero']} - {db.get_client(d['client_id']).get('nom', 'Inconnu')} ({d['total_ttc']:,.2f} DA)": d['id'] for d in devis_a_facturer}
            sel_devis = st.selectbox("Choisir un devis à facturer", list(devis_opts.keys()))
        
        with col2:
            st.write("") # Espace vide pour l'alignement
            st.write("")
            if st.button("➕ Créer la Facture", type="primary"):
                devis_id = devis_opts[sel_devis]
                devis = db.get_quote(devis_id)
                
                invoice_data = {
                    "devis_id": devis_id,
                    "client_id": devis['client_id'],
                    "montant": devis.get('total_ttc', 0),
                    "statut": "Non payée"
                }
                db.create_invoice(invoice_data)
                st.success("Facture générée avec succès à partir du devis !")
                st.balloons()
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Factures Enregistrées")
    params = db.get_entreprise_params()
    
    if factures_list:
        for f in reversed(factures_list):
            client = db.get_client(f['client_id'])
            client_name = f"{client.get('prenom', '')} {client['nom']}" if client else "Client inconnu"
            devis_source = db.get_quote(f.get('devis_id'))
            
            with st.expander(f"{f['numero']} - {client_name} - {f['montant']:,.2f} DA [{f['statut']}]"):
                st.write(f"**Date:** {f['date']} | **Devis d'origine:** {devis_source.get('numero', 'N/A') if devis_source else 'N/A'}")
                if st.button("📄 Générer PDF Facture", key=f"pdf_fac_{f['id']}"):
                    # On réutilise les infos du devis pour générer le PDF de la facture
                    if devis_source:
                        pdf_bytes = generate_document_pdf(devis_source, client, params, "facture")
                        st.download_button(
                            label="⬇️ Télécharger la Facture PDF",
                            data=pdf_bytes,
                            file_name=f"{f['numero']}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Le devis source est introuvable.")

def show_tarifs():
    st.header("💰 Gestion des Tarifs")
    tarifs = db.get_tarifs()
    
    st.subheader("Tarifs Aluminium (Prix au ML)")
    for serie, prix in tarifs['aluminium'].items():
        new_price = st.number_input(f"{serie}", 0.0, 100000.0, float(prix), key=f"alu_{serie}")
        if new_price != prix:
            tarifs['aluminium'][serie] = new_price
            db.save_tarifs(tarifs)
            st.success(f"Prix {serie} mis à jour !")
            st.rerun()

    st.subheader("Tarifs Vitrage (Prix au m²)")
    for v, prix in tarifs['vitrages'].items():
        new_price = st.number_input(f"{v}", 0.0, 100000.0, float(prix), key=f"vit_{v}")
        if new_price != prix:
            tarifs['vitrages'][v] = new_price
            db.save_tarifs(tarifs)
            st.rerun()

def show_parametres():
    st.header("⚙️ Paramètres de l'entreprise")
    params = db.get_entreprise_params()
    
    with st.form("param_form"):
        c1, c2 = st.columns(2)
        with c1:
            nom = st.text_input("Nom Entreprise", params.get('nom_entreprise', ''))
            tel = st.text_input("Téléphone", params.get('telephone', ''))
            email = st.text_input("Email", params.get('email', ''))
            adresse = st.text_area("Adresse", params.get('adresse', ''))
        with c2:
            rc = st.text_input("RC", params.get('rc', ''))
            nif = st.text_input("NIF", params.get('nif', ''))
            nis = st.text_input("NIS", params.get('nis', ''))
        
        if st.form_submit_button("Mettre à jour"):
            db.save_entreprise_params({
                "nom_entreprise": nom, "telephone": tel, "email": email, 
                "adresse": adresse, "rc": rc, "nif": nif, "nis": nis
            })
            st.success("Paramètres enregistrés !")

def show_backup():
    st.header("💾 Sauvegarde et Restauration")
    st.subheader("Exporter les données")
    if st.button("📥 Générer un fichier JSON complet"):
        data = db.export_all_data()
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        st.download_button(
            label="Télécharger la sauvegarde",
            data=json_str,
            file_name=f"djeff_backup_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
    
    st.subheader("Importer des données")
    uploaded_file = st.file_uploader("Choisissez un fichier JSON", type="json")
    if uploaded_file:
        if st.button("♻️ Importer et écraser les données"):
            try:
                data = json.loads(uploaded_file.getvalue().decode("utf-8"))
                db.import_all_data(data)
                st.success("Données importées avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de l'import: {e}")

if __name__ == "__main__":
    main()
