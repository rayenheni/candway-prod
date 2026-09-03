/* ------------------------------------------------------------------ */
/*  Blog content model + articles                                      */
/*  Hand-curated marketing content rendered from typed blocks.         */
/* ------------------------------------------------------------------ */

export type Category = "Hiring playbook" | "Responsible AI" | "Product" | "Candidates";

export type Block =
  | { k: "p"; t: string }
  | { k: "h2"; t: string }
  | { k: "h3"; t: string }
  | { k: "ul"; items: string[] }
  | { k: "ol"; items: string[] }
  | { k: "quote"; t: string }
  | { k: "callout"; title: string; t: string }
  | { k: "rubric"; title: string; rows: [string, number][] }
  | { k: "compare"; left: [string, string[]]; right: [string, string[]] };

export type Author = {
  name: string;
  role: string;
  initials: string;
  gradient: string;
};

export type Cover = "score" | "lock" | "rubric" | "candidate" | "campaign" | "report";

export type Post = {
  slug: string;
  title: string;
  dek: string;
  category: Category;
  read: number;
  date: string;
  author: Author;
  featured?: boolean;
  cover: Cover;
  body: Block[];
};

export const CATEGORY_STYLE: Record<Category, string> = {
  "Hiring playbook": "bg-primary-500/12 text-primary-700 border-primary-300/50",
  "Responsible AI": "bg-emerald-500/12 text-emerald-700 border-emerald-400/40",
  Product: "bg-sky-500/12 text-sky-700 border-sky-300/50",
  Candidates: "bg-fuchsia-500/12 text-fuchsia-700 border-fuchsia-300/50",
};

export const AUTHORS: Record<string, Author> = {
  nour: {
    name: "Nour Arbi",
    role: "Head of Growth, Candway",
    initials: "NA",
    gradient: "from-primary-500 to-indigo-500",
  },
  yassine: {
    name: "Yassine Khelifi",
    role: "Co-founder & CTO",
    initials: "YK",
    gradient: "from-sky-500 to-indigo-500",
  },
  sana: {
    name: "Sana Mansouri",
    role: "Talent Advisor",
    initials: "SM",
    gradient: "from-emerald-500 to-teal-500",
  },
};

const nour = AUTHORS.nour;
const yassine = AUTHORS.yassine;
const sana = AUTHORS.sana;

