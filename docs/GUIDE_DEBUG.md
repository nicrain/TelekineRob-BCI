# TelekineRob-BCI — Guide de dépannage

[Retour à la présentation du projet](../README.md) · [Version chinoise](GUIDE_DEBUG_cn.md)

> Liste simple d’opérations et de dépannage. Vérifier d’abord l’ordinateur et les appareils, puis utiliser System Control et l’interface de contrôle. System Control est la page ouverte par `launcher.bat` ; elle gère le démarrage, les connexions et le redémarrage des services web.
> Pour un ordinateur déjà installé. Les boutons restent en anglais. Le dépannage courant ne nécessite ni installation, ni modification du programme, ni création d’un nouvel environnement Python.

Accès rapide : [Arrêter d’abord](#arrêter-avant-le-dépannage) · [Vérifications](#1-vérifications-avant-chaque-utilisation) · [Procédure normale](#2-procédure-normale) · [Connexion EEG](#connexion-et-déconnexion-des-eeg) · [EEG sans données](#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage) · [Thymio / Keyboard](#b-le-thymio-ne-bouge-pas) · [Système / interface](#c-état-système-non-vert--interface-inaccessible) · [Calibration / boutons](#d-aucun-nouveau-résultat-de-calibration--boutons-indisponibles) · [Perte de données](#e-perte-de-données--état-gris-ou-failed) · [Nouveau dongle](#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio)

### Arrêter avant le dépannage

Cliquer d’abord sur **Stop en haut de l’interface de contrôle** et vérifier que le robot est immobile, avant de reconnecter un appareil, rebrancher le dongle ou redémarrer la page. Si elle ne répond pas ou si le robot bouge encore, éteindre le Thymio si cela peut être fait en sécurité, puis chercher la cause.

Rafraîchir / fermer la page n’est pas une commande d’arrêt. Même en présence d’une protection contre la perte de données, vérifier l’arrêt réel. Si le contrôle fonctionne encore, le retour des données peut relancer un mouvement.

## 1. Vérifications avant chaque utilisation

Avant démarrage, vérifier Bluetooth, batteries et port USB ; vérifier les rôles une fois l’interface ouverte. Vérifier seulement les appareils utilisés. La simulation ne nécessite ni Thymio réel, ni dongle, ni partage USB.

| Vérification | Comment vérifier | En cas de problème |
|---|---|---|
| 1. Module Bluetooth de l’ordinateur | Clic droit sur Démarrer Windows, **Gestionnaire de périphériques**, rubrique Bluetooth. Le [module intégré](#quel-module-bluetooth-utiliser-pour-les-eeg-) ne doit présenter ni point d’exclamation jaune ou rouge, ni avertissement. | Clic droit sur ce module, **Désactiver**, puis **Activer**. |
| 2. Batteries et alimentation | Headband, Hybrid Black et Thymio chargés ; chargeur de l’ordinateur branché pour réduire les effets possibles de l’économie d’énergie / gestion d’alimentation Windows sur le Bluetooth EEG. | Charger les appareils et brancher le chargeur. |
| 3. Dongle USB Thymio | Branché dans le port USB prévu. | Le remettre dans ce port. |
| 4. Appairage Thymio | Chaque paire Thymio / dongle est normalement déjà appairée ; pas de nouvel appairage en usage courant. | Seulement si l’appairage semble absent, suivre la [procédure officielle](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/). |
| 5. Role | **Un EEG :** première ligne `Speed` ou `Steering`, deuxième `None`. **Deux EEG :** actuellement un Headband + un Hybrid Black, avec `Speed` et `Steering` ; pas de prise en charge directe de deux appareils du même modèle. | Corriger les rôles avant calibration. |
| 6. Python Headband, uniquement s’il est utilisé | Dans **VS Code**, vérifier que l’interpréteur sélectionné est le **venv** existant utilisé pour les essais. | Suivre la [sélection du venv](#sélectionner-le-venv-dans-vs-code), puis exécuter le pont. |
| 7. Nouveau / autre Thymio | Ouvrir PowerShell selon la [section 4](#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio) et lire l’état du **BUSID `1-1`** : `Shared` ou `Attached` signifie que le partage est déjà autorisé. | Si `1-1` manque, rebrancher le dongle puis vérifier. Si `Not shared`, appliquer le partage selon la [section 4](#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio). |

### Quel module Bluetooth utiliser pour les EEG ?

- **Headband :** module Bluetooth intégré de l’ordinateur.
- **Hybrid Black :** son adaptateur Bluetooth USB fourni provoquait des déconnexions fréquentes dans ce projet ; éviter de l’utiliser. Le Hybrid Black utilise lui aussi par défaut le module intégré, plus stable dans cet environnement.

La vérification 1 concerne donc le **module intégré**. Ne pas brancher l’adaptateur Bluetooth USB du Hybrid Black ; **le dongle USB du Thymio reste nécessaire dans le port prévu**.

## 2. Procédure normale

1. Double-cliquer sur `launcher.bat` sous Windows.
2. Dans System Control : si **Stopped**, cliquer sur **Start System** et attendre **Running** en vert. Si déjà Running, continuer sans **Restart System**. Pour **Starting… / Stopping…**, attendre ; pour **Error**, suivre le [dépannage système](#c-état-système-non-vert--interface-inaccessible).
3. Connecter les EEG selon la [procédure ci-dessous](#connexion-et-déconnexion-des-eeg). Pour le robot réel, cliquer sur **Connect** du Thymio. Attendre **Connected** en vert pour les appareils nécessaires.
4. Dans **01 — Input Source**, définir Role selon la [vérification 5](#1-vérifications-avant-chaque-utilisation) ; choisir **Device = EEG** pour chaque ligne active, le bon modèle dans **Brand** et l’indicateur de la session dans **Metric**. Dans **02 — Output Target**, choisir **Thymio** ou **Thymio Simu**.
5. Avant **Calibrate**, poser le Thymio sur une surface plane et sûre, avec de l’espace autour, loin des bords, marches et obstacles. Un mouvement bref reste possible à la fin, même avec l’arrêt automatique à deux EEG. Cliquer sur **Calibrate** de l’appareil, sans Start préalable. **Preparing…** précède le décompte de 30 secondes, qui commence après réception des données. Ne pas déplacer le casque. Avec deux EEG, terminer le premier avant le second. Pour une annulation ou un message, voir les [problèmes de calibration](#d-aucun-nouveau-résultat-de-calibration--boutons-indisponibles).
6. Si **Running…** reste affiché à la fin, cliquer sur **Stop** et vérifier l’immobilité ; puis cliquer sur **Start** pour la commande EEG. Les courbes sont effacées après calibration : ce n’est pas en soi une déconnexion. Elles se remplissent après Start. Voir la [calibration du manuel opérateur](MANUEL_OPERATEUR.md#calibration).
7. À la fin, cliquer d’abord sur **Stop** et vérifier l’arrêt. Si le Headband est utilisé, interrompre son script selon la [déconnexion](#connexion-et-déconnexion-des-eeg). Cliquer enfin sur **Stop System**, attendre Stopped, puis **Exit Launcher**. Voir l’[arrêt complet](MANUEL_OPERATEUR.md#7-arrêter-le-système).

**Start System / Stop System** gèrent l’ensemble du système ; **Start / Stop** en haut de l’interface gèrent la chaîne de contrôle. Running du système signifie que les services web sont prêts, pas que le robot est commandé. Le vert EEG signifie que des données sont détectées ; le vert Thymio signifie que le dongle est accessible et doit être complété par une vérification du mouvement. Les graphiques se mettent à jour pendant calibration ou après **Start** ; **leur absence après la seule connexion est normale**.

Pendant l’utilisation, ne pas retirer le dongle, couper le Bluetooth, déplacer les appareils ou débrancher le chargeur. Voir le [manuel opérateur](MANUEL_OPERATEUR.md) pour le parcours détaillé.

### Connexion et déconnexion des EEG

**Dans ce projet, le pont Headband doit être exécuté et interrompu manuellement dans VS Code sous Windows.**

Connexion :

1. Cliquer sur **Connect** du Headband : `gpype_lsl_bridge.py` s’ouvre dans VS Code.
2. Vérifier l’environnement Python selon la [sélection du venv](#sélectionner-le-venv-dans-vs-code).
3. Cliquer sur le **triangle ▶ en haut à droite de VS Code**. Lorsque le script transmet des données, l’état Headband passe au vert.

Déconnexion :

1. Cliquer sur **Stop** en haut de l’interface.
2. Sélectionner le terminal du script dans VS Code et appuyer sur **Ctrl+C**.
3. Revenir à System Control ; si **Disconnect** du Headband est encore disponible, cliquer dessus.

**Disconnect** et **Stop System** n’interrompent pas le script Headband lancé dans VS Code.

Avant de relancer, faire Ctrl+C dans le terminal d’origine et vérifier que l’ancien script est arrêté. Ne pas multiplier les clics sur ▶ et les instances du pont.

**Hybrid Black : utiliser directement Connect / Disconnect dans System Control.** Cliquer sur **Connect** pour connecter ; arrêter le contrôle avant **Disconnect**. Aucun lancement ou arrêt manuel du script dans VS Code n’est nécessaire.

### Sélectionner le venv dans VS Code

1. Ouvrir `gpype_lsl_bridge.py` dans VS Code sous Windows.
2. Appuyer sur **Ctrl+Shift+P**, saisir et choisir **Python: Select Interpreter**.
3. Sélectionner le **venv** existant utilisé pour les essais et vérifier l’environnement en bas de la fenêtre. Le chemin relevé sur l’ordinateur d’origine est `C:\Users\Robot\Desktop\gpype_test\venv\Scripts\python.exe`. Sur un autre ordinateur, sélectionner son environnement réellement configuré, sans recopier aveuglément ce chemin.
4. Si le script fonctionne déjà, l’interrompre avec **Ctrl+C** puis le relancer avec l’environnement sélectionné.

Ne pas cliquer sur **Create Environment**. Si l’environnement est introuvable, les commandes Python absentes ou le script échoue immédiatement, conserver le message. Ne pas relancer en boucle ni installer des modules sans vérifier l’environnement.

Voir la [sélection officielle VS Code](https://code.visualstudio.com/docs/python/environments#select-an-environment) et l’[exécution des scripts](https://code.visualstudio.com/docs/python/run).

## 3. Résoudre les problèmes courants

Commencer par l’[arrêt du robot](#arrêter-avant-le-dépannage), puis choisir le symptôme correspondant. Vérifier le résultat après chaque étape ; ne pas changer plusieurs réglages à la fois.

### A. Calibration bloquée sur Preparing / aucune courbe après démarrage

Distinguer d’abord les situations normales :

- Appareil simplement connecté, sans Calibrate ni Start : l’absence d’analyse est normale ; continuer la [procédure normale](#2-procédure-normale).
- Juste après calibration, les courbes sont effacées ; elles doivent se remplir avec de nouvelles données après Start.

Si Preparing persiste ou si les graphiques restent vides après démarrage :

1. Suivre les [vérifications préalables](#1-vérifications-avant-chaque-utilisation) : Bluetooth intégré, batteries, chargeur, Role et Brand. Pour le Headband, vérifier aussi le [venv VS Code](#sélectionner-le-venv-dans-vs-code).
2. Cliquer sur **Stop**, puis reconnecter l’appareil selon la [procédure EEG](#connexion-et-déconnexion-des-eeg). Headband : interrompre puis relancer dans VS Code. Hybrid Black : **Disconnect / Connect** dans System Control. Attendre le vert.
3. Vérifier **Device = EEG**, **Brand** et l’appareil réel, puis refaire **Calibrate**. Avec deux EEG, calibrer séparément, puis Stop / Start pour la commande.

Si l’appareil est vert mais les graphiques toujours vides, ne pas conclure au succès d’après la couleur ; conserver le message et noter le symptôme selon [la section 5](#5-si-le-problème-persiste).

### B. Le Thymio ne bouge pas

1. Cliquer sur **Stop**, vérifier que le robot est allumé et le dongle dans le port prévu. Pour un nouveau / autre Thymio, vérifier le partage selon la [section 4](#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio).
2. Vérifier que **Thymio** est vert dans System Control. Pour reconnecter, utiliser **Disconnect** puis **Connect** si les deux étapes sont disponibles ; sinon cliquer directement sur Connect.
3. Vérifier **02 — Output Target = Thymio** et les rôles selon la [vérification 5](#1-vérifications-avant-chaque-utilisation).
4. **Tester le Thymio avec Keyboard, sans EEG, pour vérifier la chaîne robot :**

   - Cliquer sur **Stop**. Dans **01 — Input Source**, première ligne **Role = Speed**, **Device = Keyboard** ; deuxième ligne **Role = None**. Garder un seul rôle et **02 — Output Target = Thymio**.
   - Cliquer sur **Start**. Dans **03 — Teleop Controls**, vérifier **WS connected**, puis maintenir brièvement un bouton d’avance ou de rotation avec la souris et observer le robot. Malgré le nom Keyboard, utiliser les boutons web, pas les flèches du clavier.
   - Au relâchement, le programme envoie une commande d’arrêt ; vérifier l’arrêt réel. Au besoin, cliquer sur **■** au centre ou **Stop** en haut. Si **WS disconnected**, ne pas tester le mouvement : suivre le [dépannage web](#c-état-système-non-vert--interface-inaccessible).
   - Si le robot bouge, sa connexion et la commande de base fonctionnent. Vérifier ensuite les données EEG, rôles, indicateurs et calibration ; sans courbes, suivre le [dépannage EEG](#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage). Des données sans mouvement peuvent simplement correspondre à un indicateur qui ne produit pas de mouvement ; ce n’est pas automatiquement une panne. Si Keyboard échoue aussi, vérifier dongle, partage et appairage.
   - À la fin, cliquer sur **Stop**, remettre **Device = EEG**, rétablir les rôles et appareils de la session, puis calibrer et démarrer.

En cas de doute sur l’appairage, suivre la [procédure officielle de la vérification 4](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/).

En cas de mouvement anormal, suivre l’[arrêt du robot](#arrêter-avant-le-dépannage). Keyboard aide à distinguer la chaîne robot des problèmes EEG ; un mouvement réussi ne valide pas tous les scénarios d’arrêt / perte réseau.

### C. État système non vert / interface inaccessible

1. Arrêter le contrôle et vérifier l’immobilité. Si l’interface est inaccessible ou Stop ne répond pas, suivre l’[arrêt du robot](#arrêter-avant-le-dépannage) ; ne pas rafraîchir la page pour tenter de l’arrêter.
2. Pour **Starting… / Stopping…**, attendre sans clics répétés ; pour **Stopped**, cliquer sur **Start System**. Pour **Error**, lire le message en bas et **View Log**, puis réessayer Start System une fois.
3. Si **Running** est vert mais l’interface absente, cliquer sur **↻ Refresh** ; sinon **Restart Web** et attendre. **Open in new tab** permet aussi de vérifier l’accès séparé.
4. Une fois l’interface rétablie, revérifier Role, Device, Brand, Metric et Output Target, puis calibrer et démarrer selon la [procédure normale](#2-procédure-normale). Le retour de la page ne prouve pas le rétablissement correct de l’ancien contrôle.

En cas d’échecs répétés, conserver messages et logs ; ne pas redémarrer en boucle. Le chargeur de l’ordinateur concerne surtout l’alimentation du Bluetooth EEG ; ce n’est pas une correction de l’état système non vert.

### D. Aucun nouveau résultat de calibration / boutons indisponibles

1. Si Role, Brand, Metric ou Calibrate sont bloqués, vérifier **Running… / Preparing… / Calibrating…**. Certains réglages sont verrouillés pendant le contrôle ou la calibration ; cliquer sur **Stop** avant de les modifier.
2. Recalibrer chaque appareil après changement d’utilisateur, d’appareil ou d’indicateur, ou après annulation avec Stop. Ne pas utiliser un résultat interrompu.
3. Pour **Calibration produced no new values (see node log)**, cliquer sur Stop, vérifier la réception continue des données, rétablir l’[EEG](#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage), puis recalibrer une fois. La fin du décompte ou des valeurs inchangées ne suffisent pas à conclure au succès ; conserver le message s’il se répète.
4. Avec deux rôles, pour **not calibrated. Start anyway?**, annuler et calibrer. Ce message concerne seulement deux rôles ; son absence ne prouve pas une calibration réussie.

Ne pas changer **min / max** pour contourner une erreur ou une perte de données. Si la calibration automatique est faite et seul un réglage fin est nécessaire, suivre l’[ajustement manuel](MANUEL_OPERATEUR.md#ajustement-manuel-des-références-facultatif).

### E. Perte de données / état gris ou Failed

Les étapes suivantes concernent les **EEG**. Si c’est **Thymio** qui devient gris ou Failed, vérifier d’abord l’[arrêt](#arrêter-avant-le-dépannage), puis la [connexion Thymio et le dongle](#b-le-thymio-ne-bouge-pas), sans manipuler les ponts EEG.

1. Cliquer sur **Stop** et vérifier l’arrêt, surtout avec deux EEG ; ne pas seulement attendre le retour d’un appareil.
2. Vérifier alimentation, batteries, chargeur et Bluetooth intégré selon les [vérifications préalables](#1-vérifications-avant-chaque-utilisation). Pour le Headband, vérifier aussi si le script fonctionne encore ou affiche une erreur.
3. Reconnecter selon la [procédure EEG](#connexion-et-déconnexion-des-eeg). Headband : Ctrl+C puis ▶. Hybrid Black : Disconnect puis Connect si disponible, sinon Connect directement.
4. Vérifier le retour des données ainsi que Role, Brand et Metric, refaire la calibration selon la [procédure normale](#2-procédure-normale), puis cliquer sur **Start**. Le vert ne permet pas de reprendre sans avoir vérifié l’arrêt au préalable.

## 4. Vérification 7 : contrôler et partager un nouveau dongle Thymio

Le « partage » consiste à rendre le dongle USB branché sous Windows accessible à Linux (WSL), où s’exécute le programme de contrôle du robot.

À la première utilisation d’un nouveau / autre Thymio, suivre ces étapes. **La configuration actuelle de connexion et de déconnexion utilise le BUSID `1-1`** : c’est donc ce numéro qu’il faut vérifier et partager.

### Vérifier si le partage est déjà autorisé

1. Vérifier que le contrôle est arrêté et brancher le dongle dans le port prévu.
2. Ouvrir **Démarrer** Windows et saisir `PowerShell`.
3. Clic droit sur **Windows PowerShell**, choisir **Exécuter en tant qu’administrateur**, puis **Oui** si une confirmation apparaît.
4. Copier cette ligne dans la fenêtre et appuyer sur **Enter** :

   ```powershell
   usbipd list
   ```

5. Dans la liste USB, trouver **`1-1`** dans **BUSID**, puis lire **STATE**.

   **Si `1-1` manque :** vérifier le port prévu, débrancher et rebrancher le dongle, puis refaire `usbipd list` et vérifier ce numéro.

6. Choisir la suite selon **STATE** :

   | État | Signification | Suite |
   |---|---|---|
   | `Shared` | Partage déjà autorisé | Revenir à System Control et cliquer sur **Connect**. |
   | `Attached` | Partage autorisé et périphérique déjà connecté à WSL | Pas de nouveau partage à configurer ; vérifier l’état Thymio dans System Control. |
   | `Not shared` | Partage non autorisé | Suivre les [étapes ci-dessous](#si-létat-est-not-shared). |

**Connect** du Thymio fait passer le périphérique USB de BUSID **`1-1`** — son dongle — de **Shared** à **Attached**, donc le connecte à Linux (WSL). Après succès, `usbipd list` permet de vérifier cet état.

### Si l’état est Not shared

1. Si **BUSID `1-1`** est `Not shared`, saisir dans le même PowerShell puis appuyer sur **Enter** :

   ```powershell
   usbipd bind --busid 1-1
   ```

2. Saisir cette ligne et appuyer sur **Enter** :

   ```powershell
   usbipd list
   ```

3. Retrouver **BUSID `1-1`** : **STATE** doit être **Shared**, ce qui confirme le partage.
4. Revenir à System Control et cliquer sur **Connect** du Thymio.

Si une commande échoue, si le numéro manque toujours ou si Shared n’apparaît pas, conserver le message complet ; ne pas multiplier les bind ni choisir le numéro d’une autre ligne. Le partage réussi prouve seulement que le dongle peut être transmis à Linux. Vérifier le robot avec le [test Keyboard](#b-le-thymio-ne-bouge-pas).

Les états et commandes sont décrits dans la [documentation officielle usbipd-win](https://github.com/dorssel/usbipd-win/wiki/WSL-support).

## 5. Si le problème persiste

Garder le contrôle arrêté et conserver ces quelques informations pour reproduire et localiser le problème, sans lire le code :

- Étape concernée et message complet / capture d’écran.
- System State, états des trois appareils, appareils réellement utilisés, Role et Output Target.
- Avec Headband, interpréteur choisi et dernière erreur du terminal VS Code ; pour un problème système / web, extrait utile de View Log.
- Pour un nouveau dongle, état de `1-1` dans `usbipd list` ou erreur de commande.

Ne pas modifier le code, supprimer des fichiers, recréer le venv ou changer manuellement de numéro USB pour faire disparaître un message. Si le système n’est plus utilisé, suivre l’[arrêt complet](MANUEL_OPERATEUR.md#7-arrêter-le-système), sans seulement fermer le navigateur.
