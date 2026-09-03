"""Seed usage-guide blog articles into the live DB (idempotent by slug)."""
import sys

sys.path.insert(0, ".")

from backend.database import SessionLocal, BlogPost  # noqa: E402
from backend.models.foundation.cms import utcnow  # noqa: E402

COMPANY_ID = 4  # Candway Demo
AUTHOR_ID = 12  # admin@candway.dev

ARTICLES = [
    {
        "title": "Guide d'utilisation : votre premier profil candidat",
        "slug": "guide-premier-profil-candidat",
        "tags": "guide, candidat, profil",
        "content": """
<h2>Créer votre profil</h2>
<p>Après votre inscription, vous arrivez sur le tableau de bord. Cliquez sur « Mon profil » dans le menu latéral pour compléter vos informations : titre du poste, bio, compétences, localisation, langues et préférences de poste.</p>
<p>Un profil complet est 3 fois plus visible auprès des recruteurs. Prenez 5 minutes pour remplir chaque section : la qualité de votre CV et de vos compétences détermine directement votre score d'analyse.</p>
<h2>Postuler à une offre</h2>
<p>Ouvrez la page « Offres d'emploi » pour parcourir les postes publiés par nos entreprises partenaires. Utilisez la barre de recherche et les filtres par catégorie pour affiner votre sélection.</p>
<p>Cliquez sur « Postuler » pour envoyer votre candidature. Vous pouvez joindre votre CV au format PDF ; il sera analysé automatiquement par notre moteur d'intelligence artificielle pour extraire vos compétences.</p>
<h2>Suivre vos candidatures</h2>
<p>La page « Mes candidatures » récapitule l'état de chacune : en attente, en cours d'analyse, en entretien, offre reçue ou refusée. Vous recevez une notification à chaque changement de statut.</p>
<p>Astuce : activez les notifications pour ne manquer aucune réponse d'un recruteur.</p>
""",
    },
    {
        "title": "Guide d'utilisation : l'entretien IA, comment ça marche",
        "slug": "guide-entretien-ia",
        "tags": "guide, entretien, ia, candidat",
        "content": """
<h2>Qu'est-ce que l'entretien IA ?</h2>
<p>L'entretien IA est un entretien vidéo mené par notre assistant intelligent. Il pose des questions adaptées au poste visé, analyse vos réponses en direct et produit un rapport de compétences détaillé à destination du recruteur.</p>
<h2>Avant l'entretien</h2>
<p>Une fois votre candidature reçue, le recruteur peut vous inviter à un entretien IA. Vous recevez un lien sécurisé dans votre messagerie et dans votre tableau de bord, section « Mes entretiens ».</p>
<p>Installez-vous dans un endroit calme, testez votre microphone et votre caméra, et prévoyez environ 30 minutes. Vous pouvez vous entraîner autant de fois que vous le souhaitez avec nos questions d'exemple.</p>
<h2>Pendant l'entretien</h2>
<p>Chaque question dispose d'un temps de préparation puis d'un temps de réponse. Ne vous inquiétez pas si vous manquez une question : un chronomètre vous guide et vous pouvez relancer l'assistant si besoin.</p>
<p>Vos réponses sont évaluées selon des critères métiers précis définis par le recruteur : compétences techniques, expérience, communication et résolution de problèmes.</p>
<h2>Après l'entretien</h2>
<p>Vous retrouvez votre score global et le détail par compétence dans la page d'analyse. Le recruteur reçoit un rapport consolidé pour décider de la suite du processus.</p>
""",
    },
    {
        "title": "Guide d'utilisation : publier une offre et trouver des talents",
        "slug": "guide-publier-offre-recruteur",
        "tags": "guide, recruteur, offre",
        "content": """
<h2>Créer une offre d'emploi</h2>
<p>Depuis le tableau de bord recruteur, cliquez sur « Publier une offre » puis suivez l'assistant : intitulé du poste, département, compétences requises, niveau de séniorité et fourchette salariale. L'assistant IA peut rédiger la description pour vous en quelques secondes.</p>
<h2>Définir la grille d'évaluation</h2>
<p>L'étape « Grille d'évaluation » est essentielle : c'est elle qui pilote l'analyse des CV et l'entretien IA. Créez vos catégories et compétences, ou choisissez une grille existante dans votre bibliothèque. Chaque compétence reçoit un poids — la somme doit faire 100 %.</p>
<p>Plus votre grille est précise, plus les scores des candidats sont pertinents.</p>
<h2>Suivre les candidatures</h2>
<p>La page « Candidatures » centralise les postulants : score CV, compétences détectées, statut et historique. Utilisez les actions rapides pour inviter un candidat en entretien IA, le présélectionner ou le refuser.</p>
<h2>Lancer une campagne</h2>
<p>Pour recruter en volume, créez une campagne : importez une liste de CV, notre moteur les analyse tous automatiquement et classe les profils par score. Vous ne vous occupez que des meilleurs.</p>
""",
    },
    {
        "title": "Guide d'utilisation : gérer ses crédits et son abonnement",
        "slug": "guide-credits-abonnement",
        "tags": "guide, abonnement, credits, paiement",
        "content": """
<h2>Le système de crédits</h2>
<p>Chaque action IA de la plateforme consomme un nombre défini de crédits : analyse de CV (3 crédits), entretien IA (5 crédits), génération de questions, rédaction de descriptions, traduction, etc. Votre solde est visible dans le menu « Mon abonnement ».</p>
<h2>Comprendre les forfaits</h2>
<p>À chaque cycle de facturation, vos crédits mensuels sont renouvelés automatiquement. Les crédits non utilisés ne sont pas reportés : planifiez vos campagnes en début de mois.</p>
<p>Si vous dépassez votre forfait, vous pouvez acheter un rechargement depuis la page d'abonnement. La validation d'un reçu de paiement est effectuée par notre équipe sous 24 h ouvrées.</p>
<h2>Vérifier un paiement</h2>
<p>Après avoir payé, téléversez votre reçu dans la page d'abonnement. Vous recevrez une confirmation par e-mail dès que celui-ci sera validé et vos crédits crédités.</p>
""",
    },
    {
        "title": "Guide d'utilisation : la bibliothèque de grilles d'évaluation",
        "slug": "guide-bibliotheque-grilles",
        "tags": "guide, recruteur, grille, rubrique",
        "content": """
<h2>Qu'est-ce qu'une grille d'évaluation ?</h2>
<p>Une grille (ou rubrique) définit les compétences à évaluer pour un poste, chacune avec un niveau attendu et un poids. Elle est utilisée pour analyser les CV et évaluer les entretiens IA de manière cohérente et transparente.</p>
<h2>Créer une grille réutilisable</h2>
<p>Ouvrez « Bibliothèque de grilles » puis « Créer une grille ». Donnez-lui un titre, une description, puis ajoutez vos catégories et compétences. Vous pouvez la générer avec l'IA en renseignant simplement l'intitulé du poste.</p>
<p>Contrairement à la grille intégrée à une offre, une grille de bibliothèque se réutilise sur plusieurs offres et campagnes.</p>
<h2>Lier une grille à une offre</h2>
<p>Dans l'assistant de publication, choisissez « Utiliser une grille existante » et sélectionnez la vôtre. Les candidats seront évalués selon les critères et pondérations de cette grille.</p>
""",
    },
    {
        "title": "Guide d'utilisation : évaluer les candidats et décider",
        "slug": "guide-evaluer-candidats",
        "tags": "guide, recruteur, evaluation, decision",
        "content": """
<h2>Lire le score d'un candidat</h2>
<p>Dans la page candidat, la section « Évaluation » présente le score CV, le score de la grille, le score d'entretien IA et le score final. Chaque score est accompagné d'une explication : compétences détectées, preuves relevées dans le CV et réponses en entretien.</p>
<h2>Comparer plusieurs candidats</h2>
<p>Utilisez l'outil de comparaison pour mettre côte à côte jusqu'à 5 candidats sur les mêmes critères : score global, compétences couvertes et points forts. La décision devient plus objective.</p>
<h2>Passer à l'étape suivante</h2>
<p>Chaque candidat suit un parcours : candidature, analyse, entretien, offre. Vous pouvez faire avancer ou reculer un candidat d'une étape avec un seul clic, et envoyer une offre depuis la page d'évaluation.</p>
<p>La transparence est au cœur du processus : le candidat voit également son score et son classement.</p>
""",
    },
]


def run():
    db = SessionLocal()
    try:
        created = 0
        for art in ARTICLES:
            existing = db.query(BlogPost).filter(BlogPost.slug == art["slug"]).first()
            if existing:
                print(f"SKIP (exists): {art['slug']}")
                continue
            post = BlogPost(
                company_id=COMPANY_ID,
                title=art["title"],
                slug=art["slug"],
                content=art["content"],
                author_id=AUTHOR_ID,
                image_url=None,
                tags=art["tags"],
                is_published=True,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(post)
            created += 1
        db.commit()
        print(f"DONE: created={created} total_articles={len(ARTICLES)}")
    finally:
        db.close()


if __name__ == "__main__":
    run()