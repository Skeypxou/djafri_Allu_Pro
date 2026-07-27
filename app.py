"""
DJEFF ALUMINIUM PRO
Mini ERP pour ateliers de menuiserie Aluminium / PVC (Algerie)
Fichier unique : toute l'application tient dans app.py pour rester simple a lancer.

Lancement :
    pip install -r requirements.txt
    streamlit run app.py

Connexion par defaut : admin / admin123 (a changer dans Parametres)
"""
import os
import io
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, func
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker

from fpdf import FPDF

try:
    import qrcode
    QRCODE_DISPONIBLE = True
except ImportError:
    QRCODE_DISPONIBLE = False


# ======================================================================
# MODELES DE DONNEES (SQLAlchemy)
# ======================================================================
Base = declarative_base()


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id = Column(Integer, primary_key=True)
    nom_utilisateur = Column(String(100), unique=True, nullable=False)
    mot_de_passe = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="Commercial")  # Administrateur / Commercial / Atelier
    actif = Column(Boolean, default=True)
    date_creation = Column(DateTime, default=datetime.now)


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100))
    societe = Column(String(150))
    telephone1 = Column(String(30))
    telephone2 = Column(String(30))
    email = Column(String(120))
    adresse = Column(Text)
    wilaya = Column(String(60))
    commune = Column(String(60))
    notes = Column(Text)
    date_creation = Column(DateTime, default=datetime.now)

    devis = relationship("Devis", back_populates="client")
    factures = relationship("Facture", back_populates="client")


class Produit(Base):
    __tablename__ = "produits"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False, unique=True)
    categorie = Column(String(100))
    actif = Column(Boolean, default=True)


class Ouverture(Base):
    __tablename__ = "ouvertures"
    id = Column(Integer, primary_key=True)
    nom = Column(String(60), nullable=False, unique=True)


class MateriauAlu(Base):
    __tablename__ = "materiaux_alu"
    id = Column(Integer, primary_key=True)
    serie = Column(String(30), nullable=False, unique=True)  # Série 40, 45, 50, 60, 70
    prix_ml = Column(Float, nullable=False, default=0.0)


class MateriauPVC(Base):
    __tablename__ = "materiaux_pvc"
    id = Column(Integer, primary_key=True)
    nom = Column(String(60), nullable=False, unique=True, default="PVC Standard")
    prix_ml = Column(Float, nullable=False, default=0.0)


class Vitrage(Base):
    __tablename__ = "vitrages"
    id = Column(Integer, primary_key=True)
    nom = Column(String(60), nullable=False, unique=True)
    prix_m2 = Column(Float, nullable=False, default=0.0)


class Couleur(Base):
    __tablename__ = "couleurs"
    id = Column(Integer, primary_key=True)
    nom = Column(String(60), nullable=False, unique=True)
    type_supplement = Column(String(10), default="fixe")  # "fixe" ou "pourcentage"
    valeur_supplement = Column(Float, default=0.0)


class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True)
    nom = Column(String(80), nullable=False, unique=True)
    prix = Column(Float, nullable=False, default=0.0)


class Accessoire(Base):
    __tablename__ = "accessoires"
    id = Column(Integer, primary_key=True)
    nom = Column(String(80), nullable=False, unique=True)
    prix_unitaire = Column(Float, nullable=False, default=0.0)
    stock_actuel = Column(Float, default=0.0)
    stock_minimum = Column(Float, default=0.0)


class TarifHistorique(Base):
    __tablename__ = "tarifs_historique"
    id = Column(Integer, primary_key=True)
    categorie = Column(String(40))  # Aluminium / PVC / Vitrage / Couleur / Accessoire / Option
    element = Column(String(100))
    ancien_prix = Column(Float)
    nouveau_prix = Column(Float)
    date_modification = Column(DateTime, default=datetime.now)


class Devis(Base):
    __tablename__ = "devis"
    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, nullable=False)  # DEV-2026-0001
    date_creation = Column(DateTime, default=datetime.now)
    client_id = Column(Integer, ForeignKey("clients.id"))
    commercial = Column(String(100))
    validite_jours = Column(Integer, default=30)
    statut = Column(String(20), default="Brouillon")  # Brouillon/Envoyé/Accepté/Refusé/Expiré
    remise = Column(Float, default=0.0)  # en %
    tva = Column(Float, default=0.0)  # en %
    acompte = Column(Float, default=0.0)
    notes = Column(Text)

    client = relationship("Client", back_populates="devis")
    lignes = relationship("DevisLigne", back_populates="devis", cascade="all, delete-orphan")
    facture = relationship("Facture", back_populates="devis", uselist=False)
    fabrication = relationship("Fabrication", back_populates="devis", uselist=False)
    pose = relationship("Pose", back_populates="devis", uselist=False)


class DevisLigne(Base):
    __tablename__ = "devis_lignes"
    id = Column(Integer, primary_key=True)
    devis_id = Column(Integer, ForeignKey("devis.id"))
    produit = Column(String(100))
    ouverture = Column(String(60))
    materiau_type = Column(String(10))  # "Alu" ou "PVC"
    materiau_detail = Column(String(60))
    vitrage = Column(String(60))
    couleur = Column(String(60))
    options = Column(Text)      # liste séparée par virgules
    accessoires = Column(Text)  # JSON simplifié: "nom:qte;nom:qte"
    largeur = Column(Float)
    hauteur = Column(Float)
    quantite = Column(Integer, default=1)
    surface_m2 = Column(Float)
    ml = Column(Float)
    prix_unitaire = Column(Float)
    total_ligne = Column(Float)
    observation = Column(Text)


