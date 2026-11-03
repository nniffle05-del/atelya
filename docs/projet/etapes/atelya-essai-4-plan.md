# Étape 6-15 : essai 4 d'Atelya, l'habituer aux photos de téléphone

## Pourquoi
À l'étape 6-14, la lecture des photos de biais sans cotes est devenue très bonne **quand le coloriage est parfait** (94 % de murs justes). Mais **Atelya** (le modèle qui colorie le plan) n'a jamais vu de vraies photos de téléphone : feuille penchée avec une vraie perspective, format 4:3, table autour de la feuille. Il colorie donc mal ces photos, et on tombe à **57 % de murs justes**. C'est lui qu'il faut entraîner, pas la lecture.

## L'idée
Lui montrer, pendant son apprentissage, quelques milliers de photos « vraie caméra » fabriquées par notre générateur (option déjà présente, `--vraie-camera`), **mélangées** aux 8 219 plans qu'il connaît déjà pour qu'il n'oublie rien. On repart de ce qu'il sait déjà (essai 2), on ne recommence pas de zéro.

## Le plan, en 5 temps (tout le gros calcul sur le PC)
1. **Fabriquer les photos d'apprentissage** (PC, ~20-30 min) : ~2 500 photos vraie caméra, moitié avec cotes, moitié sans, avec d'autres numéros (« graines ») que les 342 photos de test : Atelya ne doit jamais voir pendant l'apprentissage les photos sur lesquelles on le note.
2. **Écrire le petit script de l'essai 4** (cloud) : reprend l'essai 2, mélange ~1/3 de photos et ~2/3 d'anciens plans. Je le teste à blanc dans le cloud avant.
3. **Entraîner** (PC, ~2 h, après ton « lance » écrit). PC branché, hors veille, surélevé (il chauffe à ~86 °C).
4. **Noter** (PC, ~1 h) : coloriage puis note sur les 342 photos de test et sur les 1 066 anciens niveaux.
   - But : murs justes sur les photos **57 % → le plus près possible de 94 %**.
   - Garde-fous : **aucun recul de plus de 0,5 point** sur les 1 066 anciens plans, et **0 erreur d'échelle > 3 %**. Sinon on garde l'ancien Atelya.
   - Je regarderai aussi le type des pièces (aujourd'hui 54 % sur ces photos) et s'il faut un « duo » essai 4 + essai 3 comme avant.
5. **Note honnête /100**, puis commit sur le Mac (après ton « vas-y ») et entrée 6-15 dans le suivi pour ton associé (posée sur la #14).

## Ce qu'il faudra
- **Aucune installation** : tout ce qu'il faut est déjà sur le PC.
- Le PC allumé, branché, **mise en veille désactivée**, à l'étape 1.
- Le script de l'essai 4 arrivera sur le PC par un petit fichier (directement dans les instructions, ou par e-mail s'il est trop gros).
- Limite honnête : ce sont des photos **fabriquées**. Elles ressemblent à de vraies photos, mais pas parfaitement (reflets, ombres, papier froissé, flou de bougé). Le vrai test viendra avec de vrais plans photographiés.
