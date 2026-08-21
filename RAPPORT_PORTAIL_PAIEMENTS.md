# Rapport portail et module Mes paiements

Date : 2026-08-20

## Fonctionnalites livrees

- Section `Mes paiements` dans le portail locataire.
- Historique limite au locataire resolu par le token ; aucun `locataire_id` fourni par le navigateur n'est utilise pour l'autorisation.
- Filtres par recherche, statut et periode.
- Colonnes : date, montant, devise, methode, reference, statut et prestation.
- Detail securise par paiement.
- Export CSV UTF-8 avec BOM pour Excel.
- Facture PDF telechargeable par paiement.
- Notification visible quand des paiements sont en attente.
- Interface responsive avec tableau scrollable, filtres empiles sur mobile, boutons tactiles, textes longs repliables et support paysage.

Les colonnes `methode_paiement` et `reference` n'existent pas dans le schema historique. La methode est donc explicitement `Non renseignée` et la reference deterministe `PAI-{id}`. Il faut ajouter des colonnes et les alimenter depuis un prestataire de paiement avant de les presenter comme des donnees de transaction bancaire.

## Routes ajoutees

- `GET /api/portal/<token>/payments`
- `GET /api/portal/<token>/payments/<payment_id>`
- `GET /api/portal/<token>/payments.csv`
- `GET /api/portal/<token>/payments/<payment_id>/invoice.pdf`

Chaque route resout d'abord le token hashé puis ajoute systématiquement `p.locataire_id = tenant_id` à la requête.

## Validation

- Suite fonctionnelle : `116 passed`.
- Compilation Python du portail et du serveur : OK.
- Lint ciblé des fichiers du module : OK.
- PDF valide (`%PDF`) et CSV telechargeable testes.
- HTML responsive verifie aux largeurs 375, 768 et 1440 px sans debordement horizontal.
- Accessibilite de base : navigation ancree, labels de champs, tableau semantique, `aria-label`, `role=status` et `aria-live`.

## Points qui demandent une infrastructure supplementaire

- Notifications email : aucun SMTP fiable n'est configure dans le projet ; l'interface affiche les notifications de statut, mais aucun email n'est emis automatiquement.
- 2FA : le portail actuel est un lien temporaire a secret, pas un compte utilisateur avec second facteur. Ajouter TOTP/WebAuthn demande une gestion d'identite et une procedure de recuperation.
- Chiffrement de bout en bout : HTTPS/TLS doit etre termine par un serveur de production ; Flask development server ne doit pas etre expose sur Internet. PCI DSS interdit aussi de traiter des donnees carte dans cette application sans prestataire conforme.
- Chatbot et tickets : aucune base de tickets ni fournisseur conversationnel n'est configure. Ils doivent etre ajoutes comme services separes avec minimisation RGPD et retention definie.
- Cache : un cache cote serveur peut servir des donnees locataire uniquement avec une cle incluant le hash du token et une expiration courte ; aucune mise en cache globale n'a ete ajoutee pour eviter une fuite de donnees.

## Deploiement conseille

Pour un usage local, le portail doit etre lance sur le meme Wi-Fi que le telephone et le port TCP 8765 doit etre autorise dans le pare-feu Windows. Pour un usage Internet, utiliser HTTPS derriere un reverse proxy, des tokens courts et revocables, des journaux sans secrets, une limitation de debit et un fournisseur de paiement PCI DSS.
