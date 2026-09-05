# Agenda Loire

Agenda culturel personnel de la Loire.

## Fonctionnalités

- affichage des événements
- filtres par période, catégorie, ville
- recherche
- favoris
- événements masqués
- synchronisation Supabase après connexion par lien magique
- fonctionnement local sans connexion
- collecte automatique quotidienne via GitHub Actions
- publication gratuite via GitHub Pages

## 1. Installer le projet dans GitHub

Copier tous les fichiers à la racine du repository `faberlin/agenda-loire`.

## 2. Configurer Supabase

Dans Supabase :

1. ouvrir **SQL Editor**
2. copier/coller le contenu de `supabase.sql`
3. exécuter le script

Dans **Authentication > URL Configuration** :

- Site URL : `https://faberlin.github.io/agenda-loire/`
- Redirect URLs : ajouter `https://faberlin.github.io/agenda-loire/**`

L'authentification utilise un lien magique envoyé par e-mail.

## 3. Activer GitHub Pages

Dans GitHub :

1. **Settings**
2. **Pages**
3. Source : **Deploy from a branch**
4. Branch : `main`
5. Folder : `/ (root)`
6. **Save**

Le site sera ensuite disponible sur :

`https://faberlin.github.io/agenda-loire/`

## 4. Autoriser GitHub Actions à mettre à jour events.json

Dans GitHub :

1. **Settings**
2. **Actions**
3. **General**
4. section **Workflow permissions**
5. choisir **Read and write permissions**
6. enregistrer

Le workflow `.github/workflows/update-events.yml` tourne chaque jour et peut aussi être lancé manuellement depuis l'onglet **Actions**.

## 5. Sources

Les sources sont dans `sources.json`.

La V1 contient :

- Médiathèques de Saint-Étienne : RSS
- Le Fil : données structurées JSON-LD si disponibles
- La Comédie de Saint-Étienne : données structurées JSON-LD si disponibles

Le collecteur HTML générique récupère les événements schema.org présents dans les pages. Pour les sites qui n'en publient pas, il faudra ajouter un extracteur dédié.

## Remarque sécurité

La clé présente dans `config.js` est une clé Supabase **publishable**, destinée aux applications frontend.

La table `event_preferences` est protégée par Row Level Security : un utilisateur authentifié ne peut accéder qu'à ses propres préférences.

Ne jamais placer une clé `service_role` dans ce repository.
