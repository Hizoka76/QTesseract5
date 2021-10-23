#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-

"""Script permettant la conversion des fichiers SUB en SRT avec interface graphique pour les textes non traduits automatiquement."""

#1) Traitement des arguments
#2) Vérification de la présence des exécutables
#3) Remplissage et affichage si besoin de la fenêtre de configuration => ConfigDialog()
#4) Vérification des données => ConfigDialog.CheckInfos(True)
#5) Remplissage et affichage si besoin de la fenêtre de progression de la conversion des images => ProgressDialog()
#6) Remplissage et affichage si besoin de la fenêtre de vérification des textes => CheckTextDialog()
#7) Création du fichier srt => CheckTextDialog.Next()


###############################
### Importation des modules ###
###############################
import sys
from concurrent.futures import ThreadPoolExecutor # Permet de le multi calcul
from shutil import copyfile, rmtree
from pathlib import Path # Nécessaire pour la recherche de fichier
from time import sleep

from PyQt5.QtGui import QIcon, QPixmap, QDesktopServices, QCursor, QPalette, QBrush, QColor
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog, QProgressBar, QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel, QSlider, QLineEdit, QAction, QGroupBox, QComboBox, QCheckBox, QSpinBox, QToolTip, QTextEdit, QRadioButton
from PyQt5.QtCore import QProcess, QCoreApplication, Qt, QLocale, QTranslator, QLibraryInfo, QCommandLineOption, QCommandLineParser, QTemporaryDir, QStandardPaths, QCryptographicHash, QDir, QThread, QUrl, QEvent, pyqtSignal

from WhatsUp.WhatsUp import WhatsUp

import Qtesseract5Ressources_rc # Import des images

from langcodes import LangCodes # Codes des pays pour afficher les drapeaux



#############################################################################
class QSliderCustom(QSlider):
    """QSlider customisé permettant d'afficher l'infobulle lors du déplacement du curseur par la souris."""
    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)


    #========================================================================
    def mouseMoveEvent(self, event):
        """Affichage de l'infobulle lors du déplacement de souris."""
        Md5Key = list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]] # Récupération d'une clé
        NbOfKey = len(GlobalVar["MD5Dico"][Md5Key])

        QToolTip.showText(event.globalPos(), QCoreApplication.translate("QSliderCustom", "%n image(s) contain(s) this text.", "%n is the number of images with the same text", NbOfKey))
        QSlider.mouseMoveEvent(self, event)



#############################################################################
class QLineEditCustom(QLineEdit):
    """QLineEdit customisé permettant de le glisser-déposer dans les QLineEdit de la fenêtre de config."""
    def __init__(self, Parent, Name):
        super().__init__(Parent)


        ### Variable obligatoire pour savoir les actions pour le drag and drop
        self.Name = Name


    #========================================================================
    def dragEnterEvent(self, event):
        """Fonction appelée à l'arrivée d'un fichier à déposer sur la fenêtre."""
        # Impossible d'utiliser mimetypes car il ne reconnaît pas tous les fichiers...
        ### Récupération du nom du fichier
        Item = Path(event.mimeData().urls()[0].path())


        ### Si c'est le mode idx, il faut un fichier idx ou sub
        if self.Name == "idx":
            if Item.is_file() and Item.suffix in (".idx", ".sub"):
                event.accept()


        ### Pour les autres modes, il faut un dossier
        elif self.Name:
            if Item.is_dir():
                event.accept()


    #========================================================================
    def dropEvent(self, event):
        """Fonction appelée à la dépose du fichier/dossier sur la fenêtre."""
        # Impossible d'utiliser mimetypes car il ne reconnaît pas tous les fichiers...
        ### Récupération du nom du fichier
        Item = Path(event.mimeData().urls()[0].path())


        ### Si c'est le mode idx, il faut un fichier idx ou sub
        if self.Name == "idx":
            self.setText(str(Item.with_suffix(".idx")))


        ### Si c'est le mode srt, il faut un fichier idx ou sub déjà chargé
        elif self.Name == "srt":
            if Path(GlobalVar["IDX"]).is_file():
                OutputFile = Path(Item, GlobalVar["IDX"].name).with_suffix(".srt")
                self.setText(str(OutputFile))


        ### Si c'est le mode temp
        elif self.Name == "temp":
            GlobalVar["ConfigDialog"].TemporaryFolder(True, str(Item))


        ### Si c'est le mode tesseract
        elif self.Name == "tesseract":
            GlobalVar["ConfigDialog"].TesseractPath(True, str(Item))



#############################################################################
class ConfigDialog(QDialog):
    """Fenêtre de configuration du code."""
    def __init__(self, Parent=None):
        super().__init__(Parent)


        ### Mode verbose
        if GlobalVar["Verbose"] == 3:
            print(QCoreApplication.translate("ConfigDialog", "Gui creation"), file=sys.stdout)


        ### Fenêtre
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setMinimumHeight(500)
        self.setMinimumWidth(650)
        self.resize(650, 500) # resize sinon le qtextedit prend de la place inutilement...
        self.setWindowTitle("{} v{}".format(QCoreApplication.applicationName(), QCoreApplication.applicationVersion()))
        self.accepted.connect(self.Next)
        self.setAttribute(Qt.WA_DeleteOnClose)


        ### Gestion des fichiers entrée et sortie
        ## Fichier IDX d'entrée
        self.IDXBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Input IDX file:"), self)
        self.IDXEntry = QLineEditCustom(self.IDXBox, "idx")
        self.IDXEntry.setAcceptDrops(True)
        self.IDXEntry.setClearButtonEnabled(True)
        self.IDXEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Source IDX file to translate.\nYou can drag the file here."))
        self.IDXEntryIcon = QAction(QIcon.fromTheme("document-open", QIcon(":/img/document-open.svg")), QCoreApplication.translate("ConfigDialog", "Select file dialog."), self.IDXEntry)
        self.IDXEntryIcon.triggered.connect(self.IDXPathWin)
        self.IDXEntry.addAction(self.IDXEntryIcon, QLineEdit.LeadingPosition)
        IDXLayout = QHBoxLayout(None)
        IDXLayout.addWidget(self.IDXEntry)
        self.IDXBox.setLayout(IDXLayout)


        ## Fichier SRT de sortie
        self.SRTBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Output SRT file:"), self)

        self.SRTEntry = QLineEditCustom(self.SRTBox, "srt")
        self.SRTEntry.setClearButtonEnabled(True)
        self.SRTEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Destination SRT file translated.\nYou can drag the parent folder here."))
        self.SRTEntryIcon = QAction(QIcon.fromTheme("document-open", QIcon(":/img/document-open.svg")), QCoreApplication.translate("ConfigDialog", "Select file dialog."), self.SRTEntry)
        self.SRTEntryIcon.triggered.connect(self.SRTPathWin)
        self.SRTEntry.addAction(self.SRTEntryIcon, QLineEdit.LeadingPosition)

        self.SRTOverwrite = QPushButton(QIcon.fromTheme("edit-delete", QIcon(":/img/edit-delete.svg")), "")
        self.SRTOverwrite.setToolTip(QCoreApplication.translate("ConfigDialog", "Overwrite the SRT file if it already exists"))
        self.SRTOverwrite.setCheckable(True)

        SRTLayout = QHBoxLayout(None)
        SRTLayout.addWidget(self.SRTEntry)
        SRTLayout.addWidget(self.SRTOverwrite)
        self.SRTBox.setLayout(SRTLayout)


        ## Dossier temporaire
        self.TempBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Temporary folder:"), self)
        self.TempEntry = QLineEditCustom(self.TempBox, "temp")
        self.TempEntry.setReadOnly(True)
        self.TempEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Temporary folder to use for files extracted.\nYou can drag the folder here."))
        self.TempEntryIcon1 = QAction(QIcon.fromTheme("folder-open", QIcon(":/img/folder-open.svg")), QCoreApplication.translate("ConfigDialog", "Select folder dialog."), self.TempEntry)
        self.TempEntryIcon1.triggered.connect(lambda: self.TemporaryFolder(True, None))
        self.TempEntryIcon2 = QAction(QIcon.fromTheme("view-refresh", QIcon(":/img/view-refresh.svg")), QCoreApplication.translate("ConfigDialog", "Recreate a temporary folder in /tmp."), self.TempEntry)
        self.TempEntryIcon2.triggered.connect(lambda: self.TemporaryFolder(True, "Auto"))
        self.TempEntry.addAction(self.TempEntryIcon1, QLineEdit.LeadingPosition)
        self.TempEntry.addAction(self.TempEntryIcon2, QLineEdit.TrailingPosition)

        self.TempOverwrite = QPushButton(QIcon.fromTheme("edit-delete", QIcon(":/img/edit-delete.svg")), "")
        self.TempOverwrite.setToolTip(QCoreApplication.translate("ConfigDialog", "Remove the temporary folder when closing the software.\nBe Careful if it's a personal folder."))
        self.TempOverwrite.setCheckable(True)

        TempLayout = QHBoxLayout(None)
        TempLayout.addWidget(self.TempEntry)
        TempLayout.addWidget(self.TempOverwrite)
        self.TempBox.setLayout(TempLayout)


        ## Layout
        FilesLayout = QVBoxLayout(None)
        FilesLayout.addWidget(self.IDXBox)
        FilesLayout.addWidget(self.SRTBox)
        FilesLayout.addWidget(self.TempBox)


        ### Modification de la couleur des textes et du nombre de processeur
        ## Nombre de processeur
        self.OptionsBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Options:"), self)

        OptionsLayout = QVBoxLayout(None)

        self.GuiSpin = QSpinBox(self.OptionsBox)
        self.GuiSpin.setMinimum(0)
        self.GuiSpin.setMaximum(2)
        self.GuiSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Gui level: "))
        self.GuiSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Level of the gui.\n0: No window at all.\n1: Only check texts window.\n2: All windows."))
        OptionsLayout.addWidget(self.GuiSpin)

        self.CPUSpin = QSpinBox(self.OptionsBox)
        self.CPUSpin.setMinimum(1)
        self.CPUSpin.setMaximum(QThread.idealThreadCount() * 2)
        self.CPUSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Use "))
        self.CPUSpin.setSuffix(QCoreApplication.translate("ConfigDialog", " thread(s)"))
        self.CPUSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Number of thread (cpu) to use simultaneous, max value by default."))
        OptionsLayout.addWidget(self.CPUSpin)

        self.DebugSpin = QSpinBox(self.OptionsBox)
        self.DebugSpin.setMinimum(0)
        self.DebugSpin.setMaximum(3)
        self.DebugSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Debug level: "))
        self.DebugSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Verbose mode for debug.\n\
Level 0: Errors messages, by default\n\
Level 1: Level 0, Number of images files created, Temporary folder path, Conversion progress\n\
Level 2: Level 1, Commands Lines, Tesseract languages, Options values, Custom color, Conversion started, Check texts needed, SRT file created\n\
Level 3: Level 2, Convert files names, Dialog creation info, List of the texts to check"))
        OptionsLayout.addWidget(self.DebugSpin)

        self.ColorsSpin = QSpinBox(self.OptionsBox)
        self.ColorsSpin.setMinimum(0)
        self.ColorsSpin.setMaximum(2)
        self.ColorsSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Colors level: "))
        self.ColorsSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Colors of the images texts.\n\
