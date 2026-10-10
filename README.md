# TelekineRob-BCI

[Manuel opérateur](docs/MANUEL_OPERATEUR.md) · [Guide de dépannage](docs/GUIDE_DEBUG.md) · [Dossier technique](docs/DOSSIER_TECHNIQUE.md) · [Guide développeur](docs/GUIDE_DEVELOPPEUR.md)

TelekineRob-BCI est une plateforme de commande du robot Thymio à partir de l’EEG (électroencéphalogramme). Les données acquises par les appareils g.tec sont transmises à ROS2 (framework logiciel de robotique) via LSL (Lab Streaming Layer, bibliothèque de transmission de flux). Le système calcule les puissances des bandes de fréquences et les indicateurs de contrôle, puis produit les commandes de mouvement. L’interface web permet de connecter les appareils, de les calibrer, d’observer les analyses en temps réel et de commander le robot.

Le projet est destiné à la recherche sur l’interaction EEG–robot. Il permet une commande individuelle avec un appareil, ou une commande coopérative à deux personnes, l’une responsable de la vitesse et l’autre de la direction. Les appareils réels sont connectés sous Windows ; le traitement du signal, ROS2 et les services web s’exécutent sous WSL2. Le dépôt contient aussi des outils de génération d’EEG synthétique et du code d’intégration à Gazebo pour le développement sans matériel réel.

