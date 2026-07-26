import os
import io
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import qrcode
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from fpdf import FPDF

# ==========================================
# 1. CONFIGURATION & BASE DE DONNÉES
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "assets"), exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "djeff_aluminium.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 2. MODÈLES (SQLAlchemy)
# ==========================================

class Parametres(Base):
    __tablename__ = "parametres"
    id = Column(Integer, primary_key=True)
    nom_entreprise = Column(String, default="DJEFF ALUMINIUM PRO")
    telephone = Column(String, default="0555000000")
    email = Column(String, default="contact@djeff.dz")
    adresse = Column(String, default="Alger, Algérie")
    rc = Column(String, default="16/00-1234567 B 23")
    nif = Column(String, default="000916123456789")
    nis = Column(String, default="098765432109876")
    tva_taux = Column(Float, default=19.0)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    nom = Column(String)
    prenom = Column(String)
    societe = Column(String)
    telephone1 = Column(String)
    telephone2 = Column(String)
    email = Column(String)
    adresse = Column(String)
    wilaya = Column(String)
    commune = Column(String)
    notes = Column(Text)
    date_creation = Column(DateTime, default=datetime.utcnow)
    devis = relationship("Devis", back_populates="client")

class ProduitType(Base):
    __tablename__ = "produit_types"
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True)

class Ouverture(Base):
    __tablename__ = "ouvertures"
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True)

class TarifAluminium(Base):
    __tablename__ = "tarifs_aluminium"
    id = Column(Integer, primary_key=True)
    serie = Column(String, unique=True)
    prix_ml = Column(Float)

class TarifVitrage(Base):
    __tablename__ = "tarifs_vitrage"
    id = Column(Integer, primary_key=True)
    type = Column(String, unique=True)
    prix_m2 = Column(Float)

class Couleur(Base):
    __tablename__ = "couleurs"
    id = Column(Integer, primary_key=True)
    nom = Column(String, unique=True)
    supplement_fixe = Column(Float, default=0.0)
    supplement_pourcentage = Column(Float, default=0.0)

class Devis(Base):
    __tablename__ = "devis"
    id = Column(Integer, primary_key=True)
    numero = Column(String, unique=True)
    date = Column(DateTime, default=datetime.utcnow)
    client_id = Column(Integer, ForeignKey("clients.id"))
    commercial = Column(String, default="Commercial")
    statut = Column(String, default="Brouillon")
    marge = Column(Float, default=30.0)
    remise = Column(Float, default=0.0)
    tva = Column(Boolean, default=False)
    total_ht = Column(Float, default=0.0)
    total_ttc = Column(Float, default=0.0)
    client = relationship("Client", back_populates="devis")
    items = relationship("DevisItem", back_populates="devis", cascade="all, delete-orphan")

class DevisItem(Base):
    __tablename__ = "devis_items"
    id = Column(Integer, primary_key=True)
    devis_id = Column(Integer, ForeignKey("devis.id"))
    produit_type = Column(String)
    ouverture = Column(String)
    largeur = Column(Float)
    hauteur = Column(Float)
    quantite = Column(Integer, default=1)
    materiau = Column(String)
    serie_profil = Column(String)
    type_vitrage = Column(String)
    couleur = Column(String)
    prix_unitaire = Column(Float)
    total_ligne = Column(Float)
    surface = Column(Float)
    perimeter = Column(Float)
    devis = relationship("Devis", back_populates="items")

