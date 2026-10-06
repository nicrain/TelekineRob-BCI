# MANUEL_OPERATEUR

[中文版](MANUEL_OPERATEUR_cn.md)

> Manuel opérateur : vérifications avant utilisation, connexion et calibration, démarrage de la commande EEG, dépannage courant et arrêt. Les noms des boutons restent en anglais, comme dans l'interface, pour les retrouver facilement.

Accès rapide : [Vérifications avant utilisation](#vérifications-avant-utilisation) · [Démarrer le système](#2-démarrer-le-système) · [Connexion et calibration](#3-connexion-des-appareils-et-calibration) · [Démarrer la commande EEG](#4-démarrer-la-commande-eeg) · [Dépannage](#6-dépannage) · [Arrêter le système](#7-arrêter-le-système)

## 1. Présentation et sécurité

### Les deux pages à connaître

**La page de contrôle général (System Control)** s'ouvre après un double-clic sur `launcher.bat` sous Windows. Sa barre latérale permet de démarrer le système, de connecter les appareils et de redémarrer les services web.

**La page de commande EEG (Thymio EEG Control)** s'affiche dans la zone principale de System Control. Vous pouvez aussi l'ouvrir séparément avec **Open in new tab**. Elle permet de sélectionner les appareils et leurs rôles, de calibrer, d'observer les signaux et de commander le robot.

| Emplacement | Bouton | Fonction |
|---|---|---|
| Barre latérale de System Control | Start System / Stop System | Démarrer / arrêter l'ensemble du système |
| Haut de la page de commande EEG | Start / Stop | Démarrer / arrêter le traitement EEG et la commande du robot |

Après la connexion et la calibration, cliquez sur **Start** en haut de la page de commande EEG pour démarrer la commande, voir la [section 4](#4-démarrer-la-commande-eeg).

### Vérifications avant utilisation

1. **Charge des appareils et alimentation de l'ordinateur :** chargez Headband, Hybrid Black et Thymio. Utilisez l'ordinateur avec son chargeur branché, afin de limiter les effets possibles de l'économie d'énergie / gestion de l'alimentation de Windows sur les connexions Bluetooth EEG. Allumez les appareils utilisés.
2. **Bluetooth de l'ordinateur :** faites un clic droit sur le bouton Démarrer de Windows, ouvrez le **Gestionnaire de périphériques**, puis développez Bluetooth. Le module Bluetooth intégré à l'ordinateur ne doit présenter aucun point d'exclamation jaune ou rouge, ni avertissement. En cas d'avertissement, faites un clic droit sur ce module, puis **Désactiver** et **Activer**.
3. **Module Bluetooth pour l'EEG :** Headband et Hybrid Black utilisent tous deux par défaut le Bluetooth intégré à l'ordinateur. L'adaptateur Bluetooth USB fourni avec Hybrid Black a entraîné des déconnexions fréquentes dans ce projet ; évitez de l'utiliser.
4. **Dongle Thymio :** pour le robot réel, branchez le dongle USB sur le port prévu. Chaque paire Thymio / dongle est déjà appairée par défaut ; il n'est généralement pas nécessaire de refaire l'appairage. Uniquement si vous soupçonnez un problème d'appairage, essayez de le refaire en suivant la [procédure officielle](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/).
5. **Nouveau / autre Thymio :** « partager » signifie rendre le dongle USB branché sous Windows accessible au programme de commande du robot sous Linux (WSL). La configuration actuelle utilise le BUSID **`1-1`**. Lors de la première utilisation de son dongle, vérifiez le partage selon les [étapes pour un nouveau dongle](GUIDE_DEBUG.md#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio). Si cet identifiant est absent, débranchez puis rebranchez le dongle sur le port USB prévu et vérifiez à nouveau.
6. **Environnement Python du Headband :** dans VS Code, sélectionnez le venv existant utilisé pour les expériences. Les étapes sont décrites dans [Connexion et déconnexion du Headband](#connexion-et-déconnexion-du-headband).

L'adaptateur Bluetooth USB fourni avec Hybrid Black et le dongle USB Thymio sont deux appareils différents. **Pour le robot réel, le dongle Thymio doit rester branché.**

### Mise en place et rôles

- Nettoyez les zones de contact des électrodes avant de mettre le dispositif. Pour les électrodes humides, utilisez le gel conducteur selon les instructions de l'appareil. Les électrodes sèches n'ont pas besoin de gel ; assurez-vous qu'elles sont bien en contact avec la peau.
- Un seul EEG : une personne utilise un appareil avec **Speed** (avancer / arrêter) ou **Steering** (tourner). Réglez Role sur **None** à la deuxième ligne.
- Deux EEG : attribuez **Speed** à un appareil et **Steering** à l'autre. Une personne gère l'avance / l'arrêt, l'autre la rotation et le changement de direction par clignement des yeux.
- La personne responsable de **Steering** change la direction gauche / droite en clignant des yeux. Évitez les clignements fréquents ou forcés, qui peuvent provoquer plusieurs changements.
- Pendant l'utilisation, ne déplacez pas le dispositif porté ou les électrodes, ne désactivez pas le Bluetooth et ne débranchez ni le dongle ni le chargeur de l'ordinateur. En cas de mouvement anormal du robot, cliquez d'abord sur **Stop** en haut de la page de commande EEG, puis sur **Stop System** dans System Control.

## 2. Démarrer le système

1. Sous Windows, double-cliquez sur `launcher.bat`. Le navigateur ouvre **System Control**.
2. Si le système est **Stopped**, cliquez sur **Start System** dans **Operations**, dans la barre latérale.
3. Attendez que **Starting…** devienne **Running** en vert. La page de commande EEG apparaît dans la zone principale et les boutons de connexion des appareils sont disponibles.
4. Connectez les appareils utilisés selon la [section 3](#3-connexion-des-appareils-et-calibration).

| État du système | Signification | Action |
|---|---|---|
| Stopped | Système non démarré | Cliquez sur Start System |
| Starting… / Stopping… | Démarrage / arrêt en cours | Attendez la fin |
| Running | Services web prêts | Vous pouvez connecter les appareils ; pour la commande EEG, cliquez séparément sur Start en haut de la page |
| Error | Erreur de démarrage ou de service | Consultez le message affiché et suivez le [dépannage](#6-dépannage) |

Quand le système est **Running**, le bouton Start System devient **Restart System**. Il redémarre l'ensemble du système : ne cliquez pas dessus pendant l'utilisation.

## 3. Connexion des appareils et calibration

Une fois le système **Running**, connectez les appareils utilisés dans **Devices**, dans la barre latérale. La connexion de Headband est différente de celle de Hybrid Black.

### Connexion et déconnexion du Headband

En raison des limitations de l'API officielle, le script passerelle Headband doit être lancé et interrompu manuellement dans **VS Code sous Windows**.

Pour connecter :

1. Dans System Control, cliquez sur **Connect** pour Headband. Le script `gpype_lsl_bridge.py` s'ouvre dans VS Code.
2. Appuyez sur **Ctrl+Shift+P**, saisissez et sélectionnez **Python: Select Interpreter**, puis choisissez le **venv** existant utilisé pour les expériences. Vérifiez l'environnement sélectionné en bas de la fenêtre.
3. Cliquez sur le **bouton d'exécution triangulaire (▶), en haut à droite de VS Code**, pour lancer le script passerelle ouvert.
4. Attendez que Headband affiche **Connected** (vert) dans System Control.

Pour déconnecter :

1. Cliquez d'abord sur **Stop** en haut de la page de commande EEG.
2. Dans VS Code, cliquez dans le terminal où le script s'exécute, puis appuyez sur **Ctrl+C** pour l'interrompre.
3. Revenez dans System Control. Si le bouton **Disconnect** de Headband est encore disponible, cliquez dessus.

**Disconnect** et **Stop System** dans System Control n'interrompent pas à votre place le script Headband exécuté dans VS Code. Interrompez l'ancien script avant de le relancer.

### Connexion et déconnexion de Hybrid Black et Thymio

- **Hybrid Black :** dans System Control, cliquez sur **Connect** pour **HybridBlack** et attendez **Connected** (vert). Pour déconnecter, cliquez sur **Disconnect**. Il n'est pas nécessaire de gérer le script manuellement dans VS Code.
- **Thymio :** pour le robot réel, vérifiez qu'il est allumé et que le dongle est sur le port USB prévu, puis cliquez sur **Connect** pour **Thymio**. La simulation ne nécessite pas de connecter un Thymio réel.
- Avant de déconnecter un appareil, cliquez sur **Stop** en haut de la page de commande EEG.

Le bouton **Connect** de Thymio fait passer le dongle USB de **BUSID `1-1`** de **Shared** à **Attached**, c'est-à-dire qu'il est connecté à Linux (WSL).

Un appareil en vert est connecté. Les graphiques se mettent à jour pendant la calibration ou après le démarrage de la commande avec le bouton en haut de la page.

### Choisir les appareils, les rôles et la sortie

Dans **01 — Input Source** sur la page de commande EEG, réglez :

| Champ | Choix |
|---|---|
| Role | Un EEG : première ligne Speed ou Steering, deuxième ligne None. Deux EEG : une ligne Speed et l'autre Steering |
| Device | EEG pour chaque ligne active |
| Brand | g.tec Headband ou g.tec Hybrid Black, selon l'appareil utilisé sur cette ligne |
| Source | LSL Stream |
| Metric | Alpha / TBR / EI selon l'indicateur prévu pour l'expérience |

Dans **02 — Output Target**, choisissez **Thymio** pour le robot réel ou **Thymio Simu** pour la simulation.

### Calibration

1. Dans **03 — Real-time Signals**, trouvez **Calibrate** pour l'appareil concerné et cliquez une fois.
2. **Preparing…** apparaît d'abord. Dès la réception des données d'analyse, le compte à rebours de 30 secondes **Calibrating… Ns** démarre.
3. Attendez la fin de la calibration ; le graphique affiche les références de calibration. Si Preparing reste affiché, suivez le [dépannage](#6-dépannage).
4. Avec deux EEG, terminez la calibration du premier avant de calibrer le second. Les résultats sont conservés séparément pour chaque appareil.
5. Après la calibration, si le haut de la page affiche encore **Running…**, cliquez sur **Stop** en haut, puis démarrez la commande EEG selon la [section 4](#4-démarrer-la-commande-eeg).

## 4. Démarrer la commande EEG

1. Vérifiez que le [choix des appareils et des rôles](#choisir-les-appareils-les-rôles-et-la-sortie) et la [calibration](#calibration) sont terminés.
2. Cliquez sur **Start en haut de la page de commande EEG** et attendez l'état **Running…**.
3. Dans **03 — Real-time Signals**, vérifiez que les signaux et indicateurs de chaque appareil se mettent à jour et observez les mouvements du robot.
4. Pour faire une pause, cliquez sur **Stop** en haut de la page. Pour reprendre, cliquez à nouveau sur **Start** en haut.

## 5. Pendant la commande

- **Speed :** l'indicateur EEG commande l'avance / l'arrêt.
- **Steering :** l'indicateur EEG commande la rotation sur place ; un clignement des yeux change la direction gauche / droite.
- **Deux EEG :** les deux personnes gèrent respectivement la vitesse et la rotation. La perte de données de l'un des appareils déclenche l'arrêt de sécurité du robot.
- **03 — Real-time Signals :** vérifiez que les signaux et indicateurs se mettent à jour et que l'état des appareils est normal.

Pendant la commande, ne recalibrez pas, ne changez pas d'appareil et ne redémarrez pas les services web. Avant tout réglage, cliquez sur **Stop** en haut de la page. À la fin, suivez les étapes pour [arrêter le système](#7-arrêter-le-système).

## 6. Dépannage

Les étapes détaillées sont dans le [guide de dépannage](GUIDE_DEBUG.md). Avant de reconnecter un appareil ou de redémarrer un service, cliquez sur **Stop** en haut de la page de commande EEG.

| Problème | Vérifications et actions |
|---|---|
| Calibration bloquée sur Preparing / aucun signal après le démarrage | Vérifiez le [Bluetooth de l'ordinateur, la charge des appareils et le branchement du chargeur de l'ordinateur](#vérifications-avant-utilisation), puis [Role et Brand](#choisir-les-appareils-les-rôles-et-la-sortie). Pour Headband, interrompez puis relancez le script dans VS Code ; pour Hybrid Black, cliquez sur Disconnect puis Connect dans System Control. Une fois la [connexion rétablie](#3-connexion-des-appareils-et-calibration), recalibrez. |
| Headband reste Connecting après Connect | Connect ouvre seulement le script. Suivez les [étapes de connexion Headband](#connexion-et-déconnexion-du-headband) pour choisir le bon venv et lancer le script manuellement. |
| Perte de données, état gris ou rouge | Vérifiez que les appareils sont allumés et chargés, que le Bluetooth de l'ordinateur fonctionne et que son chargeur est branché. Rétablissez la [connexion de l'appareil concerné](#3-connexion-des-appareils-et-calibration). Avec deux EEG, la perte de données de l'un des appareils déclenche l'arrêt de sécurité du robot. |
| Thymio ne bouge pas | Vérifiez que le robot est allumé, que le dongle est sur le port USB prévu, que Thymio est connecté dans System Control et que Output Target est réglé sur Thymio. Pour un nouveau dongle, vérifiez `1-1` selon les [étapes de vérification du partage](GUIDE_DEBUG.md#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio). Une fois la connexion rétablie, cliquez sur Start en haut de la page. |
| Running est vert, mais la page de commande EEG ne s'affiche pas | Cliquez sur **↻ Refresh** dans System Control. Si elle ne s'affiche toujours pas, cliquez sur **Restart Web** et attendez le rechargement. |
| Start System échoue avec l'état Error | Consultez le message en bas de la page et cliquez sur **View Log** pour voir le journal. Cliquez ensuite sur **Start System** pour réessayer. Pendant Starting, attendez la fin ; ne cliquez pas plusieurs fois de suite. |

## 7. Arrêter le système

1. **Arrêter la commande EEG :** cliquez sur **Stop** en haut de la page de commande EEG pour arrêter la commande du robot.
2. **Arrêter le script Headband :** si vous utilisez Headband, appuyez sur **Ctrl+C** dans le terminal du script dans VS Code. System Control ne l'interrompt pas à votre place.
3. **Arrêter l'ensemble du système :** cliquez sur **Stop System** dans la barre latérale de System Control et attendez **Stopping… → Stopped**.
4. **Quitter le service System Control :** cliquez enfin sur **Exit Launcher**. Ce bouton ferme uniquement le service de contrôle général ; il ne remplace ni Stop ni Stop System.
5. **Ranger les appareils :** éteignez-les. Pour les électrodes humides, nettoyez le gel selon les instructions de l'appareil. Rangez les dispositifs portés et le dongle.
