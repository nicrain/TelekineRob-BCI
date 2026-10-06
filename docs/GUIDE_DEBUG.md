# GUIDE_DEBUG

[中文版](GUIDE_DEBUG_cn.md)

> Guide simple d'utilisation et de dépannage. Vérifiez d'abord l'ordinateur et les appareils, puis démarrez depuis la page de contrôle général (**System Control**) et la page de commande EEG. System Control est la page qui s'ouvre après un double-clic sur `launcher.bat` ; elle permet de démarrer le système, de connecter les appareils et de redémarrer les services web.

Accès rapide : [Vérifications avant utilisation](#1-vérifications-avant-chaque-utilisation) · [Utilisation normale](#2-utilisation-normale) · [Connexion et déconnexion EEG](#connexion-et-déconnexion-des-appareils-eeg) · [Dépannage](#3-en-cas-de-petit-problème) · [Nouveau dongle Thymio](#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio)

## 1. Vérifications avant chaque utilisation

Avant de démarrer, vérifiez le Bluetooth, la charge des appareils et le port USB. Vérifiez les rôles une fois la page de commande EEG ouverte.

| Point à vérifier | Comment vérifier | En cas de problème |
|---|---|---|
| 1. Module Bluetooth de l'ordinateur | Faites un clic droit sur le bouton Démarrer de Windows, ouvrez le **Gestionnaire de périphériques**, puis développez Bluetooth. Vérifiez que le [module Bluetooth intégré](#module-bluetooth-à-utiliser-pour-les-appareils-eeg) ne présente aucun point d'exclamation jaune ou rouge, ni avertissement. | En cas d'avertissement, faites un clic droit sur ce module, puis **Désactiver** et **Activer**. |
| 2. Charge des appareils et alimentation de l'ordinateur | Headband, Hybrid Black et Thymio sont chargés. Utilisez l'ordinateur avec son chargeur branché, afin de limiter les effets possibles de l'économie d'énergie / gestion de l'alimentation de Windows sur les connexions Bluetooth EEG. | Chargez les appareils et branchez le chargeur de l'ordinateur. |
| 3. Dongle USB Thymio | Le dongle est branché sur le port USB prévu. | Rebranchez-le sur le port USB prévu. |
| 4. Appairage Thymio | Chaque paire Thymio / dongle est déjà appairée par défaut ; il n'est généralement pas nécessaire de refaire l'appairage. | Uniquement si vous soupçonnez un problème d'appairage, essayez de le refaire en suivant la [procédure officielle](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/). |
| 5. Rôles (Role) | **1 EEG :** première ligne `Speed` ou `Steering`, deuxième ligne `None`. **2 EEG :** une ligne `Speed` et l'autre `Steering`. | Ajustez les rôles dans la page avant de calibrer. |
| 6. Environnement Python du Headband | Dans **VS Code**, vérifiez que l'interpréteur Python sélectionné est bien l'environnement **venv** utilisé pour les expériences. | Suivez les [étapes de sélection du venv](#sélectionner-le-venv-dans-vs-code), puis lancez le script passerelle. |
| 7. Utilisation d'un nouveau / autre Thymio | Ouvrez PowerShell selon la [section 4](#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio) et vérifiez l'état du **BUSID `1-1`** par défaut : `Shared` ou `Attached` signifie qu'il est déjà partagé. | Si `1-1` est absent, débranchez puis rebranchez le dongle et vérifiez à nouveau. Si l'état est `Not shared`, suivez la [section 4](#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio) pour le partager. |

### Module Bluetooth à utiliser pour les appareils EEG

- **Headband :** utilisez le module Bluetooth intégré à l'ordinateur.
- **Hybrid Black :** un adaptateur Bluetooth USB est fourni avec l'appareil, mais dans ce projet, son utilisation a entraîné des déconnexions fréquentes. Évitez de l'utiliser. Ici, Hybrid Black utilise aussi par défaut le module Bluetooth intégré à l'ordinateur, qui s'est montré plus stable.

Le point 1 ci-dessus concerne donc **le module Bluetooth intégré à l'ordinateur**. Ne branchez pas l'adaptateur Bluetooth USB fourni avec Hybrid Black ; **le dongle USB Thymio doit, lui, rester branché sur le port USB prévu**.

## 2. Utilisation normale

1. Sous Windows, double-cliquez sur `launcher.bat`.
2. Dans **System Control**, cliquez sur **Start System** et attendez l'état **Running** (vert).
3. Connectez les appareils EEG en suivant les [instructions de connexion et déconnexion](#connexion-et-déconnexion-des-appareils-eeg) ci-dessous. Pour Thymio, cliquez sur **Connect** dans System Control. Attendez que les appareils nécessaires soient en vert.
4. Dans **01 — Input Source** sur la page de commande EEG, réglez les rôles selon le [point 5 de la liste de vérification](#1-vérifications-avant-chaque-utilisation). Pour chaque ligne active, choisissez **EEG** dans **Device**, le modèle utilisé dans **Brand**, et l'indicateur prévu dans **Metric**. Dans **02 — Output Target**, choisissez **Thymio** pour le robot réel ou **Thymio Simu** pour la simulation.
5. Cliquez sur **Calibrate** pour l'appareil. **Preparing…** apparaît d'abord ; le compte à rebours de 30 secondes démarre dès la réception des données. Avec deux EEG, terminez la calibration du premier avant de calibrer le second.
6. Après la calibration, si le haut de la page affiche encore **Running…**, cliquez d'abord sur **Stop** ; cliquez ensuite sur **Start** en haut de la page pour démarrer la commande EEG.
7. À la fin, cliquez d'abord sur **Stop** en haut de la page de commande EEG. Si vous utilisez Headband, interrompez le script passerelle selon les [étapes de déconnexion](#connexion-et-déconnexion-des-appareils-eeg) ci-dessous. Enfin, cliquez sur **Stop System** dans System Control.

**Start System / Stop System** dans System Control démarrent / arrêtent l'ensemble du système. **Start / Stop** en haut de la page de commande EEG démarrent / arrêtent la commande du robot. Un appareil en vert est connecté ; les graphiques se mettent à jour pendant la calibration ou après un clic sur **Start**.

Pendant l'utilisation, ne débranchez pas le dongle USB, ne désactivez pas le Bluetooth, ne déplacez pas les appareils et ne débranchez pas le chargeur de l'ordinateur. Pour les instructions détaillées, consultez le [manuel opérateur](MANUEL_OPERATEUR.md).

### Connexion et déconnexion des appareils EEG

**Headband : en raison des limitations de l'API officielle, le script passerelle doit être lancé et interrompu manuellement dans VS Code.**

Pour connecter :

1. Dans System Control, cliquez sur **Connect** pour Headband. Le script passerelle `gpype_lsl_bridge.py` s'ouvre dans VS Code.
2. Vérifiez l'environnement Python en suivant les [étapes de sélection du venv](#sélectionner-le-venv-dans-vs-code).
3. Cliquez sur le **bouton d'exécution triangulaire (▶), en haut à droite de VS Code**, pour lancer le script ouvert. Une fois les données transmises, l'état de Headband devient vert dans System Control.

Pour déconnecter :

1. Cliquez d'abord sur **Stop** en haut de la page de commande EEG.
2. Dans VS Code, cliquez dans le terminal où le script s'exécute, puis appuyez sur **Ctrl+C** pour l'interrompre.
3. Revenez dans System Control. Si le bouton **Disconnect** de Headband est encore disponible, cliquez dessus.

Les boutons **Disconnect** et **Stop System** de System Control n'interrompent pas à votre place le script passerelle Headband exécuté dans VS Code.

**Hybrid Black : cliquez simplement sur Connect / Disconnect dans System Control.** Pour connecter, cliquez sur **Connect**. Pour déconnecter, arrêtez d'abord la commande, puis cliquez sur **Disconnect**. Il n'est pas nécessaire de lancer ou d'interrompre un script manuellement dans VS Code.

### Sélectionner le venv dans VS Code

1. Dans VS Code sous Windows, ouvrez le script passerelle Headband `gpype_lsl_bridge.py`.
2. Appuyez sur **Ctrl+Shift+P**, saisissez et sélectionnez **Python: Select Interpreter**.
3. Dans la liste, sélectionnez l'environnement **venv** existant utilisé pour les expériences (actuellement `c:\Users\Robot\Desktop\gpype_test\venv\Scripts\python.exe`). Vérifiez en bas de la fenêtre que cet environnement est sélectionné.
4. Si le script est déjà en cours d'exécution, appuyez d'abord sur **Ctrl+C** dans son terminal, puis relancez-le avec l'environnement choisi.

Voir la [documentation officielle de VS Code sur les environnements](https://code.visualstudio.com/docs/python/environments#select-an-environment) et sur [l'exécution des scripts](https://code.visualstudio.com/docs/python/run).

## 3. En cas de petit problème

Avant de reconnecter un appareil, cliquez sur **Stop** en haut de la page de commande EEG.

### A. Calibration bloquée sur Preparing / aucun signal après le démarrage

1. Suivez les [vérifications avant utilisation](#1-vérifications-avant-chaque-utilisation) : module Bluetooth de l'ordinateur, charge des appareils et chargeur de l'ordinateur branché. Vérifiez ensuite Role et Brand. Avec Headband, vérifiez aussi le [venv dans VS Code](#sélectionner-le-venv-dans-vs-code).
2. Cliquez sur **Stop** en haut de la page, puis reconnectez l'appareil concerné selon les [étapes de connexion et déconnexion](#connexion-et-déconnexion-des-appareils-eeg). Pour Headband, interrompez puis relancez le script dans VS Code ; pour Hybrid Black, utilisez **Disconnect / Connect** dans System Control. Attendez que l'appareil soit en vert.
3. Revenez sur la page et cliquez à nouveau sur **Calibrate**.

### B. Thymio ne bouge pas

1. Cliquez d'abord sur **Stop** en haut de la page. Vérifiez que Thymio est allumé et que le dongle est sur le port USB prévu. Pour un nouveau / autre Thymio, vérifiez le partage selon la [section 4](#4-point-7--vérifier-et-partager-un-nouveau-dongle-thymio).
2. Dans System Control, vérifiez que **Thymio** est en vert. Sinon, cliquez sur **Disconnect**, puis **Connect**.
3. Vérifiez que **02 — Output Target** est réglé sur **Thymio** (robot réel) et que les rôles correspondent au [point 5 de la liste de vérification](#1-vérifications-avant-chaque-utilisation).
4. Cliquez à nouveau sur **Start** en haut de la page de commande EEG.
5. **Si Thymio ne bouge toujours pas, testez-le seul avec Keyboard (sans EEG) :**

   - Cliquez d'abord sur **Stop** en haut de la page. Dans **01 — Input Source**, choisissez **Speed** dans **Role** et **Keyboard** dans **Device** sur la première ligne. Sur la deuxième ligne, choisissez **None** dans **Role** pour ne garder qu'un seul rôle actif. Conservez **Thymio** dans **02 — Output Target**.
   - Cliquez sur **Start** en haut de la page. Dans **03 — Teleop Controls**, maintenez un bouton d'avance ou de rotation enfoncé avec la souris et observez le robot. Relâchez le bouton pour l'arrêter.
   - Si le robot bouge, sa connexion et sa commande de base fonctionnent. Vérifiez alors l'EEG selon les [étapes de dépannage EEG](#a-calibration-bloquée-sur-preparing--aucun-signal-après-le-démarrage). Sinon, poursuivez les vérifications du dongle, du partage et de l'appairage.
   - Après le test, cliquez sur **Stop** en haut de la page, remettez **Device** sur **EEG** et rétablissez les rôles et appareils utilisés. Calibrez, puis redémarrez la commande EEG.

Si vous soupçonnez un problème d'appairage entre Thymio et son dongle, essayez de refaire l'appairage selon la [procédure officielle du point 4](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/).

Si le robot effectue des mouvements anormaux, cliquez immédiatement sur **Stop** en haut de la page de commande EEG, puis sur **Stop System** dans System Control.

### C. Le système dans System Control n'est pas en vert / la page ne s'ouvre pas

1. Si l'état est **Starting…**, attendez la fin du démarrage. S'il est **Stopped** ou **Error**, cliquez sur **Start System** pour réessayer.
2. Si le système est déjà en vert (**Running**) mais que la page de commande EEG ne s'affiche pas, cliquez d'abord sur **↻ Refresh**. Si elle reste absente, cliquez sur **Restart Web** et attendez le rechargement.

## 4. Point 7 : vérifier et partager un nouveau dongle Thymio

Ici, « partager » signifie rendre le dongle USB Thymio branché sur l'ordinateur Windows accessible à Linux (WSL), pour que le programme de commande du robot exécuté sous Linux puisse l'utiliser.

Lors de la première utilisation d'un nouveau / autre Thymio, suivez les étapes ci-dessous. **La configuration actuelle de System Control utilise le BUSID `1-1` pour la connexion comme pour la déconnexion** : c'est donc cet identifiant qu'il faut vérifier et partager.

### Vérifier si le dongle est déjà partagé

1. Vérifiez que la commande du robot est arrêtée, puis branchez le dongle USB de ce Thymio sur le port USB prévu.
2. Ouvrez le **menu Démarrer** de Windows et saisissez `PowerShell`.
3. Faites un clic droit sur **Windows PowerShell**, puis choisissez **Exécuter en tant qu'administrateur**. Si une fenêtre de confirmation apparaît, cliquez sur **Oui**.
4. Dans la fenêtre ouverte, copiez la ligne suivante, puis appuyez sur **Entrée** :

   ```powershell
   usbipd list
   ```

5. Une liste des périphériques USB apparaît. Dans la colonne **BUSID**, trouvez l'identifiant par défaut **`1-1`** et consultez la colonne **STATE** (état) de cette ligne.

   **Si `1-1` est absent :** vérifiez que vous utilisez le port USB prévu, débranchez puis rebranchez le dongle sur ce même port. Saisissez à nouveau `usbipd list`, appuyez sur Entrée et vérifiez si cet identifiant apparaît.

6. Selon la valeur de **STATE**, suivez l'action indiquée :

   | État affiché | Signification | Action |
   |---|---|---|
   | `Shared` | Déjà partagé | Revenez dans System Control et cliquez sur **Connect**. |
   | `Attached` | Déjà partagé et connecté à WSL | Inutile de refaire le partage. |
   | `Not shared` | Pas encore partagé | Suivez les [étapes de partage ci-dessous](#si-létat-est-not-shared). |

Dans System Control, cliquer sur **Connect** pour Thymio fait passer le périphérique USB de **BUSID `1-1`** (le dongle USB Thymio) de **Shared** à **Attached**, c'est-à-dire qu'il est connecté à Linux (WSL). Après une connexion réussie, vous pouvez le vérifier avec `usbipd list`.

### Si l'état est Not shared

1. Si l'état du **BUSID `1-1`** est `Not shared`, saisissez la commande suivante dans la fenêtre PowerShell déjà ouverte, puis appuyez sur **Entrée** :

   ```powershell
   usbipd bind --busid 1-1
   ```

2. Saisissez ensuite la ligne suivante et appuyez sur **Entrée** :

   ```powershell
   usbipd list
   ```

3. Retrouvez la ligne **BUSID `1-1`**. Son **STATE** doit maintenant être **Shared** : le partage a réussi.
4. Revenez dans System Control et cliquez sur **Connect** pour Thymio.

Pour les états et les commandes, voir la [documentation officielle d'usbipd-win](https://github.com/dorssel/usbipd-win/wiki/WSL-support).
