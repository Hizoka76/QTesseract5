#! /bin/bash


# Fichier servant :
# - Lors de la creation du paquet sources
# - Apres la creation d'un paquet source, les fichiers sont supprimés, il faut donc les recréer

# if [[ ! $(which "pyrcc5") ]]
# then
#     echo "The pyrcc5 program is missing, installing of pyqt5-dev-tools package."
#     sudo apt-get install pyqt5-dev-tools
# fi

chemin="$(cd "$(dirname "$0")";pwd)"
cd "${chemin}"


### Mise à jour des fichiers ts -noobsolete
pylupdate5 Qtesseract5.py -ts Qtesseract5_fr_FR.ts

# -no-obsolete
[[ -e "/usr/lib/x86_64-linux-gnu/qt5/bin/lupdate" ]] && /usr/lib/x86_64-linux-gnu/qt5/bin/lupdate Qtesseract5.py -pluralonly -ts Qtesseract5_en_EN.ts
[[ -e "/usr/lib/i386-linux-gnu/qt5/bin/lupdate" ]] && /usr/lib/i386-linux-gnu/qt5/bin/lupdate Qtesseract5.py -pluralonly -ts Qtesseract5_en_EN.ts


### Convertion des fichiers ts en qm
if [[ -e "/usr/lib/x86_64-linux-gnu/qt5/bin/lrelease" ]]
then
    /usr/lib/x86_64-linux-gnu/qt5/bin/lrelease *.ts

elif [[ -e "/usr/lib/i386-linux-gnu/qt5/bin/lrelease" ]]
then
    /usr/lib/i386-linux-gnu/qt5/bin/lrelease *.ts

else
    echo "cannot find 'lrelease'"
    exit 1
fi


### Création d'un fichier source python (contient les icones)
echo '<RCC>
  <qresource prefix="/">' > Qtesseract5Ressources.qrc

for icon in img/*
do
    echo "    <file>${icon}</file>" >> Qtesseract5Ressources.qrc
done

echo '  </qresource>
</RCC>' >> Qtesseract5Ressources.qrc

pyrcc5 Qtesseract5Ressources.qrc -o Qtesseract5Ressources_rc.py