Level 0: No use custom colors\n\
Level 1: Use custom colors on images not recognized\n\
Level 2: Use only customs colors"))

        self.ColorConfig = QPushButton(QIcon.fromTheme("configure", QIcon(":/img/configure.svg")), "")
        self.ColorConfig.setToolTip(QCoreApplication.translate("ConfigDialog", "Customize the colors."))
        self.ColorConfig.clicked.connect(lambda: CustomizeDialog("ProgressDialog"))

        ColorLayout = QHBoxLayout(None)
        ColorLayout.addWidget(self.ColorsSpin)
        ColorLayout.addWidget(self.ColorConfig)
        OptionsLayout.addLayout(ColorLayout)

        self.OpenBox = QCheckBox(QCoreApplication.translate("ConfigDialog", "Open SRT file"), self.OptionsBox)
        self.OpenBox.setToolTip(QCoreApplication.translate("ConfigDialog", "Automatically open the SRT file created."))
        OptionsLayout.addWidget(self.OpenBox)

        FirstLayout = QHBoxLayout(None)

        self.OptionsBox.setLayout(OptionsLayout)

        FirstLayout = QHBoxLayout(None)
        FirstLayout.addWidget(self.OptionsBox)
        FirstLayout.addLayout(FilesLayout)


        ### Dossier des langues pour Tesseract
        self.TesseractBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Tesseract language configuration:"), self)
        TesseractLayout = QHBoxLayout(None)

        ## Box du dossier
        self.TesseractEntry = QLineEditCustom(self.TesseractBox, "tesseract")
        self.TesseractEntry.setReadOnly(True)
        self.TesseractEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Folder contains the languages for Tesseract.\nYou can drag the folder here."))
        self.FolderEntryIcon1 = QAction(QIcon.fromTheme("folder-open", QIcon(":/img/folder-open.svg")), QCoreApplication.translate("ConfigDialog", "Select folder dialog."), self.TesseractEntry)
        self.FolderEntryIcon1.triggered.connect(lambda: self.TesseractPath(True, None))
        self.FolderEntryIcon2 = QAction(QIcon.fromTheme("edit-undo", QIcon(":/img/edit-undo.svg")), QCoreApplication.translate("ConfigDialog", "Use default folder."), self.TesseractEntry)
        self.FolderEntryIcon2.triggered.connect(lambda: self.TesseractPath(True, "Auto"))
        self.TesseractEntry.addAction(self.FolderEntryIcon1, QLineEdit.LeadingPosition)
        self.TesseractEntry.addAction(self.FolderEntryIcon2, QLineEdit.TrailingPosition)
        TesseractLayout.addWidget(self.TesseractEntry)

        ## Box de la langue de Tesseract
        self.TesseractLangComboBox = QComboBox(self.TesseractBox)
        self.TesseractLangComboBox.setToolTip(QCoreApplication.translate("ConfigDialog", "Language to use for Tesseract."))
        TesseractLayout.addWidget(self.TesseractLangComboBox)

        self.TesseractBox.setLayout(TesseractLayout)


        ### Box de la langue du logiciel
        self.LanguageBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Software language:"), self)
        LanguageLayout = QHBoxLayout(None)
        LangComboBox = QComboBox(self.TesseractBox)
        LangComboBox.addItem(QIcon(":/img/en.png"), "English")
        LangComboBox.addItem(QIcon(":/img/fr.png"), "Français")

        if GlobalVar["Lang"] == "fr":
            LangComboBox.setCurrentIndex(1)

        LanguageLayout.addWidget(LangComboBox)
        self.LanguageBox.setLayout(LanguageLayout)

        SecondLayout = QHBoxLayout(None)
        SecondLayout.addWidget(self.LanguageBox)
        SecondLayout.addWidget(self.TesseractBox)


        ### Box du code
        self.CommandBox = QGroupBox(QCoreApplication.translate("ConfigDialog", "Command line:"), self)
        self.CommandEntry = QTextEdit(self.CommandBox)
        self.CommandEntry.setReadOnly(True)
        self.CommandEntry.resize(50, 50)
        self.CommandBox.resize(75, 75)

        self.CommandCopy = QPushButton(QIcon.fromTheme("edit-copy", QIcon(":/img/edit-copy.svg")), "", self)
        self.CommandCopy.clicked.connect(lambda: ClipBoard.setText(self.CommandEntry.toPlainText(), mode=ClipBoard.Clipboard))
        self.CommandCopy.setToolTip(QCoreApplication.translate("ConfigDialog", "Copy the command in the clipboard."))

        CommandLayout = QHBoxLayout(None)
        CommandLayout.addWidget(self.CommandEntry)
        CommandLayout.addWidget(self.CommandCopy)
        self.CommandBox.setLayout(CommandLayout)


        ### Boutons
        ## Bouton de lancement
        self.RunRun = QPushButton(QIcon.fromTheme("run-build", QIcon(":/img/run-build.svg")), QCoreApplication.translate("ConfigDialog", "Convert file"), self)
        self.RunRun.clicked.connect(self.accepted)

        ## Bouton à propos
        self.AboutSoft = QPushButton(QIcon.fromTheme("help-about", QIcon(":/img/help-about.svg")), QCoreApplication.translate("ConfigDialog", "About"), self)
        self.AboutSoft.clicked.connect(self.About)

        ## Bouton d'arret
        self.ByeBye = QPushButton(QIcon.fromTheme("application-exit", QIcon(":/img/application-exit.svg")), QCoreApplication.translate("ConfigDialog", "Exit"), self)
        self.ByeBye.clicked.connect(self.close)


        ## Layout
        ButtonsLayout = QHBoxLayout(None)
        ButtonsLayout.addWidget(self.ByeBye)
        ButtonsLayout.addStretch()
        ButtonsLayout.addWidget(self.AboutSoft)
        ButtonsLayout.addStretch()
        ButtonsLayout.addWidget(self.RunRun)


        ### Fenêtre
        BigLayout = QVBoxLayout(None)
        BigLayout.addLayout(FirstLayout)
        BigLayout.addLayout(SecondLayout)
        BigLayout.addWidget(self.CommandBox)
        BigLayout.addLayout(ButtonsLayout)
        self.setLayout(BigLayout)


        #~#~# Remplissage de la BigWindow #~#~#
        ### Envoie des adresses ici, si None et qu'on envoie str(var) ça affiche None
        if GlobalVar["IDX"]:
            self.IDXEntry.setText(str(GlobalVar["IDX"]))

        if GlobalVar["SRT"]:
            self.SRTEntry.setText(str(GlobalVar["SRT"]))


        ### Envoie du nombre de CPU à utiliser
        self.CPUSpin.setValue(GlobalVar["NbCPU"])


        ### Envoie la profondeur du guilevel
        self.GuiSpin.setValue(int(GlobalVar["GuiLevel"]))


        ### Envoie la profondeur du debugmode
        self.DebugSpin.setValue(int(GlobalVar["Verbose"]))


        ### Envoie de la profondeur de la coloration
        self.ColorsSpin.setValue(GlobalVar["CustomColors"])


        ### Envoie des états True / False
        self.OpenBox.setChecked(GlobalVar["SRTOpen"])
        self.SRTOverwrite.setChecked(GlobalVar["AutoSRTOverwrite"])
        self.TempOverwrite.setChecked(GlobalVar["AutoTempOverwrite"])


        ### Création d'un dossier temporaire
        self.TemporaryFolder(False, GlobalVar["FolderTemp"])


        ### Dossier de tesseract
        self.TesseractPath(False, GlobalVar["TesseractFolder"])


        ### Affichage de la fenêtre de configuration
        if GlobalVar["GuiLevel"] == 2:
            self.IDXEntry.textChanged.connect(self.CreateCommand)
            self.SRTEntry.textChanged.connect(self.CreateCommand)
            self.TesseractEntry.textChanged.connect(self.CreateCommand)
            self.TempEntry.textChanged.connect(self.CreateCommand)
            self.SRTOverwrite.toggled.connect(self.CreateCommand)
            self.TempOverwrite.toggled.connect(self.CreateCommand)
            self.OpenBox.toggled.connect(self.CreateCommand)
            self.CPUSpin.valueChanged.connect(self.CreateCommand)
            self.GuiSpin.valueChanged.connect(self.CreateCommand)
            self.ColorsSpin.valueChanged.connect(self.CreateCommand)
            self.DebugSpin.valueChanged.connect(self.CreateCommand)
            self.TesseractLangComboBox.currentIndexChanged.connect(self.CreateCommand)
            LangComboBox.currentIndexChanged.connect(LanguageChanged)

            self.CreateCommand()

            self.show()

        else:
            self.Next()



    #========================================================================
    def changeEvent(self, Event):
        """Fonction retraduisant les widgets de la fenêtre."""
        ### Ne traiter que les changements de langue
        if Event.type() == QEvent.LanguageChange:
            self.OptionsBox.setTitle(QCoreApplication.translate("ConfigDialog", "Options:"))
            self.IDXBox.setTitle(QCoreApplication.translate("ConfigDialog", "Input IDX file:"))
            self.IDXEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Source IDX file to translate.\nYou can drag the file here."))
            self.IDXEntryIcon.setText(QCoreApplication.translate("ConfigDialog", "Select file dialog."))
            self.SRTEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Destination SRT file translated.\nYou can drag the parent folder here."))
            self.SRTEntryIcon.setText(QCoreApplication.translate("ConfigDialog", "Select file dialog."))
            self.SRTBox.setTitle(QCoreApplication.translate("ConfigDialog", "Output SRT file:"))
            self.TempBox.setTitle(QCoreApplication.translate("ConfigDialog", "Temporary folder:"))
            self.SRTOverwrite.setToolTip(QCoreApplication.translate("ConfigDialog", "Overwrite the SRT file if it already exists"))
            self.TempEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Temporary folder to use for files extracted.\nYou can drag the folder here."))
            self.TempEntryIcon1.setText(QCoreApplication.translate("ConfigDialog", "Select folder dialog."))
            self.TempEntryIcon2.setText(QCoreApplication.translate("ConfigDialog", "Recreate a temporary folder in /tmp."))
            self.TempOverwrite.setToolTip(QCoreApplication.translate("ConfigDialog", "Remove the temporary folder when closing the software.\nBe Careful if it's a personal folder."))
            self.GuiSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Gui level: "))
            self.GuiSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Level of the gui.\n0: No window at all.\n1: Only check texts window.\n2: All windows."))
            self.CPUSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Use "))
            self.CPUSpin.setSuffix(QCoreApplication.translate("ConfigDialog", " thread(s)"))
            self.CPUSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Number of thread (cpu) to use simultaneous, max value by default."))
            self.ColorsSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Colors level: "))
            self.ColorsSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Colors of the images texts.\n\