export const POSTS: Post[] = [
  {
    slug: "guide-premier-profil-candidat",
    title: "Guide d'utilisation : votre premier profil candidat",
    dek: "Créer un profil complet, postuler en un clic et suivre vos candidatures — le parcours de A à Z, en 5 minutes.",
    category: "Candidates",
    read: 5,
    date: "Aug 12, 2026",
    author: sana,
    cover: "candidate",
    body: [
      { k: "p", t: "Après votre inscription, vous arrivez sur votre tableau de bord. C'est le point de départ de toute votre expérience Candway : c'est ici que vous retrouvez vos candidatures, vos entretiens et vos recommandations de postes." },
      { k: "h2", t: "1. Compléter votre profil" },
      { k: "p", t: "Cliquez sur « Mon profil » dans le menu latéral pour renseigner votre titre de poste, votre bio, vos compétences, votre localisation et vos langues. Chaque champ nourrit l'analyse de votre profil : plus il est précis, plus vos scores et vos recommandations sont fiables." },
      { k: "callout", title: "Le saviez-vous ?", t: "Un profil complet est visible 3 fois plus souvent par les recruteurs. La qualité de vos compétences déclarées détermine directement votre score d'analyse de CV." },
      { k: "ul", items: ["Titre de poste clair, par exemple « Développeur React senior »", "3 à 8 compétences précises plutôt qu'une liste vague", "Une bio courte qui résume votre valeur", "Disponibilité, fourchette salariale et préférences de poste"] },
      { k: "h2", t: "2. Postuler à une offre" },
      { k: "p", t: "Ouvrez la page « Offres d'emploi » pour parcourir les postes publiés par nos entreprises partenaires. La barre de recherche et les filtres par catégorie affinent la liste en quelques frappes." },
      { k: "ol", items: ["Trouvez une offre qui vous correspond", "Cliquez sur « Postuler »", "Joignez votre CV au format PDF — il est analysé automatiquement", "Recevez une confirmation immédiate"] },
      { k: "quote", t: "« En une journée, j'ai postulé à 4 offres et j'ai été invitée à 2 entretiens IA. C'est rapide et transparent. » — Zina, candidate" },
      { k: "h2", t: "3. Suivre vos candidatures" },
      { k: "p", t: "La page « Mes candidatures » récapitule l'état de chacune : en attente, en analyse, en entretien, offre reçue ou refusée. Une notification vous alerte à chaque changement de statut." },
      { k: "callout", title: "Astuce", t: "Activez les notifications pour ne manquer aucune réponse d'un recruteur, et consultez vos scores après chaque analyse pour comprendre ce que les recruteurs voient." },
    ],
  },
  {
    slug: "guide-entretien-ia",
    title: "Guide d'utilisation : l'entretien IA, comment ça marche",
    dek: "Un entretien vidéo mené par notre assistant intelligent : préparation, déroulé, critères évalués et rapport final.",
    category: "Responsible AI",
    read: 6,
    date: "Aug 05, 2026",
    author: yassine,
    featured: true,
    cover: "score",
    body: [
      { k: "p", t: "L'entretien IA est un entretien vidéo asynchrone mené par notre assistant intelligent. Il pose des questions adaptées au poste visé, analyse vos réponses en direct et produit un rapport de compétences détaillé à destination du recruteur." },
      { k: "h2", t: "Avant l'entretien" },
      { k: "p", t: "Une fois votre candidature reçue, le recruteur peut vous inviter à un entretien IA. Vous recevez un lien sécurisé par e-mail et dans votre tableau de bord, section « Mes entretiens »." },
      { k: "ul", items: ["Installez-vous dans un endroit calme", "Testez votre microphone et votre caméra", "Prévoyez environ 30 minutes", "Entraînez-vous avec les questions d'exemple autant de fois que nécessaire"] },
      { k: "h2", t: "Pendant l'entretien" },
      { k: "p", t: "Chaque question dispose d'un temps de préparation puis d'un temps de réponse. Un chronomètre vous guide. Vos réponses sont évaluées selon des critères métiers précis définis par le recruteur." },
      { k: "rubric", title: "Critères évalués", rows: [["Compétences techniques", 40], ["Expérience démontrée", 25], ["Communication", 20], ["Résolution de problèmes", 15]] },
      { k: "h2", t: "Après l'entretien" },
      { k: "p", t: "Vous retrouvez votre score global et le détail par compétence dans la page d'analyse. Le recruteur reçoit un rapport consolidé pour décider de la suite du processus." },
      { k: "compare", left: ["Entretien classique", ["Un seul créneau, souvent contraignant", "Prise de notes inégale", "Aucun score objectif", "Feedback rare"]], right: ["Entretien IA Candway", ["Quand vous voulez, où vous voulez", "Chaque réponse est enregistrée", "Score par compétence, pondéré par la grille", "Rapport complet partagé avec le recruteur"]] },
      { k: "callout", title: "Responsabilité", t: "Aucune décision n'est automatique : le score IA guide le recruteur, mais l'humain garde toujours le dernier mot. Vos données ne quittent jamais le serveur sans masquage préalable." },
    ],
  },
  {
    slug: "guide-publier-offre-recruteur",
    title: "Guide : publier une offre et trouver des talents",
    dek: "Assistant de création, grille d'évaluation, suivi des candidatures et campagnes de recrutement en volume.",
    category: "Hiring playbook",
    read: 7,
    date: "Jul 28, 2026",
    author: nour,
    cover: "campaign",
    body: [
      { k: "h2", t: "Créer une offre d'emploi" },
      { k: "p", t: "Depuis le tableau de bord recruteur, cliquez sur « Publier une offre » et suivez l'assistant : intitulé du poste, département, compétences requises, niveau de séniorité et fourchette salariale. L'assistant IA peut rédiger la description pour vous en quelques secondes." },
      { k: "h2", t: "Définir la grille d'évaluation" },
      { k: "p", t: "L'étape « Grille d'évaluation » est essentielle : c'est elle qui pilote l'analyse des CV et l'entretien IA. Créez vos catégories et compétences, ou choisissez une grille existante dans votre bibliothèque." },
      { k: "rubric", title: "Exemple — Développeur Frontend", rows: [["React / Vue / Angular", 40], ["TypeScript", 25], ["CSS & design systems", 20], ["Tests & CI", 15]] },
      { k: "callout", title: "Bonnes pratiques", t: "La somme des poids doit faire 100 %. Plus votre grille est précise, plus les scores des candidats sont pertinents et comparables." },
      { k: "h2", t: "Suivre les candidatures" },
      { k: "p", t: "La page « Candidatures » centralise les postulants : score CV, compétences détectées, statut et historique. Utilisez les actions rapides pour inviter un candidat en entretien IA, le présélectionner ou le refuser." },
      { k: "h2", t: "Lancer une campagne" },
      { k: "p", t: "Pour recruter en volume, créez une campagne : importez une liste de CV, notre moteur les analyse tous automatiquement et classe les profils par score. Vous ne vous occupez que des meilleurs." },
    ],
  },
  {
    slug: "guide-credits-abonnement",
    title: "Guide : gérer ses crédits et son abonnement",
    dek: "Comment fonctionne le système de crédits, que consomme chaque action IA et comment valider un paiement.",
    category: "Product",
    read: 5,
    date: "Jul 20, 2026",
    author: nour,
    cover: "lock",
    body: [
      { k: "h2", t: "Le système de crédits" },
      { k: "p", t: "Chaque action IA de la plateforme consomme un nombre défini de crédits. Votre solde est visible dans le menu « Mon abonnement » et se renouvelle à chaque cycle de facturation." },
      { k: "rubric", title: "Coût des principales actions", rows: [["Analyse de CV", 3], ["Entretien IA complet", 5], ["Génération de questions", 5], ["Rédaction de description (JD)", 2], ["Traduction", 1]] },
      { k: "h2", t: "Comprendre les forfaits" },
      { k: "p", t: "À chaque cycle, vos crédits mensuels sont renouvelés automatiquement. Les crédits non utilisés ne sont pas reportés : planifiez vos campagnes en début de mois." },
      { k: "callout", title: "Dépassement", t: "Si vous dépassez votre forfait, achetez un rechargement depuis la page d'abonnement. La validation de votre reçu de paiement est effectuée par notre équipe sous 24 h ouvrées." },
      { k: "h2", t: "Vérifier un paiement" },
      { k: "ol", items: ["Payez depuis la page d'abonnement", "Téléversez votre reçu (PDF ou image)", "Notre équipe valide le reçu sous 24 h ouvrées", "Vos crédits sont crédités et vous recevez une confirmation par e-mail"] },
      { k: "quote", t: "La transparence des coûts fait partie de notre promesse : vous savez toujours ce que consomme chaque action avant de la lancer." },
    ],
  },
  {
    slug: "guide-bibliotheque-grilles",
    title: "Guide : la bibliothèque de grilles d'évaluation",
    dek: "Créez une grille réutilisable, générez-la avec l'IA et liez-la à vos offres pour des évaluations cohérentes.",
    category: "Hiring playbook",
    read: 6,
    date: "Jul 10, 2026",
    author: yassine,
    cover: "rubric",
    body: [
      { k: "h2", t: "Qu'est-ce qu'une grille d'évaluation ?" },
      { k: "p", t: "Une grille (ou rubrique) définit les compétences à évaluer pour un poste, chacune avec un niveau attendu et un poids. Elle est utilisée pour analyser les CV et évaluer les entretiens IA de manière cohérente et transparente." },
      { k: "h2", t: "Créer une grille réutilisable" },
      { k: "p", t: "Ouvrez « Bibliothèque de grilles » puis « Créer une grille ». Donnez-lui un titre et une description, puis ajoutez vos catégories et compétences. Vous pouvez aussi la générer avec l'IA en renseignant simplement l'intitulé du poste." },
      { k: "ul", items: ["Chaque catégorie a un poids", "Chaque compétence a un niveau attendu (débutant → expert)", "Les compétences peuvent être marquées requises ou optionnelles", "La grille se réutilise sur plusieurs offres et campagnes"] },
      { k: "h2", t: "Lier une grille à une offre" },
      { k: "p", t: "Dans l'assistant de publication, choisissez « Utiliser une grille existante » et sélectionnez la vôtre. Les candidats seront évalués selon les critères et pondérations de cette grille, et vous verrez le détail par compétence dans le rapport d'évaluation." },
      { k: "callout", title: "Versioning", t: "Chaque modification crée une nouvelle version de la grille. Les offres existantes sont automatiquement re-pointées vers la version active : aucun historique d'évaluation n'est perdu." },
    ],
  },
  {
    slug: "guide-evaluer-candidats",
    title: "Guide : évaluer les candidats et décider",
    dek: "Lire les scores, comparer jusqu'à 5 profils et faire avancer les meilleurs vers la prochaine étape.",
    category: "Hiring playbook",
    read: 6,
    date: "Jun 30, 2026",
    author: sana,
    cover: "report",
    body: [
      { k: "h2", t: "Lire le score d'un candidat" },
      { k: "p", t: "Dans la page candidat, la section « Évaluation » présente le score CV, le score de la grille, le score d'entretien IA et le score final. Chaque score est accompagné d'une explication : compétences détectées, preuves relevées dans le CV et réponses en entretien." },
      { k: "h2", t: "Comparer plusieurs candidats" },
      { k: "p", t: "L'outil de comparaison met côte à côte jusqu'à 5 candidats sur les mêmes critères : score global, compétences couvertes et points forts. La décision devient plus objective et plus rapide." },
      { k: "compare", left: ["Décision à l'instinct", ["Aucune base commune", "Biais de récence possibles", "Comparaison approximative", "Retour difficile à justifier"]], right: ["Décision éclairée par Candway", ["Mêmes critères pour tous", "Scores et preuves tracés", "Classement par grille", "Feedback partageable au candidat"]] },
      { k: "h2", t: "Passer à l'étape suivante" },
      { k: "p", t: "Chaque candidat suit un parcours : candidature, analyse, entretien, offre. Faites avancer ou reculer un candidat d'une étape avec un seul clic, et envoyez une offre depuis la page d'évaluation." },
      { k: "quote", t: "« Nous avons divisé par deux notre temps de sélection et les candidats nous remercient de leur donner un vrai retour. » — Riadh, recruteur" },
    ],
  },
  {
    slug: "scoring-transparent-recruitement",
    title: "Pourquoi le scoring transparent change le recrutement",
    dek: "Scores expliqués, preuves citées, candidats informés : comment la transparence améliore la qualité et l'expérience.",
    category: "Responsible AI",
    read: 7,
    date: "Jun 18, 2026",
    author: yassine,
    cover: "score",
    body: [
      { k: "p", t: "Le recrutement souffre d'un problème de confiance : les candidats ne comprennent pas les décisions, et les recruteurs peinent à justifier leurs choix. La réponse n'est pas moins d'IA, c'est une IA plus transparente." },
      { k: "h2", t: "Chaque score est expliqué" },
      { k: "p", t: "Chez Candway, aucun score n'est une boîte noire. Le score CV est calculé à partir de votre grille : chaque compétence reçoit un poids, et le rapport affiche les preuves — mots-clés, contexte d'expérience — qui ont conduit au résultat." },
      { k: "h2", t: "Le candidat voit ce que le recruteur voit" },
      { k: "p", t: "Le candidat accède à son score, à son classement parmi les candidats et à la décomposition par compétence. Résultat : moins de surprises, moins de réclamations, et des candidats qui comprennent ce qu'ils doivent améliorer." },
      { k: "compare", left: ["Boîte noire", ["Score incompréhensible", "Décision opaque", "Réclamations et suspicion", "Aucun retour utile"]], right: ["Scoring transparent", ["Score décomposé par compétence", "Preuves citées", "Confiance accrue", "Retour constructif pour le candidat"]] },
      { k: "h2", t: "L'humain garde le dernier mot" },
      { k: "p", t: "La transparence ne remplace pas le jugement humain : elle l'éclaire. Le score IA hiérarchise et justifie, mais le recruteur décide. C'est notre engagement responsable, appliqué à chaque entretien." },
    ],
  },
  {
    slug: "reperer-meilleurs-profils-techniques",
    title: "5 signaux pour repérer les meilleurs profils techniques",
    dek: "Au-delà des années d'expérience : les signaux qui prédisent réellement la performance d'un développeur.",
    category: "Hiring playbook",
    read: 5,
    date: "Jun 05, 2026",
    author: sana,
    cover: "candidate",
    body: [
      { k: "p", t: "Les années d'expérience sont le signal le plus utilisé — et l'un des moins prédictifs. Voici les cinq signaux que nos grilles d'évaluation mesurent concrètement." },
      { k: "ol", items: ["Profondeur sur un socle solide : maîtrise réelle des fondamentaux", "Preuves tangibles : projets, contributions open source, cas concrets", "Capacité à communiquer la technique simplement", "Vitesse d'apprentissage : exemples de montée en compétence", "Attitude face à l'erreur : diagnostic, responsabilité, correction"] },
      { k: "p", t: "L'entretien IA Candway capture ces signaux grâce à des questions ciblées, et la grille les pondère selon le poste. Le score final n'est qu'une synthèse : le rapport détaille chaque signal avec les réponses qui l'ont étayé." },
      { k: "callout", title: "À retenir", t: "Un CV parfait n'est pas un signal. Cherchez les preuves, mesurez la communication et laissez la grille vous aider à rester objectif à travers les dizaines de candidatures." },
    ],
  },
];