# ==========================================
# 3. INITIALISATION DB
# ==========================================

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(Parametres).first():
        db.add(Parametres())
    if not db.query(ProduitType).first():
        for t in ["Fenêtre", "Imposte", "Porte", "Porte-fenêtre", "Baie vitrée", "Portail"]:
            db.add(ProduitType(nom=t))
    if not db.query(Ouverture).first():
        for o in ["Fixe", "1 vantail", "2 vantaux", "3 vantaux", "Coulissante", "Oscillo-battante"]:
            db.add(Ouverture(nom=o))
    if not db.query(TarifAluminium).first():
        for s in ["Série 40", "Série 45", "Série 50", "Série 60", "Série 70"]:
            db.add(TarifAluminium(serie=s, prix_ml=1500.0))
    if not db.query(TarifVitrage).first():
        for v in ["Simple vitrage", "Double vitrage", "Vitrage sécurit", "Vitrage feuilleté"]:
            db.add(TarifVitrage(type=v, prix_m2=3500.0))
    if not db.query(Couleur).first():
        db.add(Couleur(nom="Blanc", supplement_fixe=0, supplement_pourcentage=0))
        db.add(Couleur(nom="Gris Anthracite", supplement_fixe=0, supplement_pourcentage=15))
        db.add(Couleur(nom="Chêne Doré", supplement_fixe=0, supplement_pourcentage=20))
    db.commit()
    db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 4. MOTEUR DE CALCUL
# ==========================================

def calculer_prix_item(db, largeur, hauteur, qt, materiau, serie, vitrage, couleur_nom, marge):
    largeur_m = largeur / 1000
    hauteur_m = hauteur / 1000
    surface = largeur_m * hauteur_m
    perimeter = (largeur_m + hauteur_m) * 2
    
    cout_profil = 0
    if materiau == "Aluminium":
        profil = db.query(TarifAluminium).filter_by(serie=serie).first()
        cout_profil = profil.prix_ml * perimeter if profil else 0
        
    vitrage_obj = db.query(TarifVitrage).filter_by(type=vitrage).first()
    cout_vitrage = vitrage_obj.prix_m2 * surface if vitrage_obj else 0
    
    couleur_obj = db.query(Couleur).filter_by(nom=couleur_nom).first()
    cout_couleur = 0
    if couleur_obj:
        cout_couleur = couleur_obj.supplement_fixe * perimeter
        if couleur_obj.supplement_pourcentage > 0:
            cout_couleur += (cout_profil * couleur_obj.supplement_pourcentage / 100)
            
    cout_mo = (cout_profil + cout_vitrage + cout_couleur) * 0.20
    cout_revient = cout_profil + cout_vitrage + cout_couleur + cout_mo
    prix_vente_ht = cout_revient * (1 + marge / 100)
    
    return {
        'surface': surface,
        'perimeter': perimeter,
        'prix_unitaire': round(prix_vente_ht, 2),
        'total_ligne': round(prix_vente_ht * qt, 2)
    }

# ==========================================
# 5. GÉNÉRATEUR PDF
# ==========================================

class DevisPDF(FPDF):
    def header(self):
        if hasattr(self, 'params'):
            params = self.params
            logo_path = os.path.join("assets", "logo.png")
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 33)
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, params.nom_entreprise, 0, 1, 'R')
            self.set_font('Arial', '', 9)
            self.cell(0, 5, f"Tel: {params.telephone} | Email: {params.email}", 0, 1, 'R')
            self.cell(0, 5, f"RC: {params.rc} | NIF: {params.nif} | NIS: {params.nis}", 0, 1, 'R')
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Conditions: 50% à la commande, 50% à la livraison. Validité: 30 jours.', 0, 0, 'C')