Level 0: No use custom colors\n\
Level 1: Use custom colors on images not recognized\n\
Level 2: Use only customs colors"))
            self.DebugSpin.setPrefix(QCoreApplication.translate("ConfigDialog", "Debug level: "))
            self.DebugSpin.setToolTip(QCoreApplication.translate("ConfigDialog", "Verbose mode for debug.\n\
Level 0: Errors messages, by default\n\
Level 1: Level 0, Number of images files created, Temporary folder path, Conversion progress\n\
Level 2: Level 1, Commands Lines, Tesseract languages, Options values, Custom color, Conversion started, Check texts needed, SRT file created\n\
Level 3: Level 2, Convert files names, Dialog creation info, List of the texts to check"))
            self.ColorConfig.setToolTip(QCoreApplication.translate("ConfigDialog", "Customize the colors."))
            self.OpenBox.setText(QCoreApplication.translate("ConfigDialog", "Open SRT file"))
            self.OpenBox.setToolTip(QCoreApplication.translate("ConfigDialog", "Automatically open the SRT file created."))
            self.TesseractBox.setTitle(QCoreApplication.translate("ConfigDialog", "Tesseract language configuration:"))
            self.TesseractEntry.setToolTip(QCoreApplication.translate("ConfigDialog", "Folder contains the languages for Tesseract.\nYou can drag the folder here."))
            self.FolderEntryIcon1.setText(QCoreApplication.translate("ConfigDialog", "Select folder dialog."))
            self.FolderEntryIcon2.setText(QCoreApplication.translate("ConfigDialog", "Use default folder."))
            self.TesseractLangComboBox.setToolTip(QCoreApplication.translate("ConfigDialog", "Language to use for Tesseract."))
            self.LanguageBox.setTitle(QCoreApplication.translate("ConfigDialog", "Software language:"))
            self.CommandBox.setTitle(QCoreApplication.translate("ConfigDialog", "Command line:"))
            self.RunRun.setText(QCoreApplication.translate("ConfigDialog", "Convert file"))
            self.AboutSoft.setText(QCoreApplication.translate("ConfigDialog", "About"))
            self.ByeBye.setText(QCoreApplication.translate("ConfigDialog", "Exit"))
            self.CommandCopy.setToolTip(QCoreApplication.translate("ConfigDialog", "Copy the command in the clipboard."))


        ### Accepter les events
        Event.accept()



    #========================================================================
    def About(self):
        """Fonction affichant une fenêtre d'information sur le soft."""
        ### Bouton Qt
        AboutQt = QPushButton(QIcon.fromTheme("qt", QIcon(":/img/qt.png")), QCoreApplication.translate("About", "About Qt"), self)
        AboutQt.clicked.connect(lambda: QMessageBox.aboutQt(self))


        ### Bouton Changelog
        WhatUpButton = QPushButton(QIcon.fromTheme("text-x-texinfo", QIcon(":/img/text-x-texinfo.png")), QCoreApplication.translate("About", "What's up ?"), self)
        WhatUpButton.clicked.connect(lambda: WhatsUp('/usr/share/doc/qtesseract5/changelog.Debian.gz', 'qtesseract5', QCoreApplication.translate("About", "Changelog of Qtesseract5"), self))


        ### Fenêtre d'info
        Win = QMessageBox(QMessageBox.NoIcon,
                          QCoreApplication.translate("About", "About Qtesseract5"),
                          QCoreApplication.translate("About", """<html><head/><body><p align="center"><span style=" font-size:12pt; font-weight:600;">Qtesseract5 v{}</span></p><p><span style=" font-size:10pt;">GUI to convert a SUB/IDX file to SRT file..</span></p><p><span style=" font-size:10pt;">This software is programed in python3 + QT5 and is licensed under </span><span style=" font-size:8pt; font-weight:600;"><a href="{}">GNU GPL v3</a></span><span style=" font-size:8pt;">.</span></p><p>Thanks to the <a href="http://www.developpez.net/forums/f96/autres-langages/python-zope/"><span style=" text-decoration: underline; color:#0057ae;">developpez.net</span></a> python forums for their help.</p><p align="right">Created by <span style=" font-weight:600;">Belleguic Terence</span> (<a href="mailto:hizo@free.fr">Hizoka</a>), 2016</p></body></html>""").format(Qtesseract5.applicationVersion(), "http://www.gnu.org/copyleft/gpl.html"),
                          QMessageBox.Close, self)
        Win.setIconPixmap(QPixmap(QIcon.fromTheme("qtesseract5", QIcon(":/img/qtesseract5.png")).pixmap(175)))
        Win.setMinimumWidth(800)

        Win.addButton(AboutQt, QMessageBox.HelpRole)

        if Path('/usr/share/doc/qtesseract5/changelog.Debian.gz').exists():
            Win.addButton(WhatUpButton, QMessageBox.HelpRole)

        Win.setDefaultButton(QMessageBox.Close)

        Win.exec()


        ### Relance la fenêtre si on a cliqué sur les boutons AboutQt ou WhatUpButton
        if Win.clickedButton() in (AboutQt, WhatUpButton):
            self.About()


    #========================================================================
    def TemporaryFolder(self, Gui=False, Folder=None):
        """Fonction de la gestion et de la création du dossier temporaire."""
        ### Variables
        GlobalVar["FolderTempWait"] = True


        ### S'il faut demander le fichier
        if Gui and not Folder:
            ## Sélecteur de fichier
            Folder = QFileDialog.getExistingDirectory(None, QCoreApplication.translate("ConfigDialog", "Select the temporary folder"), QDir.homePath(), QFileDialog.ShowDirsOnly)

            ## En cas d'annulation
            if not Folder:
                return


        ### Suppression de l'ancien dossier temporaire s'il existe
        if GlobalVar["FolderTempWidget"]:
            GlobalVar["FolderTempWidget"].remove()
            GlobalVar["FolderTempWidget"] = None


        ### Création d'un dossier aléatoire temporaire
        if Folder == "Auto" or (not Gui and not Folder):
            ## Boucle pour être sûr qu'un dossier temporaire est créé
            while True:
                # Création d'un dossier temporaire
                GlobalVar["FolderTempWidget"] = QTemporaryDir()

                # Vérifie la validité du dossier temporaire
                if GlobalVar["FolderTempWidget"].isValid():
                    # Mise à jour de la variable
                    Folder = Path(GlobalVar["FolderTempWidget"].path())

                    # Arret de la boucle
                    break


        ### Si le dossier n'existe pas, on le crée
        if not Path(Folder).exists():
            Path(Folder).mkdir(parents=True)


        ### Liste le contenu du dossier pour être sur qu'il est vide pour éviter un problème
        FilesInFolder = []
        FilesInFolder.extend(Path(Folder).glob("*"))

        if FilesInFolder:
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The temporary folder must be empty."))
                self.TempEntry.setPalette(PalettesWigets["LineEdit"])
                self.TempEntry.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "The temporary folder must be empty."))


        ### Si ce n'est pas un dossier ou que c'est le home
        if not Path(Folder).is_dir():
            ## Message d'erreur
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The temporary folder must be a dir..."))
                self.TempEntry.setPalette(PalettesWigets["LineEdit"])
                self.TempEntry.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "The temporary folder must be a dir..."))

        ### Si ce n'est pas un dossier ou que c'est le home
        elif Path(Folder) == Path(QDir.homePath()):
            ## Message d'erreur
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The temporary folder cannot be your home dir..."))
                self.TempEntry.setPalette(PalettesWigets["LineEdit"])
                self.TempEntry.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "The temporary folder cannot be your home dir..."))


        ### Affichage du dossier temporaire
        GlobalVar["FolderTemp"] = Path(Folder)

        ## Dans le terminal
        if GlobalVar["Verbose"]:
            print("Temporary folder: {}".format(GlobalVar["FolderTemp"]), file=sys.stdout)

        ## Mise à jour du dossier
        self.TempEntry.setText(str(GlobalVar["FolderTemp"]))


        ### Variable débloquante
        GlobalVar["FolderTempWait"] = False


        ### Coloration du widget
        self.TempEntry.setPalette(self.TempEntry.style().standardPalette())


        ### Rechargement du code en mode gui (en fait ne le fait pas que lors de la création de la fenêtre de config)
        if Gui:
            self.CreateCommand()



    #========================================================================
    def TesseractPath(self, Gui=False, Folder=None):
        """Fonction définissant le dossier des langues supportées par Tesseract et leur listage."""
        GlobalVar["FolderTesseractWait"] = True

        if not Folder or Folder == "Auto":
            ### Demande le dossier du projet si pas passé par les arguments et mode Gui
            if Gui and not Folder:
                ## Sélecteur de fichier
                Folder = QFileDialog.getExistingDirectory(None, QCoreApplication.translate("ConfigDialog", "Select the langs folder for Tesseract"), QDir.homePath(), QFileDialog.ShowDirsOnly)

                ## En cas d'annulation
                if not Folder:
                    return


            ### Dossier de base des langues
            elif Path("/usr/share/tessdata/eng.traineddata").exists():
                Folder = "/usr/share/tessdata/"

            ### Il y a eu encore un changement de dossier à priori du dossier des langues...
            else:
                for Item in Path("/usr/share/tesseract-ocr").glob('**/tessdata'):
                    if Item.is_dir():
                        Folder = str(Item)
                        break

        ### Si ce n'est pas un dossier
        if not Path(Folder).is_dir():
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The Tesseract folder must be a dir..."))
                self.TesseractEntry.setPalette(PalettesWigets["LineEdit"])
                self.TesseractEntry.clear()
                self.TesseractLangComboBox.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "The Tesseract folder must be a dir..."))


        ### Liste les fichiers traineddata du dossier pour vérifier qu'il y en a
        FilesInFolder = []
        FilesInFolder.extend(Path(Folder).glob("*.traineddata"))


        ### Si le dossier n'a pas de fichier traineddata
        if not FilesInFolder:
            ## Liste les fichiers traineddata du dossier précédant pour vérifier qu'il y en avait
            OldFolder = self.TesseractEntry.text()

            if OldFolder:
                FilesInOldFolder = []
                FilesInOldFolder.extend(Path(OldFolder).glob("*.traineddata"))

            ## Message indiquant qu'on remet l'ancien dossier
            if OldFolder and FilesInOldFolder:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The Tesseract folder must contain file(s) *.traineddata.\nUse the old value {}.").format(OldFolder))
                self.TesseractEntry.setPalette(PalettesWigets["LineEdit"])
                self.TesseractEntry.clear()
                self.TesseractLangComboBox.clear()
                self.CreateCommand()
                return

            ## Message indiquant que ce n'est pas le bon dossier non plus
            else:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "This new folder not contains traineddata files."))


        ### Mise à jour variables
        GlobalVar["TesseractFolder"] = Path(Folder)
        GlobalVar["TesseractLangs"].clear()


        ### Modifications graphiques
        self.TesseractEntry.setText(str(GlobalVar["TesseractFolder"]))
        self.TesseractLangComboBox.clear()


        ### Création de la commande
        cmd = 'tesseract --list-langs --tessdata-dir "{}"'.format(GlobalVar["TesseractFolder"])


        ### Listage des langues de Tesseract et ajout des langues de 3 caractères
        for Lang in LittleProcess(cmd):
            if len(Lang) == 3:
                ## Remplissage de la liste
                GlobalVar["TesseractLangs"].append(Lang)

                # Ajoute la langue avec son drapeau
                try:
                    Icon = "/usr/share/locale/l10n/{}/flag.png".format(LangCodes[Lang])

                    if Path(Icon).exists():
                        self.TesseractLangComboBox.addItem(QIcon(Icon), Lang)

                    else:
                        self.TesseractLangComboBox.addItem(QIcon(":/img/un.png"), Lang)

                # Ajoute la langue avec un drapeau non spécifique
                except:
                    self.TesseractLangComboBox.addItem(QIcon(":/img/un.png"), Lang)


                ## Debug mode
                if GlobalVar["Verbose"] >= 2:
                    print(QCoreApplication.translate("ConfigDialog", "Tesseract can use the languages: {}").format(Lang))


        ### Si aucune langue n'a été trouvée, c'est que le dossier de Tesseract n'est pas le bon...
        if len(GlobalVar["TesseractLangs"]) == 0:
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "Tesseract hasn't found the languages. The folder haven't languages files."))
                self.TesseractEntry.setPalette(PalettesWigets["LineEdit"])
                self.TesseractEntry.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "Tesseract hasn't found the languages. The folder haven't languages files."))


        ### Si la langue indiquée n'est pas trouvée, ici pour éviter une double erreur
        elif GlobalVar["TesseractLanguage"] not in GlobalVar["TesseractLangs"]:
            if GlobalVar["GuiLevel"] == 2:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The subtitle language ({}) indicate in argument is not avaible in Tesseract languages.").format(GlobalVar["TesseractLanguage"]))
                self.TesseractEntry.setPalette(PalettesWigets["LineEdit"])
                self.TesseractEntry.clear()
                self.CreateCommand()
                return

            else:
                QuitError(QCoreApplication.translate("ConfigDialog", "The subtitle language ({}) indicate in argument is not avaible in Tesseract languages.").format(GlobalVar["TesseractLanguage"]))


        ### Si tout est bon
        ## Recherche la valeur
        Index = self.TesseractLangComboBox.findText(GlobalVar["TesseractLanguage"])

        ## Si la langue est introuvable
        if Index == -1:
            ErrorMessages(QCoreApplication.translate("ConfigDialog", "The subtitle language ({}) indicate in argument is not avaible in Tesseract languages.").format(GlobalVar["TesseractLanguage"]))

        elif Index > -1:
            self.TesseractLangComboBox.setCurrentIndex(Index)


        ### Variable débloquante et remise au propre de la couleur
        GlobalVar["FolderTesseractWait"] = False
        self.TesseractEntry.setPalette(self.TesseractEntry.style().standardPalette())


        ### Rechargement du code en mode gui (en fait ne le fait pas que lors de la création de la fenêtre de config)
        if Gui:
            self.CreateCommand()



    #========================================================================
    def IDXPathWin(self):
        """Fonction de sélection du fichier IDX."""
        ### Demande le fichier IDX à utiliser
        Value = QFileDialog.getOpenFileName(None, QCoreApplication.translate("ConfigDialog", "Select the IDX file to translate"), QDir.homePath(), "IDX file (*.idx)")[0]


        ### Envoie de la valeur dans la GUI
        if Value:
            self.IDXEntry.setText(str(Value))



    #========================================================================
    def SRTPathWin(self):
        """Fonction de sélection du fichier SRT de sortie."""
        ### Demande le fichier de sortie
        Value = QFileDialog.getSaveFileName(None, QCoreApplication.translate("ConfigDialog", "Select the output SRT file translated"), QDir.homePath(), "Text file (*.srt *.txt)")[0]


        ### Envoie de la valeur dans la GUI
        if Value:
            self.SRTEntry.setText(str(Value))



    #========================================================================
    def CheckInfos(self, Next):
        """Fonction vérifiant les données pour continuer le travail."""
        ### Blocage du bouton de poursuite
        self.RunRun.setEnabled(False)

        # Next fait la différence entre la création du code et le passage à la suite
        ### Récupération des valeurs via la gui
        GlobalVar["IDX"] = Path(self.IDXEntry.text())
        GlobalVar["SRT"] = Path(self.SRTEntry.text())
        GlobalVar["TesseractFolder"] = self.TesseractEntry.text()
        GlobalVar["TesseractLanguage"] = self.TesseractLangComboBox.currentText()
        GlobalVar["NbCPU"] = self.CPUSpin.value()
        GlobalVar["CustomColors"] = self.ColorsSpin.value()
        GlobalVar["Verbose"] = self.DebugSpin.value()
        GlobalVar["SRTOpen"] = self.OpenBox.isChecked()
        GlobalVar["AutoSRTOverwrite"] = self.SRTOverwrite.isChecked()
        GlobalVar["AutoTempOverwrite"] = self.TempOverwrite.isChecked()
        GlobalVar["GuiLevel"] = self.GuiSpin.value()
        GlobalVar["RoundNumber"] = 1


        ### Si on passe pas à la suite
        if Next:
            ## Debug mode
            if GlobalVar["Verbose"] >= 2:
                print(QCoreApplication.translate("ConfigDialog", "=> Command arguments <="), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "CustomColors arg: {}").format(GlobalVar["CustomColors"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "CustomColors to use arg: {}").format(GlobalVar["ColorsToUse"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Verbose arg: {}").format(GlobalVar["Verbose"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "IDX arg: {}").format(GlobalVar["IDX"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Number of CPU arg: {}").format(GlobalVar["NbCPU"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "SRT arg: {}").format(GlobalVar["SRT"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Open SRT file arg: {}").format(GlobalVar["SRTOpen"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Tesseract Language arg: {}").format(GlobalVar["TesseractLanguage"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Auto overwrite SRT file arg: {}").format(GlobalVar["AutoSRTOverwrite"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Auto remove the temporary folder arg: {}").format(GlobalVar["AutoTempOverwrite"]), file=sys.stdout)
                print(QCoreApplication.translate("ConfigDialog", "Gui level arg: {}").format(GlobalVar["GuiLevel"]), file=sys.stdout)


        ### Teste du dossier temporaire:
        if GlobalVar["FolderTempWait"] or GlobalVar["FolderTesseractWait"]:
            return


        ### Si le fichier IDX n'existe pas, on en créé un, cela suffit
        if not GlobalVar["IDX"].is_file():
            ## Si le fichier IDX n'est pas un dossier
            if not GlobalVar["IDX"].is_dir():
                # Fichier sub
                GlobalVar["SUB"] = GlobalVar["IDX"].with_suffix(".sub")

                # Si le fichier sub existe et est un fichier
                if GlobalVar["SUB"].is_file():
                    GlobalVar["IDX"] = GlobalVar["IDX"].with_suffix(".idx")
                    GlobalVar["IDX"].touch()

                # S'il n'y a pas de fichier sub
                else:
                    # Si on passe pas à la suite
                    if Next:
                        # Message d'erreur
                        if GlobalVar["GuiLevel"] == 2:
                            ErrorMessages(QCoreApplication.translate("ConfigDialog", "No SUB input file."))

                        else:
                            QuitError(QCoreApplication.translate("ConfigDialog", "No SUB input file."))

                    # Si c'est pour la création du code
                    else:
                        # Coloration du widget
                        self.IDXEntry.setPalette(PalettesWigets["LineEdit"])

            ## Si le fichier idx est un dossier
            else:
                # Coloration du widget
                self.IDXEntry.setPalette(PalettesWigets["LineEdit"])

            return False

        ### Si le fichier IDX est ok
        else:
            ## Suppression de la coloration du widget
            self.IDXEntry.setPalette(self.IDXEntry.style().standardPalette())



        ### Si le fichier SRT est un dossier
        if GlobalVar["SRT"].is_dir():
            ## Si on passe pas à la suite
            if Next:
                # Message d'erreur
                if GlobalVar["GuiLevel"] == 2:
                    ErrorMessages(QCoreApplication.translate("ConfigDialog", "The SRT output file cannot have the same name as a folder."))

                else:
                    QuitError(QCoreApplication.translate("ConfigDialog", "The SRT output file cannot have the same name as a folder."))

            ## Si c'est pour la création du code
            else:
                # Coloration du widget
                self.SRTEntry.setPalette(PalettesWigets["LineEdit"])

            return False


        ### Si le fichier SRT est un fichier déjà existant et pas de remplacement automatique du fichier
        elif GlobalVar["SRT"].is_file() and not GlobalVar["AutoSRTOverwrite"]:
            ## Si on passe pas à la suite
            if Next:
                ErrorMessages(QCoreApplication.translate("ConfigDialog", "The output SRT file already exists."))

            return False


        ### Si le fichier SRT est ok
        else:
            # Suppression de la coloration du widget
            self.SRTEntry.setPalette(self.SRTEntry.style().standardPalette())


        ### Déblocage du bouton de poursuite
        self.RunRun.setEnabled(True)


        ### Tout s'est bien passé
        return True



    #========================================================================
    def CreateCommand(self):
        """Fonction de création de la commande."""
        ### Vérification des valeurs
        Value = self.CheckInfos(False)


        ### Création du code si tout est ok
        if Value:
            cmd = '<span style=" color:#000000;">Qtesseract5</span> <span style=" color:#0057ae;">-g {}</span> '.format(GlobalVar["GuiLevel"])

            if GlobalVar["NbCPU"] > 1:
                cmd += '<span style=" color:#0000FF;">-t {}</span> '.format(GlobalVar["NbCPU"])

            if GlobalVar["CustomColors"]:
                cmd += '<span style=" color:#b62d7d;">-c {}</span> '.format(GlobalVar["CustomColors"])

            if GlobalVar["Verbose"]:
                cmd += '<span style=" color:#ff3300;">-v {}</span> '.format(GlobalVar["Verbose"])

            if GlobalVar["SRTOpen"]:
                cmd += '<span style=" color:#4c70a3;">-o</span> '

            cmd += '<span style=" color:#003300;">-l {}</span> <span style=" color:#006666;">-L "{}"</span> <span style=" color:#993300;">"{}"</span> <span style=" color:#5b175d;">"{}"</span>'.format(GlobalVar["TesseractLanguage"], GlobalVar["TesseractFolder"], GlobalVar["IDX"], GlobalVar["SRT"])

            ## Envoie de la commande
            self.CommandEntry.setHtml(cmd)



    #========================================================================
    def Next(self):
        """Fonction lançant la dialogue de progression."""
        ### Vérification des valeurs pour être sur...
        Reply = self.CheckInfos(True)


        ### En cas de problème sans gui, on arrete le soft
        if GlobalVar["GuiLevel"] < 2 and not Reply:
            self.close()


        ### En cas de probleme avec gui, on quitte la fonction
        elif not Reply:
            return


        ### On cache la fenêtre de configuration
        self.hide()


        ### Lancement de la fenêtre de progression qui va convertir les images en textes
        GlobalVar["ProgressDialog"] = ProgressDialog(None)



    #========================================================================
    def closeEvent(self, Event):
        """Fonction appelée lors de la fermeture de fenêtre autre que accept."""
        GlobalVar["ExitCode"] = 1


        ### Suppression du dossier temporaire automatique
        if GlobalVar["AutoTempOverwrite"]:
            if GlobalVar["FolderTempWidget"] and not GlobalVar["FolderTempWidget"].remove():
                ErrorMessages(QCoreApplication.translate("main", "The temporary folder was not deleted."))


        Event.accept()



#############################################################################
class CustomizeDialog(QDialog):
    """Fenêtre de personnalisation des couleurs."""
    def __init__(self, Parent):
        super().__init__()


        ### Valeur actuelle
        self.Parent = Parent
        self.OldValue = GlobalVar["ColorsToUse"]


        ### Mode verbose
        if GlobalVar["Verbose"] == 3:
            print(QCoreApplication.translate("CustomizeDialog", "Customize creation"), file=sys.stdout)


        ### Fenêtre
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setMinimumWidth(600)
        self.setWindowTitle("{} v{}".format(QCoreApplication.applicationName(), QCoreApplication.applicationVersion()))
        self.accepted.connect(self.ExitOk)
        self.rejected.connect(self.ExitCancel)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setWindowTitle(QCoreApplication.translate("CustomizeDialog", "Customize the colors"))

        Box = QGroupBox(QCoreApplication.translate("CustomizeDialog", "Choose the custom colors:"), self)
        Label = QLabel(QCoreApplication.translate("CustomizeDialog", "1er color: shape outside.\n2nd color: shape\n3th color: text.\n4t color: ???"), Box)

        self.Entry = QLineEdit(self)
        self.Entry.setClearButtonEnabled(True)
        self.Entry.setEnabled(False)

        self.Radio1 = QRadioButton("custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000", Box)
        self.Radio2 = QRadioButton("custom colors: ON, tridx: 0000, colors: 000000, ffffff, ffffff, ffffff", Box)
        self.Radio3 = QRadioButton(Box)
        self.Radio3.toggled.connect(self.Radio3Entry)

        if GlobalVar["ColorsToUse"] == "custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000":
            self.Radio1.setChecked(True)
            self.Entry.setText("custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000")

        elif GlobalVar["ColorsToUse"] == "custom colors: ON, tridx: 0000, colors: 000000, ffffff, ffffff, ffffff":
            self.Radio2.setChecked(True)
            self.Entry.setText("custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000")

        else:
            self.Radio3.setChecked(True)
            self.Entry.setText(GlobalVar["ColorsToUse"])

        RadioEntryLayout = QHBoxLayout(None)
        RadioEntryLayout.addWidget(self.Radio3)
        RadioEntryLayout.addWidget(self.Entry)

        RadioLayout = QVBoxLayout(None)
        RadioLayout.addWidget(Label)
        RadioLayout.addWidget(self.Radio1)
        RadioLayout.addWidget(self.Radio2)
        RadioLayout.addLayout(RadioEntryLayout)
        Box.setLayout(RadioLayout)

        ButtonOk = QPushButton(QIcon.fromTheme("dialog-ok-apply", QIcon(":/img/dialog-ok-apply.svg")), QCoreApplication.translate("CustomizeDialog", "Apply"), self)
        ButtonOk.setToolTip(QCoreApplication.translate("CustomizeDialog", "Validate my choice."))


        if self.Parent == "CheckTextDialog":
            ButtonOk.clicked.connect(self.Direct)
        else:
            ButtonOk.clicked.connect(self.accept)


        ButtonCancel = QPushButton(QIcon.fromTheme("dialog-cancel", QIcon(":/img/dialog-cancel.svg")), QCoreApplication.translate("CustomizeDialog", "Cancel"), self)
        ButtonCancel.setToolTip(QCoreApplication.translate("CustomizeDialog", "Reload old value."))
        ButtonCancel.clicked.connect(self.close)

        ButtonTest = QPushButton(QIcon.fromTheme("archive-extract", QIcon(":/img/archive-extract.svg")), QCoreApplication.translate("CustomizeDialog", "Extract images"), self)
        ButtonTest.setToolTip(QCoreApplication.translate("CustomizeDialog", "Extract and view images texts with custom colors."))
        ButtonTest.clicked.connect(self.ExteractImages)

        HLayout = QHBoxLayout(None)
        HLayout.addWidget(ButtonCancel)
        HLayout.addStretch()
        HLayout.addWidget(ButtonTest)
        HLayout.addStretch()
        HLayout.addWidget(ButtonOk)

        VLayout = QVBoxLayout(None)
        VLayout.addWidget(Box)
        VLayout.addLayout(HLayout)

        self.setLayout(VLayout)


        if self.Parent == "CheckTextDialog":
            ButtonTest.setVisible(False)

        self.exec()



    #========================================================================
    def Radio3Entry(self, Value):
        """Fonction désactivant ou activant la boite de texte."""
        self.Entry.setEnabled(Value)



    #========================================================================
    def Direct(self):
        """Fonction se limitant à l'extraction des images et au rechargement de l'image de la fenêtre de check."""
        self.setCursor(Qt.WaitCursor)

        self.accept()


        ### Initialisation de variables
        GlobalVar["IDX"] = Path(GlobalVar["ConfigDialog"].IDXEntry.text())
        GlobalVar["SUB"] = GlobalVar["IDX"].with_suffix(".sub")
        GlobalVar["IDXTemp"] = Path(GlobalVar["FolderTemp"], GlobalVar["IDX"].name)
        GlobalVar["SUBTemp"] = GlobalVar["IDXTemp"].with_suffix(".sub")
        GlobalVar["Generic"] = GlobalVar["IDXTemp"].with_suffix("")


        ### Si le fichier IDX n'existe pas, on en créé un
        if not GlobalVar["IDX"].is_file():
            GlobalVar["IDX"].touch()


        ### Si le fichier sub existe aussi
        if GlobalVar["SUB"].is_file():
            ## Extraction des images
            subp2pgm(True)


        GlobalVar["CheckTextDialog"].IMGSlide()

        self.setCursor(Qt.ArrowCursor)


    #========================================================================
    def ExitOk(self):
        """Fonction appeler via le bouton de fermeture validé qui sauvegarde la valeur des couleurs personnalisées."""
        ### Texte de la boite d'entry
        Value = self.Entry.text()


        ### Traitement des radiobuttons
        if self.Radio1.isChecked():
            GlobalVar["ColorsToUse"] = "custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000"

        elif self.Radio2.isChecked():
            GlobalVar["ColorsToUse"] = "custom colors: ON, tridx: 0000, colors: 000000, ffffff, ffffff, ffffff"

        elif self.Radio3.isChecked() and Value:
            GlobalVar["ColorsToUse"] = Value

        elif self.OldValue:
            GlobalVar["ColorsToUse"] = self.OldValue

        else:
            GlobalVar["ColorsToUse"] = "custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000"



    #========================================================================
    def ExitCancel(self):
        """Fonction appeler via le bouton de fermeture annuler qui reprend l'ancienne valeur des couleurs personnalisées."""
        if self.OldValue:
            GlobalVar["ColorsToUse"] = self.OldValue



    #========================================================================
    def ExteractImages(self):
        """Fonction se limitant à l'extraction des images et leur affichage."""
        self.setCursor(Qt.WaitCursor)

        ### Récupération de la valeur custom
        self.ExitOk()


        ### Initialisation de variables
        GlobalVar["IDX"] = Path(GlobalVar["ConfigDialog"].IDXEntry.text())
        GlobalVar["SUB"] = GlobalVar["IDX"].with_suffix(".sub")
        GlobalVar["IDXTemp"] = Path(GlobalVar["FolderTemp"], GlobalVar["IDX"].name)
        GlobalVar["SUBTemp"] = GlobalVar["IDXTemp"].with_suffix(".sub")
        GlobalVar["Generic"] = GlobalVar["IDXTemp"].with_suffix("")


        ### Si le fichier IDX n'existe pas, on en créé un
        if not GlobalVar["IDX"].is_file():
            GlobalVar["IDX"].touch()


        ### Si le fichier sub existe aussi
        if GlobalVar["SUB"].is_file():
            ## Extraction des images
            subp2pgm(True)

            ## Noms théoriques des fichiers
            PGMFile = Path(GlobalVar["FolderTemp"], "{}0001.pgm".format(GlobalVar["IDX"].stem))
            TIFFile = PGMFile.with_suffix(".tif")

            ## Si l'un des fichiers existe, on l'affiche
            if PGMFile.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(PGMFile)))

            elif TIFFile.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(TIFFile)))

        self.setCursor(Qt.ArrowCursor)



