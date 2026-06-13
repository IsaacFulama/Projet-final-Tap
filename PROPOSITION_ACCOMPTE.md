# Proposition : Gestion des Acomptes

## Contexte
Certains souscripteurs paient un acompte au lieu du montant total. Le système doit gérer cette situation.

## Proposition de solution

### 1. Structure de données

**Ajouter des colonnes dans la table `paiements` :**
- `montant_total` (DECIMAL) : Montant total de la souscription
- `montant_paye` (DECIMAL) : Montant déjà payé (acompte + paiements)
- `reste_a_payer` (DECIMAL) : Reste à payer (calculé : montant_total - montant_paye)
- `statut_paiement` (VARCHAR) : 'Acompte', 'Partiel', 'Complet', 'En attente'

### 2. Workflow utilisateur

**Option A : Formulaire de souscription avec acompte**
- Champ "Montant total" (obligatoire)
- Champ "Montant payé" (optionnel, par défaut = montant total)
- Si montant_payé < montant_total → Statut automatique = "Acompte"
- Calcul automatique du reste à payer

**Option B : Ajout de paiements complémentaires**
- Menu "Ajouter paiement" pour un souscripteur existant
- Permet d'ajouter un montant au montant_payé
- Mise à jour automatique du statut quand montant_payé = montant_total

### 3. Affichage dans le tableau

**Colonnes supplémentaires :**
- Montant total
- Montant payé
- Reste à payer (en rouge si > 0)
- Statut paiement (acompte/partiel/complet)

**Indicateurs visuels :**
- 🟡 Acompte (paiement initial < total)
- 🟠 Partiel (paiements intermédiaires)
- 🟢 Complet (paiement total effectué)
- ⚪ En attente (aucun paiement)

### 4. Fonctionnalités proposées

**A. Enregistrement d'acompte**
```
Formulaire de souscription :
- Nom, Prénom, Téléphone
- Mois
- Montant total : 500 USD
- Montant payé (acompte) : 200 USD
- Devise : USD
- Statut : Acompte (automatique)
- Reste à payer : 300 USD (automatique)
```

**B. Ajout de paiement complémentaire**
```
Menu contextuel → "Ajouter paiement"
- Montant à ajouter : 150 USD
- Nouveau montant payé : 350 USD
- Nouveau reste : 150 USD
- Statut : Partiel
```

**C. Historique des paiements**
```
Dialogue d'historique amélioré :
- Date de chaque paiement
- Montant de chaque paiement
- Cumul des paiements
- Reste à payer
```

### 5. Implémentation technique

**Migration de base de données :**
```sql
ALTER TABLE paiements 
ADD COLUMN montant_total DECIMAL(10,2) DEFAULT montant,
ADD COLUMN montant_paye DECIMAL(10,2) DEFAULT 0,
ADD COLUMN reste_a_payer DECIMAL(10,2) DEFAULT montant,
ADD COLUMN statut_paiement VARCHAR(20) DEFAULT 'En attente';
```

**Nouvelles fonctions repository :**
- `ajouter_paiement_complementaire(paiement_id, montant)`
- `mettre_a_jour_montant_paye(paiement_id, nouveau_montant)`

**Modification du formulaire :**
- Ajout champ "Montant payé" (optionnel)
- Validation : montant_payé <= montant_total
- Calcul automatique du reste

### 6. Questions à valider

1. **Mode de saisie :** Préférez-vous un seul formulaire avec acompte OU un système de paiements multiples ?

2. **Historique :** Souhaitez-vous tracer chaque paiement individuellement (date, montant) ?

3. **Rappels :** Voulez-vous un système de rappel pour les acomptes non complétés ?

4. **Statuts :** Les statuts proposés (Acompte/Partiel/Complet/En attente) vous conviennent-ils ?

5. **Affichage :** Préférez-vous voir le reste à payer dans le tableau principal ou seulement dans l'historique ?

## Recommandation

**Option recommandée :** Option A + Option B
- Permettre l'acompte à la souscription
- Permettre d'ajouter des paiements complémentaires
- Historique détaillé des paiements
- Indicateurs visuels clairs

Cela offre la flexibilité maximale tout en gardant une interface simple.
