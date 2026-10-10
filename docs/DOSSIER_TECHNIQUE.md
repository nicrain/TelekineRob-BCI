# TelekineRob-BCI — Dossier technique

[Retour à la présentation du projet](../README.md)

Présentation du produit · Exigences techniques · Conception du système

| Informations | Contenu |
|---|---|
| Version / date | v0.4 / 2026-10-09 |
| Référence de vérification de l’implémentation | `ce1ed66` sur `main` ; distinction entre réalisation actuelle et exigences de la prochaine phase |
| Public | Responsables du projet, développeurs et utilisateurs souhaitant comprendre les limites du système |
| Environnement visé | Windows + WSL2, Ubuntu 24.04, ROS2 Kilted ; sans garantie de compatibilité avec toutes les versions |
| État de validation | Voir le [périmètre des vérifications](#41-périmètre-des-vérifications) pour le code et les tests exécutés ; aucune trace complète de validation de la simulation intégrale ou du matériel sur l’ordinateur cible |

Ce document rassemble la définition du produit, les exigences et la conception actuelles. Ce n’est ni un guide d’installation par commandes, ni un tutoriel de clics. Voir le [manuel opérateur](MANUEL_OPERATEUR.md) pour l’usage quotidien, le [guide de dépannage](GUIDE_DEBUG.md) pour la récupération, et le [guide développeur](GUIDE_DEVELOPPEUR.md) pour l’installation, le diagnostic, les mises à jour et la restauration.

## Navigation

- Responsables : [Produit](#1-présentation-du-produit) → [Exigences](#2-exigences-techniques) → [Recette et validation](#4-recette-et-état-de-validation).
- Nouveaux développeurs : [Architecture générale](#31-architecture-générale) → [Traitement EEG](#35-traitement-du-signal-eeg) → [Configuration et interfaces](#39-configuration-et-persistance) → [Limites et informations à confirmer](#5-limites-actuelles-et-informations-à-confirmer).
- Accès rapide : [Démarrage et états](#33-démarrage-et-états) · [Connexions](#34-connexions-des-appareils) · [Calibration automatique](#37-calibration) / [Réglage manuel](#réglage-manuel-des-valeurs-de-calibration) · [Perte de données et reprise](#38-perte-de-données-et-reprise) · [Interfaces](#310-interfaces-et-contrats-de-données) · [Tests](#41-périmètre-des-vérifications).
- Priorité de développement : [Deux g.tec du même modèle](#25-prochaine-priorité--deux-gtec-du-même-modèle) → [Feuille de route](GUIDE_DEVELOPPEUR.md#75-priorité--intégrer-deux-gtec-du-même-modèle).

## 0. Distinguer faits, exigences et preuves

Trois catégories de preuves sont utilisées :

1. **Confirmé par le code** : une implémentation existe dans les sources ou configurations actuelles ; cela ne prouve pas son exécution réussie sur l’ordinateur cible.
2. **Confirmé par l’utilisateur** : information issue de l’usage du projet, par exemple Bluetooth intégré, port USB prévu ou lancement manuel du Headband. Elle n’est pas généralisée à tous les ordinateurs ou appareils du fabricant.
3. **Confirmé par les tests** : uniquement un résultat avec environnement et exécution identifiés. La présence d’un test ou une revue de code ne signifie pas qu’un test a réussi.

Les identifiants d’exigences servent à relier implémentation et recette, sans signifier que tout est validé. Les performances, valeurs locales et informations de licence « à confirmer » exigent des preuves ; elles ne doivent pas devenir des garanties du produit.

## 1. Présentation du produit

### 1.1 Objectif

TelekineRob-BCI convertit l’EEG acquis par les appareils g.tec en commandes de mouvement Thymio. Son interface web permet connexion, choix des paramètres, calibration, observation et arrêt du contrôle.

Les scénarios principaux sont la commande individuelle avec un appareil et la coopération à deux personnes, chacune utilisant un appareil pour la vitesse ou la direction. La simulation et la commande manuelle sont conservées pour développer et vérifier les chaînes. Il n’existe pas encore de trace complète de validation du parcours ROS / Gazebo / interface web.

La « commande par attention » désigne ici une conversion stratégique de l’indicateur EEG choisi, à partir des paramètres de calibration. Ce n’est ni une lecture directe de l’intention, ni un diagnostic ou une intervention sur l’attention validés. Le document ne définit pas de protocole clinique et ne garantit ni bénéfice thérapeutique ni précision homogène entre participants.

### 1.2 Acteurs et responsabilités

| Acteur | Responsabilités |
|---|---|
| Opérateur non informaticien | Démarrer, connecter, calibrer, contrôler, arrêter et résoudre les petits problèmes suivant les manuels |
| Porteur EEG | Assurer le rôle Speed ou Steering prévu pour la tâche |
| Développeur | Déployer, diagnostiquer, modifier, vérifier, sauvegarder, restaurer et maintenir |
| Responsable du projet | Définir configuration, périmètre d’usage, critères de recette et accès aux données |

### 1.3 Matériel et logiciels

| Composant | Usage actuel |
|---|---|
| Ordinateur Windows et Bluetooth intégré | System Control, connexions EEG et ponts |
| g.tec BCI Core-4 Headband | EEG à 4 canaux, publié en LSL via gpype |
| Unicorn Hybrid Black | EEG à 8 canaux, publié en LSL via UnicornPy |
| Thymio et dongle USB | Commande sans fil ; dongle attaché de Windows à WSL |
| WSL2 / Ubuntu | ROS2, traitement du signal et services web |
| Navigateur | System Control et interface EEG |

Sur l’ordinateur d’origine, les deux EEG utilisent le Bluetooth intégré pour sa stabilité constatée, et non sur exigence générale du fabricant. Voir les [connexions](#34-connexions-des-appareils) pour les raisons et limites de migration. Le dongle Thymio reste nécessaire ; ce n’est pas l’adaptateur Bluetooth EEG.

Les versions et réglages locaux sont décrits dans le [contrôle de l’environnement](GUIDE_DEVELOPPEUR.md#21-référence-denvironnement-et-vérifications). Les vérifications Bluetooth, alimentation et batteries sont dans le [guide de dépannage](GUIDE_DEBUG.md#1-vérifications-avant-chaque-utilisation).

### 1.4 Les deux pages et le parcours normal

| Page / entrée | Responsabilités | Signification des états |
|---|---|---|
| System Control ouvert par `launcher.bat` | Démarrage / arrêt WSL et web, connexions, états, logs et récupération web | Running signifie surtout que les services web sont prêts, pas que l’EEG commande le robot |
| Thymio EEG Control dans la zone principale | Entrées, rôles, indicateurs, sortie, calibration, observation, Start / Stop | Running en haut est un indicateur local du frontend ; ce n’est ni un contrôle continu de santé ROS ni une vérification appareils / données |

Ni l’état du frontend ni le marqueur `running` du backend ne surveillent continuellement les sous-processus ROS. Si Start / Stop échoue ou si un sous-processus se termine, les boutons seuls ne prouvent pas le démarrage ou l’arrêt. Vérifier nœuds, messages et réponse du robot selon le [diagnostic ROS](GUIDE_DEVELOPPEUR.md#63-vérifications-wsl-web-et-ros).

Parcours normal :

```text
Vérifier ordinateur et appareils
  → Ouvrir System Control → Start System
  → Connecter les EEG nécessaires et le Thymio réel (inutile en simulation)
  → Choisir Role / Device / Brand / Metric / Output Target
  → Calibrer les appareils successivement
  → Vérifier les résultats ; Stop puis Start recommandés avant le contrôle
  → Stop pour une pause ou à la fin
  → Ctrl+C du Headband → Stop System → Exit Launcher
```

Stop / Start désigne ici les boutons de l’interface EEG, et non Stop System / Start System. Une calibration à un appareil peut laisser le contrôle actif ; à deux appareils, le frontend demande Stop à la fin de chaque calibration. Séparer calibration et contrôle est recommandé, sans signifier que toutes les nouvelles valeurs nécessitent un redémarrage pour prendre effet ; voir l’[état après calibration](#état-du-contrôle-après-calibration). Le Headband exige aussi les étapes manuelles VS Code décrites dans les [connexions](#34-connexions-des-appareils). Le parcours actuel n’est donc pas entièrement « sans terminal ».

### 1.5 Modes et signification des mouvements

| Mode | Configuration | Mouvement / usage |
|---|---|---|
| Un EEG, vitesse | Première ligne Role=Speed, Device=EEG ; deuxième None | Vitesse avant selon l’indicateur, sans direction |
| Un EEG, direction | Première ligne Role=Steering, Device=EEG ; deuxième None | Rotation sur place ; clignement pour changer gauche / droite |
| Deux EEG coopératifs | Speed et Steering | Fusion avance / rotation ; les deux voies doivent rester valides |
| Vérification manuelle | Une ligne Device=Keyboard ; deuxième None | Boutons souris / tactiles pour vérifier la chaîne robot |
| Simulation, développement | Output Target=Thymio Simu | Sortie vers Thymio dans Gazebo ; parcours complet à valider, sans preuve sur USB ou moteurs réels |

La combinaison actuelle à deux appareils est Headband + Hybrid Black. Chaque modèle a un source_id fixe ; l’identité unique de plusieurs appareils identiques n’est pas gérée. « Deux EEG » ne signifie donc pas que deux appareils quelconques fonctionnent directement.

Le double appareil de même modèle est une exigence confirmée pour la prochaine phase, pas une fonction livrée ; voir la [section 2.5](#25-prochaine-priorité--deux-gtec-du-même-modèle).

Steering seul commande une rotation sur place. La fusion à deux appareils peut associer avance et rotation. Les boutons gauche / droite Keyboard utilisent d’autres paramètres manuels ; leur mouvement ne reprend pas nécessairement la rotation sur place EEG.

### 1.6 Affichage et résultats observables

Les graphiques montrent les séries de puissances fréquentielles, indicateurs dérivés, intentions de contrôle et références de calibration. Ce n’est pas un oscilloscope de tension brute par électrode. « Temps réel » signifie mise à jour continue, pas absence de latence, rafraîchissement web à 250 Hz ou enregistrement brut précisément synchronisé.

État vert, graphiques alimentés, Running et mouvement du robot sont des preuves distinctes :

- EEG vert : la sonde LSL Windows a reçu des échantillons valides.
- Thymio vert : le contrôle de périphérique WSL configuré a réussi, actuellement la présence de `/dev/ttyACM0`.
- Graphiques actualisés : les analyses ont traversé ROS et le backend jusqu’au navigateur.
- Mouvement : sortie correctement réglée, commandes valides, pilote et robot fonctionnels sont également nécessaires.

Conserver le test Keyboard pour un Thymio immobile ; voir le [dépannage utilisateur](GUIDE_DEBUG.md#b-le-thymio-ne-bouge-pas).

### 1.7 Limites du produit

- La chaîne EEG actuelle accepte uniquement LSL.
- Start System n’installe pas les SDK, n’effectue pas le premier appairage Bluetooth Windows, le partage USB, la compilation ROS ou la configuration locale.
- Pas de gestion complète de comptes, rôles d’accès, déploiement Internet ou mises à jour automatiques.
- Aucune preuve garantissant durée continue, taux de déconnexion, latence totale ou performance de classification par utilisateur.
- L’enregistrement de l’EEG brut n’est pas implémenté. La partie 4 de l’interface sert uniquement aux développeurs à collecter des indicateurs traités et informations de contrôle pour valider le système. Non nécessaire à l’usage quotidien, elle reste présente mais pourra être masquée ou supprimée.
- Des parcours de suivi de ligne et RViz restent dans le code, sans faire partie des fonctions validées de ce parcours EEG standard. Leur activation nécessite une validation distincte.

## 2. Exigences techniques

### 2.1 Périmètre et règles de recette

Les sections 2.2 à 2.4 définissent les exigences et limites actuelles. La [section 2.5](#25-prochaine-priorité--deux-gtec-du-même-modèle) isole les exigences confirmées mais non réalisées de la prochaine phase. Implémentation, tests automatisés et recette cible sont enregistrés séparément et ne se remplacent pas.

Avant chaque test, préciser robot réel ou simulation. Placer le robot réel sur une surface plane et sûre, avec de l’espace, sans obstacle, loin des bords et marches pour éviter collision ou chute après calibration ou reprise des données. Avant reconnexion, reconfiguration ou redémarrage, arrêter le contrôle et vérifier l’immobilité. La trace de recette indique commit, configuration, environnement, étapes, attendu et observé. Un échec ou skip n’est pas une réussite.

### 2.2 Exigences fonctionnelles

| Identifiant | Exigence et critère de réussite | Conception | Vérification / état actuel |
|---|---|---|---|
| RF-01 | System Control démarre les services web et affiche le résultat ; un échec ne doit pas être présenté comme Running | [Démarrage](#33-démarrage-et-états) | Implémenté ; démarrage, arrêt et échecs à tester sur la cible |
| RF-02 | Connect Headband ouvre le script ; après exécution manuelle, l’état repose sur les données ; l’interruption permet la déconnexion | [Connexions](#34-connexions-des-appareils) | Parcours confirmé par l’utilisateur ; interpréteur, API et états à revérifier |
| RF-03 | Connect / Disconnect Hybrid démarre / arrête le pont supervisé ; connexion confirmée par échantillons LSL | [Connexions](#34-connexions-des-appareils) | Implémenté ; SDK et matériel cible à tester |
| RF-04 | Le dongle partagé 1-1 peut être attaché au WSL configuré et réussir le contrôle périphérique ; procédure du nouveau dongle accessible | [Thymio](#34-connexions-des-appareils) | Configuration et procédure vérifiées ; USB, appairage et moteurs à tester |
| RF-05 | Un EEG choisit Speed ou Steering ; deux EEG ont des rôles distincts et lisent les bons source_id | [Routage](#36-stratégies-et-conversion-en-mouvement) | Modèles et code implémentés ; permutations appareils / rôles à tester |
| RF-06 | Choix Alpha, TBR, EI ; calibration et EMA propres à la voie | [Traitement](#35-traitement-du-signal-eeg), [stratégies](#36-stratégies-et-conversion-en-mouvement) | Implémenté ; indicateurs retenus et effet de contrôle à confirmer |
| RF-07 | Acquisition de 30 s à partir du premier indicateur valide ; au moins 50 échantillons d’indicateur pour sauvegarder ; sinon état de calibration effacé | [Calibration](#37-calibration) | Tests de décision / écriture réussis ; chaîne complète à tester |
| RF-08 | Calibration séparée, sans écraser l’autre voie ; démarrage ultérieur lit les résultats sauvegardés | [Configuration](#39-configuration-et-persistance) | Implémenté ; indépendance à confirmer sur deux appareils |
| RF-09 | Fusion : linear.x de Speed, angular.z de Steering, autres composantes Twist nulles | [Mouvement](#36-stratégies-et-conversion-en-mouvement) | Tests de fonction pure réussis ; routage ROS / moteurs à tester |
| RF-10 | Un clignement confirmé bascule Steering ; intention neutre pendant confirmation et délai réfractaire | [Clignements](#36-stratégies-et-conversion-en-mouvement) | Tests du détecteur réussis ; clignements volontaires / naturels à mesurer |
| RF-11 | Données périmées : commande nulle en voie unique ; voie absente / périmée en double : commande nulle globale | [Perte de données](#38-perte-de-données-et-reprise) | Tests watchdog / fusion réussis ; arrêt et reprise complets à tester |
| RF-12 | Graphiques séparés par role avec analyses fraîches ; connexion distincte de l’actualisation EEG | [Affichage](#310-interfaces-et-contrats-de-données) | Implémenté ; permutation, perte de données et rafraîchissement à tester |
| RF-13 | Keyboard envoie direction et arrêt, pour distinguer EEG et chaîne robot | [Commande manuelle](#36-stratégies-et-conversion-en-mouvement) | Parcours souris / tactile vérifié ; mouvement et arrêt réels à tester |
| RF-14 | Stop web, interruption Headband, Stop System et Exit Launcher ont des responsabilités documentées distinctes | [Cycle de vie](#33-démarrage-et-états) | Code et manuels vérifiés ; processus résiduels et arrêt réel à tester |
| RF-15 | Paramètres sauvegardés / rechargeables ; Min / Max modifiables par voie à l’arrêt et lus au Start suivant ; chemins source renvoyés pour repérer un mauvais dépôt | [Réglage manuel](#réglage-manuel-des-valeurs-de-calibration), [configuration](#39-configuration-et-persistance) | config_store / interface implémentés ; réglage et cohérence source / install à tester |
| RF-16 | Logs et récupération web accessibles ; informations conservables avant redémarrage / diagnostic | [Observabilité](#311-erreurs-et-observabilité) | Chemins vérifiés ; erreurs réelles et récupération à tester |

### 2.3 Exigences non fonctionnelles et limites

| Identifiant | Exigence | Réalisation / limite | Critère de réussite |
|---|---|---|---|
| RN-01 Arrêt sûr | Préciser fraîcheur, commande nulle et reprise | Watchdogs logiciels, pas arrêt d’urgence matériel | Mesurer arrêt / reprise ; utilisateur informé d’une reprise possible |
| RN-02 Temps réel | Pas d’accumulation d’anciennes fenêtres traitées ; cadences explicites | Dernier PSD seulement ; fréquences différentes, sans temps réel dur | Noter latences / blocages ; seuils numériques fixés par le responsable puis mesurés |
| RN-03 Utilisabilité | Parcours courant suivant les manuels non techniques | VS Code pour Headband ; PowerShell pour un partage exceptionnel | Utilisation autonome complète ; boutons / captures conformes au réel |
| RN-04 Maintenabilité | Paramètres, responsabilités et tests traçables | YAML / JSON et modules existants ; pas toutes les constantes configurables | Nouveau développeur capable de localiser, modifier et vérifier un petit problème |
| RN-05 Reproductibilité | Dépendances et licences récupérables sur un nouvel ordinateur | requirements / npm lock ne couvrent pas tout ROS / SDK Windows | Versions et sources enregistrées ; reproduction sur cible documentée |
| RN-06 Exactitude des états | Affichage cohérent avec l’objet réellement sondé | Vert / Running limités ; santé ≠ recette complète | Tester séparément services, LSL, ROS et robot |
| RN-07 Réseau | Contrôle réel ouvert uniquement au périmètre autorisé | Loopback, origin, token optionnel ≠ authentification complète ; proxy à vérifier | Vérifier écoute, redirection et clients ; pas d’exposition directe à un réseau non fiable |
| RN-08 Données / sauvegarde | Distinguer configurations, analyses, logs, brut ; restauration prévue | JSON local exclu de synchronisation ; tout `experiment_data/` ignoré, historique conservé ; chemins personnalisés à vérifier | Définir données conservées, droits, sauvegarde et validation de restauration |

### 2.4 Indicateurs quantitatifs non fixés

Seuls les réglages du code sont consignés ; aucun seuil de performance non confirmé n’est imposé :

| Sujet | Connu | À confirmer |
|---|---|---|
| Acquisition / affichage | Profils nominaux 250 Hz, valeurs réelles issues de StreamInfo ; PSD 1 s, pas 0,5 s | Débit effectif, gigue et latence d’affichage sur cible |
| Contrôle | Nœuds EEG et fusionneur 20 Hz par défaut ; boucle web environ 0,2 s | Ordonnancement, réponse complète, latences matériel / moteurs |
| Arrêt | Fraîcheur et commandes nulles implémentées | Délai jusqu’à immobilité ; pannes navigateur / réseau |
| Qualité | Indicateurs, calibration, clignements confirmés et EMA | Réussites, mouvements erronés, faux clignements, stabilité entre personnes / sessions |
| Continuité | Reconnexion / reconstruction dans les ponts | Durée continue, fréquence de déconnexion, taux de reconnexion |
| Compatibilité | Pile cible définie | Combinaison réelle OS, SDK, Python, ROS / Gazebo et outils |

### 2.5 Prochaine priorité : deux g.tec du même modèle

**État : exigence confirmée, non implémentée. La concurrence à deux appareils du SDK installé et le comportement réel restent à valider sur place.**

Objectif : acquérir simultanément deux EEG g.tec du même modèle sur un système Windows + WSL2, associer Speed et Steering et commander un Thymio. Combinaisons visées : deux Hybrid Black et deux Headband. L’ordre dépend du matériel disponible et de la vérification SDK. Conserver les modes à un appareil et Headband + Hybrid Black.

Le périmètre n’inclut ni nombre arbitraire d’EEG, ni plusieurs robots, ni synchronisation stricte des signaux bruts entre appareils. Débloquer simplement le même modèle dans l’interface ne suffit pas. Les deux nœuds ROS et le fusionneur sont réutilisables, mais découverte, identité unique, cycle de vie, configuration et sondes doivent être vérifiés.

| Identifiant | Nouvelle exigence et critère | Manque actuel / base de recette |
|---|---|---|
| RF-NEXT-01 Acquisition concurrente | Deux appareils réels identiques produisent simultanément des flux distincts et continus ; versions SDK, mode, durée et anomalies consignés | Non testé sur cible ; licence à confirmer avec Lucas, limites SDK avec fabricant / support ; simulation insuffisante |
| RF-NEXT-02 Identité | Modèle, numéro de série, source_id unique stable et rôle distincts ; impossible de sélectionner deux fois le même appareil | ID fixé par modèle ; identité cohérente ponts / sondes / configuration / ROS ; jamais choisir arbitrairement le premier flux valide en conflit |
| RF-NEXT-03 Cycle de vie indépendant | État / logs par appareil ; déconnecter / reconnecter A ne rebind pas B ; A reprend son numéro de série initial | Hybrid choisit la première unité ; watchdog Headband par nom, sonde launcher par premier source_id ; ne pas utiliser B pour prouver A actif ; conserver le parcours IDE manuel |
| RF-NEXT-04 Configuration / calibration | Choisir deux unités d’un modèle ; conserver identité / rôle après sauvegarde, rafraîchissement et redémarrage ; calibration indépendante | Même modèle interdit ; ID reconstruit par modèle ; calibration par configuration, pas par appareil physique ; changement d’appareil / conditions implique recalibration ou vérification |
| RF-NEXT-05 Signal / contrôle | Changer l’identité ne désactive pas le filtrage requis ; vérifier fréquence, canaux et unités ; permutation des rôles cohérente | Filtrage Hybrid dépend du nom du flux ; séparer modèle et identité ; garder les topics partiels et la fusion |
| RF-NEXT-06 Sécurité / compatibilité | Protection nulle du fusionneur si une voie disparaît ; régression un appareil, modèles différents, calibration et arrêt | Seuil logiciel 0,5 s ≠ garantie d’arrêt global ; reprise possible si Running ; mesurer / consigner, sans désactiver la protection |

Deux licences Hybrid Black API ne prouvent ni l’autorisation ni la capacité d’acquérir simultanément deux appareils sur une machine. Vérifier capacités SDK et conditions applicables. État, contact et migration sont dans les [licences du guide développeur](GUIDE_DEVELOPPEUR.md#licence-de-lapi-hybrid-black).

Étapes, fichiers, vérification minimale et régressions sont regroupés dans la [section développeur 7.5](GUIDE_DEVELOPPEUR.md#75-priorité--intégrer-deux-gtec-du-même-modèle), sans duplication ici. Enregistrer RF-NEXT séparément de la base RF actuelle. Sans réussite sur deux appareils réels, rapporter uniquement les progrès de validation logicielle.

## 3. Conception du système

### 3.1 Architecture générale

```text
Windows
  Bluetooth intégré ← Headband / Hybrid Black
  gpype_lsl_bridge.py / unicornpy_lsl_bridge.py → LSL
  launcher.bat → launcher_server.py (8020) → System Control
       ├─ vérification WSL, synchronisation, services web, sonde LSL
       └─ usbipd attach (1-1) → périphérique série USB dans WSL

WSL / Ubuntu
  Nœud EEG : LSL → RawLslAdapter (préfiltrage / PSD)
                  → enrich_features → Policy → conversion selon rôle
       ├─ une voie : topic vitesse finale
       └─ deux voies : /eeg_cmd_vel/<role> → cmd_vel_fuser → vitesse finale
  Vitesse finale → pilote Thymio → robot réel
                ou pont Gazebo → simulation
  Topics analyse → RosBridge → FastAPI (8010) → WebSocket
  React / Vite (5173) ← affichage / paramètres / commandes

Navigateur
  System Control local intègre Thymio EEG Control
  Accès à /api et /ws via proxy Vite, sans exposition directe requise de 8010
```

Les ports, distribution, chemins et BUSID sont la base du dépôt, modifiables par la configuration locale. Voir [windows_launcher/config.json](../windows_launcher/config.json).

Un seul dépôt WSL sert de source de synchronisation du launcher et des ponts pour éviter deux codes divergents ; ce n’est pas une récupération automatique des mises à jour distantes. La configuration Windows reste locale ; voir le [guide développeur](GUIDE_DEVELOPPEUR.md#22-chemins-et-modèle-de-configuration).

### 3.2 Modules et choix de conception

| Module | Responsabilité / entrée | Raison / limite |
|---|---|---|
| Contrôle Windows | [launcher_server.py](../windows_launcher/launcher_server.py) | Le navigateur ne peut pas exécuter directement wsl, usbipd ou Python ; service local responsable des commandes et états |
| Pont Headband | [gpype_lsl_bridge.py](../gtec_bridge/gpype_lsl_bridge.py) | SDK Windows, lancement IDE actuel, reconstruction de chaîne pour certaines pertes de données |
| Pont Hybrid | [unicornpy_lsl_bridge.py](../gtec_bridge/unicornpy_lsl_bridge.py) | UnicornPy → LSL ; processus supervisé par launcher, reconnexion après certaines erreurs |
| Adaptateur | [lsl_raw.py](../thymio_control/thymio_control/adapters/lsl_raw.py) | Interface read_frame et StreamInfo ; pas preuve de compatibilité avec tous les appareils LSL |
| Traitement | [band_power.py](../thymio_control/thymio_control/processors/band_power.py), [enrich.py](../thymio_control/thymio_control/processors/enrich.py) | PSD streaming, unités et caractéristiques découplés de ROS, donc testables |
| Stratégies | [pipeline.py](../thymio_control/thymio_control/pipeline.py), policies | Registre Alpha / TBR / EI, calibration et lissage propres à chaque voie |
| Nœud EEG | [eeg_control_node.py](../thymio_control/scripts/eeg_control_node.py) | Assemble données, calibration, stratégie, clignements, vitesse, analyse et watchdog |
| Fusion | [cmd_vel_fuser.py](../thymio_control/scripts/cmd_vel_fuser.py) | Évite deux nœuds écrivant la vitesse finale ; fusion par rôle, zéro si une voie est périmée |
| Orchestration ROS | [experiment_core.launch.py](../thymio_control/launch/experiment_core.launch.py) | Topologie réelle / simulée, deuxième nœud renommé, topics par rôle |
| Backend | [main.py](../web_gui/backend/app/main.py), [config_store.py](../web_gui/backend/app/config_store.py), [command_runner.py](../web_gui/backend/app/command_runner.py) | API, configuration et processus séparés ; le frontend n’exécute pas les commandes directement |
| Pont ROS web | [signal_subscriber.py](../web_gui/backend/app/signal_subscriber.py) | Abonnements et file Teleop dans un thread rclpy, sans conflit d’exécuteurs |
| Frontend | [App.jsx](../web_gui/frontend/src/App.jsx), [api.js](../web_gui/frontend/src/api.js) | Affichage par rôle, calibration et contrôle ; pas le cœur du traitement du signal |

Séparer stratégies et adaptateurs facilite tests et extensions. Registre, modèles et choix UI limitent ensemble les stratégies disponibles ; voir les [points d’extension](GUIDE_DEVELOPPEUR.md#73-couches-à-vérifier-lors-dune-extension).

ROS-Aseba / ROS-Thymio sont les versions suivies par ce projet, avec modifications de compatibilité et simulation ; ce ne sont pas exactement les sources amont. Sources figées, différences et limite `use_sim_time` : [section 5.5 développeur](GUIDE_DEVELOPPEUR.md#55-sources-tierces-et-modifications-du-projet).

### 3.3 Démarrage et états

System Control : Stopped, Starting, Running, Stopping, Error. Appareils : Disconnected, Connecting, Connected, Disconnecting, Error, indépendamment. Voir [state.py](../windows_launcher/state.py).

Chaîne Start System :

```text
Vérifier WSL / accès au répertoire partagé
  → robocopy du launcher et des ponts (hors config.json Windows)
  → nettoyer anciens processus web → démarrer backend / frontend
  → vérifier services → tenter la mise à jour de redirection LAN et la sonder
  → Running ou Error
```

L’échec de redirection LAN diffère d’un échec web : il ne bloque pas nécessairement le démarrage local. Les services sont aussi contrôlés pendant le fonctionnement. Le bouton est Restart System en Running et Start System en Stopped / Error.

Start web demande d’abord l’arrêt de l’ancienne chaîne, sauvegarde / recharge la configuration et lance ROS via le backend. Celui-ci force `use_teleop:=false`. Keyboard web n’utilise pas `teleop_twist_keyboard` du launch ; une valeur sauvegardée de `use_teleop` dans `launch_args.yaml` ne suffit pas à déduire la commande lancée par le web.

Responsabilités du cycle de vie :

| Objet | Lanceur | Arrêt / prise en compte des mises à jour |
|---|---|---|
| Service Windows | launcher.bat | Exit Launcher ; quitter / relancer pour actualiser le code déjà chargé |
| Pont Headband | Exécution manuelle VS Code | Ctrl+C ; Disconnect / Stop System ne tuent pas le script IDE |
| Pont Hybrid | launcher | Disconnect / Stop System terminent le processus ; nouveau processus lit le script synchronisé |
| Backend / frontend | launcher via WSL | Restart Web / Stop System ; arrêter le contrôle avant redémarrage |
| Chaîne ROS | command_runner du backend | Stop web ; nettoyage par noms pouvant affecter d’autres tâches correspondantes |
| Distribution WSL | Commandes WSL | Stop System termine par défaut la distribution entière, pas seulement le projet |

Les requêtes Start / Stop contiennent `dry_run`, par défaut true dans le modèle, mais false dans les requêtes normales du frontend. `WEB_GUI_ALLOW_REAL_COMMANDS` vaut true par défaut. False bloque les commandes ROS réelles de ce parcours de lancement, pas la publication Teleop directe : ce n’est pas un blocage global des mouvements. Isoler la sortie réelle pendant les tests ; voir les [limites réseau et commandes](#312-réseau-commandes-et-données).

### 3.4 Connexions des appareils

**Headband.** Le dépôt définit `connect_mode=open_in_ide`. System Control ouvre le script synchronisé et attend des échantillons LSL, sans superviser le pont. L’opérateur l’exécute et l’interrompt dans VS Code Windows. Le délai d’attente actuel est 120 s, sans garantie de connexion dans ce délai. Ce parcours est lié à la licence g.Pype applicable ; il ne signifie ni que l’API ne peut pas connecter par code, ni que VS Code est le seul IDE autorisé. Voir les [conditions SDK](GUIDE_DEVELOPPEUR.md#38-conditions-sdk-et-modes-de-connexion) et les [étapes utilisateur](MANUEL_OPERATEUR.md#connexion-et-déconnexion-du-headband).

Le script relie `BCICore8(channel_count=4)` → passe-bande 0,5–45 Hz → coupe-bande 48–52 Hz → LSLSender. Le nom BCICore8 ne signifie pas huit canaux acquis. Son watchdog reconstruit la chaîne lorsque les données stagnent ; ce n’est pas le watchdog d’arrêt du robot.

**Hybrid Black.** `connect_mode=spawn` lance le pont UnicornPy, qui transmet uniquement huit canaux EEG avec `gtec_hybrid_black` comme source_id fixe. Un échec de la première acquisition termine le processus ; certaines erreurs pendant l’acquisition déclenchent une reconnexion avec temporisation progressive. Cette récupération partielle ne garantit pas la résolution de toute panne Bluetooth / SDK.

L’[API officielle UnicornPy](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md) permet connexion par numéro de série, démarrage / arrêt d’acquisition et libération, sans exécution manuelle imposée dans un IDE. Le projet supervise donc ce pont. SDK et licence Windows restent séparés de Linux ; voir les [conditions SDK](GUIDE_DEVELOPPEUR.md#38-conditions-sdk-et-modes-de-connexion).

Sur l’ordinateur d’origine, l’adaptateur Bluetooth USB fourni avec Hybrid provoquait des déconnexions fréquentes ; le Bluetooth intégré était plus stable. Les deux EEG l’utilisent donc par défaut. Cette expérience locale diffère de la recommandation Suite du fabricant ; revérifier après migration ou ajout d’appareils. Voir le [choix Bluetooth](GUIDE_DEVELOPPEUR.md#choix-du-bluetooth).

**Sonde d’état EEG.** Le launcher utilise le `python_cmd` de l’appareil pour la sonde LSL. Si VS Code exécute le pont mais que l’interpréteur de la sonde manque de pylsl, Connected peut ne pas apparaître. Un processus ou un flux sans échantillons ne suffit pas à passer au vert.

**Thymio.** La commande actuelle est `usbipd attach --wsl=Ubuntu --busid=1-1` ; Disconnect exécute detach. Shared signifie que Windows autorise le partage avec Linux ; Attached signifie que le périphérique est connecté à WSL. bind n’est pas une étape automatique de Connect. Pour un nouveau dongle, voir la [section 4 du dépannage](GUIDE_DEBUG.md#4-vérification-7--contrôler-et-partager-un-nouveau-dongle-thymio).

L’utilisateur confirme que les paires Thymio / dongle sont normalement déjà appairées. La sonde actuelle ne vérifie ni dialogue du pilote ni mouvement. Le programme ne choisit pas un BUSID arbitraire. Les changements de numéro, distribution ou configuration locale sont décrits dans les [conventions de déploiement](GUIDE_DEVELOPPEUR.md#23-conventions-de-déploiement-matériel).

### 3.5 Traitement du signal EEG

**Identité.** Identifiants LSL standard actuels :

| source_id | Canaux du profil | Fréquence nominale du profil |
|---|---|---|
| `gtec_bci_core4` | F8, Fp2, Fp1, F7 | 250 Hz |
| `gtec_hybrid_black` | Fz, C3, Cz, C4, Pz, PO7, Oz, PO8 | 250 Hz |

Les canaux et la fréquence réels sont lus dans StreamInfo ; les profils ne remplacent pas cette vérification. Sans source_id, l’adaptateur cherche type=EEG. Dans les deux modes, il choisit actuellement le premier résultat. Les identifiants doivent être uniques ; une identité vide ou dupliquée ne garantit pas une liaison correcte à deux appareils.

**Prétraitement.** Le Headband appelle les nœuds gpype passe-bande 0,5–45 Hz et coupe-bande 48–52 Hz dans Windows ; voir la [référence SDK](https://gpype.gtec.at/content/7_sdk_reference/index.html). Le pont Windows Hybrid ne les utilise pas. La [référence publique UnicornPy vérifiée](https://github.com/unicorn-bi/Unicorn-Hybrid-Black-Windows-APIs/blob/main/python-api/unicorn-python-api-reference.md) n’expose pas ces fonctions ; l’adaptateur WSL ajoute donc `StreamingPreFilter` aux mêmes fréquences de coupure, avec Butterworth d’ordre 4 et réalisation SOS par défaut. Cela ne signifie pas que le matériel n’applique aucun traitement, ni que les réponses / latences des deux implémentations sont identiques. L’activation actuelle dépend du nom de flux `gtec_hybrid_black`, pas uniquement du source_id. Après changement de nom ou de pont, vérifier l’absence de filtre manquant ou doublé. Voir la [section développeur 5.4](GUIDE_DEVELOPPEUR.md#54-préfiltrage-des-deux-modèles-eeg).

**PSD et unités.** Fenêtre glissante de 1 s et pas de 0,5 s par défaut ; Welch calcule les puissances par canal : delta 1–4, theta 4–8, alpha 8–13, beta 13–30, gamma 30–100 Hz. Définir ces bandes ne signifie pas conserver tout le contenu haute fréquence après prétraitement : le passe-bande limite déjà à 45 Hz.

L’adaptateur moyenne les puissances des canaux, les convertit en µV² et ajoute les indicateurs par canal disponibles. L’unité est lue en priorité dans `source_unit`. Si absente, le DSP suppose µV et avertit ; ce n’est pas une déduction fiable de l’unité constructeur. Vérifier la cohérence entre SDK et métadonnées LSL : un graphique plausible ne suffit pas.

Si plusieurs fenêtres sont terminées, le contrôle ne renvoie que le dernier résultat pour privilégier la réactivité, sans conservation complète de toutes les fenêtres.

**Caractéristiques.** `enrich_features()` calcule :

```text
TBR = theta / (beta + 1e-9)
EI  = beta / (alpha + theta + 1e-9)
Alpha utilise la puissance alpha moyenne
```

L’adaptateur renvoie d’abord `EegFrame(ts, source, metrics)` avec les puissances ; le nœud appelle ensuite `enrich_features()`. `source="lsl_raw"` désigne le type d’adaptateur, pas le source_id ni le numéro de série : il ne distingue pas deux appareils. Le ts actuel est l’horloge murale lors de la création de l’analyse ; les timestamps bruts LSL individuels ne sont pas conservés. Il ne permet pas de garantir une mesure précise de latence acquisition–moteur.

Les flux synthétiques ne reproduisent pas exactement les deux traitements réels. Le nom Hybrid de [dummy_dual_streams.py](../thymio_control/lsl_test/dummy_dual_streams.py) est `hybrid_black_EEG` : il n’active pas le préfiltrage Hybrid déclenché par le nom ci-dessus. Voir le [périmètre de validation](#41-périmètre-des-vérifications).

### 3.6 Stratégies et conversion en mouvement

Les trois stratégies lissent leur indicateur avec une EMA, puis normalisent avec offset / scale de la voie et limitent à 0–1. Le coefficient par défaut est 0,35 ; la première trame prend la valeur courante. Ce coefficient est dans les classes de stratégie, pas un paramètre YAML réglable actuellement dans l’interface.

Pour une valeur normalisée n :

| Stratégie | Origine de n | speed_intent | steer_intent |
|---|---|---|---|
| Alpha | alpha lissé | 1−n | max(0.5, 0.75−0.5n) |
| TBR | theta_beta lissé | 1−n | max(0.5, 0.75−0.5n) |
| EI | beta_alpha_theta lissé | n | max(0.5, 0.25+0.5n) |

Ces formules sont des conversions de commande du logiciel, pas des mesures physiologiques indépendamment validées. scale doit être valide ; la calibration automatique impose au moins 0,001. Mettre directement 0 dans le fichier n’est pas une configuration prise en charge.

Dans le parcours standard `line_mode=''` :

```text
Speed:
  linear.x = max_forward_speed × speed_intent
  angular.z = 0

Steering:
  linear.x = 0
  magnitude = abs(steer_intent − 0.5)
  si magnitude < steer_deadzone : angular.z = 0
  sinon angular.z = −steer_direction × turn_angular_speed × magnitude
```

Unités : m/s et rad/s. Ce sont des échelles de commande, pas des vitesses moteurs mesurées. L’intention de rotation actuelle va de 0,5 à 0,75 ; angular.z n’est donc pas systématiquement `turn_angular_speed`. Les défauts du nœud, du backend et les YAML sauvegardés peuvent différer ; utiliser la configuration réelle confirmée.

Un EEG publie directement la vitesse finale. Deux EEG publient leurs commandes partielles ; le fusionneur prend Speed.linear.x et Steering.angular.z. Première / deuxième voie et modèles ne sont pas définitivement liés aux rôles.

**Clignement et direction.** `MetricBlinkDetector` détecte montée / baisse par rapport à une médiane glissante de 30 trames. Par défaut : au moins 15 trames pour la référence, 2 confirmations successives et 4 trames de délai réfractaire. Seuil Alpha / TBR : référence×2 ; seuil EI : référence×0,5. Pour une montée, si la référence de calibration est positive, `calib_offset + calib_scale` lu à la création du nœud sert aussi de plancher de référence. Sans correction du scale minimal, une calibration automatique donne approximativement p50 ; après réglage manuel, c’est le Max choisi, donc pas toujours p50. Cela n’élimine pas tous les faux déclenchements naturels ou musculaires.

Un événement confirmé multiplie `steer_direction` par −1 ; 1 signifie droite, −1 gauche. Pendant confirmation / délai réfractaire, l’intention vaut 0,5 : l’ancienne commande de rotation non nulle n’est pas figée. Les trames sont celles de l’indicateur, pas les échantillons bruts à 250 Hz.

**Commande manuelle.** Keyboard envoie forward, backward, left, right ou stop via `/ws/teleop`, puis la file RosBridge et le thread ROS publient Twist. Relâcher / quitter le bouton envoie stop ; le frontend répète stop après 200 ms. Ce n’est pas une garantie serveur d’arrêt sur panne réseau. La déconnexion WebSocket actuelle n’envoie pas explicitement zéro ; vérifier ce risque lors de la [recette d’arrêt](#42-scénarios-de-recette-sur-lordinateur-cible).

### 3.7 Calibration

#### Calibration automatique et enregistrement

```text
Calibrate sur une voie
  → enregistrer calibrate=true et lancer la chaîne ROS
  → Preparing, attente des analyses de cette voie
  → acquisition 30 s dès le premier indicateur valide ; décompte UI dès sa première analyse
  → au moins 50 échantillons : p5 et p50 ; sinon abandon sans nouvelles références
  → écrire le fichier correspondant et effacer calibrate
  → actualiser offset / scale de la policy existante, en conservant l’EMA
  → frontend relit le résultat par interrogation périodique de la configuration
```

```text
calib_offset = round(p5, 4)
calib_scale  = round(max(p50 − p5, 0.001), 4)
```

Les 50 échantillons sont des valeurs de l’indicateur de la voie, pas 50 mesures de tension brute. Les 30 s commencent avec les données, pas au clic initial.

Le nœud tente d’écrire dans les sources et le répertoire installé par colcon. Un échec est journalisé ; effacer calibrate ou terminer le décompte ne garantit pas la sauvegarde. Si les paramètres relus sont inchangés, le frontend signale l’absence de nouvelles valeurs ; cela peut aussi provenir de résultats arrondis identiques, sans panne nécessaire. Voir le [diagnostic de configuration](GUIDE_DEVELOPPEUR.md#63-vérifications-wsl-web-et-ros).

Les deux fichiers sont indépendants. Les valeurs appartiennent aux deux configurations courantes, pas à un profil personnel par appareil physique. Changer appareil, indicateur, port du casque ou rôle demande de vérifier les anciennes valeurs avant réemploi. Preparing signifie attente d’analyse, pas acquisition commencée ; voir le [dépannage](GUIDE_DEBUG.md#a-calibration-bloquée-sur-preparing--aucune-courbe-après-démarrage).

#### État du contrôle après calibration

Calibrate lance la chaîne dès le clic. Le nœud en calibration ne publie pas de mouvement ; après effacement du marqueur, il peut recommencer à publier, avant que le frontend découvre le résultat par interrogation périodique :

- Un appareil : aucun Stop automatique du frontend, donc Running peut persister. Une calibration réussie actualise immédiatement offset / scale de la policy existante en conservant l’EMA ; aucun redémarrage obligatoire pour ces valeurs.
- Deux appareils : le frontend demande Stop après chaque calibration. La chaîne n’est pas lancée seulement à la fin ; un bref intervalle de commandes reste possible avant l’arrêt effectif. Ce n’est pas une garantie d’arrêt synchrone.

Pour Steering Alpha / TBR, le plancher de référence du détecteur de montée est `calib_offset + calib_scale` lu à la création du nœud. La calibration actualise la policy, pas cette ancienne référence. Stop / Start crée un nœud lisant la nouvelle référence ; cela ne signifie pas que tous les indicateurs exigent un redémarrage pour leur calibration.

Placer le robot dans la [zone de test sûre](#21-périmètre-et-règles-de-recette) avant la calibration, pas à la fin du décompte. Voir les [étapes opérateur](MANUEL_OPERATEUR.md#calibration).

#### Réglage manuel des valeurs de calibration

À l’arrêt, le web permet d’éditer Min / Max par voie ; les champs sont désactivés pendant le contrôle. C’est la référence de normalisation de l’indicateur, pas l’intervalle de tension EEG brute :

```text
Min = calib_offset
Max = calib_offset + calib_scale
```

Modifier Min change seulement offset et garde scale : Max se déplace aussi. Modifier Max écrit `scale=max(0.001, Max−Min)`. Les deux modifications sont enregistrées successivement, pas atomiquement. Pour régler les deux, Min puis Max ; sinon changer Min déplace le Max déjà fixé. Si Max≤Min, la règle de scale minimal corrige l’intervalle, sans inversion.

L’API sauvegarde dans le fichier de la voie ; le prochain Start lit le résultat. Ce n’est pas un réglage à chaud du nœud ROS. Modifier la normalisation ne corrige ni perte de données, ni unité, ni port du casque. Voir la [persistance](#39-configuration-et-persistance).

### 3.8 Perte de données et reprise

Le nœud est cadencé à 20 Hz, tandis que le PSD produit environ 2 indicateurs par seconde. L’absence de nouvel indicateur entre deux trames n’est pas une perte de données. Pendant le délai de fraîcheur, le nœud répète la dernière intention pour maintenir les messages partiels.

| Situation | Nœud unique | Nœuds doubles / fusionneur |
|---|---|---|
| Données récentes | Répète la dernière commande | Répète les commandes partielles ; fusion si les deux voies sont fraîches |
| Seuil du nœud dépassé | Un Twist nul, puis silence | Arrêt des messages partiels ; fusionneur publie continuellement zéro après son timeout |
| Retour des données, toujours Running | Calcul et publication reprennent | Sortie reprend lorsque les deux voies sont fraîches |
| Stop web manuel | Chaîne arrêtée | Chaîne / fusionneur arrêtés ; le retour des données ne remplace pas un Start manuel |

Fraîcheur EEG du nœud et fraîcheur des commandes partielles du fusionneur sont deux niveaux. Le seuil de 0,5 s du second n’est pas une borne globale d’arrêt du système. Ponts, sondes couleur, ROS et navigateur ont aussi des cadences différentes.

Ces protections couvrent la perte de données, sans prouver l’arrêt sûr lors d’un blocage ROS, d’une coupure d’alimentation, d’une panne USB ou d’une perte réseau Teleop. Valider environnement et pilote réels. Pour une pause, cliquer sur Stop, sans attendre la récupération automatique.

### 3.9 Configuration et persistance

| Source | Contenu | Lecteur / rédacteur | Mise à jour / sauvegarde |
|---|---|---|---|
| `windows_launcher/config.json` Windows local | WSL, synchronisation, interpréteurs, USB, services et barre latérale | launcher | Exclu de synchronisation ; sauvegarder le fichier réel, pas seulement le modèle du dépôt |
| `thymio_control/config/launch_args.yaml` source | Réglages launch sauvegardés | config_store ; version installée lue par ROS launch | Vérifier relation source / install |
| `eeg_control_node.params.yaml` | Première voie : stratégie, ID, calibration, mouvement | Backend / nœud EEG | Modifié par usage et calibration ; pas exemple permanent |
| `eeg_control_node.eeg2.params.yaml` | Deuxième voie | Backend / deuxième nœud | Écriture indépendante ; fichier de défauts sûrs possible même si deuxième voie désactivée |
| Variables d’environnement | Commandes réelles, écoute, origin, token, données | Au démarrage backend | Redémarrage approprié nécessaire ; pas de token dans la documentation publique |
| Constantes DSP / stratégies | Fenêtre, pas, bandes, EMA | Code | Pas toutes exposées dans UI / YAML |

`source_files` de `GET /api/config` rapporte uniquement les fichiers source du backend, pas toutes les configurations ROS installées ou Windows. `reload=true` relit les fichiers. `PUT /api/config` applique un patch.

Le frontend déduit `brand` du source_id ; le backend ne persiste pas ce champ supplémentaire comme identité. `eeg2=null` désactive la deuxième voie ; la sauvegarde déduit `run_eeg2`. Le modèle refuse deux rôles identiques.

Les configurations source modifiées et installées lues par ROS doivent rester cohérentes. Changer la calibration n’exige pas en soi une recompilation. Voir les [limites de configuration](GUIDE_DEVELOPPEUR.md#53-les-trois-périmètres-de-configuration).

### 3.10 Interfaces et contrats de données

**Topics ROS.**

| Scénario / topic | Charge utile | Direction |
|---|---|---|
| Une voie `/eeg_analysis` | JSON d’analyse dans std_msgs/String, avec role | Nœud EEG → RosBridge |
| Deux voies `/eeg_analysis/speed`, `/eeg_analysis/steering` | Analyses séparées | Nœuds EEG → RosBridge |
| `/eeg_cmd_vel/speed`, `/eeg_cmd_vel/steering` | geometry_msgs/Twist partiel par rôle | Nœuds EEG → fuser |
| Réel `/cmd_vel` | geometry_msgs/Twist | Nœud unique / fuser / RosBridge manuel → pilote |
| Simulation `/model/thymio/cmd_vel` | geometry_msgs/Twist | Nœud unique / fuser / RosBridge manuel → pont simulation |
| `/led` | Message LED Thymio si disponible | Affiche la direction Steering ; pas retour moteur |

Le suffixe est `steering`, pas `steer`. Le deuxième nœud s’appelle `eeg_control_node_eeg2`. Ne pas activer simultanément EEG et commande manuelle écrivant le topic final ; aucun arbitre général de plusieurs sources de commande n’est présent.

**JSON d’analyse.** Champs : `ts`, `cmd_vel_ts`, `source`, `role`, `metrics`, `features`, `intents`, `control_mode`, `command_linear_x`, `command_angular_z`, `steer_direction`. Les command_* sont les valeurs calculées par ce nœud ; `cmd_vel_ts` est l’horloge murale du calcul, pas confirmation de publication ou retour moteur. Pendant calibration, des valeurs calculées non nulles peuvent figurer dans l’analyse sans publication du mouvement par le nœud calibrant. À deux appareils, ces champs ne sont pas non plus la commande fusionnée finale ou les vitesses réelles des roues.

**Messages web.** RosBridge écoute trois topics d’analyse et route selon role / topic. Les trames plus anciennes que son seuil de 0,5 s ne sont plus renvoyées. Structure principale de `/ws/stream` :

```json
{
  "status": { "running": true },
  "devices": {
    "speed": {
      "channels": { "alpha": 0.0, "beta": 0.0, "theta": 0.0 },
      "features": { "theta_beta_ratio": 0.0, "focus_index": 0.0 },
      "control": { "speed_intent": 0.0, "steer_intent": 0.5 },
      "timestamp": 0.0
    }
  },
  "timestamp": 0.0
}
```

Exemple de structure abrégé, pas données de test ou mesure valide. La deuxième voie utilise `steering`. Sans trame fraîche, `devices=null` est possible. La boucle web envoie un instantané environ toutes les 0,2 s, pas nécessairement un nouveau PSD à chaque envoi.

**Principaux endpoints HTTP / WebSocket.**

| Service | Endpoint | Responsabilité / charge utile |
|---|---|---|
| Contrôle Windows | GET `/status`, `/config`, `/log` | États, configuration latérale, fin des logs |
| Contrôle Windows | POST `/start-system`, `/stop-system`, `/restart-system`, `/restart-web` | Cycle système / web |
| Contrôle Windows | POST `/connect-device`, `/disconnect-device` | `{"device":"headband"}` par exemple ; clé Hybrid interne : hybrid |
| Contrôle Windows | POST `/shutdown`, `/lan-forward/fix` | Quitter le launcher / corriger la redirection LAN |
| Backend WSL | GET `/api/health`, `/api/status` | Initialisation / erreurs du pont ROS, sondes backend |
| Backend WSL | GET / PUT `/api/config` | ConfigEnvelope ; PUT : `{"patch":{...}}` |
| Backend WSL | POST `/api/system/start`, `/api/system/stop` | `{"dry_run":false}` demande un contrôle réel, sous réserve de la variable de permission |
| Backend WSL | WS `/ws/stream` | status, devices par role, timestamps |
| Backend WSL | WS `/ws/teleop` | `{"direction":"forward"}`, etc. ; réponses config / ack / error |
| Backend WSL | WS `/ws/gazebo_frame` | Proxy caméra simulée ; camera bridge amont 8011 par défaut |
| Backend WSL | GET `/api/logs` | Logs backend et fin des logs launcher WSL |

« system » dans l’API backend n’a pas le même périmètre que start-system Windows. Caméra simulée indisponible et contrôle EEG indisponible sont aussi deux pannes distinctes.

### 3.11 Erreurs et observabilité

| Emplacement | Preuve observable | Ne signifie pas |
|---|---|---|
| System Control / View Log | Gestion des services, sondes, logs Windows | Validation complète EEG / moteurs |
| Terminal VS Code Headband | SDK, création / reconstruction, stagnation des données | Existence garantie de `bridge_headband.log` |
| `bridge_hybrid.log` | Sortie du processus Hybrid supervisé | Tous les logs Headband ou ROS |
| WSL `/tmp/launcher_backend.log`, `launcher_frontend.log` | Sorties redirigées au lancement web | Tous les stdout des nœuds ROS |
| Logs ROS | Échantillons, écritures CALIB, clignements / perte de données, erreurs | CALIB effacé = références forcément sauvegardées |
| `/api/health` | subscriber_ready, subscriber_error, compteurs | ready=true = succès ; un échec d’initialisation termine aussi l’attente et met ready |
| `/api/status` | Disponibilité ROS / série / marqueur backend | eeg_stream_alive = preuve indépendante de fraîcheur brute ; il dépend actuellement de running backend |

Le runner redirige stdout / stderr ROS vers DEVNULL : View Log ne contient pas toutes les sorties des nœuds. Voir les [logs développeur](GUIDE_DEVELOPPEUR.md#64-emplacements-des-logs-et-rapport-de-panne). Preparing, couleurs, Running des services et séries de données décrivent des couches différentes et ne se remplacent pas.

### 3.12 Réseau, commandes et données

Le service Windows écoute par défaut 127.0.0.1:8020 et contrôle l’origine des POST. Le backend écoute 127.0.0.1:8010. Vite écoute 0.0.0.0:5173 et relaie API / WebSocket. Le launcher tente de mettre à jour la redirection Windows du frontend selon l’IP WSL.

La configuration launcher du dépôt fixe `WEB_GUI_FRONTEND_ORIGIN` à `*` ; token vide et commandes réelles activées par défaut. L’accès LAN n’est donc pas nécessairement limité à la visualisation. Origin n’est pas une authentification ; un token n’est pas une gestion complète des droits.

`/api/config/control_token` permet de lire le token aux clients vus comme loopback par le backend ; le frontend le récupère automatiquement. Le proxy Vite arrive lui-même depuis loopback : ce contrôle ne prouve pas qu’un client LAN du frontend ne peut pas obtenir le token. Vérifier le parcours proxy / réseau réel. Un token seul ne sécurise pas un déploiement sur réseau non fiable.

Désactiver un bouton n’est pas un contrôle d’autorisation. `/api/config` et les autres interfaces ne disposent pas d’un modèle unifié d’accès utilisateur. Teleop ne passe pas par la permission de launch `WEB_GUI_ALLOW_REAL_COMMANDS` : la restriction mock n’est pas un interrupteur global de sécurité des API.

Types de données et limites de conservation :

- Sources et déclarations de dépendances : dépôt Git ; conserver licences et provenance des tiers `src/ros-aseba` et `src/ros-thymio`.
- Configuration réelle et calibration : JSON Windows local, configurations WSL ; sauvegarder après modification, sans substituer des valeurs d’usine.
- Logs : Windows, terminal VS Code et fichiers temporaires WSL ; pas de durée de conservation uniforme gérée par le système.
- Analyses de recherche : ancien `experiment_data/` retiré de l’espace actuel, répertoire entier dans `.gitignore`, historique conservé ; fonction de collecte et usage dans les [limites du produit](#17-limites-du-produit).
- EEG brut : enregistrement non implémenté ; indicateurs et contrôle des CSV d’analyse ne remplacent pas les signaux bruts.

Le responsable définit données sensibles, dé-identification et accès. Ne pas publier mots de passe, tokens ou clés complètes dans la documentation ou Git. Sauvegarde et restauration : [guide développeur](GUIDE_DEVELOPPEUR.md#9-sauvegarde-et-restauration).

## 4. Recette et état de validation

### 4.1 Périmètre des vérifications

Résultats du 2026-10-09, sous macOS avec Python 3.14 ; ils ne prouvent pas la reproduction sous Windows + WSL2. Commandes et dépendances : [tests développeur](GUIDE_DEVELOPPEUR.md#71-tests-existants).

| Tests, chemins relatifs au dépôt | Résultat enregistré |
|---|---|
| `test_watchdog.py`, `test_cmd_vel_fuser.py`, `test_calibration.py`, `test_blink_metric.py`, `test_pre_filter.py` dans `thymio_control/test/`, et `thymio_control/lsl_test/test_dummy_dual_streams.py` | 38 passed au total |
| `thymio_control/test/test_verify_blink_clamp.py` | 2 skipped : données historiques `experiment_data/archive/` retirées |

Les tests réussis ne nécessitent ni ROS réel, ni EEG, ni Thymio et ne vérifient pas les SDK Windows. Les deux tests synthétiques vérifient génération et indicateurs, pas transmission LSL réelle ni Gazebo complet. Les relectures historiques ignorées restent un manque de validation. Ce bilan n’inclut ni toute la suite backend, ni compilation frontend, ni recette matérielle cible.

| Niveau | Ce qu’il peut démontrer | État actuel |
|---|---|---|
| Revue code / configuration | Logique, chemins, paramètres, interfaces et limites | Principales bases du document vérifiées |
| Tests purs / numériques / fichiers | Watchdog, fusion, calibration / écriture, détection, préfiltrage, génération | Tests ci-dessus réussis ; pas preuve SDK, radio ou ROS complet |
| Relecture historique | Effet du plancher de référence des clignements sur des données acquises | Données retirées, tests ignorés, pas réussite |
| ROS / backend intégré | Démarrage, routage, relecture, WebSocket, nettoyage | Implémentations / tests existants ; exécution cible à faire |
| Simulation | Chaîne sans matériel de bout en bout | Pas de validation complète ; pas substitut au réel |
| Windows réel | SDK, Bluetooth, USB, réseau WSL, moteurs | Expérience d’usage fournie ; pas de trace complète de recette |
| Utilisabilité / maintenabilité | Autonomie utilisateur, déploiement / modification développeur | Pas de validation enregistrée |

### 4.2 Scénarios de recette sur l’ordinateur cible

Noter « non exécuté / réussi / échoué » pour chaque cas, pas seulement une case cochée. Si les conditions manquent, les préciser.

| Scénario | Exigences | Observations requises |
|---|---|---|
| Démarrage / arrêt normal | RF-01, RF-14 | Deux types de Start, services, fermeture, processus résiduels |
| Headband / arrêt manuel | RF-02, RF-14 | Venv, données, Ctrl+C, reconnexion sans ancien script dupliqué |
| Hybrid / déconnexion | RF-03 | Imports SDK, échantillons LSL, processus terminé |
| Partage / attach dongle | RF-04 | Port prévu, 1-1, Shared / Attached, périphérique WSL et robot |
| Un EEG, deux rôles successifs | RF-05, RF-06 | Modèle correct ; avance et rotation sur place sans Teleop concurrent |
| Permutation des rôles à deux EEG | RF-05, RF-09, RF-12 | Modèles / rôles bien routés, aucune analyse / commande croisée |
| Calibration par voie / échantillons insuffisants | RF-07, RF-08, RF-15 | Acquisition, succès / abandon, fichiers indépendants, policy actualisée, lecture au Start ; ancienne référence clignement vérifiée séparément |
| Fin de calibration / réglage manuel | RF-07, RF-15, RN-01 | Continuation possible à un EEG, timing du Stop automatique à deux ; Min / Max à l’arrêt, relecture, rafraîchissement, Start cohérents |
| Clignements | RF-10 | Basculement volontaire, faux déclenchements naturels, pas maintien d’ancienne rotation pendant délai réfractaire |
| Perte / retour des données | RF-11, RN-01 | Zéro en simple / double, arrêt réel, couleurs / données, reprise éventuelle |
| Keyboard | RF-13, RN-01 | Appui / relâchement, stop, bonne sortie |
| Arrêt sur panne Teleop | RN-01, RN-07 | Fermeture page, perte WebSocket / réseau, panne backend : comportement réel du pilote, sans réussite présumée |
| Pannes web / logs | RF-16 | Échecs frontend / backend distincts, Restart Web, informations conservables |
| Mise à jour / sauvegarde / restauration | RN-05, RN-08 | JSON non écrasé, prise en compte du code, exécution répétable après restauration |
| Essai utilisateur non technique | RN-03 | Utilisation complète et résolution d’un problème courant avec les deux manuels utilisateur |
| Maintenance développeur | RN-04, RN-05 | Localisation, petite modification et vérification avec guides technique / développeur |

### 4.3 Traçabilité exigences, code et tests

| Groupe | Implémentation | Vérification |
|---|---|---|
| RF-01 à 04, RF-14, RF-16 | config, server, state, commands, lsl_probe de windows_launcher | windows_launcher/tests ; recette Windows |
| RF-05, RF-08, RF-15 | models, config_store, App, ROS launch | Tests models / config_store ; deux appareils réels |
| RF-06, RF-10 | policies, enrich, blink_metric, nœud EEG | test_policy, test_blink_metric, test_eeg_control_node ; EEG réel |
| RF-07 | calibration, nœud, useCalibration frontend | [test_calibration.py](../thymio_control/test/test_calibration.py) ; parcours web / nœud complet |
| RF-09, RF-11, RN-01 | fuser, watchdog, launch | [test_cmd_vel_fuser.py](../thymio_control/test/test_cmd_vel_fuser.py), [test_watchdog.py](../thymio_control/test/test_watchdog.py) ; arrêt / récupération mesurés |
| Traitement et flux synthétiques | RawLslAdapter, StreamingPreFilter, dummy_dual_streams | [Préfiltrage](../thymio_control/test/test_pre_filter.py), [génération](../thymio_control/lsl_test/test_dummy_dual_streams.py) ; LSL / ROS / simulation séparément |
| RF-12, RF-13 | signal_subscriber, main, App | Tests subscriber, UI launcher ; web et robot |
| RN-05, RN-07, RN-08 | Dépendances, proxy Vite, autorisation backend, synchronisation, déploiement | Reconstruction cible, accès réseau, restauration |

Les tests réellement exécutés sont uniquement ceux de la [section 4.1](#41-périmètre-des-vérifications). Les autres fichiers sont des entrées de vérification ultérieure. Voir les [tests développeur](GUIDE_DEVELOPPEUR.md#71-tests-existants) pour commandes, périmètre par défaut et dépendances.

## 5. Limites actuelles et informations à confirmer

### 5.1 Limites et vérifications prioritaires

| Sujet | Effet | Réponse / vérification |
|---|---|---|
| Pont Headband manuel | Arrêter System Control ne l’arrête pas | Garder Ctrl+C dans les manuels ; vérifier absence de doublons |
| source_id par modèle, vide ou premier flux choisi | Pas d’identité fiable pour deux appareils identiques | Combinaison standard actuelle ; développer et valider [RF-NEXT](#25-prochaine-priorité--deux-gtec-du-même-modèle), sans annoncer compatibilité directe |
| Calibration ne renouvelle pas la référence du détecteur | Référence de montée Alpha / TBR Steering potentiellement ancienne ; policy déjà actualisée | Stop / Start si renouvellement nécessaire ; voir [état après calibration](#état-du-contrôle-après-calibration) |
| Deux watchdogs et reprise automatique | 0,5 s ≠ garantie globale ; reprise possible | Recette arrêt / reprise ; Stop volontaire pour pause |
| Déconnexion WS manuelle sans zéro explicite | Arrêt sur panne navigateur / réseau non garanti par validation | Tester pilote réel ; répétition 200 ms ≠ arrêt réseau |
| Santé web ≠ ROS / EEG valide | États pouvant induire en erreur | Données, erreurs ROS et mouvement, pas couleurs seules |
| Commandes réelles actives / accès incomplet | Client non fiable pouvant commander ou modifier | Vérifier écoute / proxy / périmètre ; pas Internet avant examen |
| Configuration issue d’un usage passé | Rôles, indicateurs, vitesses pas forcément adaptés | Confirmer et sauvegarder les paramètres d’usage |
| SDK / environnement hors liste pip complète | Clone ou WSL importé ne restaure pas les ponts Windows | Évaluer la [migration WSL](GUIDE_DEVELOPPEUR.md#93-migration-recommandée--export-et-import-de-wsl-complet) ; SDK, licences, Python, Bluetooth, USB séparés |
| Simulation complète non validée | Scripts synthétiques / Gazebo ≠ chaîne validée | Suivre le [parcours développeur](GUIDE_DEVELOPPEUR.md#43-validation-hors-ligne-sans-appareils), sans remplacer la recette réelle |
| Pas de cycle uniforme données / logs | Fuite, suppression ou éléments manquants à la restauration | Définir accès, conservation et sauvegardes |

Les inconnues quantitatives sont en [section 2.4](#24-indicateurs-quantitatifs-non-fixés), les scénarios cibles en [section 4.2](#42-scénarios-de-recette-sur-lordinateur-cible). Les étapes de déploiement, licence et migration sont maintenues dans le [guide développeur](GUIDE_DEVELOPPEUR.md).

---

[Version chinoise](zh/DOSSIER_TECHNIQUE_cn.md)
