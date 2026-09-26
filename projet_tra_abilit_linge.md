# Projet de Traçabilité du Linge

## 1. Description du Projet
Système domotique centralisé pour l'identification, le suivi et la gestion automatisée du linge de maison. 

Chaque vêtement est équipé d'une étiquette RFID UHF lavable. Lorsqu'un article est déposé dans le panier à linge ou passe à proximité du point de contrôle, il est immédiatement détecté, identifié et enregistré dans une base de données centralisée. 

Un écran déporté affiche en temps réel le linge scanné et propose des recommandations intelligentes pour les prochaines lessives à lancer (par couleur, type de textile ou charge recommandée).

---

## 2. Architecture Matérielle (Hardware)

* **Tags RFID :** Puces RFID UHF Gen 2 lavables (format textile / silicone).
* **Lecteur RFID :** Module Chafon MU910-M (865–868 MHz, norme européenne UHF).
* **Antenne :** Antenne PCB / Céramique UHF (865–868 MHz) reliée via pigtail IPEX vers SMA.
* **Microcontrôleur Réseau :** Carte ESP32 Ethernet avec support PoE (Power over Ethernet).
* **Infrastructure Réseau :** Câble RJ45 relié à un switch PoE (alimentation + données sur un seul câble).

---

## 3. Architecture Logicielle (Software)

* **Backend (Serveur) :** 
  * **Python (Flask & SocketIO) :** Écoute les sockets TCP transmises par l'ESP32 et pousse les mises à jour en temps réel vers l'interface web.
  * **Filtre Anti-Spam :** Temporisation (cache de 3s) pour éviter les lectures en rafale multiples d'un même vêtement.
* **Base de Données & Gestion :**
  * **SQLite (`linges.db`) :** Stockage local rapide des 750+ articles (EPC, type, couleur, forme, nom d'image).
* **Frontend (Interface Écran Déporté) :**
  * **HTML5 / CSS3 / JavaScript :** Interface fluide en mode sombre (type kiosque) affichant la fiche de l'article, sa photo, un historique récent et la suggestion des lessives à préparer.

---

## 4. Flux de Fonctionnement

1. **Détection :** Passation du linge devant l'antenne UHF (~1m de portée).
2. **Acquisition :** Le module Chafon lit le code EPC et le transmet en UART à l'ESP32.
3. **Transmission :** L'ESP32 envoie le paquet TCP via le réseau RJ45 au serveur Python.
4. **Traitement :** Python consulte la base SQLite et vérifie l'état du stock/bac à linge.
5. **Affichage :** L'interface HTML se met à jour instantanément sans rafraîchissement de page.