#############################################################################
class ProgressDialog(QDialog):
    """Fenêtre de progression du travail en cours."""
    ### Si on utilise 2 tours, le 1er avec la couleur de base et la 2e avec les couleurs perso
    # 1) __init__
    # 2) ExtractionThread
    # 3) AfterExtraction
    # 4) ProgressThread
    # 5) Next                => fin du 1er tour
    # 6) ExtractionThread
    # 7) AfterExtraction
    # 8) ProgressThread
    # 9) Next               => fin du 2e tour

    def __init__(self, Parent=None):
        """Création de la fenêtre de progression."""
        super().__init__(Parent)


        ### Debug mode
        if GlobalVar["Verbose"] == 3:
            print(QCoreApplication.translate("ProgressDialog", "Progress dialog creation"), file=sys.stdout)


        ### Fenêtre en elle même
        self.setFixedSize(525, 125)
        self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("{} v{}".format(QCoreApplication.applicationName(), QCoreApplication.applicationVersion()))
        self.rejected.connect(self.Stop)
        self.setAttribute(Qt.WA_DeleteOnClose)


        ### Barre de progression
        self.ProgressBar = QProgressBar(None)
        self.ProgressBar.setMinimum(0)
        self.ProgressBar.setMaximum(0)


        ### Texte d'explication
        self.ProgressLabel = QLabel(QCoreApplication.translate("ProgressDialog", "Extraction of the images texts in progress..."), self)
        self.ProgressLabel.setAlignment(Qt.AlignCenter)
        self.ProgressLabel.setWordWrap(True)


        ### Affichage de l'image du logiciel
        Image = QLabel(self)
        Image.setPixmap(QIcon.fromTheme("qtesseract5", QIcon(":/img/qtesseract5.png")).pixmap(96, 96))
        Image.setMinimumHeight(96)
        Image.setMinimumWidth(96)


        ### Bouton stop
        self.StopButton = QPushButton(QIcon.fromTheme("process-stop", QIcon(":/img/process-stop.svg")), QCoreApplication.translate("ProgressDialog", "Stop"), None)
        self.StopButton.clicked.connect(self.reject) # Le nettoyage est fait via la commande lancée après le exec de la fenêtre
        self.StopButton.setEnabled(False)


        ### Bouton pause
        self.PauseButton = QPushButton(QIcon.fromTheme("media-playback-pause", QIcon(":/img/media-playback-pause.svg")), QCoreApplication.translate("ProgressDialog", "Pause"), None)
        self.PauseButton.setDefault(True)
        self.PauseButton.setCheckable(True)
        self.PauseButton.clicked.connect(self.WorkPauseButton)
        self.PauseButton.setEnabled(False)


        ### Organisation de la fenêtre
        HLayout = QHBoxLayout(None)
        HLayout.addWidget(self.StopButton)
        HLayout.addStretch()
        HLayout.addWidget(self.PauseButton)

        VLayout = QVBoxLayout(None)
        VLayout.addWidget(self.ProgressLabel)
        VLayout.addWidget(self.ProgressBar)
        VLayout.addLayout(HLayout)

        BigLayout = QHBoxLayout(None)
        BigLayout.addWidget(Image)
        BigLayout.addLayout(VLayout)

        self.setLayout(BigLayout)


        ### Affiche si besoin la fenêtre
        if GlobalVar["GuiLevel"] == 2:
            self.show()


        ### Initialisation de variables
        GlobalVar["MD5Dico"] = {}
        GlobalVar["SUB"] = GlobalVar["IDX"].with_suffix(".sub")
        GlobalVar["IDXTemp"] = Path(GlobalVar["FolderTemp"], GlobalVar["IDX"].name)
        GlobalVar["SUBTemp"] = GlobalVar["IDXTemp"].with_suffix(".sub")
        GlobalVar["Generic"] = GlobalVar["IDXTemp"].with_suffix("")


        ### Extraction des images via un QThread pour ne pas bloquer la fenêtre de progression
        ## Création du thread
        GlobalVar["ExtractionThread"] = ExtractionThread()

        ## Connexion du signal
        GlobalVar["ExtractionThread"].ExtractionFinished.connect(self.AfterExtraction)

        ## Démarrage du thread
        GlobalVar["ExtractionThread"].start()



    #========================================================================
    def AfterExtraction(self):
        """Travail post extraction des images."""
        # 1 seul tour si CustomColors = 0 ou 2
        # 2 tours si CustomColors = 1 (1er tour sans, 2e tour avec sur les images problématiques)

        GlobalVar["Ctrl+C"] = False

        ### Debug mode
        if GlobalVar["Verbose"] >= 2:
            ## Dans le cas de custom colors direct ou 2e tour
            if GlobalVar["CustomColors"] == 2 or GlobalVar["RoundNumber"] == 2:
                print(QCoreApplication.translate("ProgressDialog", "Conversion from images to texts with custom colors"))

            ## Mode sans custom colors
            else:
                print(QCoreApplication.translate("ProgressDialog", "Conversion from images to texts"))


        ### Création d'une liste des fichiers sous titres à convertir
        GlobalVar["SubImgFiles"] = []

        ## Dans le cas de custom colors 2e tour
        if GlobalVar["RoundNumber"] == 2:
            for ImageFiles in GlobalVar["MD5Dico"].values():
                GlobalVar["SubImgFiles"].extend(ImageFiles)

            TotalFiles = len(GlobalVar["SubImgFiles"])

        ## Dans le cas de custom color direct ou sans custom color
        else:
            for ImageFile in ["*.pgm", "*.tif"]:
                GlobalVar["SubImgFiles"].extend(GlobalVar["FolderTemp"].glob(ImageFile))

            TotalFiles = GlobalVar["TotalSubtitles"]

        GlobalVar["SubImgFiles"].sort()


        ### S'il n'y a pas de fichier à traiter c'est qu'il y a eu un problème
        if not GlobalVar["SubImgFiles"]:
            ## Renvoie un erreur de création
            QuitError(QCoreApplication.translate("ProgressDialog", "No image file created by subp2pgm?!"))


        ### Modifications graphiques
        self.PauseButton.setEnabled(True)
        self.StopButton.setEnabled(True)
        self.ProgressBar.setFormat(QCoreApplication.translate("ProgressDialog", "%v files done"))
        self.ProgressBar.setMaximum(TotalFiles)


        ## Dans le cas de custom colors direct ou 2e tour
        if GlobalVar["CustomColors"] == 2 or GlobalVar["RoundNumber"] == 2:
            self.ProgressLabel.setText(QCoreApplication.translate("ProgressDialog", "Convertion of %n image(s) by Tesseract with custom colors in progress...", "%n is the number of image", TotalFiles))

        ## Mode sans custom colors
        else:
            self.ProgressLabel.setText(QCoreApplication.translate("ProgressDialog", "Convertion of %n image(s) by Tesseract in progress...", "%n is the number of image", TotalFiles))


        ### Conversion des images en textes
        ## Utile uniquement lors du 1er tour
        if GlobalVar["RoundNumber"] == 1:
            ## Création du thread
            GlobalVar["MonProgressThread"] = ProgressThread()

            ## Connexion des signaux de progression et de fin du thread
            GlobalVar["MonProgressThread"].ProgDuThread.connect(self.WorkProgression)
            GlobalVar["MonProgressThread"].PauseDuThread.connect(self.WorkPauseExt)
            GlobalVar["MonProgressThread"].KillDuThread.connect(self.Stop)
            GlobalVar["MonProgressThread"].FinDuThread.connect(self.Next)


        ## Démarrage du thread
        GlobalVar["MonProgressThread"].start()


        ### Boucle qui surveille l'arrêt brutal avec ctrl + c du mode console ou de la présence d'un fichier Stop
        if GlobalVar["GuiLevel"] < 2:
            try:
                while not GlobalVar["Ctrl+C"]:
                    sleep(0.2)

                    if Path(GlobalVar["FolderTemp"], "Stop").exists():
                        self.Stop()
                        break

            except KeyboardInterrupt:
                self.Stop()



    #========================================================================
    def WorkPauseButton(self):
        """Fonction de gestion de la pause du logiciel via la création ou la suppression d'un fichier Pause."""
        ### Suppression du fichier Pause sil existe
        if Path(GlobalVar["FolderTemp"], "Pause").exists():
            Path(GlobalVar["FolderTemp"], "Pause").unlink()


        ### Création du fichier de Pause si besoin
        else:
            Path(GlobalVar["FolderTemp"], "Pause").touch()



    #========================================================================
    def WorkPauseExt(self, value):
        """Fonction de gestion de la pause du logiciel via la création ou la suppression d'un fichier Pause depuis l'extérieur du soft."""
        ### Regarde la valeur à appliquer et l'état actuel du bouton
        if (value and not self.PauseButton.isChecked()) or (not value and self.PauseButton.isChecked()):
            ## Bloque les signaux du bouton
            self.PauseButton.blockSignals(True)

            ## Change l'état du bouton
            self.PauseButton.toggle()

            ## Débloque les signaux du bouton
            self.PauseButton.blockSignals(False)


            ## Debug mode
            if GlobalVar["Verbose"] == 3:
                # Fichier détécté
                if value:
                    print(QCoreApplication.translate("ProgressDialog", "A Pause file has been detected."), file=sys.stdout)

                # Fichier supprimé
                else:
                    print(QCoreApplication.translate("ProgressDialog", "A Pause file has been deleted."), file=sys.stdout)



    #========================================================================
    def WorkProgression(self, value):
        """Fonction de progression de la barre."""
        ### Envoie de la valeur
        self.ProgressBar.setValue(value)


        ### Force la mise à jour graphique
        QCoreApplication.processEvents()



    #========================================================================
    def Next(self, value):
        """Fonction lancée en fin de conversion des images en textes."""
        ### En cas de custom color à faire sur les fichiers non reconnus
        if GlobalVar["MD5Dico"] and GlobalVar["RoundNumber"] == 1 and GlobalVar["CustomColors"] == 1:
            GlobalVar["RoundNumber"] = 2

            ## Modifications graphiques
            self.ProgressBar.setMaximum(0)
            self.ProgressBar.setValue(0)
            self.ProgressLabel.setText(QCoreApplication.translate("ProgressDialog", "Extraction of the images texts in progress..."))
            self.PauseButton.setEnabled(False)
            self.StopButton.setEnabled(False)

            ## Démarrage du thread
            GlobalVar["ExtractionThread"].start()


        ### Si c'est bon, on peut fermer
        else:
            ## Debug mode
            if GlobalVar["Verbose"] == 3:
                print(value, file=sys.stdout)

            ## Fermeture via validation de la fenêtre de progression
            self.accept()

            ## Lacement de la dialogue des textes non reconnus.
            GlobalVar["CheckTextDialog"] = CheckTextDialog(None)



    #========================================================================
    def MaxValue(self):
        """Renvoie la valeur maximale de la barre."""
        return self.ProgressBar.maximum()



    #========================================================================
    def Stop(self):
        """Fonction d'arrêt du logiciel si on ferme la fenêtre de progression."""
        ### Nettoyage du QThread ayant géré la conversion
        GlobalVar["MonProgressThread"].shutdown()


        ### En cas de travail annulé
        QuitError(QCoreApplication.translate("ProgressDialog", "The work has been canceled."))



