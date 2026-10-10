# TelekineRob-BCI — Guide développeur

[Retour à la présentation du projet](../README.md)

> Pour les développeurs du projet : installation, localisation du code, diagnostic, modifications et tests, mises à jour, sauvegarde et restauration.

## Documentation du projet

Ce guide explique comment développer et maintenir le système. Le dossier technique définit produit, exigences, algorithmes et interfaces ; le manuel opérateur et le guide de dépannage couvrent usage quotidien et problèmes courants.

### Les cinq documents de référence

| Document | Usage pendant le développement |
|---|---|
| [README du projet](../README.md) | Vue d’ensemble, prérequis et démarrage rapide |
| [Dossier technique](DOSSIER_TECHNIQUE.md) | Produit, exigences, conception, algorithmes, interfaces et critères de recette |
| [Manuel opérateur](MANUEL_OPERATEUR.md) | Reproduire le parcours utilisateur et vérifier l’impact des changements |
| [Guide de dépannage](GUIDE_DEBUG.md) | Éliminer les problèmes courants de matériel / connexion avant le diagnostic du code |
| [Guide développeur, ce fichier](#1-prise-en-main-du-développement) | Installation, code, diagnostic, tests, mises à jour, sauvegarde et restauration |

### Ordre de lecture conseillé

- **Développeurs** : lire le [README](../README.md), puis suivre la [prise en main](#1-prise-en-main-du-développement) pour exécuter l’existant ; comprendre et modifier avec le [dossier technique](DOSSIER_TECHNIQUE.md) et ce guide.
- **Priorité de la prochaine phase** : [deux g.tec du même modèle](#75-priorité--intégrer-deux-gtec-du-même-modèle). Limites, étapes et régressions, pas une fonction déjà réalisée.
- **Licences** : [licence API Hybrid Black](#licence-de-lapi-hybrid-black).
- **Déploiement / maintenance** : [sources officielles](#37-sources-officielles-et-dépendances) · [conditions SDK](#38-conditions-sdk-et-modes-de-connexion) · [filtrage](#54-préfiltrage-des-deux-modèles-eeg) · [sources tierces modifiées](#55-sources-tierces-et-modifications-du-projet) · [migration WSL complète](#93-migration-recommandée--export-et-import-de-wsl-complet).

Le périmètre de validation et la recette sont au [chapitre 4 du dossier technique](DOSSIER_TECHNIQUE.md#4-recette-et-état-de-validation), les limites connues en [section 5.1](DOSSIER_TECHNIQUE.md#51-limites-et-vérifications-prioritaires).

Le format des données de validation est décrit dans la [référence spécialisée](reference/DONNEES_EXPERIMENTALES.md), les champs réels restant ceux du code. Le [répertoire archivé](archived/) conserve anciens guides, historique et plans de recherche, sans constituer les étapes ou exigences actuelles.

## Navigation

- [1. Prise en main](#1-prise-en-main-du-développement) : exécuter, puis comprendre et modifier.
- [2. Environnement et configuration locale](#2-environnement-et-configuration-locale) : référence, versions, chemins et réglages.
- [3. Installation et reconstruction](#3-installation-et-reconstruction-de-lenvironnement) : Windows et WSL séparément.
- [4. Démarrage et diagnostic de développement](#4-démarrage-et-diagnostic-de-développement) : lancement, services web séparés, flux hors ligne.
- [5. Lecture du code et des configurations](#5-lecture-du-code-et-des-configurations) : localiser la couche à modifier.
- [6. Diagnostic par couche et logs](#6-diagnostic-par-couche-et-logs) : appareils jusqu’au robot.
- [7. Modifications et tests](#7-modifications-et-tests) : tests, périmètre, sécurité et [priorité même modèle](#75-priorité--intégrer-deux-gtec-du-même-modèle).
- [8. Mises à jour et publication](#8-mises-à-jour-et-publication) : Git, compilation et synchronisation Windows.
- [9. Sauvegarde et restauration](#9-sauvegarde-et-restauration) : configurations, dépendances et environnement WSL complet.

Les blocs indiquent l’environnement d’exécution. Ne pas copier PowerShell dans Bash WSL. `<…>` désigne un élément à remplacer, pas à exécuter tel quel. Installation, calibration, sauvegarde web, mise à jour et restauration changent l’état : arrêter le contrôle et sauvegarder les réglages concernés avant.

## 1. Prise en main du développement

Pour commencer, suivre cet ordre sans devoir lire tous les documents historiques :

1. Vérifier interpréteurs, chemins, matériel et port USB selon l’[environnement](#2-environnement-et-configuration-locale), puis sauvegarder. SDK et licences : [section 3](#3-installation-et-reconstruction-de-lenvironnement).
2. Effectuer démarrage, test Keyboard Thymio, connexion EEG, calibration, contrôle et arrêt selon le [manuel opérateur](MANUEL_OPERATEUR.md). En cas de problème courant, consulter d’abord le [dépannage utilisateur](GUIDE_DEBUG.md).
3. Lire la [conception](DOSSIER_TECHNIQUE.md#3-conception-du-système), puis suivre la [lecture du code](#5-lecture-du-code-et-des-configurations) d’un appareil de LSL à `/cmd_vel`.
4. Exécuter les [tests par couche](#7-modifications-et-tests), en distinguant logique pure, services simulés et matériel réel.
5. Réaliser un petit changement bien délimité sur une copie de développement, vérifier puis suivre les [mises à jour](#8-mises-à-jour-et-publication). Pour deux appareils identiques, commencer par le SDK suivant la [feuille de route](#75-priorité--intégrer-deux-gtec-du-même-modèle), sans essais hasardeux sur l’installation utilisée.
6. Vérifier la [restauration](#9-sauvegarde-et-restauration) dans un environnement indépendant, sans écraser le système en service.

Trois distinctions essentielles :

- **System Control ≠ interface EEG** : le premier gère système, ponts et USB ; la seconde rôles, sortie, calibration, Start / Stop et Teleop.
- **Connexion ≠ contrôle** : vert EEG = échantillons frais reçus par la sonde ; graphiques pendant calibration ou contrôle. Vert Thymio = surtout `/dev/ttyACM0` visible, pas preuve de réponse du robot.
- **Code ≠ configuration d’exécution** : web et calibration modifient les YAML ; le JSON Windows local n’est pas écrasé par synchronisation. Sauvegarder avant les tests et ne pas laisser leurs paramètres dans l’environnement utilisé.

## 2. Environnement et configuration locale

### 2.1 Référence d’environnement et vérifications

Ce sont les références du projet, pas un inventaire complet d’un ordinateur particulier. Avant déploiement, migration ou mise à niveau, vérifier versions et chemins réels, sans assimiler le modèle à la configuration locale.

| Élément | Référence / entrée actuelle | À vérifier |
|---|---|---|
| Code / branche | [Dépôt](https://github.com/nicrain/TelekineRob-BCI), déploiement depuis `main` | Branche, commit, modifications locales |
| Windows / WSL | Windows + WSL2 | Version WSL, nom enregistré, mode réseau |
| Ubuntu / ROS | Ubuntu 24.04 / ROS2 Kilted | Version système et `ROS_DISTRO`, sans mélange de distributions ROS |
| Python WSL | Python 3.12 ; `.venv` racine | Chemin, compatibilité ROS Python et [imports](#34-environnement-python-wsl-et-frontend) |
| Python Windows | `python` dans le modèle launcher et les deux `python_cmd` | Interpréteurs réels launcher, ponts, sondes, VS Code ; version / architecture SDK |
| SDK | `gpype` Headband, `UnicornPy` Hybrid | Versions en [3.1](#31-prérequis-windows), installation / licences en [3.8](#38-conditions-sdk-et-modes-de-connexion) |
| Node / npm | Vite 5, React 18, lockfile npm | Versions existantes, installation selon lockfile, sans mise à niveau systématique |
| USB / robot | usbipd-win, BUSID `1-1`, `/dev/ttyACM0` | Port prévu, Shared / Attached, droits série |
| Gazebo / Aseba | Paquets ROS Gazebo ; pilotes ROS Thymio / Aseba du dépôt | Dépendances et versions, garder les [modifications tierces](#55-sources-tierces-et-modifications-du-projet) |
| Réseau / données | [Réseau](#36-réseau-et-périmètre-daccès), [logs](#64-emplacements-des-logs-et-rapport-de-panne), [sauvegarde](#9-sauvegarde-et-restauration) | Accès réels, emplacements et conservation |

Les commandes suivantes sont en lecture seule. Avant partage des sorties, retirer noms personnels, appareils ou adresses internes inutiles ; ne pas publier identifiants ou tokens.

Windows PowerShell :

```powershell
wsl --version
wsl -l -v
usbipd --version
Get-Command python, pythonw, code, usbipd
python --version
```

WSL Bash, racine du dépôt réellement utilisé :

```bash
git status --short --branch
git rev-parse HEAD
lsb_release -ds
python3 --version
.venv/bin/python --version
node --version
npm --version
source /opt/ros/kilted/setup.bash
printenv ROS_DISTRO
```

`python --version` sous Windows ne décrit que l’interpréteur du terminal. Vérifier chaque `python_cmd` effectif et séparément l’interpréteur sélectionné dans VS Code.

### 2.2 Chemins et modèle de configuration

| Élément | Valeur du modèle / entrée | Vérification requise |
|---|---|---|
| Nom WSL | `Ubuntu` | Nom enregistré, pas version ; vérifier `wsl -l -v` |
| Dépôt WSL | `/home/robot/TelekineRob-BCI` | Chemin modèle, pas preuve de l’emplacement cible |
| Cible Windows | `C:\Users\Robot\Desktop\gpype_test\TelekineRob-BCI` | Répertoire réel du projet Windows |
| Source WSL de synchronisation | `\\wsl$\Ubuntu\home\robot\TelekineRob-BCI` | Cohérence distribution, utilisateur et dépôt |
| Configuration Windows locale | `windows_launcher/config.json` dans la copie Windows | Sauvegarder le fichier réel ; ne pas écraser avec le modèle |
| Entrée utilisateur | `windows_launcher/launcher.bat` Windows | Copie visée par le raccourci |
| Paramètres ROS | Trois YAML de `thymio_control/config/` | Rôles, appareils, indicateurs, vitesses et calibration confirmés |
| Ports | launcher 8020, backend 8010, frontend 5173 | Occupation, URL réelle et pare-feu |

Champs JSON et résolution des placeholders : [notice launcher](../windows_launcher/README.md). Échapper les antislashs des chemins Windows dans JSON. Le fichier contient des commandes exécutables et doit être modifié uniquement par des mainteneurs de confiance.

### 2.3 Conventions de déploiement matériel

- Les EEG de l’ordinateur d’origine utilisent le Bluetooth intégré. Vérifier à nouveau après changement d’ordinateur ou ajout d’appareils ; voir les raisons en [3.8](#38-conditions-sdk-et-modes-de-connexion).
- Le dongle Thymio utilise le port prévu et BUSID `1-1`. Si ce numéro ne peut réellement pas être conservé après migration, le développeur doit vérifier et mettre à jour ensemble connexion, déconnexion, sonde et manuels utilisateur.

Préparation, connexion et rôles : [manuel opérateur](MANUEL_OPERATEUR.md). Bluetooth, appairage et nouveau partage : [dépannage](GUIDE_DEBUG.md).

## 3. Installation et reconstruction de l’environnement

Pour un nouvel ordinateur ou une restauration. Sur un système fonctionnel, [sauvegarder](#9-sauvegarde-et-restauration) avant toute action ; ne pas réinstaller / mettre à niveau simplement pour uniformiser. Les documents officiels guident l’installation système ; commandes spécifiques et configuration réelle du projet restent la référence.

### 3.1 Prérequis Windows

1. Préparer WSL2 / Ubuntu 24.04 et noter le nom enregistré. Ne pas remplacer le couple Ubuntu / ROS validé parce qu’une installation propose une nouvelle version par défaut.
2. Installer usbipd-win et vérifier la commande. Le partage USB n’est pas natif dans WSL ; voir [Microsoft USB](https://learn.microsoft.com/en-us/windows/wsl/connect-usb) pour installation et droits. Ses BUSID sont des exemples ; le projet utilise toujours `1-1`.
3. Préparer Python / Pythonw, VS Code et la commande `code`. Restaurer `gpype`, `UnicornPy`, pilotes et licences selon les SDK fournis. Version, architecture Python et compatibilité `.pyd` doivent correspondre. Sources en [3.7](#37-sources-officielles-et-dépendances), conditions / connexions en [3.8](#38-conditions-sdk-et-modes-de-connexion).
4. Vérifier les Python des ponts et sondes. `requirements.txt` racine ne contient pas les deux SDK et n’est pas une liste complète d’installation Windows.
5. Reproduire les ponts existants avec Bluetooth intégré et appareils appairés. Ne pas lancer plusieurs ponts pour un même appareil ni changer automatiquement de SDK pour tester au hasard.

Windows PowerShell : `python` doit être l’interpréteur de l’appareil concerné ; sinon utiliser le chemin relevé.

```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
python -c "import pylsl; import gpype; print('Headband imports OK')"
python -c "import pylsl; import numpy; import UnicornPy; print('Hybrid imports OK')"
```

Les appareils peuvent avoir des environnements différents ; vérifier les imports séparément. Pour un chemin avec espaces, PowerShell utilise `& "C:\chemin réel\python.exe" ...`. Ne pas copier cette syntaxe dans `python_cmd` du launcher ; voir [config.py](../windows_launcher/config.py) et [commands.py](../windows_launcher/commands.py).

Version g.Pype, dans l’environnement réellement utilisé par le pont Headband, sous PowerShell :

```powershell
python -m pip show gpype
```

Chemin Python et version API Hybrid, sans connexion EEG, dans son environnement PowerShell :

```powershell
python -c "import sys, UnicornPy; print(sys.executable); print(UnicornPy.GetApiVersion())"
```

Noter séparément versions Suite et API UnicornPy ; ce ne sont pas les informations du produit sous licence. `GetApiVersion()` ne prouve ni activation ni droit de concurrence à deux appareils. Voir la [licence](#licence-de-lapi-hybrid-black). En cas d’échec d’import, diagnostiquer l’environnement sans désactiver une licence pour essayer.

### 3.2 Prérequis WSL et ROS

Ubuntu 24.04 / ROS2 Kilted : [installation officielle](https://docs.ros.org/en/kilted/Installation/Ubuntu-Install-Debs.html), ou [source du même document](https://github.com/ros2/ros2_documentation/blob/kilted/source/Installation/Ubuntu-Install-Debs.rst) si la page est inaccessible. Préparer dépôts et outils selon cette version, sans mélanger les commandes d’autres distributions ROS.

Vérifier systemd dans WSL ; voir [Microsoft systemd](https://learn.microsoft.com/en-us/windows/wsl/systemd). S’il est déjà actif, ne rien changer. Si nécessaire seulement, éditer `/etc/wsl.conf` en conservant les autres réglages :

```ini
[boot]
systemd=true
```

Appliquer la configuration de démarrage exige un redémarrage ; sauvegarder et arrêter les autres tâches avant. Le launcher vérifie `systemctl is-system-running` et dispose d’un repli sur l’accès au partage. `degraded` peut permettre de poursuivre mais exige de comprendre les services en échec ; ce n’est pas un état entièrement sain.

WSL Bash :

```bash
systemctl is-system-running
source /opt/ros/kilted/setup.bash
command -v ros2
command -v colcon
command -v rosdep
```

Les manifests déclarent les dépendances, mais certains anciens paquets tiers peuvent être incomplets. Par exemple, le CMake d’`asebaros` exige LibXml2 : rosdep sans erreur ne prouve pas que toutes les dépendances de compilation existent. Diagnostiquer avec l’erreur, CMake / package.xml, puis noter les installations réelles. Ne pas ignorer tout le pilote pour présenter une compilation comme réussie.

### 3.3 Récupération du code et première compilation

Nouvelle installation : depuis le répertoire parent WSL choisi. Ne pas recloner dans un dépôt existant. Le nom utilisateur n’a pas à être `robot` ; reporter ensuite les chemins réels dans Windows.

```bash
git clone --branch main https://github.com/nicrain/TelekineRob-BCI.git TelekineRob-BCI
cd TelekineRob-BCI
git rev-parse HEAD
source /opt/ros/kilted/setup.bash
```

Préparer rosdep selon la documentation ROS. `sudo rosdep init` uniquement si non initialisé. Après mise à jour de l’index, vérifier puis installer les dépendances déclarées, dans WSL à la racine :

```bash
rosdep update
rosdep check --from-paths src thymio_control --ignore-src --rosdistro kilted
rosdep install --from-paths src thymio_control --ignore-src --rosdistro kilted -y
colcon build --symlink-install
source install/setup.bash
ros2 pkg prefix thymio_control
ros2 pkg executables thymio_control
```

La première compilation inclut Thymio / Aseba dans `src/`, pas seulement `thymio_control`. Les deux dernières commandes doivent retrouver le paquet de cet espace et `eeg_control_node.py`, `cmd_vel_fuser.py`. En cas d’échec, conserver erreur complète et logs, résoudre les dépendances puis réessayer.

Compiler avec Python du ROS système, sans priorité donnée à une autre version ou à Conda.

### 3.4 Environnement Python WSL et frontend

WSL Bash, racine du dépôt, pour une réinstallation depuis les sources. Vérifier un `.venv` existant avant de le remplacer. En reconstruction, recréer le venv plutôt que le copier seul entre ordinateurs. Une [importation WSL complète](#93-migration-recommandée--export-et-import-de-wsl-complet) peut conserver l’environnement Linux ; le vérifier avant toute suppression / recréation systématique :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
source /opt/ros/kilted/setup.bash
source install/setup.bash
python -c "import sys; print(sys.executable); import rclpy, pylsl, numpy, scipy, fastapi, yaml; print('WSL imports OK')"
```

L’interpréteur doit venir du `.venv` du dépôt et les imports réussir. `rclpy` vient de ROS : ne pas tenter un `pip install rclpy` arbitraire. Vérifier environnement ROS chargé, ABI Python et compilation. Si `pylsl` signale liblsl absent, vérifier le chargement de la bibliothèque native ; pip réussi ne prouve pas LSL opérationnel.

Installer le frontend sous WSL, avec Node / npm vérifiés et le lockfile :

```bash
cd web_gui/frontend
npm ci
npm run build
```

Installation / compilation ne valident ni interface, ni WebSocket, ni Gazebo, ni robot. Examiner et committer séparément les ajouts / mises à niveau de dépendances et leur lockfile ; ne pas le régénérer à chaque déploiement.

### 3.5 Premier déploiement du launcher Windows

1. Copier `windows_launcher` du dépôt WSL dans le répertoire Windows choisi et créer le raccourci. L’Explorateur peut accéder à `\\wsl$\<distribution>\<chemin du dépôt>` pour cette première copie.
2. Éditer le JSON Windows : source, cible, dépôt WSL, nom enregistré et noms de distribution inclus dans toutes les commandes doivent correspondre. Vérifier `devices.thymio.attach_cmd` et `verify_cmd`, pas seulement `wsl.distro`.
3. Définir un `python_cmd` utilisable pour chaque appareil. Le Python Headband VS Code et celui de la sonde doivent avoir leurs dépendances ; `open_in_ide` ne sélectionne pas l’environnement à la place de l’utilisateur.
4. Vérifier les chemins ROS, install et venv de `web.backend_cmd` et la disponibilité npm de `frontend_cmd`.
5. Vérifier le partage du dongle dans le port prévu, BUSID `1-1`, avant de configurer la connexion Thymio ; voir le [guide de dépannage](GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio).
6. Lancer par double-clic, vérifier services et appareils selon le [manuel opérateur](MANUEL_OPERATEUR.md), puis sauvegarder le JSON réel. Diagnostic complémentaire : [section 6](#6-diagnostic-par-couche-et-logs).

`attach_cmd` transmet le périphérique `1-1` de Shared à WSL (Attached) ; `verify_cmd` vérifie `/dev/ttyACM0`. Vérifier ensemble les deux commandes si port ou distribution change.

Chaque Start System synchronise `windows_launcher/`, hors `config.json`, et `gtec_bridge/` de WSL vers Windows. Il n’installe ni SDK ni dépendances, ne compile pas ROS, ne fait pas Git pull et ne remplace pas la configuration locale.

### 3.6 Réseau et périmètre d’accès

Vérifier d’abord le fonctionnement local avant le LAN. Par défaut : launcher `127.0.0.1:8020`, backend `127.0.0.1:8010`, frontend Vite `0.0.0.0:5173`, avec proxy `/api` et `/ws`.

Le launcher tente de mettre à jour la redirection Windows de 5173. Un échec ne bloque pas nécessairement Running. Vérifier mode réseau WSL, redirection et pare-feu réels ; ne pas généraliser la solution d’un ordinateur à toutes les configurations WSL.

| Variable backend | Défaut / modèle actuel | Attention |
|---|---|---|
| `WEB_GUI_HOST` / `WEB_GUI_PORT` | `127.0.0.1` / `8010` | L’écoute loopback peut rester accessible au LAN via Vite |
| `WEB_GUI_FRONTEND_ORIGIN` | Origins locaux par défaut backend ; modèle launcher : `*` | `*` relâche la vérification, sans authentification |
| `WEB_GUI_CONTROL_TOKEN` | Vide | Certains endpoints le prennent en charge ; pas gestion globale des droits |
| `WEB_GUI_ALLOW_REAL_COMMANDS` | `true` | `false` restreint lancement / nettoyage des processus, pas publication Teleop directe |

Utiliser uniquement un réseau de confiance vérifié. Loopback, token et dry-run ne prouvent pas que toutes les interfaces de contrôle / configuration sont protégées. Voir les [limites réseau techniques](DOSSIER_TECHNIQUE.md#312-réseau-commandes-et-données) et risques du proxy. Ne pas déployer le système actuel comme service public de commande sur Internet.

### 3.7 Sources officielles et dépendances

Ces entrées fabricant / mainteneur servent à installer, consulter les API et maintenir. Les pages évoluent ; leur version n’est pas celle installée. Vérifier d’abord l’existant et restaurer selon sa version, sans mise à niveau directe depuis le dernier exemple.

| Appareil / composant | Sources officielles ou amont | Usage dans le projet |
|---|---|---|
| Headband | [BCI Core-4](https://www.gtec.at/product/unicorn-bci-core-4-headband/), [g.Pype GitHub](https://github.com/gtec-medical-engineering/gpype), [documentation](https://gpype.gtec.at/index.html), [formation / exemples](https://gpype.gtec.at/content/2_gpype_training/index.html), [SDK](https://gpype.gtec.at/content/7_sdk_reference/index.html) | Installation, acquisition et filtres ; le projet utilise son pont gpype, pas le programme de démonstration officiel comme entrée |
| Conditions g.Pype | [FAQ](https://gpype.gtec.at/content/5_faq/index.html), [licence GNCL](https://github.com/gtec-medical-engineering/gpype/blob/main/LICENSE-GNCL.txt) | Usage individuel / pédagogique dans IDE versus Runtime ; parcours manuel VS Code conservé |
| Hybrid Black | [Produit](https://www.gtec.at/product/unicorn-hybrid-black-bci-platform/), [Windows APIs](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs), [installation / usage Python](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api.md), [référence Python](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md) | Bibliothèque, compatibilité Python / binaires, découverte, numéro de série et acquisition ; seuls huit canaux EEG sont transmis en LSL |
| Unicorn Suite Hybrid Black | [Installation, Bluetooth, licences, appairage](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md), [installateurs du mainteneur](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/releases) | Pilotes / API Windows et licences ; utiliser les informations de Lucas, sans assimiler une licence d’application Suite à celle de l’API Python |
| Thymio | [Site français](https://www.thymio.org/fr/), [Thymio Suite](https://www.thymio.org/fr/telecharger-thymio-suite/), [programmation / usage](https://www.thymio.org/fr/produits/programmer-avec-thymio-suite/), [appairage dongle](https://www.thymio.org/fr/faq/comment-configurer-lappairage-du-thymio-sans-fil-avec-son-dongle/) | Maintenance, outils fabricant, appairage si nécessaire ; mouvements envoyés par ROS, sans démarrage de contrôle requis dans Suite |
| ROS2 Kilted | [Documentation](https://docs.ros.org/en/kilted/), [installation Ubuntu](https://docs.ros.org/en/kilted/Installation/Ubuntu-Install-Debs.html), [source officielle](https://github.com/ros2/ros2_documentation/blob/kilted/source/Installation/Ubuntu-Install-Debs.rst) | Ubuntu 24.04 / ROS2, colcon et diagnostic ; conserver la distribution du projet |
| ROS-Aseba / asebaros | [jeguzzi/ros-aseba](https://github.com/jeguzzi/ros-aseba), [documentation mainteneur](https://jeguzzi.github.io/ros-aseba/) | Interface générale ROS ↔ réseau Aseba ; sources dans `src/ros-aseba`, avec Aseba / Dashel imbriqués |
| ROS-Thymio | [jeguzzi/ros-thymio](https://github.com/jeguzzi/ros-thymio), [documentation du même mainteneur](https://jeguzzi.github.io/ros-aseba/) | Pilote, messages et modèle au-dessus d’asebaros ; paquets de `src/ros-thymio` compilés avec colcon, pas installés par pip |
| Windows / WSL / USB | [Commandes WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands), [importation](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro), [USB dans WSL](https://learn.microsoft.com/en-us/windows/wsl/connect-usb) | Export / import Linux et usbipd ; BUSID / chemins selon configuration réelle et manuels du projet |

Les branches et anciens tutoriels ROS-Aseba / ROS-Thymio contiennent de l’historique ROS1 ; ce pilote du projet n’est pas publié directement par le fabricant Thymio. Utiliser en priorité les sources suivies et versions figées du projet ; voir [5.5](#55-sources-tierces-et-modifications-du-projet). Les documents officiels expliquent les interfaces mais ne remplacent pas configuration, compilation, arrêt et recette du projet.

### 3.8 Conditions SDK et modes de connexion

#### Headband / g.Pype

La [FAQ officielle](https://gpype.gtec.at/content/5_faq/index.html) décrit l’usage gratuit individuel et pédagogique dans un IDE, et le besoin de g.Pype Runtime pour le déploiement commercial. Respecter les [conditions GNCL](https://github.com/gtec-medical-engineering/gpype/blob/main/LICENSE-GNCL.txt) de la version concernée. Le projet conserve le lancement humain dans un IDE ; vérifier la licence avant tout changement de déploiement.

Avant mise à niveau, vérifier interfaces et noms de classes du pont existant plutôt que les remplacer d’après une documentation récente. Version : [3.1](#31-prérequis-windows). Chemin et sélection du venv sont maintenus uniquement dans le [guide de dépannage](GUIDE_DEBUG.md#sélectionner-le-venv-dans-vs-code).

#### Hybrid Black / UnicornPy

Préparer pilotes et API Python selon les documents Suite / DevTools de la version ; chargement décrit dans l’[installation officielle](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api.md). Le répertoire de `UnicornPy.pyd` doit être chargeable par l’interpréteur réel, avec `PYTHONPATH` selon la notice. Vérifier Python, architecture et bibliothèques natives. La liste pip racine seule ne déploie pas ce SDK. Imports et version : [3.1](#31-prérequis-windows).

Connexion / processus : [conception 3.4](DOSSIER_TECHNIQUE.md#34-connexions-des-appareils). Modifications pour deux appareils identiques : [7.5.2](#752-limites-actuelles-et-fichiers-à-modifier).

##### Licence de l’API Hybrid Black

Le projet possède deux licences API Hybrid Black, demandées par Lucas, qui détient leurs informations. La première est activée sur l’ordinateur Windows d’origine ; **la deuxième n’est pas activée**. Pour déploiement / migration, demander à Lucas produit exact, conditions et identifiants. Deux licences ne signifient ni « une licence obligatoire par EEG » ni autorisation déjà confirmée de deux acquisitions concurrentes sur une machine.

Consulter l’état dans **Unicorn Suite Hybrid Black → Licenses**. Activation / désactivation selon la [notice officielle de la version](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md#licensing). Ne pas désactiver pour simplement vérifier. Avant migration, confirmer avec Lucas conditions et interruption de service. Clés complètes, emails d’achat et comptes se transmettent par canal contrôlé, pas dans Git, logs ou captures publiques.

#### Choix du Bluetooth

Le Bluetooth intégré a été retenu sur l’ordinateur d’origine pour la stabilité constatée. Ce choix diffère de la [notice fabricant](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornSuite.md#bluetooth-configuration) recommandant l’adaptateur fourni. Revérifier après migration ou ajout d’appareils ; tous les modules intégrés ne sont pas supposés compatibles.

## 4. Démarrage et diagnostic de développement

### 4.1 Démarrage et arrêt normaux

Suivre le [manuel opérateur](MANUEL_OPERATEUR.md) pour démarrage, appareils, calibration, contrôle et fermeture. En développement :

- Ne pas lancer une deuxième copie des services / chaîne depuis un terminal si elle existe déjà.
- Le script Headband VS Code reste hors gestion launcher et exige une interruption manuelle.
- Stop System termine par défaut toute la distribution WSL configurée ; sauvegarder ses autres tâches.
- Arrêter le contrôle et vérifier l’immobilité avant Restart Web ; ce bouton ne remplace pas Stop.

### 4.2 Démarrer séparément backend et frontend

Uniquement si le launcher ne supervise pas ces services. Le backend ci-dessous est un service réel, avec commandes réelles actives par défaut ; vérifier d’abord l’absence de contrôle du matériel.

Utiliser deux terminaux distincts, tous deux initialement à la racine du projet.

#### Backend (terminal A, WSL Bash)

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

#### Frontend (terminal B, WSL Bash)

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

Frontend : `http://localhost:5173`. Santé backend : `http://localhost:8010/api/health`, pas `/health`. Vérifier `subscriber_error` même si `subscriber_ready` est vrai. Réponse web, disponibilité ROS, réception EEG et mouvement doivent être vérifiés séparément.

Ctrl+C arrête le processus du terminal. La chaîne créée par Start web doit d’abord être arrêtée par Stop web. Fermer le navigateur n’arrête pas le robot.

### 4.3 Validation hors ligne sans appareils

Outils dans `thymio_control/lsl_test/`, pas `lsl_test/` à la racine. Ils ne remplacent pas ponts Windows réels, Bluetooth, réseau entre systèmes ou USB.

Dans un environnement de test indépendant, arrêter les ponts réels, isoler la sortie matérielle et sauvegarder les trois YAML. WSL Bash, racine :

```bash
source .venv/bin/activate
python thymio_control/lsl_test/dummy_dual_streams.py --blink
```

Deux flux synthétiques `gtec_bci_core4` et `gtec_hybrid_black`, 250 Hz chacun, jusqu’à Ctrl+C. Même source_id que les ponts réels : pas de mélange laissant le choix du flux au hasard.

Après démarrage web dans un autre terminal, choisir Headband / Hybrid Black, Speed / Steering et explicitement **Thymio Simu**, puis Start ; vérifier graphiques et réponses synthétiques. Pas besoin d’états Windows tous verts, puisque l’entrée est produite dans WSL. La sauvegarde web modifie encore les YAML. Restaurer les paramètres après et ne pas conserver de calibration synthétique pour un utilisateur réel.

Pour observer le launch, après Stop web, remplacer Start par un lancement manuel :

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
ros2 launch thymio_control experiment_core.launch.py --show-args
ros2 launch thymio_control experiment_core.launch.py use_sim:=true run_eeg:=true run_eeg2:=true use_teleop:=false input:=lsl role:=speed eeg2_input:=lsl eeg2_role:=steering
```

Les deux fichiers EEG installés doivent déjà viser deux source_id synthétiques distincts et ne contenir aucune calibration résiduelle. Les arguments ci-dessus ne changent pas les source_id. Résoudre les dépendances Gazebo / ROS avant d’attribuer un échec au matériel. Quitter le launch, arrêter les flux, restaurer la configuration et vérifier l’absence de nœuds de contrôle résiduels.

## 5. Lecture du code et des configurations

### 5.1 Localiser une fonction dans le code

Le tableau est un point d’entrée pour diagnostiquer ou ajuster, pas une liste de nouvelles exigences / corrections. Il n’impose pas de modifier tous les fichiers cités.

| Fonction / cible du diagnostic | Entrées principales |
|---|---|
| Launcher, connexion et états | [launcher_server.py](../windows_launcher/launcher_server.py), [commands.py](../windows_launcher/commands.py), [state.py](../windows_launcher/state.py), [lsl_probe.py](../windows_launcher/lsl_probe.py) |
| Acquisition / reconnexion EEG | [gpype_lsl_bridge.py](../gtec_bridge/gpype_lsl_bridge.py), [unicornpy_lsl_bridge.py](../gtec_bridge/unicornpy_lsl_bridge.py) |
| Filtres, puissances, indicateurs | [lsl_raw.py](../thymio_control/thymio_control/adapters/lsl_raw.py), [band_power.py](../thymio_control/thymio_control/processors/band_power.py), [enrich.py](../thymio_control/thymio_control/processors/enrich.py) |
| Stratégies et conversion vitesse / direction | [policies/](../thymio_control/thymio_control/policies/), [pipeline.py](../thymio_control/thymio_control/pipeline.py), [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py) |
| Calibration / clignements | [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py), [calibration.py](../thymio_control/thymio_control/calibration.py), [blink_metric.py](../thymio_control/thymio_control/processors/blink_metric.py) ; [App.jsx](../web_gui/frontend/src/App.jsx) si UI concernée |
| Fusion et perte de données | [cmd_vel_fuser.py](../thymio_control/scripts/cmd_vel_fuser.py), [watchdog.py](../thymio_control/thymio_control/watchdog.py), [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py) |
| UI et sauvegarde | [App.jsx](../web_gui/frontend/src/App.jsx), [models.py](../web_gui/backend/app/models.py), [config_store.py](../web_gui/backend/app/config_store.py) |
| Affichage ROS / Teleop | [signal_subscriber.py](../web_gui/backend/app/signal_subscriber.py), [main.py](../web_gui/backend/app/main.py) |
| Lancement, réel / simulation | [command_runner.py](../web_gui/backend/app/command_runner.py), [experiment_core.launch.py](../thymio_control/launch/experiment_core.launch.py) |

La détection actuelle par indicateur est dans `blink_metric.py`, pas l’ancien `blink.py`. Responsabilités, algorithmes et interfaces : [conception technique](DOSSIER_TECHNIQUE.md#3-conception-du-système). Pilotes tiers : [5.5](#55-sources-tierces-et-modifications-du-projet).

### 5.2 Chaîne principale et interfaces

Architecture / flux : [dossier technique 3.1](DOSSIER_TECHNIQUE.md#31-architecture-générale). Topics, JSON, HTTP et WebSocket : [3.10](DOSSIER_TECHNIQUE.md#310-interfaces-et-contrats-de-données).

Pour la chaîne réelle, vérifier nœuds, topics, émetteurs, messages et paramètres selon la [section 6.3](#63-vérifications-wsl-web-et-ros), pas uniquement les YAML sauvegardés.

Keyboard web et télécommande clavier en terminal sont distincts. Ne pas confondre leurs options de lancement ni lancer plusieurs sources de mouvement. Voir les [conditions de démarrage](DOSSIER_TECHNIQUE.md#33-démarrage-et-états).

### 5.3 Les trois périmètres de configuration

1. **JSON launcher Windows local** : chemins, interpréteurs, services et commandes attach / detach ; exclu de synchronisation et hors API web.
2. **YAML source WSL** : `launch_args.yaml`, `eeg_control_node.params.yaml`, `eeg_control_node.eeg2.params.yaml` ; cible principale de sauvegarde web.
3. **YAML installé ROS** : launch lit le package share ; calibration tente source et install. Vérifier réellement les liens symboliques, sans supposer les deux répertoires toujours identiques.

Le deuxième fichier EEG correspond à la deuxième configuration, pas nécessairement Hybrid ou Steering. La désactivation dépend de `run_eeg2` et des réglages associés ; inutile de supprimer le fichier.

Si les valeurs sauvegardées ne sont pas utilisées, comparer source écrite, install lue, liens symboliques et logs. `source_files` de `GET /api/config` rapporte seulement les chemins source backend, pas les fichiers installés réellement lus par ROS.

Sauvegarde, prise en compte de calibration et cas particuliers Stop / Start : [conception 3.7](DOSSIER_TECHNIQUE.md#37-calibration). Lecture / écriture complète : [3.9](DOSSIER_TECHNIQUE.md#39-configuration-et-persistance). Ne pas supprimer `thymio_control/` pour résoudre une incohérence.

### 5.4 Préfiltrage des deux modèles EEG

Emplacements, fréquences, capacités API et différences : [traitement technique 3.5](DOSSIER_TECHNIQUE.md#35-traitement-du-signal-eeg). Ici figurent les entrées de maintenance et test.

- **Code** : filtres Headband reliés dans [`GpypeBridge.build()`](../gtec_bridge/gpype_lsl_bridge.py) ; activation Linux dans [`lsl_raw.py`](../thymio_control/thymio_control/adapters/lsl_raw.py), réalisation [`StreamingPreFilter` dans `band_power.py`](../thymio_control/thymio_control/processors/band_power.py).
- **Identité modifiée** : le préfiltrage Hybrid dépend actuellement du nom `gtec_hybrid_black`, pas du `source_id`. Après changement de nom, pont ou ajout d’appareils identiques, éviter filtre absent / doublé.
- **État streaming** : préserver l’état par canal entre blocs ; ne pas réinitialiser à chaque bloc.
- **Unités** : le [pont Hybrid](../gtec_bridge/unicornpy_lsl_bridge.py) n’écrit pas `source_unit`. µV par défaut ne signifie pas unité confirmée : vérifier SDK / métadonnées, sans se fier à l’apparence.

Après modification, [tests du préfiltre](../thymio_control/test/test_pre_filter.py) pour composante continue, 50 Hz, conservation 10 Hz, continuité, multicanal et reset ; [puissances](../thymio_control/test/test_band_power.py) pour le traitement suivant. Ces tests numériques ne vérifient ni réponse réelle du SDK Windows ni stabilité Bluetooth.

### 5.5 Sources tierces et modifications du projet

`src/ros-aseba` et `src/ros-thymio` sont devenus des répertoires Git ordinaires au commit `12c093c`, avec dépendances imbriquées conservées. Ce ne sont pas des sous-modules récupérant automatiquement les derniers upstream. Les `.gitmodules` restants sont des traces de provenance, pas une instruction de mise à jour récursive actuelle.

Versions amont figées ci-dessous. Les versions imbriquées viennent de l’arbre amont ros-aseba correspondant, pas de la branche récente :

| Répertoire / composant | Version amont |
|---|---|
| `src/ros-aseba` | [jeguzzi/ros-aseba @ 94acaba](https://github.com/jeguzzi/ros-aseba/tree/94acaba803d748b84fce62ab0527d1348b28be12) |
| `src/ros-aseba/asebaros/aseba` | [aseba-community/aseba @ 3c14f0c](https://github.com/aseba-community/aseba/tree/3c14f0cb9510c60502821bfd7adb22e795540479) |
| `src/ros-aseba/asebaros/dashel` | [aseba-community/dashel @ 1a8d36e](https://github.com/aseba-community/dashel/tree/1a8d36e7fe48ce0f4fd292f5b64b2a0a880953da) |
| `src/ros-thymio` | [jeguzzi/ros-thymio @ d996f49](https://github.com/jeguzzi/ros-thymio/tree/d996f4994feb5332c42a2b58c2c2c17fed0c938d) |

| Fichier différent | Différence confirmée et conséquence |
|---|---|
| Aseba [`TargetDescription.h`](../src/ros-aseba/asebaros/aseba/aseba/common/msg/TargetDescription.h) | Ajout `#include <cstdint>` pour les types dont `uint16_t`. Correction de compatibilité de compilation, pas optimisation d’acquisition. Après mise à niveau, vérifier si nécessaire et compiler sur cible |
| Aseba [`DashelTarget.cpp`](../src/ros-aseba/asebaros/aseba/aseba/clients/studio/DashelTarget.cpp), [`challenge.cpp`](../src/ros-aseba/asebaros/aseba/aseba/targets/challenge/challenge.cpp) | Libellé chinois « 汉语 » remplacé par « Chinois », code `zh` inchangé. Texte UI, pas correction ROS |
| Thymio [`base.urdf.xacro`](../src/ros-thymio/thymio_description/urdf/base.urdf.xacro) | Plugins anciens Gazebo ROS différentiel / joint-state remplacés par GZ Sim DiffDrive ; bloc ground-truth supprimé. Adaptation simulation, sans conservation garantie des anciens capteurs / ground-truth |
| Thymio [`imu.urdf.xacro`](../src/ros-thymio/thymio_description/urdf/imu.urdf.xacro), [`proximity_sensor.urdf.xacro`](../src/ros-thymio/thymio_description/urdf/proximity_sensor.urdf.xacro) | Anciens blocs plugins `gazebo_ros` retirés ; pas preuve que GZ moderne publie les topics capteurs ROS |
| Thymio [`wheel.urdf.xacro`](../src/ros-thymio/thymio_description/urdf/wheel.urdf.xacro) | Limite effort de 0 à 10 ; paramètre simulé, pas plafond universel de commande moteur réelle |
| Thymio [`model.launch.py`](../src/ros-thymio/thymio_description/launch/model.launch.py) | Sortie screen → log, déclaration `use_sim_time` ajoutée ; valeur des nœuds encore codée `True`, non issue de l’argument. Limite à vérifier, pas transmission corrigée. Modification repérable au commit `d377c77` |

Distinguer compatibilité Aseba, texte UI et simulation Thymio, sans tout qualifier d’optimisation. Ancien `master` / tutoriels contiennent ROS1 ; vérifier ROS2 / GZ avant mise à niveau.

En migration, conserver tout `src/` plutôt que l’écraser avec les derniers upstream. Pour une mise à jour nécessaire, comparer séparément, garder / refaire les correctifs, compiler puis tester robot réel, simulation, topics et horloge. Préserver [ROS-Aseba LICENCE](../src/ros-aseba/LICENCE), [ROS-Thymio LICENSE](../src/ros-thymio/LICENSE), [licence Aseba](../src/ros-aseba/asebaros/aseba/license.txt) et [licence Dashel](../src/ros-aseba/asebaros/dashel/license), sans licence unique déclarée pour ces composants distincts.

## 6. Diagnostic par couche et logs

### 6.1 Identifier d’abord la couche en cause

Arrêter le contrôle, noter heure et reproduction minimale, puis vérifier couche par couche. Ne pas réinstaller Python, changer Bluetooth, BUSID et YAML simultanément : l’action efficace deviendrait impossible à identifier.

| Couche / symptôme | Vérification minimale | Interprétation / suite |
|---|---|---|
| Appareil Windows / Bluetooth instable | Batteries, chargeur, module intégré dans Gestionnaire de périphériques, adaptateur USB Hybrid utilisé par erreur | Rétablir le physique ; distinguer dongle Thymio et Bluetooth |
| Interpréteur / SDK non importable | Imports 3.1 avec le bon Python | Paquet, ABI ou licence : pas encore ROS ; vérifier VS Code Headband et sonde |
| Launcher ne démarre pas / WSL non prêt | `launcher_server.log`, nom enregistré, `\\wsl$`, systemd | Configuration / partage réels ; ne pas réinstaller WSL à cause d’un simple timeout |
| EEG non vert dans System Control | Sonde Windows correspondante et sortie du pont | Distinguer not-found, stalled, no-pylsl selon 6.2 |
| EEG vert, graphiques vides | Calibrate / Start lancé ? source_id, nœuds / topics, subscriber_error | Connexion seule sans analyse normale ; découverte Windows ≠ découverte WSL |
| Preparing persistant | Échantillons Windows frais, découverte WSL, source_id, erreurs nœud | Décompte attend la première trame ; pas toujours réseau |
| YAML enregistré, valeurs d’exécution inchangées | source_files API, package prefix et paramètres du nœud | Vérifier dépôt, source / install ; recompiler frontend ne suffit pas |
| Thymio vert mais immobile | Test Keyboard à un rôle, puis vitesse finale et pilote | USB visible ≠ appairage / pilote / mouvement opérationnels |
| Deux EEG, une seule voie / aucun mouvement | Deux source_id, rôles, topics partiels, fuser | Zéro watchdog peut être correct si voie absente ; ne pas désactiver |
| Web local fonctionne, autre ordinateur non | Redirection 5173 / pare-feu, proxy, origin WS et autorisation | Vérifier le parcours réel ; ne pas couper tout le pare-feu ou ouvrir tous les ports backend |

La récupération matérielle courante est dans le [guide de dépannage](GUIDE_DEBUG.md). Les vérifications suivantes localisent davantage ponts, LSL, ROS et services.

### 6.2 Vérifications LSL Windows et USB

PowerShell, dans le répertoire Windows `windows_launcher`, avec les interpréteurs réels des appareils :

```powershell
python lsl_probe.py gtec_bci_core4 2
python lsl_probe.py gtec_hybrid_black 2
usbipd list
```

La sonde affiche `alive`, `stalled`, `not-found` ou `no-pylsl`. Son code de sortie normal reste 0 : il ne suffit pas à conclure à une connexion réussie.

- `alive` : flux résolu et échantillons frais reçus.
- `stalled` : flux présent sans échantillons frais, éventuellement pont actif mais appareil sans données.
- `not-found` : flux absent ou exception de résolution ; consulter le pont avant de conclure que l’appareil est éteint.
- `no-pylsl` : pylsl absent du Python de la sonde ; pas preuve d’absence dans le venv VS Code.

États USB selon le [dépannage 4](GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio) : `1-1` Shared peut être attaché avec Connect ; Attached déjà connecté ; Not shared exige bind ; numéro absent, rebrancher dans le port prévu.

Après attach, vérifier périphérique et droits dans WSL Bash :

```bash
ls -l /dev/ttyACM0
id
```

Si le périphérique existe mais le pilote manque de droits, vérifier groupe, utilisateur et règles udev. `chmod 777` n’est pas une solution durable. Si le port série change, vérifier ensemble sonde launcher, configuration ROS device et documentation.

### 6.3 Vérifications WSL, web et ROS

Running en haut du web est un marqueur local frontend ; `running` dans `/api/status` n’est pas une sonde de santé du sous-processus ROS. Une requête en échec ou un processus terminé peut laisser un état inexact. Après Start EEG, vérifier nœuds, topics et messages ; avec deux EEG, fusionneur et deux topics partiels aussi. Keyboard ne nécessite pas les nœuds EEG : vérifier topic final et pilote. Ne pas conclure au démarrage ou à l’arrêt d’après les boutons seuls.

WSL Bash, ROS / install chargés. Ces diagnostics lisent et ne publient aucun mouvement :

```bash
curl --fail http://127.0.0.1:8010/api/health
curl --fail http://127.0.0.1:8010/api/config
ros2 node list
ros2 topic list
ros2 topic info /cmd_vel --verbose
ros2 topic echo /eeg_analysis --once
```

À deux voies, lire `/eeg_analysis/speed`, `/eeg_analysis/steering` et les topics partiels. En simulation, final `/model/thymio/cmd_vel`. Sans publication, echo attend ; Ctrl+C termine. Cette attente n’est pas forcément un terminal bloqué.

Utiliser `ros2 param list <nom du nœud>` et `ros2 param get <nom du nœud> <paramètre>` pour comparer les valeurs exécutées, pas seulement les YAML. Pour calibration : `CALIB:`, échantillons valides, écritures et paramètres de chaque fichier.

Localiser l’installation dans WSL :

```bash
ros2 pkg prefix thymio_control
```

Comparer `share/thymio_control/config/` sous ce prefix aux sources et cibles des liens symboliques. `source_files` de `/api/config` ne couvre pas tous les fichiers installés utilisés. Demander `/api/config?reload=true` seulement pour relire le disque ; une migration d’ancienne configuration peut écrire le deuxième fichier, donc sauvegarder avant.

Réseau en lecture : PowerShell `netsh interface portproxy show all`, WSL `hostname -I` et `ss -ltnp` pour IP et écoute 5173 / 8010. IPv6 a déjà causé un blocage LSL dans ce projet, mais sa désactivation n’est pas la première solution universelle. Prouver d’abord données Windows normales / découverte ou connexion WSL anormale, conserver les logs et examiner la configuration. Un changement réseau à la fois, avec ancienne valeur et restauration notées.

### 6.4 Emplacements des logs et rapport de panne

| Source | Emplacement / entrée | Attention |
|---|---|---|
| Launcher Windows | `windows_launcher/launcher_server.log` Windows ; View Log | Lire la copie réellement exécutée |
| Hybrid Black | `bridge_hybrid.log` dans ce répertoire | Lancement, imports, acquisition / reconnexion |
| Headband | Terminal VS Code du script manuel | Aucun bridge_headband garanti ; copier le texte après Ctrl+C si nécessaire |
| Backend WSL | `/tmp/launcher_backend.log` | Redirection écrasante dans le modèle : conserver l’utile avant redémarrage |
| Frontend WSL | `/tmp/launcher_frontend.log` | npm / Vite et erreurs de port |
| ROS | Logs launch / nœuds ; erreurs du launch manuel | Runner web met stdout / stderr ROS en DEVNULL ; tout n’est pas dans le backend |
| Compilation | `log/` colcon | Ne pas committer produits / logs comme sources |

Un rapport utile contient heure, commit exécuté, résumé de configuration modifiée, appareils / rôles / sortie, étapes, attendu / réel, logs clés, changement testé et résultat. Retirer données de participants, token ou adresses internes avant partage ; ne pas committer des logs sensibles complets.

## 7. Modifications et tests

### 7.1 Tests existants

Utiliser `.venv` racine WSL après contrôle des dépendances. Choisir les tests selon le changement ; résoudre les dépendances selon l’installation.

WSL Bash, racine :

```bash
source .venv/bin/activate
python -m pytest thymio_control/test -v
python -m pytest windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

Le backend importe `app.*` ; exécuter depuis son répertoire :

```bash
cd web_gui/backend
../../.venv/bin/python -m pytest app -v
```

Frontend : `npm ci`, `npm run build` dans son répertoire. pytest à la racine découvre uniquement les trois répertoires de `pytest.ini`, **sans le backend**.

| Périmètre | Ce qu’il démontre | Ce qu’il ne démontre pas |
|---|---|---|
| Logique watchdog / fuser / policy / calibration | Décisions, conversion, calculs et limites | Délai d’arrêt physique, stabilité Bluetooth / USB |
| launcher tests | Cycle, commandes et états avec fake executor | Windows, SDK, WSL et réseau réels |
| backend tests | Modèles, configuration, runner, subscriber | Toute la vie ROS réelle ou l’exécution physique |
| lsl_test | Génération, EDF / streaming et validation de développement | Réseau réel entre systèmes ou validité physiologique |
| npm build | Frontend compilable | Interaction correcte ou arrêt après panne WS |
| Intégration cible | Comportement des scénarios effectivement exécutés | Environnements, appareils ou pannes non couverts |

Certains tests sont ignorés si dépendance ou données manquent : skip ≠ réussite. `gtec_bridge/test_*.py` contient des scripts de diagnostic matériel / SDK, pas des tests purs sûrs partout. Ne pas tous les lancer pour prétendre à une couverture totale.

Régression rapide sans ROS, dans un environnement de développement :

```bash
python -m pytest thymio_control/test/test_watchdog.py thymio_control/test/test_cmd_vel_fuser.py thymio_control/test/test_calibration.py thymio_control/test/test_blink_metric.py -q
```

Les données historiques ont été retirées. [test_verify_blink_clamp.py](../thymio_control/test/test_verify_blink_clamp.py) est ignoré si ses archives manquent ; ce n’est pas une fonction actuelle de relecture disponible. Résultats réellement établis : [périmètre technique](DOSSIER_TECHNIQUE.md#41-périmètre-des-vérifications). Relancer les tests concernés après chaque modification.

### 7.2 Procédure pour une petite modification

1. Décrire reproduction, attendu et succès ; vérifier Git et préserver les changements existants de l’utilisateur.
2. Localiser la couche avec la [lecture du code](#5-lecture-du-code-et-des-configurations), puis modifier le minimum. Pas de refonte opportuniste des pilotes / anciens modules.
3. Ajouter / mettre à jour les tests ; tests locaux puis suites affectées. Pour UI : compilation et vérification par clics.
4. Vérifier en simulation ou environnement contrôlé ; connexion, calibration, fusion, watchdog, Teleop et arrêt des processus exigent aussi des scénarios réels.
5. Mettre à jour manuels, migration de configuration et notes de version ; examiner le diff puis committer. Ne pas inclure calibrations temporaires, chemins privés, logs ou données personnelles.

Respecter conventions et style : logique pure testable, seuils nommés, erreurs explicites.

### 7.3 Couches à vérifier lors d’une extension

| Changement | Points de liaison à vérifier au minimum |
|---|---|
| Nouvel indicateur / stratégie | Caractéristiques processors, policy / registre `POLICIES`, indicateur de calibration du nœud, validation backend, options / affichage frontend, YAML, tests numériques / calibration |
| EMA | `ema_alpha=0.35` des trois classes, pas paramètre YAML / UI actuel. Plus élevé : réactif mais instable ; plus bas : lisse mais lent. Vérifier état et régressions |
| Appareil | API / SDK Windows, pont / StreamInfo, source_id unique, canaux / fréquence / unités, device_profiles, filtre adapter, modèles / rôles frontend-backend, launcher / sondes |
| USB / chemins | Toutes les commandes / chemins JSON Windows, attach / detach / verify, ROS device, manuels et port prévu |
| Arrêt / perte de données | Watchdog nœud, fuser, nettoyage runner, ponts Windows, erreurs web / WS et arrêt pilote réel |

Pour un appareil, vérifier ensemble identité, métadonnées et traitement selon [5.4](#54-préfiltrage-des-deux-modèles-eeg). L’intégration de deux modèles identiques suit la [feuille de route 7.5](#75-priorité--intégrer-deux-gtec-du-même-modèle).

### 7.4 Limites de sécurité à préserver et tester

Ne pas masquer un problème en désactivant la protection. Voir les [limites techniques](DOSSIER_TECHNIQUE.md#51-limites-et-vérifications-prioritaires) et vérifier particulièrement :

- Fraîcheur contrôlée séparément par nœud EEG et fusionneur, chacun à 0,5 s par défaut actuellement. Pas un délai global d’arrêt. Mesurer perte / reprise ; les données peuvent relancer un contrôle toujours Running.
- Steering Alpha / TBR : calibration automatique ne renouvelle pas le plancher de montée du détecteur existant ; Stop / Start le recharge. Pas une règle universelle imposant de redémarrer toute calibration ; voir l’[état après calibration](DOSSIER_TECHNIQUE.md#état-du-contrôle-après-calibration).
- Déconnexion WebSocket Teleop : pas de publication zéro automatique explicite du backend ; Stop au relâchement ne garantit pas l’arrêt réseau.
- dry-run / `WEB_GUI_ALLOW_REAL_COMMANDS=false` ne bloque pas Teleop direct. Isoler le réel même pour les tests sans matériel.
- Nettoyage par noms pouvant atteindre d’autres tâches ROS / web. Stop System termine toute la distribution configurée ; vérifier les autres tâches avant de partager une station.

Anciens designs et revues sont des pistes, pas des preuves actuelles. Vérifier le code et reproduire avant modification.

### 7.5 Priorité : intégrer deux g.tec du même modèle

Non implémenté et non validé sur matériel réel. Périmètre et réussite : [RF-NEXT-01 à 06](DOSSIER_TECHNIQUE.md#25-prochaine-priorité--deux-gtec-du-même-modèle). Ci-dessous, fichiers, ordre et régressions.

#### 7.5.1 Objectif et éléments réutilisables

Combinaisons, périmètre et compatibilité : [dossier technique 2.5](DOSSIER_TECHNIQUE.md#25-prochaine-priorité--deux-gtec-du-même-modèle).

ROS launch lance déjà deux nœuds EEG ; deux YAML sauvegardent les calibrations ; `cmd_vel_fuser` fusionne par rôle, et backend / graphiques routent par rôle. Réutiliser ces éléments. Le manque central est **sélection de l’appareil Windows → flux LSL unique → liaison de configuration → état de connexion**, pas un nouvel algorithme de contrôle.

#### 7.5.2 Limites actuelles et fichiers à modifier

| Couche / entrée | État vérifié | Travail requis |
|---|---|---|
| [Pont Hybrid](../gtec_bridge/unicornpy_lsl_bridge.py) | `_connect_unicorn()` prend le premier `GetAvailableDevices(True)` et recommence à la reconnexion ; ID fixe | Numéro de série explicite, identique au départ / reconnexion ; ID unique ; ne pas substituer un autre appareil si la cible manque |
| [Pont Headband](../gtec_bridge/gpype_lsl_bridge.py) | `BCICore8(channel_count=4)` sans sélection explicite ; nom LSLSender fixe ; sonde interne par nom | Vérifier interfaces SDK installées pour sélection / ID ; préserver cible à la reconstruction et sonder seulement cette instance ; garder IDE manuel |
| [Config launcher](../windows_launcher/config.json), [commandes](../windows_launcher/commands.py), [server](../windows_launcher/launcher_server.py), [sonde](../windows_launcher/lsl_probe.py) | Un Headband et un Hybrid ; processus par clé ; pas d’arguments d’instance ; premier flux correspondant sondé | Réutiliser la gestion par clé, avec entrées / paramètres / logs / sondes séparés ; arrêter seulement la cible et ne pas utiliser l’autre pour afficher Connected |
| [App frontend](../web_gui/frontend/src/App.jsx) | Même modèle désactivé en deuxième voie, effect change le modèle ; `buildPatch()` reconstruit ID, chargement déduit modèle depuis ID | Autoriser modèles identiques mais rôles distincts ; choix d’appareil concret ; sauvegarder / relire identité sans écraser ID par modèle |
| [Modèles backend](../web_gui/backend/app/models.py), [écriture](../web_gui/backend/app/config_store.py), [YAML](../thymio_control/config/) | `lsl_source_id` conservé mais pas modèle / série ; validation des rôles seulement | Champs minimaux d’identité et validation ; refuser appareil / ID dupliqués côté serveur aussi ; sauvegarde, relecture, calibration sans perte d’identité |
| [RawLslAdapter](../thymio_control/thymio_control/adapters/lsl_raw.py) | Résolution ID ou type, `streams[0]` ; filtre Hybrid selon `info.name()` | Liaison explicite ; refuser conflits de flux valides ; séparer traitement du modèle et identité ; vérifier unités / canaux / filtres |
| [Launch](../thymio_control/launch/experiment_core.launch.py), [nœud EEG](../thymio_control/scripts/eeg_control_node.py), [fusionneur](../thymio_control/scripts/cmd_vel_fuser.py), [RosBridge](../web_gui/backend/app/signal_subscriber.py) | Deux nœuds, fichiers et topics role existent | Identité transmise effectivement ; garder routage, fusion, protection ; pas de refonte sans rapport |

#### 7.5.3 Conception minimale de l’identité

Ne plus assimiler « modèle » à « cet appareil ». Distinguer au moins quatre éléments ; noms des champs à définir et aligner entre frontend, backend et fichiers :

| Information | Usage / contrainte |
|---|---|
| Modèle | Acquisition et filtrage, par exemple Headband / Hybrid ; pas identifiant unique |
| Numéro de série physique | Cible explicite SDK Windows ; deux voies ne peuvent pas viser la même unité |
| source_id LSL | Liaison unique Linux / sondes ; possible modèle + série ; stable à la reconnexion, sans rôle dans l’ID |
| Rôle | `speed` / `steering`, échangeable sans changer l’identité physique |

`gtec_hybrid_black_<serial_A>` et `gtec_hybrid_black_<serial_B>` sont des exemples proposés, **pas des paramètres existants ou flux déjà publiés**. Les libellés A / B aident l’affichage mais ne remplacent pas la vérification des numéros réels.

Nom LSL et source_id sont distincts. Garder le nom modèle et rendre le source_id unique peut être transitoire, mais la sonde Headband par nom doit aussi changer. Une solution plus robuste explicite modèle et filtrage déjà appliqué dans configuration / métadonnées pour choisir le traitement. Le choix dépend des interfaces g.Pype installées ; ne pas supposer un paramètre `LSLSender` non vérifié. Ajouter seulement un suffixe au nom Hybrid peut désactiver le filtre Linux actuel.

La calibration appartient actuellement aux première / deuxième configurations, pas définitivement à un appareil physique. Changement d’unité ou conditions : effacer / revérifier les anciens résultats. Après permutation des rôles, vérifier appareil, indicateur et calibration. Pas besoin d’une nouvelle base de données. Définir compatibilité ou migration des anciens ID fixes, sauvegarder avant conversion ; ne pas deviner silencieusement le modèle ni écraser l’ID au chargement.

#### 7.5.4 Réalisation et validation par étapes

1. **Conserver la base et vérifier les conditions.** Demander les [licences](#licence-de-lapi-hybrid-black) à Lucas ; vérifier SDK / Python / Suite et séries des appareils. Arrêter, sauvegarder et tester sur copie de développement, sans mise à niveau exploratoire du SDK existant.
2. **Vérifier d’abord l’acquisition concurrente Windows.** Sans contrôle robot, tenter deux acquisitions avec numéros explicites. Vérifier possibilités mono / multiprocessus, restrictions API, libération et reconnexion. La [FAQ g.Pype](https://gpype.gtec.at/content/5_faq/index.html) décrit plusieurs sources instanciables, mais ne garantit pas deux Headband indépendamment démarrables / arrêtables avec la version actuelle. Consigner versions, mode, identités, données, durée, échecs et limites. Si la capacité fabricant manque, expliquer le blocage sans changer soi-même API / parcours.
3. **Créer des ponts configurables par instance.** Sélection d’appareil et ID unique, reconnexion fixe, ressources, sondes et logs indépendants. Vérifier deux LSL sans ROS d’abord. Hybrid peut réutiliser un processus supervisé par entrée si la concurrence a réussi. Clarifier paramètres d’instance / lancement IDE Headband : ni constantes à éditer à chaque usage, ni conversion implicite en lancement automatique de fond.
4. **Relier configuration et Linux.** Champs modèle / série nécessaires, refus des doublons, écriture YAML, appariement explicite adaptateurs / sondes. Distinguer flux résiduels périmés et frais à la reconnexion ; plusieurs flux valides en conflit doivent produire une erreur, pas un choix arbitraire. Vérifier filtres, fréquence, canaux et unités de chaque voie.
5. **Actualiser les deux interfaces.** L’interface EEG accepte deux unités d’un même modèle, avec sauvegarde, relecture, permutation et calibration correctes. System Control propose entrées et états indépendants. Déconnecter une voie n’interrompt que son acquisition ; le robot s’arrête suivant la protection double existante.
6. **Régression hors ligne, puis matériel réel.** Étendre le [générateur double](../thymio_control/lsl_test/dummy_dual_streams.py) pour métadonnées identiques, ID distincts et valeurs différenciables ; tests sélection / reconnexion, configuration, sondes, filtres et UI. Vérifier ensuite deux appareils réels, ROS et Thymio. Consigner et actualiser manuels / migration avant déploiement.

Les deux premières étapes établissent la faisabilité fabricant ; les quatre suivantes intègrent le projet. Sans appareils, configuration et simulation peuvent être développées / testées, mais ni concurrence SDK, ni Bluetooth, ni arrêt réel ne doivent être déclarés validés.

#### 7.5.5 Scénarios de régression et résultats

Critères : [RF-NEXT-01 à 06](DOSSIER_TECHNIQUE.md#25-prochaine-priorité--deux-gtec-du-même-modèle). Pour chaque exigence, noter commit, environnement / configuration, étapes, attendu, mesuré, preuves, cas non testés et échecs.

- **Identité / configuration** : données simulées distinctes, puis déconnexion réelle unité par unité pour prouver les sources, pas seulement deux courbes. Tester même appareil, même ID, flux valides conflictuels et cible absente ; revérifier modèle, identité et rôle après sauvegarde, rafraîchissement et redémarrage.
- **Connexion / reconnexion indépendantes** : A, B séparément puis ensemble ; déconnexion, extinction, reconnexion ou arrêt A sans effet incorrect sur acquisition, liaison, état ou processus B. Sonde A sans données B, reconnexion ciblant A ; inverser et répéter.
- **Calibration / permutation** : calibration par voie et fichier correspondant seulement ; permutation, sauvegarde / relecture, correspondance appareil, indicateur, calibration, courbes et mouvement. Changement physique : vérifier effacement / revalidation de l’ancien résultat.
- **Contrôle / compatibilité** : filtres, fréquence, canaux, unités et fusion ; interrompre chaque voie, mesurer arrêt / reprise et noter reprise éventuelle si Running. Régresser Headband seul, Hybrid seul, combinaison mixte, simulation, Keyboard et arrêts.

Consigner séparément tests unitaires / simulés et deux appareils réels. Les anciens tests ne couvrent pas automatiquement la nouvelle fonction ; un seuil logiciel ne remplace pas l’arrêt mesuré. Les critères formels sont en [2.5 technique](DOSSIER_TECHNIQUE.md#25-prochaine-priorité--deux-gtec-du-même-modèle) ; sans recette réelle à deux unités, ne pas marquer la fonction validée.

## 8. Mises à jour et publication

### 8.1 Préparation et mise à jour des sources WSL

Arrêter contrôle, pont Headband manuel et services. Sauvegarder JSON réel, trois YAML et données utiles. Noter ancien commit et retour arrière ; coordonner l’interruption des autres tâches WSL.

WSL Bash, racine, lecture d’abord :

```bash
git status --short --branch
git diff --stat
git rev-parse HEAD
```

Si l’espace n’est pas propre, distinguer développement et réglages d’usage, préserver puis décider. Pas de `reset --hard`, écrasement forcé ou commit indifférencié.

Après confirmation d’un espace propre, de la branche et de la source seulement, tirer les changements. Déploiement sur `main`, pas mise à jour automatique :

```bash
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

Divergence / conflit : arrêter et diagnostiquer, sans push forcé. Consigner le commit déployé. Tester le développement sur une branche séparée avant l’environnement utilisé.

### 8.2 Actions selon le changement

| Changement | Déploiement |
|---|---|
| Dépendances Python | Installer dans le `.venv` cible, vérifier ROS / SDK et tester |
| Sources ROS / launch / ressources installées | Charger ROS, compiler et vérifier la version installée ; avec dépendances déjà prêtes, `colcon build --symlink-install --packages-select thymio_control` ; changements interpaquets : compiler les dépendances concernées |
| Frontend | `npm ci` si lockfile modifié, `npm run build`, redémarrer le vrai Vite et vérifier |
| Launcher / ponts Windows | Start System synchronise ; quitter / relancer le launcher pour son code, redémarrer chaque pont selon sa procédure |
| JSON Windows local | Migration explicite et sauvegarde ; pas mise à jour par synchronisation |
| YAML / calibration | Comparer, vérifier source / install, redémarrer les nœuds ; pas écrasement arbitraire des valeurs validées |
| Documentation seule | Liens, commandes, langue et parcours ; normalement sans réinstallation / compilation système |

Après mise à jour : commit réellement exécuté, copie Windows, JSON intact, provenance de la page, paramètres des nœuds, test Keyboard et fonctions affectées. En cas d’échec global, restaurer la base vérifiée plutôt que multiplier les configurations sur un système toujours actif.

### 8.3 Vérifications de publication et commit

Committer sources, documentation nécessaire et lockfile. Distinguer défauts partagés et configuration locale. Si des YAML versionnés changent, vérifier qu’il s’agit des défauts voulus, pas de paramètres d’essai ou de calibration personnelle. Examiner staging et diff ; pas de `git add .` indifférencié embarquant données / réglages locaux.

Notes de publication : commit, migration dépendances / configuration, tests et résultats, validation réelle ou non, limites et retour arrière. Toute modification fonctionnelle ou opératoire implique les documents et leurs versions linguistiques concernés.

## 9. Sauvegarde et restauration

### 9.1 Éléments à sauvegarder

| Élément | Raison | Conservation |
|---|---|---|
| Commit et changements non committés | Pont Windows seul insuffisant pour tout restaurer | Historique Git et changements locaux nécessaires séparément |
| JSON Windows réel et entrée | Chemins / interpréteurs locaux hors restauration par synchronisation | Copie contrôlée, datée et identifiée par ordinateur |
| Trois YAML réels | Web / calibration modifient l’exécution | Copier après arrêt ; noter appareils / rôles / indicateurs |
| SDK, pilotes, licences | Hors dépendances pip / Git complètes | Informations Hybrid auprès de Lucas, sauvegarde contrôlée selon [licences](#licence-de-lapi-hybrid-black), organisme / fabricant |
| Versions système / dépendances | Versions flottantes / ABI peuvent empêcher reproduction | Inventaires WSL et Python Windows, lockfile frontend |
| Logs et analyses à conserver | Fichiers originaux utiles au diagnostic / validation numérique | Emplacements réels ; pas données sensibles dans Git |
| Export WSL complet, prioritaire en migration | Conserve Linux, espace et réglages, réduit reconstruction | Après arrêt des services ; vérifier restauration selon [9.3](#93-migration-recommandée--export-et-import-de-wsl-complet) ; ne remplace pas sauvegarde Windows |

Conserver au besoin `python -m pip freeze`, `npm ls --depth=0` et versions ROS / système. Inventaire actuel seulement, sans garantie de récupération publique de chaque paquet ; ne remplace ni sources SDK ni licences.

Analyses par défaut dans `experiment_data/`, ou chemin `EXPERIMENT_DATA_DIR` du backend : sauvegarder selon le réglage réel. Les anciennes données ont été retirées, mais le code peut générer de nouveaux fichiers ; voir les [précautions README](../README.md#précautions-dutilisation). Le répertoire par défaut figure dans `.gitignore`, sans effacement de l’historique ni couverture des sorties personnalisées. Vérifier séparément leurs droits et règles d’ignorance.

### 9.2 Restauration

1. Restaurer la version enregistrée dans un nouveau répertoire / environnement contrôlé, sans écraser un espace non sauvegardé.
2. Évaluer l’[import WSL complet](#93-migration-recommandée--export-et-import-de-wsl-complet). Sans image utilisable ou pour une installation propre, suivre la [reconstruction](#3-installation-et-reconstruction-de-lenvironnement). Installation propre : nouveau venv, pas copie isolée. Import complet : vérifier le venv conservé. SDK / Python Windows toujours séparés.
3. Restaurer le JSON réel et adapter chemins, distribution, interpréteurs et commandes à la nouvelle machine, sans le remplacer aveuglément par le modèle.
4. Restaurer les trois YAML, vérifier rôles, ID, mouvements et conditions de calibration. Recalibrer la personne si nécessaire, jamais avec les valeurs synthétiques.
5. Vérifier installation ROS, compiler au besoin, restaurer partage USB et périmètre réseau.
6. Web local, Keyboard réel, un EEG, deux EEG, puis arrêt, perte / reprise et pannes réseau.
7. Consigner version, paramètres, dépendances manquantes et résultats ; archive conservée ≠ restauration validée.

Ordre général ci-dessus ; commandes de migration WSL complète ci-dessous.

### 9.3 Migration recommandée : export et import de WSL complet

Si l’ordinateur d’origine est accessible et la sauvegarde autorisée, exporter d’abord sa distribution fonctionnelle, copier l’archive puis l’importer sur le nouveau. L’image conserve ROS, sources, réglages, dépendances, utilisateurs et venv dans le système de fichiers Linux. Ce n’est ni une copie du dépôt seul ni du venv seul. Voir [commandes Microsoft](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#export-a-distribution) et [importation](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro).

**Non restaurés par l’export Linux :** Suite / API / licences g.tec Windows, Python / venv Windows, VS Code, appairage Bluetooth, usbipd / partage, copie launcher / JSON local, pare-feu / redirections, `.wslconfig` hôte et fichiers Windows montés via `/mnt/c`. Préparer et sauvegarder séparément selon la [section 3](#3-installation-et-reconstruction-de-lenvironnement) ; le tar Linux ne les inclut pas.

#### 9.3.1 Export sur l’ordinateur d’origine

Suivre l’[ordre d’arrêt](#41-démarrage-et-arrêt-normaux) : immobiliser, arrêter les services et le Headband, sauvegarder les autres tâches. Lire le **nom enregistré** avec `wsl -l -v`, pas « WSL2 » ni la version Ubuntu. Préparer un répertoire avec assez d’espace. L’exemple `D:\BCI-transfer` doit déjà exister ; adapter disque, nom et date.

PowerShell Windows, remplacer les placeholders puis exécuter par étapes. Arrêter à tout échec ; ne pas prendre un ancien fichier pour une nouvelle sauvegarde :

```powershell
wsl -l -v
$sourceDistro = "<nom de distribution relevé sur l’ancien ordinateur>"
$backupFile = "D:\BCI-transfer\TelekineRob-WSL-20261009.tar"
if (Test-Path -LiteralPath $backupFile) { throw "Le fichier existe déjà ; choisir un nouveau nom" }
wsl --terminate $sourceDistro
if ($LASTEXITCODE -ne 0) { throw "Échec de l’arrêt ; diagnostiquer avant de continuer" }
wsl --export $sourceDistro $backupFile
if ($LASTEXITCODE -ne 0) { throw "Échec de l’export ; ne pas utiliser cette sauvegarde" }
Get-Item -LiteralPath $backupFile
Get-FileHash -LiteralPath $backupFile -Algorithm SHA256
```

`--terminate` n’arrête que la distribution indiquée, mais toutes ses tâches sont interrompues. Éviter `--shutdown` qui toucherait les autres distributions. Noter nom, utilisateur / chemins Linux, architecture, commit / modifications, versions et hash. L’archive peut inclure identifiants, SSH, données et logs ; stockage autorisé par l’organisme, pas Git ou partage public.

#### 9.3.2 Import et vérifications Linux sur le nouvel ordinateur

Préparer WSL2 et vérifier architecture CPU compatible ; sinon [reconstruire](#3-installation-et-reconstruction-de-lenvironnement) au lieu de supposer qu’un venv neuf rendra l’image compatible. Copier le tar par canal contrôlé et comparer SHA256. Choisir un **nouveau nom non enregistré** et un **répertoire d’installation dédié vide**. `TelekineRob-BCI` est ici seulement un nom enregistré adaptable, sans écraser Ubuntu existant. Les chemins suivants doivent exister et respecter ces contraintes. En cas d’échec, préserver l’existant, sans supprimer une ancienne distribution pour réessayer.

PowerShell Windows :

```powershell
wsl -l -v
Get-FileHash -LiteralPath "D:\BCI-transfer\TelekineRob-WSL-20261009.tar" -Algorithm SHA256
wsl --import "TelekineRob-BCI" "D:\WSL\TelekineRob-BCI" "D:\BCI-transfer\TelekineRob-WSL-20261009.tar" --version 2
if ($LASTEXITCODE -ne 0) { throw "Échec de l’import ; diagnostiquer avant de continuer" }
wsl -l -v
wsl -d "TelekineRob-BCI" -u "<ancien utilisateur Linux>" -- whoami
```

Vérifier VERSION 2, utilisateur, dépôt et permissions. L’import peut démarrer en root par défaut. Conserver `/etc/wsl.conf` existant ; si nécessaire, configurer `[user]` avec `default=<ancien utilisateur Linux>` déjà présent. Suivre [Microsoft](https://learn.microsoft.com/en-us/windows/wsl/use-custom-distro#add-wsl-specific-components-like-a-default-user), redémarrer cette distribution puis vérifier sans `-u` : `wsl -d "TelekineRob-BCI" -- whoami`. Ne pas lancer aveuglément le launcher en root, ce qui changerait droits / chemins.

Depuis le dépôt réel importé, effectuer les [contrôles 2.1](#21-référence-denvironnement-et-vérifications) et [imports 3.4](#34-environnement-python-wsl-et-frontend), puis systemd, ROS, venv, Node / npm et cibles install. Même architecture, chemins et dépendances peuvent préserver le venv Linux : vérifier avant de le reconstruire. S’il est invalide ou manque des bibliothèques, suivre la section 3. Cela ne permet pas de réutiliser le venv Windows. Recompiler colcon si nécessaire, en gardant les [correctifs tiers](#55-sources-tierces-et-modifications-du-projet).

#### 9.3.3 Configuration Windows et vérification d’exécution

1. Préparer logiciels g.tec, API, pilotes et environnements Python selon les [sources / conditions](#37-sources-officielles-et-dépendances). Confirmer la migration des licences avec Lucas ; import WSL ≠ UnicornPy autorisé.
2. Installer VS Code / usbipd-win, appairer EEG, vérifier Bluetooth intégré et alimentation. Revérifier la stabilité sur la nouvelle machine ; Thymio / dongle selon appairage et port prévus.
3. Redéployer launcher Windows, sauvegarder / adapter JSON : `wsl.distro`, chemin du dépôt, `sync.src_wsl_root`, cible Windows, Python, `open_cmd`, et toutes les distributions / chemins inclus dans attach, verify et services. `wsl.distro` seul ne suffit pas ; le modèle contient `Ubuntu` en plusieurs endroits.
4. Vérifier BUSID réel. La convention actuelle reste `1-1` : brancher au port prévu, rebrancher et vérifier. Si ce numéro ne peut être conservé, le développeur vérifie / actualise ensemble attach, detach et manuels ; l’opérateur ne choisit pas un autre périphérique au hasard. Premier partage : [dépannage](GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio).
5. Vérifier réseau, redirection, pare-feu et suivre la [restauration générale](#92-restauration) : web, Keyboard, un EEG, combinaison mixte, arrêt / perte de données. Deux appareils du même modèle exigent d’abord le [développement et la validation 7.5](#75-priorité--intégrer-deux-gtec-du-même-modèle) et ne sont pas la base actuelle de restauration.

---

[Version chinoise](zh/GUIDE_DEVELOPPEUR_cn.md)
