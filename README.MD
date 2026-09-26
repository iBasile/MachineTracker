# Traçabilité du linge

Application locale de suivi des habits RFID avec ESP32 Ethernet, API Flask,
SQLite et interface temps réel Socket.IO.

## Démarrage

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Ouvrir ensuite <http://localhost:5000>. La base `linges.db` est créée
automatiquement au premier démarrage.

* `/` : tableau de bord kiosque, détections et historique ;
* `/admin` : ajout, modification, suppression et activation du mode ajout ;
* `POST /api/scan` : endpoint HTTP utilisé par l’ESP32 ;
* port TCP `9000` : protocole complémentaire, un objet JSON par ligne
  (`{"epc":"E280..."}`), utile si le firmware préfère une socket brute.

Variables d’environnement disponibles :

* `PORT` (5000) : port de l’interface web ;
* `LINGE_TCP_PORT` (9000) : port TCP pour l’ESP32 ;
* `LINGE_DB` : chemin de la base SQLite ;
* `LINGE_SECRET` : secret Flask à remplacer en production.

## Mode ajout

Depuis **Gestion → + Ajout**, le serveur active le mode d’enrôlement et
l’interface affiche l’instruction « Ne rien ajouter dans le panier à linge ».
Quand un EPC inconnu est lu, il est envoyé en temps réel au formulaire. Il
suffit alors de compléter les critères de l’habit puis d’enregistrer.

Les lectures répétées d’un même EPC dans une fenêtre de trois secondes sont
ignorées. Une lecture connue marque l’habit comme présent et crée une ligne
d’historique.

Le tableau de bord regroupe les habits présents dans le panier par température
et matière afin de proposer des machines compatibles. Les couleurs sont
indiquées comme mélangées lorsqu’un groupe contient plusieurs couleurs ; les
instructions particulières sont affichées comme avertissement. Le bouton
**Vider le panier** remet les habits présents à zéro après le lancement d’une
lessive.

## ESP32 et lecteur MU910-M

Le sketch de référence est dans
[`firmware/esp32_linge.ino`](firmware/esp32_linge.ino). Il utilise Ethernet,
lit l’UART du lecteur et transmet un EPC par `POST /api/scan`. Adapter
`API_URL`, les broches UART et le débit au câblage et au protocole exact du
firmware MU910-M. Le sketch attend une ligne EPC terminée par CR/LF, ce qui
permet de valider l’ensemble avec un lecteur configuré en mode texte.

Pour un réseau réel, placer l’ESP32 et le serveur sur le même VLAN, fixer
l’adresse IP du serveur (ou utiliser un DNS local), et ne pas exposer Flask
directement sur Internet.