#############################################################################
class ExtractionThread(QThread):
    """QThread d'extraction des images."""
    ### Signal indiquant la fin du travail
    ExtractionFinished = pyqtSignal()


    def __init__(self):
        super().__init__()


    def run(self):
        """Le QThread permet de ne pas bloquer la fenêtre de progression."""
        ### Pour le premier tour
        if GlobalVar["RoundNumber"] == 1:
            ## Pour la version couleurs perso
            if GlobalVar["CustomColors"] == 2:
                GlobalVar["TotalSubtitles"] = subp2pgm(True)

            ## Pour la version des couleurs par défaut
            else:
                GlobalVar["TotalSubtitles"] = subp2pgm(False)

        ### Pour le 2e tour
        else:
            GlobalVar["TotalSubtitles"] = subp2pgm(True)


        ### Envoie de l'info de fin de taf
        self.ExtractionFinished.emit()



#############################################################################
class ProgressThread(QThread):
    """QThread de conversion des images en textes."""
    ### Signaux et variable blo
    ## Création d'un nouveau signal pour informer de la fin du thread
    FinDuThread = pyqtSignal(str)

    ## Création d'un nouveau signal pour info du % d'avancement
    ProgDuThread = pyqtSignal(float)

    ## Création d'un nouveau signal en cas de pause extérieure
    PauseDuThread = pyqtSignal(bool)

    ## Création d'un nouveau signal en cas de stop extérieure
    KillDuThread = pyqtSignal()


    #========================================================================
    def __init__(self):
        super().__init__()


    #========================================================================
    def shutdown(self):
        """Fonction de nettoyage lancée lors de la fermeture de la fenêtre de progression ou de la création d'un fichier Stop."""
        ### Suppression du fichier de pause s'il existe pour ne rien bloquer
        if Path(GlobalVar["FolderTemp"], "Pause").exists():
            Path(GlobalVar["FolderTemp"], "Pause").unlink()


        ### Si la fenêtre de progression est toujours visible, envoie d'une demande de fermeture
        if GlobalVar["ProgressDialog"].isVisible():
            self.FinDuThread.emit(QCoreApplication.translate("ProgressThread", "A Stop file has been detected."))


        ### Variable bloquante servant aux commandes en cours d'exécution
        self.abort = True


        ### Annulation du travail restant
        for f in self.WorkList:
            f.cancel()

        self.pool.shutdown(wait=True)



    #========================================================================
    def run(self):
        """Fonction lancée lors de l'exécution du QThread."""
        ### Création de variables pour le QThread
        ## Valeur de progression
        self.done = 0

        ## Variable bloquante
        self.abort = False


        ### Création de la liste de travail
        self.WorkList = []
        self.pool = ThreadPoolExecutor(max_workers=QThread.idealThreadCount())


        ### Remplissage de la liste
        for ImageFile in GlobalVar["SubImgFiles"]:
            ## Chaque commande créée lance la fonction self.Work avec l'argument ImageFile
            future = self.pool.submit(self.Work, ImageFile)

            ## Ajout de la commande à la liste de travail
            self.WorkList.append(future)



    #========================================================================
    def MD5Dico(self, ImageFile):
        """Fonction de création des Hash et de leur gestion pour reconnaître les doublons."""
        ### Uniquement en 1er tour
        if GlobalVar["RoundNumber"] == 1:
            ## Hash le fichier
            FileHash = bytes(QCryptographicHash.hash(ImageFile.open("rb").read(), QCryptographicHash.Md5).toHex()).decode('utf-8')

            ## Si le FileHash existe déjà, c'est une image doublon, on l'ajoute à la liste du hash
            if FileHash in GlobalVar["MD5Dico"].keys():
                GlobalVar["MD5Dico"][FileHash].append(ImageFile)

            ## Si le FileHash n'existe pas, ajout d'une nouvelle paire FileHash : fichier
            else:
                GlobalVar["MD5Dico"][FileHash] = [ImageFile]



    #========================================================================
    def Work(self, File):
        """Fonction exécutée pour chaque image à convertir."""
        ### Si la variable bloquante est active, c'est que la fenêtre est fermée ou un fichier stop est présent
        if self.abort:
            return


        ### En cas d'annulation du travail via un fichier extérieur
        if Path(GlobalVar["FolderTemp"], "Stop").exists():
            self.KillDuThread.emit()
            return


        ### En cas de mise en pause via la présence d'un fichier Pause
        if Path(GlobalVar["FolderTemp"], "Pause").exists():
            ## Envoie de l'info de mise en pause
            self.PauseDuThread.emit(True)

            ## Bloque le thread en cours
            while Path(GlobalVar["FolderTemp"], "Pause").exists():
                # En cas d'annulation du travail via un fichier extérieur
                if Path(GlobalVar["FolderTemp"], "Stop").exists():
                    self.KillDuThread.emit()
                    return

                else:
                    self.wait(500)

            ## Envoie de la reprise du travail
            self.PauseDuThread.emit(False)


        ### Reconnaissance de l'image suivante
        Reply = LittleProcess('tesseract -l {0} --tessdata-dir "{2}" "{1}" "{1}"'.format(GlobalVar["TesseractLanguage"], File, GlobalVar["TesseractFolder"]))


        ### Debug mode
        if GlobalVar["Verbose"] == 3:
            print(QCoreApplication.translate("ProgressThread", "Reply of the convertion of {}: {}").format(File, Reply), file=sys.stdout)


        ### Gestion des Hash
        ## Variables
        ImageFile = Path(File)
        TxtFile = Path("{}.txt".format(ImageFile))

        ## S'il y plus d'un retour de Tesseract
        if len(Reply) > 1:
            # S'il y a "Empty page" ou "diacritics" dans le retour de Tesseract
            if "Empty page" in Reply[1] or "diacritics" in Reply[1]:
                self.MD5Dico(File)

        ## Si le fichier texte obtenu est vide
        elif TxtFile.stat().st_size == 0:
            self.MD5Dico(File)


        ### Progression du travail
        self.done += 1
        MaxValue = GlobalVar["ProgressDialog"].MaxValue()


        ## Progression graphique
        self.ProgDuThread.emit(self.done)

        ## Progression console
        if GlobalVar["GuiLevel"] < 2:
            print("{}/{}".format(self.done, MaxValue))

        ## Envoie d'infos en mode gui
        elif GlobalVar["Verbose"] == 3:
            print(QCoreApplication.translate("ProgressThread", "{} / {} files done.".format(self.done, MaxValue)), file=sys.stdout)


        ### Si c'était le dernier fichier à traiter
        if self.done == MaxValue:
            GlobalVar["Ctrl+C"] = True
            self.FinDuThread.emit(QCoreApplication.translate("ProgressThread", "The conversion is finished."))



