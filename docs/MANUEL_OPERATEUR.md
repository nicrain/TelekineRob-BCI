# TelekineRob-BCI — Manuel opérateur

[Retour à la présentation du projet](../README.md) · [Version chinoise](MANUEL_OPERATEUR_cn.md)

> Manuel d’utilisation : vérifications préalables, connexion, calibration, commande EEG, dépannage courant et arrêt. Les noms des boutons restent en anglais pour correspondre à l’interface.
> Destiné à l’ordinateur déjà installé. L’installation, les modifications du code et la restauration de l’environnement ne font pas partie des opérations quotidiennes décrites ici.

Accès rapide : [Arrêter en cas d’anomalie](#arrêter-le-robot-en-cas-danomalie) · [Vérifications préalables](#vérifications-avant-utilisation) · [Démarrage](#2-démarrer-le-système) · [Connexion et calibration](#3-connecter-les-appareils-et-calibrer) · [Ajustement manuel](#ajustement-manuel-des-références-facultatif) · [Commande EEG](#4-démarrer-la-commande-eeg) · [Test Keyboard](GUIDE_DEBUG.md#b-le-thymio-ne-bouge-pas) · [Dépannage](#6-dépannage) · [Arrêt](#7-arrêter-le-système)

## 1. Présentation et sécurité

### Les deux pages

**System Control** s’ouvre après un double-clic sur `launcher.bat` sous Windows. Sa barre latérale sert à démarrer le système, connecter les appareils et redémarrer les services web.

**Thymio EEG Control**, l’interface de contrôle, apparaît dans la zone principale de System Control. **Open in new tab** permet aussi de l’ouvrir séparément. Elle sert à choisir les appareils et rôles, calibrer, observer les signaux et commander le robot.

| Emplacement | Boutons | Usage |
|---|---|---|
| Barre latérale de System Control | Start System / Stop System | Démarrer / arrêter l’ensemble du système |
| Haut de l’interface de contrôle | Start / Stop | Démarrer / arrêter le traitement EEG et la commande du robot |

Après connexion et calibration, cliquer sur **Start** en haut de l’interface de contrôle pour lancer la commande EEG ; voir la [section 4](#4-démarrer-la-commande-eeg).

### Arrêter le robot en cas d’anomalie

1. En cas de mouvement anormal, de perte de données ou avant un dépannage, cliquer d’abord sur **Stop en haut de l’interface de contrôle** et vérifier que le robot s’est réellement arrêté.
2. Si la page ne répond pas ou si le robot continue, éteindre le **Thymio** si cela peut être fait en sécurité ; arrêter ensuite le système et chercher la cause.
3. Rafraîchir la page, fermer le navigateur ou voir un état gris ne prouve pas l’arrêt. Après reconnexion, vérifier que le contrôle est arrêté avant de reprendre la procédure normale.

Garder de l’espace autour du robot et ne pas tester au bord d’une table. La protection contre la perte de données ne remplace pas la vérification de l’arrêt réel. Si le système fonctionne encore, le retour des données peut relancer des mouvements.

### Vérifications avant utilisation

Vérifier et allumer uniquement les appareils utilisés. Sans Headband, aucune manipulation de son environnement VS Code n’est nécessaire. La simulation n’exige ni Thymio réel, ni dongle, ni partage USB.

1. **Batteries et alimentation :** charger les EEG et le Thymio utilisés ; brancher le chargeur de l’ordinateur pour réduire les effets possibles de l’économie d’énergie / gestion d’alimentation Windows sur les connexions Bluetooth EEG.
2. **Bluetooth de l’ordinateur :** clic droit sur Démarrer Windows, puis **Gestionnaire de périphériques**, rubrique Bluetooth. Le module intégré ne doit présenter ni point d’exclamation jaune ou rouge, ni avertissement. Sinon, clic droit sur ce module, **Désactiver**, puis **Activer**.
3. **Module Bluetooth des EEG :** Headband et Hybrid Black utilisent par défaut le module intégré. L’adaptateur Bluetooth USB fourni avec le Hybrid Black provoquait souvent des déconnexions dans ce projet ; éviter de l’utiliser.
4. **Dongle Thymio :** pour le robot réel, le brancher dans le port USB prévu. Chaque paire Thymio / dongle est normalement déjà appairée ; aucun nouvel appairage n’est nécessaire en usage courant. Seulement en cas de doute, suivre la [procédure officielle d’appairage](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/).
5. **Nouveau / autre Thymio :** le « partage » transmet le dongle USB Windows au programme de contrôle sous Linux (WSL). La configuration actuelle utilise le BUSID **`1-1`**. À la première utilisation du dongle, vérifier son partage selon les [étapes pour un nouveau dongle](GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio). Si ce numéro manque, débrancher et rebrancher dans le port prévu, puis vérifier à nouveau.
6. **Python du Headband, uniquement s’il est utilisé :** dans VS Code, sélectionner le venv existant utilisé pour les essais. Le chemin de l’ordinateur d’origine et les étapes sont dans le [guide de dépannage](GUIDE_DEBUG.md#sélectionner-le-venv-dans-vs-code).

L’adaptateur Bluetooth USB du Hybrid Black et le dongle USB du Thymio sont différents : **le dongle Thymio reste nécessaire pour le robot réel**.

### Port des appareils et rôles

- Suivre les instructions de l’appareil utilisé pour le port et la préparation des électrodes. Ne pas mélanger les procédures des deux modèles. Garder la même position pendant la calibration et l’utilisation.
- Un EEG : une personne, un appareil ; choisir **Speed** (avancer / arrêter) ou **Steering** (tourner), puis **None** pour le Role de la deuxième ligne.
- Deux EEG : la combinaison actuelle est **un Headband + un Hybrid Black**, avec **Speed** et **Steering**. Une personne commande l’avance / l’arrêt, l’autre la rotation et le changement de direction par clignement. Deux appareils du même modèle ne sont pas utilisables directement actuellement.
- L’utilisateur **Steering** change de direction gauche / droite par clignement ; éviter les clignements très fréquents ou forcés qui peuvent provoquer plusieurs basculements.
- Ne pas déplacer le casque ou les électrodes, couper le Bluetooth, retirer le dongle ou débrancher le chargeur pendant l’utilisation. En cas de mouvement anormal, suivre la [procédure d’arrêt](#arrêter-le-robot-en-cas-danomalie).

## 2. Démarrer le système

1. Utiliser le raccourci Windows configuré sur l’ordinateur ou double-cliquer sur le `launcher.bat` existant : **System Control** s’ouvre dans le navigateur.
2. Si le système est **Stopped**, cliquer sur **Start System** dans **Operations**.
3. Attendre le passage de **Starting…** à **Running** en vert, l’affichage de l’interface de contrôle et l’activation des boutons de connexion.
4. Connecter les appareils utilisés selon la [section 3](#3-connecter-les-appareils-et-calibrer).

| État système | Signification | Action |
|---|---|---|
| Stopped | Système non démarré | Cliquer sur Start System |
| Starting… / Stopping… | Démarrage / arrêt en cours | Attendre |
| Running | Services web prêts | Connecter les appareils ; la commande EEG nécessite ensuite Start dans l’interface de contrôle |
| Error | Erreur de démarrage ou de service | Lire le message et suivre le [dépannage](#6-dépannage) |

En **Running**, Start System devient **Restart System**. Ce bouton redémarre l’ensemble du système : ne pas l’utiliser pendant une session.

## 3. Connecter les appareils et calibrer

Lorsque le système est **Running**, connecter les appareils utilisés dans **Devices**. Headband et Hybrid Black n’ont pas la même procédure.

### Connexion et déconnexion du Headband

Dans ce projet, le pont Headband doit être exécuté et interrompu manuellement dans **VS Code sous Windows**.

Connexion :

1. Cliquer sur **Connect** du Headband dans System Control. Le script `gpype_lsl_bridge.py` s’ouvre dans VS Code.
2. Vérifier le **venv** existant utilisé pour les essais ; voir les [étapes et le chemin d’origine](GUIDE_DEBUG.md#sélectionner-le-venv-dans-vs-code). Ne pas recréer l’environnement.
3. Cliquer sur le **bouton triangulaire ▶ en haut à droite de VS Code** pour exécuter le script.
4. Attendre **Connected** en vert dans System Control.

Déconnexion :

1. Cliquer d’abord sur **Stop** en haut de l’interface de contrôle.
2. Dans VS Code, sélectionner le terminal du script et appuyer sur **Ctrl+C** pour l’interrompre.
3. Revenir à System Control ; si le bouton **Disconnect** du Headband est encore disponible, cliquer dessus.

**Disconnect** ou **Stop System** n’interrompent pas le script Headband lancé dans VS Code. Arrêter l’ancien script avant toute nouvelle exécution.

### Connexion et déconnexion du Hybrid Black et du Thymio

- **Hybrid Black :** cliquer sur **Connect** de **HybridBlack** dans System Control et attendre **Connected** en vert. Pour déconnecter, cliquer sur **Disconnect** ; aucune exécution manuelle dans VS Code n’est nécessaire.
- **Thymio :** pour le robot réel, vérifier qu’il est allumé et que le dongle est dans le port prévu, puis cliquer sur **Connect** de **Thymio**. Inutile en simulation.
- Avant toute déconnexion, cliquer sur **Stop** en haut de l’interface de contrôle.

**Connect** du Thymio fait passer le dongle USB de BUSID **`1-1`** de **Shared** à **Attached**, c’est-à-dire qu’il le connecte à Linux (WSL).

**Connected** en vert pour un EEG signifie que des données ont été détectées. Pour Thymio, le vert signifie que le dongle est accessible au système ; vérifier aussi le mouvement réel du robot. **L’absence de graphiques après la seule connexion est normale** : ils se mettent à jour pendant la calibration ou après Start.

### Choisir les appareils, rôles et sortie

Dans **01 — Input Source** :

| Champ | Choix |
|---|---|
| Role | Un EEG : Speed ou Steering en première ligne, None en deuxième ; deux EEG : Speed et Steering |
| Device | EEG pour chaque ligne active |
| Brand | g.tec Headband ou g.tec Hybrid Black selon l’appareil réellement utilisé |
| Source | LSL Stream |
| Metric | Alpha / TBR / EI selon le protocole de la session |

Dans **02 — Output Target**, choisir **Thymio** pour le robot réel, **Thymio Simu** pour la simulation.

Un EEG en **Speed** commande seulement l’avance ; en **Steering**, seulement la rotation sur place. Il ne commande pas les deux simultanément. Avec deux appareils, vérifier Brand et Role de chaque ligne pour identifier qui commande l’avance et qui commande la rotation. Conserver les autres réglages validés pour la session.

### Calibration

**Avant Calibrate, poser le Thymio sur une surface plane et sûre, avec de l’espace autour, loin des bords de table, marches et obstacles. Un mouvement bref est possible à la fin de la calibration ; l’arrêt automatique en mode à deux EEG ne garantit pas une immobilité totale.**

1. Vérifier que le contrôle est arrêté et que les appareils / rôles / indicateurs sont choisis. Dans **03 — Real-time Signals**, cliquer une fois sur **Calibrate** de l’appareil concerné, sans cliquer d’abord sur Start.
2. **Preparing…** apparaît d’abord ; après réception de données d’analyse, **Calibrating… Ns** lance le décompte de 30 secondes.
3. Respecter l’état demandé par la session et ne pas déplacer le casque. Attendre les références **min / max** dans le panneau ; privilégier la calibration automatique. Si Preparing persiste, suivre le [dépannage EEG](GUIDE_DEBUG.md#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage).
4. Avec deux EEG, terminer la calibration du premier avant de calibrer le second. Les résultats sont enregistrés séparément.
5. Si **Running…** reste affiché en haut à la fin, cliquer sur **Stop**, vérifier l’arrêt réel du robot, puis démarrer selon la [section 4](#4-démarrer-la-commande-eeg).

Avec deux EEG, le système s’arrête normalement automatiquement après calibration ; avec un seul, il peut rester Running. Dans les deux cas, commencer la commande proprement dite avec un nouveau Start. Recalibrer après changement d’utilisateur, d’appareil ou d’indicateur, ou après une calibration annulée par Stop. Si **Calibration produced no new values** apparaît, la fin du décompte ne prouve pas une calibration réussie : suivre le [dépannage calibration](GUIDE_DEBUG.md#d-aucun-nouveau-résultat-de-calibration--boutons-indisponibles).

Les courbes sont effacées après calibration ; cela ne signifie pas en soi une déconnexion. Après Start, elles se remplissent avec les nouvelles données. Si elles restent vides, suivre le [dépannage EEG](GUIDE_DEBUG.md#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage).

#### Ajustement manuel des références (facultatif)

Effectuer normalement la calibration automatique d’abord. Ajuster manuellement seulement si la conversion en commande nécessite un réglage fin :

1. Cliquer sur **Stop** en haut et vérifier l’arrêt réel.
2. Dans **03 — Real-time Signals**, trouver **min / max** de l’appareil. Pour changer les deux, modifier **min**, puis **max**, et vérifier que **max est supérieur à min**. Avec deux EEG, traiter chaque appareil séparément.
3. Les changements sont enregistrés automatiquement. En cas d’erreur de sauvegarde, conserver le message et ne pas démarrer. Vérifier les valeurs puis cliquer sur **Start** selon la [section 4](#4-démarrer-la-commande-eeg).

Ces nombres délimitent la référence de conversion en commande, pas les extrema de la tension EEG brute. Ne pas les modifier pour contourner une erreur de calibration, une perte de données ou un problème de port du casque.

## 4. Démarrer la commande EEG

1. Vérifier le [choix des appareils et rôles](#choisir-les-appareils-rôles-et-sortie) et la [calibration](#calibration).
   Avec deux EEG, si **not calibrated. Start anyway?** apparaît, annuler et calibrer d’abord. Ce message concerne seulement le mode à deux appareils ; son absence ne prouve pas une calibration réussie.
2. Cliquer sur **Start en haut de l’interface de contrôle** et attendre **Running…**.
3. Vérifier dans **03 — Real-time Signals** que les données et indicateurs de chaque appareil se mettent à jour, puis observer le robot.
4. Pour une pause, cliquer sur **Stop** ; pour reprendre, cliquer à nouveau sur **Start**.

## 5. Pendant le contrôle

- **Speed :** l’indicateur EEG commande l’avance / l’arrêt.
- **Steering :** l’indicateur EEG commande la rotation sur place ; un clignement bascule gauche / droite.
- **Deux EEG :** les deux personnes commandent vitesse et direction. Si l’un perd ses données, le programme tente une protection par commande nulle ; vérifier quand même l’arrêt réel et cliquer sur Stop.
- **03 — Real-time Signals :** observer l’actualisation des graphiques et l’état des appareils. Alpha / theta / beta sont des puissances fréquentielles calculées, non des tensions EEG brutes. Les flèches représentent direction / intensité de la commande ; elles ne prouvent pas que le robot bouge.

Ne pas recalibrer, changer d’appareil ou redémarrer les services web pendant le contrôle. Cliquer d’abord sur **Stop** pour tout réglage. À la fin, suivre l’[arrêt du système](#7-arrêter-le-système).

## 6. Dépannage

Les étapes détaillées sont dans le [guide de dépannage](GUIDE_DEBUG.md). Avant reconnexion ou redémarrage, cliquer sur **Stop** et vérifier l’arrêt réel du robot.

| Symptôme | Vérification et action |
|---|---|
| Preparing persistant / aucune courbe après démarrage | Suivre le [dépannage EEG](GUIDE_DEBUG.md#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage) : Bluetooth, alimentation, rôles, appareils, reconnexion et calibration. |
| Headband reste Connecting après Connect | Connect ouvre seulement le script ; choisir le bon venv et cliquer sur ▶ selon la [connexion Headband](#connexion-et-déconnexion-du-headband). |
| EEG sans données, état gris ou Failed | Stop et arrêt réel d’abord, puis [récupération EEG](GUIDE_DEBUG.md#e-perte-de-données--état-gris-ou-failed) ; ne pas seulement attendre une reconnexion automatique. |
| Thymio immobile, gris ou Failed | Stop et arrêt réel d’abord, puis [dépannage Thymio et test Keyboard](GUIDE_DEBUG.md#b-le-thymio-ne-bouge-pas) pour distinguer la connexion robot des problèmes EEG. |
| Running vert mais interface absente | Arrêter le contrôle / vérifier l’immobilité, puis suivre la [récupération web](GUIDE_DEBUG.md#c-état-système-non-vert--interface-inaccessible). |
| Start System échoue, état Error | Lire le message et View Log selon le [dépannage système](GUIDE_DEBUG.md#c-état-système-non-vert--interface-inaccessible) ; ne pas multiplier les clics. |
| Aucun nouveau résultat de calibration, options / boutons bloqués | Suivre le [dépannage calibration et boutons](GUIDE_DEBUG.md#d-aucun-nouveau-résultat-de-calibration--boutons-indisponibles), en vérifiant d’abord si le contrôle fonctionne encore. |

## 7. Arrêter le système

1. **Arrêter la commande EEG :** cliquer sur **Stop** en haut et vérifier l’immobilité du robot ; si la page ne répond pas, suivre l’[arrêt en cas d’anomalie](#arrêter-le-robot-en-cas-danomalie).
2. **Arrêter le script Headband :** s’il est utilisé, appuyer sur **Ctrl+C** dans son terminal VS Code. System Control ne le fait pas à votre place.
3. **Arrêter l’ensemble du système :** cliquer sur **Stop System** dans la barre latérale et attendre **Stopping… → Stopped**.
4. **Quitter le launcher :** cliquer enfin sur **Exit Launcher**. Ce bouton quitte seulement le service de contrôle ; il ne remplace ni Stop ni Stop System.
5. **Ranger les appareils :** les éteindre, nettoyer et ranger les électrodes selon leurs notices, ranger les casques et le dongle, puis les charger si nécessaire.

Fermer un onglet n’arrête pas le système. Stop System ferme aussi par défaut l’environnement Linux utilisé ; sauvegarder d’abord les autres travaux qui pourraient y être ouverts.