Pour une **utilisation quotidienne sur l’ordinateur du projet déjà installé**, consulter directement le [manuel opérateur](docs/MANUEL_OPERATEUR.md) et, en cas de problème, le [guide de dépannage](docs/GUIDE_DEBUG.md), sans réinstaller le système. Pour un premier déploiement, commencer par les [prérequis](#prérequis) et le [démarrage rapide](#démarrage-rapide). Pour changer d’ordinateur, évaluer en priorité la [migration complète de WSL](docs/GUIDE_DEVELOPPEUR.md#93-migration-recommandée--export-et-import-de-wsl-complet) ; l’environnement des appareils sous Windows reste à configurer séparément.

## Fonctionnalités principales

- **Commande avec un EEG** : Speed commande la marche avant ; Steering commande la rotation sur place.
- **Coopération avec deux EEG** : un Headband et un Hybrid Black se répartissent les rôles Speed et Steering ; un fusionneur produit la commande finale.
- **Trois indicateurs** : puissance Alpha, TBR (θ / β) et EI (β / (α + θ)).
- **Changement de direction par clignement** : la détection à partir de l’indicateur bascule entre gauche et droite pour le rôle Steering.
- **Calibration par appareil** : acquisition pendant 30 secondes à partir de données valides ; si le nombre d’échantillons est suffisant, les références sont calculées et enregistrées dans son fichier de paramètres.
- **Interface web** : choix des appareils, rôles, indicateurs et sortie ; affichage des puissances, des indicateurs et de la direction de contrôle.
- **Vérification manuelle et simulation** : boutons directionnels Keyboard, simulation Thymio dans Gazebo et outil de génération de deux flux LSL synthétiques.
- **Protection contre la perte de données** : les nœuds EEG et le fusionneur contrôlent la fraîcheur des entrées et traitent les données manquantes ou périmées.

Avec un seul appareil, un seul rôle est actif et la deuxième ligne est réglée sur None. Avec deux appareils, attribuer Speed et Steering. Les graphiques web montrent des résultats d’analyse, et non la tension EEG brute échantillon par échantillon.

## Matériel pris en charge

| Appareil | Connexion actuelle | Canaux EEG / source_id LSL |
|---|---|---|
| g.tec BCI Core-4 Headband | Pont gpype sous Windows | 4 : F8, Fp2, Fp1, F7 ; `gtec_bci_core4` |
| Unicorn Hybrid Black | Pont UnicornPy sous Windows | 8 : Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 ; `gtec_hybrid_black` |
| Thymio sans fil et son dongle USB | Dongle transmis à WSL par usbipd-win, puis commande par le pilote ROS | Robot réel |
| Thymio dans Gazebo | Pont ROS / Gazebo | Simulation, sans dongle réel |

Dans ce projet, le Headband et le Hybrid Black utilisent le Bluetooth intégré de l’ordinateur. Le Hybrid Black est livré avec un adaptateur Bluetooth USB, mais celui-ci provoquait des déconnexions fréquentes sur l’ordinateur d’origine. Le Bluetooth intégré étant plus stable dans cet environnement, l’adaptateur fourni n’est pas utilisé par défaut. Vérifier à nouveau la stabilité sur un autre ordinateur ; voir la [section 3.8 du guide développeur](docs/GUIDE_DEVELOPPEUR.md#38-conditions-sdk-et-modes-de-connexion). Le dongle USB du Thymio est un autre périphérique et reste nécessaire pour commander le robot réel.

Les ponts actuels utilisent un source_id fixe par modèle. Ils ne permettent pas d’utiliser directement deux appareils EEG quelconques du même modèle comme deux sources indépendantes.

La priorité de la prochaine phase est de prendre en charge **deux EEG g.tec du même modèle**, associés à Speed et Steering, en conservant les modes actuels à un appareil et à deux modèles différents. Cet objectif n’est pas encore implémenté ni validé sur matériel réel ; voir les [exigences et critères de validation](docs/DOSSIER_TECHNIQUE.md#25-prochaine-priorité--deux-gtec-du-même-modèle) et la [feuille de route](docs/GUIDE_DEVELOPPEUR.md#75-priorité--intégrer-deux-gtec-du-même-modèle).

## Architecture du système

```text
Windows
  System Control : services web, pont Hybrid supervisé et connexion USB
  Pont Headband : lancement / interruption manuels dans VS Code, hors supervision
  Headband / Hybrid Black → ponts des appareils → LSL
                                                   ↓
WSL2 / Ubuntu
  Nœud EEG : RawLslAdapter → Welch PSD → caractéristiques → Policy → commandes
                                           ├─ une voie → vitesse finale
                                           └─ commandes partielles → fuser → vitesse finale
  Analyse ROS → FastAPI / WebSocket → interface React
  Boutons manuels → RosBridge → vitesse finale
                                           ↓
                                 Thymio / Gazebo
```

Le topic final est `/cmd_vel` pour le robot réel et `/model/thymio/cmd_vel` pour la simulation. Les commandes partielles sont publiées sur `/eeg_cmd_vel/speed` et `/eeg_cmd_vel/steering`. Les analyses utilisent `/eeg_analysis` ou ses variantes suffixées par le rôle.

Les algorithmes, la conversion en mouvement, la configuration et les interfaces sont détaillés dans le [dossier technique](docs/DOSSIER_TECHNIQUE.md#3-conception-du-système).

Le Headband appelle les filtres gpype dans le pont Windows. Pour le Hybrid Black, cette étape se déroule dans l’adaptateur WSL. Les deux voies passent ensuite au calcul des puissances fréquentielles. Voir l’[implémentation du filtrage](docs/GUIDE_DEVELOPPEUR.md#54-préfiltrage-des-deux-modèles-eeg) pour les emplacements et limites.

## Prérequis

| Environnement | Exigences |
|---|---|
| Système d’exploitation | Windows + WSL2, Ubuntu 24.04 |
| ROS2 | Kilted ; Python compatible avec le ROS installé, avec Python 3.12 comme référence du projet |
| Python WSL | `.venv` à la racine et [requirements.txt](requirements.txt) |
| Frontend | Node.js / npm compatibles avec Vite 5 du dépôt ; versions gérées par [package-lock.json](web_gui/frontend/package-lock.json) |
| Appareils sous Windows | gpype / UnicornPy, pylsl et SDK / pilotes correspondants ; version et architecture Python compatibles avec les SDK |
| Outils Windows | Python, VS Code et usbipd-win (outil de partage USB Windows, dont la commande est `usbipd`) |
| Espace ROS | Paquets Thymio / Aseba du dépôt ; paquets ROS Gazebo supplémentaires pour la simulation |

Les SDK g.tec ne figurent pas dans la liste pip à la racine. Les dépendances système, SDK, réseau WSL et premier déploiement Windows sont décrits dans l’[installation de l’environnement](docs/GUIDE_DEVELOPPEUR.md#3-installation-et-reconstruction-de-lenvironnement). Voir aussi les [liens officiels](docs/GUIDE_DEVELOPPEUR.md#37-sources-officielles-et-dépendances). Ce tableau est une référence de projet : au déploiement ou à la migration, vérifier les versions, chemins et compatibilités réels selon le [contrôle de l’environnement](docs/GUIDE_DEVELOPPEUR.md#21-référence-denvironnement-et-vérifications).

## Démarrage rapide

Cette section présente le premier déploiement et les tests de développement. La section 3 concerne l’EEG synthétique et la simulation ; la section 4 concerne les appareils réels. Ce ne sont pas deux étapes successives. Pour l’utilisation quotidienne d’un ordinateur installé, consulter le [manuel opérateur](docs/MANUEL_OPERATEUR.md).

### 1. Récupérer le code et préparer l’espace WSL

Exécuter ces commandes dans **WSL Bash**. Préparer d’abord ROS2, colcon et les dépendances système selon les [instructions d’installation](docs/GUIDE_DEVELOPPEUR.md#32-prérequis-wsl-et-ros). Cloner dans le répertoire parent choisi, sans écraser un dépôt existant.

Si un `.venv` ou un système fonctionnel existe déjà, le vérifier avant de le recréer. Ce qui suit concerne un nouvel espace de travail. La première compilation ROS inclut les dépendances de `src/`, et pas seulement le paquet de contrôle EEG.

```bash
git clone --branch main https://github.com/nicrain/TelekineRob-BCI.git
cd TelekineRob-BCI
source /opt/ros/kilted/setup.bash
colcon build --symlink-install
source install/setup.bash

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Installation et compilation du frontend, en partant de la racine :

```bash
cd web_gui/frontend
npm ci
npm run build
```

Après installation, vérifier l’interpréteur et les imports essentiels depuis la racine, dans un nouveau terminal WSL :

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
python -c "import sys; print(sys.executable); import rclpy, pylsl, numpy, scipy, fastapi, yaml; print('WSL imports OK')"
```

En cas d’échec, suivre le [contrôle de l’environnement](docs/GUIDE_DEVELOPPEUR.md#34-environnement-python-wsl-et-frontend). Une installation pip réussie ne suffit pas à prouver que ROS / LSL sont utilisables.

### 2. Démarrer l’interface web

Choisir une seule méthode. **Ne pas démarrer les services web avec les deux méthodes simultanément.**

#### Méthode 1 : démarrage automatique avec System Control

Cette méthode suppose le [premier déploiement du launcher Windows](docs/GUIDE_DEVELOPPEUR.md#35-premier-déploiement-du-launcher-windows) terminé. Double-cliquer sur le fichier local Windows `windows_launcher/launcher.bat`. Si le système est **Stopped**, cliquer sur **Start System** et attendre **Running**. S’il est déjà Running, continuer sans cliquer sur **Restart System**. Le launcher démarre le backend et le frontend dans WSL et affiche l’interface dans la zone principale ; aucune commande de démarrage web n’est nécessaire dans un terminal.

#### Méthode 2 : démarrage manuel dans deux terminaux WSL

Le backend et le frontend fonctionnent séparément. Ouvrir deux fenêtres de terminal WSL. Dans chacune, aller d’abord à la racine du projet (`TelekineRob-BCI`, le répertoire contenant `web_gui/`), puis exécuter les commandes correspondantes. Garder les deux services actifs pendant l’utilisation.

**Démarrer le backend (premier terminal WSL) :**

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
cd web_gui/backend
python -m app.main
```

**Démarrer le frontend (second terminal WSL) :**

```bash
cd web_gui/frontend
npm run dev -- --port 5173 --strictPort
```

Une fois les deux services lancés, ouvrir `http://localhost:5173`.

#### Vérifications et opérations après démarrage

Le port par défaut du backend est 8010 ; son endpoint de santé est `http://localhost:8010/api/health`. Une page accessible ne prouve pas que l’EEG, ROS ou le robot sont prêts. Choisir l’entrée et les rôles dans **01 — Input Source**, puis la sortie dans **02 — Output Target**.

Les boutons **Start System / Stop System** gèrent les services web et l’environnement des appareils. Les boutons **Start / Stop** en haut de l’interface de contrôle démarrent et arrêtent la chaîne de commande du robot. Avant de quitter, cliquer d’abord sur Stop dans l’interface de contrôle et vérifier l’arrêt réel du robot.

### 3. Outils de développement : EEG synthétique et simulation

Le dépôt contient un [script EEG synthétique à deux voies](thymio_control/lsl_test/dummy_dual_streams.py) et du [code de lancement ROS / Gazebo](thymio_control/launch/experiment_core.launch.py). Toutefois, la chaîne complète « LSL synthétique → contrôle ROS2 → affichage web / robot Gazebo » n’a pas encore été validée. Préparer ROS2, Gazebo et les dépendances, puis compiler avant exécution. Voir la [validation hors ligne](docs/GUIDE_DEVELOPPEUR.md#43-validation-hors-ligne-sans-appareils) et le [périmètre des vérifications réalisées](docs/DOSSIER_TECHNIQUE.md#41-périmètre-des-vérifications).

Arrêter les ponts EEG réels et ne pas connecter de sortie vers un robot réel. Ouvrir un terminal WSL supplémentaire, aller à la racine et lancer le générateur :

```bash
source .venv/bin/activate
python thymio_control/lsl_test/dummy_dual_streams.py --blink
```

Configuration web : première ligne `Role = Speed`, `Device = EEG`, `Brand = g.tec Headband` ; deuxième ligne `Role = Steering`, `Device = EEG`, `Brand = g.tec Hybrid Black`. Garder Source sur LSL Stream et choisir **Thymio Simu**. Calibrer chaque voie puis démarrer ; vérifier les deux analyses et la réponse du robot simulé. Running ne prouve pas à lui seul la validation de la chaîne.

Les flux synthétiques ont les mêmes source_id que les ponts réels : ne pas les exécuter ensemble. La sauvegarde web et la calibration modifient les YAML ; les sauvegarder avant et les restaurer après. Ne pas utiliser une calibration synthétique pour une personne. Ce parcours ne nécessite ni SDK Windows, ni Bluetooth, ni Thymio réel ; il ne reproduit pas tout le filtrage ni les connexions sans fil / USB réelles. À la fin, cliquer sur Stop puis arrêter le générateur avec Ctrl+C.

### 4. Utiliser les appareils réels

Démarrer via le launcher Windows selon la [méthode 1 de la section 2](#méthode-1--démarrage-automatique-avec-system-control), puis connecter les appareils. Ne pas redémarrer un système déjà lancé.

- **Headband** : Connect ouvre le script. Dans VS Code, sélectionner le venv existant puis cliquer sur **▶** en haut à droite. Pour déconnecter, interrompre le script avec **Ctrl+C** dans son terminal.
- **Hybrid Black** : utiliser Connect / Disconnect dans System Control ; le pont utilise UnicornPy.
- **Thymio** : brancher le dongle dans le port prévu, vérifier que le BUSID `1-1` est « Shared », puis cliquer sur Connect pour le transmettre à WSL : son état devient « Attached ». « Shared » signifie que Windows autorise le partage avec Linux ; « Attached » signifie qu’il y est connecté. Voir le [contrôle du partage](docs/GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio) pour un nouveau dongle.

Charger les appareils et brancher le chargeur de l’ordinateur pour réduire les déconnexions Bluetooth liées à l’économie d’énergie. Choisir les modèles et rôles, sélectionner **Thymio**, puis calibrer chaque appareil.

Calibrate démarre la chaîne nécessaire à la calibration. Avec deux EEG, le frontend demande Stop après chaque calibration ; avec un seul EEG, la chaîne peut continuer. Après une calibration réussie, il est recommandé de cliquer sur Stop si elle fonctionne encore, de vérifier l’immobilité du robot, puis de cliquer sur Start pour la commande proprement dite. Cela sépare les phases et recharge les dernières références. Ce n’est pas une condition obligatoire pour que les nouveaux paramètres de calibration d’un EEG unique prennent effet.

Contrôle arrêté, il est aussi possible d’ajuster manuellement les références min / max de chaque appareil, puis de cliquer sur Start. Ce ne sont pas les extrema de l’EEG brut. Utiliser normalement la calibration automatique avant un éventuel ajustement manuel.

Des commandes peuvent être émises brièvement entre la fin de calibration et l’arrêt effectif. Avant la calibration, poser le Thymio sur une surface plane et sûre, sans obstacle à proximité et loin d’un bord de table ou d’une marche. Voir le [manuel opérateur](docs/MANUEL_OPERATEUR.md) pour les opérations et l’ordre d’arrêt, et le [guide de dépannage](docs/GUIDE_DEBUG.md) pour les problèmes courants.

## Configuration

| Fichier | Usage |
|---|---|
| `windows_launcher/config.json` local à Windows | Nom / chemins WSL, cible de synchronisation, interpréteurs, services et commandes USB ; exclu de la synchronisation |
| [launch_args.yaml](thymio_control/config/launch_args.yaml) | Robot réel / simulation, activation des nœuds et entrée du pilote |
| [eeg_control_node.params.yaml](thymio_control/config/eeg_control_node.params.yaml) | Indicateur, source_id, calibration et mouvement de la première configuration EEG |
| [eeg_control_node.eeg2.params.yaml](thymio_control/config/eeg_control_node.eeg2.params.yaml) | Paramètres indépendants de la deuxième configuration, sans association permanente à un modèle |

Utiliser le web au quotidien. Il enregistre les YAML du code source ; ROS launch lit par défaut les fichiers installés. Voir la [configuration](docs/GUIDE_DEVELOPPEUR.md#53-les-trois-périmètres-de-configuration) pour leur cohérence et l’enregistrement de la calibration. Les valeurs versionnées peuvent provenir d’une exécution particulière ; elles ne sont pas universelles pour tous les utilisateurs.

## Organisation du dépôt

```text
windows_launcher/       Contrôle Windows et cycle de vie des appareils
gtec_bridge/            Ponts Windows API des appareils → LSL
thymio_control/
  launch/               Lancements ROS
  scripts/              Nœuds EEG et fusionneur à deux voies
  thymio_control/       Adaptateurs, traitement, stratégies, calibration, watchdog
  config/               Paramètres YAML et ressources de simulation
  test/                 Tests du contrôle
  lsl_test/             LSL synthétique et validation hors ligne
web_gui/
  backend/              FastAPI, RosBridge, configuration et processus
  frontend/             React, Vite, ECharts
src/                    Dépendances ROS Thymio / Aseba
docs/                   Manuels et références
```

## Tests

Dans WSL, à la racine, après installation des dépendances et compilation :

```bash
source /opt/ros/kilted/setup.bash
source install/setup.bash
source .venv/bin/activate
python -m pytest thymio_control/test -v
python -m pytest windows_launcher/tests -v
python -m pytest thymio_control/lsl_test -v
```

Pour le backend, utiliser un autre terminal ayant chargé le même environnement ROS, en partant de la racine :

```bash
cd web_gui/backend
../../.venv/bin/python -m pytest app -v
```

Compiler le frontend avec `npm run build` depuis `web_gui/frontend`. Le pytest par défaut à la racine n’inclut pas le backend. Les tests du launcher utilisent un fake executor, sans commandes Windows réelles. Un skip dû à une dépendance ou à des données manquantes n’est pas une réussite. Voir les [tests du guide développeur](docs/GUIDE_DEVELOPPEUR.md#7-modifications-et-tests) pour le périmètre et les vérifications matérielles.

## Précautions d’utilisation

- Garder de l’espace autour du robot. Avant une pause, un dépannage ou la fermeture, cliquer sur Stop et vérifier l’arrêt réel. Fermer ou rafraîchir le navigateur n’est pas une commande d’arrêt.
- Le seuil de protection contre la perte de données n’est pas une garantie mesurée d’arrêt du robot. S’il reste Running, le retour des données peut relancer les mouvements. Vérifier les effets d’une panne du navigateur / réseau sur le système utilisé.
- L’interface peut commander réellement le robot. La réserver à l’ordinateur local ou à un réseau de confiance vérifié ; ne pas l’exposer directement à Internet. Le dry-run ne bloque pas toutes les commandes de mouvement : isoler la sortie réelle pendant les tests.
- L’enregistrement de l’EEG brut n’est pas implémenté. Les graphiques et indicateurs traités ne le remplacent pas et ne constituent pas un diagnostic d’attention validé. Gérer l’accès et la sauvegarde des données selon le périmètre d’utilisation du projet.
- La partie 4 reste dédiée à la collecte d’indicateurs traités et d’informations de contrôle par les développeurs pour valider le système. Elle n’est pas nécessaire à la commande quotidienne EEG / Thymio ; elle pourra être masquée ou supprimée.

L’ancien répertoire `experiment_data/` a été retiré de l’espace de travail actuel ; l’historique Git n’a pas été effacé. La collecte peut encore produire de nouveaux fichiers d’analyse. Tout le répertoire de sortie par défaut `experiment_data/` est ignoré par Git.

## Documentation

| Document | Usage |
|---|---|
| Ce README | Présentation, architecture, installation, démarrage et accès au développement |
| [Manuel opérateur](docs/MANUEL_OPERATEUR.md) | Utilisation quotidienne d’un ordinateur installé |
| [Guide de dépannage](docs/GUIDE_DEBUG.md) | Problèmes EEG, robot, interface et USB |
| [Dossier technique](docs/DOSSIER_TECHNIQUE.md) | Produit, exigences, algorithmes, interfaces et conception |
| [Guide développeur](docs/GUIDE_DEVELOPPEUR.md#documentation-du-projet) | Installation, lecture du code, diagnostic, tests, mises à jour, sauvegarde et restauration |

Voir aussi les notices [Windows launcher](windows_launcher/README.md) et [Web GUI](web_gui/README.md), et la [référence des formats de données](docs/reference/DONNEES_EXPERIMENTALES.md). Les anciens guides, l’historique de conception et les plans de recherche sont conservés dans [docs/archived/](docs/archived/) ; ils ne constituent ni un point d’entrée actuel, ni une référence d’exigences, ni un autre guide officiel d’installation.

## Composants tiers

Le dépôt contient des sources tierces ROS Thymio / Aseba. Leurs licences et mentions sont conservées dans leurs répertoires, par exemple la [LICENSE de ros-thymio](src/ros-thymio/LICENSE). Les SDK g.tec se préparent séparément et ne sont pas fournis par la liste pip. Les autorisations des composants ne doivent pas être présentées comme une licence unique pour tout le projet.

Les licences SDK se préparent séparément. Les conditions, l’état et la migration de la licence de l’API Hybrid Black sont décrits dans le [guide développeur](docs/GUIDE_DEVELOPPEUR.md#licence-de-lapi-hybrid-black). Ne pas enregistrer les clés complètes dans le dépôt.

---

[Version chinoise](docs/zh/README_cn.md)