#############################################################################
class CheckTextDialog(QDialog):
    """Fenêtre de vérification des textes."""
    def __init__(self, Parent=None):
        super().__init__(Parent)


        ### Fenêtre en elle-même
        self.setMinimumHeight(275)
        self.setMinimumWidth(525)
        self.setWindowFlags(Qt.WindowTitleHint)
        self.setWindowTitle("{} v{}".format(QCoreApplication.applicationName(), QCoreApplication.applicationVersion()))
        self.rejected.connect(lambda: QuitError(QCoreApplication.translate("CheckTextDialog", "The check of the texts was canceled.")))
        self.setAttribute(Qt.WA_DeleteOnClose)


        ### Texte d'explication
        Label = QLabel(self)
        Label.setAlignment(Qt.AlignCenter)


        ### Afficheur des images
        self.ImageViewer = QLabel(self)
        self.ImageViewer.setMinimumHeight(70)
        self.ImageViewer.setAlignment(Qt.AlignCenter)


        ### Barre de progression et de sélection
        self.ImageProgress = QSliderCustom()
        self.ImageProgress.setOrientation(Qt.Horizontal)
        self.ImageProgress.setMinimum(0)
        self.ImageProgress.setSingleStep(1)
        self.ImageProgress.setPageStep(1)
        self.ImageProgress.setTickInterval(1)
        self.ImageProgress.setTickPosition(QSlider.TicksBothSides)
        self.ImageProgress.valueChanged.connect(lambda: (self.TextUpdate(), self.IMGSlide()))

        ColorConfig = QPushButton(QIcon.fromTheme("configure", QIcon(":/img/configure.svg")), "")
        ColorConfig.setToolTip(QCoreApplication.translate("CheckTextDialog", "Customize the colors."))
        ColorConfig.clicked.connect(lambda: CustomizeDialog("CheckTextDialog"))


        ### Zone de texte de traduction
        self.ImageTranslate = QPlainTextEdit(self)


        ### Bouton image précédente
        self.ImagePrevious = QPushButton(QIcon.fromTheme("go-previous", QIcon(":/img/go-previous.svg")), QCoreApplication.translate("CheckTextDialog", "Previous image"), None)
        self.ImagePrevious.clicked.connect(lambda: (self.TextUpdate(), self.IMGViewer(-1)))


        ### Bouton terminé
        self.ImageFinish = QPushButton(QIcon.fromTheme("dialog-ok-apply", QIcon(":/img/dialog-ok-apply.svg")), QCoreApplication.translate("CheckTextDialog", "Finish"), None)
        self.ImageFinish.setToolTip(QCoreApplication.translate("CheckTextDialog", "Now, creation of the SRT file."))
        self.ImageFinish.clicked.connect(lambda: (self.TextUpdate(), self.Next()))


        ### Bouton image suivante
        self.ImageNext = QPushButton(QIcon.fromTheme("go-next", QIcon(":/img/go-next.svg")), QCoreApplication.translate("CheckTextDialog", "Next image"), None)
        self.ImageNext.setLayoutDirection(Qt.RightToLeft)
        self.ImageNext.clicked.connect(lambda: (self.TextUpdate(), self.IMGViewer(1)))


        ### Organisation de la fenêtre
        HLayout1 = QHBoxLayout(None)
        HLayout1.addWidget(self.ImageProgress)
        HLayout1.addWidget(ColorConfig)

        HLayout2 = QHBoxLayout(None)
        HLayout2.addWidget(self.ImagePrevious)
        HLayout2.addStretch()
        HLayout2.addWidget(self.ImageFinish)
        HLayout2.addStretch()
        HLayout2.addWidget(self.ImageNext)

        VLayout = QVBoxLayout(None)
        VLayout.addWidget(Label)
        VLayout.addWidget(self.ImageViewer)
        VLayout.addLayout(HLayout1)
        VLayout.addWidget(self.ImageTranslate)
        VLayout.addLayout(HLayout2)

        self.setLayout(VLayout)


        ###############################################
        ### Conversion des images en texte manuelle ###
        ###############################################
        ### Si le dico contient des fichiers à reconnaître manuellement
        if GlobalVar["MD5Dico"] and GlobalVar["GuiLevel"]:
            ## Debug mode
            if GlobalVar["Verbose"] >= 2:
                print(QCoreApplication.translate("CheckTextDialog", "Need to check texts"), file=sys.stdout)

                if GlobalVar["Verbose"] == 3:
                    for key, value in GlobalVar["MD5Dico"].items():
                        print(key, "=", value, file=sys.stdout)


            ## Variables
            GlobalVar["RecognizedNumber"] = 0 # Numero du sous titre à reconnaître
            GlobalVar["RecognizedTotal"] = len(GlobalVar["MD5Dico"]) # Nombre de sous-titres uniques à traiter


            ## Debug mode
            if GlobalVar["Verbose"] == 3:
                print(QCoreApplication.translate("CheckTextDialog", "Creation of the check dialog."), file=sys.stdout)


            self.ImageProgress.setMaximum(GlobalVar["RecognizedTotal"] - 1)
            x = GlobalVar["RecognizedTotal"]

            if GlobalVar["CustomColors"] == 1:
                Label.setText(QCoreApplication.translate("CheckTextDialog", "%n subtitle(s) file(s) were not recognized or diacritic were detected.\nThe files converted with the custom colors are present too with their texts.\nCheck or write manually this text(s).", "%n is the number of subtitle", x))

            else:
                Label.setText(QCoreApplication.translate("CheckTextDialog", "%n subtitle(s) file(s) were not recognized or diacritic were detected.\nCheck or write manually this text(s).", "%n is the number of subtitle", x))


            ### Affichage de la 1ere image
            self.IMGViewer(0)
            self.show()

        else:
            self.Next()


    #========================================================================
    def IMGViewer(self, change):
        """Fonction de gestion de conversion manuelle des sous titres."""
        ### Mise à jour des variables
        Var = GlobalVar["RecognizedNumber"] + change
        GlobalVar["RecognizedNumber"] = Var # Mise à jour du numéro à traiter (0 , +1, -1)
        md5Key = list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]] # Récupération d'une clé
        img = GlobalVar["MD5Dico"][md5Key][0] # Sélectionne la 1ere image de la clé
        NbImg = len(GlobalVar["MD5Dico"][md5Key])
        txt = Path("{}.txt".format(img)) # Adresse du fichier texte


        ### Affichage de l'image
        self.ImageViewer.setPixmap(QPixmap(str(img)))
        self.ImageViewer.setToolTip(QCoreApplication.translate("CheckTextDialog", "%n file(s) with the hash: {}.", "%n is the number of subtitle with the same hash.", NbImg).format(md5Key))


        ### Progression du travail
        self.ImageProgress.setSliderPosition(GlobalVar["RecognizedNumber"])


        ### Modifications graphiques
        if GlobalVar["RecognizedNumber"] + 1 == GlobalVar["RecognizedTotal"]:
            ## Blocage du bouton suivant
            self.ImageNext.setEnabled(False)

        else:
            ## Déblocage du bouton suivant
            self.ImageNext.setEnabled(True)

        if GlobalVar["RecognizedNumber"] == 0:
            ## Blocage du bouton précédant
            self.ImagePrevious.setEnabled(False)
        else:
            ## Déblocage du bouton précédant
            self.ImagePrevious.setEnabled(True)


        ### Si le fichier texte n'est plus vide (en cas de retour en arrière)
        if txt.stat().st_size > 0:
            with txt.open("r") as SubFile:
                text = SubFile.read().strip()
                self.ImageTranslate.setPlainText(text)


        ### Donne le focus au widget texte et sélectionne le texte
        self.ImageTranslate.setFocus()
        self.ImageTranslate.selectAll()



    #========================================================================
    def IMGSlide(self):
        """Fonction de changement de l'image via le curseur de progression."""
        ### Récupération du numéro de l'image
        Value = self.ImageProgress.value() - GlobalVar["RecognizedNumber"]


        ### Affichage de l'image
        self.IMGViewer(Value)



    #========================================================================
    def TextUpdate(self):
        """Fonction d'écriture du texte de la conversion manuelle des sous-titres."""
        ### Récupération du texte et de la clé
        SubText, md5Key = self.ImageTranslate.toPlainText(), list(GlobalVar["MD5Dico"].keys())[GlobalVar["RecognizedNumber"]]


        ### Si le texte n'est pas vide, on met à jour les fichiers txt
        if SubText:
            ## Traite les images ayant le même md5
            for ImgFile in GlobalVar["MD5Dico"][md5Key]:
                with open("{}.txt".format(ImgFile), "w") as SubFile:
                    SubFile.write(SubText)

            ## Mise au propre du texte
            self.ImageTranslate.clear()



    #========================================================================
    def Next(self):
        """Fonction de création du fichier SRT en combinant les textes traduits."""
        ### Création du fichier SRT
        LittleProcess('"{}" -s -w -t srt -i "{}.xml" -o "{}"'.format(GlobalVar["subptools"], GlobalVar["Generic"], GlobalVar["SRT"]))


        ### Si le fichier SRT existe
        if GlobalVar["SRT"].exists():
            ## Si le fichier SRT est vide
            if GlobalVar["SRT"].stat().st_size == 0:
                QuitError(QCoreApplication.translate("CheckTextDialog", "SRT file is empty."))

            ## Indique que tout est ok
            if GlobalVar["Verbose"] > 0:
                print(QCoreApplication.translate("CheckTextDialog", "The SRT file is created."), file=sys.stdout)

            ## Ouverture automatique du fichier srt créé
            if GlobalVar["SRTOpen"]:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(GlobalVar["SRT"])))

            ## Fermeture de la fenêtre
            GlobalVar["ExitCode"] = 0
            self.accept()

        ### Si le fichier SRT n'existe pas
        else:
            QuitError(QCoreApplication.translate("CheckTextDialog", "SRT file isn't created."))




