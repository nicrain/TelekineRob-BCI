# Script de présentation — Point d'avancement mi-stage

## Introduction

Bonjour, aujourd'hui, je vais vous présenter l'avancement de mon stage. Pour commencer, le projet TelekineRob vise l'amélioration de l'attention chez des sujets atteints de TDAH, grâce au contrôle d'un robot piloté par un casque EEG. Concrètement, c'est un système de neurofeedback en boucle fermée : le sujet porte un casque EEG et tente de contrôler un robot par la pensée. Le signal EEG est traité et transformé en commandes de déplacement pour le robot, et le mouvement du robot sert de retour visuel au sujet.

## Environnement expérimental

Ensuite, l'environnement expérimental. L'idée, c'est d'avoir deux sujets équipées d'un casque EEG : une qui contrôle la vitesse d'avancement, et l'autre qui contrôle la direction, c'est-à-dire tourner à gauche ou à droite.

## Schéma d'architecture

Ensuite, le schéma d'architecture. D'abord, on a l'entrée, le casque EEG : le signal EEG qui arrive au système ROS2. ROS2 traite ce signal et génère les commandes pour piloter le robot Thymio. En fait, on a plusieurs sources d'entrée possibles — Tobii, Enobio, g.tec, etc. — et ROS2 est capable de traiter ces différents signaux. On dispose aussi d'un Thymio simulé, qui facilite le développement sans nécessiter le robot physique.

## Interface visuelle

Ensuite, pour opérer et visualiser le système, j'ai développé cette interface visuelle. Elle se compose de trois parties : la configuration de l'entrée, c'est-à-dire le casque EEG ; la sortie, qui correspond au robot Thymio ; et la visualisation des signaux en temps réel.

## Sommaire

Voilà pour l'introduction. Aujourd'hui, je vais vous présenter six parties : les préparatifs, le matériel et les équipements, l'environnement expérimental, l'architecture et le développement, l'étude et validation du devis EEG, et pour finir, les travaux futurs.

## Préparatifs

D'abord, les préparatifs. J'ai appris les concepts fondamentaux du projet : TDAH, BCI, EEG, le système 10-20, ainsi que les bandes de fréquences — alpha, beta, theta, delta, gamma. J'ai aussi acquis des compétences techniques : le système ROS pour contrôler le robot, et des algorithmes de traitement de signal comme la FFT, la fenêtre de Hanning et le PSD.

## Projets étudiés

En complément, j'ai étudié plusieurs projets similaires : Brain Kart de David Trocellier, le projet de Thymio contrôlé par EEG de Luca Mondada en 2015, un projet de robot EEG avec réalité augmentée, ainsi que RelaxQuest. Ces projets m'ont servi de référence pour les choix techniques du nôtre.

## Matériel et équipements

Ensuite, la partie matériel et équipements. Je vais vous présenter trois dispositifs : le robot Thymio, le système de suivi oculaire Tobii, et le casque EEG Enobio.

## Thymio - Un robot éducatif opensource

D'abord, le Thymio. C'est un robot éducatif open source : il peut avancer, reculer et tourner. Il dispose aussi de son, de LEDs et de capteurs, le tout programmable.

## Thymio simulé

On peut également utiliser un Thymio simulé, ce qui facilite le développement sans matériel physique.

## Système — Choix techniques

Pour le système, j'ai fait deux choix principaux. D'abord, ROS 2 : c'est un framework open source, avec une architecture modulaire, une communication par topics et messages, et un écosystème riche. Ensuite, Ubuntu 24.04, qui est la distribution de référence pour ROS 2, offrant la meilleure compatibilité native.

## Sources de données — Entrées

Comme je l'ai mentionné, les entrées peuvent être des matériels : Tobii, Enobio, g.tec. Mais on peut aussi utiliser des fichiers comme entrée. En effet, l'Enobio peut enregistrer ses données dans un fichier, et on peut ensuite relire ce fichier comme source de données.

## Interface visuelle (comparaison)

Pour l'interface visuelle, j'ai opté pour une Web GUI plutôt qu'une application individuelle classique en Java ou Python. Les avantages sont clairs : une faible dépendance envers le système d'exploitation, moins de ressources système, un accès local ou distant sans développement supplémentaire, et aucune installation requise côté client — il suffit d'un navigateur.

## Interface visuelle — Web GUI

Pour le Web GUI, j'ai développé plusieurs fonctionnalités : la relecture de fichiers, le contrôle au clavier, un Thymio simulé pour la visualisation, et la visualisation des signaux. De plus, je l'ai déployé sur un serveur, ce qui facilite le développement sans matériel physique. Pour la stack technique, c'est React 18 avec Vite et ECharts en frontend, et FastAPI en backend.