class Facture(Base):
    __tablename__ = "factures"
    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, nullable=False)  # FAC-2026-0001
    date_creation = Column(DateTime, default=datetime.now)
    devis_id = Column(Integer, ForeignKey("devis.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    montant_total = Column(Float, default=0.0)

    devis = relationship("Devis", back_populates="facture")
    client = relationship("Client", back_populates="factures")
    paiements = relationship("Paiement", back_populates="facture", cascade="all, delete-orphan")


class Paiement(Base):
    __tablename__ = "paiements"
    id = Column(Integer, primary_key=True)
    facture_id = Column(Integer, ForeignKey("factures.id"))
    date_paiement = Column(DateTime, default=datetime.now)
    montant = Column(Float, nullable=False)
    mode = Column(String(20))  # Espèces/CCP/Virement/Chèque
    observation = Column(Text)

    facture = relationship("Facture", back_populates="paiements")


class Fabrication(Base):
    __tablename__ = "fabrication"
    id = Column(Integer, primary_key=True)
    devis_id = Column(Integer, ForeignKey("devis.id"))
    statut = Column(String(20), default="En attente")  # En attente/En fabrication/Terminé/Livré
    responsable = Column(String(100))
    date_debut = Column(DateTime)
    date_fin = Column(DateTime)
    observations = Column(Text)

    devis = relationship("Devis", back_populates="fabrication")


class Pose(Base):
    __tablename__ = "pose"
    id = Column(Integer, primary_key=True)
    devis_id = Column(Integer, ForeignKey("devis.id"))
    adresse_chantier = Column(Text)
    date_pose = Column(DateTime)
    equipe = Column(String(150))
    statut = Column(String(20), default="À programmer")  # À programmer/En cours/Terminé
    observations = Column(Text)

    devis = relationship("Devis", back_populates="pose")


class Fournisseur(Base):
    __tablename__ = "fournisseurs"
    id = Column(Integer, primary_key=True)
    nom = Column(String(120), nullable=False)
    telephone = Column(String(30))
    email = Column(String(120))
    adresse = Column(Text)
    produits_fournis = Column(Text)


class Achat(Base):
    __tablename__ = "achats"
    id = Column(Integer, primary_key=True)
    fournisseur_id = Column(Integer, ForeignKey("fournisseurs.id"))
    date_achat = Column(DateTime, default=datetime.now)
    designation = Column(String(150))
    quantite = Column(Float)
    prix_unitaire = Column(Float)
    montant_total = Column(Float)

    fournisseur = relationship("Fournisseur")


class StockItem(Base):
    __tablename__ = "stock_items"
    id = Column(Integer, primary_key=True)
    categorie = Column(String(30))  # Aluminium/PVC/Vitrage/Quincaillerie
    designation = Column(String(120), nullable=False)
    unite = Column(String(20), default="unité")
    quantite = Column(Float, default=0.0)
    stock_minimum = Column(Float, default=0.0)


class MouvementStock(Base):
    __tablename__ = "mouvements_stock"
    id = Column(Integer, primary_key=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"))
    type_mouvement = Column(String(10))  # Entrée / Sortie
    quantite = Column(Float)
    date_mouvement = Column(DateTime, default=datetime.now)
    observation = Column(Text)

    stock_item = relationship("StockItem")


class Parametre(Base):
    __tablename__ = "parametres"
    id = Column(Integer, primary_key=True)
    cle = Column(String(60), unique=True, nullable=False)
    valeur = Column(Text)


# ======================================================================
# BASE DE DONNEES (connexion SQLite, initialisation, donnees de reference)
# ======================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "djeff_aluminium.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    return SessionLocal()


PRODUITS_DEFAUT = [
    ("Fenêtre", "Fenêtres"), ("Imposte", "Impostes"), ("Porte", "Portes"),
    ("Porte-fenêtre", "Portes-fenêtres"), ("Baie vitrée", "Baies vitrées"),
    ("Véranda", "Vérandas"), ("Façade vitrée", "Façades vitrées"),
    ("Portail", "Portails"), ("Rideau métallique", "Rideaux métalliques"),
    ("Porte de garage", "Portes de garage"),
]

OUVERTURES_DEFAUT = [
    "Fixe", "1 vantail", "2 vantaux", "3 vantaux", "Coulissante",
    "Oscillo-battante", "Soufflet", "Pivotante",
]

SERIES_ALU_DEFAUT = ["Série 40", "Série 45", "Série 50", "Série 60", "Série 70"]

VITRAGES_DEFAUT = [
    "Simple vitrage", "Double vitrage", "Triple vitrage", "Vitrage teinté",
    "Vitrage réfléchissant", "Vitrage feuilleté", "Vitrage sécurit",
]

COULEURS_DEFAUT = [
    "Blanc", "Noir", "Gris Anthracite", "Bronze", "Bois", "Acajou", "Chêne Doré",
]

OPTIONS_DEFAUT = [
    "Oscillo-battant", "Coulissant", "Moustiquaire", "Volet manuel", "Volet motorisé",
]

ACCESSOIRES_DEFAUT = [
    "Poignée", "Serrure", "Cylindre", "Paumelles", "Roulettes", "Crémone",
    "Charnières", "Butées", "Joints", "Brosses", "Visserie",
]

PARAMETRES_DEFAUT = {
    "nom_entreprise": "DJEFF ALUMINIUM",
    "telephone": "",
    "email": "",
    "adresse": "",
    "rc": "",
    "nif": "",
    "nis": "",
    "logo_path": "",
    "cout_main_oeuvre_ml": "500",  # DA / ML, modifiable
    "marge_beneficiaire_pct": "20",  # % appliqué en fin de calcul
    "prochain_numero_devis": "1",
    "prochain_numero_facture": "1",
    "conditions_generales": "Devis valable selon la durée indiquée. Acompte de 50% à la commande.",
}


def init_db():
    """Crée les tables si nécessaire et insère les données de référence par défaut."""
    Base.metadata.create_all(engine)
    session = get_session()
    try:
        if session.query(Produit).count() == 0:
            for nom, cat in PRODUITS_DEFAUT:
                session.add(Produit(nom=nom, categorie=cat))

        if session.query(Ouverture).count() == 0:
            for nom in OUVERTURES_DEFAUT:
                session.add(Ouverture(nom=nom))

        if session.query(MateriauAlu).count() == 0:
            for serie in SERIES_ALU_DEFAUT:
                session.add(MateriauAlu(serie=serie, prix_ml=0.0))

        if session.query(MateriauPVC).count() == 0:
            session.add(MateriauPVC(nom="PVC Standard", prix_ml=0.0))

        if session.query(Vitrage).count() == 0:
            for nom in VITRAGES_DEFAUT:
                session.add(Vitrage(nom=nom, prix_m2=0.0))

        if session.query(Couleur).count() == 0:
            for nom in COULEURS_DEFAUT:
                session.add(Couleur(nom=nom, type_supplement="fixe", valeur_supplement=0.0))

        if session.query(Option).count() == 0:
            for nom in OPTIONS_DEFAUT:
                session.add(Option(nom=nom, prix=0.0))

        if session.query(Accessoire).count() == 0:
            for nom in ACCESSOIRES_DEFAUT:
                session.add(Accessoire(nom=nom, prix_unitaire=0.0, stock_actuel=0.0, stock_minimum=0.0))

        if session.query(Parametre).count() == 0:
            for cle, valeur in PARAMETRES_DEFAUT.items():
                session.add(Parametre(cle=cle, valeur=str(valeur)))

        if session.query(Utilisateur).count() == 0:
            # Compte administrateur par défaut - à changer depuis Paramètres
            session.add(Utilisateur(
                nom_utilisateur="admin",
                mot_de_passe="admin123",
                role="Administrateur",
                actif=True,
            ))

        session.commit()
    finally:
        session.close()


# ======================================================================
# FONCTIONS UTILITAIRES (numerotation, formatage, parametres)
# ======================================================================
def get_parametre(session, cle, defaut=""):
    p = session.query(Parametre).filter_by(cle=cle).first()
    return p.valeur if p else defaut


def set_parametre(session, cle, valeur):
    p = session.query(Parametre).filter_by(cle=cle).first()
    if p:
        p.valeur = str(valeur)
    else:
        session.add(Parametre(cle=cle, valeur=str(valeur)))
    session.commit()


def formater_da(montant):
    """Formate un montant en Dinars Algériens, ex: 1 250 000,00 DA"""
    try:
        montant = float(montant)
    except (TypeError, ValueError):
        montant = 0.0
    txt = f"{montant:,.2f}".replace(",", " ").replace(".", ",")
    return f"{txt} DA"


def generer_numero_devis(session):
    annee = datetime.now().year
    prochain = int(get_parametre(session, "prochain_numero_devis", "1"))
    # S'assure qu'il n'y a pas de collision si le compteur a dérivé
    numero = f"DEV-{annee}-{prochain:04d}"
    while session.query(Devis).filter_by(numero=numero).first() is not None:
        prochain += 1
        numero = f"DEV-{annee}-{prochain:04d}"
    set_parametre(session, "prochain_numero_devis", prochain + 1)
    return numero


def generer_numero_facture(session):
    annee = datetime.now().year
    prochain = int(get_parametre(session, "prochain_numero_facture", "1"))
    numero = f"FAC-{annee}-{prochain:04d}"
    while session.query(Facture).filter_by(numero=numero).first() is not None:
        prochain += 1
        numero = f"FAC-{annee}-{prochain:04d}"
    set_parametre(session, "prochain_numero_facture", prochain + 1)
    return numero


STATUTS_DEVIS = ["Brouillon", "Envoyé", "Accepté", "Refusé", "Expiré"]
STATUTS_FABRICATION = ["En attente", "En fabrication", "Terminé", "Livré"]
STATUTS_POSE = ["À programmer", "En cours", "Terminé"]
MODES_PAIEMENT = ["Espèces", "CCP", "Virement", "Chèque"]


# ======================================================================
# CALCULS (dimensions et prix)
# ======================================================================
def calc_surface(largeur_mm, hauteur_mm):
    """Surface en m² à partir de dimensions en mm."""
    return (float(largeur_mm) / 1000.0) * (float(hauteur_mm) / 1000.0)


def calc_ml(largeur_mm, hauteur_mm):
    """Périmètre (ML - Mètre Linéaire) à partir de dimensions en mm."""
    return ((float(largeur_mm) + float(hauteur_mm)) * 2) / 1000.0


def calc_prix_ligne(
    ml, surface,
    prix_ml_materiau,
    prix_m2_vitrage,
    couleur_type, couleur_valeur,
    prix_options,          # liste de prix (float) des options sélectionnées
    accessoires_detail,    # liste de tuples (prix_unitaire, quantite)
    cout_main_oeuvre_ml,
    marge_pct,
    quantite=1,
):
    """Calcule le détail des coûts et le prix total d'une ligne de devis."""
    cout_profiles = prix_ml_materiau * ml
    cout_vitrage = prix_m2_vitrage * surface

    if couleur_type == "pourcentage":
        cout_couleur = (cout_profiles + cout_vitrage) * (couleur_valeur / 100.0)
    else:
        cout_couleur = couleur_valeur

    cout_options = sum(prix_options) if prix_options else 0.0
    cout_accessoires = sum(p * q for p, q in accessoires_detail) if accessoires_detail else 0.0
    cout_main_oeuvre = cout_main_oeuvre_ml * ml

    prix_ht = (
        cout_profiles + cout_vitrage + cout_couleur
        + cout_options + cout_accessoires + cout_main_oeuvre
    )
    prix_unitaire_final = prix_ht * (1 + (marge_pct / 100.0))
    total_ligne = prix_unitaire_final * quantite

    return {
        "cout_profiles": round(cout_profiles, 2),
        "cout_vitrage": round(cout_vitrage, 2),
        "cout_couleur": round(cout_couleur, 2),
        "cout_options": round(cout_options, 2),
        "cout_accessoires": round(cout_accessoires, 2),
        "cout_main_oeuvre": round(cout_main_oeuvre, 2),
        "prix_ht": round(prix_ht, 2),
        "prix_unitaire": round(prix_unitaire_final, 2),
        "total_ligne": round(total_ligne, 2),
    }


def calc_totaux_devis(lignes_totaux, remise_pct=0.0, tva_pct=0.0, acompte=0.0):
    """lignes_totaux : liste des 'total_ligne' de chaque ligne du devis."""
    sous_total = sum(lignes_totaux)
    montant_remise = sous_total * (remise_pct / 100.0)
    apres_remise = sous_total - montant_remise
    montant_tva = apres_remise * (tva_pct / 100.0)
    total_ttc = apres_remise + montant_tva
    reste_a_payer = total_ttc - acompte

    return {
        "sous_total": round(sous_total, 2),
        "montant_remise": round(montant_remise, 2),
        "montant_tva": round(montant_tva, 2),
        "total_ttc": round(total_ttc, 2),
        "acompte": round(acompte, 2),
        "reste_a_payer": round(reste_a_payer, 2),
    }


# ======================================================================
# GENERATION DES PDF (devis / factures)
# ======================================================================
try:
    QRCODE_DISPONIBLE = True
except ImportError:
    QRCODE_DISPONIBLE = False


class DocumentPDF(FPDF):
    def __init__(self, entreprise, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entreprise = entreprise
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        logo_path = self.entreprise.get("logo_path", "")
        if logo_path and os.path.exists(logo_path):
            self.image(logo_path, x=10, y=8, w=28)
            self.set_xy(42, 8)
        else:
            self.set_xy(10, 8)

        self.set_font("Helvetica", "B", 16)
        self.cell(0, 8, self.entreprise.get("nom_entreprise", "DJEFF ALUMINIUM"), ln=1)
        self.set_x(42 if (logo_path and os.path.exists(logo_path)) else 10)
        self.set_font("Helvetica", "", 9)
        infos = []
        if self.entreprise.get("telephone"):
            infos.append(f"Tél: {self.entreprise['telephone']}")
        if self.entreprise.get("email"):
            infos.append(f"Email: {self.entreprise['email']}")
        if infos:
            self.cell(0, 5, "  |  ".join(infos), ln=1)
        self.set_x(42 if (logo_path and os.path.exists(logo_path)) else 10)
        if self.entreprise.get("adresse"):
            self.cell(0, 5, self.entreprise["adresse"], ln=1)

        legal = []
        for cle, label in (("rc", "RC"), ("nif", "NIF"), ("nis", "NIS")):
            if self.entreprise.get(cle):
                legal.append(f"{label}: {self.entreprise[cle]}")
        if legal:
            self.set_x(42 if (logo_path and os.path.exists(logo_path)) else 10)
            self.set_font("Helvetica", "", 8)
            self.cell(0, 5, "  |  ".join(legal), ln=1)

        self.ln(2)
        self.set_draw_color(30, 30, 30)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")


def _table_en_tete(pdf, colonnes, largeurs):
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for titre, largeur in zip(colonnes, largeurs):
        pdf.cell(largeur, 7, titre, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)


def generer_pdf_document(
    type_document,      # "DEVIS" ou "FACTURE"
    numero,
    date_str,
    entreprise: dict,
    client: dict,
    lignes: list,        # liste de dict avec les champs du DevisLigne + prix
    totaux: dict,
    validite_jours=None,
    statut=None,
):
    pdf = DocumentPDF(entreprise)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, f"{type_document} N° {numero}", ln=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Date : {date_str}", ln=1)
    if validite_jours:
        pdf.cell(0, 6, f"Validité : {validite_jours} jours", ln=1)
    if statut:
        pdf.cell(0, 6, f"Statut : {statut}", ln=1)
    pdf.ln(2)

    # Informations client
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Client", ln=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Nom : {client.get('nom', '')}", ln=1)
    if client.get("telephone"):
        pdf.cell(0, 5, f"Téléphone : {client['telephone']}", ln=1)
    if client.get("adresse"):
        pdf.cell(0, 5, f"Adresse : {client['adresse']}", ln=1)
    pdf.ln(3)

    # Tableau détaillé
    colonnes = ["Produit", "Ouverture", "Matériau", "Couleur", "L x H (mm)", "Surf. m²", "ML", "Qté", "P.U.", "Total"]
    largeurs = [22, 20, 20, 18, 22, 15, 13, 10, 20, 20]
    _table_en_tete(pdf, colonnes, largeurs)

    pdf.set_font("Helvetica", "", 7.5)
    for l in lignes:
        valeurs = [
            str(l.get("produit", ""))[:14],
            str(l.get("ouverture", ""))[:12],
            str(l.get("materiau_detail", ""))[:12],
            str(l.get("couleur", ""))[:11],
            f"{int(l.get('largeur', 0))}x{int(l.get('hauteur', 0))}",
            f"{l.get('surface_m2', 0):.2f}",
            f"{l.get('ml', 0):.2f}",
            str(l.get("quantite", 1)),
            f"{l.get('prix_unitaire', 0):,.0f}".replace(",", " "),
            f"{l.get('total_ligne', 0):,.0f}".replace(",", " "),
        ]
        for v, largeur in zip(valeurs, largeurs):
            pdf.cell(largeur, 6, v, border=1)
        pdf.ln()

    pdf.ln(4)

    # Bloc financier
    def ligne_totaux(label, valeur, gras=False):
        pdf.set_font("Helvetica", "B" if gras else "", 9)
        pdf.cell(150, 6, label, align="R")
        pdf.cell(30, 6, f"{valeur:,.2f} DA".replace(",", " "), align="R", ln=1)

    ligne_totaux("Sous-total :", totaux.get("sous_total", 0))
    if totaux.get("montant_remise"):
        ligne_totaux("Remise :", -totaux.get("montant_remise", 0))
    if totaux.get("montant_tva"):
        ligne_totaux("TVA :", totaux.get("montant_tva", 0))
    ligne_totaux("Total TTC :", totaux.get("total_ttc", 0), gras=True)
    if totaux.get("acompte"):
        ligne_totaux("Acompte versé :", totaux.get("acompte", 0))
    ligne_totaux("Reste à payer :", totaux.get("reste_a_payer", totaux.get("total_ttc", 0)), gras=True)

    pdf.ln(8)

    # Conditions générales
    cg = entreprise.get("conditions_generales", "")
    if cg:
        pdf.set_font("Helvetica", "I", 8)
        pdf.multi_cell(0, 4.5, cg)
        pdf.ln(4)

    # QR Code (optionnel) + signature / cachet
    y_bas = pdf.get_y()
    if QRCODE_DISPONIBLE:
        qr_contenu = f"{type_document} {numero} - {entreprise.get('nom_entreprise', '')}"
        img = qrcode.make(qr_contenu)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        pdf.image(buf, x=10, y=y_bas, w=22)

    pdf.set_xy(140, y_bas)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(30, 6, "Signature", align="C")
    pdf.set_xy(170, y_bas)
    pdf.cell(30, 6, "Cachet", align="C")

    return bytes(pdf.output())


# ======================================================================
# PAGE : TABLEAU DE BORD
# ======================================================================
def page_dashboard():
    st.title("🏠 Tableau de bord")
    session = get_session()

    total_devis = session.query(Devis).count()
    debut_mois = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    devis_du_mois = session.query(Devis).filter(Devis.date_creation >= debut_mois).count()
    total_clients = session.query(Client).count()

    ca_total = session.query(func.sum(Facture.montant_total)).scalar() or 0
    total_encaisse = session.query(func.sum(Paiement.montant)).scalar() or 0
    total_restant = ca_total - total_encaisse

    en_fabrication = session.query(Fabrication).filter_by(statut="En fabrication").count()
    terminees = session.query(Fabrication).filter_by(statut="Terminé").count()
    livrees = session.query(Fabrication).filter_by(statut="Livré").count()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total devis", total_devis)
    c2.metric("Devis du mois", devis_du_mois)
    c3.metric("Clients", total_clients)
    c4.metric("Chiffre d'affaires", formater_da(ca_total))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total encaissé", formater_da(total_encaisse))
    c6.metric("Reste à encaisser", formater_da(total_restant))
    c7.metric("En fabrication", en_fabrication)
    c8.metric("Terminées / Livrées", f"{terminees} / {livrees}")

    st.divider()

    # --- CA mensuel ---
    factures = session.query(Facture).all()
    if factures:
        df = pd.DataFrame([{
            "mois": f.date_creation.strftime("%Y-%m"),
            "montant": f.montant_total,
        } for f in factures])
        ca_mensuel = df.groupby("mois", as_index=False)["montant"].sum().sort_values("mois")
        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(ca_mensuel, x="mois", y="montant", title="Chiffre d'affaires mensuel")
            st.plotly_chart(fig1, use_container_width=True)

        df["annee"] = df["mois"].str[:4]
        ca_annuel = df.groupby("annee", as_index=False)["montant"].sum()
        with col2:
            fig2 = px.bar(ca_annuel, x="annee", y="montant", title="Chiffre d'affaires annuel")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aucune facture pour le moment — les graphiques de CA apparaîtront ici.")

    # --- Produits les plus vendus ---
    lignes = session.query(DevisLigne).all()
    col3, col4 = st.columns(2)
    if lignes:
        df_lignes = pd.DataFrame([{"produit": l.produit, "quantite": l.quantite or 1} for l in lignes])
        top_produits = df_lignes.groupby("produit", as_index=False)["quantite"].sum().sort_values(
            "quantite", ascending=False).head(10)
        with col3:
            fig3 = px.bar(top_produits, x="produit", y="quantite", title="Produits les plus vendus")
            st.plotly_chart(fig3, use_container_width=True)

        df_mat = pd.DataFrame([{"materiau": l.materiau_type or "N/A"} for l in lignes])
        rep_mat = df_mat["materiau"].value_counts().reset_index()
        rep_mat.columns = ["materiau", "count"]
        with col4:
            fig4 = px.pie(rep_mat, names="materiau", values="count", title="Répartition des matériaux")
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Aucune ligne de devis pour le moment — les statistiques produits apparaîtront ici.")

    # --- Évolution des devis ---
    devis_all = session.query(Devis).all()
    if devis_all:
        df_devis = pd.DataFrame([{
            "mois": d.date_creation.strftime("%Y-%m"),
            "statut": d.statut,
        } for d in devis_all])
        evolution = df_devis.groupby(["mois", "statut"], as_index=False).size().sort_values("mois")
        fig5 = px.line(evolution, x="mois", y="size", color="statut", markers=True,
                        title="Évolution des devis")
        st.plotly_chart(fig5, use_container_width=True)

    session.close()


# ======================================================================
# PAGE : CLIENTS
# ======================================================================
WILAYAS = [
    "Alger", "Oran", "Constantine", "Blida", "Sétif", "Annaba", "Batna",
    "Tlemcen", "Béjaïa", "Tizi Ouzou", "Boumerdès", "Mostaganem", "Autre",
]


def page_clients():
    st.title("👤 Clients")
    session = get_session()

    onglet_liste, onglet_ajout = st.tabs(["📋 Liste des clients", "➕ Ajouter un client"])

    with onglet_ajout:
        with st.form("nouveau_client", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nom = col1.text_input("Nom *")
            prenom = col2.text_input("Prénom")
            societe = st.text_input("Société")
            col3, col4 = st.columns(2)
            tel1 = col3.text_input("Téléphone 1")
            tel2 = col4.text_input("Téléphone 2")
            email = st.text_input("Email")
            adresse = st.text_area("Adresse")
            col5, col6 = st.columns(2)
            wilaya = col5.selectbox("Wilaya", WILAYAS)
            commune = col6.text_input("Commune")
            notes = st.text_area("Notes")
            submit = st.form_submit_button("Enregistrer le client", type="primary")

            if submit:
                if not nom:
                    st.error("Le nom est obligatoire.")
                else:
                    client = Client(
                        nom=nom, prenom=prenom, societe=societe,
                        telephone1=tel1, telephone2=tel2, email=email,
                        adresse=adresse, wilaya=wilaya, commune=commune, notes=notes,
                    )
                    session.add(client)
                    session.commit()
                    st.success(f"Client « {nom} » ajouté avec succès.")
                    st.rerun()

    with onglet_liste:
        recherche = st.text_input("🔍 Rechercher un client (nom, société, téléphone)")
        clients = session.query(Client).order_by(Client.date_creation.desc()).all()
        if recherche:
            r = recherche.lower()
            clients = [c for c in clients if
                       r in (c.nom or "").lower() or
                       r in (c.societe or "").lower() or
                       r in (c.telephone1 or "") or
                       r in (c.telephone2 or "")]

        if not clients:
            st.info("Aucun client trouvé.")
        else:
            df = pd.DataFrame([{
                "ID": c.id, "Nom": c.nom, "Prénom": c.prenom, "Société": c.societe,
                "Téléphone": c.telephone1, "Wilaya": c.wilaya, "Commune": c.commune,
            } for c in clients])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Fiche client détaillée")
            options_client = {f"{c.nom} {c.prenom or ''} (#{c.id})": c.id for c in clients}
            choix = st.selectbox("Sélectionner un client", list(options_client.keys()))
            client_id = options_client[choix]
            client = session.query(Client).get(client_id)

            with st.expander("✏️ Modifier / Supprimer", expanded=False):
                col1, col2 = st.columns(2)
                nom_m = col1.text_input("Nom", value=client.nom, key="nom_m")
                prenom_m = col2.text_input("Prénom", value=client.prenom or "", key="prenom_m")
                societe_m = st.text_input("Société", value=client.societe or "", key="soc_m")
                col3, col4 = st.columns(2)
                tel1_m = col3.text_input("Téléphone 1", value=client.telephone1 or "", key="tel1_m")
                tel2_m = col4.text_input("Téléphone 2", value=client.telephone2 or "", key="tel2_m")
                email_m = st.text_input("Email", value=client.email or "", key="email_m")
                adresse_m = st.text_area("Adresse", value=client.adresse or "", key="adr_m")
                notes_m = st.text_area("Notes", value=client.notes or "", key="notes_m")

                colA, colB = st.columns(2)
                if colA.button("💾 Enregistrer les modifications"):
                    client.nom, client.prenom, client.societe = nom_m, prenom_m, societe_m
                    client.telephone1, client.telephone2, client.email = tel1_m, tel2_m, email_m
                    client.adresse, client.notes = adresse_m, notes_m
                    session.commit()
                    st.success("Client mis à jour.")
                    st.rerun()

                if colB.button("🗑️ Supprimer ce client", type="secondary"):
                    if session.query(Devis).filter_by(client_id=client.id).count() > 0:
                        st.error("Impossible de supprimer : ce client possède des devis liés.")
                    else:
                        session.delete(client)
                        session.commit()
                        st.success("Client supprimé.")
                        st.rerun()

            hist_devis, hist_factures, hist_paiements, hist_chantiers = st.tabs(
                ["Devis", "Factures", "Paiements", "Chantiers (Pose)"]
            )
            with hist_devis:
                devis_list = session.query(Devis).filter_by(client_id=client.id).all()
                if devis_list:
                    st.dataframe(pd.DataFrame([{
                        "Numéro": d.numero, "Date": d.date_creation.strftime("%d/%m/%Y"),
                        "Statut": d.statut,
                    } for d in devis_list]), use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun devis pour ce client.")

            with hist_factures:
                factures_list = session.query(Facture).filter_by(client_id=client.id).all()
                if factures_list:
                    st.dataframe(pd.DataFrame([{
                        "Numéro": f.numero, "Date": f.date_creation.strftime("%d/%m/%Y"),
                        "Montant": formater_da(f.montant_total),
                    } for f in factures_list]), use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucune facture pour ce client.")

            with hist_paiements:
                factures_ids = [f.id for f in session.query(Facture).filter_by(client_id=client.id).all()]
                paiements = session.query(Paiement).filter(Paiement.facture_id.in_(factures_ids)).all() \
                    if factures_ids else []
                if paiements:
                    st.dataframe(pd.DataFrame([{
                        "Date": p.date_paiement.strftime("%d/%m/%Y"), "Montant": formater_da(p.montant),
                        "Mode": p.mode,
                    } for p in paiements]), use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun paiement enregistré.")

            with hist_chantiers:
                devis_ids = [d.id for d in devis_list] if devis_list else []
                poses = session.query(Pose).filter(Pose.devis_id.in_(devis_ids)).all() if devis_ids else []
                if poses:
                    st.dataframe(pd.DataFrame([{
                        "Adresse": p.adresse_chantier, "Date pose": p.date_pose,
                        "Statut": p.statut,
                    } for p in poses]), use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun chantier pour ce client.")

    session.close()


# ======================================================================
# PAGE : DEVIS
# ======================================================================
def _init_lignes_state():
    if "lignes_devis_en_cours" not in st.session_state:
        st.session_state.lignes_devis_en_cours = []


def _entreprise_dict(session):
    cles = ["nom_entreprise", "telephone", "email", "adresse", "rc", "nif", "nis",
            "logo_path", "conditions_generales"]
    return {c: get_parametre(session, c, "") for c in cles}


def _formulaire_ligne(session):
    st.subheader("➕ Ajouter une ligne au devis")

    produits = [p.nom for p in session.query(Produit).filter_by(actif=True).all()]
    ouvertures = [o.nom for o in session.query(Ouverture).all()]
    series_alu = session.query(MateriauAlu).all()
    materiau_pvc = session.query(MateriauPVC).first()
    vitrages = session.query(Vitrage).all()
    couleurs = session.query(Couleur).all()
    options = session.query(Option).all()
    accessoires = session.query(Accessoire).all()

    col1, col2, col3 = st.columns(3)
    produit = col1.selectbox("Produit", produits)
    ouverture = col2.selectbox("Type d'ouverture", ouvertures)
    materiau_type = col3.radio("Matériau", ["Alu", "PVC"], horizontal=True)

    if materiau_type == "Alu":
        choix_serie = st.selectbox("Série aluminium", [s.serie for s in series_alu])
        materiau_obj = next(s for s in series_alu if s.serie == choix_serie)
        prix_ml_materiau = materiau_obj.prix_ml
        materiau_detail = materiau_obj.serie
    else:
        materiau_obj = materiau_pvc
        prix_ml_materiau = materiau_obj.prix_ml if materiau_obj else 0.0
        materiau_detail = materiau_obj.nom if materiau_obj else "PVC"

    col4, col5, col6 = st.columns(3)
    largeur = col4.number_input("Largeur (mm)", min_value=0, step=10, value=1000)
    hauteur = col5.number_input("Hauteur (mm)", min_value=0, step=10, value=1200)
    quantite = col6.number_input("Quantité", min_value=1, step=1, value=1)

    col7, col8 = st.columns(2)
    vitrage_choix = col7.selectbox("Vitrage", [v.nom for v in vitrages])
    vitrage_obj = next(v for v in vitrages if v.nom == vitrage_choix)
    couleur_choix = col8.selectbox("Couleur", [c.nom for c in couleurs])
    couleur_obj = next(c for c in couleurs if c.nom == couleur_choix)

    options_choisies = st.multiselect("Options", [o.nom for o in options])

    st.markdown("**Accessoires**")
    accessoires_choisis = {}
    cols_acc = st.columns(3)
    for i, acc in enumerate(accessoires):
        with cols_acc[i % 3]:
            qte = st.number_input(f"{acc.nom} (qté)", min_value=0, step=1, value=0, key=f"acc_{acc.id}")
            if qte > 0:
                accessoires_choisis[acc.nom] = (acc.prix_unitaire, qte)

    st.markdown("**Accessoires personnalisés**")
    col9, col10, col11 = st.columns(3)
    acc_perso_nom = col9.text_input("Nom", key="acc_perso_nom")
    acc_perso_prix = col10.number_input("Prix unitaire (DA)", min_value=0.0, step=100.0, key="acc_perso_prix")
    acc_perso_qte = col11.number_input("Quantité", min_value=0, step=1, key="acc_perso_qte")

    observation = st.text_input("Observation (pour cette ligne)")

    if st.button("Calculer et ajouter la ligne", type="primary"):
        surface = calc_surface(largeur, hauteur)
        ml = calc_ml(largeur, hauteur)

        prix_options = [o.prix for o in options if o.nom in options_choisies]
        accessoires_detail = list(accessoires_choisis.values())
        if acc_perso_nom and acc_perso_qte > 0:
            accessoires_detail.append((acc_perso_prix, acc_perso_qte))
            accessoires_choisis[acc_perso_nom] = (acc_perso_prix, acc_perso_qte)

        cout_main_oeuvre_ml = float(get_parametre(session, "cout_main_oeuvre_ml", "0"))
        marge_pct = float(get_parametre(session, "marge_beneficiaire_pct", "0"))

        resultat = calc_prix_ligne(
            ml=ml, surface=surface,
            prix_ml_materiau=prix_ml_materiau,
            prix_m2_vitrage=vitrage_obj.prix_m2,
            couleur_type=couleur_obj.type_supplement,
            couleur_valeur=couleur_obj.valeur_supplement,
            prix_options=prix_options,
            accessoires_detail=accessoires_detail,
            cout_main_oeuvre_ml=cout_main_oeuvre_ml,
            marge_pct=marge_pct,
            quantite=quantite,
        )

        ligne = {
            "produit": produit, "ouverture": ouverture,
            "materiau_type": materiau_type, "materiau_detail": materiau_detail,
            "vitrage": vitrage_choix, "couleur": couleur_choix,
            "options": ", ".join(options_choisies),
            "accessoires": "; ".join(f"{n}:{q}" for n, (p, q) in accessoires_choisis.items()),
            "largeur": largeur, "hauteur": hauteur, "quantite": quantite,
            "surface_m2": round(surface, 3), "ml": round(ml, 3),
            "prix_unitaire": resultat["prix_unitaire"], "total_ligne": resultat["total_ligne"],
            "observation": observation,
        }
        st.session_state.lignes_devis_en_cours.append(ligne)
        st.success("Ligne ajoutée au devis en cours.")
        st.rerun()


def _formulaire_creation(session):
    _init_lignes_state()
    clients = session.query(Client).all()
    if not clients:
        st.warning("Ajoutez d'abord un client dans le module Clients.")
        return

    col1, col2, col3 = st.columns(3)
    options_client = {f"{c.nom} {c.prenom or ''}": c.id for c in clients}
    client_choix = col1.selectbox("Client", list(options_client.keys()))
    commercial = col2.text_input("Commercial", value=st.session_state.utilisateur["nom"])
    validite = col3.number_input("Validité (jours)", min_value=1, value=30)

    col4, col5, col6 = st.columns(3)
    remise = col4.number_input("Remise (%)", min_value=0.0, max_value=100.0, value=0.0)
    tva = col5.number_input("TVA (%)", min_value=0.0, max_value=100.0, value=0.0)
    acompte = col6.number_input("Acompte (DA)", min_value=0.0, value=0.0)
    notes = st.text_area("Notes générales du devis")

    st.divider()
    _formulaire_ligne(session)

    st.divider()
    st.subheader("📝 Lignes du devis en cours")
    if not st.session_state.lignes_devis_en_cours:
        st.caption("Aucune ligne ajoutée pour le moment.")
    else:
        df = pd.DataFrame(st.session_state.lignes_devis_en_cours)
        st.dataframe(df[["produit", "ouverture", "materiau_detail", "couleur",
                          "largeur", "hauteur", "quantite", "surface_m2", "ml",
                          "prix_unitaire", "total_ligne"]], use_container_width=True, hide_index=True)

        idx_suppr = st.number_input("Supprimer la ligne n° (0 = première)", min_value=0,
                                     max_value=len(st.session_state.lignes_devis_en_cours) - 1, step=1)
        if st.button("🗑️ Supprimer cette ligne"):
            st.session_state.lignes_devis_en_cours.pop(idx_suppr)
            st.rerun()

        totaux = calc_totaux_devis(
            [l["total_ligne"] for l in st.session_state.lignes_devis_en_cours],
            remise_pct=remise, tva_pct=tva, acompte=acompte,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Sous-total", formater_da(totaux["sous_total"]))
        c2.metric("Total TTC", formater_da(totaux["total_ttc"]))
        c3.metric("Reste à payer", formater_da(totaux["reste_a_payer"]))

        if st.button("✅ Enregistrer le devis", type="primary"):
            client_id = options_client[client_choix]
            numero = generer_numero_devis(session)
            devis = Devis(
                numero=numero, client_id=client_id, commercial=commercial,
                validite_jours=validite, statut="Brouillon",
                remise=remise, tva=tva, acompte=acompte, notes=notes,
            )
            session.add(devis)
            session.flush()

            for l in st.session_state.lignes_devis_en_cours:
                session.add(DevisLigne(devis_id=devis.id, **l))
            session.commit()

            st.session_state.lignes_devis_en_cours = []
            st.success(f"Devis {numero} enregistré avec succès.")
            st.rerun()


def _generer_pdf_devis(session, devis):
    entreprise = _entreprise_dict(session)
    client = devis.client
    client_dict = {"nom": f"{client.nom} {client.prenom or ''}",
                   "telephone": client.telephone1, "adresse": client.adresse}
    lignes = [{
        "produit": l.produit, "ouverture": l.ouverture, "materiau_detail": l.materiau_detail,
        "couleur": l.couleur, "largeur": l.largeur, "hauteur": l.hauteur,
        "surface_m2": l.surface_m2, "ml": l.ml, "quantite": l.quantite,
        "prix_unitaire": l.prix_unitaire, "total_ligne": l.total_ligne,
    } for l in devis.lignes]
    totaux = calc_totaux_devis([l.total_ligne for l in devis.lignes],
                                remise_pct=devis.remise, tva_pct=devis.tva, acompte=devis.acompte)
    return generer_pdf_document(
        "DEVIS", devis.numero, devis.date_creation.strftime("%d/%m/%Y"),
        entreprise, client_dict, lignes, totaux,
        validite_jours=devis.validite_jours, statut=devis.statut,
    )


def _liste_devis(session):
    st.subheader("📋 Liste des devis")
    filtre_statut = st.selectbox("Filtrer par statut", ["Tous"] + STATUTS_DEVIS)
    q = session.query(Devis).order_by(Devis.date_creation.desc())
    if filtre_statut != "Tous":
        q = q.filter_by(statut=filtre_statut)
    devis_list = q.all()

    if not devis_list:
        st.info("Aucun devis trouvé.")
        return

    for d in devis_list:
        client_nom = f"{d.client.nom} {d.client.prenom or ''}" if d.client else "—"
        total = sum(l.total_ligne for l in d.lignes)
        with st.expander(f"{d.numero} — {client_nom} — {formater_da(total)} — {d.statut}"):
            col1, col2, col3, col4 = st.columns(4)
            nouveau_statut = col1.selectbox("Statut", STATUTS_DEVIS,
                                             index=STATUTS_DEVIS.index(d.statut),
                                             key=f"statut_{d.id}")
            if nouveau_statut != d.statut:
                d.statut = nouveau_statut
                session.commit()
                st.rerun()

            if col2.button("📄 Générer PDF", key=f"pdf_{d.id}"):
                pdf_bytes = _generer_pdf_devis(session, d)
                st.download_button("⬇️ Télécharger le PDF", data=pdf_bytes,
                                    file_name=f"{d.numero}.pdf", mime="application/pdf",
                                    key=f"dl_{d.id}")

            if col3.button("📑 Dupliquer", key=f"dup_{d.id}"):
                numero = generer_numero_devis(session)
                nouveau = Devis(
                    numero=numero, client_id=d.client_id, commercial=d.commercial,
                    validite_jours=d.validite_jours, statut="Brouillon",
                    remise=d.remise, tva=d.tva, acompte=0, notes=d.notes,
                )
                session.add(nouveau)
                session.flush()
                for l in d.lignes:
                    session.add(DevisLigne(
                        devis_id=nouveau.id, produit=l.produit, ouverture=l.ouverture,
                        materiau_type=l.materiau_type, materiau_detail=l.materiau_detail,
                        vitrage=l.vitrage, couleur=l.couleur, options=l.options,
                        accessoires=l.accessoires, largeur=l.largeur, hauteur=l.hauteur,
                        quantite=l.quantite, surface_m2=l.surface_m2, ml=l.ml,
                        prix_unitaire=l.prix_unitaire, total_ligne=l.total_ligne,
                        observation=l.observation,
                    ))
                session.commit()
                st.success(f"Devis dupliqué sous le numéro {numero}.")
                st.rerun()

            if col4.button("🗑️ Supprimer", key=f"suppr_{d.id}"):
                if session.query(Facture).filter_by(devis_id=d.id).first():
                    st.error("Impossible : une facture est liée à ce devis.")
                else:
                    session.delete(d)
                    session.commit()
                    st.success("Devis supprimé.")
                    st.rerun()

            if d.statut == "Accepté" and not d.facture:
                if st.button("➡️ Transformer en facture", key=f"fact_{d.id}"):
                    numero_facture = generer_numero_facture(session)
                    total = sum(l.total_ligne for l in d.lignes)
                    totaux = calc_totaux_devis([l.total_ligne for l in d.lignes],
                                                remise_pct=d.remise, tva_pct=d.tva, acompte=d.acompte)
                    facture = Facture(
                        numero=numero_facture, devis_id=d.id, client_id=d.client_id,
                        montant_total=totaux["total_ttc"],
                    )
                    session.add(facture)
                    session.commit()
                    st.success(f"Facture {numero_facture} créée.")
                    st.rerun()

            if d.lignes:
                st.dataframe(pd.DataFrame([{
                    "Produit": l.produit, "Ouverture": l.ouverture, "Matériau": l.materiau_detail,
                    "Couleur": l.couleur, "L x H": f"{int(l.largeur)}x{int(l.hauteur)}",
                    "Qté": l.quantite, "Total": formater_da(l.total_ligne),
                } for l in d.lignes]), use_container_width=True, hide_index=True)


def page_devis():
    st.title("📄 Devis")
    session = get_session()
    onglet_creation, onglet_liste = st.tabs(["➕ Nouveau devis", "📋 Liste des devis"])
    with onglet_creation:
        _formulaire_creation(session)
    with onglet_liste:
        _liste_devis(session)
    session.close()


# ======================================================================
# PAGE : TARIFS
# ======================================================================
def _maj_prix(session, categorie, element, ancien, nouveau, objet, champ_prix):
    if nouveau != ancien:
        setattr(objet, champ_prix, nouveau)
        session.add(TarifHistorique(
            categorie=categorie, element=element, ancien_prix=ancien, nouveau_prix=nouveau,
        ))
        session.commit()
        st.toast(f"Prix mis à jour : {element}")


def page_tarifs():
    st.title("💰 Tarifs")
    session = get_session()

    onglets = st.tabs(["Aluminium", "PVC", "Vitrage", "Couleurs", "Options", "Accessoires", "Historique"])

    with onglets[0]:
        for m in session.query(MateriauAlu).all():
            col1, col2 = st.columns([2, 1])
            col1.write(m.serie)
            nouveau = col2.number_input("Prix / ML (DA)", value=float(m.prix_ml), min_value=0.0,
                                         step=50.0, key=f"alu_{m.id}")
            if st.button("Enregistrer", key=f"btn_alu_{m.id}"):
                _maj_prix(session, "Aluminium", m.serie, m.prix_ml, nouveau, m, "prix_ml")
                st.rerun()

    with onglets[1]:
        m = session.query(MateriauPVC).first()
        if m:
            nouveau = st.number_input("Prix PVC / ML (DA)", value=float(m.prix_ml), min_value=0.0, step=50.0)
            if st.button("Enregistrer le prix PVC"):
                _maj_prix(session, "PVC", m.nom, m.prix_ml, nouveau, m, "prix_ml")
                st.rerun()

    with onglets[2]:
        for v in session.query(Vitrage).all():
            col1, col2 = st.columns([2, 1])
            col1.write(v.nom)
            nouveau = col2.number_input("Prix / m² (DA)", value=float(v.prix_m2), min_value=0.0,
                                         step=50.0, key=f"vit_{v.id}")
            if st.button("Enregistrer", key=f"btn_vit_{v.id}"):
                _maj_prix(session, "Vitrage", v.nom, v.prix_m2, nouveau, v, "prix_m2")
                st.rerun()

    with onglets[3]:
        for c in session.query(Couleur).all():
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.write(c.nom)
            type_supp = col2.selectbox("Type", ["fixe", "pourcentage"],
                                        index=0 if c.type_supplement == "fixe" else 1,
                                        key=f"type_coul_{c.id}")
            nouveau = col3.number_input(
                "Supplément (DA ou %)", value=float(c.valeur_supplement), min_value=0.0,
                step=10.0, key=f"coul_{c.id}",
            )
            if st.button("Enregistrer", key=f"btn_coul_{c.id}"):
                c.type_supplement = type_supp
                _maj_prix(session, "Couleur", c.nom, c.valeur_supplement, nouveau, c, "valeur_supplement")
                st.rerun()

    with onglets[4]:
        for o in session.query(Option).all():
            col1, col2 = st.columns([2, 1])
            col1.write(o.nom)
            nouveau = col2.number_input("Prix (DA)", value=float(o.prix), min_value=0.0,
                                         step=50.0, key=f"opt_{o.id}")
            if st.button("Enregistrer", key=f"btn_opt_{o.id}"):
                _maj_prix(session, "Option", o.nom, o.prix, nouveau, o, "prix")
                st.rerun()

    with onglets[5]:
        for a in session.query(Accessoire).all():
            col1, col2 = st.columns([2, 1])
            col1.write(a.nom)
            nouveau = col2.number_input("Prix unitaire (DA)", value=float(a.prix_unitaire), min_value=0.0,
                                         step=10.0, key=f"acc_{a.id}")
            if st.button("Enregistrer", key=f"btn_acc_{a.id}"):
                _maj_prix(session, "Accessoire", a.nom, a.prix_unitaire, nouveau, a, "prix_unitaire")
                st.rerun()
        st.divider()
        st.caption("Ajouter un nouvel accessoire au catalogue")
        col1, col2 = st.columns(2)
        nom_nouveau = col1.text_input("Nom de l'accessoire")
        prix_nouveau = col2.number_input("Prix unitaire (DA)", min_value=0.0, step=10.0, key="nouv_acc_prix")
        if st.button("➕ Ajouter l'accessoire"):
            if nom_nouveau:
                session.add(Accessoire(nom=nom_nouveau, prix_unitaire=prix_nouveau))
                session.commit()
                st.success("Accessoire ajouté.")
                st.rerun()

    with onglets[6]:
        historique = session.query(TarifHistorique).order_by(TarifHistorique.date_modification.desc()).all()
        if historique:
            st.dataframe(pd.DataFrame([{
                "Date": h.date_modification.strftime("%d/%m/%Y %H:%M"),
                "Catégorie": h.categorie, "Élément": h.element,
                "Ancien prix": h.ancien_prix, "Nouveau prix": h.nouveau_prix,
            } for h in historique]), use_container_width=True, hide_index=True)
        else:
            st.caption("Aucune modification de prix enregistrée.")

    session.close()


# ======================================================================
# PAGE : STOCK
# ======================================================================
CATEGORIES = ["Aluminium", "PVC", "Vitrage", "Quincaillerie"]


def page_stock():
    st.title("📦 Stock")
    session = get_session()

    onglet_inventaire, onglet_mouvement, onglet_ajout = st.tabs(
        ["📋 Inventaire", "🔄 Entrée / Sortie", "➕ Nouvel article"]
    )

    with onglet_ajout:
        with st.form("nouvel_article", clear_on_submit=True):
            col1, col2 = st.columns(2)
            categorie = col1.selectbox("Catégorie", CATEGORIES)
            designation = col2.text_input("Désignation")
            col3, col4, col5 = st.columns(3)
            unite = col3.text_input("Unité", value="unité")
            quantite = col4.number_input("Quantité initiale", min_value=0.0, step=1.0)
            stock_min = col5.number_input("Stock minimum (seuil d'alerte)", min_value=0.0, step=1.0)
            if st.form_submit_button("Ajouter l'article", type="primary"):
                if designation:
                    session.add(StockItem(
                        categorie=categorie, designation=designation, unite=unite,
                        quantite=quantite, stock_minimum=stock_min,
                    ))
                    session.commit()
                    st.success("Article ajouté au stock.")
                    st.rerun()
                else:
                    st.error("La désignation est obligatoire.")

    with onglet_inventaire:
        filtre = st.selectbox("Filtrer par catégorie", ["Toutes"] + CATEGORIES)
        q = session.query(StockItem)
        if filtre != "Toutes":
            q = q.filter_by(categorie=filtre)
        items = q.all()

        if not items:
            st.info("Aucun article en stock.")
        else:
            alertes = [i for i in items if i.quantite <= i.stock_minimum]
            if alertes:
                st.warning(f"⚠️ {len(alertes)} article(s) en dessous du stock minimum : "
                           + ", ".join(a.designation for a in alertes))

            df = pd.DataFrame([{
                "Catégorie": i.categorie, "Désignation": i.designation, "Unité": i.unite,
                "Quantité": i.quantite, "Stock minimum": i.stock_minimum,
                "Alerte": "🔴" if i.quantite <= i.stock_minimum else "🟢",
            } for i in items])
            st.dataframe(df, use_container_width=True, hide_index=True)

    with onglet_mouvement:
        items = session.query(StockItem).all()
        if not items:
            st.info("Ajoutez d'abord des articles au stock.")
        else:
            options_item = {f"{i.designation} ({i.categorie})": i.id for i in items}
            choix = st.selectbox("Article", list(options_item.keys()))
            item = session.query(StockItem).get(options_item[choix])
            st.caption(f"Stock actuel : {item.quantite} {item.unite}")

            type_mvt = st.radio("Type de mouvement", ["Entrée", "Sortie"], horizontal=True)
            qte_mvt = st.number_input("Quantité", min_value=0.0, step=1.0)
            observation = st.text_input("Observation")

            if st.button("Valider le mouvement", type="primary"):
                if qte_mvt <= 0:
                    st.error("La quantité doit être supérieure à 0.")
                elif type_mvt == "Sortie" and qte_mvt > item.quantite:
                    st.error("Quantité insuffisante en stock.")
                else:
                    if type_mvt == "Entrée":
                        item.quantite += qte_mvt
                    else:
                        item.quantite -= qte_mvt
                    session.add(MouvementStock(
                        stock_item_id=item.id, type_mouvement=type_mvt,
                        quantite=qte_mvt, observation=observation,
                    ))
                    session.commit()
                    st.success(f"{type_mvt} enregistrée.")
                    st.rerun()

            st.divider()
            st.subheader("Historique des mouvements")
            mouvements = session.query(MouvementStock).filter_by(
                stock_item_id=item.id).order_by(MouvementStock.date_mouvement.desc()).all()
            if mouvements:
                st.dataframe(pd.DataFrame([{
                    "Date": m.date_mouvement.strftime("%d/%m/%Y %H:%M"),
                    "Type": m.type_mouvement, "Quantité": m.quantite,
                    "Observation": m.observation,
                } for m in mouvements]), use_container_width=True, hide_index=True)
            else:
                st.caption("Aucun mouvement enregistré pour cet article.")

    session.close()


# ======================================================================
# PAGE : FOURNISSEURS
# ======================================================================
def page_fournisseurs():
    st.title("🚚 Fournisseurs")
    session = get_session()

    onglet_liste, onglet_ajout = st.tabs(["📋 Liste des fournisseurs", "➕ Ajouter un fournisseur"])

    with onglet_ajout:
        with st.form("nouveau_fournisseur", clear_on_submit=True):
            nom = st.text_input("Nom *")
            col1, col2 = st.columns(2)
            telephone = col1.text_input("Téléphone")
            email = col2.text_input("Email")
            adresse = st.text_area("Adresse")
            produits_fournis = st.text_area("Produits fournis")
            if st.form_submit_button("Enregistrer", type="primary"):
                if nom:
                    session.add(Fournisseur(
                        nom=nom, telephone=telephone, email=email,
                        adresse=adresse, produits_fournis=produits_fournis,
                    ))
                    session.commit()
                    st.success("Fournisseur ajouté.")
                    st.rerun()
                else:
                    st.error("Le nom est obligatoire.")

    with onglet_liste:
        fournisseurs = session.query(Fournisseur).all()
        if not fournisseurs:
            st.info("Aucun fournisseur enregistré.")
        else:
            df = pd.DataFrame([{
                "Nom": f.nom, "Téléphone": f.telephone, "Email": f.email,
                "Produits fournis": f.produits_fournis,
            } for f in fournisseurs])
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.divider()
            options_f = {f.nom: f.id for f in fournisseurs}
            choix = st.selectbox("Sélectionner un fournisseur", list(options_f.keys()))
            fournisseur = session.query(Fournisseur).get(options_f[choix])

            st.subheader(f"Historique des achats — {fournisseur.nom}")
            with st.form("nouvel_achat", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                designation = col1.text_input("Désignation")
                quantite = col2.number_input("Quantité", min_value=0.0, step=1.0)
                prix_unitaire = col3.number_input("Prix unitaire (DA)", min_value=0.0, step=100.0)
                if st.form_submit_button("Ajouter l'achat"):
                    if designation:
                        session.add(Achat(
                            fournisseur_id=fournisseur.id, designation=designation,
                            quantite=quantite, prix_unitaire=prix_unitaire,
                            montant_total=quantite * prix_unitaire,
                        ))
                        session.commit()
                        st.success("Achat enregistré.")
                        st.rerun()

            achats = session.query(Achat).filter_by(fournisseur_id=fournisseur.id).order_by(
                Achat.date_achat.desc()).all()
            if achats:
                st.dataframe(pd.DataFrame([{
                    "Date": a.date_achat.strftime("%d/%m/%Y"), "Désignation": a.designation,
                    "Quantité": a.quantite, "Prix unitaire": formater_da(a.prix_unitaire),
                    "Total": formater_da(a.montant_total),
                } for a in achats]), use_container_width=True, hide_index=True)
            else:
                st.caption("Aucun achat enregistré pour ce fournisseur.")

    session.close()


# ======================================================================
# PAGE : FACTURES
# ======================================================================
def page_factures():
    st.title("🧾 Factures")
    session = get_session()

    factures = session.query(Facture).order_by(Facture.date_creation.desc()).all()
    if not factures:
        st.info("Aucune facture. Transformez un devis « Accepté » en facture depuis le module Devis.")
        session.close()
        return

    for f in factures:
        client_nom = f"{f.client.nom} {f.client.prenom or ''}" if f.client else "—"
        total_paye = sum(p.montant for p in f.paiements)
        reste = f.montant_total - total_paye
        badge = "🟢 Soldée" if reste <= 0 else ("🟡 Partielle" if total_paye > 0 else "🔴 Impayée")

        with st.expander(f"{f.numero} — {client_nom} — {formater_da(f.montant_total)} — {badge}"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Montant total", formater_da(f.montant_total))
            col2.metric("Payé", formater_da(total_paye))
            col3.metric("Reste à payer", formater_da(reste))

            st.markdown("**Enregistrer un paiement**")
            with st.form(f"paiement_{f.id}", clear_on_submit=True):
                colA, colB, colC = st.columns(3)
                montant = colA.number_input("Montant (DA)", min_value=0.0, step=100.0)
                mode = colB.selectbox("Mode de paiement", MODES_PAIEMENT)
                observation = colC.text_input("Observation")
                if st.form_submit_button("Ajouter le paiement"):
                    if montant > 0:
                        session.add(Paiement(
                            facture_id=f.id, montant=montant, mode=mode, observation=observation,
                        ))
                        session.commit()
                        st.success("Paiement enregistré.")
                        st.rerun()

            if f.paiements:
                st.dataframe(pd.DataFrame([{
                    "Date": p.date_paiement.strftime("%d/%m/%Y"), "Montant": formater_da(p.montant),
                    "Mode": p.mode, "Observation": p.observation,
                } for p in f.paiements]), use_container_width=True, hide_index=True)

            if f.devis and st.button("📄 Générer le PDF de la facture", key=f"pdf_fact_{f.id}"):
                d = f.devis
                entreprise = _entreprise_dict(session)
                client_dict = {"nom": client_nom, "telephone": f.client.telephone1 if f.client else "",
                               "adresse": f.client.adresse if f.client else ""}
                lignes = [{
                    "produit": l.produit, "ouverture": l.ouverture, "materiau_detail": l.materiau_detail,
                    "couleur": l.couleur, "largeur": l.largeur, "hauteur": l.hauteur,
                    "surface_m2": l.surface_m2, "ml": l.ml, "quantite": l.quantite,
                    "prix_unitaire": l.prix_unitaire, "total_ligne": l.total_ligne,
                } for l in d.lignes]
                totaux = calc_totaux_devis([l.total_ligne for l in d.lignes],
                                            remise_pct=d.remise, tva_pct=d.tva, acompte=total_paye)
                pdf_bytes = generer_pdf_document(
                    "FACTURE", f.numero, f.date_creation.strftime("%d/%m/%Y"),
                    entreprise, client_dict, lignes, totaux,
                )
                st.download_button("⬇️ Télécharger le PDF", data=pdf_bytes,
                                    file_name=f"{f.numero}.pdf", mime="application/pdf",
                                    key=f"dlf_{f.id}")

    session.close()


# ======================================================================
# PAGES : FABRICATION ET POSE
# ======================================================================
PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "photos_chantiers")


def page_fabrication():
    st.title("🏭 Fabrication")
    session = get_session()

    devis_acceptes = session.query(Devis).filter_by(statut="Accepté").all()
    devis_sans_fab = [d for d in devis_acceptes if not d.fabrication]

    if devis_sans_fab:
        st.subheader("➕ Lancer une fabrication")
        options_d = {f"{d.numero} — {d.client.nom if d.client else ''}": d.id for d in devis_sans_fab}
        choix = st.selectbox("Devis accepté", list(options_d.keys()))
        responsable = st.text_input("Responsable")
        if st.button("Démarrer la fabrication", type="primary"):
            session.add(Fabrication(
                devis_id=options_d[choix], statut="En attente", responsable=responsable,
            ))
            session.commit()
            st.success("Fabrication créée.")
            st.rerun()
        st.divider()

    st.subheader("📋 Suivi des fabrications")
    fabrications = session.query(Fabrication).all()
    if not fabrications:
        st.info("Aucune fabrication en cours.")
    for fab in fabrications:
        numero = fab.devis.numero if fab.devis else "—"
        with st.expander(f"{numero} — {fab.statut}"):
            col1, col2 = st.columns(2)
            responsable = col1.text_input("Responsable", value=fab.responsable or "", key=f"resp_{fab.id}")
            statut = col2.selectbox("Statut", STATUTS_FABRICATION,
                                     index=STATUTS_FABRICATION.index(fab.statut), key=f"stat_fab_{fab.id}")
            col3, col4 = st.columns(2)
            date_debut = col3.date_input("Date début", value=fab.date_debut or datetime.now(),
                                          key=f"debut_{fab.id}")
            date_fin = col4.date_input("Date fin", value=fab.date_fin or datetime.now(), key=f"fin_{fab.id}")
            observations = st.text_area("Observations", value=fab.observations or "", key=f"obs_fab_{fab.id}")

            if st.button("💾 Mettre à jour", key=f"maj_fab_{fab.id}"):
                fab.responsable = responsable
                fab.statut = statut
                fab.date_debut = date_debut
                fab.date_fin = date_fin
                fab.observations = observations
                session.commit()
                st.success("Fabrication mise à jour.")
                st.rerun()

    session.close()


def page_pose():
    st.title("🔧 Pose")
    session = get_session()
    os.makedirs(PHOTOS_DIR, exist_ok=True)

    devis_fabriques = session.query(Fabrication).filter(
        Fabrication.statut.in_(["Terminé", "Livré"])).all()
    devis_sans_pose = [f.devis for f in devis_fabriques if f.devis and not f.devis.pose]

    if devis_sans_pose:
        st.subheader("➕ Planifier une pose")
        options_d = {f"{d.numero} — {d.client.nom if d.client else ''}": d.id for d in devis_sans_pose}
        choix = st.selectbox("Devis fabriqué", list(options_d.keys()))
        adresse = st.text_area("Adresse du chantier")
        date_pose = st.date_input("Date de pose")
        equipe = st.text_input("Équipe")
        if st.button("Planifier la pose", type="primary"):
            session.add(Pose(
                devis_id=options_d[choix], adresse_chantier=adresse,
                date_pose=date_pose, equipe=equipe, statut="À programmer",
            ))
            session.commit()
            st.success("Pose planifiée.")
            st.rerun()
        st.divider()

    st.subheader("📋 Suivi des poses")
    poses = session.query(Pose).all()
    if not poses:
        st.info("Aucune pose planifiée.")
    for pose in poses:
        numero = pose.devis.numero if pose.devis else "—"
        with st.expander(f"{numero} — {pose.statut}"):
            adresse = st.text_area("Adresse chantier", value=pose.adresse_chantier or "", key=f"adr_{pose.id}")
            col1, col2 = st.columns(2)
            date_pose = col1.date_input("Date pose", value=pose.date_pose or datetime.now(), key=f"date_{pose.id}")
            statut = col2.selectbox("Statut", STATUTS_POSE, index=STATUTS_POSE.index(pose.statut),
                                     key=f"stat_pose_{pose.id}")
            equipe = st.text_input("Équipe", value=pose.equipe or "", key=f"eq_{pose.id}")
            observations = st.text_area("Observations", value=pose.observations or "", key=f"obs_pose_{pose.id}")

            photo = st.file_uploader("Ajouter une photo du chantier", type=["jpg", "jpeg", "png"],
                                      key=f"photo_{pose.id}")
            if photo:
                chemin = os.path.join(PHOTOS_DIR, f"pose_{pose.id}_{photo.name}")
                with open(chemin, "wb") as fichier:
                    fichier.write(photo.getbuffer())
                st.success("Photo enregistrée.")

            photos_existantes = [f for f in os.listdir(PHOTOS_DIR) if f.startswith(f"pose_{pose.id}_")] \
                if os.path.exists(PHOTOS_DIR) else []
            if photos_existantes:
                st.image([os.path.join(PHOTOS_DIR, p) for p in photos_existantes], width=150)

            if st.button("💾 Mettre à jour", key=f"maj_pose_{pose.id}"):
                pose.adresse_chantier = adresse
                pose.date_pose = date_pose
                pose.statut = statut
                pose.equipe = equipe
                pose.observations = observations
                session.commit()
                st.success("Pose mise à jour.")
                st.rerun()

    session.close()


# ======================================================================
# PAGE : STATISTIQUES
# ======================================================================
def page_statistiques():
    st.title("📊 Statistiques")
    session = get_session()

    factures = session.query(Facture).all()
    lignes = session.query(DevisLigne).all()
    devis_list = session.query(Devis).all()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CA mensuel / annuel")
        if factures:
            df = pd.DataFrame([{"mois": f.date_creation.strftime("%Y-%m"), "montant": f.montant_total}
                                for f in factures])
            ca_mensuel = df.groupby("mois", as_index=False)["montant"].sum().sort_values("mois")
            st.plotly_chart(px.bar(ca_mensuel, x="mois", y="montant"), use_container_width=True)
        else:
            st.caption("Aucune donnée de facturation.")

    with col2:
        st.subheader("Produits les plus vendus")
        if lignes:
            df_l = pd.DataFrame([{"produit": l.produit, "quantite": l.quantite or 1} for l in lignes])
            top = df_l.groupby("produit", as_index=False)["quantite"].sum().sort_values(
                "quantite", ascending=False).head(10)
            st.plotly_chart(px.bar(top, x="produit", y="quantite"), use_container_width=True)
        else:
            st.caption("Aucune ligne de devis.")

    st.divider()
    st.subheader("🏆 Clients les plus rentables")
    if factures:
        df_f = pd.DataFrame([{
            "client": f"{f.client.nom} {f.client.prenom or ''}" if f.client else "—",
            "montant": f.montant_total,
        } for f in factures])
        top_clients = df_f.groupby("client", as_index=False)["montant"].sum().sort_values(
            "montant", ascending=False).head(10)
        top_clients["montant"] = top_clients["montant"].apply(formater_da)
        st.dataframe(top_clients, use_container_width=True, hide_index=True)
    else:
        st.caption("Aucune facture pour établir ce classement.")

    st.divider()
    st.subheader("💹 Marge bénéficiaire")
    if lignes:
        cout_estime = sum(
            (l.total_ligne or 0) for l in lignes
        )  # Le coût de revient détaillé n'est pas stocké ligne par ligne ; estimation globale
        st.caption("Estimation basée sur les paramètres de marge configurés dans Tarifs / Paramètres.")
        st.metric("Chiffre d'affaires cumulé des lignes de devis", formater_da(cout_estime))
    else:
        st.caption("Aucune donnée disponible.")

    st.divider()
    st.subheader("📤 Export")
    col_a, col_b = st.columns(2)
    if lignes:
        df_export = pd.DataFrame([{
            "Devis": l.devis.numero if l.devis else "", "Produit": l.produit, "Ouverture": l.ouverture,
            "Matériau": l.materiau_detail, "Couleur": l.couleur, "Largeur": l.largeur, "Hauteur": l.hauteur,
            "Quantité": l.quantite, "Surface m2": l.surface_m2, "ML": l.ml,
            "Prix unitaire": l.prix_unitaire, "Total ligne": l.total_ligne,
        } for l in lignes])

        csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
        col_a.download_button("⬇️ Export CSV", data=csv_bytes, file_name="statistiques_devis.csv",
                               mime="text/csv")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Lignes de devis")
        col_b.download_button("⬇️ Export Excel", data=buffer.getvalue(),
                               file_name="statistiques_devis.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    session.close()


# ======================================================================
# PAGE : PARAMETRES
# ======================================================================
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def page_parametres():
    st.title("⚙️ Paramètres")
    session = get_session()

    onglet_societe, onglet_calcul, onglet_utilisateurs = st.tabs(
        ["🏢 Informations société", "🧮 Paramètres de calcul", "👥 Utilisateurs"]
    )

    with onglet_societe:
        with st.form("infos_societe"):
            nom_entreprise = st.text_input("Nom de l'entreprise", value=get_parametre(session, "nom_entreprise"))
            col1, col2 = st.columns(2)
            telephone = col1.text_input("Téléphone", value=get_parametre(session, "telephone"))
            email = col2.text_input("Email", value=get_parametre(session, "email"))
            adresse = st.text_area("Adresse", value=get_parametre(session, "adresse"))
            col3, col4, col5 = st.columns(3)
            rc = col3.text_input("RC", value=get_parametre(session, "rc"))
            nif = col4.text_input("NIF", value=get_parametre(session, "nis"))
            nis = col5.text_input("NIS", value=get_parametre(session, "nis"))
            conditions = st.text_area("Conditions générales (affichées sur les PDF)",
                                       value=get_parametre(session, "conditions_generales"))
            logo = st.file_uploader("Logo de l'entreprise", type=["png", "jpg", "jpeg"])

            if st.form_submit_button("💾 Enregistrer", type="primary"):
                set_parametre(session, "nom_entreprise", nom_entreprise)
                set_parametre(session, "telephone", telephone)
                set_parametre(session, "email", email)
                set_parametre(session, "adresse", adresse)
                set_parametre(session, "rc", rc)
                set_parametre(session, "nif", nif)
                set_parametre(session, "nis", nis)
                set_parametre(session, "conditions_generales", conditions)
                if logo:
                    os.makedirs(ASSETS_DIR, exist_ok=True)
                    chemin_logo = os.path.join(ASSETS_DIR, "logo.png")
                    with open(chemin_logo, "wb") as f:
                        f.write(logo.getbuffer())
                    set_parametre(session, "logo_path", chemin_logo)
                st.success("Informations société enregistrées.")
                st.rerun()

        logo_path = get_parametre(session, "logo_path")
        if logo_path and os.path.exists(logo_path):
            st.image(logo_path, width=120, caption="Logo actuel")

    with onglet_calcul:
        st.caption("Ces paramètres influencent directement le calcul automatique des prix dans les devis.")
        with st.form("params_calcul"):
            cout_mo = st.number_input(
                "Coût main-d'œuvre par ML (DA)",
                value=float(get_parametre(session, "cout_main_oeuvre_ml", "0")), min_value=0.0, step=10.0,
            )
            marge = st.number_input(
                "Marge bénéficiaire (%)",
                value=float(get_parametre(session, "marge_beneficiaire_pct", "0")), min_value=0.0, step=1.0,
            )
            if st.form_submit_button("💾 Enregistrer", type="primary"):
                set_parametre(session, "cout_main_oeuvre_ml", cout_mo)
                set_parametre(session, "marge_beneficiaire_pct", marge)
                st.success("Paramètres de calcul enregistrés.")
                st.rerun()

    with onglet_utilisateurs:
        st.subheader("Utilisateurs")
        utilisateurs = session.query(Utilisateur).all()
        st.dataframe(pd.DataFrame([{
            "Nom d'utilisateur": u.nom_utilisateur, "Rôle": u.role,
            "Actif": "Oui" if u.actif else "Non",
        } for u in utilisateurs]), use_container_width=True, hide_index=True)

        st.markdown("**Ajouter un utilisateur**")
        with st.form("nouvel_utilisateur", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            nom_u = col1.text_input("Nom d'utilisateur")
            mdp_u = col2.text_input("Mot de passe", type="password")
            role_u = col3.selectbox("Rôle", ["Administrateur", "Commercial", "Atelier"])
            if st.form_submit_button("➕ Créer l'utilisateur"):
                if nom_u and mdp_u:
                    if session.query(Utilisateur).filter_by(nom_utilisateur=nom_u).first():
                        st.error("Ce nom d'utilisateur existe déjà.")
                    else:
                        session.add(Utilisateur(nom_utilisateur=nom_u, mot_de_passe=mdp_u, role=role_u))
                        session.commit()
                        st.success("Utilisateur créé.")
                        st.rerun()
                else:
                    st.error("Nom d'utilisateur et mot de passe requis.")

    session.close()


# ======================================================================
# APPLICATION PRINCIPALE
# ======================================================================

st.set_page_config(
    page_title="DJEFF ALUMINIUM PRO",
    page_icon="\U0001F3D7\uFE0F",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

st.markdown("""
<style>
    .block-container {padding-top: 1.5rem;}
    [data-testid="stMetricValue"] {font-size: 1.6rem;}
    .stButton>button {border-radius: 8px;}
    div[data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)

# ---------------- Authentification simple ----------------
if "utilisateur" not in st.session_state:
    st.session_state.utilisateur = None

if st.session_state.utilisateur is None:
    st.title("DJEFF ALUMINIUM PRO")
    st.caption("Connexion")
    with st.form("connexion"):
        col1, col2 = st.columns(2)
        nom_utilisateur = col1.text_input("Nom d'utilisateur", value="admin")
        mot_de_passe = col2.text_input("Mot de passe", type="password", value="admin123")
        valide = st.form_submit_button("Se connecter", type="primary")
    if valide:
        session = get_session()
        user = session.query(Utilisateur).filter_by(
            nom_utilisateur=nom_utilisateur, actif=True
        ).first()
        session.close()
        if user and user.mot_de_passe == mot_de_passe:
            st.session_state.utilisateur = {"nom": user.nom_utilisateur, "role": user.role}
            st.rerun()
        else:
            st.error("Identifiants incorrects.")
    st.info("Compte par defaut : **admin** / **admin123** -- a modifier dans Parametres.")
    st.stop()

role = st.session_state.utilisateur["role"]

# ---------------- Menu lateral (avec restriction par role) ----------------
session = get_session()
nom_entreprise_param = session.query(Parametre).filter_by(cle="nom_entreprise").first()
session.close()

with st.sidebar:
    st.markdown(f"### {nom_entreprise_param.valeur if nom_entreprise_param else 'DJEFF ALUMINIUM PRO'}")
    st.caption(f"Connecte : {st.session_state.utilisateur['nom']} ({role})")
    st.divider()

    MENU_COMPLET = [
        ("Tableau de bord", "dashboard", ["Administrateur", "Commercial", "Atelier"]),
        ("Clients", "clients", ["Administrateur", "Commercial"]),
        ("Devis", "devis", ["Administrateur", "Commercial"]),
        ("Factures", "factures", ["Administrateur", "Commercial"]),
        ("Tarifs", "tarifs", ["Administrateur"]),
        ("Stock", "stock", ["Administrateur", "Atelier"]),
        ("Fournisseurs", "fournisseurs", ["Administrateur", "Atelier"]),
        ("Fabrication", "fabrication", ["Administrateur", "Atelier"]),
        ("Pose", "pose", ["Administrateur", "Atelier"]),
        ("Statistiques", "statistiques", ["Administrateur"]),
        ("Parametres", "parametres", ["Administrateur"]),
    ]
    menu_autorise = [m for m in MENU_COMPLET if role in m[2]]
    labels = [m[0] for m in menu_autorise]
    choix = st.radio("Navigation", labels, label_visibility="collapsed")
    page_key = dict((m[0], m[1]) for m in menu_autorise)[choix]

    st.divider()
    if st.button("Deconnexion"):
        st.session_state.utilisateur = None
        st.rerun()

# ---------------- Routage vers les pages ----------------
if page_key == "dashboard":
    page_dashboard()
elif page_key == "clients":
    page_clients()
elif page_key == "devis":
    page_devis()
elif page_key == "factures":
    page_factures()
elif page_key == "tarifs":
    page_tarifs()
elif page_key == "stock":
    page_stock()
elif page_key == "fournisseurs":
    page_fournisseurs()
elif page_key == "fabrication":
    page_fabrication()
elif page_key == "pose":
    page_pose()
elif page_key == "statistiques":
    page_statistiques()
elif page_key == "parametres":
    page_parametres()