def generate_devis_pdf(db, devis_id):
    devis = db.query(Devis).get(devis_id)
    client = devis.client
    items = devis.items
    params = db.query(Parametres).first()
    
    pdf = DevisPDF()
    pdf.params = params
    pdf.add_page()
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"DEVIS N°: {devis.numero}", 0, 1, 'L')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 7, f"Date: {devis.date.strftime('%d/%m/%Y')}", 0, 1, 'L')
    pdf.ln(5)
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(95, 8, "Client:", 1, 0, 'L', 1)
    pdf.cell(95, 8, "Informations:", 1, 1, 'L', 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 8, f"{client.prenom} {client.nom}", 1, 0)
    pdf.cell(95, 8, f"Statut: {devis.statut}", 1, 1)
    pdf.cell(95, 8, f"Tel: {client.telephone1}", 1, 0)
    pdf.cell(95, 8, f"Commercial: {devis.commercial}", 1, 1)
    pdf.multi_cell(190, 8, f"Adresse: {client.adresse}, {client.wilaya}", 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 9)
    headers = ["Désignation", "Ouverture", "Dim (LxH)", "Qté", "P.U HT", "Total HT"]
    widths = [50, 30, 35, 15, 30, 30]
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    for item in items:
        designation = f"{item.produit_type} {item.couleur} ({item.serie_profil})"
        pdf.cell(widths[0], 8, designation[:35], 1, 0)
        pdf.cell(widths[1], 8, item.ouverture[:15], 1, 0)
        pdf.cell(widths[2], 8, f"{int(item.largeur)}x{int(item.hauteur)}", 1, 0, 'C')
        pdf.cell(widths[3], 8, str(item.quantite), 1, 0, 'C')
        pdf.cell(widths[4], 8, f"{item.prix_unitaire:,.2f} DA", 1, 0, 'R')
        pdf.cell(widths[5], 8, f"{item.total_ligne:,.2f} DA", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(50, 8, "Sous Total HT:", 1, 0)
    pdf.cell(30, 8, f"{devis.total_ht:,.2f} DA", 1, 1, 'R')
    
    if devis.tva:
        tva_montant = devis.total_ht * (params.tva_taux / 100)
        pdf.set_x(110)
        pdf.cell(50, 8, f"TVA ({params.tva_taux}%):", 1, 0)
        pdf.cell(30, 8, f"{tva_montant:,.2f} DA", 1, 1, 'R')
        
    pdf.set_x(110)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(50, 10, "TOTAL TTC:", 1, 0, 'R', True)
    pdf.cell(30, 10, f"{devis.total_ttc:,.2f} DA", 1, 1, 'R', True)
    
    # QR Code généré en mémoire (RAM)
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(f"Devis: {devis.numero}|Client: {client.nom}|Total: {devis.total_ttc}")
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    pdf.image(img_byte_arr, x=10, y=pdf.get_y()+10, w=25)
        
    # Retourne les bytes pour Streamlit
    return bytes(pdf.output(dest='S'))

# ==========================================
# 6. INTERFACE STREAMLIT
# ==========================================

def main():
    st.set_page_config(page_title="DJEFF ALUMINIUM PRO", page_icon="🏭", layout="wide")
    init_db()
    db = next(get_db())
    
    st.sidebar.title("🏭 DJEFF ALUMINIUM PRO")
    menu = st.sidebar.radio("Navigation", [
        "🏠 Tableau de bord", "👤 Clients", "📄 Devis", 
        "💰 Tarifs", "⚙️ Paramètres"
    ])
    
    if menu == "🏠 Tableau de bord":
        show_dashboard(db)
    elif menu == "👤 Clients":
        show_clients(db)
    elif menu == "📄 Devis":
        show_devis(db)
    elif menu == "💰 Tarifs":
        show_tarifs(db)
    elif menu == "⚙️ Paramètres":
        show_parametres(db)

def show_dashboard(db):
    st.header("🏠 Tableau de bord")
    col1, col2, col3, col4 = st.columns(4)
    
    total_ca = db.query(func.sum(Devis.total_ttc)).filter(Devis.statut == 'Accepté').scalar() or 0
    
    col1.metric("Total Clients", db.query(Client).count())
    col2.metric("Total Devis", db.query(Devis).count())
    col3.metric("Devis Acceptés", db.query(Devis).filter_by(statut="Accepté").count())
    col4.metric("CA Total (DA)", f"{total_ca:,.0f}")
    
    st.markdown("---")
    st.subheader("Évolution des Devis")
    devis_data = db.query(Devis).all()
    if devis_data:
        df = pd.DataFrame([{
            'Date': d.date,
            'Total TTC': d.total_ttc,
            'Statut': d.statut
        } for d in devis_data])
        df['Mois'] = df['Date'].dt.to_period('M').astype(str)
        ca_mensuel = df.groupby('Mois')['Total TTC'].sum().reset_index()
        fig = px.bar(ca_mensuel, x='Mois', y='Total TTC', title="Chiffre d'Affaires Mensuel (DA)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucun devis pour afficher les statistiques.")

def show_clients(db):
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
                    new_client = Client(nom=nom, prenom=prenom, societe=societe, telephone1=tel1, 
                                        telephone2=tel2, wilaya=wilaya, commune=commune, adresse=adresse)
                    db.add(new_client)
                    db.commit()
                    st.success("Client ajouté avec succès !")
                    st.rerun()
                else:
                    st.error("Le nom et le téléphone sont obligatoires.")
    
    st.subheader("Liste des Clients")
    clients = db.query(Client).all()
    if clients:
        df = pd.DataFrame([{
            'ID': c.id, 'Nom': c.nom, 'Prénom': c.prenom, 'Téléphone': c.telephone1, 
            'Société': c.societe, 'Wilaya': c.wilaya
        } for c in clients])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucun client enregistré.")

def show_devis(db):
    st.header("📄 Création de Devis")
    
    if 'cart' not in st.session_state:
        st.session_state.cart = []

    clients = db.query(Client).all()
    if not clients:
        st.warning("Veuillez d'abord créer un client avant de faire un devis.")
        return

    # 1. Informations du Devis (Hors formulaire pour garder les valeurs en mémoire)
    st.subheader("Informations du Devis")
    c1, c2, c3 = st.columns(3)
    with c1:
        client_opts = {f"{c.prenom} {c.nom} ({c.telephone1})": c.id for c in clients}
        client_sel = st.selectbox("Client", list(client_opts.keys()))
        commercial = st.text_input("Commercial", "DJEFF")
    with c2:
        marge = st.number_input("Marge (%)", 0, 100, 30)
        remise = st.number_input("Remise (%)", 0.0, 100.0, 0.0)
    with c3:
        tva = st.checkbox("Appliquer TVA (19%)")
        statut = st.selectbox("Statut", ["Brouillon", "Envoyé", "Accepté", "Refusé"])

    st.markdown("---")
    
    # 2. Formulaire d'ajout d'article
    st.subheader("Ajouter un produit au panier")
    with st.form("item_form"):
        types = [t.nom for t in db.query(ProduitType).all()]
        ouv = [o.nom for o in db.query(Ouverture).all()]
        series = [s.serie for s in db.query(TarifAluminium).all()]
        vitrages = [v.type for v in db.query(TarifVitrage).all()]
        couleurs = [c.nom for c in db.query(Couleur).all()]
        
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
            calc = calculer_prix_item(db, p_larg, p_haut, p_qte, p_mat, p_serie, p_vitr, p_coul, marge)
            item = {
                "type": p_type, "ouv": p_ouv, "larg": p_larg, "haut": p_haut, "qte": p_qte,
                "mat": p_mat, "serie": p_serie, "vitr": p_vitr, "coul": p_coul,
                "pu": calc['prix_unitaire'], "total": calc['total_ligne'],
                "surf": calc['surface'], "peri": calc['perimeter']
            }
            st.session_state.cart.append(item)
            st.success(f"Produit ajouté au panier (Total: {calc['total_ligne']} DA)")

    # 3. Affichage du panier et validation
    if st.session_state.cart:
        st.subheader("Articles du Devis")
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart[['type', 'ouv', 'larg', 'haut', 'qte', 'mat', 'serie', 'vitr', 'coul', 'pu', 'total']], use_container_width=True)
        
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
                year = datetime.now().year
                prefix = f"DEV-{year}-"
                last = db.query(Devis).filter(Devis.numero.like(f"{prefix}%")).order_by(Devis.id.desc()).first()
                seq = int(last.numero[-4:]) + 1 if last else 1
                num_devis = f"{prefix}{seq:04d}"
                
                new_devis = Devis(
                    numero=num_devis, client_id=client_opts[client_sel], commercial=commercial,
                    statut=statut, marge=marge, remise=remise, tva=tva, 
                    total_ht=total_ht_net, total_ttc=total_ttc
                )
                db.add(new_devis)
                db.commit()
                
                for it in st.session_state.cart:
                    db_item = DevisItem(
                        devis_id=new_devis.id, produit_type=it['type'], ouverture=it['ouv'],
                        largeur=it['larg'], hauteur=it['haut'], quantite=it['qte'],
                        materiau=it['mat'], serie_profil=it['serie'], type_vitrage=it['vitr'],
                        couleur=it['coul'], prix_unitaire=it['pu'], total_ligne=it['total'],
                        surface=it['surf'], perimeter=it['peri']
                    )
                    db.add(db_item)
                db.commit()
                st.session_state.cart = []
                st.success(f"Devis {num_devis} enregistré avec succès !")
                st.balloons()
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Devis Enregistrés")
    devis_list = db.query(Devis).order_by(Devis.id.desc()).all()
    if devis_list:
        for d in devis_list:
            with st.expander(f"{d.numero} - {d.client.nom} {d.client.prenom} - {d.total_ttc:,.2f} DA [{d.statut}]"):
                st.write(f"**Date:** {d.date.strftime('%d/%m/%Y')} | **Commercial:** {d.commercial}")
                if st.button("📄 Générer PDF", key=f"pdf_{d.id}"):
                    pdf_bytes = generate_devis_pdf(db, d.id)
                    st.download_button(
                        label="⬇️ Télécharger le PDF",
                        data=pdf_bytes,
                        file_name=f"{d.numero}.pdf",
                        mime="application/pdf"
                    )

