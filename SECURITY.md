# Politique de sécurité

## Versions supportées

Le projet est en développement actif. Seule la branche `main` reçoit des correctifs de sécurité.

## Signaler une vulnérabilité

Merci de ne **pas** ouvrir d'issue publique pour une faille de sécurité.

Contact : **sorohenluy@gmail.com**

Inclure dans le rapport :

- Description de la vulnérabilité
- Étapes de reproduction (idéalement un PoC minimal)
- Impact potentiel
- Versions affectées
- Suggestion de correctif si possible

Réponse sous 7 jours. Coordination de divulgation possible.

## Garanties côté code

Voir section 10 de `BRIEF.md`. Résumé :

- Validation des uploads (whitelist d'extensions + magic number via `python-magic`)
- Limites de taille (100 MB / fichier, 500 MB / job, 50 fichiers / job)
- Stockage filesystem par UUID, jamais le nom utilisateur
- Prévention path traversal (`Path.resolve().is_relative_to(DATA_DIR)`)
- Strip JavaScript dans les PDF via `pikepdf` avant traitement
- Sanitization XSS sur le markdown rendu (côté client)
- CORS restreint, rate limiting `slowapi`
- Containers : utilisateurs non-root, images pinnées
- Lockfiles committés + Dependabot actif
- `.env` jamais committé