#############################################################################
def subp2pgm(Value):
    """Fonction d'extraction des images textes."""
    ### Création d'un fichier IDX maison
    if Value and GlobalVar["ColorsToUse"]:
        ### Debug mode
        if GlobalVar["Verbose"] >= 2:
            print(QCoreApplication.translate("main", "Customization of the color of the images text"), file=sys.stdout)


        ### Suppression du fichier temporaire s'il existe déjà
        if GlobalVar["IDXTemp"].exists():
            GlobalVar["IDXTemp"].unlink()


        ### Lit le fichier idx original ligne par ligne et renvoie le tout (ligne + la ligne modifiée) dans un nouveau fichier, permet une meilleur détection des textes
        CustomColors = False

        with GlobalVar["IDX"].open("r") as fichier_idx:
            with GlobalVar["IDXTemp"].open("w") as new_fichier_idx:
                for ligne in fichier_idx:
                    if "custom colors:" in ligne:
                        new_fichier_idx.write(GlobalVar["ColorsToUse"] + "\n")
                        CustomColors = True

                    else:
                        new_fichier_idx.write(ligne)

        ## S'il n'y avait pas de ligne custom colors
        if not CustomColors:
            var = False
            with GlobalVar["IDX"].open("r") as fichier_idx:
                with GlobalVar["IDXTemp"].open("w") as new_fichier_idx:
                    for ligne in fichier_idx:
                        if var:
                            new_fichier_idx.write(GlobalVar["ColorsToUse"] + "\n")
                            var = False

                        else:
                            if "palette:" in ligne:
                                var = True

                            new_fichier_idx.write(ligne)


    ### Copie des fichiers IDX et SUB
    else:
        copyfile(str(GlobalVar["IDX"]), str(GlobalVar["IDXTemp"]))


    ### Déplacement dans le dossier temporaire
    copyfile(str(GlobalVar["SUB"]), str(GlobalVar["SUBTemp"]))


    ### Extraction des images depuis le fichier SUB
    ## Création de la liste des images, récupération du nombre de sous-titres créé
    TotalSubtitles = int(LittleProcess('"{}" -n "{}"'.format(GlobalVar["subp2pgm"], GlobalVar["Generic"]))[0].split(" ")[0])


    if GlobalVar["Verbose"]:
        if Value:
            print(QCoreApplication.translate("main", "%n file(s) generated with custom colors.", "%n is the number of images by subp2pgm", TotalSubtitles), file=sys.stdout)

        else:
            print(QCoreApplication.translate("main", "%n file(s) generated.", "%n is the number of images by subp2pgm", TotalSubtitles), file=sys.stdout)


    ### Renvoie le nombre d'images extrait
    return TotalSubtitles




#############################################################################
def LittleProcess(Command):
    """Petite fonction récupérant les retours de process simples."""
    ### Liste qui contiendra les retours
    Reply = []


    ### Debug mode
    if GlobalVar["Verbose"] >= 2:
        print(QCoreApplication.translate("main", "Execution of: {}".format(Command)), file=sys.stdout)


    ### Création du QProcess avec unification des 2 sorties (normale + erreur)
    process = QProcess()
    process.setProcessChannelMode(1)


    ### Lance et attend la fin de la commande
    process.start(Command)
    process.waitForFinished()


    ### Ajoute les lignes du retour dans la liste
    for line in bytes(process.readAllStandardOutput()).decode('utf-8').splitlines():
        Reply.append(line)



    ### Renvoie le résultat
    return Reply



#############################################################################
def ErrorMessages(Message):
    """Fonction affichant le message d'erreur dans une fenêtre ou en console."""
    if GlobalVar["GuiLevel"] == 2:
        QMessageBox.critical(None, QCoreApplication.translate("main", "Error Message"), Message)

    else:
        print(QCoreApplication.translate("main", "Error Message: {}").format(Message), file=sys.stderr)



#############################################################################
def QuitError(Text):
    """Fonction de fermeture du logiciel avec message d'erreur."""
    ### Code d'erreur de sortie
    GlobalVar["ExitCode"] = 1


    ### Suppression du dossier temporaire automatique
    if GlobalVar["AutoTempOverwrite"]:
        if GlobalVar["FolderTempWidget"] and not GlobalVar["FolderTempWidget"].remove():
            ErrorMessages(QCoreApplication.translate("main", "The temporary folder was not deleted."))


    ### Affichage du message d'erreur
    ErrorMessages(Text)


    ### Arrêt de Qtesseract5
    Qtesseract5.exit()



#############################################################################
def LanguageChanged(Value):
    """Fonction appelée via la combobox de la langue du soft ou au début du script qui recharge les traductions et qui va lancé QEvent.LanguageChange."""
    ### Suppression de la traduction
    Qtesseract5.removeTranslator(GlobalVar["QTranslator"])

    ### Version US
    if Value in (0, "en"):
        ## Mise à jour du fichier langage de Qt
        if GlobalVar["QTranslator"].load("qt_en_EN", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])

        if GlobalVar["QTranslator"].load("qt_en", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])
        ## Pour la trad anglaise
        find = GlobalVar["QTranslator"].load("Qtesseract5_en_EN", str(GlobalVar["FolderLang"]))

        # Si le fichier n'a pas été trouvé, affiche une erreur et utilise la version anglaise
        if not find:
            QMessageBox(3, "Erreur de traduction", "Aucun fichier de traduction <b>française</b> trouvé.<br/>Utilisation de la langue <b>anglaise</b>.", QMessageBox.Close, None, Qt.WindowSystemMenuHint).exec()

        # Chargement de la traduction
        else:
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])


    ### Version FR
    elif Value in (1, "fr"):
        ## Mise à jour du fichier langage de Qt
        if GlobalVar["QTranslator"].load("qt_fr_FR", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])

        if GlobalVar["QTranslator"].load("qt_fr", QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])

        ## Pour la trad française
        find = GlobalVar["QTranslator"].load("Qtesseract5_fr_FR", str(GlobalVar["FolderLang"]))

        # Si le fichier n'a pas été trouvé, affiche une erreur et utilise la version anglaise
        if not find:
            QMessageBox(3, "Erreur de traduction", "Aucun fichier de traduction <b>française</b> trouvé.<br/>Utilisation de la langue <b>anglaise</b>.", QMessageBox.Close, None, Qt.WindowSystemMenuHint).exec()

        # Chargement de la traduction
        else:
            Qtesseract5.installTranslator(GlobalVar["QTranslator"])