def show_tarifs(db):
    st.header("💰 Gestion des Tarifs")
    
    st.subheader("Tarifs Aluminium (Prix au ML)")
    alus = db.query(TarifAluminium).all()
    for alu in alus:
        new_price = st.number_input(f"{alu.serie}", 0.0, 100000.0, float(alu.prix_ml), key=f"alu_{alu.id}")
        if new_price != alu.prix_ml:
            alu.prix_ml = new_price
            db.commit()
            st.success(f"Prix {alu.serie} mis à jour !")
            st.rerun()

    st.subheader("Tarifs Vitrage (Prix au m²)")
    vits = db.query(TarifVitrage).all()
    for vit in vits:
        new_price = st.number_input(f"{vit.type}", 0.0, 100000.0, float(vit.prix_m2), key=f"vit_{vit.id}")
        if new_price != vit.prix_m2:
            vit.prix_m2 = new_price
            db.commit()
            st.success(f"Prix {vit.type} mis à jour !")
            st.rerun()

def show_parametres(db):
    st.header("⚙️ Paramètres de l'entreprise")
    params = db.query(Parametres).first()
    if params:
        with st.form("param_form"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom Entreprise", params.nom_entreprise)
                tel = st.text_input("Téléphone", params.telephone)
                email = st.text_input("Email", params.email)
                adresse = st.text_area("Adresse", params.adresse)
            with c2:
                rc = st.text_input("RC", params.rc)
                nif = st.text_input("NIF", params.nif)
                nis = st.text_input("NIS", params.nis)
                tva = st.number_input("Taux TVA (%)", 0.0, 100.0, float(params.tva_taux))
            
            if st.form_submit_button("Mettre à jour"):
                params.nom_entreprise = nom
                params.telephone = tel
                params.email = email
                params.adresse = adresse
                params.rc = rc
                params.nif = nif
                params.nis = nis
                params.tva_taux = tva
                db.commit()
                st.success("Paramètres enregistrés !")

if __name__ == "__main__":
    main()