#############################################################################
if __name__ == '__main__':
    ####################
    ### QApplication ###
    ####################
    Qtesseract5 = QApplication(sys.argv)
    Qtesseract5.setApplicationVersion("2.2") # Version de l'application
    Qtesseract5.setApplicationName("Qtesseract5") # Nom de l'application
    Qtesseract5.setWindowIcon(QIcon.fromTheme("qtesseract5", QIcon(":/img/qtesseract5.png"))) # Icône de l'application

    ClipBoard = QApplication.clipboard()
    ClipBoard.clear(mode=ClipBoard.Clipboard)


    ### Dictionnaires permettant de mettre en avant certains widgets
    PalettesWigets = {}
    PalettesWigets["LineEdit"] = QPalette()
    brush = QBrush(QColor(255, 255, 125))
    brush.setStyle(Qt.SolidPattern)
    PalettesWigets["LineEdit"].setBrush(QPalette.Active, QPalette.Base, brush)
    brush = QBrush(QColor(0, 0, 0))
    brush.setStyle(Qt.SolidPattern)
    PalettesWigets["LineEdit"].setBrush(QPalette.Active, QPalette.ToolTipText, brush)
    brush = QBrush(QColor(255, 255, 255))
    brush.setStyle(Qt.SolidPattern)
    PalettesWigets["LineEdit"].setBrush(QPalette.Active, QPalette.ToolTipBase, brush)


    ### Dictionnaire contenant toutes les variables
    GlobalVar = {}
    GlobalVar["IDX"] = None
    GlobalVar["SRT"] = None
    GlobalVar["TesseractFolder"] = None
    GlobalVar["TesseractLangs"] = []
    GlobalVar["FolderTempWidget"] = None
    GlobalVar["NoDialog"] = False
    GlobalVar["FolderTempWait"] = True
    GlobalVar["FolderTesseractWait"] = True
    GlobalVar["RoundNumber"] = None
    GlobalVar["ProgressDialog"] = None


    ###################
    ### Traductions ###
    ###################
    ### Création des valeurs
    GlobalVar["Lang"] = QLocale().name().split("_")[0]
    GlobalVar["QTranslator"] = QTranslator() # Création d'un QTranslator
    GlobalVar["FolderLang"] = Path(sys.argv[0]).resolve().parent # Dossier des traductions


    LanguageChanged(GlobalVar["Lang"])



    ########################
    ### Parser de config ###
    ########################
    ### Création des options
    COption = QCommandLineOption(["C", "colors"], QCoreApplication.translate("main", "Colors to use for the custom-colors"), QCoreApplication.translate("main", "Custom Colors"), "custom colors: ON, tridx: 0000, colors: 000000, ffffff, 000000, 000000")
    cOption = QCommandLineOption(["c", "custom-colors"], QCoreApplication.translate("main", "Colors of the images texts.\n\
Level 0: No use custom colors\n\
Level 1: Use custom colors on images not recognized\n\
Level 2: Use only customs colors"), QCoreApplication.translate("main", "Level"), "1")
    gOption = QCommandLineOption(["g", "gui-level"], QCoreApplication.translate("main", "Level of the gui.\n0: No window at all.\n1: Only check texts window.\n2: All windows."), QCoreApplication.translate("main", "Level"), "2")
    langOption = QCommandLineOption(["lang"], QCoreApplication.translate("main", "Language of the soft (en or fr), use the language of the system by default."), QCoreApplication.translate("main", "Lang"), GlobalVar["Lang"])
    oOption = QCommandLineOption(["o", "open"], QCoreApplication.translate("main", "Automatically open the SRT file created."), "", "False")
    wOption = QCommandLineOption(["w", "overwrite"], QCoreApplication.translate("main", "Overwrite the SRT output file."), "", "False")
    LOption = QCommandLineOption(["L", "tesseract-folder"], QCoreApplication.translate("main", "Folder contains the languages for Tesseract."), QCoreApplication.translate("main", "Folder"), "")
    lOption = QCommandLineOption(["l", "tesseract-language"], QCoreApplication.translate("main", "Language to use for Tesseract, language system by default."), QCoreApplication.translate("main", "Lang"), str(QLocale().system().language()))
    fOption = QCommandLineOption(["f", "temporary-folder"], QCoreApplication.translate("main", "Folder in which temporary files will be stored."), QCoreApplication.translate("main", "Folder"), "")
    rOption = QCommandLineOption(["r", "temporary-remove"], QCoreApplication.translate("main", "Automatically remove the temporary folder (True by default).\nBe Careful if it's a personal folder."), "", "True")
    tOption = QCommandLineOption(["t", "thread"], QCoreApplication.translate("main", "Number of thread (cpu) to use simultaneous, max value by default."), QCoreApplication.translate("main", "Number"), str(QThread.idealThreadCount()))
    vOption = QCommandLineOption(["v", "verbose"], QCoreApplication.translate("main", "Verbose mode for debug.\n\
Level 0: Errors messages\n\
Level 1: Level 0, Number of images files created, Temporary folder path, Conversion progress, by default\n\
Level 2: Level 1, Commands Lines, Tesseract languages, Options values, Custom color, Conversion started, Check texts needed, SRT file created\n\
Level 3: Level 2, Convert files names, Dialog creation info, Progress dialod ended, List of the texts to check"), QCoreApplication.translate("main", "Level"), "1")
    VOption = QCommandLineOption(["V", "version"], QCoreApplication.translate("main", "Version of the soft."), "", "False")

    ### Création du parser
    parser = QCommandLineParser()
    parser.setApplicationDescription(QCoreApplication.translate("main", "This software convert a IDX/SUB file in SRT (text) file with Tesseract, subp2pgm and subptools."))
    parser.addHelpOption()
    parser.addOption(COption)
    parser.addOption(cOption)
    parser.addOption(gOption)
    parser.addOption(langOption)
    parser.addOption(oOption)
    parser.addOption(wOption)
    parser.addOption(LOption)
    parser.addOption(lOption)
    parser.addOption(fOption)
    parser.addOption(rOption)
    parser.addOption(tOption)
    parser.addOption(vOption)
    parser.addOption(VOption)
    parser.addPositionalArgument(QCoreApplication.translate("main", "source"), QCoreApplication.translate("main", "Source IDX file to convert."))
    parser.addPositionalArgument(QCoreApplication.translate("main", "destination"), QCoreApplication.translate("main", "Destination SRT file converted."))
    parser.process(Qtesseract5)



    ##################################
    ### Récupération des arguments ###
    ##################################
    ### Langue
    Value = parser.value(langOption)

    if Value in ("en", "fr") and Value != GlobalVar["Lang"]:
        GlobalVar["Lang"] = parser.value(langOption)
        LanguageChanged(GlobalVar["Lang"])


    ### Version du soft
    if parser.isSet(VOption):
        print(QCoreApplication.translate("main", "{} v{} by Hizoka <hizo@free.fr>".format(QCoreApplication.applicationName(), QCoreApplication.applicationVersion())), file=sys.stdout)
        sys.exit(0)


    ### Mode gui
    GlobalVar["GuiLevel"] = int(parser.value(gOption))


    ### Nombre de cpu à utiliser
    GlobalVar["NbCPU"] = int(parser.value(tOption))


    ### Ouverture automatique du fichier srt
    GlobalVar["SRTOpen"] = parser.isSet(oOption)
    GlobalVar["AutoSRTOverwrite"] = parser.isSet(wOption)


    ### Mode verbose
    GlobalVar["Verbose"] = int(parser.value(vOption))


    ### Mode custom color
    GlobalVar["CustomColors"] = int(parser.value(cOption))
    GlobalVar["ColorsToUse"] = parser.value(COption)


    ### Dossier temporaire
    GlobalVar["FolderTemp"] = parser.value(fOption)
    GlobalVar["AutoTempOverwrite"] = not parser.isSet(rOption) # La valeur étant positive par défaut, il faut inverser la valeur, si -r => false


    ### Langue à utiliser
    GlobalVar["TesseractFolder"] = parser.value(LOption)

    try:
        ## Si la valeur est un numéro de langue
        GlobalVar["TesseractLanguage"] = LangCodes[int(parser.value(lOption))]

    except:
        ## Si la valeur est une abréviation de langue en 2 lettres
        if len(parser.value(lOption)) == 2:
            GlobalVar["TesseractLanguage"] = LangCodes.get(parser.value(lOption), "osd")

        ## Si c'est en 3 lettres, on vérifie son existence
        elif parser.value(lOption) in LangCodes:
            GlobalVar["TesseractLanguage"] = parser.value(lOption)

        ## Si la valeur n'est pas connue, on lui donne la valeur par défaut osd
        else:
            GlobalVar["TesseractLanguage"] = "osd"


    ### Récupération des arguments
    NbArg = len(parser.positionalArguments())

    for Arg in parser.positionalArguments():
        Arg = Path(Arg)

        ## Vérifie que le fichier donné est bien un fichier IDX
        if Arg.suffix in (".idx", ".IDX"):
            GlobalVar["IDX"] = Arg.resolve()

        ## Si le fichier est de type SUB, ça passe encore
        elif Arg.suffix in (".sub", ".SUB"):
            GlobalVar["IDX"] = Arg.with_suffix(".idx").resolve()

        ## Dans le cas de l'utilisation d'un argument pour le fichier SRT de sortie
        elif Arg.suffix in (".srt", ".SRT"):
            GlobalVar["SRT"] = Arg

            # Crée l'adresse absolue du SRT si besoin
            if not GlobalVar["SRT"].is_absolute():
                GlobalVar["SRT"] = Path(Path().resolve(), GlobalVar["SRT"])


    if GlobalVar["IDX"] and GlobalVar["IDX"].is_file() and not GlobalVar["SRT"]:
        GlobalVar["SRT"] = GlobalVar["IDX"].with_suffix(".srt")




    ###############################################
    ### Recherche les 3 exécutables nécessaires ###
    ###############################################
    ### Boucle testant les exécutables
    for executable in ["tesseract", "subp2pgm", "subptools"]:
        ## Recherche les exécutables
        if not QStandardPaths.findExecutable(executable) and not QStandardPaths.findExecutable(executable, [str(GlobalVar["FolderLang"])]):
            # Stoppe le soft si l'executable n'existe pas
            QuitError(QCoreApplication.translate("main", "The {} executable isn't founded.").format(executable))

        ## Définit les adresses des exécutables
        x = QStandardPaths.findExecutable(executable)
        y = QStandardPaths.findExecutable(executable, [str(GlobalVar["FolderLang"])])

        ## Définit l'adresse du programme
        if x:
            GlobalVar[executable] = x

        elif y:
            GlobalVar[executable] = y



    ###################################
    ### Fenêtre de config et config ###
    ###################################
    ### Création de la fenêtre de config
    GlobalVar["ConfigDialog"] = ConfigDialog(None)
    GlobalVar["ConfigDialog"].setAttribute(Qt.WA_DeleteOnClose)


    ### Exécution de l'application
    Qtesseract5.exec()


    ### Permet d'éviter les fameux Erreur de segmentation (core dumped)
    QCoreApplication.processEvents()


    ### Suppression du dossier temporaire automatique
    if GlobalVar["AutoTempOverwrite"]:
        if GlobalVar["FolderTempWidget"] and not GlobalVar["FolderTempWidget"].remove():
            ErrorMessages(QCoreApplication.translate("main", "The temporary folder was not deleted."))


    ### Ferme le code python
    sys.exit(GlobalVar["ExitCode"])
